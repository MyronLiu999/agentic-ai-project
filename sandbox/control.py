"""The durable file behind run control state (Milestone 2 setup; owner: claudea; agent/checkpoints.py, agent/runs.py and policy/ read and write it).

One SQLite file in the sandbox's state folder, `control.sqlite3`, holds what must survive a crash or a
restart and is not domain data: checkpoints and their journal (agent/checkpoints.py), the run numbers of
each console session (agent/runs.py), waits, stop flags (policy/flags.py) and stated limits
(policy/rules.py). Everything in it is JSON text, so nothing open (files, connections) is ever saved.

`make serve` keeps it; `make app`, `make seed` and every run.py run reset it with the sandbox
(sandbox/seed.py calls reset()). It is not the memory store: memory outlives the run (agent/memory.py).
"""

from __future__ import annotations

import contextlib
import sqlite3

from harness.paths import state_dir

FILENAME = "control.sqlite3"

SCHEMA = """
CREATE TABLE IF NOT EXISTS checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT, run_key TEXT NOT NULL, saved_at TEXT NOT NULL,
    mode TEXT NOT NULL, state_json TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS checkpoints_by_run ON checkpoints(run_key, id);
CREATE TABLE IF NOT EXISTS journal (
    run_key TEXT NOT NULL, key TEXT NOT NULL, tool TEXT NOT NULL, args_json TEXT NOT NULL,
    result_json TEXT NOT NULL, at TEXT NOT NULL, PRIMARY KEY (run_key, key));
CREATE TABLE IF NOT EXISTS runs (
    run_key TEXT PRIMARY KEY, session_id TEXT NOT NULL, run_no INTEGER NOT NULL, started_at TEXT NOT NULL,
    ended_at TEXT, end_reason TEXT);
CREATE TABLE IF NOT EXISTS waits (
    run_key TEXT PRIMARY KEY, session_id TEXT NOT NULL, kind TEXT NOT NULL, ref TEXT NOT NULL,
    deadline TEXT, since TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS stops (
    target TEXT PRIMARY KEY, session_id TEXT NOT NULL, set_at TEXT NOT NULL, cleared_at TEXT);
CREATE TABLE IF NOT EXISTS rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL, rule_json TEXT NOT NULL, created TEXT NOT NULL);
"""


def path():
    return state_dir() / FILENAME


@contextlib.contextmanager
def connect():
    """A connection that creates the schema if needed, commits on success and always closes."""
    path().parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path(), timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        with conn:
            yield conn
    finally:
        conn.close()


def reset() -> None:
    """Empty every table (the sandbox reset calls this; `make serve` never does)."""
    with connect() as conn:
        for table in ("checkpoints", "journal", "runs", "waits", "stops", "rules"):
            conn.execute(f"DELETE FROM {table}")


def now() -> str:
    from harness.trace import now as trace_now
    return trace_now()
