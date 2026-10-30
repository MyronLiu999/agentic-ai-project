# Abraham's agent core implementation plan

> Execute this plan inline with the executing-plans and test-driven-development workflows. Stop after each reviewable step: show the changes, verification, and proposed commit message. Commit or push only after the user's explicit approval for that action.

**Goal:** Implement Abraham's responsibilities from PLAN.md in independently reviewable steps.

**Architecture:** Keep the existing service entry point, request-bound registry, sandbox, and harness. Establish controlled inputs first, then implement routing, bounded execution, service integration, and batch planning. Use the shared events and critique contract.

**Tech stack:** Python 3.10+, unittest, YAML, SQLite, existing harness and sandbox.

**Spec:** PLAN.md, sections 3 and 5 (B1–B10), plus the step-by-step breakdown approved in this chat.

## Global constraints

- Work on the user-requested `abraham` branch in this checkout.
- Wait for the user's review after each implementation step; no automatic commits or pushes.
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

Each checkpoint is specified further when its preceding review is accepted. This preserves the user's opportunity to change direction between steps.

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

## Known dependencies

- The referenced milestone handout is absent; exact gate definitions and the five plan-test requirements remain unverified.
- Claudea must supply the standard-workflow callable interface.
- Myron must supply argument-validating fakes and the registry pre-call hook interface.
- These dependencies do not prevent the fixture and routing checkpoints.
