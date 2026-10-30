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

## Known dependencies

- The referenced milestone handout is absent; exact gate definitions and the five plan-test requirements remain unverified.
- Claudea must supply the standard-workflow callable interface.
- Myron must supply argument-validating fakes and the registry pre-call hook interface.
- These dependencies do not prevent the first fixture checkpoint.
