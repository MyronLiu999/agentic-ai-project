"""The memory store and its one write policy (Milestone 2, Part 1 task 7; owner: claudea, C6-C7).

    write(record) -> dict                         the one place memory is written (insert, merge or supersede)
    for_session(session_id, budget_tokens=2000) -> list[dict]   what a session reads before its first model call
    read_log(session_id) -> list[dict]            what each read returned

    record = {"id", "kind": "episodic" | "semantic" | "procedural", "fact",
              "source": "operator" | "stranger" | "system" | "private_data", "written_at",
              "derived_or_ingested": "derived" | "ingested", "confirmed": bool, "supersedes": id | None}

Text from the outside channel is stored, if at all, as ingested and unconfirmed, and never reaches the
planner. Setup stub: stores nothing and reads nothing.
"""

from __future__ import annotations


def write(record: dict) -> dict:
    return dict(record)


def for_session(session_id: str, budget_tokens: int = 2000) -> list[dict]:
    return []


def read_log(session_id: str) -> list[dict]:
    return []
