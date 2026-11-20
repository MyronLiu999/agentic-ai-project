"""Messages the operator sends while a run has not finished (Milestone 2, Part 2 task 7; owner: abraham, B6).

    intercept(session_id, text) -> Reply | None
        called by agent.service.operator_turn for a session with a live run, before routing;
        None lets the message through as a new turn (the setup's behaviour)
    classify(session_id, text) -> "add" | "replace" | "queue" | "reject"
        add: carry on with it; replace: end the run, start over, list its effects for rollback;
        queue (the default, bounded): it waits until the run ends; reject: the sender is told at once

Setup stub: lets every message through.
"""

from __future__ import annotations

from harness.turns import Reply


def classify(session_id: str, text: str) -> str:
    return "queue"


def intercept(session_id: str, text: str) -> Reply | None:
    return None
