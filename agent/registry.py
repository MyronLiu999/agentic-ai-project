"""The tool registry: every call, the model's and your code's, goes through it (Part 3).

Owner of tools/registry fills in: boundary validation, the call record (trace.tool_call with key, cost,
latency), the pre-call hook that fails closed, retries of transient failures, write keys derived here
(never by the model), and definitions() in one fixed order.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

MODEL, CODE, OPERATOR = "model", "code", "operator"


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


class Registry:
    def __init__(self, specs: list[ToolSpec]):
        self._specs = {s.name: s for s in specs}

    def definitions(self) -> list[dict]:
        """What the model sees, in the same order on every request (slide 28)."""
        return [{"name": s.name, "description": s.description, "input_schema": s.input_schema}
                for s in sorted(self._specs.values(), key=lambda s: s.name) if MODEL in s.callers]

    def call(self, name: str, args: dict, caller: str, *, step: str | None = None) -> dict:
        raise NotImplementedError("Registry.call: validate, hook, key, retry, execute, record")
