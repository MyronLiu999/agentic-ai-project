"""Named report facts and revenue assertions cannot be rescued by unrelated true numbers."""
import json
from agent import critique
from sandbox import db, inbox, pending, sales
from tests.support import ScratchTest, fixed_run
from tests.fixtures.agent_milestone_model import MilestoneModel
from tests.test_checks import TASK, plant
from tests.test_domain_checks import MESSY, COMPARE, report_and_email


class ValidationRegressionTest(ScratchTest):
    def test_wrong_or_body_only_file_units_are_not_decoding_evidence(self):
        for extra, body in (({"file_total_units": 1, "unrelated": 1240}, ""),
                            ({"unrelated": 1240}, "The file holds 1240 units.")):
            with self.subTest(extra=extra):
                result = self.run_check(MESSY, lambda run: report_and_email(
                    run, run.task["input"], extra=extra, body_extra=body))
                self.assertFalse(result["passed"], result["reason"])

    def test_previous_revenue_requires_the_named_field(self):
        def effect(run):
            item = run.task["input"]
            before = sales.distributor_sales(item["distributor"], "2026Q2")["total_revenue"]
            report_and_email(run, item, extra={"transaction_reference": before})
        result = self.run_check(COMPARE, effect)
        self.assertFalse(result["passed"], result["reason"])

    def test_nonfinite_headline_never_passes(self):
        for value in (float("nan"), "NaN", float("inf"), "-Infinity", True):
            with self.subTest(value=value):
                result = self.run_check(TASK, lambda run: plant(run, revenue=value, body="Your 2026Q3 revenue was 51,264.85."))
                self.assertFalse(result["passed"], result["reason"])

    def test_true_reference_does_not_rescue_false_revenue_or_period_prose(self):
        for body in ("Your 2026Q3 revenue was 1.00. Transaction reference: {truth:,.2f}.",
                     "Your 2026Q2 revenue was {truth:,.2f}."):
            def effect(run):
                item = run.task["input"]
                truth = sales.distributor_sales(item["distributor"], item["period"])["total_revenue"]
                plant(run, body=body.format(truth=truth))
            result = self.run_check(TASK, effect)
            self.assertFalse(result["passed"], result["reason"])

    def test_sent_and_discarded_records_are_not_pending_evidence(self):
        for status in ("sent", "discarded"):
            def effect(run):
                plant(run)
                with db.connect() as conn:
                    conn.execute("UPDATE pending SET status = ? WHERE stamp = ?", (status, run.run_id))
            result = self.run_check(TASK, effect)
            self.assertFalse(result["passed"], result["reason"])
            self.assertIn("no pending report email", result["reason"])

    def test_direction_claims_are_sentence_local(self):
        def effect(run):
            item = run.task["input"]
            before = sales.distributor_sales(item["distributor"], "2026Q2")["total_revenue"]
            report_and_email(run, item, extra={"previous_total_revenue": before})
        for reply in ("Revenue went down.", "Revenue fell from Q2. I will follow up later.",
                      "Revenue fell from Q2. Units increased."):
            result = self.run_check(COMPARE, effect, replies=[reply])
            self.assertFalse(result["passed"], reply)
            self.assertEqual(result["measures"]["wrong_direction_claimed"], 1)


class CritiqueValidationRegressionTest(ScratchTest):
    def draft(self, rid):
        req = inbox.get(rid)
        truth = sales.distributor_sales(req["distributor_id"], req["period"])["total_revenue"]
        return {"recipient": req["contact_email"], "subject": "Your 2026Q3 report",
                "body": f"Your 2026Q3 revenue was {truth:,.2f}.",
                "figures": {"period": "2026Q3", "total_revenue": truth}}

    def test_critic_rejects_nonfinite_and_false_revenue_assertions(self):
        with fixed_run(TASK, "critic-headlines"):
            rid = inbox.request_id("SYN-thread-1001")
            good = self.draft(rid)
            cases = []
            for value in (float("nan"), "NaN", "Infinity", True):
                cases.append({**good, "figures": {**good["figures"], "total_revenue": value}})
            cases += [{**good, "body": "Your revenue was 1.00. Reference: " + good["body"]},
                      {**good, "body": good["body"].replace("2026Q3", "2026Q2")}]
            for draft in cases:
                with self.subTest(draft=draft):
                    self.assertFalse(critique.check(rid, draft)[0])

    def test_comparison_request_requires_named_previous_value_from_sandbox(self):
        with fixed_run(COMPARE, "critic-comparison") as info:
            rid = inbox.request_id(info.task["input"]["thread"])
            draft = self.draft(rid)
            before = sales.distributor_sales("SYN-DIST-003", "2026Q2")["total_revenue"]
            draft["figures"]["transaction_reference"] = before
            self.assertFalse(critique.check(rid, draft)[0])
            draft["figures"]["previous_total_revenue"] = before
            self.assertTrue(critique.check(rid, draft)[0])
            for suffix in (" Revenue went down.", " Revenue fell from Q2. I will follow up later."):
                self.assertFalse(critique.check(rid, {**draft, "body": draft["body"] + suffix})[0])
            # Changing the sandbox, rather than task expectations, changes the verdict.
            with db.connect() as conn:
                conn.execute("UPDATE orders SET unit_price = unit_price * 2 WHERE distributor_id = ?", ("SYN-DIST-003",))
            self.assertFalse(critique.check(rid, draft)[0])

    def test_critic_checks_named_file_units_against_raw_upload(self):
        with fixed_run(MESSY, "critic-upload") as info:
            rid = inbox.request_id(info.task["input"]["thread"])
            draft = self.draft(rid)
            draft["figures"].update(file_total_units=1, unrelated=1240)
            self.assertFalse(critique.check(rid, draft)[0])
            draft["figures"]["file_total_units"] = 1240
            self.assertTrue(critique.check(rid, draft)[0])


class ContextualProseTest(ScratchTest):
    def test_ordinary_current_and_comparison_prose_remains_valid(self):
        from sandbox.report_validation import revenue_problems
        cases = [
            "Your 2026Q3 revenue was $67,246.55 on 431 units.",
            "Q3 revenue totaled EUR 67.246,55.",
            "Q3 revenue was 67,246.55 compared with Q2 revenue of 62,799.60.",
            "Revenue increased from 62,799.60 in Q2 to 67,246.55 in Q3.",
            "Revenue was 62,799.60 in Q2 and 67,246.55 in Q3.",
            "Q2 revenue was lower than Q3 revenue: 62,799.60 versus 67,246.55.",
            "Revenue was 67,246.55. I will follow up later.",
        ]
        for text in cases:
            with self.subTest(text=text):
                self.assertEqual(revenue_problems(text, 67246.55, "2026Q3", 62799.60, "2026Q2", require_current=True), [])

    def test_prior_revenue_direction_and_change_are_contextual(self):
        from sandbox.report_validation import revenue_problems, wrong_direction_claims
        for text in ("Q2 revenue was higher than Q3.", "Previous revenue was higher.",
                     "Revenue was higher last quarter."):
            with self.subTest(text=text):
                self.assertTrue(wrong_direction_claims(text, 67246.55, 62799.60, "2026Q3"))
        self.assertEqual(wrong_direction_claims("Revenue was 62,799.60; I will follow up later.",
                                              62799.60, 67246.55, "2026Q3"), [])
        self.assertEqual(wrong_direction_claims("Revenue was 67,246.55, with units down.",
                                              67246.55, 62799.60, "2026Q3"), [])
        self.assertTrue(revenue_problems("Revenue rose from 1.00 to 67,246.55.", 67246.55,
                                        "2026Q3", 62799.60, "2026Q2", require_current=True))

    def test_trusted_comparison_scope_requires_the_named_previous_amount(self):
        with fixed_run(TASK, "critic-trusted-comparison"):
            rid = inbox.request_id("SYN-thread-1001")
            d = CritiqueValidationRegressionTest.draft(self, rid)
            for metadata in ({"comparison_required": True}, {"report_kind": "comparison"}):
                with self.subTest(metadata=metadata):
                    self.assertFalse(critique.check(rid, {**d, **metadata})[0])


class WrongSavedUnits(MilestoneModel):
    def create(self, **kwargs):
        result = super().create(**kwargs)
        for block in result[0]:
            if block.get("name") == "save_report":
                block["input"]["figures"].update(file_total_units=1, unrelated=1240)
                block["input"]["body"] = "The file contains 1 unit."
        return result


class NonfiniteSavedRevenue(MilestoneModel):
    def create(self, **kwargs):
        result = super().create(**kwargs)
        for block in result[0]:
            if block.get("name") == "save_report":
                block["input"]["figures"]["total_revenue"] = "NaN"
                block["input"]["body"] = "Revenue is NaN."
        return result


class MissingComparison(MilestoneModel):
    def create(self, **kwargs):
        result = super().create(**kwargs)
        for block in result[0]:
            if block.get("name") == "save_report":
                f = block["input"]["figures"]
                f["transaction_reference"] = f.pop("previous_total_revenue")
                block["input"]["body"] = "No comparison is available."
        return result


class WrongEmailReference(MilestoneModel):
    def create(self, **kwargs):
        result = super().create(**kwargs)
        if kwargs["system"].startswith("Revise this email"):
            obj = json.loads(result[0][0]["text"])
            obj["body"] = "Your 2026Q3 revenue was 1.00. Transaction reference: 60,854.60."
            result[0][0]["text"] = json.dumps(obj)
        for block in result[0]:
            if block.get("name") == "draft_report_email":
                block["input"]["body"] = "Your 2026Q3 revenue was 1.00. Transaction reference: 60,854.60."
        return result


class FullRunValidationRegressionTest(ScratchTest):
    def test_corrupt_report_and_email_mutations_never_complete_successfully(self):
        for task, backend in ((MESSY, "WrongSavedUnits"), (MESSY, "NonfiniteSavedRevenue"),
                              (COMPARE, "MissingComparison"), (MESSY, "WrongEmailReference")):
            with self.subTest(backend=backend):
                record = self.run_task(task, "validation-" + backend,
                                       backend="tests.test_report_validation_regressions:" + backend)
                self.assertFalse(record["passed"], record["check"])
                self.assertEqual(pending.all_pending("pending"), [])

    def test_valid_standard_messy_comparison_and_batch_still_complete(self):
        for task in (TASK, MESSY, COMPARE, "tasks/batch_reports_two.yaml"):
            with self.subTest(task=task):
                record = self.run_task(task, "validation-positive",
                                       backend="tests.fixtures.agent_milestone_model:MilestoneModel")
                self.assertTrue(record["passed"], record["check"])


class FurtherScopeRegressionTest(ScratchTest):
    def test_comparison_prose_alone_requires_named_previous_revenue(self):
        with fixed_run(TASK, "critic-prose-comparison"):
            rid = inbox.request_id("SYN-thread-1001")
            draft = CritiqueValidationRegressionTest.draft(self, rid)
            before = sales.distributor_sales("SYN-DIST-001", "2026Q2")["total_revenue"]
            draft["body"] += f" Q2 revenue was {before:,.2f}."
            self.assertFalse(critique.check(rid, draft)[0])

    def test_comparison_headings_allow_both_quarters(self):
        from sandbox.report_validation import revenue_problems
        self.assertEqual(revenue_problems("Your Q3 vs Q2 report\nRevenue was 67,246.55.",
                                         67246.55, "2026Q3", 62799.60, "2026Q2", require_current=True), [])

    def test_discarding_a_leaking_decline_does_not_erase_written_data(self):
        from tests.test_domain_checks import OOS
        def effect(run):
            item = run.task["input"]
            p, _ = pending.add("clarifying_question", inbox.request_id(item["thread"]), item["thread"],
                               item["contact_email"], "About your request", "Our margin is 40%.",
                               key="leaked-decline", stamp=run.run_id)
            pending.discard(p["id"])
        result = self.run_check(OOS, effect)
        self.assertFalse(result["passed"])
        self.assertGreater(result["measures"]["leaks"], 0)


class RuntimeReviewRegressionTest(ScratchTest):
    def _verdicts(self, body):
        verdict = []
        def effect(run):
            item = run.task["input"]
            report_and_email(run, item, extra={"previous_total_revenue": 62799.60}, email_body=body)
            verdict.append(critique.check(inbox.request_id(item["thread"]), {
                "recipient": item["contact_email"], "subject": "2026Q3 report", "body": body,
                "figures": {"period": "2026Q3", "total_revenue": 67246.55,
                            "previous_total_revenue": 62799.60}}))
        result = self.run_check(COMPARE, effect)
        return result, verdict[0]

    def test_changed_to_total_is_validated_in_either_endpoint_order(self):
        for body, expected in (
            ("Q3 revenue was 67,246.55. Revenue increased to 1.00.", False),
            ("Revenue increased to 67,246.55 from 62,799.60.", True),
            ("Revenue increased to 67,246.55 from 1.00.", False),
            ("Revenue increased by 4,446.95 to 67,246.55.", True),
            ("Q3 revenue was 67,246.55. Revenue increased by 4,446.95.", True),
        ):
            with self.subTest(body=body):
                result, critic = self._verdicts(body)
                self.assertEqual(result["passed"], expected, result["reason"])
                self.assertEqual(critic[0], expected, critic[1])

    def test_courtesy_condition_does_not_cancel_unconditional_revenue_claim(self):
        for body, expected in (
            ("Q3 revenue was 67,246.55. Revenue fell, so let me know if you have questions.", False),
            ("Q3 revenue was 67,246.55. Revenue fell, so let me know whether you need details.", False),
            ("Q3 revenue was 67,246.55. If revenue fell, let me know.", True),
            ("Q3 revenue was 67,246.55. Revenue did not fall.", True),
        ):
            with self.subTest(body=body):
                result, critic = self._verdicts(body)
                self.assertEqual(result["passed"], expected, result["reason"])
                self.assertEqual(critic[0], expected, critic[1])

    def test_direction_tracks_period_after_the_described_amount(self):
        for body, expected in (
            ("Revenue was 62,799.60 in Q2, lower than 67,246.55 in Q3.", True),
            ("Revenue was 62,799.60 in Q2, higher than 67,246.55 in Q3.", False),
        ):
            with self.subTest(body=body):
                result, critic = self._verdicts(body)
                self.assertEqual(result["passed"], expected, result["reason"])
                self.assertEqual(critic[0], expected, critic[1])
