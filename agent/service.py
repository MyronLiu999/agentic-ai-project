"""The agent's one entry point. The app and run.py reach the agent only through these functions
(harness/turns.py calls them). Routing lives in agent/router.py; the paths behind it are
agent/workflows.py (your code picks each step) and agent/loop.py (the model picks, bounded by
agent/bounds.py). Text from the outside channel is the stranger's, never the operator's: it enters
model calls labelled as theirs.
"""

from __future__ import annotations

import math

from agent import domain_workflows, events, loop, router, workflows
from harness import runtime
from harness.turns import Reply
from sandbox import inbox, pending, reports, sales


def operator_turn(session_id: str, text: str) -> Reply:
    """One message from the operator: route the case to its path, run it, reply."""
    trace = runtime.trace(session_id)
    # Milestone 2 setup seams, in this order (PLAN_M2.md 3.3): a console command before any model sees the
    # text; a stated limit becomes a rule the hook reads; a message to a session whose run has not finished;
    # memory read before the session's first model call; then a new run number for this task.
    from agent import memory, messages, runs, stop
    from policy import limits, rules
    command = stop.handle_command(session_id, text)
    if command is not None:
        return command
    rule = limits.parse_limit(text)
    if rule:
        rules.add_rule(session_id, rule)
    if runs.live(session_id):
        taken = messages.intercept(session_id, text)
        if taken is not None:
            return taken
    if runs.first_turn(session_id):
        memory.for_session(session_id)
    runs.new_run(session_id)
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
        reply = domain_workflows.status_question(session_id, "Status for " + " ".join(ids))
        follow_up = router.report_follow_up(text)
        if follow_up and follow_up["quarter"]:
            reply.text += "\n" + _saved_comparisons(ids, follow_up["quarter"].upper())
        return reply
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
            result = loop.run(session_id, request_id, text,
                              comparison_required=route.use_case == "compare_check")
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
        if line.get("type") == events.ROUTE and line.get("request_ids"):
            return tuple(rid for rid in line.get("request_ids", []) if inbox.get(rid) is not None)
    return ()


def _saved_comparisons(ids, quarter):
    """Explain recorded comparisons without starting another reporting task."""
    lines = []
    for rid in ids:
        saved = reports.latest(rid)
        figures = reports.figures(saved) if saved else {}
        period = figures.get("period")
        try:
            previous = sales.previous_period(period)
        except (TypeError, ValueError, IndexError):
            previous = ""
        current, before = figures.get("total_revenue"), figures.get("previous_total_revenue")
        if (not previous.endswith(quarter) or
                any(type(n) not in (int, float) or not math.isfinite(n) for n in (current, before))):
            lines.append(f"{rid}: No saved comparison from {quarter} is available.")
            continue
        delta = current - before
        direction = "increased" if delta >= 0 else "decreased"
        lines.append(f"{rid}: Revenue {direction} by {abs(delta):,.2f}, from {before:,.2f} in "
                     f"{previous} to {current:,.2f} in {period}.")
    return "\n".join(lines)


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
    """A stranger's answer on a thread (agent/outside.py, abraham): the run waiting on it resumes."""
    from agent import outside
    return outside.on_reply(thread_id, text)


def pending_approvals() -> list[dict]:
    """Every gated call waiting for the operator (agent/approvals.py, myron), each with its session_id."""
    from agent import approvals
    return approvals.pending()


def decide_approval(approval_id: str, approved: bool, note: str = "") -> Reply | None:
    """The operator's answer on the approvals page; the run it held resumes (agent/runs.py)."""
    from agent import approvals, runs
    item = approvals.decide(approval_id, approved, note)
    run_key = item.get("run_key") if isinstance(item, dict) else None
    if not run_key:
        return Reply(f"Approval {approval_id} recorded.")
    return runs.resume(run_key, {"kind": "approval", "approval_id": approval_id, "approved": bool(approved),
                                 "note": note})
