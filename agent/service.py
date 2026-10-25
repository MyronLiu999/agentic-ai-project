"""The agent's one entry point. The app and run.py reach the agent only through these functions
(harness/turns.py calls them). Routing lives in agent/router.py; the paths behind it are
agent/workflows.py (your code picks each step) and agent/loop.py (the model picks, bounded by
agent/bounds.py). Text from the outside channel is the stranger's, never the operator's: it enters
model calls labelled as theirs.
"""

from __future__ import annotations

from agent import router
from harness.turns import Reply  # noqa: F401


def operator_turn(session_id: str, text: str) -> Reply:
    """One message from the operator: route the case to its path, run it, reply."""
    use_case = router.classify_operator_message(session_id, text)
    path = router.path_for(use_case)
    raise NotImplementedError(f"operator_turn: run use case {use_case!r} on the {path} path")


def on_outside_reply(thread_id: str, text: str) -> Reply:
    """A stranger's answer on a thread. Milestone 2's: ignored until then."""
    return Reply()


def pending_approvals() -> list[dict]:
    """Empty until Milestone 2: the pending records on the product page are not approvals."""
    return []


def decide_approval(approval_id: str, approved: bool, note: str = "") -> Reply | None:
    raise NotImplementedError("decide_approval: no approval gate is built yet")
