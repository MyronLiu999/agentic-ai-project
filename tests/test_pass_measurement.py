"""Regression checks for scoped diagnostics and the single-switch pass surface."""

import unittest
from unittest import mock

from agent.tools import build
from experiments.analysis.analyze import analyze_arm, call_hash
from tests.support import ScratchTest
from tests.test_analyze import write_run


class PassMeasurementTest(ScratchTest):
    def test_different_request_queries_are_not_repeated_effects(self):
        def call(request):
            return {"name": "query_sales", "input": {"period": "2026Q3"},
                    "output": {"ok": True, "output": {"request_id": request}}}
        first, second = call("REQ-A"), call("REQ-B")
        self.assertNotEqual(call_hash(first), call_hash(second))
        self.assertEqual(call_hash(first), call_hash(call("REQ-A")))

    def test_status_follow_up_does_not_count_as_initial_misroute(self):
        task = self.tmp / "task.yaml"
        task.write_text("use_case: batch_reports\n", encoding="utf-8")
        write_run(self.tmp, "scoped", "batch", 1, passed=True, cost=0,
                  task_file=str(task), trace=[{"type": "route", "use_case": "batch_reports"},
                                             {"type": "route", "use_case": "status_question"}])
        routing = analyze_arm(self.tmp)["routing"]
        self.assertEqual((routing["routes"], routing["scored_routes"], routing["misroutes"]), (2, 1, 0))

    def test_pass_switch_changes_only_report_description(self):
        with mock.patch("agent.tools._switch", return_value="off"):
            before = build(None).definitions()
        with mock.patch("agent.tools._switch", side_effect=lambda name, default="off":
                        "on" if name == "examples.save_report" else "off"):
            after = build(None).definitions()
        for old, new in zip(before, after):
            if old["name"] == "save_report":
                self.assertNotEqual(old["description"], new["description"])
                self.assertIn("file_total_units", new["description"])
                new = {**new, "description": old["description"]}
            self.assertEqual(old, new)
