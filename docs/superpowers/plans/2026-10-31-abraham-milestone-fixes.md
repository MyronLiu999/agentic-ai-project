# Abraham milestone fixes implementation plan

> **For agentic workers:** Use superpowers:executing-plans task by task; documentation can proceed independently. Steps use checkbox syntax to record verification.

**Goal:** Correct the Abraham-owned defects reproduced in the Milestone 1 audit, then commit and push directly to main as requested.

**Architecture:** Preserve the public operator-turn entry point and scoped tools. Repair routing without widening authorization; separate reactive write identity from trace attribution; constrain planning to trusted metadata, sanitized checkpoint observations, and exact execution order.

**Tech stack:** Python, unittest, SQLite sandbox, existing harness and registry.

**Spec:** Project Milestone 1.pdf, pp. 6–7, 9–10, 14; audit in this chat on 2026-10-31.

## Global constraints

- Work directly on main; no new branch. User authorized commit and push.
- Use free scripted model responses and real sandbox effects for regressions.
- Preserve existing scope, critique, resource-bound, and planned-write guarantees.
- Change shared interfaces only where needed for Abraham's integration fixes.
- Do not claim live-model results, an official baseline, or an actual live planner specimen.

## Review focus

- New batch wording must not authorize excluded requests or unrelated quantifiers.
- Generic follow-ups use durable session scope; unknown named requests cannot inherit it.
- Prose revisions must not duplicate effects; different effects in one round must remain distinct.
- Outside text in both successful and failed tool results must never enter replanning.
- Independent ready steps still execute in list order; completed steps retain their prefix on revision.

## Task 1: Official routing and follow-ups

Files: agent/router.py, agent/service.py, tests/test_agent_router.py, tests/test_agent_service.py.
Consumes: official YAML operator turns and durable route events. Produces: unchanged Route/Reply interfaces.

- [x] Add failing tests for the exact batch command, both follow-ups, absent session scope, and unsafe batch qualifiers.
- [x] Run those tests and confirm the audit failures.
- [x] Extend bounded command grammar; resolve generic follow-ups from session scope and answer comparison from saved figures.
- [x] Verify routing/service tests including existing scope regressions.

## Task 2: Reactive identity and repeat evidence

Files: agent/loop.py, agent/registry.py, tests/fixtures/agent_loop_fakes.py, tests/test_agent_loop.py, tests/test_agent_effects.py, plan.md.
Consumes: Registry.call and ToolSpec.key_fields. Produces: optional trace_step metadata separate from logical step identity.

- [x] Add real-registry failing tests for cross-round report/email retries, different writes in one round, and exact repeated reads.
- [x] Confirm the failing effects and absent repeat event.
- [x] Omit logical step for reactive calls, preserve model origin using trace_step, and emit request-scoped repeat events.
- [x] Verify loop/registry/effects tests and existing critique attribution.

## Task 3: Planner boundary and ordering

Files: agent/plan.py, tests/test_agent_plan.py, tests/test_agent_plan_execution.py.
Consumes: scoped request records and tool outcomes. Produces: metadata-only planner context and sequential Guard authorization.

- [x] Add failing tests for outside text in initial/revision prompts, forward dependencies, independent-step reordering, and moving completed steps.
- [x] Confirm each fails against current code.
- [x] Allowlist planner metadata, summarize checkpoint outcomes in code, reject forward dependencies, require the next listed step, and preserve completed prefix.
- [x] Verify planning tests and exact official batch through the real registry.

## Task 4: Evidence, review, and delivery

Files: docs/milestones/M1.md, docs/abraham-handoff.md, CHANGES.md, this plan.

- [x] Correct four gates, economic formulas and assumptions, planning guarantees, and stale missing-handout notes.
- [x] Preserve explicit pending official-run dependencies; do not turn scripted evidence into live claims.
- [x] Run make test, make check, and the manual integration probes; request an independent code review.
- [x] Resolve important findings and verify resulting changes.
Delivery: commit reviewed changes, push main without force, then verify the remote commit and clean worktree; report the resulting commit in the chat.

## Execution record

- Tasks 1–3: failing audit regressions observed before each production fix; focused routing/service, real-effect, and planner tests pass.
- Review correction: unsupported qualified batches cannot fall back to a lone new request; a conflicting quarter also requires clarification. Both regression tests failed before the correction.
- Planner detail: runtime request bindings keep periods/contacts out of planner input; remaining-only revisions receive an immutable prefix from code. No completed argument data is sent to the reviser.
- Step-size check: bind parsed row count and chart ID into saved figures; reject unused non-checkpoint outputs. Checkpoints may serve as observable prerequisites.
- Added all five required fake-plan scenarios on the official plan=yes batch task, through the public operator-turn entry point.
- Evidence limit: live-model tuning, a live planner specimen and official first-failure rows await coordinated model access and baseline records. Other owners' known audit issues remain separately assigned.
- Final verification: 278 routine tests, four structural checks, ten manual integration probes, and git diff --check passed. Independent review found one scope issue; its regression and the full suite pass after correction.
