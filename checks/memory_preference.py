"""Check for tasks/memory_subject_preference.yaml (Milestone 2, claudea). Reads the sandbox, never the agent's
account: the standard report effects (checks/common.py, report_email_problems), and whether the one pending
email's subject starts with the prefix the operator stated in an earlier session (the task's expect:, which the
agent never reads). facts_used counts it: 1 if the remembered fact was used, else 0."""

from __future__ import annotations

from checks.common import report_email_problems, run_pending
from checks.helpers import requires_disclosure


@requires_disclosure
def check(run):
    item = run.task["input"]
    prefix = run.task["expect"]["subject_prefix"]
    problems, counts = report_email_problems(run, item)
    emails = run_pending(run, item["thread"], "report_email", active_only=True)
    used = sum(1 for e in emails if str(e["subject"]).startswith(prefix))
    measures = {"facts_used": min(used, 1), "duplicate_emails": counts["duplicate_emails"]}
    if emails and not used:
        problems.append(f"the email's subject {emails[-1]['subject']!r} does not start with the remembered {prefix!r}")
    if problems:
        return False, "; ".join(problems), measures
    return True, "report saved; one pending email whose subject uses the remembered prefix", measures
