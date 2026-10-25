"""The work waiting, for the app's queue page: requests nobody has finished."""

from __future__ import annotations

from sandbox import inbox


def waiting() -> list[dict]:
    return [{"id": r["id"], "summary": r["question"][:80], "status": r["status"], "since": r["created_at"],
             "distributor": r["distributor_id"]}
            for r in inbox.all_requests() if r["status"] != "done"]
