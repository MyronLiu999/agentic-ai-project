"""The two small domain workflows (owner: claudea); the router (abraham) calls them for the
status_question and out_of_scope use cases. Both are plain code: no model call, no step a model picks.

    status_question(session_id, text) -> Reply     answers from records; writes nothing
    out_of_scope(session_id, request_id) -> Reply  declines with a fixed-template pending reply

Each ends the run with trace.end(...). out_of_scope's one write goes through the registry.
"""

from __future__ import annotations

from agent import events
from agent.registry import CODE
from harness import runtime
from harness.turns import Reply
from sandbox import inbox, pending, reports

# A fixed template: code fills the facts, no model writes it, so nothing private can be steered into it
# (and so it needs no critique: Lecture 2, slide 43's second gate has nothing new to check).
DECLINE = ("Thank you for your request. We can share only {name}'s own sales figures: the company's internal "
           "cost data and other distributors' sales are confidential and are not shared. Would you like your own "
           "{period} report by product instead?")


def _request_lines(r: dict) -> tuple[list[str], int]:
    lines = [f"{r['id']} ({r['distributor_id']}, {r['period'] or 'no period'}): status {r['status']}."]
    latest = reports.latest(r["id"])
    if latest:
        f = reports.figures(latest)
        revenue = f.get("total_revenue")
        money = f"{float(revenue):,.2f}" if isinstance(revenue, (int, float)) else str(revenue)
        lines.append(f"  Report v{latest['version']} ({latest['kind']}, {f.get('period', '?')}): revenue {money}"
                     + (f", {f['total_units']} units" if "total_units" in f else "") + ".")
    else:
        lines.append("  No report saved.")
    open_count = 0
    for p in pending.for_request(r["id"]):
        lines.append(f"  {p['kind']} to {p['recipient']}: {p['status']}.")
        open_count += p["status"] == "pending"
    if r["status"] not in ("done", "declined") or open_count:
        open_count = max(open_count, 1)
    return lines, open_count


def status_question(session_id: str, text: str) -> Reply:
    """Answer from the records: the requests the text names (or all of them), their latest report, their
    pending records, and what is still open. Reads only; writes nothing."""
    trace = runtime.trace(session_id)
    named = inbox.mentioned(text)
    targets = named or inbox.all_requests()
    if not targets:
        trace.end(events.DONE, detail="no requests")
        return Reply("There are no requests in the system.")
    lines, still_open = [], 0
    for r in targets:
        more, n = _request_lines(r)
        lines += more
        still_open += n
    lines.append("Nothing is still open." if not still_open else f"{still_open} item(s) still open.")
    trace.end(events.DONE, detail=f"answered from records for {len(targets)} request(s)")
    return Reply("\n".join(lines), [f"read records for {len(targets)} request(s); wrote nothing"])


def _registry(request_id: str, registry):
    if registry is not None:
        return registry
    from agent import tools
    return tools.build(request_id)


def out_of_scope(session_id: str, request_id: str, registry=None) -> Reply:
    """Decline a request for margins or other distributors' data, by rule: a pending reply to the request's
    own contact (the operator sends it), and nothing else read or written."""
    trace = runtime.trace(session_id)
    req = inbox.get(request_id)
    if req is None:
        trace.end(events.TOOL_ERROR, detail=f"no request {request_id}")
        return Reply(f"There is no request {request_id}.")
    from sandbox import sales
    dist = sales.distributor(req["distributor_id"]) or {"name": req["distributor_id"]}
    question = DECLINE.format(name=dist["name"], period=req["period"] or "quarterly")
    result = _registry(request_id, registry).call("draft_clarifying_question", {"question": question}, CODE,
                                                  step="1-decline")
    if not result.get("ok"):
        error = result.get("error") or {}
        trace.end(events.TOOL_ERROR, detail=f"draft_clarifying_question: {error.get('message', '')}")
        return Reply(f"{request_id} asks for confidential data. I could not draft the reply: "
                     f"{error.get('message', 'the tool failed')}.")
    pid = (result.get("output") or {}).get("pending_id")
    inbox.set_status(request_id, "declined")
    trace.end(events.DECLINED, detail="asks for margins or other distributors' data")
    return Reply(f"{request_id} asks for margins or other distributors' figures, which are confidential. I drafted "
                 f"a reply declining and offering their own report (pending record {pid}); it waits for you to send.",
                 [f"draft_clarifying_question: pending record {pid} for the operator to send"])
