"""Escalation on a named signal (Milestone 2, Part 2 task 5; owner: myron, M7).

    signal(run_key, name, attempted, why, needs) -> dict
        name: a signal named in advance ("failed_check", "unsettled_write", ...), never low confidence.
        Checkpoints the run as held and returns the packet {"run_key", "signal", "attempted", "why",
        "needs", "over_cap"}; nothing proceeds by default.
    held(session_id=None) -> list[dict]     held runs, for the queue page

Callers: claudea's three exits ("unsettled_write"), the critique held at its bound ("failed_check"),
abraham's loop. Setup stub: marks the run held in its checkpoint and traces it; no packet page, no cap.
"""

from __future__ import annotations

from agent import checkpoints, events


def signal(run_key, name, attempted, why, needs) -> dict:
    packet = {"run_key": run_key, "signal": name, "attempted": attempted, "why": why, "needs": needs,
              "over_cap": False}
    if run_key:
        checkpoints.update(run_key, held=packet)
    try:
        from harness import runtime
        runtime.trace().event(events.ESCALATION, **packet)
    except Exception:
        pass
    return packet


def held(session_id=None) -> list[dict]:
    return []
