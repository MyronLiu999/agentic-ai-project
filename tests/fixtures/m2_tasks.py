"""Free task backends shared by split and real-process recovery matrices."""

from pathlib import Path


def task_backend(path, *, split=False):
    """Select a model that follows the task's real operator/approval script."""
    task = Path(path).stem
    if task in {"approval_send_report", "approval_send_declined"}:
        return "tests.test_approval:SendsAfterApproval"
    if task == "outside_units":
        return "tests.fixtures.outside_m2:OutsideModel"
    if task == "long_campaign":
        return "tests.fixtures.context_session_model:LongSessionModel"
    if split and task == "batch_reports_two":
        return "tests.fixtures.split_model:SplitModel"
    # The milestone model reads real parsed files and sales, including the
    # authoritative correction for escalation and operator memory preferences.
    return "tests.fixtures.agent_milestone_model:MilestoneModel"
