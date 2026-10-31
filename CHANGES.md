# Changes

## Milestone 1

**Myron — live development corrections (2026-10-31, before baseline):** the first
real sweep passed 3/6 tasks. Batch proposals repeatedly omitted write outcomes;
the planner now explicitly requires expect on every step and includes a complete
scoped five-step example. Comparison/messy-file runs omitted figure fields,
mixed file units with database facts and supplied an incorrect delimiter. The
reactive prompt and parser/report descriptions now spell out autodetection,
separate file totals, scalar authoritative current totals and previous-quarter
fields. These ordinary pre-baseline corrections are not the measured pass.

**Myron — Part 3 bad-argument probe (2026-10-31):** added a free `BadArgs` model,
a fixture outside the official task set, and an independent check of six rejected
calls and zero sandbox writes. The real service/loop returns the errors to the
fake model; the existing email gate rejects the malformed email before Registry.
`M1.md` cites each saved `tool_call` trace line under `results/_free/`. These
records demonstrate error plumbing only, not live-model quality or baseline
performance. Regression tests run in scratch state.

**Added:** (scaffold) SQLite sandbox for a sales database, uploads, requests, reports and pending
records (`sandbox/`); seed and demo data; product pages (requests, request, query); agent stubs
(`agent/router.py`, `bounds.py`, `registry.py`, `tools.py`, `workflows.py`, `loop.py`); switch groups;
test task `standard_report_clean` with its check and tests.
- (claudea) Sandbox: `sandbox/charts.py` (keyed SVG charts, a `charts` table), report and request helpers, seed
  `history:` for work already done. Five more test tasks and a dev task, one check each (`checks/common.py` holds
  the shared reads) with their tests. The critique loop (`agent/critique.py`), the `standard_report` workflow
  (`agent/workflows.py`), `status_question` and `out_of_scope` (`agent/domain_workflows.py`). Product page: charts,
  the change from last quarter, a form to email a report by hand. `experiments/analysis/analyze.py`. End reasons
  `tool_error` and `unknown_layout` in `agent/events.py`.

**Removed:** `tasks/example.yaml`, `checks/example.py`.

**Limited:** the agent has no send tool; the emailed report is a pending record the operator sends.
`sandbox/margins.py` is imported by no tool.
- (claudea) The hand email form always sends to the request's own contact (no free recipient). The
  `standard_report` workflow refuses a file that is not the known layout (`unknown_layout`) rather than guess.

**Fixes after the baseline:** none yet.

**Reused code/design:** no assignment source was copied. Stable canonical
write keys and short protocol errors adapt the design from Myron Liu's
`MyronLiu999/agentic-ai-assignment3`, commit
`eb6b35703b212474b561099ec265c427174c7a4b`; A1/A2 provide cited measurements.

**Myron — pre-baseline records and documentation (2026-10-31):** Registry now
preserves complete result/error envelopes in traces while keeping a short
summary. Analysis reads structured error kinds and legacy error-type metadata,
rather than guessing classes from prose; UTF-8 record loading is explicit.
Part 3 now contains the unified action/tool table, per-tool examples/strict
decisions, key/read-back inventory and clearly labeled scripted error evidence.
Stale switch descriptions were corrected without changing settings. Critique's
A2 citation is filled; live plan/failure specimens and project measurements
remain dependent on actual API runs.

**claudea — audit fixes (2026-10-31, before the baseline):** the report checks (`checks/common.py`)
read `figures.total_revenue` and `figures.period` themselves, where before the true revenue anywhere in the
report passed (a report with `total_revenue: 1` passed); the pending email must state the true revenue and
point at the last report saved. Sending a pending report email from the product page now marks the request
done, as the hand email form does. `analyze.py`: critique rounds per run divide by every run (rounds per run
with a critique is kept beside it), runs ended at a bound count once per run, and `f` counts only tasks both arms
ran in all three sweeps. Each fix has a test that fails on the old code.
A pending email or question can now be discarded from the request page (`POST /pending/<id>/discard`,
`pending.discard`; a sent record cannot be), the undo path the action table names; the table's undo column
now names only what the build does.
`checks/standard_report.py` uses the same shared rules as the other report checks (it had its own, which passed
an email with a wrong amount); a report task's email must state the true revenue (two of Abraham's tests'
planted emails now do). `analyze.py` scores a misroute on a run's first route only: a follow-up turn routes to
`status_question` by design; a first turn the router declined is counted as unrouted, apart from misroutes.

**Abraham — milestone audit fixes (2026-10-31, before the baseline):** accepted the
official batch command and relative report follow-ups without widening request scope;
comparison follow-ups read the saved difference. Reactive calls now use effect-based
write keys and separate `trace_step` attribution, with exact-repeat events. Planning
receives only IDs/counts and trusted instructions; code resolves scoped request fields,
sanitizes checkpoint feedback, preserves completed prefixes and enforces listed order.
Unused non-checkpoint outputs are rejected; the scripted batch consumes file counts
and chart IDs in its saved figures. Corrected the four-gate economics, documented
assumptions and added the step-size illustration and official-task scenario mapping.
Verified 278 routine tests, four structural checks and ten manual integration probes;
all model responses were free/scripted. Independent review found a one-new-request
batch-qualifier fallback, corrected with a failing-then-passing regression. Live tuning,
a live planner specimen and the official first-failure rows still require team run evidence.

**Abraham — main integration (2026-10-31):** merged the agent core with the domain
and tools already on main. Resolved the milestone write-up conflict by preserving
each owner's completed sections. Production code merged unchanged. Verified 250
routine tests, four structural checks, ten integration probes, and three real-registry
workflow task checks, all with free scripted models.

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

**Abraham — citations and compatibility evidence:** located Myron's completed A1/A2
references on `origin/myron` and verified the immutable report JSON, A1 metric
definitions, and model settings directly in his repositories. Filled Abraham's M1
cost/success/latency and planning-result citations, with dates, run counts, and
explicit separation from project measurements. Added a manual, free-model integration
probe and reproducible snapshot instructions. Six probes pass after the two fixes;
two contract probes still fail (six call-shape mismatches and one parser row-shape
mismatch). The handoff now identifies the tool owner actions, absent local API key,
and still-missing handout. No teammate code, shared model setting, or official run
record was changed or merged.

**Abraham — named status integration:** status questions now resolve exact distributor
names/IDs and quarter/year references against trusted metadata before dispatching
to the existing status workflow. Ambiguous years, duplicate requests, unmatched names,
and unresolved alternative/conjoined references ask for explicit request IDs. Generic
follow-ups reuse the latest resolved selection, including status-only sessions after
restart. Added routing regressions and manual real-domain probes: the published
status task now answers the seeded report revenue without writes, and a follow-up
keeps its request scope. Teammate tool-contract and analysis-module conflicts remain
separate integration dependencies.
