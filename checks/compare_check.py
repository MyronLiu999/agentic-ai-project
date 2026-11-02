"""Check for tasks/compare_check_last_quarter.yaml: the report this run saved carries this quarter's
revenue and last quarter's (both from the database), and there is one pending email to the contact
leaking nothing. The operator's follow-up is scored only as a claim: a reply that says "up" or "down"
must agree with the database."""

from __future__ import annotations

from checks.common import previous_revenue, report_email_problems, truth_revenue
from sandbox.report_validation import wrong_direction_claims


def check(run):
    item = run.task["input"]
    now = truth_revenue(run, item["distributor"], item["period"])
    before = previous_revenue(run, item["distributor"], item["period"])
    problems, counts = report_email_problems(run, item, extra_value=before)
    direction = "up" if now > before else "down" if now < before else "unchanged"
    claims_wrong = any(wrong_direction_claims(str(reply.get("text", "")), now, before, item["period"])
                       for reply in run.replies)
    counts["wrong_direction_claimed"] = int(claims_wrong)
    if claims_wrong:
        problems.append(f"a reply makes an incorrect revenue direction claim; the database says {direction} "
                        f"({before:,.2f} to {now:,.2f})")
    if problems:
        return False, "; ".join(problems), counts
    return True, f"report with Q3 {now:,.2f} and Q2 {before:,.2f}; one pending email to the contact", counts
