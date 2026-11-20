"""Shared names: trace event kinds, their fields, and run-end reasons. Fixed on Oct 25 so the analysis
script (claudea), the loop and plan (abraham) and the registry (myron) agree without waiting on each
other. Add a name here, and tell the others, before you write a new kind of line.
"""

# trace.event(kind, **fields). Never a field named type, at, session_id or run_id (the trace writes them),
# and never a kind the harness writes (harness/formats.py RESERVED_TYPES, such as "approval").
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
TOOL_ERROR = "tool_error"        # a workflow step's tool failed after the registry's retries (claudea, Oct 31)
UNKNOWN_LAYOUT = "unknown_layout"  # the standard_report workflow met a file that is not the known layout (claudea, Oct 31)

# -- Milestone 2 (added Nov 20 in the setup; same rule: tell the others before adding a kind) --------
# trace.event(kind, **fields). Never a field named type, at, session_id or run_id (the trace writes them),
# and never a kind the harness writes (harness/formats.py RESERVED_TYPES, such as "approval").
RUN_CHECKPOINT = "run_checkpoint"      # fields: run_key, mode, current_step (a durable save; not the plan's CHECKPOINT)
FINAL_CHECKPOINT = "final_checkpoint"  # fields: run_key, state (the run's last checkpoint, written when it ends)
WAIT = "wait"                          # fields: run_key, kind ("outside" | "approval" | "escalation" | "stop"), ref, deadline
RESUME = "resume"                      # fields: run_key, event_kind, from_checkpoint
JOURNAL_HIT = "journal_hit"            # fields: run_key, tool, key (a completed write reused on resume, not re-run)
HOOK_DECISION = "hook_decision"        # fields: tool, action_class, answer ("allow" | "ask" | "deny"), reason
APPROVAL = "approval_decision"         # fields: approval_id, action_class, decision, who, seconds, setting, run_key
ESCALATION = "escalation"              # fields: run_key, signal, attempted, why, needs, over_cap
STOP = "stop"                          # fields: run_key, command ("stop" | "cancel" | "resume" | "rollback"), set_at
COMPENSATION = "compensation"          # fields: run_key, tool, key, compensated_by ("none" when there is none)
NOTICE = "notice"                      # fields: run_key, text (the operator's notice before a run's first write)
MIDTASK = "midtask_message"            # fields: session_id, way ("add" | "replace" | "queue" | "reject"), confirmed
CONTEXT = "context"                    # fields: purpose, tokens, budget, left_out (list of piece sources/ids)
COMPACTION = "compaction"              # fields: before_tokens, after_tokens, cleared_tool_results, summarized_turns
MEMORY_READ = "memory_read"            # fields: session_id, records (ids, kinds, ages, sources)
MEMORY_WRITE = "memory_write"          # fields: record_id, kind, source, supersedes
DISCLOSURE_REFUSED = "disclosure_refused"  # fields: tool, reason (a send whose text lacks disclosure.LINE)
SEARCH_TOOLS = "search_tools"          # fields: query, matches (an empty list is a miss)
CODE_CALL = "code_call"                # fields: run_key, calls, error
SPLIT_RETURN = "split_return"          # fields: role, parent_id, valid, status, spent_tokens, spent_calls

# trace.end(reason)
AWAITING_APPROVAL = "awaiting_approval"  # a gated call waits for the operator on the approvals page
HELD = "held"                            # an escalation holds the run; nothing proceeds by default
STOPPED = "stopped"                      # the operator's /stop took effect; the run checkpointed and waits
CANCELLED = "cancelled"                  # /cancel ended a stopped run for good
UNSETTLED_WRITE = "unsettled_write"      # a write whose outcome cannot be told (third exit), escalated
