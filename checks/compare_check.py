"""Check for tasks/compare_check_last_quarter.yaml: the report this run saved carries this quarter's
revenue and last quarter's (both from the database), and there is one pending email to the contact
leaking nothing. The operator's follow-up is scored only as a claim: a reply that says "up" or "down"
must agree with the database."""

from __future__ import annotations

from checks.common import previous_revenue, report_email_problems, truth_revenue


def check(run):
    item = run.task["input"]
    now = truth_revenue(run, item["distributor"], item["period"])
    before = previous_revenue(run, item["distributor"], item["period"])
    problems, counts = report_email_problems(run, item, extra_value=before)
    said = " ".join(str(r.get("text", "")) for r in run.replies).lower()
    direction = "up" if now > before else "down"
    wrong = "down" if direction == "up" else "up"
    wrong_words = {"up": ("increase", "grew", "higher", " up "), "down": ("decrease", "fell", "lower", " down ")}[wrong]
    right_words = {"up": ("increase", "grew", "higher", " up "), "down": ("decrease", "fell", "lower", " down ")}[direction]
    claims_wrong = any(w in f" {said} " for w in wrong_words) and not any(w in f" {said} " for w in right_words)
    counts["wrong_direction_claimed"] = int(claims_wrong)
    if claims_wrong:
        problems.append(f"a reply says revenue went {wrong}, but the database says {direction} "
                        f"({before:,.2f} to {now:,.2f})")
    if problems:
        return False, "; ".join(problems), counts
    return True, f"report with Q3 {now:,.2f} and Q2 {before:,.2f}; one pending email to the contact", counts
