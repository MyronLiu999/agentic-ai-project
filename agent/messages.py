"""Durable operator messages read at the next safe call boundary.

/add and /replace are explicit operator choices, so no model's classification
can replace a task. Ordinary messages queue (at most eight). A rejected message
is not stored. Mailboxes reuse the resettable control checkpoint store without
creating extra live runs or waits.
"""

from __future__ import annotations

import json
import re

from agent import checkpoints, events, runs, stop
from harness import runtime
from harness.turns import Reply
from sandbox import control

QUEUE_LIMIT = 8
MAX_MESSAGE_CHARS = 16000
_COMMAND = re.compile(r"^/(add|replace)\s+(?:(\d+)\s+)?(.+)$", re.I | re.S)


def classify(session_id: str, text: str) -> str:
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_MESSAGE_CHARS:
        return "reject"
    text = text.strip()
    match = _COMMAND.fullmatch(text)
    if match:
        return match.group(1).lower()
    return "reject" if text.startswith("/") else "queue"


def _load(conn, key):
    row = conn.execute("SELECT state_json FROM checkpoints WHERE run_key = ? ORDER BY id DESC LIMIT 1",
                       (key,)).fetchone()
    return json.loads(row["state_json"]) if row else {"items": [], "next_id": 1}


def _save(conn, key, state):
    conn.execute("INSERT INTO checkpoints (run_key, saved_at, mode, state_json) VALUES (?, ?, 'sync', ?)",
                 (key, control.now(), json.dumps(state, ensure_ascii=False)))


def _mailbox(session):
    return f"@messages:{session}"


def _selected_run(session, number):
    live = runs.live(session)
    if number is None:
        return live[0] if len(live) == 1 else None
    with control.connect() as conn:
        row = conn.execute("SELECT run_key FROM runs WHERE session_id = ? AND run_no = ? AND ended_at IS NULL",
                           (session, int(number))).fetchone()
    return row["run_key"] if row else None


def _record(session, way, text, run_key=None):
    with control.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        state = _load(conn, _mailbox(session))
        if len(state["items"]) >= QUEUE_LIMIT:
            return False
        state["items"].append({"id": state["next_id"], "way": way, "text": text,
                               "run_key": run_key, "created": control.now()})
        state["next_id"] += 1
        _save(conn, _mailbox(session), state)
    return True


def intercept(session_id: str, text: str) -> Reply | None:
    session = stop.session_key(session_id)
    live = runs.live(session)
    if not live:
        return None
    way = classify(session, text)
    trace = runtime.trace(session)
    if way == "reject":
        trace.event(events.MIDTASK, way=way, confirmed=False)
        return Reply("Message rejected. Use /add [run number] <instruction>, /replace [run number] <task>, "
                     "or a plain message to queue; each message must fit 16000 characters.")
    number, run_key, instruction = None, None, text.strip()
    if way in ("add", "replace"):
        match = _COMMAND.fullmatch(instruction)
        number, instruction = match.group(2), match.group(3).strip()
        run_key = _selected_run(session, number)
        if not run_key:
            trace.event(events.MIDTASK, way="reject", confirmed=False)
            return Reply("No unique live run selected. Give its run number after /add or /replace.")
    if not _record(session, way, instruction, run_key):
        trace.event(events.MIDTASK, way="reject", confirmed=False, reason="queue_full")
        return Reply("The message queue is full (8). Wait for a task to finish before adding more.")
    trace.event(events.MIDTASK, way=way, confirmed=way in ("add", "replace"), run_key=run_key)
    if way == "add":
        return Reply(f"Added to {run_key}; it will be read before the next model call. Earlier work stays recorded.")
    if way == "replace":
        state = checkpoints.load(run_key) or {}
        with control.connect() as conn:
            row = conn.execute("SELECT run_no FROM runs WHERE run_key = ?", (run_key,)).fetchone()
        stop.handle_command(session, f"/cancel {row['run_no']}")
        effects = [f"{c['tool']} ({c.get('key', 'no key')}): {json.dumps(c.get('result', {}).get('output'))}"
                   for c in state.get("completed_calls", [])]
        return Reply(f"Replaced {run_key}; the new task is queued for the safe boundary. "
                     "An in-flight call may still finish. Earlier effects remain; choose /rollback "
                     f"{row['run_no']} to undo reversible ones.\n" + ("\n".join(effects) or "No completed effects recorded."))
    return Reply("Queued until the current task ends. Use /add or /replace to change that task explicitly.")


def consume(run_key: str) -> list[str]:
    """Take additions once, recording them in the run checkpoint in the same transaction.

    The loop also appends returned texts to its in-memory conversation. If the
    process dies in that gap, a resume already has the additions in the checkpoint.
    """
    session = runs.session_of(run_key)
    with control.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        key = _mailbox(session)
        state = _load(conn, key)
        additions = [i for i in state["items"] if i["way"] == "add" and i["run_key"] == run_key]
        if not additions:
            return []
        snapshot = _load(conn, run_key)
        conversation = list(snapshot.get("conversation") or [])
        for item in additions:
            conversation.append({"role": "user", "content": json.dumps({"operator_instruction_addition": item["text"]})})
        snapshot["conversation"] = conversation
        snapshot["operator_additions"] = list(snapshot.get("operator_additions") or []) + [i["text"] for i in additions]
        _save(conn, run_key, snapshot)
        ids = {i["id"] for i in additions}
        state["items"] = [i for i in state["items"] if i["id"] not in ids]
        _save(conn, key, state)
    return [item["text"] for item in additions]


def pending(session_id: str) -> list[dict]:
    session = stop.session_key(session_id)
    with control.connect() as conn:
        return _load(conn, _mailbox(session))["items"]


def next_queued(session_id: str) -> str | None:
    """Admit one queued task once the service has reached a safe end boundary."""
    session = stop.session_key(session_id)
    with control.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        if conn.execute("SELECT 1 FROM runs WHERE session_id = ? AND ended_at IS NULL", (session,)).fetchone():
            return None
        key = _mailbox(session)
        state = _load(conn, key)
        # Additions addressed to a cancelled/finished run never become new tasks.
        queued = [i for i in state["items"] if i["way"] in ("queue", "replace")]
        if not queued:
            return None
        item = queued[0]
        state["items"] = [i for i in state["items"] if i["id"] != item["id"] and i["way"] != "add"]
        _save(conn, key, state)
    return item["text"]
