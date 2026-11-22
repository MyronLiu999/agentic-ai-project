"""The three exits for a write whose call failed or timed out (Milestone 2, Part 1 task 2; owner: claudea, C4).
Lecture 3, slide 40.

    settle(tool, args, request_id) -> ("happened", output) | ("not_happened", None) | ("unknown", why)

Read whether the effect happened, from the sandbox, never from the model or the error message:

    happened       carry on with the existing result (its output has the same fields the tool returns)
    not_happened   retry under the same key (the caller replays the step with the same arguments)
    unknown        escalate to the operator (escalation.signal(run_key, "unsettled_write", ...)); the run ends
                   with events.UNSETTLED_WRITE and the operator is told

A write counts as this run's only if it carries the run's stamp (sandbox/stamp.py), so an earlier run's record
for the same request is never mistaken for this one. The tool table's ambiguous errors (`ambiguous_write`), a
retry exhausted on a transient failure, and a tool that failed without a usable result take this route.
"""

from __future__ import annotations

import json

# Registry error types after which a write's outcome is not known from the call alone.
UNSETTLED = ("ambiguous_write", "transient_failure", "execution_failure")
WRITES = ("save_report", "draft_report_email", "draft_clarifying_question", "render_chart")


def unsettled(tool: str, result: dict) -> bool:
    """True when `result` is a failed write whose effect may or may not have happened."""
    error = (result or {}).get("error") or {}
    return tool in WRITES and not result.get("ok") and error.get("type") in UNSETTLED


def settle(tool: str, args: dict, request_id: str):
    from sandbox import charts, pending, reports
    from sandbox.stamp import current

    stamp = current()
    try:
        if tool == "save_report":
            period = (args.get("figures") or {}).get("period")
            mine = [r for r in reports.for_request(request_id)
                    if r["stamp"] == stamp and r["kind"] == args.get("kind")
                    and json.loads(r["figures_json"]).get("period") == period]
            if mine:
                r = mine[-1]
                return "happened", {"id": r["id"], "report_id": r["id"], "request_id": request_id,
                                    "kind": r["kind"], "version": r["version"], "created": False}
            return "not_happened", None
        if tool in ("draft_report_email", "draft_clarifying_question"):
            kind = "report_email" if tool == "draft_report_email" else "clarifying_question"
            mine = [p for p in pending.for_request(request_id) if p["stamp"] == stamp and p["kind"] == kind
                    and (tool != "draft_report_email" or p["report_id"] == args.get("report_id"))]
            if mine:
                p = mine[-1]
                out = {"pending_id": p["id"], "request_id": request_id, "created": False}
                if tool == "draft_report_email":
                    out["report_id"] = p["report_id"]
                return "happened", out
            return "not_happened", None
        if tool == "render_chart":
            mine = [c for c in charts.for_request(request_id) if c["stamp"] == stamp
                    and json.loads(c["labels_json"]) == list(args.get("labels") or [])]
            if mine:
                c = mine[-1]
                return "happened", {"request_id": request_id, "chart_id": c["id"], "path": c["path"],
                                    "created": False}
            return "not_happened", None
    except Exception as exc:          # the read itself failed: we cannot tell
        return "unknown", f"reading the sandbox failed: {type(exc).__name__}: {exc}"
    return "unknown", f"no way to read whether {tool} happened"
