# Milestone 2 integration fixes

Date: 2026-11-22 (America/Chicago). Status: contributions merged; integration fixes remain.

This is the fix breakdown for the combined `main`, not a claim that the milestone is ready to submit.
The merged sources are `claudea-m2` at `9bf4d24`, `myron-m2` at `3ec926c`, `abraham-m2` at `853ba13`,
and `abraham-split` at `0d940dc`. Myron's commit was already on remote `main` before this merge.
The split implementation is now included in `main`; `topology=single` remains the default. This changes
the original plan's branch arrangement, not its decision to keep single-agent execution by default.

Only documentation and the appended switch groups conflicted. Both owners' additions were retained.
The final test results and failing test names are recorded in `docs/milestones/M2-integration-evidence.json`.
All verification uses fake models and synthetic state. No measured build arm, performance claim, or final tag
is established by this merge.

## Work order and ownership

Priorities describe impact; order follows dependencies. The first fixture fixes remove misleading failures
without relaxing production behavior. Context and recovery work can proceed independently after that.

| ID | Priority | Owner | Work | Depends on |
|---|---|---|---|---|
| F1 | P2 | Abraham | Replace the setup-only outside tool fixture with real MCP; correct the model-question approval expectation | — |
| F2 | P2 | Myron | Give the approval delegation fixture a real durable wait | — |
| F3 | P1 | Abraham | Pack retrieved history within the context budget without dropping every relevant fact | — |
| F4 | P1 | Abraham | Resume crashed runs even when another run in the session is waiting | — |
| F5 | P1 | Abraham; Claudea for shared recovery code | Mark prepared calls consistently and preserve exact arguments on replay | — |
| F6 | P1 | Abraham + Claudea; Myron for send evidence | Apply the three exits to uncertain agent writes, including irreversible sends | F5 |
| F7 | P1 | Claudea + Myron; Abraham integrates | Move recovery fault injection to the actual MCP write boundary | — |
| F8 | P1 | Abraham, with task owners | Expand the recovery matrix and replay complete task scripts | F1, F3–F7 |
| F9 | P2 | Abraham, with Myron's task fixtures | Update the split task matrix for the full merged task set and real tools | F1, F3 |

### F1 — Outside fixtures and approval expectation

Files: `tests/fixtures/outside_m2.py`, `tests/test_outside.py`, and its uses in `tests/test_split.py`.

The fixture adds `ask_stranger` to a registry that now already supplies it through MCP. Remove the obsolete
`build`/`install` wrapper, retaining the fake `OutsideModel`. Use `agent.tools.build` in both in-process tests
and the embedded restart subprocess. Do not bypass the real registry, policy hook or channel.

The model-written-question test must first assert `awaiting_approval` and zero sent questions, then approve
through the service and assert the outside wait. Code-owned fixed templates continue without that approval.

Acceptance: `python -m unittest tests.test_outside -v` passes using the real MCP path. The independent
outside check still sees one disclosed question before the answer, one report, 800 clarified file units,
and the authoritative database revenue. Stopped duplicate answers and process restart remain covered.

### F2 — Approval delegation fixture

File: `tests/test_approval.py`, `GateTest.test_decide_approval_resumes_the_run_through_the_one_resume_entry`.

The test obtains an approval from the registry without recording the executor's wait. Supply
`checkpoints.set_wait(run_key, "approval", approval_id)` for the live run before deciding. Keep the service's
stale/withdrawn/wrong-run checks. A read-only probe already confirms one resume with that wait present.

Acceptance: `python -m unittest tests.test_approval tests.test_m2_contracts -v` passes; real approval restart
and duplicate/stale-decision regressions still pass. No policy change is needed for this fixture.

### F3 — Retrieved history under the real tool-definition budget

File: `agent/context.py`, `_extras` and the optional-context admission loop; tests in `tests/test_context.py`.

Reproduced on the fourth long-session report: the prompt uses 15,296 estimated tokens, and its history
block adds 747, reaching 16,043 against the 16,000 limit. The whole block is dropped, so the report stores
`campaign_code=UNRESOLVED`. The fact remains in durable history. The two added tool definitions account
for 258 more tokens than the pre-merge catalogue.

Admit history records individually, prioritizing relevant stable instructions and their corrections.
Preserve provenance and source IDs in omissions. Do not hard-code the campaign value, enlarge the budget,
truncate the current operator request, or weaken the sandbox check. A focused replay with the earliest
history record fits at 15,500 and recovers the fact; this is a diagnostic, not the complete implementation.

Acceptance: `python -m unittest tests.test_context -v` returns 4/4 campaign facts and the correct final answer
with all real tool definitions. Every request remains within 16,000 estimated input tokens; malformed/missing
final answers still fail their negative tests. Add a correction case so preserving an old fact cannot defeat
a later operator correction.

### F4 — The operator's crashed-run continuation

File: `agent/service.py`, `operator_turn`; regressions in the existing service/control tests.

Use `runs.crashed(session)` with the active-session and stop guards, and resume with `{"kind": "crash"}`.
Keep `continue_run` as the execution-ownership and queue-draining wrapper around `runs.resume`.
The current one-live-run heuristic misses a crashed run when another run has an outside wait: a probe
identified the crashed key but the operator's continuation was queued and no resume occurred.

Acceptance: cover one crashed run, a crashed run beside a waiting run, an actively executing run, a stopped
run, and a cancelled run. Only the eligible crashed run resumes; existing waits are preserved; completed
effects are not repeated. Preserve the operator's incoming work according to the existing queue/add rules.

### F5 — Prepared-call marks and exact replay

Files: `agent/loop.py`, `agent/plan.py`; checkpoint/recovery regressions.

Loop persistence already saves post-critique `prepared_call` arguments and restores pending calls. Add
`checkpoints.before_step` metadata for each prepared tool call: agent path, tool, exact args, current step
and request/run identity. Keep the existing pending-call state and pairing of tool calls with results.

Plan persistence also already exists. Its restored `pending_call.args` currently goes through email critique
again. First add a regression that stops after preparation and proves whether replay re-enters critique;
then skip preparation for an already prepared call. Preserve argument authorization and the original key.
This plan issue was identified by code inspection; it was not separately crash-reproduced in the trial.

Acceptance: replay sends the exact persisted args, makes no additional preparation/model call, and creates
one effect. Checkpoint/trace metadata names the actual tool step. Existing stop and approval tests pass.

### F6 — Three exits for unknown outcomes

Files: `agent/exits.py`, `agent/loop.py`, `agent/plan.py`; audit the included `agent/split.py` path too.
Myron owns transport/tool evidence for `ask_stranger` and `send_report_email`.

The workflow uses `exits.settle`; the reactive loop sends uncertain errors back to the model, and the plan
ends `plan_rejected`. Before dropping a pending call, handle the shared contract: confirmed effect means
continue with its original result; confirmed absence permits one retry with the same call/key; inability
to tell produces durable `escalation.signal(run_key, "unsettled_write", ...)` and a hold.

The shared `exits.WRITES` omits the two new sends. Extend evidence carefully: an earlier session artifact
does not prove this run's effect. Use exact keyed write/channel/package evidence; `sending`/`send_failed`
alone must not justify a blind retry or a false success. Preserve stop precedence and record recovered effects.

Acceptance: inject happened/absent/unknown outcomes on each executor path. Assert one effect after a
confirmed result, at most one same-key retry after absence, and no later write plus an inspectable escalation
when unknown. Include a lost MCP response after an irreversible send.

### F7 — Crash injection at the real process boundary

Files: `tests/recovery_child.py`, `tests/test_recovery.py`, test-launched MCP transport/server support.
Keep `harness/`, `channel/` and `run.py` unchanged.

All five existing cases fail because the driver monkeypatches its own sandbox module, while actual writes
run in the MCP child. Inject after the selected write commits inside that child, before returning the result
and before registry journaling. Stop the driver at that boundary too. Killing only MCP tests ambiguous-return
handling while the executor is still running, which is a different test.

Acceptance: each existing recovery case really exits from SIGKILL at the intended boundary. A fresh process
uses the same durable state and run ID, passes the task's independent check, and adds no duplicate effect
or repeated completed call. Record before/crashed/resumed state separately.

### F8 — T2c recovery coverage and script progress

Files: `tests/test_recovery.py`, `tests/recovery_child.py`, task-specific fixtures; evidence tables in
`docs/milestones/M2.md` and M1's recovery evidence after the tests actually run.

Remove the stale warning that plan.py has no checkpoints. Add these six cases to the existing five:

| Task | Targeted last write / required outcome |
|---|---|
| `batch_reports_two` | Second request's draft; two reports, two drafts, two charts |
| `outside_units` | Report after the answer; one ordered question/answer, clarified units |
| `approval_send_report` | Approved send; exactly one channel message and sent draft |
| `approval_send_declined` | Draft before rejection; rejection recorded, no sent message |
| `escalation_conflicting_figure` | Deterministic correction/hold path; exact effects and escalation state |
| `sessions/long_campaign` | Fourth report's draft; four campaign facts and correct final status answer |

Each case needs a fake backend, precise tool/request/occurrence target, and durable script progress/replies.
The current driver plays only the first operator turn and assumes one pending row after any crash. Preserve
the runner's event order for outside replies and approvals, and carry on the remaining turns after recovery.
The long-session checker requires all five operator replies. Do not replace a real crash with a fabricated state.

Acceptance: all eleven cases pass their task checks and exact effect counts after a real crash. Recovery traces
show no repeated completed calls; the report contains measured before/crashed/resumed rows from those runs.

### F9 — Split task matrix on the merged catalogue

File: `tests/test_split.py`, `SplitTaskMatrixTest`, and task-specific fake backends.

Remove the obsolete outside installer from the matrix. Choose backends appropriate to approved sends,
declined sends, escalation, outside replies, memory and the long session. Only batch reports should enter
the split executor; the other tasks still exercise their normal paths under the split configuration.
Retain role-surface, return-ledger, budget, stop/replay, and persisted-artifact-tampering assertions.

Acceptance: `python -m unittest tests.test_split -v` and every current official task pass on real MCP within
the existing task/session ceilings. No performance benefit is claimed. Keep `topology=single` unless a later
matched-budget experiment satisfies the decision record.

## Already present; do not rebuild

- Confirmed operator/system memory enters context with provenance. The long-session failure is retrieved
  history admission, not missing cross-session memory. Repeated memory reads/logging are optional cleanup,
  not an established blocker.
- Plan outputs and prepared arguments are persisted; the recovery-list comment claiming otherwise is stale.
- The fixed outside template, process restart, stopped first-answer retention, and the real model-question
  approval path passed isolated probes on the combined three-owner tree.

## Completion evidence

Run targeted tests while fixing each item, then `make test` and `make check` on the final combined commit.
Do not skip failing tests, relax disclosure/approval rules, or report the old branch-only numbers as a passing
merged build. Finish the real recovery matrix before updating the recovery tables. Live-model passes,
human approval timing, final rubric review and submission tags remain the separate PLAN_M2 deliverables.
