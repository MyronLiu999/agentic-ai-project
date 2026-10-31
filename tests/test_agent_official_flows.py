"""Exact official operator turns through real service, tools, critique, and checks."""

import json

from sandbox import inbox, pending, reports
from tests.support import ScratchTest

MODEL = "tests.fixtures.agent_milestone_model:MilestoneModel"


class AgentOfficialFlowsTest(ScratchTest):
    def test_official_batch_creates_two_reports_and_answers_its_follow_up(self):
        record = self.run_task("tasks/batch_reports_two.yaml", "batch-full-flow", backend=MODEL)
        self.assertTrue(record["passed"], record["check"]["reason"])
        self.assertEqual(record["measures"]["reports"], 2)
        self.assertEqual(record["measures"]["emails"], 2)
        self.assertEqual(record["replies"][1]["text"].count("Report v1"), 2)
        for rid in ("REQ-SYN-thread-1301", "REQ-SYN-thread-1302"):
            self.assertIn(rid, record["replies"][1]["text"])
            self.assertEqual(inbox.get(rid)["status"], "report_drafted")
            self.assertEqual(pending.for_request(rid)[0]["report_id"], reports.latest(rid)["id"])

    def test_official_comparison_answers_the_saved_change(self):
        record = self.run_task("tasks/compare_check_last_quarter.yaml", "compare-full-flow", backend=MODEL)
        self.assertTrue(record["passed"], record["check"]["reason"])
        follow_up = record["replies"][1]["text"]
        self.assertIn("62,799.60", follow_up)
        self.assertIn("4,446.95", follow_up)
        self.assertIn("still open", follow_up)

    def test_official_messy_file_still_uses_parsed_units_and_database_revenue(self):
        record = self.run_task("tasks/messy_file_semicolon.yaml", "messy-full-flow", backend=MODEL)
        self.assertTrue(record["passed"], record["check"]["reason"])
        figures = json.loads(reports.latest("REQ-SYN-thread-1101")["figures_json"])
        self.assertEqual(figures["file_total_units"], 1240)
        self.assertEqual(figures["total_revenue"], 60854.60)
        self.assertIn("REQ-SYN-thread-1101", record["replies"][1]["text"])
