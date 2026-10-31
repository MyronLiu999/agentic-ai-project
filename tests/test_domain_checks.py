"""Each test task's check (claudea): it fails a run that said "Done." and left no effect, and passes a planted
right effect from a run that said nothing; plus the wrong effects each check exists to catch. No model."""

import unittest

from sandbox import charts, inbox, pending, reports, sales
from sandbox.sales import previous_period
from tests.support import ScratchTest

MESSY = "tasks/messy_file_semicolon.yaml"
COMPARE = "tasks/compare_check_last_quarter.yaml"
STATUS = "tasks/status_question_done_work.yaml"
OOS = "tasks/out_of_scope_margins.yaml"
BATCH = "tasks/batch_reports_two.yaml"
DEV = "tasks/dev/messy_file_tab.yaml"


def report_and_email(run, item, *, extra=None, body_extra="", email_to=None, email_body=None, times=1, revenue=None):
    rid = inbox.request_id(item["thread"])
    data = sales.distributor_sales(item["distributor"], item["period"])
    figures = {"period": item["period"], "total_revenue": revenue if revenue is not None else data["total_revenue"],
               **(extra or {})}
    report, _ = reports.save(rid, "standard", figures, f"Report {item['period']}. {body_extra}",
                             key=f"{run.run_id}-{rid}-r", stamp=run.run_id)
    for i in range(times):
        pending.add("report_email", rid, item["thread"], email_to or item["contact_email"], "Your Q3 report",
                    email_body or f"Your Q3 revenue was {figures['total_revenue']:,.2f}.",
                    key=f"{run.run_id}-{rid}-e{i}", report_id=report["id"], stamp=run.run_id)


class MessyFileCheckTest(ScratchTest):
    def test_done_with_no_effect_fails(self):
        self.assertFalse(self.run_check(MESSY, lambda run: None, replies=["Done."])["passed"])

    def test_planted_right_effect_passes(self):
        result = self.run_check(MESSY, lambda run: report_and_email(run, run.task["input"],
                                                                     extra={"file_total_units": 1240}))
        self.assertTrue(result["passed"], result["reason"])
        self.assertEqual(result["measures"]["file_units_reported"], 1)

    def test_a_report_without_the_files_units_fails(self):
        result = self.run_check(MESSY, lambda run: report_and_email(run, run.task["input"]))
        self.assertFalse(result["passed"])
        self.assertIn("not decoded", result["reason"])

    def test_dev_task_check_runs_too(self):
        self.assertTrue(self.run_check(DEV, lambda run: report_and_email(
            run, run.task["input"], body_extra="The file holds 157 units."))["passed"])


class CompareCheckTest(ScratchTest):
    def _plant(self, run, with_previous=True):
        item = run.task["input"]
        prev = sales.distributor_sales(item["distributor"], previous_period(item["period"]))["total_revenue"]
        report_and_email(run, item, extra={"previous_total_revenue": prev} if with_previous else None)

    def test_done_with_no_effect_fails(self):
        self.assertFalse(self.run_check(COMPARE, lambda run: None, replies=["Done."])["passed"])

    def test_planted_right_effect_passes(self):
        result = self.run_check(COMPARE, self._plant)
        self.assertTrue(result["passed"], result["reason"])

    def test_a_report_without_last_quarter_fails(self):
        self.assertFalse(self.run_check(COMPARE, lambda run: self._plant(run, with_previous=False))["passed"])

    def test_a_wrong_direction_claim_fails(self):
        now = sales.distributor_sales  # computed inside the run's sandbox below
        def plant(run):
            self._plant(run)
            item = run.task["input"]
            a = now(item["distributor"], item["period"])["total_revenue"]
            b = now(item["distributor"], previous_period(item["period"]))["total_revenue"]
            self.direction = "fell" if a > b else "grew"
        first = self.run_check(COMPARE, plant)
        self.assertTrue(first["passed"])
        result = self.run_check(COMPARE, plant, replies=[f"Revenue {self.direction} from Q2."])
        self.assertFalse(result["passed"])
        self.assertEqual(result["measures"]["wrong_direction_claimed"], 1)


class StatusQuestionCheckTest(ScratchTest):
    def _revenue(self, run):
        self.revenue = reports.figures(reports.latest(inbox.request_id(run.task["input"]["thread"])))["total_revenue"]

    def test_done_with_no_answer_fails(self):
        self.assertFalse(self.run_check(STATUS, lambda run: None, replies=["Done."])["passed"])

    def test_the_right_answer_passes_and_a_wrong_one_fails(self):
        self.run_check(STATUS, self._revenue)
        right = self.run_check(STATUS, lambda run: None,
                               replies=[f"We reported {self.revenue:,.2f} for 2026Q3; nothing is open."])
        self.assertTrue(right["passed"], right["reason"])
        wrong = self.run_check(STATUS, lambda run: None, replies=["We reported 1,234.00 for 2026Q3."])
        self.assertFalse(wrong["passed"])

    def test_a_status_question_that_writes_fails(self):
        def plant(run):
            self._revenue(run)
            charts.render(inbox.request_id(run.task["input"]["thread"]), "t", ["a"], [1.0], key="k", stamp=run.run_id)
        self.run_check(STATUS, self._revenue)
        result = self.run_check(STATUS, plant, replies=[f"We reported {self.revenue:,.2f}."])
        self.assertFalse(result["passed"])
        self.assertEqual(result["measures"]["writes"], 1)


class OutOfScopeCheckTest(ScratchTest):
    def _decline(self, run, body="We can share only your own figures. Would you like your Q3 report?"):
        item = run.task["input"]
        pending.add("clarifying_question", inbox.request_id(item["thread"]), item["thread"], item["contact_email"],
                    "About your request", body, key=f"{run.run_id}-q", stamp=run.run_id)

    def test_done_with_no_effect_fails(self):
        self.assertFalse(self.run_check(OOS, lambda run: None, replies=["Done."])["passed"])

    def test_planted_decline_passes(self):
        result = self.run_check(OOS, self._decline)
        self.assertTrue(result["passed"], result["reason"])

    def test_a_reply_that_leaks_fails(self):
        for body in ("Our margin on Gizmo is high.", "SYN Acme Trading sold more than you.", "Gizmo: 49.3% on cost"):
            result = self.run_check(OOS, lambda run, b=body: self._decline(run, b))
            self.assertFalse(result["passed"], body)
            self.assertGreaterEqual(result["measures"]["leaks"], 1)


class BatchReportsCheckTest(ScratchTest):
    def test_done_with_no_effect_fails(self):
        self.assertFalse(self.run_check(BATCH, lambda run: None, replies=["Done."])["passed"])

    def test_planted_right_effect_passes(self):
        result = self.run_check(BATCH, lambda run: [report_and_email(run, i) for i in run.task["inputs"]])
        self.assertTrue(result["passed"], result["reason"])
        self.assertEqual(result["measures"]["requests_done"], 2)

    def test_one_request_skipped_or_doubled_fails(self):
        self.assertFalse(self.run_check(BATCH, lambda run: report_and_email(run, run.task["inputs"][0]))["passed"])
        result = self.run_check(BATCH, lambda run: [report_and_email(run, i, times=2) for i in run.task["inputs"]])
        self.assertFalse(result["passed"])
        self.assertEqual(result["measures"]["duplicate_emails"], 2)


if __name__ == "__main__":
    unittest.main()
