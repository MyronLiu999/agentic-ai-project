import unittest

from agent.registry import CODE, MODEL
from agent.tools import build
from harness.paths import state_dir
from sandbox import inbox, pending, reports, seed
from tests.support import ScratchTest


class ToolsTest(ScratchTest):
    def setUp(self):
        super().setUp()
        seed.reset()
        seed.seed(None)
        self.request_id = inbox.request_id("SYN-thread-2001")
        self.registry = build(self.request_id)

    def test_surface_has_six_tools_and_no_send_tool(self):
        definitions = self.registry.definitions()
        names = [item["name"] for item in definitions]
        self.assertEqual(len(names), 6)
        self.assertFalse(any("send" in name for name in names))
        strict = {item["name"]: item.get("strict") for item in definitions}
        self.assertTrue(strict["query_sales"])
        self.assertFalse(strict["save_report"])

    def test_parse_file_returns_a_bounded_untrusted_shape(self):
        result = self.registry.call("parse_file", {}, MODEL, step="parse")
        self.assertTrue(result["ok"], result)
        output = result["output"]
        self.assertEqual(output["row_count"], 2)
        self.assertEqual(output["trust"], "untrusted_distributor_data")
        self.assertFalse(output["truncated"])

    def test_query_sales_binds_distributor_from_the_request(self):
        result = self.registry.call(
            "query_sales", {"period": "2026Q3", "metric": "both"}, MODEL, step="sales"
        )
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["output"]["distributor_id"], "SYN-DIST-001")
        rejected = self.registry.call(
            "query_sales",
            {"period": "2026Q3", "metric": "both", "distributor_id": "SYN-DIST-003"},
            MODEL,
        )
        self.assertEqual(rejected["error"]["type"], "invalid_arguments")

    def test_chart_retry_is_one_artifact(self):
        args = {
            "title": "Q3 revenue", "period": "2026Q3", "metric": "revenue",
            "series": [{"label": "Widget", "value": 1250.5}],
        }
        first = self.registry.call("render_chart", args, CODE, step="chart")
        second = build(self.request_id).call("render_chart", args, CODE, step="chart")
        self.assertTrue(first["output"]["created"])
        self.assertFalse(second["output"]["created"])
        self.assertEqual(len(list((state_dir() / "artifacts" / self.request_id).glob("*.svg"))), 1)

    def test_report_and_email_writes_are_idempotent_and_bound(self):
        report_args = {
            "kind": "STANDARD", "period": "2026Q3",
            "figures": {"total_revenue": 123.45}, "body": "Synthetic report.",
        }
        first = self.registry.call("save_report", report_args, CODE, step="save")
        second = build(self.request_id).call("save_report", report_args, CODE, step="save")
        self.assertTrue(first["ok"], first)
        self.assertTrue(first["output"]["created"])
        self.assertFalse(second["output"]["created"])
        self.assertEqual(len(reports.for_request(self.request_id)), 1)

        email_args = {
            "report_id": first["output"]["id"],
            "subject": "Your Q3 report",
            "body": "Please review the attached synthetic report.",
        }
        email = self.registry.call("draft_report_email", email_args, MODEL, step="email")
        duplicate = build(self.request_id).call("draft_report_email", email_args, MODEL, step="email")
        self.assertTrue(email["ok"], email)
        self.assertEqual(email["output"]["recipient"], "contact@acme.example")
        self.assertTrue(email["output"]["created"])
        self.assertFalse(duplicate["output"]["created"])
        self.assertEqual(len(pending.for_request(self.request_id)), 1)

    def test_clarifying_question_is_pending_not_sent(self):
        result = self.registry.call(
            "draft_clarifying_question",
            {"subject": "Which period?", "body": "Should this cover Q2 or Q3?"},
            MODEL,
            step="clarify",
        )
        self.assertTrue(result["ok"], result)
        record = pending.for_request(self.request_id)[0]
        self.assertEqual((record["kind"], record["status"]), ("clarifying_question", "pending"))


if __name__ == "__main__":
    unittest.main()
