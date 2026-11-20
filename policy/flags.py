"""Stop flags, written by the operator's /stop and read by the hook first (Milestone 2 setup).

    set_stop(session_id, run_no=None, at=None)   /stop: every live run of the session; /stop <n>: run n
    clear_stop(run_key, at=None)                 /resume <n>: lift the flag, recorded with its time
    is_stopped(run_key) -> bool                  the hook asks this before anything else
    log(run_key) -> list[dict]                   every flag that applies to the run, with its times

A session-wide stop reaches the runs that started before it; a later run is not stopped by it. A flag
for one run overrides the session's. In a run.py run the session is the run ID.
"""

from __future__ import annotations

from sandbox import control as state_store


def _target(session_id: str, run_no) -> str:
    return f"{session_id}#*" if run_no is None else f"{session_id}#{int(run_no)}"


def set_stop(session_id: str, run_no: int | None = None, at: str | None = None) -> str:
    target = _target(session_id, run_no)
    with state_store.connect() as conn:
        conn.execute("INSERT OR REPLACE INTO stops (target, session_id, set_at, cleared_at) VALUES (?, ?, ?, NULL)",
                     (target, session_id, at or state_store.now()))
    return target


def stop_run(run_key: str, at: str | None = None) -> str:
    """Stop one run by its key (a run.py run ID, or "<session>#<n>")."""
    from agent import runs
    with state_store.connect() as conn:
        conn.execute("INSERT OR REPLACE INTO stops (target, session_id, set_at, cleared_at) VALUES (?, ?, ?, NULL)",
                     (run_key, runs.session_of(run_key), at or state_store.now()))
    return run_key


def clear_stop(run_key: str, at: str | None = None) -> None:
    from agent import runs
    stamp = at or state_store.now()
    with state_store.connect() as conn:
        conn.execute("INSERT OR REPLACE INTO stops (target, session_id, set_at, cleared_at) VALUES (?, ?, "
                     "COALESCE((SELECT set_at FROM stops WHERE target = ?), ?), ?)",
                     (run_key, runs.session_of(run_key), run_key, stamp, stamp))


def is_stopped(run_key: str | None) -> bool:
    if not run_key:
        return False
    from agent import runs
    with state_store.connect() as conn:
        own = conn.execute("SELECT cleared_at FROM stops WHERE target = ?", (run_key,)).fetchone()
        if own is not None:
            return own["cleared_at"] is None
        session = runs.session_of(run_key)
        wide = conn.execute("SELECT set_at, cleared_at FROM stops WHERE target = ?", (f"{session}#*",)).fetchone()
        if wide is None or wide["cleared_at"] is not None:
            return False
        started = conn.execute("SELECT started_at FROM runs WHERE run_key = ?", (run_key,)).fetchone()
    return started is None or started["started_at"] <= wide["set_at"]


def log(run_key: str) -> list[dict]:
    from agent import runs
    session = runs.session_of(run_key)
    with state_store.connect() as conn:
        rows = conn.execute("SELECT * FROM stops WHERE target IN (?, ?) ORDER BY set_at",
                            (run_key, f"{session}#*")).fetchall()
    return [dict(r) for r in rows]
