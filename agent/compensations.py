"""Compensations, for rollback and for irreversible-steps-last (Milestone 2; owner: claudea, C4).

    compensate(call_record) -> {"compensated_by": name | "none", "result": ...}
        call_record is a checkpoint's completed call {"tool", "args", "key", "result"}.
        agent.registry.Registry.compensate calls this for any tool whose ToolSpec has no compensate of its
        own, so abraham's /rollback and the workflows' compensate-in-reverse use one table. Never offered to
        the model: the operator's /rollback or code calls it.

    UNDO   what undoes each write; None where nothing can (a sent email, a question already sent)

Every compensation is itself safe to repeat: a second call finds nothing left to undo and says so.
"""

from __future__ import annotations

UNDO = {
    "save_report": "withdraw that report version, so the previous one is the latest again",
    "draft_report_email": "discard the pending record (only while it is still pending)",
    "draft_clarifying_question": "discard the pending record (only while it is still pending)",
    "render_chart": "delete the chart's row and file",
    "send_report_email": None,
    "ask_stranger": None,
}


def _output(call_record: dict) -> dict:
    result = call_record.get("result") or {}
    return (result.get("output") if isinstance(result, dict) and "output" in result else result) or {}


def compensate(call_record: dict) -> dict:
    tool = call_record.get("tool")
    out = _output(call_record)
    if tool == "save_report":
        from sandbox import reports
        report_id = out.get("report_id") or out.get("id")
        done = bool(report_id) and reports.withdraw(int(report_id))
        return {"compensated_by": "withdraw_report", "result": {"report_id": report_id, "undone": done}}
    if tool in ("draft_report_email", "draft_clarifying_question"):
        from sandbox import pending
        pending_id = out.get("pending_id")
        done = bool(pending_id) and pending.discard(int(pending_id))
        return {"compensated_by": "discard_pending", "result": {"pending_id": pending_id, "undone": done}}
    if tool == "render_chart":
        from sandbox import charts
        chart_id = out.get("chart_id")
        done = bool(chart_id) and charts.delete(int(chart_id))
        return {"compensated_by": "delete_chart", "result": {"chart_id": chart_id, "undone": done}}
    return {"compensated_by": "none", "result": None}
