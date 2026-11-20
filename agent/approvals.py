"""The approval gate's store and log (Milestone 2, Part 2 task 4; owner: myron, M6).

    put_up(run_key, session_id, call, action_class, screen) -> approval_id
        call = {"name", "args", "key"}; screen = the dry run, the computed facts, the labelled rationale
    pending() -> list[dict]          what agent.service.pending_approvals() returns (each with id, session_id)
    decide(approval_id, approved, note, who="operator") -> dict
        logs: action class, the facts shown, the decision, who, seconds from put up to answer,
        the approval switch's setting, the run key. Returns the item, with its run_key.
    is_approved(run_key, key) -> bool    the hook asks this when the resumed run calls again
    withdraw(run_key) -> list[str]       a stop withdraws the run's waiting calls

agent.service's pending_approvals / decide_approval delegate here; decide_approval then resumes the run
through agent.runs.resume(run_key, {"kind": "approval", ...}).
Setup stub: nothing is ever put up (the setup hook never answers "ask").
"""

from __future__ import annotations


def put_up(run_key, session_id, call, action_class, screen) -> str:
    raise NotImplementedError("approvals.put_up is myron's M6")


def pending() -> list[dict]:
    return []


def decide(approval_id: str, approved: bool, note: str = "", who: str = "operator") -> dict:
    raise NotImplementedError("approvals.decide is myron's M6")


def is_approved(run_key, key) -> bool:
    return False


def withdraw(run_key) -> list[str]:
    return []


# Approval at the plan (approval.<use_case> = plan). abraham's plan.py puts the validated plan up once, listing
# every gated step it will take with what each will do; myron's hook then lets a call through unasked only if
# the approved plan covers it exactly. A gated call the plan did not list, or any revision, asks again.

def put_up_plan(run_key, session_id, plan, gated_steps) -> str:
    """gated_steps = [{"step_id", "tool", "args", "action_class"}]. Returns an approval_id (in pending())."""
    raise NotImplementedError("approvals.put_up_plan is myron's M6")


def plan_covers(run_key, call) -> bool:
    """True only if an approved plan of this run lists this call: same tool, same arguments."""
    return False
