"""Checkpoints, the journal and waits (Milestone 2; owner: claudea).

A checkpoint holds one run's state, keyed by its run key (agent/runs.py), on a durable backend
(sandbox/control.py). It is not the memory store. Its fields:

    {"run_key", "use_case", "path" ("workflow" | "agent"), "request_id", "plan", "step_status",
     "completed_calls": [{"tool", "args", "key", "result"}], "findings", "current_step",
     "conversation" (optional, trimmed), "waiting_for", "held", "stopped"}

Everything is JSON-serializable: no open files or connections.

    save(run_key, state, mode="sync")        write a whole state
    update(run_key, mode="sync", **fields)   merge fields into the last state and save it
    load(run_key) -> dict | None             the last state
    history(run_key) -> list[dict]           every saved state, oldest first
    before_step(run_key, step)               the placement rule: save where a replay would repeat an effect
    after_call(run_key, call, result)        record a completed keyed write in the journal
    completed(run_key, key) -> dict | None   the journal: the recorded result of a completed write
    set_wait(run_key, kind, ref, deadline=None) / clear_wait(run_key) / waiting(session_id=None)
    to_trace(trace, run_key)                 the last checkpoint into the trace, when a run ends

The setup's before_step saves on every step it is given (a safe default). claudea's C2 narrows it to the
steps the decision table marks, and sets each kind of run's durability mode.
"""

from __future__ import annotations

import json

from agent import events
from sandbox import control as state_store

MODES = ("sync", "async", "exit")


def _dump(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def save(run_key: str, state: dict, mode: str = "sync") -> dict:
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    state = {**state, "run_key": run_key}
    text = _dump(state)        # raises if something in the state does not serialize
    with state_store.connect() as conn:
        conn.execute("INSERT INTO checkpoints (run_key, saved_at, mode, state_json) VALUES (?, ?, ?, ?)",
                     (run_key, state_store.now(), mode, text))
    return state


def load(run_key: str) -> dict | None:
    with state_store.connect() as conn:
        row = conn.execute("SELECT state_json FROM checkpoints WHERE run_key = ? ORDER BY id DESC LIMIT 1",
                           (run_key,)).fetchone()
    return json.loads(row["state_json"]) if row else None


def history(run_key: str) -> list[dict]:
    with state_store.connect() as conn:
        rows = conn.execute("SELECT state_json FROM checkpoints WHERE run_key = ? ORDER BY id",
                            (run_key,)).fetchall()
    return [json.loads(r["state_json"]) for r in rows]


def update(run_key: str, mode: str = "sync", **fields) -> dict:
    state = load(run_key) or {"completed_calls": [], "step_status": {}, "findings": {}}
    state.update(fields)
    return save(run_key, state, mode)


# -- where a checkpoint goes (C2) -----------------------------------------------------------------------
#
# Resuming replays everything since the last checkpoint (Lecture 4, slides 10 to 13). A step needs a checkpoint
# before it only if replaying it would repeat an effect no key closes, or would redo work too costly to repeat:
#
#   agent loop, every model round   YES: the model writes the next call's arguments; on a replay it may write
#                                    others, which gives a new key and a second effect. So the conversation is
#                                    saved before each round and a resume replays from it, not from the model's
#                                    memory. (abraham's loop may also save the call itself before it runs:
#                                    step kind "tool_call", which is saved too.)
#   workflow write, args fixed by code before it runs (render_chart, save_report, out_of_scope's decline)
#                                    NO: the key comes from the step id, so a replay gets the first result back.
#   workflow write whose args came from model calls (standard_report's 6-email: the body was drafted and passed
#   the critique in model calls)    YES: after a read too costly to repeat, so a resume reuses the passed draft.
#   reads (parse_file, query_sales) NO: safe to repeat; their results are kept in the journal for reuse anyway.

def needs_checkpoint(step: dict) -> bool:
    if step.get("path") == "agent":
        return True
    return bool(step.get("args_from_model"))


# The durability mode, per kind of run (slide 12): how each save is written. Every save here is a synchronous
# SQLite commit; the mode records the decision and the reason, and a pass could relax it.
#   sync   any run with an irreversible step (send_report_email: an emailed report cannot be recalled). The agent
#          path may reach it once myron's gated send is in, so every agent run is sync.
#   async  a run whose only writes are keyed and reversible (standard_report, out_of_scope): a crash in the gap
#          loses at most the step in flight, and its key closes the replay.
#   exit   a run that only reads (status_question: it answers the operator from records); a crash loses the
#          answer, which the operator's next turn asks again.
MODES_BY_USE_CASE = {
    "standard_report": "async", "out_of_scope": "async", "status_question": "exit",
    "messy_file": "sync", "compare_check": "sync", "batch_reports": "sync",
}


def mode_for(step: dict) -> str:
    if step.get("path") == "agent":
        return "sync"
    return MODES_BY_USE_CASE.get(step.get("use_case") or "", "sync")


def before_step(run_key: str | None, step: dict) -> bool:
    """Called before a step runs. `step` carries what the caller knows: {"path", "request_id", "use_case",
    "workflow", "step" (a workflow or plan step id), "tool", "args", "args_from_model", "conversation", ...}.
    Saves a checkpoint only where needs_checkpoint says so; returns whether it saved."""
    if not run_key or not needs_checkpoint(step):
        return False
    mode = mode_for(step)
    fields = {k: v for k, v in step.items() if k != "step"}
    update(run_key, mode=mode, current_step=step.get("step") or step.get("tool"), **fields)
    try:
        from harness import runtime
        runtime.trace().event(events.RUN_CHECKPOINT, run_key=run_key, mode=mode,
                              current_step=step.get("step") or step.get("tool"))
    except Exception:
        pass
    return True


def start(run_key: str | None, **fields) -> None:
    """Record what a run is, before its first step, so a resume knows its path and request (cheap; no replay
    window opens here)."""
    if run_key:
        update(run_key, **fields)


# -- the journal of finished steps (slide 37: each finished call and its result, so a replay skips it) ------

def record_step(run_key: str | None, step_id: str, tool: str, args: dict, output) -> None:
    """A finished workflow step and its output, reads included, so a resume reuses it instead of calling again."""
    if not run_key:
        return
    with state_store.connect() as conn:
        conn.execute("INSERT OR IGNORE INTO journal (run_key, key, tool, args_json, result_json, at) "
                     "VALUES (?, ?, ?, ?, ?, ?)",
                     (run_key, f"step:{step_id}", tool, _dump(args or {}), _dump(output), state_store.now()))


def step_result(run_key: str | None, step_id: str):
    """The recorded output of a finished step, or None."""
    if not run_key:
        return None
    with state_store.connect() as conn:
        row = conn.execute("SELECT result_json FROM journal WHERE run_key = ? AND key = ?",
                           (run_key, f"step:{step_id}")).fetchone()
    return json.loads(row["result_json"]) if row else None


def after_call(run_key: str | None, call: dict, result: dict) -> None:
    """Record a successful keyed write: `call` is {"tool", "args", "key"}."""
    if not run_key or not call.get("key") or not result.get("ok"):
        return
    with state_store.connect() as conn:
        conn.execute("INSERT OR IGNORE INTO journal (run_key, key, tool, args_json, result_json, at) "
                     "VALUES (?, ?, ?, ?, ?, ?)",
                     (run_key, call["key"], call["tool"], _dump(call.get("args") or {}), _dump(result),
                      state_store.now()))
    state = load(run_key) or {"completed_calls": []}
    done = [c for c in state.get("completed_calls") or [] if c.get("key") != call["key"]]
    done.append({"tool": call["tool"], "args": call.get("args") or {}, "key": call["key"], "result": result})
    update(run_key, completed_calls=done)


def completed(run_key: str | None, key: str | None) -> dict | None:
    if not run_key or not key:
        return None
    with state_store.connect() as conn:
        row = conn.execute("SELECT result_json FROM journal WHERE run_key = ? AND key = ?",
                           (run_key, key)).fetchone()
    return json.loads(row["result_json"]) if row else None


def set_wait(run_key: str, kind: str, ref: str, deadline: str | None = None) -> None:
    from agent import runs
    with state_store.connect() as conn:
        conn.execute("INSERT OR REPLACE INTO waits (run_key, session_id, kind, ref, deadline, since) "
                     "VALUES (?, ?, ?, ?, ?, ?)",
                     (run_key, runs.session_of(run_key), kind, str(ref), deadline, state_store.now()))
    update(run_key, waiting_for={"kind": kind, "ref": str(ref), "deadline": deadline})
    try:
        from harness import runtime
        runtime.trace().event(events.WAIT, run_key=run_key, kind=kind, ref=str(ref), deadline=deadline)
    except Exception:
        pass


def clear_wait(run_key: str) -> None:
    with state_store.connect() as conn:
        conn.execute("DELETE FROM waits WHERE run_key = ?", (run_key,))
    if load(run_key) is not None:
        update(run_key, waiting_for=None)


def waiting(session_id: str | None = None) -> list[dict]:
    sql, args = "SELECT * FROM waits", ()
    if session_id:
        sql, args = sql + " WHERE session_id = ?", (session_id,)
    with state_store.connect() as conn:
        return [dict(r) for r in conn.execute(sql + " ORDER BY since", args).fetchall()]


def to_trace(trace, run_key: str | None) -> None:
    if not run_key:
        return
    state = load(run_key)
    if state is not None:
        trace.event(events.FINAL_CHECKPOINT, run_key=run_key, state=state)
