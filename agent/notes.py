"""Notes: a record outside the conversation that compaction never touches (Milestone 2; owner: abraham, B3).

    for_call(session_id, call_kind) -> str      "" when notes.<kind> is off, or for a planner call
    update(session_id, *, done=None, open_items=None, ids=None)

From the outside channel they hold identifiers and status, never the stranger's words.
Setup stub: no notes.
"""

from __future__ import annotations


def for_call(session_id: str, call_kind: str) -> str:
    return ""


def update(session_id: str, *, done=None, open_items=None, ids=None) -> None:
    return None
