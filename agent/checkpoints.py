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


def before_step(run_key: str | None, step: dict) -> None:
    """Called before a step runs. `step` carries what the caller knows: {"path", "request_id",
    "use_case", "step" (a workflow or plan step id), "tool", "args", "conversation", ...}."""
    if not run_key:
        return
    fields = {k: v for k, v in step.items() if k != "step"}
    update(run_key, current_step=step.get("step") or step.get("tool"), **fields)
    try:
        from harness import runtime
        runtime.trace().event(events.RUN_CHECKPOINT, run_key=run_key, mode="sync",
                              current_step=step.get("step") or step.get("tool"))
    except Exception:
        pass


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
