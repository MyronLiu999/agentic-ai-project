"""The critique loop on draft_report_email (owner: claudea). A stub until claudea builds it.

Contract (PLAN.md section 3), so the workflow and the loop (abraham) can call it today:

    result = critique.run(request_id, draft, revise, rounds=2)
    if not result.passed: trace.end(events.CRITIQUE_HELD) and write nothing

`draft` is a dict with recipient, subject, body and figures. `revise(reason)` returns a new draft.
`check(request_id, draft)` reads only the sandbox and the request record: an outside signal.
"""

from __future__ import annotations

from dataclasses import dataclass

from harness import runtime


@dataclass
class CritiqueResult:
    passed: bool
    draft: dict
    rounds: int
    reason: str


def enabled() -> bool:
    return runtime.switch("critique.report_email") == "external"


def check(request_id: str, draft: dict) -> tuple[bool, str]:
    raise NotImplementedError("critique.check: recompute figures, period and recipient from the sandbox")


def run(request_id: str, draft: dict, revise, *, rounds: int = 2) -> CritiqueResult:
    if not enabled():
        return CritiqueResult(True, draft, 0, "critique off")
    raise NotImplementedError("critique.run: check, revise with the reason, hold at the bound")
