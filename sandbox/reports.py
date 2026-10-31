"""Saved reports. A saved report can be replaced: each save is a new version. The key makes a
retried write one effect: the target accepts each key once and returns the first result to a repeat."""

from __future__ import annotations

import json

from sandbox import db
from sandbox.stamp import current


def save(request_id: str, kind: str, figures: dict, body: str, key: str, stamp: str | None = None) -> tuple[dict, bool]:
    """Returns (report, created). A repeat of `key` creates nothing and returns the first report."""
    with db.connect() as conn:
        first = conn.execute("SELECT * FROM reports WHERE key = ?", (key,)).fetchone()
        if first:
            return dict(first), False
        version = conn.execute("SELECT COUNT(*) FROM reports WHERE request_id = ? AND kind = ?",
                               (request_id, kind)).fetchone()[0] + 1
        cur = conn.execute("INSERT INTO reports (request_id, kind, version, key, figures_json, body, stamp, created_at) "
                           "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                           (request_id, kind, version, key, json.dumps(figures, sort_keys=True), body,
                            stamp or current(), db.NOW))
        return dict(conn.execute("SELECT * FROM reports WHERE id = ?", (cur.lastrowid,)).fetchone()), True


def for_request(request_id: str) -> list[dict]:
    with db.connect() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM reports WHERE request_id = ? ORDER BY id", (request_id,))]


def latest(request_id: str, kind: str | None = None) -> dict | None:
    with db.connect() as conn:
        if kind:
            row = conn.execute("SELECT * FROM reports WHERE request_id = ? AND kind = ? ORDER BY id DESC LIMIT 1",
                               (request_id, kind)).fetchone()
        else:
            row = conn.execute("SELECT * FROM reports WHERE request_id = ? ORDER BY id DESC LIMIT 1",
                               (request_id,)).fetchone()
    return dict(row) if row else None


def figures(report: dict) -> dict:
    return json.loads(report["figures_json"])
