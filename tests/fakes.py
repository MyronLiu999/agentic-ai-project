"""Fakes, so each member can test their part without waiting on the others'.

FakeRegistry   the registry's interface (agent/registry.py) with canned results: abraham's loop,
               workflows and plan, and claudea's domain workflows, test against it until myron's
               registry is in.
ScriptedTools  a fake model (free = True) that calls a fixed list of tools, then answers and ends.
               Subclass it with your own `script`, and run it as --backend tests.fakes:YourClass or
               with ScratchTest.run_task(..., backend="tests.fakes:YourClass").
"""

from __future__ import annotations

from harness.client import Usage
from harness.scripted import estimate_tokens


class FakeRegistry:
    """Same calls as agent.registry.Registry. `results` maps a tool name to its output, or to a
    callable taking the arguments. Every call is kept in `calls`."""

    def __init__(self, definitions: list[dict] | None = None, results: dict | None = None):
        self._definitions = sorted(definitions or [], key=lambda d: d["name"])
        self.results = results or {}
        self.calls: list[dict] = []

    def definitions(self) -> list[dict]:
        return list(self._definitions)

    def call(self, name: str, args: dict, caller: str, *, step=None, trace_step=None) -> dict:
        self.calls.append({"name": name, "args": args, "caller": caller, "step": step})
        if name not in self.results:
            return {"ok": False, "output": "unknown tool", "is_error": True,
                    "error": {"kind": "protocol", "message": f"no tool {name!r}", "retry": False}}
        result = self.results[name]
        output = result(args) if callable(result) else result
        return {"ok": True, "output": output, "is_error": False, "error": None}


class ScriptedTools:
    """Calls each (tool, arguments) in `script` in turn, then answers `final` and ends its turn."""

    name = "scripted-tools"
    free = True
    script: list[tuple[str, dict]] = []
    final = "Done."

    def __init__(self, settings=None):
        self.calls = 0

    def create(self, *, system, messages, tools):
        prompt = estimate_tokens({"system": system, "tools": tools, "messages": messages})
        self.calls += 1
        if self.calls <= len(self.script):
            tool, args = self.script[self.calls - 1]
            block = {"type": "tool_use", "id": f"toolu_fake_{self.calls:04d}", "name": tool, "input": args}
            return [block], "tool_use", self.name, Usage(prompt, 20)
        return [{"type": "text", "text": self.final}], "end_turn", self.name, Usage(prompt, 5)
