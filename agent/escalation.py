"""Escalation on a named signal (Milestone 2, Part 2 task 5; owner: myron, M7).

    signal(run_key, name, attempted, why, needs) -> dict
        name: a signal named in advance in policy/autonomy.yaml ("failed_check", "unsettled_write"), never
        low confidence. Holds the run and returns the packet {"run_key", "signal", "attempted", "why",
        "needs", "over_cap"}; nothing proceeds by default.
    held(session_id=None) -> list[dict]     held runs, for the queue page (each with its packet)
    active_hold(run_key) -> dict | None     the hook refuses every call of a run while it is held
    answer(run_key, text, who="operator") -> Reply   the operator's answer, in any later session: resumes the run
    expire(now=None) -> list[str]           holds past their deadline end held, never approved
    packet_text(packet) -> str              the packet as the console shows it (the held turn's Reply text)

The four decisions, made before the agent runs (Lecture 5, slide 37):
  trigger  a signal our code sets, named in advance: failed_check (agent/critique.py, at its bound) and
           unsettled_write (claudea's three exits, when a write's outcome cannot be told);
  packet   what the run attempted, why it stopped, what it needs from the operator: three non-empty fields;
  hold     the run checkpoints (its checkpoint's `held`, and a wait of kind "escalation"), the hook refuses its
           every call, and only an answer resumes it; with no answer by the deadline it ends held;
  budget   one daily cap counted with the approvals against the reviewer's minutes (policy/autonomy.yaml,
           budget.daily_asks). Past it a signal still holds its run, but sends no packet: the run waits in the
           queue, marked over the cap, until the operator opens it from the console.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from agent import checkpoints, events
from sandbox import queue as store

HELD_EXPIRED = "held_expired"      # the end reason of a hold nobody answered in time
NEVER = ("low_confidence", "uncertain", "unsure", "confidence", "doubt")


def _policy() -> dict:
    from policy import hook
    return hook.load_policy()


def signals() -> dict:
    return dict(_policy().get("escalate") or {})


def _budget() -> dict:
    budget = _policy().get("budget") or {}
    return {"daily_asks": int(budget.get("daily_asks", 20)), "hold_timeout_hours": float(budget.get("hold_timeout_hours", 24))}


def _trace(kind: str, **fields) -> None:
    try:
        from harness import runtime
        runtime.trace().event(kind, **fields)
    except Exception:
        pass


def signal(run_key, name, attempted, why, needs) -> dict:
    if any(word in str(name).casefold() for word in NEVER):
        raise ValueError("an escalation is never on low confidence: name the signal your code set")
    if name not in signals():
        raise ValueError(f"{name!r} is not a signal named in advance in policy/autonomy.yaml")
    fields = {"attempted": str(attempted or "").strip(), "why": str(why or "").strip(),
              "needs": str(needs or "").strip()}
    empty = [k for k, v in fields.items() if not v]
    if empty:
        raise ValueError(f"a packet needs every field: {', '.join(empty)} is empty")
    budget = _budget()
    raised = store.now()
    over_cap = store.asks_on(raised[:10]) >= budget["daily_asks"]
    deadline = (datetime.fromisoformat(raised) + timedelta(hours=budget["hold_timeout_hours"])).isoformat()
    packet = {"run_key": run_key, "signal": name, **fields, "over_cap": over_cap}
    if run_key:
        from agent import runs
        hold_id = store.add_hold(run_key, runs.session_of(run_key), name, fields["attempted"], fields["why"],
                                 fields["needs"], over_cap, deadline)
        checkpoints.update(run_key, held=packet)
        checkpoints.set_wait(run_key, "escalation", hold_id, deadline)
    _trace(events.ESCALATION, **packet)
    return packet


def packet_text(packet: dict) -> str:
    """The packet on the console: what the run attempted, why it stopped, what it needs."""
    if packet.get("over_cap"):
        return (f"Run {packet.get('run_key')} is held ({packet.get('signal')}) and waits in the queue, marked over "
                "today's cap of asks; open it from the console when you can.")
    return (f"Run {packet.get('run_key')} is held: {packet.get('signal')}.\n"
            f"Attempted: {packet.get('attempted')}\nWhy it stopped: {packet.get('why')}\n"
            f"What it needs from you: {packet.get('needs')}\nNothing proceeds until you answer.")


def active_hold(run_key) -> dict | None:
    if not run_key:
        return None
    found = store.holds(status="held", run_key=run_key)
    return found[-1] if found else None


def expire(now: str | None = None) -> list[str]:
    from agent import runs
    now = now or store.now()
    ended = []
    for hold in store.holds(status="held"):
        if hold.get("deadline") and hold["deadline"] < now and store.set_hold(hold["id"], "held", status="expired"):
            runs.end(hold["run_key"], HELD_EXPIRED)      # the hold's row keeps status "expired" as the record
            checkpoints.clear_wait(hold["run_key"])
            ended.append(hold["run_key"])
    return ended


def held(session_id=None) -> list[dict]:
    expire()
    return [{"run_key": h["run_key"], "signal": h["signal"], "attempted": h["attempted"], "why": h["why"],
             "needs": h["needs"], "over_cap": h["over_cap"], "since": h["raised_at"], "until": h["deadline"],
             "escalation": h["id"], "session_id": h["session_id"]}
            for h in store.holds(status="held", session_id=session_id)]


def answer(run_key, text, who: str = "operator"):
    """Submit the operator's answer through the service's shared continuation ownership."""
    from agent import service
    from harness.turns import Reply
    expire()
    hold = active_hold(run_key)
    if hold is None:
        return Reply(f"Run {run_key} is not held: nothing to answer.")
    return service.continue_run(run_key, {"kind": "escalation_answer", "text": text,
                                          "who": who, "escalation": hold["id"]})


def _accept_answer(run_key, event):
    """Lift the exact hold only after the service owns this session's execution."""
    from agent import runs
    from harness.turns import Reply
    if event.get("who") != "operator":
        return Reply("Only the operator can answer a held run.")
    text = event.get("text")
    if not isinstance(text, str) or not text.strip():
        return Reply("An answer must contain the operator's instruction.")
    expire()
    hold = active_hold(run_key)
    if hold is None or hold["id"] != event.get("escalation"):
        return Reply(f"Run {run_key} is not held by that escalation: nothing to answer.")
    if run_key not in runs.live(runs.session_of(run_key)):
        return Reply(f"Run {run_key} has ended and cannot continue.")
    state = checkpoints.load(run_key) or {}
    if (state.get("path") == "workflow" or state.get("split_state")) and text.strip().casefold() not in (
            "retry", "discard"):
        return Reply("This fixed executor accepts only retry or discard. Use /answer <run number> retry to "
                     "retry its saved work, or /answer <run number> discard and start a revised request.")
    accepted = store.answer_hold(run_key, hold["id"], text)
    if accepted is None:
        return Reply(f"Run {run_key}'s hold was answered or ended meanwhile.")
    return accepted
