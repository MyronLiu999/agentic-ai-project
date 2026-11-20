"""Run keys and the one resume entry (Milestone 2 setup; owner: claudea).

A run key names one run's checkpoint, wait, stop flag and hold:

    in a run.py run      the run ID (one key for the whole run)
    in the app           "<session_id>#<run_no>": one console session holds many runs, numbered by code

    key(run_id=None, session_id=None, run_no=None) -> str
    new_run(session_id) -> str          the next run of a console session (the run ID in run.py)
    current_key(session_id=None) -> str | None   the latest run of the session in scope, or None
    session_of(run_key) -> str
    live(session_id) -> list[str]       runs of the session that have not ended
    end(run_key, reason)                record that a run ended
    resume(run_key, event) -> Reply     the ONE way a waiting or crashed run carries on

`event` is {"kind": "outside_reply" | "approval" | "operator_turn" | "stop_resume" | "crash", ...}
plus what that kind brings (the reply text, the approval decision). Nothing resumes a run at start-up
on its own: a call reaches it (the operator's next turn, a stranger's reply, an approval).
"""

from __future__ import annotations

import contextlib
import contextvars

from sandbox import control as state_store
from harness import runtime
from harness.turns import Reply

_resuming: contextvars.ContextVar[str | None] = contextvars.ContextVar("resuming", default=None)


def key(run_id: str | None = None, session_id: str | None = None, run_no: int | None = None) -> str:
    if run_id:
        return str(run_id)
    if not session_id or run_no is None:
        raise ValueError("a run key needs a run_id, or a session_id and a run_no")
    return f"{session_id}#{int(run_no)}"


def session_of(run_key: str) -> str:
    return str(run_key).split("#", 1)[0]


def new_run(session_id: str) -> str:
    """Start the next run of a session and return its key. In a run.py run, the run ID."""
    run = runtime.current_run()
    if run is not None:
        _ensure(run.run_id, run.run_id, 1)
        return run.run_id
    with state_store.connect() as conn:
        row = conn.execute("SELECT MAX(run_no) FROM runs WHERE session_id = ?", (session_id,)).fetchone()
        run_no = int(row[0] or 0) + 1
        run_key = key(session_id=session_id, run_no=run_no)
        conn.execute("INSERT INTO runs (run_key, session_id, run_no, started_at) VALUES (?, ?, ?, ?)",
                     (run_key, session_id, run_no, state_store.now()))
    return run_key


def _ensure(run_key: str, session_id: str, run_no: int) -> None:
    with state_store.connect() as conn:
        conn.execute("INSERT OR IGNORE INTO runs (run_key, session_id, run_no, started_at) VALUES (?, ?, ?, ?)",
                     (run_key, session_id, run_no, state_store.now()))


def current_key(session_id: str | None = None) -> str | None:
    """The run in scope: the run.py run, or the session's latest run; None outside any run or session."""
    run = runtime.current_run()
    if run is not None:
        return run.run_id
    session_id = session_id or runtime.current_session()
    if not session_id:
        return None
    with state_store.connect() as conn:
        row = conn.execute("SELECT run_key FROM runs WHERE session_id = ? ORDER BY run_no DESC LIMIT 1",
                           (session_id,)).fetchone()
    return row["run_key"] if row else None


def first_turn(session_id: str) -> bool:
    """True before the session's (or the run.py run's) first task has started."""
    run = runtime.current_run()
    session_id = run.run_id if run is not None else session_id
    with state_store.connect() as conn:
        row = conn.execute("SELECT COUNT(*) FROM runs WHERE session_id = ?", (session_id,)).fetchone()
    return int(row[0]) == 0


def live(session_id: str) -> list[str]:
    with state_store.connect() as conn:
        rows = conn.execute("SELECT run_key FROM runs WHERE session_id = ? AND ended_at IS NULL ORDER BY run_no",
                            (session_id,)).fetchall()
    return [r["run_key"] for r in rows]


# A run that ends its turn for one of these has not finished: it waits, and resumes when a call reaches it.
WAITING = ("needs_answer", "awaiting_approval", "held", "stopped")


def end(run_key: str | None, reason: str) -> None:
    """Record that a run's turn ended; a waiting reason leaves it live."""
    if not run_key or reason in WAITING:
        return
    with state_store.connect() as conn:
        conn.execute("UPDATE runs SET ended_at = ?, end_reason = ? WHERE run_key = ?",
                     (state_store.now(), reason, run_key))


def resuming() -> str | None:
    """The run key being resumed in this call, if any (the registry's journal is read only then)."""
    return _resuming.get()


@contextlib.contextmanager
def _resume_scope(run_key: str):
    token = _resuming.set(run_key)
    try:
        yield
    finally:
        _resuming.reset(token)


def resume(run_key: str, event: dict) -> Reply:
    """Carry on a run from its last checkpoint. Writes already completed come back from the journal
    (agent/checkpoints.py) instead of running again; a write replays with the arguments the checkpoint
    saved, never new ones from the model."""
    from agent import checkpoints, events

    state = checkpoints.load(run_key)
    if state is None:
        return Reply(f"Nothing to resume for {run_key}: it has no checkpoint.")
    runtime.trace().event(events.RESUME, run_key=run_key, event_kind=str(event.get("kind")),
                          from_checkpoint=state.get("current_step"))
    checkpoints.clear_wait(run_key)
    with _resume_scope(run_key):
        if state.get("path") == "agent":
            from agent import loop
            result = loop.resume_from(state, event)
            return Reply(result.text, list(result.actions), result.waiting_for)
        if state.get("path") == "workflow":
            # MERGE-CHECK (claudea, C3): workflows re-enter from their saved step.
            raise NotImplementedError("resuming a workflow run is claudea's C3")
    raise ValueError(f"the checkpoint of {run_key} names no path it can resume")
