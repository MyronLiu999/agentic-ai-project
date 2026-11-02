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
        # New work must stay visible even when it arrives just after a send completed.
        # Replayed keys return above, so historical sent records do not reopen requests.
        conn.execute("UPDATE requests SET status = ? WHERE id = ? AND status = 'done'",
                     ("awaiting_answer" if kind == "clarifying_question" else "report_drafted", request_id))
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
    """Record seeded historical delivery. Live delivery must claim_send then complete_send."""
    with db.connect() as conn:
        conn.execute("UPDATE pending SET status = 'sent' WHERE id = ? AND status = 'pending'", (pid,))


def claim_send(pid: int) -> dict | None:
    """Durably reserve a draft before the channel effect, across threads and processes.

    A crash leaves 'sending' for inspection; it must never become automatically retryable.
    Discard uses the same pending-only condition, so exactly one action can claim a draft.
    """
    with db.connect() as conn:
        claimed = conn.execute("UPDATE pending SET status = 'sending' WHERE id = ? AND status = 'pending'", (pid,))
        if claimed.rowcount != 1:
            return None
        return dict(conn.execute("SELECT * FROM pending WHERE id = ?", (pid,)).fetchone())


def fail_send(pid: int) -> None:
    """Delivery may have happened: preserve the draft, but prohibit send/discard/retry."""
    with db.connect() as conn:
        conn.execute("UPDATE pending SET status = 'send_failed' WHERE id = ? AND status = 'sending'", (pid,))


def complete_send(pid: int) -> bool:
    """Finish a claimed delivery and its fulfilled request in one transaction.

    A report closes only its current version, with no other unresolved draft or delivery.
    Reading after the conditional write holds SQLite's write lock through the closure check,
    so work saved while channel.send was running cannot be hidden by an old send.
    """
    with db.connect() as conn:
        sent = conn.execute("UPDATE pending SET status = 'sent' WHERE id = ? AND status = 'sending'", (pid,))
        if sent.rowcount != 1:
            return False
        record = conn.execute("SELECT * FROM pending WHERE id = ?", (pid,)).fetchone()
        if record["kind"] == "clarifying_question":
            conn.execute("UPDATE requests SET status = 'awaiting_answer' WHERE id = ?", (record["request_id"],))
        else:
            conn.execute("""UPDATE requests SET status = 'done'
                WHERE id = ? AND status <> 'awaiting_answer'
                AND ? IS (SELECT id FROM reports WHERE request_id = ? ORDER BY id DESC LIMIT 1)
                AND NOT EXISTS (SELECT 1 FROM pending WHERE request_id = ?
                                AND status IN ('pending', 'sending', 'send_failed'))""",
                         (record["request_id"], record["report_id"], record["request_id"], record["request_id"]))
        return True


def discard(pid: int) -> bool:
    """The undo of a draft: a pending record the operator will not send. Only a record still pending;
    a sent one cannot be undone. Returns whether it was discarded."""
    with db.connect() as conn:
        cur = conn.execute("UPDATE pending SET status = 'discarded' WHERE id = ? AND status = 'pending'", (pid,))
        return cur.rowcount == 1
