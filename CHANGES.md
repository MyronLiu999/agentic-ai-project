# Changes

## Milestone 1

**Added:** (scaffold) SQLite sandbox for a sales database, uploads, requests, reports and pending
records (`sandbox/`); seed and demo data; product pages (requests, request, query); agent stubs
(`agent/router.py`, `bounds.py`, `registry.py`, `tools.py`, `workflows.py`, `loop.py`); switch groups;
test task `standard_report_clean` with its check and tests.

**Removed:** `tasks/example.yaml`, `checks/example.py`.

**Limited:** the agent has no send tool; the emailed report is a pending record the operator sends.
`sandbox/margins.py` is imported by no tool.

**Fixes after the baseline:** none yet.

**Reused code:** none yet (name each assignment and whose repository).

**Abraham — B2, first fixture:** added a synthetic messy-file request with semicolon-separated
headers and decimal-comma amounts. Tests exercise the real sandbox seed and existing report check:
the upload remains intact, an empty completion claim fails, and a correct report plus pending email
passes. The fixture stays outside the official evaluation tasks. Routing and agent execution follow
in later reviewed steps.

**Abraham — B1, routing:** added request/thread selection from stored records, use-case routing
from request questions and CSV headers, switch-controlled paths, and route trace events. An
ambiguous work-versus-status message uses one metered classification call with no tools. Unknown
references, ambiguous request selection, and invalid classifier replies require clarification.
Excluded/alternative IDs and qualified batch phrases cannot silently widen request selection;
ambiguous status questions beginning with "check" use classification before any rerun.
Tests cover all six use cases using the sandbox and free scripted model responses. Service dispatch
and agent execution remain the next implementation steps.

**Abraham — B3, bounded loop:** added a request-bound model/tool loop with externally
enforced step, token, and monotonic-time limits, traced values and rationales, bounded
repair attempts, and preserved assistant/tool history. Email writes require a passed
critique over the selected request's saved report; revisions consume the same budget.
Held drafts, malformed revisions, and foreign report references leave no pending email.
Successful clarifying questions retain their pending state even when a time limit expires.
Review fixes preserve tool-step attribution, trace local rejections, expose revised
executed inputs to the model, and isolate mutable arguments/figures. Tests use the real
sandbox, metering, and traces with scripted models and substitutes for team-owned stubs.
The initial 12-call/150,000-token/90-second limits are provisional; in-flight synchronous
operations are not interrupted. Service integration and batch planning follow separately.

**Abraham — B4/B5, service:** connected public operator turns to record-based routing,
the bounded loop, and the shared workflow signatures. Status follow-ups recover request
scope from the session trace after restart; ambiguous selection asks for clarification.
Replies preserve action lines and pending questions. Request states come from recorded
effects, not a model's completion claim. Harness-level tests exercise never-stops,
each dispatch path, session follow-ups, and isolated unplanned batch requests.

**Abraham — B6a, plan contract:** added bounded plan validation, same-request dependency
and `$fill` bindings, cycle/orphan checks, immutable completed steps, observable-result
predicates, off-plan call refusal, plan-difference records, and request-scoped repeat
detection. Twelve tests cover valid bindings and malformed, unauthorized, or incomplete
plans. Batch planning/execution is connected in the following step.

**Abraham — B6b, batch execution:** connected the batch switch to a bounded planner
and dependency scheduler. Plans and fills are traced; sandbox checks verify queries
and writes. Failed read checkpoints may revise remaining work at most twice, preserving
completed steps and effects. Exactly one terminal and at most one saved report are
allowed per request. Planned email uses the same critique gate as the reactive loop;
approved email amendments are recorded in the plan before execution. Tests include
actual report/email effects, two-request isolation, bounded bad planners, parse repair,
no duplicate writes across replan, false tool success, and held/revised email drafts.

**Abraham — B8, failure analysis:** added `experiments/analysis/failures.py` to list
failed/unfinished records, all terminal reasons, and the first explicit failure's
physical trace line. Missing/corrupt evidence is reported without inventing a cause.
Synthetic and discarded runs are excluded by default; explicit inclusion labels
synthetic rows. JSON and Markdown output are read-only and tested against handwritten
records, including nested tool errors, held critiques, and malformed trace lines.

**Abraham — final review fixes:** a registry error after a write now stops the batch
because the effect may already exist; only designated read checkpoints can replan.
Added regressions for a report persisted before an error, oversized public batches,
unrepresentable numeric values, and deeply nested plan data. Plan nesting is capped
before recursive processing; invalid input returns traced bounded rejection rather
than an uncaught exception. No baseline or live-model run was used for these fixes.

**Abraham — B9 and integration handoff:** filled the agent-owned build/decision entries,
plan design, checkpoint/step-size explanation, per-step batch/messy persistence
inventory, and first-failure table skeleton in `docs/milestones/M1.md`. Added
`docs/abraham-handoff.md` with public interfaces, verification, prompt assumptions,
and the ordered integration/development steps. B7 remains unmeasured: no real-model
tuning is claimed while production tools, registry, critique and workflows are
unintegrated. Exact handout gate/test wording, Myron's A1/A2 values, and official
run evidence remain explicit dependencies. Final code verification: 169 tests and
four structural checks passed on 2026-10-31, using no live API calls.

**Abraham — critique integration:** tested the published domain implementation in
an isolated snapshot. Its critic catches callback exceptions, which had relabeled
an exhausted model-call allowance as `critique_held`. The shared email gate now
preserves the original execution-limit reason. Regressions cover both reactive and
planned execution; five focused probes using the real critic/status workflow pass
with scripted models and sandbox-writing tool substitutes. The published tool
branch still differs from PLAN.md's six-tool contract; full integration remains pending.

**Abraham — planned write identity:** a probe using the published real registry
showed that distinct chart steps reused one write key when the planner supplied the
model-call number as `step`. Planned calls now pass their stable plan-step ID. A
regression verifies two intended charts leave two different artifacts; the same
probe passes with the published registry after the fix.
