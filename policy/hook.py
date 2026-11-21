"""The policy hook: one answer for every tool call before it runs (Milestone 2; owner: myron, M5).

    decide(call, ctx) -> Decision
        call = {"name", "args", "caller", "step", "key", "request_id"}
        ctx  = {"run_key", "session_id"}
        Decision = {"answer": "allow" | "ask" | "deny", "action_class": "<tool>/<circumstance>",
                    "reason": str, "error_type": str (optional; "stopped" for a stop, "undisclosed"),
                    "screen": dict (for "ask": what the approvals page shows)}
    classify(call) -> str            the action class: the tool, and the circumstance code reads from the sandbox
    registry_hook(request_id) -> callable   what agent/tools.py hands the registry as pre_call_hook

Order (PLAN_M2.md 3.2): the stop flag first (policy/flags.py); a run held by an escalation proceeds no
further; then the prohibited column; then the operator's stated limits (policy/rules.py); then the
disclosure line on any send (agent/disclosure.py); then the columns of policy/autonomy.yaml. A class in no
column is denied. A hook that raises denies the call (the registry fails closed). No answer from the app turns
a prohibited class into a yes: approvals are read only for the requires-approval column and for a stated
limit that asks, never before the prohibited column. The model never sees this file or the policy.

MERGE-CHECK (abraham): a model's ask_stranger call reaches the registry from the loop; pass its question through
disclosure.with_disclosure() there, or the hook refuses it as undisclosed (code-call programs already do).

Classification reads arguments and the sandbox, never a tool's annotations: those are claims a tool makes
about itself (Lecture 5, slide 15).
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from agent import disclosure
from policy import flags

POLICY_FILE = Path(__file__).with_name("autonomy.yaml")
COLUMNS = ("independent", "requires_approval", "prohibited")
_cache: dict = {}


def load_policy() -> dict:
    """policy/autonomy.yaml, read again whenever the file changes."""
    stamp = os.stat(POLICY_FILE).st_mtime_ns
    if _cache.get("stamp") != stamp:
        data = yaml.safe_load(POLICY_FILE.read_text(encoding="utf-8")) or {}
        columns = {c: dict(data.get(c) or {}) for c in COLUMNS}
        seen = [k for c in COLUMNS for k in columns[c]]
        if len(seen) != len(set(seen)):
            raise ValueError("policy/autonomy.yaml: an action class is in more than one column")
        _cache.update(stamp=stamp, policy={**data, **columns})
    return _cache["policy"]


def column_of(action_class: str) -> str | None:
    policy = load_policy()
    return next((c for c in COLUMNS if action_class in policy[c]), None)


def _same(a, b) -> bool:
    return str(a or "").strip().casefold() == str(b or "").strip().casefold()


def classify(call: dict) -> str:
    """The action class of one call: <tool>/<circumstance>."""
    from agent.registry import CODE
    from sandbox import inbox, pending
    name = str(call.get("name") or "")
    args = call.get("args") or {}
    request = inbox.get(call["request_id"]) if call.get("request_id") else None
    if "margin" in name:
        return "read_margins/any"
    if name == "parse_file":
        return "parse_file/own_request"
    if name == "query_sales":
        named = args.get("distributor_id") or args.get("distributor")
        if named and (request is None or not _same(named, request["distributor_id"])):
            return "query_sales/other_distributor"
        return "query_sales/own_distributor"
    if name in ("render_chart", "save_report"):
        return f"{name}/own_request"
    if name == "draft_report_email":
        return "draft_report_email/own_contact"     # narrowed: the tool refuses any other recipient (permanent)
    if name == "draft_clarifying_question":
        return "draft_clarifying_question/own_thread"
    if name == "ask_stranger":
        return "ask_stranger/template" if call.get("caller") == CODE else "ask_stranger/model_written"
    if name == "send_report_email":
        try:
            record = pending.get(int(args.get("pending_id")))
        except (TypeError, ValueError):
            record = None
        if (record is None or request is None or record["request_id"] != request["id"]
                or record["kind"] != "report_email"):
            return "send_report_email/unknown_draft"
        own = _same(record["recipient"], request["contact_email"])
        return "send_report_email/own_contact" if own else "send_report_email/new_recipient"
    if name in ("search_tools", "run_program"):
        return f"{name}/any"
    return f"{name}/unclassified"


def _deny(action_class: str, reason: str, error_type: str | None = None) -> dict:
    decision = {"answer": "deny", "action_class": action_class, "reason": reason}
    if error_type:
        decision["error_type"] = error_type
    return decision


def _trace(kind: str, **fields) -> None:
    try:
        from harness import runtime
        runtime.trace().event(kind, **fields)
    except Exception:
        pass


def decide(call: dict, ctx: dict) -> dict:
    from agent import approvals, escalation
    from policy import rules

    name = call.get("name", "")
    run_key = ctx.get("run_key")
    if flags.is_stopped(run_key):
        return _deny(f"{name}/any", "the operator stopped this run", "stopped")
    hold = escalation.active_hold(run_key)
    if hold is not None:
        return _deny(f"{name}/any", f"held by the {hold['signal']} escalation: waiting for the operator's answer")

    action_class = classify(call)
    policy = load_policy()
    column = column_of(action_class)
    if column == "prohibited":
        return _deny(action_class, f"prohibited: {policy['prohibited'][action_class]}")

    asking_rule = None
    for rule in rules.rules_for(ctx.get("session_id")):
        if rules.matches(rule, action_class, name):
            if rule.get("effect") == "deny":
                return _deny(action_class, f"the operator's stated limit: {rule.get('source_text')!r}")
            asking_rule = asking_rule or rule

    if not disclosure.check(call):
        from agent import events
        reason = "a message to a stranger must carry the disclosure line"
        _trace(events.DISCLOSURE_REFUSED, tool=name, reason=reason)
        return _deny(f"{name}/undisclosed", reason, "undisclosed")

    if column is None:
        return _deny(action_class, "this action class is in no column of the policy: denied")
    if column == "independent" and asking_rule is None:
        return {"answer": "allow", "action_class": action_class, "reason": policy["independent"][action_class]}
    if approvals.is_approved(run_key, call.get("key")):
        return {"answer": "allow", "action_class": action_class, "reason": "the operator approved this call"}
    if asking_rule is None and approvals.plan_covers(run_key, call):
        return {"answer": "allow", "action_class": action_class, "reason": "the approved plan lists this call"}
    reason = (f"the operator's stated limit: {asking_rule.get('source_text')!r}" if asking_rule
              else policy["requires_approval"][action_class])
    screen = approvals.screen_for(call, action_class, call.get("request_id"), caller=call.get("caller"))
    return {"answer": "ask", "action_class": action_class, "reason": reason, "screen": screen}


def registry_hook(request_id: str | None):
    """The registry's pre_call_hook(spec=, args=, caller=, step=, key=) for one request's registry."""
    def hook(*, spec, args, caller, step, key):
        from agent import runs
        from harness import runtime
        run_key = runs.current_key()
        call = {"name": spec.name, "args": args, "caller": caller, "step": step, "key": key,
                "request_id": request_id}
        ctx = {"run_key": run_key, "session_id": runtime.current_session() or (run_key and runs.session_of(run_key))}
        return decide(call, ctx)
    return hook
