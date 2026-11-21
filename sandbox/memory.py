"""The memory store's table (Milestone 2, Part 1 task 7; owner: claudea). agent/memory.py holds the write
policy; this module only stores and reads.

One SQLite file in the sandbox, memory.sqlite3: `make serve` keeps it (the operator's later session reads it);
`make app`, `make seed` and every run.py run reset it with the sandbox, so a test task that is a later session
seeds the earlier session's records itself (seed(task)'s `memory:`). It is not a checkpoint: a checkpoint holds
one run's state; memory holds what outlives the run.

Every record carries its provenance: source (operator | stranger | system | private_data), written_at,
derived_or_ingested, confirmed. A record is never edited: a newer one supersedes it, and both stay, each saying
which replaced which.
"""

from __future__ import annotations

import contextlib
import json
import sqlite3

from harness.paths import state_dir

FILENAME = "memory.sqlite3"

SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, name TEXT NOT NULL, fact TEXT NOT NULL,
    value_json TEXT, source TEXT NOT NULL, written_at TEXT NOT NULL, derived_or_ingested TEXT NOT NULL,
    confirmed INTEGER NOT NULL, session_id TEXT, supersedes INTEGER, superseded_by INTEGER,
    last_read_at TEXT, read_count INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS records_by_name ON records(name, superseded_by);
CREATE TABLE IF NOT EXISTS committed (session_id TEXT PRIMARY KEY, lines_done INTEGER NOT NULL);
"""

FIELDS = ("id", "kind", "name", "fact", "value", "source", "written_at", "derived_or_ingested", "confirmed",
          "session_id", "supersedes", "superseded_by", "last_read_at", "read_count")


@contextlib.contextmanager
def connect():
    path = state_dir() / FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        with conn:
            yield conn
    finally:
        conn.close()


def _record(row) -> dict:
    out = dict(row)
    out["value"] = json.loads(out.pop("value_json")) if out.get("value_json") is not None else None
    out["confirmed"] = bool(out["confirmed"])
    return out


def reset() -> None:
    with connect() as conn:
        conn.execute("DELETE FROM records")
        conn.execute("DELETE FROM committed")


def insert(record: dict) -> dict:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO records (kind, name, fact, value_json, source, written_at, derived_or_ingested, confirmed, "
            "session_id, supersedes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (record["kind"], record["name"], record["fact"], json.dumps(record.get("value")), record["source"],
             record["written_at"], record["derived_or_ingested"], int(bool(record["confirmed"])),
             record.get("session_id"), record.get("supersedes")))
        if record.get("supersedes"):
            conn.execute("UPDATE records SET superseded_by = ? WHERE id = ?", (cur.lastrowid, record["supersedes"]))
        return _record(conn.execute("SELECT * FROM records WHERE id = ?", (cur.lastrowid,)).fetchone())


def current(name: str) -> dict | None:
    """The record that holds `name` now: the one nothing superseded."""
    with connect() as conn:
        row = conn.execute("SELECT * FROM records WHERE name = ? AND superseded_by IS NULL ORDER BY id DESC LIMIT 1",
                           (name,)).fetchone()
    return _record(row) if row else None


def active(kinds: tuple[str, ...] | None = None) -> list[dict]:
    """Every record nothing superseded, newest first; of the given kinds only, if any."""
    with connect() as conn:
        rows = conn.execute("SELECT * FROM records WHERE superseded_by IS NULL ORDER BY id DESC").fetchall()
    out = [_record(r) for r in rows]
    return [r for r in out if kinds is None or r["kind"] in kinds]


def all_records() -> list[dict]:
    with connect() as conn:
        return [_record(r) for r in conn.execute("SELECT * FROM records ORDER BY id").fetchall()]


def touch(ids: list[int], at: str) -> None:
    with connect() as conn:
        conn.executemany("UPDATE records SET last_read_at = ?, read_count = read_count + 1 WHERE id = ?",
                         [(at, i) for i in ids])


def delete(ids: list[int]) -> int:
    with connect() as conn:
        return sum(conn.execute("DELETE FROM records WHERE id = ?", (i,)).rowcount for i in ids)


def lines_done(session_id: str) -> int:
    with connect() as conn:
        row = conn.execute("SELECT lines_done FROM committed WHERE session_id = ?", (session_id,)).fetchone()
    return int(row["lines_done"]) if row else 0


def set_lines_done(session_id: str, n: int) -> None:
    with connect() as conn:
        conn.execute("INSERT OR REPLACE INTO committed (session_id, lines_done) VALUES (?, ?)", (session_id, n))
