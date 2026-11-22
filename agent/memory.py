"""Memory with provenance, and the operator's later session (Milestone 2, Part 1 task 7; owner: claudea).

What is kept (slide 23's "what"): a fact is kept only if it is expensive to derive, stated rather than
inferred, or confirmed, and the sandbox does not already hold it.

    KEPT      the operator's stated preferences (semantic: what is true of how they want the work done, such as a
              prefix on every report email's subject; switch memory.preferences) and standing rules (procedural:
              how to do something here, "from now on, always ..."; switch memory.standing_rules). Both are stated by
              the trusted operator, cannot be derived from any record, and would otherwise be asked again.
    NOT KEPT  anything the sandbox holds (a distributor's revenue, last quarter's report, a request's status):
              it is read there, fresh, every time; a copy in memory could only go stale. And nothing a stranger
              writes: text from the outside channel is never stored here, so it can never come back as the
              system's own knowledge (memory poisoning, slide 24) or reach a planner.

The write policy, in one place (write()):
    how     insert a new name; merge a repeat of the same value (it confirms the record, no new row); a new value
            for a name supersedes the old record, keeping both, with a timestamp and which replaced which
    with    provenance on every record: source, written_at, derived_or_ingested, confirmed
    when    at a run's end (commit_run, called by agent.runs.end), never mid-run on a guess
The failure it invites (slide 25) and its answers: stale (every record shows its age; one unread past
EXPIRE_DAYS expires when next read), contradictory (supersede, never append a rival), unbounded (MAX_RECORDS;
superseded records go first, then the least recently read).

    write(record) -> dict
    commit_run(session_id) -> list[dict]          what the run's operator stated, written at its end
    for_session(session_id, budget_tokens=2000) -> list[dict]   read before the session's first model call
    preference(session_id, name)                  a kept preference's value, or None
    read_log(session_id) -> list[dict]
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from agent import events
from sandbox import memory as store

KINDS = ("episodic", "semantic", "procedural")
SOURCES = ("operator", "stranger", "system", "private_data")
MAX_RECORDS = 200          # store size
EXPIRE_DAYS = 180          # unread this long, a record expires when next read

# kind of fact -> its switch
SWITCH = {"preference": "memory.preferences", "standing_rule": "memory.standing_rules"}

_SUBJECT = re.compile(r"start (?:every|each|all|the) (?:report )?(?:e-?mail )?subjects? with\s*['\"“‘](.+?)['\"”’]",
                      re.I)
_RULE = re.compile(r"(?:^|[.!?]\s+)((?:from now on|always|never)\b[^.!?]*[.!?]?)", re.I)


def _now() -> str:
    from harness.trace import now
    return now()


def _switch_on(kind_of_fact: str) -> bool:
    try:
        from harness import runtime
        return runtime.switch(SWITCH[kind_of_fact]) == "on"
    except Exception:
        return False


def _age_days(written_at: str) -> float:
    try:
        then = datetime.fromisoformat(written_at)
    except (TypeError, ValueError):
        return 0.0
    return round((datetime.now(timezone.utc) - then).total_seconds() / 86400, 1)


# -- the one write policy -------------------------------------------------------------------------------------

def write(record: dict) -> dict:
    """Insert, merge or supersede one record, with its provenance. Returns the record that now holds the name."""
    record = dict(record)
    record.setdefault("written_at", _now())
    if record.get("kind") not in KINDS or record.get("source") not in SOURCES:
        raise ValueError("a memory record needs a kind (episodic | semantic | procedural) and a source")
    if record.get("derived_or_ingested") not in ("derived", "ingested") or "confirmed" not in record:
        raise ValueError("a memory record needs derived_or_ingested and confirmed (its provenance)")
    if record["source"] == "stranger":
        # Text anyone can write is stored, if at all, only as ingested and unconfirmed: never as a fact.
        record.update(derived_or_ingested="ingested", confirmed=False)
    now = store.current(record["name"])
    if now is not None and now.get("value") == record.get("value"):
        return now                                    # merge: the same fact stated again adds no row
    if now is not None:
        record["supersedes"] = now["id"]              # a new value replaces the old, which stays, marked
    written = store.insert(record)
    _evict()
    _trace(events.MEMORY_WRITE, record_id=written["id"], kind=written["kind"], source=written["source"],
           supersedes=written.get("supersedes"))
    return written


def _evict() -> None:
    records = store.all_records()
    extra = len(records) - MAX_RECORDS
    if extra <= 0:
        return
    old = [r for r in records if r["superseded_by"] is not None]
    live = sorted((r for r in records if r["superseded_by"] is None), key=lambda r: r["last_read_at"] or "")
    store.delete([r["id"] for r in (old + live)[:extra]])


# -- what the operator stated, written at the run's end ---------------------------------------------------------

def extract(text: str) -> list[dict]:
    """The facts an operator's message states, by code (never the model). Returns record drafts."""
    out = []
    subject = _SUBJECT.search(text or "")
    if subject:
        out.append({"kind": "semantic", "name": "email_subject_prefix", "value": subject.group(1).strip(),
                    "fact": f"Start every report email's subject with '{subject.group(1).strip()}'",
                    "kind_of_fact": "preference"})
    for sentence in _RULE.findall(text or ""):
        sentence = sentence.strip()
        if _SUBJECT.search(sentence):
            continue
        key = re.sub(r"[^a-z0-9]+", "-", sentence.lower()).strip("-")[:60]
        out.append({"kind": "procedural", "name": f"rule:{key}", "value": sentence, "fact": sentence,
                    "kind_of_fact": "standing_rule"})
    return out


def commit_run(session_id: str | None) -> list[dict]:
    """At a run's end: write what the operator stated in this session since the last commit. Reads only the
    operator's own lines of the trace; the stranger's lines are never read here."""
    if not session_id:
        return []
    from harness import runtime
    lines = runtime.trace(session_id).lines()
    done = store.lines_done(session_id)
    written = []
    for line in lines[done:]:
        if line.get("type") != "operator":
            continue
        for draft in extract(str(line.get("text") or "")):
            if not _switch_on(draft.pop("kind_of_fact")):
                continue
            written.append(write({**draft, "source": "operator", "derived_or_ingested": "ingested",
                                  "confirmed": True, "session_id": session_id, "written_at": line.get("at") or _now()}))
    store.set_lines_done(session_id, len(lines))
    return written


# -- the later session's read ------------------------------------------------------------------------------------

def _enabled_kinds() -> tuple[str, ...]:
    kinds = []
    if _switch_on("preference"):
        kinds.append("semantic")
    if _switch_on("standing_rule"):
        kinds.append("procedural")
    return tuple(kinds)


def for_session(session_id: str, budget_tokens: int = 2000) -> list[dict]:
    """Read before the session's first model call: the kept records (newest first, within the budget) and the
    runs still waiting. Logs the read in the trace and shows the operator each record with its age and source.
    The model sees only what this returns, and only where context assembly puts it (slide 20)."""
    from agent import checkpoints
    from harness import runtime

    chosen, used, expired = [], 0, []
    for record in store.active(_enabled_kinds()):
        age = _age_days(record["written_at"])
        last = record["last_read_at"] or record["written_at"]
        if _age_days(last) > EXPIRE_DAYS:
            expired.append(record["id"])            # expiry on access: stale and unread, so it is not used
            continue
        cost = max(1, len(record["fact"]) // 4)
        if used + cost > budget_tokens:
            break
        used += cost
        chosen.append({**record, "age_days": age})
    if expired:
        store.delete(expired)
    store.touch([r["id"] for r in chosen], _now())
    waiting = checkpoints.waiting(session_id)
    trace = runtime.trace(session_id)
    trace.event(events.MEMORY_READ, records=[{"id": r["id"], "kind": r["kind"], "name": r["name"],
                                              "age_days": r["age_days"], "source": r["source"],
                                              "confirmed": r["confirmed"]} for r in chosen],
                waiting=[{"run_key": w["run_key"], "kind": w["kind"], "ref": w["ref"]} for w in waiting],
                expired=expired)
    for r in chosen:
        trace.progress(f"Remembered ({r['age_days']} days old, from the {r['source']}): {r['fact']}")
    for w in waiting:
        trace.progress(f"Still waiting: run {w['run_key']} on {w['kind']} {w['ref']} since {w['since']}")
    return chosen


def preference(session_id: str, name: str):
    """The value of a kept preference, or None (switch off, or never stated)."""
    if not _switch_on("preference"):
        return None
    record = store.current(name)
    return record.get("value") if record else None


def read_log(session_id: str) -> list[dict]:
    from harness import runtime
    return [l for l in runtime.trace(session_id).lines() if l.get("type") == events.MEMORY_READ]


def _trace(event_kind: str, **fields) -> None:
    try:
        from harness import runtime
        runtime.trace().event(event_kind, **fields)
    except Exception:
        pass
