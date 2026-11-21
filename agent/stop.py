"""Operator controls at cooperative call boundaries; no model can lift a stop."""

from __future__ import annotations

from copy import deepcopy
import re

from agent import approvals, checkpoints, events, runs, tools
from harness import runtime
from harness.turns import Reply
from policy import flags
from sandbox import control

COMMAND = re.compile(r"^\s*/(stop|cancel|resume|rollback)(?:\s+(\d+))?\s*$", re.I)


class ControlStopped(Exception):
    def __init__(self, reason=events.STOPPED):
        self.reason = reason
        super().__init__(reason)


def session_key(session_id):
    run = runtime.current_run()
    return run.run_id if run is not None else session_id


def check(run_key):
    """Check before a model/tool call, including after a model returns tool calls."""
    if not run_key:
        return
    with control.connect() as conn:
        row = conn.execute("SELECT end_reason FROM runs WHERE run_key = ?", (run_key,)).fetchone()
    if row and row["end_reason"] == events.CANCELLED:
        raise ControlStopped(events.CANCELLED)
    if flags.is_stopped(run_key):
        raise ControlStopped()


def after_call(run_key):
    """After the registry journals an in-flight call, checkpoint an intervening stop."""
    try:
        check(run_key)
    except ControlStopped:
        checkpoints.update(run_key, stopped=True)
        checkpoints.to_trace(runtime.trace(runs.session_of(run_key)), run_key)
        raise


def notice(run_key):
    if not run_key:
        return
    check(run_key)
    state = checkpoints.load(run_key) or {}
    if state.get("stop_notice_shown"):
        return
    text = ("This run may write local reports or ask a disclosed clarification. Use /stop to interrupt; "
            "the call already running can finish. /cancel keeps its effects, /resume continues, "
            "and /rollback undoes only reversible writes.")
    trace = runtime.trace(runs.session_of(run_key))
    trace.event(events.NOTICE, run_key=run_key, text=text)
    trace.progress(text)
    checkpoints.update(run_key, stop_notice_shown=True)


def _target(session_id, number):
    if number is not None:
        with control.connect() as conn:
            row = conn.execute("SELECT run_key FROM runs WHERE session_id = ? AND run_no = ?",
                               (session_id, int(number))).fetchone()
        return row["run_key"] if row else None
    live = runs.live(session_id)
    return live[0] if len(live) == 1 else None


def _freeze(run_key):
    state = checkpoints.load(run_key) or {}
    packets = [deepcopy(item) for item in approvals.pending() if item.get("run_key") == run_key]
    flags.stop_run(run_key)
    withdrawn = approvals.withdraw(run_key)
    saved = state.get("withdrawn_approvals", [])
    saved.extend(item for item in packets if item.get("id") in withdrawn)
    checkpoints.update(run_key, stopped=True, withdrawn_approvals=saved,
                       stopped_wait=state.get("waiting_for") or state.get("stopped_wait"))
    checkpoints.to_trace(runtime.trace(runs.session_of(run_key)), run_key)


def handle_command(session_id: str, text: str) -> Reply | None:
    match = COMMAND.fullmatch(text or "")
    if not match:
        if re.match(r"^\s*/(?:stop|cancel|resume|rollback)\b", text or "", re.I):
            return Reply("Use /stop [run number], /cancel <n>, /resume <n>, or /rollback <n>.")
        return None
    session_id = session_key(session_id)
    command, number = match.group(1).lower(), match.group(2)
    trace = runtime.trace(session_id)
    if command == "stop" and number is None:
        target = flags.set_stop(session_id)
        for run_key in runs.live(session_id):
            _freeze(run_key)
        trace.event(events.STOP, run_key=target, command="stop", set_at=control.now())
        return Reply("Stopped every live run in this session. An in-flight call may finish and is recorded. "
                     "Use /resume <n>, /cancel <n>, or /rollback <n>.")
    run_key = _target(session_id, number)
    if run_key is None:
        return Reply("No unique run selected. Give an existing run number from this session.")
    state = checkpoints.load(run_key)
    if state is None:
        return Reply(f"Run {run_key} has no saved state.")
    trace.event(events.STOP, run_key=run_key, command=command, set_at=control.now())
    if command in ("stop", "cancel", "rollback"):
        _freeze(run_key)
    if command == "stop":
        return Reply(f"Stopped {run_key}; an in-flight call may finish. Use /resume, /cancel, or /rollback with its number.")
    if command == "cancel":
        checkpoints.clear_wait(run_key)
        checkpoints.update(run_key, cancelled=True)
        runs.end(run_key, events.CANCELLED)
        return Reply(f"Cancelled {run_key}. Its completed effects remain; /rollback can undo reversible ones.")
    if command == "rollback":
        return _rollback(run_key)
    return _resume(run_key, session_id)


def _resume(run_key, session_id):
    state = checkpoints.load(run_key) or {}
    with control.connect() as conn:
        row = conn.execute("SELECT ended_at, end_reason FROM runs WHERE run_key = ?", (run_key,)).fetchone()
    if state.get("cancelled") or (row and row["end_reason"] == events.CANCELLED):
        return Reply(f"Run {run_key} was cancelled and cannot resume. Start a new task.")
    if any(item.get("compensated_by") != "none" for item in state.get("compensations", [])):
        return Reply(f"Run {run_key} has undone effects. Start a new task; its old journal cannot resume safely.")
    if row and row["ended_at"]:
        return Reply(f"Run {run_key} has already ended. Start a new task.")
    if not flags.is_stopped(run_key):
        return Reply(f"Run {run_key} is not stopped.")
    flags.clear_stop(run_key)
    checkpoints.update(run_key, stopped=False, stop_notice_shown=False)
    notice(run_key)
    packets = state.get("withdrawn_approvals") or []
    if packets:
        ids = []
        replaced = {}
        for packet in packets:
            if packet.get("plan") is not None:
                approval_id = approvals.put_up_plan(run_key, session_id, packet["plan"], packet["gated_steps"])
            else:
                approval_id = approvals.put_up(run_key, session_id, packet["call"],
                                               packet["action_class"], packet["screen"])
            ids.append(approval_id)
            replaced[packet["id"]] = approval_id
        fields = {"withdrawn_approvals": []}
        plan_state = deepcopy(state.get("plan_state"))
        if plan_state and plan_state.get("pending_approval", {}).get("id") in replaced:
            saved = plan_state["pending_approval"]
            saved["id"] = replaced[saved["id"]]
            fields["plan_state"] = plan_state
        split_state = deepcopy(state.get("split_state"))
        if split_state and split_state.get("approval_id") in replaced:
            split_state["approval_id"] = replaced[split_state["approval_id"]]
            fields["split_state"] = split_state
        checkpoints.update(run_key, **fields)
        checkpoints.set_wait(run_key, "approval", ids[0])
        return Reply(f"Resumed {run_key}; the withdrawn approval must be answered again ({', '.join(ids)}).")
    wait = state.get("stopped_wait") or state.get("waiting_for")
    if wait and wait.get("kind") == "outside":
        if state.get("outside_reply"):
            from agent import notes
            exchange = state.get("outside_exchange") or {}
            checkpoints.clear_wait(run_key)
            checkpoints.update(run_key, stopped_wait=None, outside_exchange={**exchange, "status": "answered"})
            notes.record(session_id, "stranger", state["outside_reply"].get("text", ""))
            notes.update(session_id, done=[state["request_id"]], ids=[wait["ref"]])
            return runs.resume(run_key, {"kind": "stop_resume"})
        checkpoints.set_wait(run_key, "outside", wait["ref"], wait.get("deadline"))
        return Reply(f"Resumed {run_key}; still waiting for the stranger's answer.", waiting_for=wait["ref"])
    return runs.resume(run_key, {"kind": "stop_resume"})


def _rollback(run_key):
    state = checkpoints.load(run_key) or {}
    registry = tools.build(state.get("request_id"))
    undone = list(state.get("compensations") or [])
    completed = {item["key"] for item in undone}
    lines = []
    for call in reversed(state.get("completed_calls") or []):
        key = call.get("key")
        if key in completed:
            continue
        if state.get("compensation_in_flight"):
            lines.append("A compensation has an unknown outcome; inspect it before further rollback.")
            break
        checkpoints.update(run_key, compensation_in_flight=key)
        try:
            result = registry.compensate({**call, "caller": "code", "operator_command": "rollback"})
        except Exception as exc:
            lines.append(f"{call['tool']}: outcome unknown ({type(exc).__name__}); inspect before retrying.")
            break
        entry = {"key": key, "tool": call["tool"], **result}
        undone.append(entry)
        checkpoints.update(run_key, compensations=undone, compensation_in_flight=None)
        runtime.trace(runs.session_of(run_key)).event(events.COMPENSATION, run_key=run_key, tool=call["tool"],
                                                     key=key, compensated_by=result["compensated_by"],
                                                     operator_command="rollback")
        lines.append(f"{call['tool']}: {result['compensated_by']}")
    checkpoints.to_trace(runtime.trace(runs.session_of(run_key)), run_key)
    return Reply(f"Rollback for {run_key}; the run remains stopped.\n" + ("\n".join(lines) or "No uncompensated writes remain."))
