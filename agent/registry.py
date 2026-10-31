"""The single boundary around every model- and code-initiated tool call.

The registry validates both sides of a call, derives stable write keys, applies a
fail-closed hook, retries only failures known to be transient, and records one
summary line in the session trace.  A tool failure is data: callers always receive
the same ``ok/output/is_error/error`` shape instead of an exception.
"""

from __future__ import annotations

import copy
import hashlib
import json
import time
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Callable

from harness.schema import errors as schema_errors

MODEL, CODE, OPERATOR = "model", "code", "operator"
CALLERS = (MODEL, CODE, OPERATOR)


class TransientToolError(RuntimeError):
    """A read or a definitely pre-dispatch write failure that is safe to retry."""


class AmbiguousToolError(RuntimeError):
    """A write may have committed, so the registry must not retry it blindly."""


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict
    fn: Callable[..., dict]
    callers: tuple[str, ...] = (MODEL,)       # who may call it: the tool table's "who may call it"
    credential: str = "sandbox, read only"    # the narrowest scope; the tool table's credential column
    writes: bool = False                      # a write gets a key
    result_bound: str = ""                    # e.g. "50 rows"; the tool table's result bound
    model_visible: dict = field(default_factory=dict)
    result_schema: dict = field(default_factory=dict)
    validate_args: Callable[[dict], list[str]] | None = None
    retryable: Callable[[Exception], bool] | None = None
    key_fields: tuple[str, ...] = ()           # effect identity only; never prose written by the model


class Registry:
    def __init__(
        self,
        specs: list[ToolSpec],
        *,
        pre_call_hook: Callable[..., bool | None] | None = None,
        max_retries: int = 2,
        backoff_base_s: float = 0.05,
        sleep: Callable[[float], None] = time.sleep,
        key_context: str | None = None,
        trace=None,
    ):
        names = [s.name for s in specs]
        if len(names) != len(set(names)):
            raise ValueError("tool names must be unique")
        if max_retries < 0:
            raise ValueError("max_retries must be zero or greater")
        self._ordered = tuple(specs)
        self._specs = {s.name: s for s in specs}
        self._pre_call_hook = pre_call_hook or (lambda **_: True)
        self._max_retries = max_retries
        self._backoff_base_s = max(0.0, float(backoff_base_s))
        self._sleep = sleep
        self._key_context = key_context or "unbound"
        self._trace = trace

    def definitions(self) -> list[dict]:
        """What the model sees, in the same order on every request (slide 28)."""
        definitions = []
        for spec in self._ordered:
            if MODEL not in spec.callers:
                continue
            definition = {
                "name": spec.name,
                "description": spec.description,
                "input_schema": copy.deepcopy(spec.input_schema),
            }
            definition.update(copy.deepcopy(spec.model_visible))
            definitions.append(definition)
        return definitions

    def call(self, name: str, args: dict, caller: str, *, step: str | None = None,
             trace_step: int | None = None) -> dict:
        """Validate, authorize, execute and record one call without leaking an exception.

        ``step`` is a program-owned plan/checkpoint identifier.  It is used in a
        write key when present; otherwise only a spec's explicitly named
        ``key_fields`` contribute to effect identity. ``trace_step`` attributes a
        reactive call to its model response without changing its write identity.
        """
        started = time.monotonic()
        spec = self._specs.get(name)
        if spec is None:
            result = self._error(
                "unknown_tool",
                "Tool call was not accepted.",
                "Use one of the tool definitions supplied for this turn.",
            )
            return self._record(name, args, caller, step, None, result, started, attempts=0,
                                outcome="rejected", trace_step=trace_step)

        if caller not in CALLERS:
            result = self._error("invalid_caller", "Tool call was not accepted.",
                                 f"Caller must be one of {', '.join(CALLERS)}.")
            return self._record(name, args, caller, step, None, result, started, attempts=0,
                                outcome="rejected", trace_step=trace_step)
        if caller not in spec.callers:
            result = self._error("caller_denied", "Tool call was not accepted.",
                                 f"The {caller} caller is not authorized for this tool.")
            return self._record(name, args, caller, step, None, result, started, attempts=0,
                                outcome="denied", trace_step=trace_step)
        if not isinstance(args, dict):
            result = self._error("invalid_arguments", "Tool arguments must be a JSON object.",
                                 "Send an object matching the tool's input schema.")
            return self._record(name, args, caller, step, None, result, started, attempts=0,
                                outcome="rejected", trace_step=trace_step)

        normalized = _normalize_enums(copy.deepcopy(args), spec.input_schema)
        problems = schema_errors(normalized, spec.input_schema)
        if not problems and spec.validate_args is not None:
            try:
                problems = list(spec.validate_args(normalized) or [])
            except Exception as exc:
                problems = [f"argument content check failed: {type(exc).__name__}: {str(exc)[:160]}"]
        if problems:
            repair = "; ".join(str(p) for p in problems[:4])
            result = self._error("invalid_arguments", "Tool arguments failed validation.", repair,
                                 details={"problems": problems[:8]})
            return self._record(name, normalized, caller, step, None, result, started, attempts=0,
                                outcome="rejected", trace_step=trace_step)

        key = self._write_key(spec, normalized, step) if spec.writes else None
        try:
            allowed = self._pre_call_hook(spec=spec, args=copy.deepcopy(normalized), caller=caller,
                                          step=step, key=key)
            if allowed is False:
                raise PermissionError("pre-call hook returned false")
        except Exception as exc:
            result = self._error("hook_denied", "Tool call was denied before execution.",
                                 "Ask the operator or correct the call before retrying.",
                                 details={"hook_error": f"{type(exc).__name__}: {str(exc)[:160]}"})
            return self._record(name, normalized, caller, step, key, result, started, attempts=0,
                                outcome="denied", trace_step=trace_step)

        attempts = 0
        while attempts <= self._max_retries:
            attempts += 1
            try:
                output = spec.fn(**normalized, **({"key": key} if spec.writes else {}))
                result_problems = schema_errors(output, spec.result_schema) if spec.result_schema else []
                if result_problems:
                    result = self._error(
                        "invalid_result",
                        "The tool returned a result outside its declared contract.",
                        "Do not use this result; repair the tool implementation.",
                        details={"problems": result_problems[:8]},
                    )
                    return self._record(name, normalized, caller, step, key, result, started, attempts,
                                        outcome="invalid_result", trace_step=trace_step)
                result = {"ok": True, "output": output, "is_error": False, "error": None}
                return self._record(name, normalized, caller, step, key, result, started, attempts,
                                    outcome="ok", trace_step=trace_step)
            except AmbiguousToolError as exc:
                result = self._error(
                    "ambiguous_write",
                    "The write may already have happened.",
                    "Read the environment to confirm the effect before any retry.",
                    ambiguous=True,
                    details={"exception": str(exc)[:200]},
                )
                return self._record(name, normalized, caller, step, key, result, started, attempts,
                                    outcome="ambiguous", trace_step=trace_step)
            except Exception as exc:  # the registry turns tool failures into the public error contract
                retryable = isinstance(exc, TransientToolError)
                if spec.retryable is not None:
                    try:
                        retryable = retryable or bool(spec.retryable(exc))
                    except Exception:
                        pass
                if retryable and attempts <= self._max_retries:
                    self._sleep(min(self._backoff_base_s * (2 ** (attempts - 1)), 1.0))
                    continue
                if retryable:
                    result = self._error(
                        "transient_failure",
                        "The tool is temporarily unavailable after bounded retries.",
                        "Retry later; the registry has stopped retrying this call.",
                        transient=True,
                        details={"exception": f"{type(exc).__name__}: {str(exc)[:200]}"},
                    )
                    outcome = "retry_exhausted"
                elif isinstance(exc, (ValueError, KeyError, FileNotFoundError)):
                    result = self._error(
                        "permanent_failure",
                        "The tool could not execute this request.",
                        str(exc)[:300] or "Correct the arguments before retrying.",
                        details={"exception": type(exc).__name__},
                    )
                    outcome = "permanent_error"
                else:
                    result = self._error(
                        "execution_failure",
                        "The tool failed without a usable result.",
                        "Do not assume the requested read or write succeeded.",
                        details={"exception": type(exc).__name__},
                    )
                    outcome = "execution_error"
                return self._record(name, normalized, caller, step, key, result, started, attempts,
                                    outcome=outcome, trace_step=trace_step)

        raise AssertionError("bounded retry loop exited unexpectedly")

    def _write_key(self, spec: ToolSpec, args: dict, step: str | None) -> str:
        identity = {field: _nested_value(args, field) for field in spec.key_fields}
        payload = {
            "v": 1,
            "scope": _scope_id(),
            "context": self._key_context,
            "tool": spec.name,
            "identity": {"step": str(step)} if step is not None else identity,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return f"{spec.name}:v1:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"

    @staticmethod
    def _error(error_type: str, message: str, repair: str, *, transient: bool = False,
               ambiguous: bool = False, details: dict | None = None) -> dict:
        # PLAN.md's shared caller contract uses kind/retry.  Keep the more
        # specific type/repair/transient/ambiguous fields as useful extensions,
        # but always expose the shared fields so workflows and agent loops can
        # classify a failure without knowing registry internals.
        if transient:
            kind = "transient"
        elif error_type in {
            "unknown_tool", "invalid_caller", "caller_denied", "invalid_arguments",
            "hook_denied", "invalid_result",
        }:
            kind = "protocol"
        else:
            kind = "permanent"
        error = {
            "type": error_type,
            "kind": kind,
            "message": message,
            "repair": repair,
            "retry": transient,
            "transient": transient,
            "ambiguous": ambiguous,
        }
        if details:
            error.update(details)
        return {
            "ok": False,
            "output": {"message": message, "repair": repair},
            "is_error": True,
            "error": error,
        }

    def _record(self, name, args, caller, step, key, result, started, attempts: int, outcome: str,
                *, trace_step=None) -> dict:
        trace = self._trace or _current_trace()
        if trace is not None:
            latency = time.monotonic() - started
            traced_result = SimpleNamespace(
                # Keep the same complete envelope returned to the caller,
                # including error details. Only result_summary is truncated.
                content=copy.deepcopy(result),
                is_error=result["is_error"],
                latency_s=latency,
            )
            trace.tool_call(
                trace_step if trace_step is not None else (step if step is not None else 0),
                {"name": name, "input": args if isinstance(args, dict) else {"value": args}},
                traced_result,
                plan_step=step,
                caller=caller,
                key=key,
                attempts=attempts,
                outcome=outcome,
                error_type=(result.get("error") or {}).get("type"),
                result_summary=_summary(result.get("output")),
                cost_usd=0.0,
            )
        return result


def _normalize_enums(value, schema: dict):
    """Canonicalize string enum values while comparing them case-insensitively."""
    if isinstance(value, str) and isinstance(schema.get("enum"), list):
        for choice in schema["enum"]:
            if isinstance(choice, str) and value.casefold() == choice.casefold():
                return choice
    if isinstance(value, dict):
        props = schema.get("properties") or {}
        return {name: _normalize_enums(item, props.get(name, {})) for name, item in value.items()}
    if isinstance(value, list) and isinstance(schema.get("items"), dict):
        return [_normalize_enums(item, schema["items"]) for item in value]
    return value


def _nested_value(value: dict, dotted: str):
    """Read an effect-identity field such as ``figures.period`` without
    widening the model-visible schema merely to construct a stable key."""
    current = value
    for part in dotted.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _scope_id() -> str:
    try:
        from harness import runtime

        run = runtime.current_run()
        if run is not None:
            return run.run_id
        return runtime.current_session() or "unscoped"
    except Exception:
        return "unscoped"


def _current_trace():
    try:
        from harness import runtime

        run = runtime.current_run()
        if run is not None:
            return run.trace
        session = runtime.current_session()
        return runtime.trace(session) if session else None
    except Exception:
        return None


def _summary(value, limit: int = 1200) -> str:
    try:
        text = json.dumps(value, sort_keys=True, default=str, ensure_ascii=False)
    except (TypeError, ValueError):
        text = str(value)
    return text if len(text) <= limit else text[:limit] + "…[truncated]"
