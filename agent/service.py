"""The agent's one entry point. The app and run.py reach the agent only through these functions
(harness/turns.py calls them). Routing lives in agent/router.py; the paths behind it are
agent/workflows.py (your code picks each step) and agent/loop.py (the model picks, bounded by
agent/bounds.py). Text from the outside channel is the stranger's, never the operator's: it enters
model calls labelled as theirs.
"""

from __future__ import annotations

import math
import json
import threading

from agent import domain_workflows, events, loop, router, workflows
from harness import runtime
from harness.turns import Reply
from sandbox import inbox, pending, reports, sales


_active_sessions = set()
_session_lock = threading.RLock()


def operator_turn(session_id: str, text: str) -> Reply:
    """Control commands remain responsive while a session's task is in flight."""
    from agent import checkpoints, context, memory, messages, notes, outside, runs, stop
    from harness.client import BudgetExceeded
    from policy import limits, rules
    caller_session = session_id
    run = runtime.current_run()
    session_id = run.run_id if run else session_id
    with _session_lock:
        busy = session_id in _active_sessions
    if busy and text.strip().split(' ', 1)[0].lower() in ('/resume', '/rollback'):
        stop.handle_command(session_id, '/stop')
        return Reply('Stop requested. The current call must finish and be recorded; retry resume or rollback afterward.')
    continuing = text.strip().split(' ', 1)[0].lower() in ('/resume', '/rollback')
    if continuing:
        with _session_lock:
            _active_sessions.add(session_id)
    try:
        command = stop.handle_command(session_id, text)
    finally:
        if continuing:
            with _session_lock:
                _active_sessions.discard(session_id)
    if command is not None:
        if continuing:
            _refresh_session_status(session_id)
            return _drain(session_id, command)
        return command
    if text.strip().startswith('/history'):
        query = text.strip()[len('/history'):].strip()
        return Reply(json.dumps(notes.search(session_id, query, limit=8), ensure_ascii=False))
    outside.expire(session_id)
    rule = limits.parse_limit(text)
    if rule:
        rules.add_rule(session_id, rule)
        notes.record(session_id, 'operator', text)
        return Reply('The stated limit is recorded and applies before subsequent tool calls.')
    live = runs.live(session_id)
    if not busy and len(live) == 1 and not text.lstrip().startswith('/'):
        state = checkpoints.load(live[0]) or {}
        from policy import flags
        if (state.get('path') and not state.get('waiting_for') and not state.get('held')
                and not flags.is_stopped(live[0])):
            return continue_run(live[0], {'kind': 'operator_turn', 'text': text})
    with _session_lock:
        active = session_id in _active_sessions
        live = runs.live(session_id)
        if active or live:
            taken = messages.intercept(session_id, text)
            if taken is not None:
                if active:
                    return taken
                queued = messages.next_queued(session_id)
                if not queued:
                    return taken
                text = queued['text'] if isinstance(queued, dict) else queued
                prefix = taken.text + '\n'
            else:
                prefix = ''
        else:
            prefix = ''
        _active_sessions.add(session_id)
    notes.record(session_id, 'operator', text)
    try:
        if runs.first_turn(session_id):
            memory.for_session(session_id)
        run_key = runs.new_run(session_id)
        if run:
            # The harness uses one ID for all sequential tasks in a session.
            from sandbox import control
            with control.connect() as conn:
                conn.execute('UPDATE runs SET ended_at = NULL, end_reason = NULL WHERE run_key = ?', (run_key,))
        reply = _execute_task(caller_session, text)
        state = checkpoints.load(run_key) or {}
        if state.get('resume_requested'):
            event = state['resume_requested']
            checkpoints.update(run_key, resume_requested=None)
            reply = runs.resume(run_key, event)
            state = checkpoints.load(run_key) or {}
        ends = [line for line in runtime.trace(session_id).lines() if line.get('type') == 'end']
        reason = state.get('end_reason') or (ends[-1].get('terminal_reason') if ends else events.DONE)
        if reply.waiting_for:
            reason = events.NEEDS_ANSWER
        elif state.get('waiting_for'):
            reason = events.AWAITING_APPROVAL
        runs.end(run_key, reason or events.DONE)
        reply.text = prefix + reply.text
    except stop.ControlStopped as exc:
        key = runs.current_key(session_id)
        checkpoints.update(key, stopped=True)
        runs.end(key, exc.reason)
        runtime.trace(session_id).end(exc.reason, detail='Operator control interrupted the run.')
        reply = Reply('The operator stopped this run; its completed effects are saved.')
    except (context.ContextBudgetError, BudgetExceeded) as exc:
        runs.end(runs.current_key(session_id), events.AGENT_BUDGET)
        runtime.trace(session_id).end(events.AGENT_BUDGET, detail=str(exc))
        reply = Reply('Context/session budget reached. Start a new session and consult /history. ' + str(exc))
    finally:
        with _session_lock:
            _active_sessions.discard(session_id)
    return _drain(session_id, reply)


def _drain(session_id, reply):
    from agent import messages
    queued = messages.next_queued(session_id)
    if queued:
        follow = operator_turn(session_id, queued)
        return Reply(reply.text + '\n' + follow.text, reply.actions + follow.actions, follow.waiting_for)
    return reply


def _refresh_session_status(session_id):
    from agent import checkpoints
    from sandbox import control
    with control.connect() as conn:
        keys = [r['run_key'] for r in conn.execute('SELECT run_key FROM runs WHERE session_id = ?', (session_id,))]
    for key in keys:
        state = checkpoints.load(key) or {}
        rid = state.get('request_id')
        if not rid or inbox.get(rid) is None:
            continue
        reason = state.get('end_reason')
        if state.get('cancelled'):
            inbox.set_status(rid, 'cancelled')
        elif state.get('held'):
            inbox.set_status(rid, 'held')
        elif reason == events.DONE:
            saved = reports.for_request(rid)
            drafted = any(p['kind'] == 'report_email' for p in pending.for_request(rid))
            inbox.set_status(rid, 'report_drafted' if drafted else 'report_saved' if saved else 'unfinished')
            checkpoints.update(key, stopped_wait=None)
        elif state.get('waiting_for'):
            inbox.set_status(rid, 'awaiting_answer' if state['waiting_for']['kind'] == 'outside' else 'awaiting_approval')


def continue_run(run_key, event):
    """All external continuation events share the same execution ownership and queue drain."""
    from agent import checkpoints, runs
    session_id = runs.session_of(run_key)
    with _session_lock:
        if session_id in _active_sessions:
            checkpoints.update(run_key, resume_requested=event)
            return Reply('The answer is saved; the current call will finish before this run continues.')
        _active_sessions.add(session_id)
    try:
        reply = runs.resume(run_key, event)
        _refresh_session_status(session_id)
    finally:
        with _session_lock:
            _active_sessions.discard(session_id)
    return _drain(session_id, reply)


def _execute_task(session_id: str, text: str) -> Reply:
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
        reply = domain_workflows.status_question(session_id, "Status for " + " ".join(ids))
        follow_up = router.report_follow_up(text)
        if follow_up and follow_up["quarter"]:
            reply.text += "\n" + _saved_comparisons(ids, follow_up["quarter"].upper())
        return reply
    if route.path == "agent" and route.use_case == "batch_reports" and runtime.switch("topology") == "split":
        from agent import split
        return split.run(session_id, route.request_ids, text)
    if route.path == "agent" and route.use_case == "batch_reports" and runtime.switch("plan.batch_reports") == "on":
        from agent import plan
        return plan.run(session_id, route.request_ids, text)
    replies = []
    for request_id in route.request_ids:
        if route.path == "workflow":
            from agent import runs, stop
            stop.notice(runs.current_key(session_id))
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
    from agent import checkpoints
    from policy import flags
    item = next((i for i in approvals.pending() if str(i.get('id')) == str(approval_id)), None)
    run_key = item.get('run_key') if item else None
    wait = (checkpoints.load(run_key) or {}).get('waiting_for') if run_key else None
    if (not item or not wait or wait.get('kind') != 'approval' or str(wait.get('ref')) != str(approval_id)
            or flags.is_stopped(run_key) or run_key not in runs.live(runs.session_of(run_key))):
        return Reply('This approval is stale, withdrawn, or belongs to a run that is no longer awaiting it.')
    item = approvals.decide(approval_id, approved, note)
    return continue_run(run_key, {'kind': 'approval', 'approval_id': approval_id,
                                  'approved': bool(approved), 'note': note})


def outside_statuses():
    from agent import outside
    return outside.statuses()
