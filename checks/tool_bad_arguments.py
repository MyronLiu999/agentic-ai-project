"""Verify negative-probe traces and real sandbox effects, independently of model claims."""

import json

from checks.helpers import connect, sent_by_agent
from sandbox import db


TOOLS = {"parse_file", "query_sales", "render_chart", "save_report",
         "draft_report_email", "draft_clarifying_question"}


def check(run):
    lines = [json.loads(line) for line in run.trace_path.read_text(encoding="utf-8").splitlines()]
    calls = [line for line in lines if line.get("type") == "tool_call"]
    with connect(run, db.FILENAME) as conn:
        writes = sum(conn.execute(f"SELECT COUNT(*) FROM {table} WHERE stamp = ?", (run.run_id,)).fetchone()[0]
                     for table in ("reports", "pending", "charts"))
    measures = {"rejected_tool_calls": sum(bool(call.get("is_error")) for call in calls),
                "writes": writes, "email_gate_rejections": sum(call.get("rejected_by") == "loop" for call in calls)}
    if writes or sent_by_agent(run, run.task["input"]["thread"]):
        return False, "The negative probe created a write or sent a message.", measures
    if len(calls) != 6 or {call["name"] for call in calls} != TOOLS:
        return False, "Expected exactly one recorded call per tool.", measures
    models = [line for line in lines if line.get("type") == "model_call"]
    if (len(models) != 2 or {call["name"] for call in models[0].get("tool_calls", [])} != TOOLS
            or models[1].get("text") != "BadArgs verified 6 error results; no successful action claimed."):
        return False, "Missing evidence that the model requested and received all six errors.", measures
    for call in calls:
        output = call.get("output")
        if isinstance(output, str):
            output = json.loads(output)
        error = output.get("error") if isinstance(output, dict) else None
        if (not call.get("is_error") or not isinstance(error, dict)
                or error.get("kind") != "protocol" or not error.get("message")):
            return False, f"{call['name']}: missing a complete flagged protocol error.", measures
        if call["name"] != "draft_report_email" and not error.get("repair"):
            return False, f"{call['name']}: missing Registry repair guidance.", measures
    return True, "Six model-requested bad calls rejected; model received errors; no effects written.", measures
