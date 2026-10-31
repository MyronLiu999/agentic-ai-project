"""Abraham's fixtures use the real seed and checks, without calling a model."""

import csv
import io

import channel
from harness import ROOT, tasks
from sandbox import files, inbox, pending, reports, sales
from tests.support import ScratchTest, fixed_run


MESSY_TASK = "tests/fixtures/agent_messy_file.yaml"
THREAD = "SYN-thread-agent-messy"


class AgentFixtureTest(ScratchTest):
    def test_messy_fixture_seeds_one_scoped_request_and_preserves_the_upload(self):
        task = tasks.load(ROOT / MESSY_TASK)
        with fixed_run(task, "fixture-messy"):
            requests = inbox.all_requests()
            self.assertEqual(len(requests), 1)
            request = requests[0]
            self.assertEqual(request["thread_id"], THREAD)
            self.assertEqual(request["distributor_id"], "SYN-DIST-002")
            self.assertEqual(request["contact_email"], "contact@brightline.example")
            self.assertEqual(request["period"], "2026Q3")

            upload = files.read_upload(request["id"], request["file_name"])
            rows = list(csv.reader(io.StringIO(upload), delimiter=";"))
            self.assertEqual(rows, [
                ["Artikel", "Menge", "Netto_Betrag"],
                ["SYN-SKU-003", "98", "2940,00"],
                ["SYN-SKU-004", "42", "1890,00"],
            ])
            messages = channel.messages(THREAD)
            self.assertEqual(len(messages), 1)
            self.assertTrue(messages[0].from_outside)
            self.assertTrue(messages[0].seeded)
            self.assertEqual(messages[0].text, request["question"])
            self.assertEqual(reports.for_request(request["id"]), [])
            self.assertEqual(pending.for_request(request["id"]), [])

    def test_messy_fixture_rejects_a_completion_claim_without_effects(self):
        result = self.run_check(MESSY_TASK, lambda run: None, replies=["Done."])
        self.assertFalse(result["passed"])
        self.assertIn("no report", result["reason"])

    def test_messy_fixture_accepts_a_correct_report_and_pending_email(self):
        def plant(run):
            rid = inbox.request_id(THREAD)
            figures = sales.distributor_sales("SYN-DIST-002", "2026Q3")
            report, _ = reports.save(rid, "standard", figures, "Q3 report",
                                     key=f"{run.run_id}-report")
            pending.add("report_email", rid, THREAD, "contact@brightline.example",
                        "Q3 report", f"Your Q3 revenue was {figures['total_revenue']:,.2f}.",
                        key=f"{run.run_id}-email", report_id=report["id"])

        result = self.run_check(MESSY_TASK, plant)
        self.assertTrue(result["passed"], result["reason"])
        self.assertEqual(result["measures"], {"duplicate_reports": 0, "duplicate_emails": 0})
