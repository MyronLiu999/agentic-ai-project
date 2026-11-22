"""Checkpoints, the three exits, compensations and the workflow resume (Milestone 2, C2 to C4; owner: claudea).
All on a fake model (tests.fixtures.agent_milestone_model:MilestoneModel), reading the sandbox for effects."""

import unittest
from unittest import mock

from tests.support import ScratchTest, fixed_run

MODEL = "tests.fixtures.agent_milestone_model:MilestoneModel"
TASK = "tasks/standard_report_clean.yaml"
REQUEST = "REQ-SYN-thread-1001"


class PlacementTest(unittest.TestCase):
    def test_one_step_that_needs_a_checkpoint_and_one_that_does_not(self):
        from agent import checkpoints
        # The agent loop: the model writes the next call's arguments, so a replay could write others.
        self.assertTrue(checkpoints.needs_checkpoint({"path": "agent", "step": "round-3"}))
        # A workflow's keyed write whose arguments code fixed before it runs: the key closes the replay.
        self.assertFalse(checkpoints.needs_checkpoint({"path": "workflow", "tool": "save_report", "step": "4-save"}))
        # A workflow write whose arguments came from model calls too costly to repeat.
        self.assertTrue(checkpoints.needs_checkpoint({"path": "workflow", "tool": "draft_report_email",
                                                      "args_from_model": True}))
        self.assertFalse(checkpoints.needs_checkpoint({"path": "workflow", "tool": "parse_file"}))

    def test_durability_mode_per_kind_of_run(self):
        from agent import checkpoints
        self.assertEqual(checkpoints.mode_for({"path": "agent"}), "sync")
        self.assertEqual(checkpoints.mode_for({"path": "workflow", "use_case": "standard_report"}), "async")
        self.assertEqual(checkpoints.mode_for({"path": "workflow", "use_case": "status_question"}), "exit")


class _Flaky:
    """The real registry, except that one write fails with an unknown outcome: after committing it
    (`commit_first`) or before."""

    def __init__(self, real, tool, commit_first, times=1):
        self.real, self.tool, self.commit_first, self.left = real, tool, commit_first, times
        self.calls = []

    def call(self, name, args, caller, *, step=None, trace_step=None):
        self.calls.append(name)
        if name == self.tool and self.left > 0:
            self.left -= 1
            if self.commit_first:
                self.real.call(name, args, caller, step=step)
            return {"ok": False, "output": None, "is_error": True,
                    "error": {"type": "ambiguous_write", "kind": "permanent", "message": "timed out", "retry": False}}
        return self.real.call(name, args, caller, step=step, trace_step=trace_step)

    def compensate(self, record):
        return self.real.compensate(record)

    def definitions(self):
        return self.real.definitions()


class ThreeExitsTest(ScratchTest):
    def _run(self, run_id, commit_first, times=1, settle=None):
        from agent import tools, workflows
        from sandbox import pending
        with fixed_run(TASK, run_id, backend=MODEL):
            flaky = _Flaky(tools.build(REQUEST), "draft_report_email", commit_first, times)
            if settle:
                with mock.patch("agent.exits.settle", settle):
                    reply = workflows.standard_report(run_id, REQUEST, registry=flaky)
            else:
                reply = workflows.standard_report(run_id, REQUEST, registry=flaky)
            emails = [p for p in pending.for_request(REQUEST) if p["kind"] == "report_email" and p["stamp"] == run_id]
            from harness import runtime
            lines = runtime.trace().lines()
        return reply, flaky, emails, lines

    def test_happened_carries_on_with_the_existing_result(self):
        reply, flaky, emails, _ = self._run("exit-yes", commit_first=True)
        self.assertEqual(len(emails), 1)
        self.assertEqual(flaky.calls.count("draft_report_email"), 1)      # read, not retried
        self.assertIn("pending record", reply.text)

    def test_not_happened_retries_under_the_same_key(self):
        reply, flaky, emails, _ = self._run("exit-no", commit_first=False)
        self.assertEqual(len(emails), 1)
        self.assertEqual(flaky.calls.count("draft_report_email"), 2)      # retried once

    def test_cannot_tell_escalates_and_writes_nothing_more(self):
        reply, flaky, emails, lines = self._run("exit-unknown", commit_first=False,
                                                settle=lambda *a: ("unknown", "the mailbox did not answer"))
        self.assertEqual(emails, [])
        ends = [l for l in lines if l.get("type") == "end"]
        self.assertEqual(ends[-1]["terminal_reason"], "unsettled_write")
        packets = [l for l in lines if l.get("type") == "escalation"]
        self.assertEqual(packets[-1]["signal"], "unsettled_write")
        self.assertTrue(all(packets[-1][k] for k in ("attempted", "why", "needs")))


class CompensationsTest(ScratchTest):
    def test_each_write_has_its_undo_and_sends_have_none(self):
        from agent import compensations, tools
        from sandbox import charts, pending, reports
        with fixed_run(TASK, "undo", backend=MODEL):
            reg = tools.build(REQUEST)
            chart = reg.call("render_chart", {"title": "t", "labels": ["a"], "values": [1.0]}, "code", step="c")
            saved = reg.call("save_report", {"kind": "standard", "figures": {"period": "2026Q3", "total_revenue": 1.0},
                                             "body": "b"}, "code", step="s")
            email = reg.call("draft_report_email", {"recipient": "contact@acme.example", "subject": "s", "body": "b",
                                                    "report_id": saved["output"]["report_id"]}, "code", step="e")
            for tool, result in (("draft_report_email", email), ("save_report", saved), ("render_chart", chart)):
                undone = reg.compensate({"tool": tool, "result": result})
                self.assertTrue(undone["result"]["undone"], tool)
            self.assertEqual(pending.get(email["output"]["pending_id"])["status"], "discarded")
            self.assertIsNone(reports.latest(REQUEST))
            self.assertIsNone(charts.get(chart["output"]["chart_id"]))
            self.assertEqual(compensations.compensate({"tool": "send_report_email"})["compensated_by"], "none")
            # Safe to repeat: a second undo finds nothing left.
            self.assertFalse(reg.compensate({"tool": "save_report", "result": saved})["result"]["undone"])

    def test_a_permanent_failure_after_writes_compensates_them_newest_first(self):
        from agent import tools, workflows
        from sandbox import charts, reports

        class FailsEmail(_Flaky):
            def call(self, name, args, caller, *, step=None, trace_step=None):
                if name == "draft_report_email":
                    return {"ok": False, "output": None, "is_error": True,
                            "error": {"type": "permanent_failure", "kind": "permanent", "message": "no", "retry": False}}
                return self.real.call(name, args, caller, step=step, trace_step=trace_step)

        with fixed_run(TASK, "undo-reverse", backend=MODEL):
            reply = workflows.standard_report("undo-reverse", REQUEST,
                                              registry=FailsEmail(tools.build(REQUEST), "x", False))
            self.assertIsNone(reports.latest(REQUEST))
            self.assertEqual(charts.for_request(REQUEST), [])
        undone = [a for a in reply.actions if a.startswith("compensated")]
        self.assertEqual(undone, ["compensated 4-save save_report: withdraw_report",
                                  "compensated 3-chart render_chart: delete_chart"])


class WorkflowResumeTest(ScratchTest):
    def test_a_resumed_workflow_reuses_finished_steps(self):
        from agent import checkpoints, runs, tools, workflows
        with fixed_run(TASK, "wf-resume", backend=MODEL):
            calls = []
            real = tools.build(REQUEST)

            class Counting(_Flaky):
                def call(self, name, args, caller, *, step=None, trace_step=None):
                    calls.append(name)
                    return self.real.call(name, args, caller, step=step, trace_step=trace_step)

            workflows.standard_report("wf-resume", REQUEST, registry=Counting(real, "x", False))
            first = list(calls)
            calls.clear()
            with runs._resume_scope("wf-resume"):
                workflows.standard_report("wf-resume", REQUEST, registry=Counting(real, "x", False))
            self.assertEqual(first, ["parse_file", "query_sales", "render_chart", "save_report", "draft_report_email"])
            self.assertEqual(calls, [])            # every step came back from the journal
            self.assertEqual(checkpoints.load("wf-resume")["current_step"], "6-email")


if __name__ == "__main__":
    unittest.main()
