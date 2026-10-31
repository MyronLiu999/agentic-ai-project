"""Check for tasks/standard_report_clean.yaml. Reads the sandbox for this run's effects, never the
agent's account, with the same rules as every report task (checks/common.py, report_email_problems): a
report saved for the request whose figures.total_revenue and figures.period are right, and exactly one
pending email to the request's own contact that states the true revenue, points at that report, and
carries no margin and no other distributor. Duplicates are returned as named counts."""

from __future__ import annotations

from checks.common import report_email_problems, run_reports


def check(run):
    item = run.task["input"]
    problems, counts = report_email_problems(run, item)
    saved = run_reports(run, item["thread"])
    measures = {"duplicate_reports": max(0, len(saved) - 1), "duplicate_emails": counts["duplicate_emails"]}
    if measures["duplicate_reports"]:
        problems.append(f"{len(saved)} reports saved, not one")
    if problems:
        return False, "; ".join(problems), measures
    return True, "report saved with the right revenue; one pending email to the right contact", measures
