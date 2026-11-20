"""Fakes, so each member can test their part without waiting on the others'.

FakeRegistry   the registry's interface (agent/registry.py) with canned results: abraham's loop,
               workflows and plan, and claudea's domain workflows, test against it until myron's
               registry is in.
ScriptedTools  a fake model (free = True) that calls a fixed list of tools, then answers and ends.
               Subclass it with your own `script`, and run it as --backend tests.fakes:YourClass or
               with ScratchTest.run_task(..., backend="tests.fakes:YourClass").

Milestone 2 (setup, Nov 20; PLAN_M2.md section 3), so nobody waits on another member's real code:
FakeRegistry   also knows the new tools (ask_stranger, send_report_email, search_tools, run_program),
               checks their argument shapes, and offers compensate(call_record).
FakeHook       a policy hook with scripted answers: pass it to a real Registry as pre_call_hook, or
               install() it in place of policy.hook.decide.
FakeApprovals  an in-memory agent.approvals (put_up, pending, decide, is_approved, withdraw, put_up_plan,
               plan_covers); install().
FakeResume     records agent.runs.resume(run_key, event) calls instead of resuming; install().
FakeStranger   a stranger with scripted answers per thread, delivered through harness.turns.outside_reply.
"""

from __future__ import annotations

import contextlib
import itertools
from unittest import mock

from harness.client import Usage
from harness.scripted import estimate_tokens

# The Milestone 2 tools' arguments (PLAN_M2.md 3.4): name -> {argument: type}. All are required.
M2_TOOL_ARGS = {
    "ask_stranger": {"question": str},
    "send_report_email": {"pending_id": int},
    "search_tools": {"query": str},
    "run_program": {"code": str},
}


class FakeRegistry:
    """Same calls as agent.registry.Registry. `results` maps a tool name to its output, or to a
    callable taking the arguments. Every call is kept in `calls`."""

    def __init__(self, definitions: list[dict] | None = None, results: dict | None = None,
                 compensations: dict | None = None):
        self._definitions = sorted(definitions or [], key=lambda d: d["name"])
        self.results = results or {}
        self.compensations = compensations or {}      # tool name -> output, or callable(call_record)
        self.calls: list[dict] = []
        self.compensated: list[dict] = []

    def compensate(self, call_record: dict) -> dict:
        """As Registry.compensate: {"compensated_by": name or "none", "result": ...}."""
        self.compensated.append(call_record)
        undo = self.compensations.get(call_record.get("tool"))
        if undo is None:
            return {"compensated_by": "none", "result": None}
        return {"compensated_by": f"compensate:{call_record['tool']}",
                "result": undo(call_record) if callable(undo) else undo}

    def definitions(self) -> list[dict]:
        return list(self._definitions)

    def call(self, name: str, args: dict, caller: str, *, step=None, trace_step=None) -> dict:
        self.calls.append({"name": name, "args": args, "caller": caller, "step": step})
        if name not in self.results:
            return {"ok": False, "output": "unknown tool", "is_error": True,
                    "error": {"kind": "protocol", "message": f"no tool {name!r}", "retry": False}}
        problems = _m2_arg_problems(name, args)
        if problems:
            return {"ok": False, "output": {"message": "Tool arguments failed validation.", "repair": problems},
                    "is_error": True, "error": {"type": "invalid_arguments", "kind": "protocol",
                                                "message": problems, "retry": False}}
        result = self.results[name]
        output = result(args) if callable(result) else result
        return {"ok": True, "output": output, "is_error": False, "error": None}


def _m2_arg_problems(name: str, args) -> str:
    shape = M2_TOOL_ARGS.get(name)
    if shape is None:
        return ""
    if not isinstance(args, dict):
        return "arguments must be an object"
    if set(args) != set(shape):
        return f"{name} takes exactly {sorted(shape)}"
    bad = [k for k, t in shape.items() if not isinstance(args[k], t) or isinstance(args[k], bool)]
    return f"wrong type for {bad}" if bad else ""


class FakeHook:
    """A policy hook with scripted answers. `answers` maps a tool name to "allow" | "ask" | "deny" (or a
    whole Decision dict); anything unlisted is allowed. Every decision is kept in `decisions`."""

    def __init__(self, answers: dict | None = None):
        self.answers = answers or {}
        self.decisions: list[dict] = []

    def decide(self, call: dict, ctx: dict) -> dict:
        answer = self.answers.get(call.get("name"), "allow")
        decision = dict(answer) if isinstance(answer, dict) else {
            "answer": answer, "action_class": f"{call.get('name')}/scripted", "reason": "scripted"}
        self.decisions.append({"call": call, "ctx": ctx, **decision})
        return decision

    def __call__(self, *, spec, args, caller, step, key):     # the registry's pre_call_hook signature
        return self.decide({"name": spec.name, "args": args, "caller": caller, "step": step, "key": key},
                           {"run_key": None, "session_id": None})

    @contextlib.contextmanager
    def install(self):
        with mock.patch("policy.hook.decide", self.decide):
            yield self


class FakeApprovals:
    """agent.approvals in memory, with its contract's functions (PLAN_M2.md 3.2)."""

    def __init__(self):
        self.items: dict[str, dict] = {}
        self.log: list[dict] = []
        self._ids = itertools.count(1)

    def put_up(self, run_key, session_id, call, action_class, screen):
        approval_id = f"apr-{next(self._ids)}"
        self.items[approval_id] = {"id": approval_id, "run_key": run_key, "session_id": session_id,
                                   "call": call, "action_class": action_class, "screen": screen,
                                   "status": "waiting"}
        return approval_id

    def pending(self):
        return [dict(i) for i in self.items.values() if i["status"] == "waiting"]

    def decide(self, approval_id, approved, note="", who="operator"):
        item = self.items[approval_id]
        item["status"] = "approved" if approved else "rejected"
        self.log.append({"approval_id": approval_id, "approved": bool(approved), "note": note, "who": who})
        return dict(item)

    def is_approved(self, run_key, key):
        return any(i["run_key"] == run_key and (i["call"] or {}).get("key") == key and i["status"] == "approved"
                   for i in self.items.values())

    def put_up_plan(self, run_key, session_id, plan, gated_steps):
        approval_id = f"apr-{next(self._ids)}"
        self.items[approval_id] = {"id": approval_id, "run_key": run_key, "session_id": session_id,
                                   "call": None, "plan": plan, "gated_steps": list(gated_steps),
                                   "action_class": "plan", "screen": None, "status": "waiting"}
        return approval_id

    def plan_covers(self, run_key, call):
        return any(i["run_key"] == run_key and i.get("gated_steps") and i["status"] == "approved"
                   and any(g.get("tool") == call.get("name") and g.get("args") == call.get("args")
                           for g in i["gated_steps"])
                   for i in self.items.values())

    def withdraw(self, run_key):
        out = [i["id"] for i in self.items.values() if i["run_key"] == run_key and i["status"] == "waiting"]
        for approval_id in out:
            self.items[approval_id]["status"] = "withdrawn"
        return out

    @contextlib.contextmanager
    def install(self):
        with contextlib.ExitStack() as stack:
            for name in ("put_up", "pending", "decide", "is_approved", "withdraw", "put_up_plan", "plan_covers"):
                stack.enter_context(mock.patch(f"agent.approvals.{name}", getattr(self, name)))
            yield self


class FakeResume:
    """Stands in for agent.runs.resume: keeps each (run_key, event) and returns `reply`."""

    def __init__(self, reply=None):
        from harness.turns import Reply
        self.reply = reply if reply is not None else Reply("resumed (fake)")
        self.calls: list[tuple[str, dict]] = []

    def resume(self, run_key, event):
        self.calls.append((run_key, dict(event)))
        return self.reply

    @contextlib.contextmanager
    def install(self):
        with mock.patch("agent.runs.resume", self.resume):
            yield self


class FakeStranger:
    """A stranger with scripted answers: `answers` maps a thread_id to a list of replies, given in turn.
    answer(thread_id) delivers the next one through harness.turns.outside_reply (or returns None)."""

    def __init__(self, answers: dict | None = None, name: str = "SYN-contact-fake"):
        self.answers = {k: list(v) for k, v in (answers or {}).items()}
        self.name = name
        self.asked: dict[str, int] = {}

    def answer(self, thread_id: str):
        from harness import turns
        self.asked[thread_id] = self.asked.get(thread_id, 0) + 1
        queue = self.answers.get(thread_id) or []
        if not queue:
            return None
        return turns.outside_reply(thread_id, queue.pop(0), sender=self.name)


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
