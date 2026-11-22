"""Crash and resume a complete official task script against the real MCP server.

    python -m tests.recovery_child crash  <task file> <run id> <target JSON> <progress file>
    python -m tests.recovery_child resume <task file> <run id> <progress file>

The script cursor is durable before each external event. A crash resumes that
in-flight event through the service, preserves its reply, then continues the
remaining operator turns, outside answers, and approval decisions in runner order.
"""

from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path
import sys
from unittest import mock

from tests.recovery_mcp import write_json


def counts(run_id: str) -> dict:
    """Independent durable effect counts, excluding seeded and other-run rows."""
    import channel
    from sandbox import db
    with db.connect() as conn:
        result = {table: conn.execute(f"SELECT COUNT(*) FROM {table} WHERE stamp = ?", (run_id,)).fetchone()[0]
                  for table in ("reports", "pending", "charts")}
        result["sent_drafts"] = conn.execute(
            "SELECT COUNT(*) FROM pending WHERE stamp = ? AND status = 'sent'", (run_id,)).fetchone()[0]
    messages = [m for thread in channel.threads() for m in channel.messages(thread["thread_id"])
                if m.run_id == run_id and not m.seeded]
    result["agent_messages"] = sum(m.sender == channel.AGENT for m in messages)
    result["outside_answers"] = sum(m.sender not in (channel.AGENT, "operator") for m in messages)
    return result


@contextlib.contextmanager
def crashing_server(target: dict, boundary: Path):
    """Change only the test driver's Popen command, never production hooks."""
    from mcp_server import client
    popen = client.subprocess.Popen

    def launch(command, *args, **kwargs):
        if command == [sys.executable, "-m", "mcp_server"]:
            command = [sys.executable, "-m", "tests.recovery_mcp"]
            kwargs["env"] = {**kwargs.get("env", os.environ),
                             "RECOVERY_TARGET": json.dumps(target),
                             "RECOVERY_DRIVER_PID": str(os.getpid()),
                             "RECOVERY_BOUNDARY": str(boundary)}
        return popen(command, *args, **kwargs)

    with mock.patch.object(client.subprocess, "Popen", side_effect=launch):
        yield


class Script:
    """The runner's event order with a durable cursor around each harness turn."""

    def __init__(self, task, run_id, path, *, fresh):
        import channel
        from harness import tasks
        self.task, self.run_id, self.path = task, run_id, Path(path)
        self.people = channel._script.install(task.get("outside") or [])
        self.answers = tasks.scripted_answers(task)
        self.state = ({"operator_index": 0, "approval_index": 0, "outside": [], "replies": [],
                       "events": [], "inflight": None, "last_reply": None, "complete": False}
                      if fresh else json.loads(self.path.read_text()))
        for person, saved in zip(self.people, self.state["outside"]):
            for field in ("asked", "answered", "wrote_unasked"):
                setattr(person, field, saved[field])
        self.save()

    def save(self):
        self.state["outside"] = [{field: getattr(person, field) for field in
                                  ("thread", "asked", "answered", "wrote_unasked")} for person in self.people]
        write_json(self.path, self.state)

    def finish(self, event, reply, *, resumed=False):
        serialized = reply.as_dict() if reply is not None else None
        if serialized is not None:
            self.state["replies"].append({"function": event["function"], **serialized})
            if resumed:
                from harness import runtime
                runtime.trace().write({"type": "reply", "function": event["function"],
                                       **serialized, "crash_resume": True})
        self.state["events"].append({**event, "resumed": resumed, "reply": serialized})
        self.state.update(inflight=None, last_reply=serialized)
        self.save()

    def execute(self, event):
        from harness import turns
        self.state["inflight"] = event
        self.save()
        kind = event["function"]
        if kind == "operator_turn":
            reply = turns.operator_turn(self.run_id, event["text"])
        elif kind == "on_outside_reply":
            reply = turns.outside_reply(event["thread"], event["text"], sender=event["sender"])
        else:
            reply = turns.decide_approval(event["approval_id"], event["approved"],
                                          "scripted answer from the task file")
        self.finish(event, reply)

    def resume(self):
        from agent import runs, service
        from harness import runtime
        event = self.state["inflight"]
        if event is None:
            raise AssertionError("Crash left no durable in-flight script event")
        stopped = runs.crashed(self.run_id)
        if len(stopped) != 1:
            raise AssertionError(f"Expected exactly one eligible crashed run, found {stopped}")
        with runtime.in_session(self.run_id):
            reply = service.continue_run(stopped[0], {"kind": "crash"})
        self.state["resumed_run"] = stopped[0]
        self.finish(event, reply, resumed=True)

    def play(self):
        import channel
        from harness import runner, turns
        for _ in range(100):
            # Same order as runner._after: outside reply, approval, next operator.
            last = self.state["last_reply"] or {}
            thread = last.get("waiting_for")
            answer = channel._script.answer(thread) if thread else None
            if answer is not None:
                self.execute({"function": "on_outside_reply", "thread": thread,
                              "sender": answer[0], "text": answer[1]})
                continue
            approvals = turns.pending_approvals()
            index = self.state["approval_index"]
            if approvals and index < len(self.answers):
                self.state["approval_index"] += 1
                self.execute({"function": "decide_approval", "approval_id": str(approvals[0]["id"]),
                              "approved": self.answers[index]})
                continue
            index = self.state["operator_index"]
            if index < len(self.task["operator"]):
                self.state["operator_index"] += 1
                self.execute({"function": "operator_turn", "index": index, "text": self.task["operator"][index]})
                continue
            person = next((p for p in self.people if not p.asked and not p.wrote_unasked
                           and p.never_asked is not None), None)
            if person is not None:
                thread = runner._concrete_thread(channel, person)
                person.wrote_unasked += 1
                if thread is not None:
                    self.execute({"function": "on_outside_reply", "thread": thread,
                                  "sender": person.name, "text": person.never_asked})
                    continue
            self.state["complete"] = True
            self.save()
            return
        raise AssertionError("Recovery script exceeded 100 external events")


def main(argv: list[str]) -> int:
    from tests.fixtures.m2_tasks import task_backend
    from tests.support import fixed_run

    phase, task_file, run_id = argv[:3]
    progress = Path(argv[4] if phase == "crash" else argv[3])
    with fixed_run(task_file, run_id, backend=task_backend(task_file), fresh=phase == "crash") as run:
        script = Script(run.task, run_id, progress, fresh=phase == "crash")
        if phase == "crash":
            write_json(progress.with_suffix(".before.json"), counts(run_id))
            with crashing_server(json.loads(argv[3]), progress.with_suffix(".boundary.json")):
                script.play()
            return 3  # Completing without the targeted kill is a test failure.
        script.resume()
        script.play()
        print(json.dumps({"resumed_run": script.state["resumed_run"], "replies": script.state["replies"],
                          "complete": script.state["complete"]}))
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
