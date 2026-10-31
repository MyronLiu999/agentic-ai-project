"""Checkable batch plans, scoped data bindings, and fail-closed call enforcement."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
import re

from agent import events

MAX_STEPS = 48  # Up to eight requests with six ordinary tools each.
MAX_REQUESTS = 8
MAX_REPLANS = 2
TERMINAL = {"draft_report_email", "draft_clarifying_question"}
READS = {"parse_file", "query_sales"}
FIELDS = {
    "parse_file": ({"delimiter": str, "decimal": str}, set(), {"file_name", "columns", "rows", "row_count", "truncated"}),
    "query_sales": ({"period": str}, {"period"}, {"distributor_id", "period", "by_product", "total_units", "total_revenue"}),
    "render_chart": ({"title": str, "labels": list, "values": list}, {"title", "labels", "values"}, {"chart_id", "path"}),
    "save_report": ({"kind": str, "figures": dict, "body": str}, {"kind", "figures", "body"}, {"report_id", "version", "created"}),
    "draft_report_email": ({"recipient": str, "subject": str, "body": str, "report_id": int},
                           {"recipient", "subject", "body", "report_id"}, {"pending_id", "created"}),
    "draft_clarifying_question": ({"question": str}, {"question"}, {"pending_id", "created"}),
}


class PlanError(ValueError):
    pass


def _encoded(value):
    try:
        return json.dumps(value, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError, RecursionError) as exc:
        raise PlanError("Plan values must be finite JSON data") from exc


def _fills(value):
    if isinstance(value, dict):
        if "$fill" in value:
            if set(value) != {"$fill"} or not isinstance(value["$fill"], str) or not re.fullmatch(
                    r"[A-Za-z][A-Za-z0-9_-]*(?:\.[A-Za-z][A-Za-z0-9_]*)*", value["$fill"]):
                raise PlanError("A fill must be exactly {'$fill': 'step_id.output_field'}")
            yield value["$fill"]
        else:
            for child in value.values():
                yield from _fills(child)
    elif isinstance(value, list):
        for child in value:
            yield from _fills(child)
    elif value == "$fill":
        raise PlanError("Bare $fill is not resolvable; name a dependency and output field")


def validate_args(tool: str, args: dict, *, allow_fills=True):
    shapes, required, _ = FIELDS[tool]
    if not isinstance(args, dict) or not required <= set(args) or set(args) - set(shapes):
        raise PlanError(f"{tool} arguments must contain {sorted(required)}; allowed: {sorted(shapes)}")
    bindings = list(_fills(args))
    if bindings and not allow_fills:
        raise PlanError("Unresolved fill at execution")
    for key, value in args.items():
        if isinstance(value, dict) and "$fill" in value:
            continue
        if type(value) is not shapes[key] or isinstance(value, str) and not value.strip():
            raise PlanError(f"{tool}.{key} must be a nonempty {shapes[key].__name__}")
    if "period" in args and isinstance(args["period"], str) and not re.fullmatch(r"\d{4}Q[1-4]", args["period"]):
        raise PlanError("period must have the form YYYYQ1 through YYYYQ4")
    for key, allowed in (("delimiter", (",", ";", "\t")), ("decimal", (".", ","))):
        if key in args and not isinstance(args[key], dict) and args[key] not in allowed:
            raise PlanError(f"Invalid {key}")
    if tool == "save_report" and isinstance(args["figures"], dict) and "$fill" not in args["figures"]:
        if not {"period", "total_revenue"} <= set(args["figures"]):
            raise PlanError("Report figures require period and total_revenue")
    if tool == "render_chart" and not bindings:
        if (len(args["labels"]) != len(args["values"]) or not args["labels"]
                or any(type(v) not in (int, float) or not math.isfinite(v) for v in args["values"])
                or any(not isinstance(v, str) for v in args["labels"])):
            raise PlanError("Chart labels and finite numeric values must have matching nonzero lengths")


def validate(raw: dict, request_ids, *, completed=None) -> list[dict]:
    """Validate the entire graph before any effects; return independent normalized steps."""
    if len(_encoded(raw)) > 64_000:
        raise PlanError("Plan exceeds 64000 characters")
    scope = set(request_ids)
    if not scope or len(scope) > MAX_REQUESTS:
        raise PlanError(f"Select between one and {MAX_REQUESTS} requests")
    if not isinstance(raw, dict) or set(raw) != {"steps"} or not isinstance(raw["steps"], list):
        raise PlanError("Return an object containing only a steps list")
    if not 1 <= len(raw["steps"]) <= MAX_STEPS:
        raise PlanError(f"Plan must contain 1 through {MAX_STEPS} steps")
    steps = deepcopy(raw["steps"])
    by_id = {}
    required = {"id", "request_id", "tool", "args", "depends_on", "expect"}
    for step in steps:
        if not isinstance(step, dict) or not required <= set(step) or set(step) - required - {"checkpoint"}:
            raise PlanError("Each step needs id, request_id, tool, args, depends_on, expect; checkpoint is optional")
        sid = step["id"]
        if not isinstance(sid, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", sid) or sid in by_id:
            raise PlanError("Step IDs must be unique identifiers of at most 64 characters")
        if not isinstance(step["request_id"], str) or step["request_id"] not in scope:
            raise PlanError(f"{sid}: request is outside the selected scope")
        if not isinstance(step["tool"], str) or step["tool"] not in FIELDS:
            raise PlanError(f"{sid}: unknown tool")
        validate_args(step["tool"], step["args"])
        deps = step["depends_on"]
        if not isinstance(deps, list) or any(not isinstance(d, str) for d in deps) or len(set(deps)) != len(deps):
            raise PlanError("Dependencies must be distinct step IDs")
        predicate = step["expect"]
        if (not isinstance(predicate, dict) or not {"field", "op"} <= set(predicate)
                or set(predicate) - {"field", "op", "value"}
                or not isinstance(predicate["field"], str) or not isinstance(predicate["op"], str)
                or predicate["field"] not in FIELDS[step["tool"]][2]
                or predicate["op"] not in ("exists", "eq", "gte")):
            raise PlanError(f"{sid}: expect must check a documented output field")
        if predicate["op"] != "exists" and "value" not in predicate:
            raise PlanError("Comparison predicates require value")
        if predicate["op"] == "gte" and type(predicate["value"]) not in (int, float):
            raise PlanError("gte requires a numeric value")
        if list(_fills(predicate)):
            raise PlanError("Expected outcomes must be concrete")
        step.setdefault("checkpoint", False)
        if type(step["checkpoint"]) is not bool or step["checkpoint"] and step["tool"] not in READS:
            raise PlanError("Only read steps can be revision checkpoints")
        by_id[sid] = step

    ancestors = {}
    def visit(sid, active):
        if sid in active:
            raise PlanError("Plan dependency cycle")
        if sid in ancestors:
            return ancestors[sid]
        found = set()
        for dep in by_id[sid]["depends_on"]:
            if dep not in by_id or by_id[dep]["request_id"] != by_id[sid]["request_id"]:
                raise PlanError("Dependencies must exist within the same request")
            found |= {dep} | visit(dep, active | {sid})
        ancestors[sid] = found
        return found
    for sid, step in by_id.items():
        visit(sid, set())
        for binding in _fills(step["args"]):
            source, *path = binding.split(".")
            if source not in ancestors[sid]:
                raise PlanError(f"{sid}: fill {binding!r} is not a dependency")
            if path and path[0] not in FIELDS[by_id[source]["tool"]][2]:
                raise PlanError(f"{sid}: unknown fill output field")
    for rid in scope:
        terminals = [s for s in steps if s["request_id"] == rid and s["tool"] in TERMINAL]
        if not terminals or not any(s["request_id"] == rid and s["checkpoint"] for s in steps):
            raise PlanError("Each request needs a terminal email/question and a read checkpoint")
        needed = {t["id"] for t in terminals}
        for terminal in terminals:
            needed |= ancestors[terminal["id"]]
        if any(s["request_id"] == rid and s["id"] not in needed for s in steps):
            raise PlanError("Orphan step: its result contributes to no terminal action")
    for sid, old in (completed or {}).items():
        if by_id.get(sid) != old:
            raise PlanError(f"Completed step {sid!r} cannot be changed or removed")
    return steps


def resolve(value, outputs):
    """Resolve recorded bindings without sharing mutable output dictionaries."""
    if isinstance(value, dict):
        if "$fill" in value:
            bindings = list(_fills(value))
            source, *path = bindings[0].split(".")
            try:
                result = outputs[source]
                for field in path:
                    result = result[field]
                return deepcopy(result)
            except (KeyError, TypeError) as exc:
                raise PlanError(f"Missing output for fill {bindings[0]!r}") from exc
        return {k: resolve(v, outputs) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve(v, outputs) for v in value]
    return deepcopy(value)


def matches(predicate, output):
    value = output.get(predicate["field"]) if isinstance(output, dict) else None
    if predicate["op"] == "exists":
        return value is not None
    if predicate["op"] == "eq":
        return type(value) is type(predicate["value"]) and value == predicate["value"]
    return type(value) in (int, float) and math.isfinite(value) and value >= predicate["value"]


class Guard:
    """No registry call is allowed until scope, dependencies, tool, and args match."""
    def __init__(self, steps, trace, *, outputs=None, repeats=None, version=1):
        self.steps = deepcopy(steps)
        self.trace = trace
        self.outputs = deepcopy(outputs or {})
        self.repeats = repeats if repeats is not None else {}
        self.version = version

    def ready(self):
        return [s for s in self.steps if s["id"] not in self.outputs
                and set(s["depends_on"]) <= self.outputs.keys()]

    def authorize(self, step_id, request_id, tool, args):
        step = next((s for s in self.steps if s["id"] == step_id), None)
        label = "extra"
        if step and step_id not in self.outputs:
            if not set(step["depends_on"]) <= self.outputs.keys():
                label = "out_of_order"
            elif step["request_id"] == request_id and step["tool"] == tool and resolve(step["args"], self.outputs) == args:
                return True
        self.trace.event(events.OFF_PLAN, tool=tool, args=args, request_id=request_id, step_id=step_id)
        self.trace.event(events.PLAN_DIFF, step_id=step_id, label=label, version=self.version)
        return False

    def track(self, request_id, tool, args):
        digest = hashlib.sha256(_encoded([request_id, tool, args]).encode()).hexdigest()
        count = self.repeats[digest] = self.repeats.get(digest, 0) + 1
        if count > 1:
            self.trace.event(events.REPEAT_CALL, tool=tool, args_hash=digest, count=count, request_id=request_id)

    def record(self, step_id, output):
        self.outputs[step_id] = deepcopy(output)
        self.trace.event(events.PLAN_DIFF, step_id=step_id, label="executed", version=self.version)

    def finish(self):
        for step in self.steps:
            if step["id"] not in self.outputs:
                self.trace.event(events.PLAN_DIFF, step_id=step["id"], label="skipped", version=self.version)
