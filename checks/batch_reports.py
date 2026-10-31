"""Check for tasks/batch_reports_two.yaml: for every request in the task, a report saved by this run with
the database's revenue and exactly one pending email to that request's contact, leaking nothing."""

from __future__ import annotations

from checks.common import report_email_problems


def check(run):
    problems, counts = [], {"reports": 0, "emails": 0, "duplicate_emails": 0, "requests_done": 0}
    for item in run.task["inputs"]:
        found, c = report_email_problems(run, item)
        problems += found
        for k in ("reports", "emails", "duplicate_emails"):
            counts[k] += c[k]
        counts["requests_done"] += int(not found)
    if problems:
        return False, "; ".join(problems), counts
    return True, f"all {len(run.task['inputs'])} requests: report and one pending email each", counts
