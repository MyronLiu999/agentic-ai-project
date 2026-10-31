# Abraham's agent core implementation plan

> Execute this plan inline with the executing-plans and test-driven-development workflows. On 2026-10-31 the user authorized completing all remaining Abraham work in steps and automatically committing and pushing each verified step. This supersedes the earlier approval pauses.

**Goal:** Implement Abraham's responsibilities from PLAN.md in independently reviewable steps.

**Architecture:** Keep the existing service entry point, request-bound registry, sandbox, and harness. Establish controlled inputs first, then implement routing, bounded execution, service integration, and batch planning. Use the shared events and critique contract.

**Tech stack:** Python 3.10+, unittest, YAML, SQLite, existing harness and sandbox.

**Spec:** PLAN.md, sections 3 and 5 (B1–B10), plus the step-by-step breakdown approved in this chat.

## Global constraints

- Work on the user-requested `abraham` branch in this checkout.
- Commit and push verified implementation steps to `origin/abraham` automatically, as authorized on 2026-10-31.
- Edit Abraham's files, tests, and documentation; preserve other owners' interfaces.
- Do not edit `harness/`, `channel/`, or `run.py`.
- Use only synthetic inputs. No API keys in source or fixtures.
- Use fake models for automated tests. Coordinate any real-model development with the team's official runs.
- Keep fixtures in `tests/fixtures/agent_*`, outside the official evaluation task suite.

## Review focus

- Task fixtures must seed actual domain records and preserve uploaded data.
- A claim of completion without persistent effects must not pass a fixture's check.
- The checker must accept a correct planted effect for the fixture's distributor and period.
- Subsequent routing must distinguish a follow-up from a new request.
- Subsequent execution must preserve request scope, enforce limits, and critique before writing an email.

## Task 1: First runnable messy-file fixture (B2, first checkpoint)

**Files:**
- Create `tests/fixtures/agent_messy_file.yaml`.
- Create `tests/test_agent_fixtures.py`.
- Update Abraham's entry in `CHANGES.md`.

**Consumes:** `harness.tasks.load(path)`, `tests.support.fixed_run(task_file, run_id)`, `ScratchTest.run_check(task_file, plant, replies=None)`, the existing sandbox seed, and `checks/standard_report.py`.

**Produces:** A complete task fixture that can later drive routing and loop tests: Brightline's Q3 report request with semicolon-separated German headers and decimal-comma amounts. Its final expected effects are the existing quarterly report and pending email contract. Its checker does not yet verify parsing or routing.

- [x] Write tests for loading/seeding the fixture, rejecting a no-effect completion claim, and accepting a correct report and pending email.
- [x] Run the focused tests before adding the fixture; verify that the absent fixture is the failure.
- [x] Add the fixture without changing the router or the sandbox.
- [x] Run the focused tests, `make test`, `make check`, and `git diff --check`.
- [x] Present the first checkpoint and proposed commit message; wait for approval.

Proposed message: `test(agent): add a runnable messy-file fixture`

Verification on 2026-10-30: the baseline had 56 passing tests; the first checkpoint has
59 passing tests (3 new), and all four structural checks pass. No model calls were made.
The user approved this checkpoint and requested the next step on 2026-10-30.
Approval is applied to the local commit; pushing still requires explicit instruction.

## Subsequent checkpoints

Each checkpoint is specified before implementation and verified before its commit and push.

1. Complete the remaining controlled fixtures as their test consumers are introduced (B2).
2. Implement trusted-data routing and trace decisions (B1).
3. Implement the bounded loop and critique-before-write behavior (B3).
4. Connect service dispatch, follow-ups, and pending questions (B4).
5. Verify full paths and bounded nontermination on fakes (B5).
6. Add batch plan validation, placeholder resolution, enforcement, checkpoint revision, and diff/repeat detection (B6).
7. Tune prompts in coordinated development runs (B7).
8. Build failure analysis and its tests (B8).
9. Complete Abraham's milestone evidence and inventory (B9).
10. Verify and integrate with the real components (B10, T2, T3).

## Task 2: Request routing (B1)

**Files:** modify `agent/router.py`, add `tests/test_agent_router.py` and
`tests/fixtures/agent_intent_models.py`, and update Abraham's changelog entry.

**Consumes:** `inbox.all_requests()`, `files.read_upload(request_id, name)`,
`runtime.switch(name)`, `runtime.client(session_id)`, and `runtime.trace(session_id)`.

**Produces:** `route_operator_message(session_id, text) -> Route`, where the immutable
result carries `use_case`, `path`, `request_ids` (a tuple), and `how`. Preserve
`classify_operator_message(session_id, text) -> str` as the existing compatibility
interface and `path_for(use_case) -> str`. `RoutingError(ValueError)` reports missing,
unknown, or ambiguous requests and invalid model classifications; B4 will turn these
into operator-facing replies. Routing does not execute tools or change domain state.

Implementation decisions for this checkpoint:

- Clear status and action phrases are handled by code. Only ambiguous operator text
  receives one metered, traced model call with no tools. The response must be exactly
  `new_task` or `status_question`; invalid answers do not authorize execution.
  Generic verbs such as "check" do not alone authorize new work: "Check whether
  REQ-SYN-thread-1001 is done" goes through intent classification.
- Resolve exact request/thread references from the operator's text against records.
  An unqualified action selects the sole new request. Multiple new requests require
  an explicit batch instruction or explicit IDs. A bare status question leaves request
  selection to the session-aware status workflow.
- Excluded or alternative IDs require clarification rather than selecting every
  mentioned record. Batch selection without IDs accepts only unqualified whole
  commands such as "Handle all new requests". Phrases such as "all products" or
  "all reports for Acme" do not authorize processing every new request.
- The model receives only the operator's text and a count of new requests. It does
  not receive file contents or distributor questions and cannot select request IDs.
- For new work, precedence is restricted-data request, batch, comparison, then file
  fingerprint. Restriction and comparison rules inspect text as data, not instructions.
  A batch containing a restricted request is declined as a whole in this first version.
- The known standard fingerprint is a comma-separated header with `sku`, `units_sold`,
  and optional `region`, without duplicate or unexpected fields. Missing, unreadable,
  empty, or unfamiliar files go to `messy_file`; actual data validation belongs to tools.
- Every successful decision records the existing `route` event, its configured path,
  provenance, and selected request IDs. Do not add paths not yet implemented to switches.

- [x] Write failing routing tests covering all six use cases and the cases below.
- [x] Implement classification, record selection, file fingerprint, and route tracing.
- [x] Verify ambiguous/unknown references, completed requests, misleading filenames,
  unreadable files, prefix-colliding IDs, and restrictive requests within batches.
- [x] Verify a metered model fallback, rejected malformed/tool-calling responses,
  status questions with no domain writes, and switch-controlled dispatch.
- [x] Run focused tests, `make test`, `make check`, and whitespace checks; review the change.
- [x] Present the checkpoint and proposed message; wait for approval before committing.

Proposed message: `feat(agent): route requests from records and file fingerprints`

Verification on 2026-10-30: all 87 tests pass, including 28 routing tests, and all four
structural checks pass. A separate code review identified excluded-ID selection,
unrelated batch quantifiers, and status questions beginning with "check" as potential
unintended-work paths. Regression tests reproduced these failures before the fixes;
the corrected suite passes. Tests use free scripted model responses, with no live API
calls. Service execution and operator-facing clarification replies belong to B4.
The user approved this checkpoint and requested the next step on 2026-10-30.
Approval covers the local commit; pushing remains unauthorized.

Task 1 local commit: `3182b64`. No push has been authorized.

## Task 3: Bounded agent loop (B3)

Task 2 local commit: `0817e3b`.

**Files:** `agent/loop.py`, `agent/bounds.py`, `tests/test_agent_loop.py`,
`tests/test_agent_bounds.py`, `tests/fixtures/agent_loop_fakes.py`, and this plan/changelog.

**Consumes:** the metered runtime client and trace; `Registry.definitions()` and
`call(name, args, caller, step=...)`; `critique.run(request_id, draft, revise, rounds=2)`;
request records and saved reports. Default registry construction binds the request ID.

**Produces:** `loop.run(session_id, request_id, text, *, registry=None, limits=None,
clock=None) -> LoopResult`, with terminal reason, model/operator text, action lines,
waiting thread, step count, and loop token use. B4 adapts this result to `Reply`.

Design decisions:

- A step is one model invocation, including retries and critique revisions. The
  initial limit is 12: six ordinary tool rounds, a final response, up to two draft
  revisions, and three repair rounds. This is a provisional engineering allowance,
  not an A1 measurement. The token allowance is 150,000 (below the 400,000 harness
  ceiling); 90 seconds limits further work after a slow turn. All values and their
  rationales are traced. A monotonic clock avoids clock-adjustment errors.
- Check token/time limits before and after model calls, before every tool, and
  after tools/critique. A synchronous operation already running cannot be interrupted;
  the guard prevents subsequent work once it returns. Token usage includes cached
  tokens and revisions, measured from loop entry; the harness ceiling still applies.
- Preserve complete assistant content and return all tool results together with
  error flags. Registry errors go back to the model for a bounded repair attempt.
  The registry owns tool-call traces and retries; the loop owns model-call traces.
  Calls rejected before reaching the registry are traced with `executed=false` and
  `rejected_by=loop`. A changed executed input accompanies model feedback separately
  from the original assistant blocks and unchanged registry result fields.
- Label the operator's instruction separately from the outside request and file
  data. Scope is bound by code. Never infer successful effects from model prose.
- Before `draft_report_email`, resolve its report only within the bound request and
  attach its saved figures for critique. Execute only the passed draft. Revision
  calls have no tools and can edit recipient, subject, and body; the report link and
  its saved figures stay fixed. Wrong saved figures therefore hold the email for
  correction in a later turn instead of making the email disagree with the report.
- A held critique or exhausted bound writes no email. A successful clarifying
  question ends immediately as `needs_answer`; later calls in that response are
  not executed. Service/status integration and batch planning remain B4/B6.
  If its write returns after the deadline, the result keeps the waiting thread
  while reporting `wall_clock`; the pending effect is not lost from the reply state.
- Test-only substitutes are necessary because registry/tool bodies and the enabled
  critique are still stubs. Pending/report writes in these tests use the real sandbox.

- [x] Write failing tests for step/token/time boundaries and invalid limits.
- [x] Implement external bounds and their rationales.
- [x] Write failing tests for the model/tool conversation, failures, scope, critique,
  revision limits, and actual pending effects.
- [x] Implement the loop and critique gate against the shared contracts.
- [x] Run the focused and full suites, structural checks, and whitespace checks.
- [x] Present the checkpoint and proposed commit message; subsequent user authorization covers committing and pushing.

Proposed message: `feat(agent): enforce loop bounds and critique pending emails`

Review: a separate read-only review reproduced waiting-state loss after a slow
question write, tool-step attribution shifting during critique, and missing context
about revised email arguments. Local validation rejections also lacked trace evidence,
and shallow copying allowed critique to mutate the figures comparison baseline.
Regression tests failed before the fixes and passed afterward. A further regression
proved that registry argument normalization must not mutate assistant history; the
loop now passes independent argument copies. All 31 focused tests pass.
Final verification on 2026-10-30: all 118 tests pass, all four structural checks pass,
and tracked/new-file whitespace checks pass. No live model calls were made.

Rulings retained from the review: numerical limits are provisional pending run evidence;
time/token checks are cooperative and can overshoot within one synchronous call;
critique-off deliberately uses the shared pass-through; saved figures stay fixed
during email revision, so a bad report requires a later correction; production
registry/critique/service/planner integration is deferred to its assigned checkpoint.

## Known dependencies

- The referenced milestone handout is absent; exact gate definitions and the five plan-test requirements remain unverified.
- Claudea must supply the standard-workflow callable interface.
- Myron must supply argument-validating fakes and the registry pre-call hook interface.
- These dependencies do not prevent the fixture and routing checkpoints.

## Remaining execution sequence (authorized 2026-10-31)

1. B4/B5: wire the public service to the router, loop and domain workflows; preserve
   request scope and pending questions; prove path dispatch and never-stops behavior
   through the actual harness. Do not mark requests done from model text alone.
2. B6: validate and trace batch plans, including dependency cycles/orphans and explicit
   `$fill` bindings; enforce each call, compare calls with plans, count repeats, check
   observable outcomes, and bound planning/revision. Test invalid plans, off-plan
   calls, placeholder resolution, checkpoint recovery, and exhaustion.
3. B8: implement a read-only failure report with terminal reasons and the physical
   trace line of the first failure; distinguish missing evidence and synthetic runs.
4. B7/B9/B10: document prompts, gates, step sizes, durable effects, and integration
   requirements; run final checks and a fresh code review. Real-model tuning requires
   working team-owned tools and coordinated access; never substitute fake evidence.

Published interface inspection: `origin/claudea/domain` exposes
`standard_report(session_id, request_id, registry=None)`, matching the intended
two-argument service call. Its code is not merged or copied into Abraham's files.
The remote main still contains registry/tool/critique stubs. The milestone handout
is still absent; exact handout wording and assignment numbers cannot be invented.

## Task 4: Public service and path tests (B4/B5)

Implemented `operator_turn` dispatch through the real harness, preservation of action
lines and waiting threads, scope recovery from durable route events, and status updates
based on saved reports/pending records. Model completion alone becomes `unfinished`,
not `done`. A status question without prior session selection requires explicit IDs.
Unplanned batches stop on a pending question or non-success terminal reason. Planned
batches delegate to B6. Outside replies and approvals remain Milestone 2 operations.

Evidence: 12 new service tests; the never-stops harness test reaches `step_limit`
after 12 model calls and fails the effects check, as intended. Standard/status/decline
workflow dispatch uses substitutes for the team-owned stubs. Published standard
workflow signature verified read-only; no teammate source was merged or modified.
