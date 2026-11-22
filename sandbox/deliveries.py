"""Durable association between a pending send and its actual channel message."""
from sandbox import db


def record(pending_id: int, message_id: int, body: str) -> None:
    with db.connect() as conn:
        conn.execute("INSERT OR IGNORE INTO delivery_receipts (pending_id, message_id, body) VALUES (?, ?, ?)",
                     (pending_id, message_id, body))


def get(pending_id: int) -> dict | None:
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM delivery_receipts WHERE pending_id=?", (pending_id,)).fetchone()
    return dict(row) if row else None
