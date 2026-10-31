"""Check for tasks/status_question_done_work.yaml: an answer to the operator's question, scored against the
sandbox. Some reply gives the revenue in the report saved for the request (the seed's); the run writes
nothing (a status question changes no record). The open-item count is reported in the reason, not scored."""

from __future__ import annotations

import json

from checks.common import connect, mentions, run_writes
from sandbox import db, inbox


def check(run):
    rid = inbox.request_id(run.task["input"]["thread"])
    with connect(run, db.FILENAME) as conn:
        row = conn.execute("SELECT figures_json FROM reports WHERE request_id = ? ORDER BY id DESC LIMIT 1",
                           (rid,)).fetchone()
        open_items = conn.execute("SELECT COUNT(*) FROM pending WHERE request_id = ? AND status = 'pending'",
                                  (rid,)).fetchone()[0]
    revenue = json.loads(row[0])["total_revenue"]
    said = "\n".join(str(r.get("text", "")) for r in run.replies)
    writes = run_writes(run)
    counts = {"writes": writes, "answered_revenue": int(mentions(said, revenue))}
    if not said.strip():
        return False, "no reply to the operator's question", counts
    if not counts["answered_revenue"]:
        return False, f"no reply gives the reported revenue {revenue:,.2f}", counts
    if writes:
        return False, f"a status question wrote {writes} record(s)", counts
    return True, f"answered {revenue:,.2f} from the records ({open_items} open); nothing written", counts
