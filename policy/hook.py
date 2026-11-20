"""The policy hook: one answer for every tool call before it runs (Milestone 2; owner: myron, M5).

    decide(call, ctx) -> Decision
        call = {"name", "args", "caller", "step", "key", "request_id"}
        ctx  = {"run_key", "session_id"}
        Decision = {"answer": "allow" | "ask" | "deny", "action_class": "<tool>/<circumstance>",
                    "reason": str, "error_type": str (optional; "stopped" for a stop)}

    registry_hook(request_id) -> callable   what agent/tools.py hands the registry as pre_call_hook

Order: the stop flag first (policy/flags.py), then the prohibited column, then the operator's stated
limits (policy/rules.py), then the disclosure line on any send (agent/disclosure.py), then the columns
of policy/autonomy.yaml. A hook that raises denies the call (the registry fails closed). No answer from
the app turns a prohibited class into a yes. The model never sees this file or the policy.

Setup stub: stop -> deny; a send without the disclosure line -> deny; everything else -> allow.
myron's M5 replaces the body of decide(); keep its signature and the registry_hook adapter.
"""

from __future__ import annotations

from agent import disclosure
from policy import flags


def decide(call: dict, ctx: dict) -> dict:
    name = call.get("name", "")
    if flags.is_stopped(ctx.get("run_key")):
        return {"answer": "deny", "action_class": f"{name}/any", "reason": "the operator stopped this run",
                "error_type": "stopped"}
    if not disclosure.check(call):
        return {"answer": "deny", "action_class": f"{name}/undisclosed",
                "reason": "a message to a stranger must carry the disclosure line", "error_type": "undisclosed"}
    return {"answer": "allow", "action_class": f"{name}/any", "reason": "setup stub: allow"}


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
