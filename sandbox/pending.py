"""Pending records: an action below the approval line, written down for the operator to do by hand
(a drafted email with figures, a clarifying question). 'Sent' in Milestone 1 means written here;
the operator sends it from the product page with channel.send(..., sender="operator")."""

from __future__ import annotations

from sandbox import db
from sandbox.stamp import current

KINDS = ("report_email", "clarifying_question")


def add(kind: str, request_id: str, thread_id: str, recipient: str, subject: str, body: str, key: str,
        report_id: int | None = None, stamp: str | None = None) -> tuple[dict, bool]:
    """Returns (record, created); a repeat of `key` returns the first record."""
    if kind not in KINDS:
        raise ValueError(f"kind {kind!r} must be one of {', '.join(KINDS)}")
    with db.connect() as conn:
        first = conn.execute("SELECT * FROM pending WHERE key = ?", (key,)).fetchone()
        if first:
            return dict(first), False
        cur = conn.execute("INSERT INTO pending (kind, request_id, thread_id, recipient, subject, body, report_id, "
                           "key, stamp, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                           (kind, request_id, thread_id, recipient, subject, body, report_id, key,
                            stamp or current(), db.NOW))
        return dict(conn.execute("SELECT * FROM pending WHERE id = ?", (cur.lastrowid,)).fetchone()), True


def get(pid: int) -> dict | None:
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM pending WHERE id = ?", (pid,)).fetchone()
    return dict(row) if row else None


def all_pending(status: str | None = None) -> list[dict]:
    with db.connect() as conn:
        if status:
            rows = conn.execute("SELECT * FROM pending WHERE status = ? ORDER BY id", (status,))
        else:
            rows = conn.execute("SELECT * FROM pending ORDER BY id")
        return [dict(r) for r in rows]


def for_request(request_id: str) -> list[dict]:
    with db.connect() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM pending WHERE request_id = ? ORDER BY id", (request_id,))]


def mark_sent(pid: int) -> None:
    with db.connect() as conn:
        conn.execute("UPDATE pending SET status = 'sent' WHERE id = ?", (pid,))


def discard(pid: int) -> bool:
    """The undo of a draft: a pending record the operator will not send. Only a record still pending;
    a sent one cannot be undone. Returns whether it was discarded."""
    with db.connect() as conn:
        cur = conn.execute("UPDATE pending SET status = 'discarded' WHERE id = ? AND status = 'pending'", (pid,))
        return cur.rowcount == 1
