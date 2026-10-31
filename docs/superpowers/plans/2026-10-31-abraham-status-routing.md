# Abraham status routing Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for this single bug fix, with a fresh code review before committing.

**Goal:** Make the published status task answer from the correct saved request in a fresh session.

**Architecture:** Keep intent classification separate from scope. For status questions without explicit request/thread IDs, resolve an exact distributor name or ID and optional quarter/year against trusted database metadata. Require exactly one request; preserve explicit IDs and generic session follow-ups. Persist resolved status selections through the existing route trace.

**Tech Stack:** Python, SQLite sandbox, unittest, existing free intent model.

**Spec:** PLAN.md B1/B4/B5 and the merge audit's status-task failure: `status_question_done_work` names SYN Acme Trading and Q3, but the current service receives no request IDs. User requested Abraham's fixes first and previously authorized automatic verified commits/pushes.

## Global Constraints

- Work on the existing `abraham` branch; edit only Abraham-owned code, tests and notes.
- Preserve the shared workflow/tool interfaces and the configured model.
- Match metadata only; request questions and uploaded cells cannot select scope.
- Ambiguous, conflicting or unmatched named references require clarification.
- Use no paid API calls; verify the published domain implementation in a temporary snapshot.

## Review Focus

- Same distributor and quarter across years: require a year or request ID.
- Duplicate requests for one period: require a request ID, never choose the newest implicitly.
- Unmatched named requests: do not fall back to the previous session selection.
- Negated/alternative references and partial names: do not widen selection.
- Status-only sessions and restart: reuse the last explicitly resolved selection.

## Task 1: Resolve and retain status references

**Files:** `agent/router.py`, `agent/service.py`, `tests/test_agent_status_routing.py`, `tests/fixtures/agent_integration_probe.py`, `CHANGES.md`, `docs/abraham-handoff.md`.

**Interfaces:** Keep `route_operator_message(session_id, text) -> Route` and `domain_workflows.status_question(session_id, "Status for <IDs>")` unchanged. Read distributor names/IDs and request periods from SQLite. Reuse the existing `route` trace event.

- [x] Add failing routing regressions for the published question, year disambiguation, duplicate/missing matches, exclusions, trusted-data scope, and persisted status selection. Add manual probes for the real task and follow-up.
- [x] Run the new tests before implementation and confirm the expected missing-selection failures.
- [x] Implement status reference resolution and preserve the latest nonempty route selection.
- [x] Run the focused tests, then the actual published status task in a disposable integration snapshot; assert its domain check passes and writes remain zero.
- [x] Run `make test`, `make check`, and `git diff --check`; obtain a fresh review and address substantive findings.
- Finish: update the handoff/changelog, commit `fix(agent): resolve named status requests without widening scope`, and push `abraham` under the user's existing authorization.


## Verification recorded 2026-10-31

- Routine branch: 184 tests and four structural checks passed; `git diff --check` passed.
- Published domain task: saved revenue answered, zero writes; named-status follow-up retained scope after restart.
- Fresh review found unmatched-name fallback and mixed reference selection; public-turn regressions failed before repair and passed afterward. Known generic follow-ups may reuse prior scope; unsupported reference phrasing requests explicit IDs.
- Temporary combined tree: 249 discovered test entries, one pre-existing `tests.test_analysis` import error. Ten manual probes: eight passed; two tool-contract methods still have seven failed assertions. Standard-report and decline tasks still fail against incompatible published tools; status passes.
- Scope: no teammate implementation, shared model, public tool/workflow interface, or official result changed.
