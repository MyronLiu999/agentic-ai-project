"""Requests: a distributor's file and question, one per thread."""

from __future__ import annotations

from sandbox import db
from sandbox.stamp import current


def request_id(thread_id: str) -> str:
    return f"REQ-{thread_id}"


def add(thread_id: str, distributor_id: str, contact_email: str, question: str,
        file_name: str | None = None, period: str | None = None, stamp: str | None = None) -> str:
    rid = request_id(thread_id)
    with db.connect() as conn:
        conn.execute("INSERT OR REPLACE INTO requests (id, thread_id, distributor_id, contact_email, question, "
                     "file_name, period, status, created_at, stamp) VALUES (?, ?, ?, ?, ?, ?, ?, 'new', ?, ?)",
                     (rid, thread_id, distributor_id, contact_email, question, file_name, period, db.NOW,
                      stamp or current()))
    return rid


def get(rid: str) -> dict | None:
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM requests WHERE id = ?", (rid,)).fetchone()
    return dict(row) if row else None


def by_thread(thread_id: str) -> dict | None:
    return get(request_id(thread_id))


def all_requests() -> list[dict]:
    with db.connect() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM requests ORDER BY created_at, id")]


def set_status(rid: str, status: str) -> None:
    with db.connect() as conn:
        conn.execute("UPDATE requests SET status = ? WHERE id = ?", (status, rid))
