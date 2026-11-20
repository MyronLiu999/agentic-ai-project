"""Compensations, for rollback and for irreversible-steps-last (Milestone 2; owner: claudea, C4).

    compensate(call_record) -> {"compensated_by": name | "none", "result": ...}
        call_record is a checkpoint's completed call {"tool", "args", "key", "result"}.
        agent.registry.Registry.compensate calls this for any tool whose ToolSpec has no compensate of its
        own, so abraham's /rollback and claudea's three exits use one table. Never offered to the model.

    UNDO   what undoes each write; None where nothing can (a sent email, a question already sent)

Setup stub: nothing is undone yet ("none" for every tool). claudea's C4 builds the entries below on the
sandbox's own modules (sandbox/reports.py, sandbox/pending.py, sandbox/charts.py).
"""

from __future__ import annotations

UNDO = {
    "save_report": "restore the report's previous version (or remove a first version)",
    "draft_report_email": "discard the pending record",
    "draft_clarifying_question": "discard the pending record",
    "render_chart": "delete the chart artifact",
    "send_report_email": None,
    "ask_stranger": None,
}


def compensate(call_record: dict) -> dict:
    return {"compensated_by": "none", "result": None}
