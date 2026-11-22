"""Resolve uncertain writes using exact keys and durable delivery receipts."""
from __future__ import annotations

UNSETTLED = ("ambiguous_write", "transient_failure", "execution_failure")
WRITES = ("save_report", "draft_report_email", "draft_clarifying_question", "render_chart",
          "ask_stranger", "send_report_email")


class UnsettledWrite(RuntimeError):
    """An operator hold now owns resolution; no further effects may proceed."""


def unsettled(tool: str, result: dict) -> bool:
    error = (result or {}).get("error") or {}
    return tool in WRITES and not result.get("ok") and error.get("type") in UNSETTLED


def write_key(reg, tool, args, step=None):
    # Test/decorator registries may wrap the production registry without changing its identity.
    while not hasattr(reg, "write_key") and hasattr(reg, "real"):
        reg = reg.real
    return reg.write_key(tool, args, step=step) if hasattr(reg, "write_key") else None


def settle(tool: str, args: dict, request_id: str, key: str | None = None):
    from sandbox import charts, db, deliveries, email_packages, pending, reports
    if not key:
        return "unknown", "the exact write key is unavailable"
    try:
        table = {"save_report": "reports", "render_chart": "charts", "draft_report_email": "pending",
                 "draft_clarifying_question": "pending", "ask_stranger": "pending"}.get(tool)
        if tool == "send_report_email":
            row = pending.get(int(args["pending_id"]))
            if row is None or row["request_id"] != request_id or row["kind"] != "report_email":
                return "unknown", "the target draft cannot be verified"
        elif table:
            with db.connect() as conn:
                found = conn.execute(f"SELECT * FROM {table} WHERE key=? AND request_id=?", (key, request_id)).fetchone()
            row = dict(found) if found else None
            if row is None:
                return "not_happened", None
        else:
            return "unknown", f"no way to inspect {tool}"
        if tool == "save_report":
            return "happened", {"id": row["id"], "report_id": row["id"], "request_id": request_id,
                                "kind": row["kind"], "version": row["version"], "created": False}
        if tool == "render_chart":
            from pathlib import Path
            if not Path(row["path"]).is_file():
                return "unknown", "the chart record exists but its artifact is missing"
            import json
            return "happened", {"request_id": request_id, "chart_id": row["id"], "path": row["path"],
                                "artifact": row["path"], "bars_rendered": len(json.loads(row["labels_json"])),
                                "truncated": len(args.get("labels", [])) > len(json.loads(row["labels_json"])),
                                "created": False}
        out = {"id": row["id"], "pending_id": row["id"], "request_id": request_id,
               "kind": row["kind"], "recipient": row["recipient"], "status": row["status"], "created": False}
        if tool == "draft_report_email":
            out["report_id"] = row["report_id"]
        if tool in ("draft_report_email", "draft_clarifying_question"):
            if row["status"] == "discarded":
                return "unknown", "the draft was discarded"
            return "happened", out
        # A claimed send without its receipt is ambiguous, even if similar text is on the thread.
        if row["status"] == "pending":
            return "not_happened", None
        receipt = deliveries.get(row["id"])
        if receipt is None or row["status"] not in ("sent", "sending", "send_failed"):
            return "unknown", "no durable receipt confirms this delivery"
        import channel
        from agent.tools import _email_text
        expected = args["question"] if tool == "ask_stranger" else _email_text(row, email_packages.saved(row["id"]))
        matches = [m for m in channel.messages(row["thread_id"]) if m.id == receipt["message_id"]
                   and m.sender == channel.AGENT and m.text == expected == receipt["body"]]
        if not matches:
            return "unknown", "the recorded delivery cannot be verified on its thread"
        if row["status"] == "sending":
            if not pending.complete_send(row["id"]):
                return "unknown", "the delivery status changed during settlement"
        elif row["status"] != "sent":
            return "unknown", "the delivery status requires operator inspection"
        out = {"request_id": request_id, "pending_id": row["id"], "thread_id": row["thread_id"], "created": False}
        if tool == "ask_stranger":
            out["message_id"] = receipt["message_id"]
        else:
            email_packages.link_message(row["id"], receipt["message_id"])
            out.update(sent_id=receipt["message_id"], recipient=row["recipient"])
        return "happened", out
    except Exception as exc:
        return "unknown", f"reading the sandbox failed: {type(exc).__name__}: {exc}"


def resolve(reg, tool, args, caller, result, *, request_id, run_key, step=None, trace_step=None):
    """Read the outcome; retry once only when absent; otherwise hold for inspection."""
    if not unsettled(tool, result):
        return result
    from agent import checkpoints, escalation
    key = write_key(reg, tool, args, step)
    for attempt in range(2):
        outcome, found = settle(tool, args, request_id, key)
        if outcome == "happened":
            recovered = {"ok": True, "output": found, "is_error": False, "error": None}
            checkpoints.after_call(run_key, {"tool": tool, "args": args, "key": key}, recovered)
            return recovered
        if outcome != "not_happened" or attempt:
            break
        result = reg.call(tool, args, caller, step=step, trace_step=trace_step)
        if not unsettled(tool, result):
            return result
    why = found if isinstance(found, str) else f"{tool} failed twice; retry allowance exhausted"
    packet = escalation.signal(run_key, "unsettled_write", attempted=f"{tool} for {request_id} (step {step})",
                               why=why, needs="the operator to inspect this exact effect before retrying or discarding")
    raise UnsettledWrite(escalation.packet_text(packet))
