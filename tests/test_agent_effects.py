"""Reactive calls through the public service and real registry, tools, and critic."""

from harness import runtime, turns
from harness.client import Usage
from sandbox import inbox, pending, reports, sales
from tests.fixtures.agent_loop_fakes import tool
from tests.support import ScratchTest, fixed_run

TASK = "tests/fixtures/agent_messy_file.yaml"
RID = "REQ-SYN-thread-agent-messy"
MODEL = "tests.fixtures.agent_loop_fakes:SequenceModel"


class AgentEffectsTest(ScratchTest):
    def run_calls(self, *rounds):
        runtime.client().backend.responses = [(calls, "tool_use", Usage(10, 5)) for calls in rounds]
        return turns.operator_turn("operator", "Handle the new request.")

    def figures(self):
        request = inbox.get(RID)
        return sales.distributor_sales(request["distributor_id"], request["period"])

    def test_report_retry_with_new_prose_reuses_effect_across_model_rounds(self):
        with fixed_run(TASK, "report-retry", backend=MODEL):
            args = {"kind": "standard", "figures": self.figures(), "body": "First wording"}
            self.run_calls([tool("save_report", args, "first")],
                           [tool("save_report", {**args, "body": "Reworded"}, "retry")])
            self.assertEqual(len(reports.for_request(RID)), 1)
            calls = [e for e in runtime.trace().lines() if e["type"] == "tool_call"]
            self.assertEqual([e["step"] for e in calls], [1, 2])
            self.assertEqual(calls[0]["key"], calls[1]["key"])
            self.assertTrue(all(e["plan_step"] is None for e in calls))

    def test_email_retry_with_new_prose_reuses_effect_through_real_critique(self):
        with fixed_run(TASK, "email-retry", backend=MODEL):
            figures = self.figures()
            saved, _ = reports.save(RID, "standard", figures, "Report", "planted-report")
            args = {"recipient": inbox.get(RID)["contact_email"], "report_id": saved["id"],
                    "subject": "Q3 report", "body": f"Revenue {figures['total_revenue']:,.2f}."}
            self.run_calls([tool("draft_report_email", args, "first")],
                           [tool("draft_report_email", {**args, "body": "Your report: " + args["body"]}, "retry")])
            self.assertEqual(len(pending.for_request(RID)), 1)
            self.assertEqual([e["verdict"] for e in runtime.trace().lines() if e["type"] == "critique"],
                             ["pass", "pass"])

    def test_different_report_effects_in_one_round_remain_distinct(self):
        with fixed_run(TASK, "distinct-reports", backend=MODEL):
            args = {"kind": "standard", "figures": self.figures(), "body": "Standard"}
            self.run_calls([tool("save_report", args, "standard"),
                            tool("save_report", {**args, "kind": "comparison", "body": "Comparison"}, "comparison")])
            self.assertEqual({r["kind"] for r in reports.for_request(RID)}, {"standard", "comparison"})
            calls = [e for e in runtime.trace().lines() if e["type"] == "tool_call"]
            self.assertNotEqual(calls[0]["key"], calls[1]["key"])
            self.assertEqual([e["step"] for e in calls], [1, 1])

    def test_exact_read_repeats_are_traced_without_blocking_a_retry(self):
        with fixed_run(TASK, "reactive-repeats", backend=MODEL):
            self.run_calls([tool("query_sales", {"period": "2026Q3"}, "first")],
                           [tool("query_sales", {"period": "2026Q3"}, "retry")],
                           [tool("query_sales", {"period": "2026Q2"}, "different")])
            repeats = [e for e in runtime.trace().lines() if e["type"] == "repeat_call"]
            self.assertEqual(len(repeats), 1)
            self.assertEqual((repeats[0]["request_id"], repeats[0]["tool"], repeats[0]["count"]),
                             (RID, "query_sales", 2))
            calls = [e for e in runtime.trace().lines() if e["type"] == "tool_call"]
            self.assertEqual(len(calls), 3)
            self.assertTrue(all(e["outcome"] == "ok" for e in calls))
