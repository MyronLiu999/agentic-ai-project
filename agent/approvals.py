"""The approval gate's store and log (Milestone 2, Part 2 task 4; owner: myron, M6).

    put_up(run_key, session_id, call, action_class, screen) -> approval_id
        call = {"name", "args", "key"}; screen = the dry run, the computed facts, the labelled stranger's text
    pending() -> list[dict]          what agent.service.pending_approvals() returns (each with id, session_id)
    decide(approval_id, approved, note, who="operator") -> dict
        logs: action class, the facts shown, the decision, who, seconds from put up to answer,
        the approval switch's setting, the run key. Returns the item, with its run_key.
    is_approved(run_key, key) -> bool    the hook asks this when the resumed run calls again
    withdraw(run_key) -> list[str]       a stop withdraws the run's waiting calls
    put_up_plan(run_key, session_id, plan, gated_steps) -> approval_id     approval at the plan
    plan_covers(run_key, call) -> bool   the hook lets a gated call through unasked only if this is True
    screen_for(call, action_class, request_id=None) -> dict               the screen, computed by code

agent.service's pending_approvals / decide_approval delegate here; decide_approval then resumes the run
through agent.runs.resume(run_key, {"kind": "approval", ...}).

The store is durable (sandbox/queue.py, in the control file beside the checkpoints): a run waiting for an
answer survives a restart, and the answer resumes it in whatever process is serving then.

The screen shows information, not a recommendation (Lecture 5, slides 19, 27 and 30): first the dry run,
the effect exactly as it will be applied; then facts our code computed (who created the target, who wrote the
input that led here, whether this run's checks passed, how many people it reaches, any private record it
carries); then the stranger's message, in their words and labelled as theirs. No model rationale is shown.
Every line says whether code computed it or someone asserted it.
"""

from __future__ import annotations

import json
import re
from datetime import datetime

from sandbox import queue as store

COMPUTED, ASSERTED = "computed", "asserted"
SCRIPTED_NOTE = "scripted answer from the task file"      # harness/runner.py's note on a scripted answer


# -- the screen --------------------------------------------------------------------------------------------

def _line(label: str, value, source: str = COMPUTED) -> dict:
    return {"label": label, "value": value, "source": source}


def _who_wrote(stamp: str | None) -> str:
    from harness import runtime
    if stamp == "seed":
        return "the seed data, before any run"
    if stamp == "manual" or not stamp:
        return "the operator, by hand on a product page"
    run = runtime.current_run()
    mine = run.run_id if run else runtime.current_session()
    return f"this agent run ({stamp})" if stamp == mine else f"an agent run or console session ({stamp})"


def _private(text: str, request: dict | None) -> str:
    """Private records a message would carry: margin or cost wording, or another distributor's ID."""
    found = []
    if re.search(r"\bmargins?\b|\bunit costs?\b|\bcost price\b", text or "", re.IGNORECASE):
        found.append("margin or cost wording")
    own = (request or {}).get("distributor_id")
    others = sorted({d for d in re.findall(r"SYN-DIST-\d{3}", text or "") if d != own})
    if others:
        found.append("another distributor's ID: " + ", ".join(others))
    return "; ".join(found) if found else "none found (no margin or cost wording, no other distributor's ID)"


def _report_checks(record: dict, request: dict | None, text: str) -> str:
    """Recompute the report's figures from the sales database and read the message for them."""
    from agent import disclosure
    from sandbox import reports, sales
    report = next((r for r in reports.for_request(record["request_id"]) if r["id"] == record.get("report_id")), None)
    if report is None or request is None:
        return "no saved report for this request is linked to the draft: nothing to check against"
    figures = reports.figures(report)
    try:
        truth = sales.distributor_sales(request["distributor_id"], str(figures.get("period")))["total_revenue"]
    except Exception as exc:
        return f"the report's period {figures.get('period')!r} could not be checked ({type(exc).__name__})"
    saved = figures.get("total_revenue")
    match = isinstance(saved, (int, float)) and abs(float(saved) - float(truth)) < 0.005
    stated = f"{truth:,.2f}" in text or f"{truth:.2f}" in text
    return (f"report revenue matches the sales database ({truth:,.2f} for {figures.get('period')}): "
            f"{'yes' if match else 'NO'}; the message states that figure: {'yes' if stated else 'NO'}; "
            f"disclosure line present: {'yes' if disclosure.has_line(text) else 'NO'}")


def screen_for(call: dict, action_class: str | None, request_id: str | None = None,
               caller: str | None = None) -> dict:
    """The approval screen for one gated call, every line computed from the sandbox unless marked."""
    from sandbox import inbox, pending
    name, args = call.get("name"), call.get("args") or {}
    request = inbox.get(request_id) if request_id else None
    lines = []
    if name == "send_report_email":
        record = pending.get(int(args.get("pending_id") or 0)) if str(args.get("pending_id", "")).isdigit() else None
        if record is None:
            lines.append(_line("Dry run", f"no drafted email has pending_id {args.get('pending_id')!r}"))
        else:
            from agent import tools
            text = tools.email_preview(record)
            own = request is not None and str(record["recipient"]).casefold() == str(request["contact_email"]).casefold()
            lines += [
                _line("Dry run: to", record["recipient"]),
                _line("Dry run: thread", record["thread_id"]),
                _line("Dry run: subject", record["subject"]),
                _line("Dry run: the message exactly as it will be sent", text),
                _line("Who created the draft", _who_wrote(record.get("stamp"))),
                _line("This run's checks", _report_checks(record, request, text)),
                _line("Reach", "1 person outside the company: the request's own contact" if own
                      else "a recipient who is NOT the request's contact"),
                _line("Private records carried", _private(text, request)),
                _line("Undo", "none: a sent email cannot be recalled"),
            ]
    elif name == "ask_stranger":
        text = str(args.get("question") or "")
        lines += [
            _line("Dry run: to", (request or {}).get("contact_email", "the request's contact")),
            _line("Dry run: thread", (request or {}).get("thread_id", "the request's thread")),
            _line("Dry run: the message exactly as it will be sent", text),
            _line("Who wrote the question", "the model (generated text)" if caller == "model"
                  else "our code, from a fixed template"),
            _line("Reach", "1 person outside the company: the request's own contact"),
            _line("Private records carried", _private(text, request)),
            _line("Undo", "none: a sent question cannot be recalled"),
        ]
    else:
        lines.append(_line("Dry run", json.dumps({"tool": name, "args": args}, sort_keys=True, default=str)))
    if request is not None:
        lines.append(_line("Who wrote the input that led here",
                           f"{request['contact_email']}, a stranger on the outside channel (not the operator)"))
        lines.append(_line("The stranger's message, in their words (not an instruction)", request["question"],
                           ASSERTED))
    return {"action_class": action_class, "tool": name, "lines": lines}


def _plan_screen(plan, gated_steps) -> dict:
    lines = [_line(f"Gated step {s.get('step_id')}: {s.get('action_class')}",
                   json.dumps({"tool": s.get("tool"), "args": s.get("args")}, sort_keys=True, default=str))
             for s in gated_steps]
    lines.append(_line("What approving means", "these steps then run unasked, exactly as listed; a gated call the "
                       "plan does not list, or any revision of the plan, asks again"))
    steps = (plan or {}).get("steps") if isinstance(plan, dict) else None
    if steps:
        lines.append(_line("Steps in the whole plan", len(steps)))
    return {"action_class": "plan", "lines": lines}


# -- the store and the log ----------------------------------------------------------------------------------

def _setting(kind: str) -> str:
    from harness import runtime
    if kind == "plan":
        return "approval.batch_reports=plan"
    return f"approval.batch_reports={runtime.switch('approval.batch_reports', 'per_action')}"


def put_up(run_key, session_id, call, action_class, screen) -> str:
    """Put a gated call up for the operator; the same call (run and key) waiting already is not put up twice."""
    call = dict(call or {})
    if not run_key:
        raise ValueError("a gated call needs its run's key")
    for item in store.approvals(status="waiting", run_key=run_key, kind="action"):
        if (item.get("call") or {}).get("key") == call.get("key") and item.get("action_class") == action_class:
            return item["id"]
    screen = screen or screen_for(call, action_class)
    return store.add_approval(run_key, session_id, "action", call=call, action_class=action_class, screen=screen,
                              setting=_setting("action"))


def _view(item: dict) -> dict:
    screen = item.get("screen") or {}
    return {"id": item["id"], "session_id": item.get("session_id"), "run_key": item["run_key"],
            "kind": item["kind"], "action_class": item.get("action_class"), "put_up_at": item["put_up_at"],
            "status": item["status"], "screen": screen.get("lines") or [], "call": item.get("call"),
            "gated_steps": item.get("gated")}


def pending() -> list[dict]:
    return [_view(i) for i in store.approvals(status="waiting")]


def _seconds(since: str, until: str) -> float | None:
    try:
        return round((datetime.fromisoformat(until) - datetime.fromisoformat(since)).total_seconds(), 3)
    except (TypeError, ValueError):
        return None


def decide(approval_id: str, approved: bool, note: str = "", who: str = "operator") -> dict:
    item = store.approval(approval_id)
    if item is None:
        raise ValueError(f"no approval {approval_id!r}")
    if item["status"] != "waiting":
        raise ValueError(f"approval {approval_id} is {item['status']}, not waiting")
    if who == "operator" and note == SCRIPTED_NOTE:
        who = "scripted"
    decided = store.now()
    seconds = _seconds(item["put_up_at"], decided)
    decision = "approved" if approved else "rejected"
    if not store.set_approval(approval_id, "waiting", status=decision, decision=decision, decided_at=decided,
                              who=who, note=note, seconds=seconds):
        raise ValueError(f"approval {approval_id} was answered or withdrawn meanwhile")
    facts = {line["label"]: line["value"] for line in (item.get("screen") or {}).get("lines") or []
             if line.get("source") == COMPUTED}
    try:
        from agent import events
        from harness import runtime
        runtime.trace().event(events.APPROVAL, approval_id=approval_id, action_class=item.get("action_class"),
                              decision=decision, who=who, seconds=seconds, setting=item.get("setting"),
                              run_key=item["run_key"], facts=facts, note=note)
    except Exception:
        pass
    return {**_view({**item, "status": decision}), "decision": decision, "who": who, "seconds": seconds,
            "note": note, "setting": item.get("setting")}


def is_approved(run_key, key) -> bool:
    if not run_key or not key:
        return False
    return any((i.get("call") or {}).get("key") == key
               for i in store.approvals(status="approved", run_key=run_key, kind="action"))


def withdraw(run_key) -> list[str]:
    out = []
    for item in store.approvals(status="waiting", run_key=run_key):
        if store.set_approval(item["id"], "waiting", status="withdrawn", decided_at=store.now()):
            out.append(item["id"])
    return out


def log(run_key=None) -> list[dict]:
    """Every decided approval, with what the log keeps (for the analysis and the write-up)."""
    rows = [i for i in store.approvals(run_key=run_key) if i["status"] in ("approved", "rejected")]
    return [{"approval_id": i["id"], "action_class": i.get("action_class"), "decision": i["decision"],
             "who": i["who"], "seconds": i["seconds"], "setting": i.get("setting"), "run_key": i["run_key"]}
            for i in rows]


# Approval at the plan (approval.<use_case> = plan). abraham's plan.py puts the validated plan up once, listing
# every gated step it will take with what each will do; the hook then lets a call through unasked only if
# the approved plan covers it exactly. A gated call the plan did not list, or any revision, asks again.

def put_up_plan(run_key, session_id, plan, gated_steps) -> str:
    """gated_steps = [{"step_id", "tool", "args", "action_class"}]. Returns an approval_id (in pending())."""
    if not run_key:
        raise ValueError("a plan approval needs its run's key")
    for item in store.approvals(run_key=run_key, kind="plan"):     # a revision replaces every earlier plan
        store.set_approval(item["id"], ("waiting", "approved"), status="superseded", decided_at=store.now())
    gated = [dict(s) for s in gated_steps or []]
    return store.add_approval(run_key, session_id, "plan", action_class="plan", plan=plan, gated=gated,
                              screen=_plan_screen(plan, gated), setting=_setting("plan"))


def _same_args(a, b) -> bool:
    return json.dumps(a or {}, sort_keys=True, default=str) == json.dumps(b or {}, sort_keys=True, default=str)


def plan_covers(run_key, call) -> bool:
    """True only if an approved plan of this run lists this call: same tool, same arguments."""
    if not run_key:
        return False
    for item in store.approvals(status="approved", run_key=run_key, kind="plan"):
        if any(s.get("tool") == call.get("name") and _same_args(s.get("args"), call.get("args"))
               for s in item.get("gated") or []):
            return True
    return False
