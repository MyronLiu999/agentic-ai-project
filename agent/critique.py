"""The critique loop on draft_report_email (owner: claudea). Lecture 2, Section C.

Contract (PLAN.md section 3), called by the standard_report workflow and by the agent loop (abraham):

    result = critique.run(request_id, draft, revise, rounds=2)
    if not result.passed: trace.end(events.CRITIQUE_HELD) and write nothing

`draft` is a dict with recipient, subject, body and figures. `revise(reason)` returns a new draft.

`check(request_id, draft)` is the outside signal: it reads only the sandbox and the request record,
never a test task's check or expected answer, and recomputes what the author could have got wrong:

  - recipient   the contact on the request record (code's, not the stranger's text)
  - period      the request record's period
  - figures     finite named totals, including required comparisons, recomputed from the orders table
                for the request's own distributor (sandbox/sales.py)
  - upload      file_total_units, when given, recomputed from the raw uploaded units column
  - body        states the correct revenue/period and direction, with no other distributor or margin

Three gates (slide 43): the check finds the error without redoing the report (bounded sandbox reads);
it independently recomputes facts from the request and database; its rounds are bounded and each is a
`critique` trace event. A round is one check: with rounds=2 a draft is checked, revised once with the
reason, and checked again; a draft still failing then is held, and the caller writes nothing.
"""

from __future__ import annotations

from dataclasses import dataclass

from agent import events
from harness import runtime
from sandbox import db, files, inbox, reports, sales
from sandbox.report_validation import (comparison_requested, named_number_problems,
                                       revenue_problems, upload_units)

FIELDS = ("recipient", "subject", "body", "figures")


@dataclass
class CritiqueResult:
    passed: bool
    draft: dict
    rounds: int
    reason: str


def enabled() -> bool:
    return runtime.switch("critique.report_email") == "external"


def check(request_id: str, draft: dict) -> tuple[bool, str]:
    """Pass or fail with a reason, from the sandbox alone."""
    req = inbox.get(request_id)
    if req is None:
        return False, f"no request {request_id} in the sandbox"
    problems = []
    missing = [f for f in FIELDS if not draft.get(f)]
    if missing:
        problems.append(f"the draft has no {', '.join(missing)}")
    figures = draft.get("figures") or {}
    if not isinstance(figures, dict):
        problems.append("the draft figures must be an object")
        figures = {}
    body = f"{draft.get('subject', '')}\n{draft.get('body', '')}"

    if draft.get("recipient") and draft["recipient"] != req["contact_email"]:
        problems.append(f"recipient is {draft['recipient']}, but the request's contact is {req['contact_email']}")

    period = str(figures.get("period") or "")
    if req["period"] and period != req["period"]:
        problems.append(f"period is {period or 'missing'}, but the request is about {req['period']}")
        period = req["period"]
    period = period or req["period"]

    if period:
        try:
            truth = sales.distributor_sales(req["distributor_id"], period)["total_revenue"]
        except ValueError as exc:
            truth = None
            problems.append(str(exc))
        if truth is not None:
            problems += named_number_problems(figures, "total_revenue", truth)
            before_period = sales.previous_period(period)
            before = sales.distributor_sales(req["distributor_id"], before_period)["total_revenue"]
            saved = next((r for r in reports.for_request(request_id) if r["id"] == draft.get("report_id")), None)
            needs_comparison = (bool(draft.get("comparison_required")) or draft.get("report_kind") == "comparison"
                                or (saved and saved["kind"] == "comparison")
                                or comparison_requested(req.get("question", ""))
                                or comparison_requested(body, period)
                                or any(k in figures for k in ("previous_total_revenue", "previous_period", "revenue_change")))
            if needs_comparison:
                problems += named_number_problems(figures, "previous_total_revenue", before)
            if "previous_period" in figures and figures["previous_period"] != before_period:
                problems.append(f"previous_period is {figures['previous_period']}, not {before_period}")
            if "revenue_change" in figures:
                problems += named_number_problems(figures, "revenue_change", truth - before)
            if "file_total_units" in figures:
                try:
                    units = upload_units(files.read_upload(request_id, req["file_name"])) if req.get("file_name") else None
                except (OSError, TypeError):
                    units = None
                if units is None:
                    problems.append("cannot verify file_total_units from the uploaded units column")
                else:
                    problems += named_number_problems(figures, "file_total_units", units)
            if draft.get("body"):
                problems += [f"the body {p}" for p in revenue_problems(
                    body, truth, period, before, before_period, require_current=True)]
            if saved:
                problems += [f"the saved report {p}" for p in revenue_problems(
                    saved.get("body", ""), truth, period, before, before_period)]

    low = body.lower()
    if "margin" in low:
        problems.append("the body mentions margins, which never go to a distributor")
    for d in _other_distributors(req["distributor_id"]):
        if d["id"].lower() in low or d["name"].lower() in low:
            problems.append(f"the body names another distributor, {d['name']}")

    if problems:
        return False, "; ".join(problems)
    return True, "recipient, period and figures match the sandbox"


def _other_distributors(distributor_id: str) -> list[dict]:
    with db.connect() as conn:
        return [dict(r) for r in conn.execute("SELECT id, name FROM distributors WHERE id != ?", (distributor_id,))]


def _changed(old: dict, new: dict) -> list[str]:
    return [k for k in sorted(set(old) | set(new)) if old.get(k) != new.get(k)]


def run(request_id: str, draft: dict, revise, *, rounds: int = 2) -> CritiqueResult:
    """Check the draft; revise it with the reason while a round remains; hold it at the bound."""
    if not enabled():
        return CritiqueResult(True, draft, 0, "critique off")
    rounds = max(1, int(rounds))
    trace = runtime.trace()
    changed: list[str] = []
    reason = ""
    for n in range(1, rounds + 1):
        passed, reason = check(request_id, draft)
        if passed:
            trace.event(events.CRITIQUE, round=n, verdict="pass", reason=reason, changed=changed)
            return CritiqueResult(True, draft, n, reason)
        if n == rounds:
            trace.event(events.CRITIQUE, round=n, verdict="held", reason=reason, changed=changed)
            break
        trace.event(events.CRITIQUE, round=n, verdict="revise", reason=reason, changed=changed)
        try:
            new = revise(reason)
        except Exception as exc:  # a reviser that fails holds the draft; it never sends the old one
            reason = f"{reason}; the reviser raised {type(exc).__name__}: {exc}"
            trace.event(events.CRITIQUE, round=n + 1, verdict="held", reason=reason, changed=[])
            return CritiqueResult(False, draft, n + 1, reason)
        new = dict(new or {})
        changed = _changed(draft, new)
        draft = new
    return CritiqueResult(False, draft, rounds, reason)
