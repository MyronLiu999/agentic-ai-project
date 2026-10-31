"""The agent's one entry point. The app and run.py reach the agent only through these functions
(harness/turns.py calls them). Routing lives in agent/router.py; the paths behind it are
agent/workflows.py (your code picks each step) and agent/loop.py (the model picks, bounded by
agent/bounds.py). Text from the outside channel is the stranger's, never the operator's: it enters
model calls labelled as theirs.
"""

from __future__ import annotations

from agent import domain_workflows, events, loop, router, workflows
from harness import runtime
from harness.turns import Reply
from sandbox import inbox, pending, reports


def operator_turn(session_id: str, text: str) -> Reply:
    """One message from the operator: route the case to its path, run it, reply."""
    trace = runtime.trace(session_id)
    try:
        route = router.route_operator_message(session_id, text)
    except router.RoutingError as exc:
        trace.end(events.DECLINED, detail=f"Routing requires clarification: {exc}")
        return Reply(str(exc))
    if route.use_case == "status_question":
        ids = route.request_ids or _last_selection(trace)
        if not ids:
            trace.end(events.DONE, detail="No requests selected in this session")
            return Reply("No requests have been selected in this session. Name a request or thread to check its status.")
        # The workflow's bare-status default is all records; provide only resolved IDs.
        return domain_workflows.status_question(session_id, "Status for " + " ".join(ids))
    if route.path == "agent" and route.use_case == "batch_reports" and runtime.switch("plan.batch_reports") == "on":
        from agent import plan
        return plan.run(session_id, route.request_ids, text)
    replies = []
    for request_id in route.request_ids:
        if route.path == "workflow":
            if route.use_case == "out_of_scope":
                reply = domain_workflows.out_of_scope(session_id, request_id)
            elif route.use_case == "standard_report":
                run_workflow = getattr(workflows, "standard_report", None)
                if run_workflow is None:
                    raise NotImplementedError("The standard_report workflow is not integrated yet")
                reply = run_workflow(session_id, request_id)
            else:
                raise ValueError(f"No workflow for {route.use_case!r}")
        elif route.path == "agent":
            result = loop.run(session_id, request_id, text)
            reply = _agent_reply(request_id, result)
        else:
            raise ValueError(f"Unknown execution path: {route.path!r}")
        replies.append(reply)
        if reply.waiting_for:
            break
        if route.path == "agent" and result.reason != events.DONE:
            break
    return Reply("\n".join(r.text for r in replies if r.text),
                 [action for r in replies for action in r.actions],
                 next((r.waiting_for for r in replies if r.waiting_for), None))


def _last_selection(trace) -> tuple[str, ...]:
    """Recover scope from the session's durable trace, including after a restart."""
    for line in reversed(trace.lines()):
        if line.get("type") == events.ROUTE and line.get("use_case") != "status_question":
            return tuple(rid for rid in line.get("request_ids", []) if inbox.get(rid) is not None)
    return ()


def _agent_reply(request_id: str, result: loop.LoopResult) -> Reply:
    """Only recorded effects justify request state; model prose never marks it done."""
    text = result.text
    if result.waiting_for:
        inbox.set_status(request_id, "awaiting_answer")
    elif result.reason == events.CRITIQUE_HELD:
        inbox.set_status(request_id, "held")
    elif result.reason == events.DONE:
        saved = {r["id"] for r in reports.for_request(request_id)}
        emails = [p for p in pending.for_request(request_id)
                  if p["kind"] == "report_email" and p["report_id"] in saved]
        if emails:
            inbox.set_status(request_id, "report_drafted")
            text = "A saved report and its email draft are recorded; the operator controls sending."
        else:
            inbox.set_status(request_id, "unfinished")
            text = "The agent stopped. A saved report with an email draft was not confirmed."
    else:
        inbox.set_status(request_id, "unfinished")
    return Reply(f"{request_id}: {text}", [f"{request_id}: {action}" for action in result.actions], result.waiting_for)


def on_outside_reply(thread_id: str, text: str) -> Reply:
    """A stranger's answer on a thread. Milestone 2's: ignored until then."""
    return Reply()


def pending_approvals() -> list[dict]:
    """Empty until Milestone 2: the pending records on the product page are not approvals."""
    return []


def decide_approval(approval_id: str, approved: bool, note: str = "") -> Reply | None:
    raise NotImplementedError("decide_approval: no approval gate is built yet")
