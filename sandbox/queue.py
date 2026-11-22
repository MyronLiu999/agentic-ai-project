"""The work waiting, for the app's queue page, and the durable store behind the approval gate and the
escalation's holds (Milestone 2, Part 2 tasks 4 and 5; owner: myron, M6-M7).

    waiting() -> list[dict]      what has arrived and is not finished, each with its status; runs held by an
                                 escalation (marked when over the daily cap); runs waiting on a stranger, an
                                 approval or a stop; and every call waiting for approval

The approvals and holds live beside the checkpoints, in the sandbox's control file (sandbox/control.py), so a
run waiting for an answer survives a restart (`make serve` keeps the file). connect() adds their two tables.
A row belongs to one run: its run key and the run's start time, so a run key that comes back after the
sandbox was reset (`make app`) never picks up an earlier run's rows.
MERGE-CHECK (claudea): add "approvals" and "held_runs" to sandbox/control.py's reset() so `make app` empties
them too (until then the run-start match above keeps old rows from showing).

Every function here reads or writes rows; agent/approvals.py and agent/escalation.py decide what to write.
"""

from __future__ import annotations

import contextlib
import json

from sandbox import control, inbox

SCHEMA = """
CREATE TABLE IF NOT EXISTS approvals (
    id TEXT PRIMARY KEY, seq INTEGER NOT NULL, run_key TEXT NOT NULL, run_started TEXT, session_id TEXT,
    kind TEXT NOT NULL, call_json TEXT, action_class TEXT, screen_json TEXT, plan_json TEXT, gated_json TEXT,
    status TEXT NOT NULL, put_up_at TEXT NOT NULL, decided_at TEXT, decision TEXT, who TEXT, note TEXT,
    seconds REAL, setting TEXT);
CREATE TABLE IF NOT EXISTS held_runs (
    id TEXT PRIMARY KEY, seq INTEGER NOT NULL, run_key TEXT NOT NULL, run_started TEXT, session_id TEXT,
    signal TEXT NOT NULL, attempted TEXT NOT NULL, why TEXT NOT NULL, needs TEXT NOT NULL,
    over_cap INTEGER NOT NULL, status TEXT NOT NULL, raised_at TEXT NOT NULL, deadline TEXT,
    answered_at TEXT, answer TEXT, who TEXT);
"""
JSON_FIELDS = ("call_json", "screen_json", "plan_json", "gated_json")


@contextlib.contextmanager
def connect():
    """The control file's connection, with the queue's two tables created if needed."""
    with control.connect() as conn:
        conn.executescript(SCHEMA)
        yield conn


def now() -> str:
    return control.now()


def run_started(conn, run_key: str) -> str | None:
    row = conn.execute("SELECT started_at FROM runs WHERE run_key = ?", (run_key,)).fetchone()
    return row["started_at"] if row else None


def _current(conn, table: str, where: str = "1=1", args: tuple = ()) -> list[dict]:
    """Rows of runs that still exist as they were when the row was written (see the module docstring)."""
    rows = conn.execute(
        f"SELECT t.* FROM {table} t JOIN runs r ON r.run_key = t.run_key "
        f"AND (t.run_started IS r.started_at) WHERE {where} ORDER BY t.seq", args).fetchall()
    return [_decode(dict(r)) for r in rows]


def _decode(row: dict) -> dict:
    for field in JSON_FIELDS:
        if field in row:
            value = row.pop(field)
            row[field[:-5]] = json.loads(value) if value else None
    return row


def _next_id(conn, table: str, prefix: str) -> tuple[str, int]:
    seq = int(conn.execute(f"SELECT COALESCE(MAX(seq), 0) FROM {table}").fetchone()[0]) + 1
    return f"{prefix}-{seq}", seq


# -- approvals -------------------------------------------------------------------------------------------

def add_approval(run_key: str, session_id: str | None, kind: str, *, call=None, action_class=None, screen=None,
                 plan=None, gated=None, setting=None) -> str:
    with connect() as conn:
        approval_id, seq = _next_id(conn, "approvals", "apr")
        conn.execute(
            "INSERT INTO approvals (id, seq, run_key, run_started, session_id, kind, call_json, action_class, "
            "screen_json, plan_json, gated_json, status, put_up_at, setting) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'waiting', ?, ?)",
            (approval_id, seq, run_key, run_started(conn, run_key), session_id, kind,
             json.dumps(call, sort_keys=True, default=str) if call is not None else None, action_class,
             json.dumps(screen, sort_keys=True, default=str) if screen is not None else None,
             json.dumps(plan, sort_keys=True, default=str) if plan is not None else None,
             json.dumps(gated, sort_keys=True, default=str) if gated is not None else None,
             now(), setting))
    return approval_id


def approvals(status: str | None = None, run_key: str | None = None, kind: str | None = None) -> list[dict]:
    where, args = ["1=1"], []
    for field, value in (("t.status", status), ("t.run_key", run_key), ("t.kind", kind)):
        if value is not None:
            where.append(f"{field} = ?")
            args.append(value)
    with connect() as conn:
        return _current(conn, "approvals", " AND ".join(where), tuple(args))


def approval(approval_id: str) -> dict | None:
    with connect() as conn:
        found = _current(conn, "approvals", "t.id = ?", (str(approval_id),))
    return found[0] if found else None


def set_approval(approval_id: str, from_status: str | tuple, **fields) -> bool:
    """Change one approval only while it is in `from_status`; True if this call changed it."""
    statuses = (from_status,) if isinstance(from_status, str) else tuple(from_status)
    names = sorted(fields)
    with connect() as conn:
        cur = conn.execute(
            f"UPDATE approvals SET {', '.join(f'{n} = ?' for n in names)} WHERE id = ? AND status IN "
            f"({', '.join('?' for _ in statuses)})", (*[fields[n] for n in names], str(approval_id), *statuses))
        return cur.rowcount == 1


# -- held runs (the escalation) ---------------------------------------------------------------------------

def add_hold(run_key: str, session_id: str | None, signal: str, attempted: str, why: str, needs: str,
             over_cap: bool, deadline: str | None) -> str:
    with connect() as conn:
        hold_id, seq = _next_id(conn, "held_runs", "esc")
        conn.execute(
            "INSERT INTO held_runs (id, seq, run_key, run_started, session_id, signal, attempted, why, needs, "
            "over_cap, status, raised_at, deadline) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'held', ?, ?)",
            (hold_id, seq, run_key, run_started(conn, run_key), session_id, signal, attempted, why, needs,
             int(bool(over_cap)), now(), deadline))
    return hold_id


def holds(status: str | None = None, session_id: str | None = None, run_key: str | None = None) -> list[dict]:
    where, args = ["1=1"], []
    for field, value in (("t.status", status), ("t.session_id", session_id), ("t.run_key", run_key)):
        if value is not None:
            where.append(f"{field} = ?")
            args.append(value)
    with connect() as conn:
        rows = _current(conn, "held_runs", " AND ".join(where), tuple(args))
    for row in rows:
        row["over_cap"] = bool(row["over_cap"])
    return rows


def set_hold(hold_id: str, from_status: str, **fields) -> bool:
    names = sorted(fields)
    with connect() as conn:
        cur = conn.execute(f"UPDATE held_runs SET {', '.join(f'{n} = ?' for n in names)} "
                           "WHERE id = ? AND status = ?", (*[fields[n] for n in names], hold_id, from_status))
        return cur.rowcount == 1


def answer_hold(run_key: str, hold_id: str, text: str) -> dict | None:
    """Commit an answer, release its hold/wait, and retain its continuation together.

    The executor clears pending_operator_answer only with the checkpoint that
    incorporates the instruction. A crash before then replays this exact event.
    """
    event = {"kind": "operator_turn", "text": text, "escalation": hold_id}
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        holds = _current(conn, "held_runs", "t.id = ? AND t.run_key = ? AND t.status = 'held'",
                         (hold_id, run_key))
        run = conn.execute("SELECT ended_at FROM runs WHERE run_key = ?", (run_key,)).fetchone()
        latest = conn.execute("SELECT state_json FROM checkpoints WHERE run_key = ? ORDER BY id DESC LIMIT 1",
                              (run_key,)).fetchone()
        wait = conn.execute("SELECT kind, ref FROM waits WHERE run_key = ?", (run_key,)).fetchone()
        if not holds or run is None or run["ended_at"] or latest is None:
            return None
        state = json.loads(latest["state_json"])
        if (state.get("cancelled") or state.get("pending_operator_answer") or not wait
                or wait["kind"] != "escalation" or wait["ref"] != hold_id):
            return None
        answered_at = now()
        if holds[0].get("deadline") and holds[0]["deadline"] < answered_at:
            return None
        conn.execute("UPDATE held_runs SET status = 'answered', answered_at = ?, answer = ?, who = 'operator' "
                     "WHERE id = ?", (answered_at, text, hold_id))
        state.update(held=None, waiting_for=None, pending_operator_answer=event)
        conn.execute("INSERT INTO checkpoints (run_key, saved_at, mode, state_json) VALUES (?, ?, 'sync', ?)",
                     (run_key, answered_at, json.dumps(state, sort_keys=True, ensure_ascii=False)))
        conn.execute("DELETE FROM waits WHERE run_key = ? AND kind = 'escalation' AND ref = ?",
                     (run_key, hold_id))
    return event


def asks_on(day: str) -> int:
    """Asks a reviewer met on one day (YYYY-MM-DD): approvals put up, and packets sent (not over the cap)."""
    with connect() as conn:
        put_up = len(_current(conn, "approvals", "substr(t.put_up_at, 1, 10) = ?", (day,)))
        packets = len(_current(conn, "held_runs", "substr(t.raised_at, 1, 10) = ? AND t.over_cap = 0", (day,)))
    return put_up + packets


# -- the queue page ---------------------------------------------------------------------------------------

def waiting() -> list[dict]:
    """Everything waiting, newest kind of wait last: requests, held runs, waits, approvals."""
    items = [{"id": r["id"], "summary": r["question"][:80], "status": r["status"], "since": r["created_at"],
              "kind": "request", "distributor": r["distributor_id"]}
             for r in inbox.all_requests() if r["status"] != "done"]
    try:
        from agent import escalation
        escalation.expire()                   # a hold past its deadline ends held, never approved
    except Exception:
        pass
    for hold in holds(status="held"):
        items.append({"id": hold["run_key"], "kind": "held run",
                      "summary": f"{hold['signal']}: {hold['why']}"[:120],
                      "status": "held, over the daily cap: open it from the console" if hold["over_cap"] else "held",
                      "since": hold["raised_at"], "attempted": hold["attempted"], "needs": hold["needs"],
                      "until": hold["deadline"], "escalation": hold["id"]})
    with connect() as conn:
        waits = [dict(r) for r in conn.execute("SELECT * FROM waits ORDER BY since").fetchall()]
    for wait in waits:
        if wait["kind"] == "escalation":
            continue                          # listed above, with its packet
        items.append({"id": wait["run_key"], "kind": f"run waiting ({wait['kind']})",
                      "summary": f"waits for {wait['kind']} {wait['ref']}", "status": "waiting",
                      "since": wait["since"], "until": wait["deadline"]})
    for item in approvals(status="waiting"):
        items.append({"id": item["id"], "kind": "approval", "summary": f"{item['action_class']} for {item['run_key']}",
                      "status": "waiting for the operator", "since": item["put_up_at"],
                      "session": item["session_id"]})
    return items
