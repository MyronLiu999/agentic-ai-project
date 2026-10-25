"""Shared names: trace event kinds, their fields, and run-end reasons. Fixed on Oct 25 so the analysis
script (claudea), the loop and plan (abraham) and the registry (myron) agree without waiting on each
other. Add a name here, and tell the others, before you write a new kind of line.
"""

# trace.event(kind, **fields)
PLAN_DIFF = "plan_diff"          # fields: step_id, label ("executed" | "skipped" | "out_of_order" | "extra")
REPEAT_CALL = "repeat_call"      # fields: tool, args_hash, count
CRITIQUE = "critique"            # fields: round, verdict ("pass" | "revise" | "held"), reason, changed
CHECKPOINT = "checkpoint"        # fields: step_id, passed, reason
OFF_PLAN = "off_plan_refused"    # fields: tool, args
ROUTE = "route"                  # fields: use_case, path, how ("record" | "fingerprint" | "model")
BOUND = "bound"                  # fields: max_steps, token_budget, wall_clock_s (written once per loop)

# trace.end(reason)
DONE = "done"
STEP_LIMIT = "step_limit"
WALL_CLOCK = "wall_clock"
AGENT_BUDGET = "agent_budget"    # never "token_budget": the runner reserves that name
PLAN_REJECTED = "plan_rejected"
REPLAN_BOUND = "replan_bound"
CRITIQUE_HELD = "critique_held"
DECLINED = "declined"
NEEDS_ANSWER = "needs_answer"    # a case that needs a stranger's answer, ended with a pending question
