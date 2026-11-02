"""Check for tasks/messy_file_semicolon.yaml (and the dev task): the file was decoded and set against the
database. A report saved by this run with the database's revenue and the file's unit total (the task's
`expect`, which the agent never reads), and one pending email to the request's own contact leaking nothing."""

from __future__ import annotations

from checks.common import report_figures, report_email_problems, run_reports
from sandbox.report_validation import named_number_problems


def check(run):
    item = run.task["input"]
    problems, counts = report_email_problems(run, item)
    units = run.task["expect"]["file_total_units"]
    saved = run_reports(run, item["thread"])
    decoded = bool(saved) and not named_number_problems(report_figures(saved[-1]), "file_total_units", units)
    counts["file_units_reported"] = int(decoded)
    if saved and not decoded:
        problems.append(f"the report does not carry the file's {units} units: the file was not decoded")
    if problems:
        return False, "; ".join(problems), counts
    return True, "file decoded; report with the database revenue and the file's units; one pending email", counts
