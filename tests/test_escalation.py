"""The escalation (Milestone 2, Part 2 task 5; owner: myron, M7). Tests read the sandbox.

The handout's test: when the signal fires, a packet with three non-empty fields, a checkpoint and no write;
with the operator silent, the run ends held with no write; answered in a new session (a process of its own),
it resumes with no duplicate in the sandbox. Plus: only signals named in advance, never low confidence, and
the daily cap.
"""

import json
import subprocess
import sys
import unittest
from unittest import mock

from agent.registry import CODE, MODEL
from harness.client import Usage
from sandbox import inbox, reports
from tests.support import ScratchTest, fixed_run

TASK = "tasks/escalation_conflicting_figure.yaml"
SAVE = {"kind": "standard", "body": "SYNTHETIC.", "figures": {"period": "2026Q3", "total_revenue": 3000.0}}


def writes(rid) -> int:
    from sandbox import pending
    return len(reports.for_request(rid)) + len(pending.for_request(rid))


class SavesTheSameReport:
    """On a resume, calls save_report with the arguments the run already used, then ends."""
    name, free = "saves-the-same-report", True

    def __init__(self, settings=None):
        self.calls = 0

    def create(self, *, system, messages, tools):
        self.calls += 1
        if self.calls == 1:
            return ([{"type": "tool_use", "id": "toolu_again", "name": "save_report", "input": SAVE}], "tool_use",
                    self.name, Usage(50, 10))
        return [{"type": "text", "text": "Carried on with the operator's answer."}], "end_turn", self.name, Usage(60, 5)


class EscalationTest(ScratchTest):
    def held_run(self, run_id):
        from agent import escalation, runs, tools
        runs.new_run(run_id)
        rid = inbox.all_requests()[0]["id"]
        before = writes(rid)
        packet = escalation.signal(run_id, "failed_check", attempted=f"the report email for {rid}",
                                   why="the draft still states 99,999.99 after the critique's last round",
                                   needs="the operator to correct or discard the draft")
        return rid, before, packet, tools.build(rid)

    def test_the_signal_holds_the_run_with_a_packet_a_checkpoint_and_no_write(self):
        from agent import checkpoints, escalation
        from sandbox import queue
        with fixed_run(TASK, "esc-fires") as run:
            rid, before, packet, registry = self.held_run("esc-fires")
            self.assertEqual(set(packet), {"run_key", "signal", "attempted", "why", "needs", "over_cap"})
            self.assertTrue(all(packet[k].strip() for k in ("attempted", "why", "needs")))
            self.assertFalse(packet["over_cap"])
            self.assertEqual(checkpoints.load("esc-fires")["held"], packet)
            self.assertEqual(writes(rid), before)
            refused = registry.call("save_report", SAVE, MODEL)           # nothing proceeds by default
            self.assertEqual(refused["error"]["type"], "policy_denied")
            self.assertIn("held", refused["error"]["repair"])
            self.assertEqual(writes(rid), before)
            held = [i for i in queue.waiting() if i["kind"] == "held run"]
            self.assertEqual([i["id"] for i in held], ["esc-fires"])
            self.assertIn("Attempted:", escalation.packet_text(packet))
        traced = [json.loads(l) for l in run.trace_path.read_text(encoding="utf-8").splitlines()]
        self.assertTrue(any(l.get("type") == "escalation" and l.get("signal") == "failed_check" for l in traced))

    def test_only_signals_named_in_advance_never_low_confidence(self):
        from agent import escalation
        with fixed_run(TASK, "esc-names"):
            with self.assertRaises(ValueError):
                escalation.signal("esc-names", "low_confidence", "a", "b", "c")
            with self.assertRaises(ValueError):
                escalation.signal("esc-names", "model_seems_unsure", "a", "b", "c")
            with self.assertRaises(ValueError):
                escalation.signal("esc-names", "failed_check", "a", "", "c")    # every packet field is needed

    def test_a_silent_operator_ends_the_run_held_never_approved(self):
        from agent import escalation, runs
        from sandbox import queue
        with fixed_run(TASK, "esc-silent"):
            rid, before, _, registry = self.held_run("esc-silent")
            ended = escalation.expire(now="9999-01-01T00:00:00+00:00")
            self.assertEqual(ended, ["esc-silent"])
            self.assertEqual(runs.live("esc-silent"), [])
            self.assertEqual(queue.holds(run_key="esc-silent")[0]["status"], "expired")
            self.assertEqual(writes(rid), before)
            answer = escalation.answer("esc-silent", "go ahead")
            self.assertIn("not held", answer.text)                             # too late: it stays ended
            self.assertEqual(writes(rid), before)

    def test_past_the_daily_cap_a_signal_holds_but_sends_no_packet(self):
        from agent import escalation
        from sandbox import queue
        with fixed_run(TASK, "esc-cap"):
            with mock.patch("agent.escalation._budget", return_value={"daily_asks": 0, "hold_timeout_hours": 24}):
                _, _, packet, _ = self.held_run("esc-cap")
            self.assertTrue(packet["over_cap"])
            self.assertIn("over today's cap", escalation.packet_text(packet))
            held = [i for i in queue.waiting() if i["kind"] == "held run"][0]
            self.assertIn("over the daily cap", held["status"])
            self.assertIsNotNone(escalation.active_hold("esc-cap"))           # still held: nothing proceeds


STEP = """
import sys
from tests.support import fixed_run
from tests.test_escalation import SAVE
from agent import checkpoints, escalation, runs, tools
from agent.registry import MODEL
from sandbox import inbox
with fixed_run("tasks/escalation_conflicting_figure.yaml", "esc-later", backend="tests.test_escalation:SavesTheSameReport",
               fresh=sys.argv[1] == "first"):
    if sys.argv[1] == "first":
        runs.new_run("esc-later")
        rid = inbox.all_requests()[0]["id"]
        first = {"role": "user", "content": '{"operator_instruction": "Handle the new request."}'}
        checkpoints.before_step("esc-later", {"path": "agent", "request_id": rid, "operator_text": "Handle the new request.",
                                              "step": "round-1", "conversation": [first]})
        assert tools.build(rid).call("save_report", SAVE, MODEL)["ok"]
        escalation.signal("esc-later", "failed_check", "the report email", "the draft kept a figure the database contradicts",
                          "the operator's decision on the figure")
    else:
        reply = escalation.answer("esc-later", "Use the database figure and carry on.")
        print(reply.text)
"""


class EscalationAnsweredLaterTest(ScratchTest):
    def test_answered_in_a_new_session_it_resumes_with_no_duplicate(self):
        from harness import ROOT
        first = subprocess.run([sys.executable, "-c", STEP, "first"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(first.returncode, 0, first.stderr[-2000:])
        second = subprocess.run([sys.executable, "-c", STEP, "again"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(second.returncode, 0, second.stderr[-2000:])
        self.assertIn("Carried on", second.stdout)
        from sandbox import queue
        with fixed_run(TASK, "esc-later", fresh=False) as run:
            rid = inbox.all_requests()[0]["id"]
            self.assertEqual(len(reports.for_request(rid)), 1)                 # the replayed save came from the journal
            self.assertEqual(queue.holds(run_key="esc-later")[0]["status"], "answered")
        traced = [json.loads(l) for l in run.trace_path.read_text(encoding="utf-8").splitlines()]
        self.assertTrue(any(l.get("type") == "journal_hit" and l.get("tool") == "save_report" for l in traced))


if __name__ == "__main__":
    unittest.main()
