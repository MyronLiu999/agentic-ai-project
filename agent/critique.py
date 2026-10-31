"""The critique loop on draft_report_email (owner: claudea). Lecture 2, Section C.

Contract (PLAN.md section 3), called by the standard_report workflow and by the agent loop (abraham):

    result = critique.run(request_id, draft, revise, rounds=2)
    if not result.passed: trace.end(events.CRITIQUE_HELD) and write nothing

`draft` is a dict with recipient, subject, body and figures. `revise(reason)` returns a new draft.

`check(request_id, draft)` is the outside signal: it reads only the sandbox and the request record,
never a test task's check or expected answer, and recomputes what the author could have got wrong:

  - recipient   the contact on the request record (code's, not the stranger's text)
  - period      the request record's period
  - figures     total_revenue (and previous_total_revenue, if given) recomputed from the orders table
                for the request's own distributor (sandbox/sales.py)
  - body        writes the recomputed total, and names no other distributor and no margin

Three gates (slide 43): the check finds the error without redoing the report (one SQL sum); it knows
what the author did not (the request record and the database); its rounds are bounded and each is a
`critique` trace event. A round is one check: with rounds=2 a draft is checked, revised once with the
reason, and checked again; a draft still failing then is held, and the caller writes nothing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from agent import events
from harness import runtime
from sandbox import db, inbox, sales

FIELDS = ("recipient", "subject", "body", "figures")


@dataclass
class CritiqueResult:
    passed: bool
    draft: dict
    rounds: int
    reason: str


def enabled() -> bool:
    return runtime.switch("critique.report_email") == "external"


def _forms(value: float) -> list[str]:
    value = round(float(value), 2)
    forms = {f"{value:,.2f}", f"{value:.2f}", f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")}
    if value == int(value):
        forms |= {f"{int(value):,}", str(int(value))}
    return sorted(forms, key=len, reverse=True)


def writes_figure(text: str, value: float) -> bool:
    return any(re.search(rf"(?<![\d.,]){re.escape(f)}(?![\d]|[.,]\d)", text or "") for f in _forms(value))


def _number(x) -> float | None:
    try:
        return float(str(x).replace(",", "")) if not isinstance(x, bool) else None
    except (TypeError, ValueError):
        return None


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
            given = _number(figures.get("total_revenue"))
            if given is None or abs(given - truth) > 0.01:
                problems.append(f"total_revenue is {figures.get('total_revenue')}, but the database says "
                                f"{truth:,.2f} for {period}")
            if draft.get("body") and not writes_figure(body, truth):
                problems.append(f"the body does not state the total revenue {truth:,.2f}")
            if "previous_total_revenue" in figures:
                before = sales.distributor_sales(req["distributor_id"], sales.previous_period(period))["total_revenue"]
                given = _number(figures.get("previous_total_revenue"))
                if given is None or abs(given - before) > 0.01:
                    problems.append(f"previous_total_revenue is {figures.get('previous_total_revenue')}, but the "
                                    f"database says {before:,.2f} for {sales.previous_period(period)}")

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
