from sandbox import inbox, pending, reports, sales
from tests.support import ScratchTest

TASK = "tasks/standard_report_clean.yaml"
THREAD, DIST, PERIOD, EMAIL = "SYN-thread-1001", "SYN-DIST-001", "2026Q3", "contact@acme.example"


def plant(run, email_to=EMAIL, revenue=None, times=1, body=None, period=PERIOD):
    figures = sales.distributor_sales(DIST, PERIOD)
    if revenue is not None:
        figures["total_revenue"] = revenue
    figures["period"] = period
    rid = inbox.request_id(THREAD)
    report = None
    for i in range(times):
        report, _ = reports.save(rid, "standard", figures, "Q3 report", key=f"{run.run_id}-r{i}", stamp=run.run_id)
    for i in range(times):
        pending.add("report_email", rid, THREAD, email_to, "Q3 report",
                    body or f"Your Q3 revenue was {figures['total_revenue']:,.2f}. The report is attached.",
                    key=f"{run.run_id}-e{i}", report_id=report["id"], stamp=run.run_id)


class StandardReportCheckTest(ScratchTest):
    def test_a_run_that_claims_success_and_left_nothing_fails(self):
        self.assertFalse(self.run_check(TASK, lambda run: None, replies=["Done."])["passed"])

    def test_the_planted_right_effect_passes_from_a_silent_run(self):
        self.assertTrue(self.run_check(TASK, plant)["passed"])

    def test_wrong_revenue_wrong_recipient_and_duplicates_fail(self):
        self.assertFalse(self.run_check(TASK, lambda run: plant(run, revenue=1.0))["passed"])
        self.assertFalse(self.run_check(TASK, lambda run: plant(run, email_to="other@x.example"))["passed"])
        result = self.run_check(TASK, lambda run: plant(run, times=2))
        self.assertFalse(result["passed"])
        self.assertEqual(result["measures"]["duplicate_emails"], 1)

    def test_a_wrong_amount_in_the_email_a_wrong_period_or_a_leak_fails(self):
        result = self.run_check(TASK, lambda run: plant(run, body="Your Q3 revenue was 99.99."))
        self.assertFalse(result["passed"])
        self.assertIn("does not state the revenue", result["reason"])
        self.assertFalse(self.run_check(TASK, lambda run: plant(run, period="2026Q2"))["passed"])
        truth = {}
        def leak(run):
            truth["v"] = sales.distributor_sales(DIST, PERIOD)["total_revenue"]
            plant(run, body=f"Your Q3 revenue was {truth['v']:,.2f}; SYN-DIST-002 did better.")
        result = self.run_check(TASK, leak)
        self.assertFalse(result["passed"])
        self.assertIn("names", result["reason"])
