"""The agent path's bound, set from outside the model. DRAFT values: the owner of agent/ sets each
with its reason, and the trace or record must show them (trace.end reasons: step_limit, wall_clock,
agent_budget; the runner's own `token_budget` is the harness's ceiling, so name ours differently)."""

MAX_STEPS = 12            # TODO(agent owner): why 12 (Assignment 1's longest successful run + margin)
TOKEN_BUDGET = 150_000    # TODO: why; must stay below settings.yaml's session_token_ceiling (400000)
WALL_CLOCK_S = 90         # TODO: why; a turn over ~10 s should show progress (Lecture 1, slide 34)
