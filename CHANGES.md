# Changes

**Final submission maintenance (2026-11-01):** synchronized main with the team's
latest critique fixes, reduced M1 to approximately 1,800 prose words while retaining
all 19 tables, and narrowed claims about unseen facts and arbitrary email prose.
Malformed API keys now fail locally with an actionable, credential-free message;
the local UI's 400 error was traced to an invisible character in its process key.
The live smoke check also exposed repeated contact-name placeholders; standard
email instructions now request a generic greeting when no personal name is supplied.
Demo defaults remain synthetic, with explicit local contact overrides and matching
manifest/ZIP generation. Historical baseline/pass records and scores are unchanged.
The final submission tag is advanced to include these fixes; Canvas submission is
tracked separately in `docs/submission.md`.

**UI demo and email charts (2026-11-01, after the M1 tag):** Added nine synthetic
CSV scenarios, expected database figures, a downloadable bundle and an additive,
repeatable UI installer. Personal demo overrides can use supplied university emails;
repository defaults and official fixtures stay synthetic. Manual and pending report emails include
request-scoped PNG charts, frozen at simulated send time and displayed in Threads.
Self-contained `.eml` downloads preserve edited text and embed chart images without
sending. Historical emails retain their original contents. Added Pillow and tests
for fixture totals, preserved state, MIME exports, chart scope and frozen images.
Live mailbox delivery is not configured; these changes do not constitute a new
measured pass or alter the historical M1 results.

**Submission documentation (2026-11-01):** Completed the decision and action-grid
explanations, clarified the limited scope of critique, updated Abraham's handoff,
and added Claudea's Claude disclosure. Shortened the main report and preserved
supporting specimens and individual failure diagnoses in
`docs/milestones/M1-evidence.md`. The simulated email channel remains unchanged.

## Milestone 2

**Myron — Pass 2 switch (2026-11-22):** Added `tools.send_after_draft` (off), Pass 2. With it on, `draft_report_email`'s description tells the model to call `send_report_email` next with the draft's `pending_id` when the operator asked for the email to be sent, instead of leaving it "for the operator to review and send". The send's approval gate, every other definition, schema and switch are unchanged; off keeps the measured `m2-build` text. Added `tests/test_send_after_draft.py`. The prediction is in `experiments/LEDGER.md`; results are pending.

**Myron — Pass 3 switch (2026-11-22):** Added `tools.computed_figures` (off), Pass 3. With it on, the registry's `save_report` call replaces `total_revenue`, `total_units` and, for a comparison, `previous_period`, `previous_total_revenue` and `revenue_change` with values computed from the sales database for the request's own distributor, before the call reaches the MCP server (`agent/tools.py`: `computed_figures`, wired in `build()`). Other figures, the definitions, schemas, validation and the write's key are unchanged; off stores the caller's figures as built. Pass 2's verdict is recorded in the ledger: `tools.send_after_draft` stays off. Added `tests/test_computed_figures.py`. The prediction is in `experiments/LEDGER.md`.

**Myron — Pass 3 verdict (2026-11-22):** `tools.computed_figures` is now `"on"` in `switches.yaml` (ledger, Pass 3: drafts held on a figures field 9 → 0 of 36, passes 20 → 25 of 36, tokens per run −7.1%). `tests/test_computed_figures.py` now pins off (caller's figures stored) and the default on. `tests/test_report_validation_regressions.py`'s `MissingComparison` case now runs with `tools.computed_figures=off`, its assertions unchanged: with the switch on, code fills the dropped comparison, so that saved report is no longer corrupt; the on side is pinned in `tests/test_computed_figures.py`.

**Final-pass write-up (2026-11-22):** Filled the Part 4 build-run table from `results/m2-build/` (16 failing runs, first failure and trace line each); the decision table's checkpoint, durability and memory cells for the four use-case rows, plus a row per pass switch; `## The team` and `## AI assistance`; the remaining placeholders (memory rate, the `unsettled_write` wiring, Part 1's pass note, the person-answered cells stated as not recorded). Replaced the "measured build pending" notes in M2.md and README.md with the measured runs and how to reproduce each pass's arms. *Limited:* no session answered by a person was recorded, so no human approval rate or seconds are claimed. *Removed:* the setup skeleton note at the top of M2.md. *Reused:* no assignment code.

**Submission topology (2026-11-22):** Preserved the integrated analyst/writer experiment on `m2-split` at `m2-split-final`. The submission main contains only single-agent execution and refuses old split checkpoints with a pointer to that preserved revision. No matched-budget improvement is claimed.

**Operator control follow-up (2026-11-22):** Model-authored programs retain the approval requirement for questions, even when their text matches a fixed template. Nested approvals and stops suspend the program; resume executes only the saved inner call, without recomputing earlier reads or writes. A successful question establishes an outside wait before later effects. Added the console's `/answer <run number> <text>` route for held escalations, with session ownership, exact hold matching and execution serialization. Answers are committed with hold release and a durable continuation; corrected instructions reach the agent before pending effects, including automatic questions. Fixed workflows require explicit retry or discard. Completed Abraham's current-code report sections and prepared the measured-build and human-review runbook; those measurements remain pending because the API key was unavailable.

**Integration fixes (2026-11-22):** All four Milestone 2 branches are included in `main`, preserving strict-tool settings and `topology=single`. Replaced stale tool fixtures with real MCP calls and corrected approval waits. Context now admits individual operator records within its existing budget. Interrupted runs resume through the shared service entry with queued operator messages preserved. Tool calls checkpoint exact prepared arguments; plan replay skips already completed critique. All executors share exact-key write settlement, one retry after confirmed absence, and a durable operator hold for unknown outcomes. Delivery receipts bind a send to its actual channel message. Recovery now kills the MCP server and driver after a committed write, then checks fresh-process recovery across eleven tasks. Local implementation plans are ignored and untracked. Historical failing baseline and current verification are recorded in `docs/milestones/M2-integration-evidence.json`; no measured topology benefit is claimed.

**Abraham (2026-11-20):** Added durable outside waits and first-reply handling, a fixed disclosed units-column question, exact pending-call replay, context budgets, notes and searchable session history, compaction, persistent session token accounting, stop/cancel/resume/rollback commands, bounded mid-task messages and plan-side approval/recovery. Thread status comes from checkpoints. Added restart, second-thread, malformed-return, independent-check and long-session fixtures; updated failure analysis for control events. The experimental analyst/writer split remains on `abraham-split`, with single-agent behavior retained here. Corrected the shared run-key lookup to honor its active resume scope, and initialized a genuine waiting run in the approval-delegation contract test. Myron's disclosure-test caller correction is included.

Removed pass-through context/control stubs. Limited current requests to the input budget, queues to eight messages, templates to code-owned text and outside answers to untrusted data. Real MCP/send, approvals and compensation integration remains T2/T2c work. No assignment code was copied; A2/A6 results are cited from the team's existing assignment reference file. The harness and existing M1 measured evidence are unchanged.

Each owner adds their own bullets here: what it added, what it removed, what it limited (such as a tool's
reach), and a line for any assignment or course code reused (which assignment, whose repository).

**Abraham, split experiment (2026-11-21):** Added a read-only analyst and artifact writer for batch reports on `abraham-split`, with validated returns, observed call ledgers, run-specific effect keys, a shared task budget and a combined sandbox check. Saved model responses, pending actions and operator additions survive stop/resume. The combined check rechecks persisted drafts, reports, chart values and SVGs. Twenty-one fake-model tests include all eight official tasks and the review regressions. The switch defaults to single; no live-model benefit is claimed. No assignment code was copied.

**Setup (claudea, 2026-11-20):** the shared contracts of `PLAN_M2.md` section 3, so the three branches can be
built without waiting on each other. Added `agent/runs.py` (run keys, the one resume entry),
`agent/checkpoints.py` and `sandbox/control.py` (a durable SQLite store for checkpoints, the journal, waits, run
numbers, stop flags and stated limits; reset with the sandbox, kept by `make serve`), `policy/` (`flags.py`,
`rules.py` working; `hook.py`, `limits.py` and `autonomy.yaml` as stubs for myron), `agent/disclosure.py` (the
disclosure line, checked by the hook), `agent/compensations.py` (the one undo table for rollback; a stub for claudea), approval at the plan (`approvals.put_up_plan`, `plan_covers`), and documented stubs for `memory`, `context`, `notes`, `approvals`,
`escalation`, `outside`, `stop`, `messages` and `code_calls`. Inserted pass-through seams into `agent/loop.py`,
`agent/workflows.py`, `agent/critique.py`, `agent/service.py`, `agent/registry.py` (the hook's allow/ask/deny,
the journal read only while resuming, `compensate`) and `agent/tools.py` (every registry gets the policy hook);
a minimal `loop.resume_from`. New trace event names in `agent/events.py`. Every task check now also fails an
agent message without the disclosure line (`checks/helpers.requires_disclosure`), adding the measure only when it
is not zero, so Milestone 1's results are unchanged. New switches, each `added: 2026-11-20`, with provisional
settings; the flat `notes` switch became the `notes` group. Fakes for the new contracts in `tests/fakes.py` and
their pinning tests in `tests/test_m2_contracts.py`. Assignment 2 (Part G), 4, 5 and 6 numbers from claudea's
repositories in `docs/assignment_refs.md`. Milestone 1 behaviour is unchanged: the 384 existing tests pass.

**Tools, MCP, policy, approvals and escalation (myron, 2026-11-20, branch `myron-m2`):**
- *Added*:
  - `mcp_server/`, a stateless MCP server on the official SDK (`mcp==2.3.0`, revision 2026-07-28), started
    by the registry as a child process. Every tool call now reaches it through the registry, with its
    context in `_meta`.
  - Four tools (`ask_stranger`, `send_report_email`, `search_tools`, `run_program`).
  - Deferred loading behind `tools.loading` (set `all`).
  - Code calls behind `code_calls.batch_reports` (set `off`), run as `python -I` under an audit hook.
  - The three-column policy (`policy/autonomy.yaml`), the hook (`policy/hook.py`) and stated limits as rules
    (`policy/limits.py`, `rules.matches`).
  - The approval gate with computed screens, the decision log and approval at the plan
    (`agent/approvals.py`).
  - The durable queue store and queue page (`sandbox/queue.py`, `queue.html`, `approvals.html`).
  - The escalation's packet, hold, timeout and daily cap (`agent/escalation.py`).
  - Three test tasks with checks (`approval_send_report`, `approval_send_declined`,
    `escalation_conflicting_figure`).
  - `experiments/analysis/m2.py` (analyze.py's Milestone 2 numbers), `scripts/strict_request.py`,
    `definition_cost.py --milestone 2`, and ledger drafts in `docs/drafts/`.
  - Strict switches for the four new tools (`added: 2026-11-20`).
- *Limited*:
  - `send_report_email` sends only a draft of the request's own contact, and only after approval.
  - A send to anyone else, another distributor's sales and margins are prohibited.
  - `ask_stranger` writes only on the request's own thread, and asks for approval when the model wrote the
    text.
  - Programs reach nothing but the registry.
- *Removed*: nothing.
- *Changed tests*: `tests/test_tools.py` and `tests/test_registry.py` (myron's own) now pin the eight-tool
  surface of PLAN_M2.md 3.4 instead of M1's six.

**claudea's build (2026-11-21, C1 to C10):** *Added:* the checkpoint placement rule and durability mode per kind
of run (`agent/checkpoints.py`), a journal of finished steps so a resume reuses them, the workflow resume
(`workflows.resume`, `runs.crashed`), the three exits for a write whose outcome is unknown (`agent/exits.py`),
compensations for rollback (`agent/compensations.py`, `sandbox/reports.withdraw`, `sandbox/charts.delete`) and
compensate-in-reverse on a permanent failure, the recovery test (`tests/test_recovery.py`, kill -9 during the last
write of every task that writes), the memory store and its write policy (`sandbox/memory.py`, `agent/memory.py`),
the later session's read, the test task `memory_subject_preference` and its check, and the disclosure tests.
*Changed:* `domain_workflows` now ends its runs through `runs.end`; the standard report's email subject takes a
remembered prefix; `memory.preferences` and `memory.standing_rules` are on. *Limited:* memory keeps only what the
operator states; nothing from the outside channel is stored. *Reused:* no assignment code; the kill-during-a-write
test follows the design of claudea's Assignment 4 `--die-during-step` (`claudea24/agentic-ai-assignment4`).

## Milestone 1

**Post-measurement audit fixes (2026-11-01, items 1–6):** report checks and the
email critic now require finite named revenue/file/comparison figures, validate
explicit revenue assertions against their periods, and preserve the operator's
comparison requirement. Discarded or sent drafts cannot satisfy a pending-effect
check. Planned recipients are bound to each request's trusted contact before
execution and remain bound through email revisions. Reactive chart identity uses
labels and numeric values, so changed data produces a new chart and a changed
title alone does not duplicate it. Operator sends atomically claim a draft before
delivery; ambiguous failures remain inspectable, and old sends cannot close newer
work. Regression tests cover these failures and valid end-to-end flows.

Failure analysis resolves Windows paths and relocated checkouts. The new
`python -m experiments.analysis.recompute` command regenerates six derived evidence
artifacts; `--check` verifies their source integrity and freshness without writing.
It separates rejected proposals from terminal rejection, initial-task false finishes
from later status endings, and malformed schemas from trace-annotated semantic
argument errors; it also computes target-only metrics and arm differences. Hashes
normalize CRLF to LF while retaining the original hashes and line-ending provenance.
These are ordinary fixes after measurement: raw runs/traces, historical scores,
the prospective prediction and the negative Pass 1 retention verdict are unchanged.
No new live-model performance measurement is claimed.

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

**Fixes after the baseline:** analysis corrections and the switchable Pass 1
example below; no additional model-facing fix was mixed into the measured arms.

**Post-baseline analysis corrections (ordinary fixes, not Pass 1):** repeated-call
hashes now include request scope from recorded outputs, so two distributors'
identical quarter queries are not falsely treated as repeats. Routing scores
only the initial work against a task's use_case; normal later status turns are
not misroutes. The original analyzer reported 3 repeat-containing runs and 12
misroutes on baseline; corrected counts are recomputed from the unchanged
records. UTF-8/portable task paths and optional JSON summary output support
recomputation on another machine. Both pass arms use this same analyzer.

**Pass 1 implementation:** `examples.save_report` now controls one illustrative
argument example that separates file_total_units from database total_units and
total_revenue. Example numbers are synthetic and do not contain a task answer.
With the switch off the model-visible definitions match the baseline. The fix
changes only this description; Registry schemas, prompts, checks and budgets
were held constant between the two measured arms. Per Myron's instruction at
measurement time, both pass arms ran on clean `myron` while main was held.

**Pass 1 result (2026-10-31):** prediction was pushed as `2e18da0` before both
fresh arms ran on that identical clean commit. Off passed 15/18; on 14/18;
the target messy-file task passed 3/3 in both. The predeclared retention rule
therefore rejects activation: `examples.save_report` stays off. Mean tokens/run
were 3,668.33 off and 3,589.72 on, but fewer batch steps completed on, so this
is not a successful-work efficiency benefit. All 36 records/traces, recomputed
summary, integrity audit and seven failed-run diagnoses are retained. Batch
placeholder recipients and comparison figure omissions remain limitations.
Analyzer endpoint false-finish counts include completed status follow-ups after
held work; the report distinguishes these from initial task-turn false finishes.
The experiment and its result were initially kept on `myron`; later integration
into main does not alter those historical runs or the prospective prediction.

**Main integration (2026-10-31):** merged Myron's completed Pass 1 into main
after Claudea's `54a159c`. The analyzer keeps request-scoped repeat identities,
explicit scored-route counts, first-turn unrouted detection, per-run and
per-critiqued-run denominators, unique bounded-run counts and complete-sweep f.
Regenerated baseline/pass summaries with this combined analyzer; raw records,
traces, prediction and treatment setting are unchanged. Claudea's stricter
report checks and pending-record discard/send updates remain in the merged
code. Historical verdicts describe the checks at their recorded commits and
were not re-scored using these later checks.

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

**claudea — audit fixes after the baseline (2026-10-31, `54a159c`; the baseline ran on `71b13b9`):** the report checks (`checks/common.py`)
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

**claudea — UI check fixes (2026-11-01, after the baseline and the pass; no run record changed):** a live
console turn on SYN-thread-2002 held four correct comparison drafts. `sandbox/report_validation.py` read "Q3
2026" as quarter plus a 2026 revenue amount, read a change ("a decrease in revenue of 1,377.90", "a decrease of
1,377.90 in revenue") as a revenue total, and flipped the expected direction of a change noun ("showing a
decrease") when the sentence first named the previous quarter; a list line under a "Previous Period:
2026Q2" heading now belongs to that quarter. The critique (`agent/critique.py`) now holds a
draft with an unfilled template slot, as the sent "Dear [Distributor's Contact]," was. The demo contacts in
`sandbox/seed.py`, `scripts/prepare_ui_demo.py` and `demo-data/` are synthetic `.example` addresses again
(`43aa53a` had set team members' real addresses). Tests in `tests/test_report_validation_regressions.py`.

**claudea — chat console and email prompt (2026-11-01, after the baseline and the pass; no run record changed):** the console
is a chat page (`app/templates/console.html`, `_history.html`): suggested prompts for the open requests, and under
each reply a card per request it names, read from `sandbox/` (`product.request_cards`), with the latest report's
figures, its chart and its drafts with Send and Discard (the same `/pending/<id>` routes). The routes and the one
path through `harness.turns` are unchanged. The standard-report email prompt (`agent/workflows.py`) opens with
"Hello," and forbids placeholders (myron's wording in `6ff57f5` kept at the merge): given no contact name,
gpt-4o-mini wrote "Dear [Distributor's Contact]," which the new placeholder check held on both rounds (1 of 1 live
run before the change, 0 of 3 after). Runs after this prompt change are not comparable with the baseline's email
drafts.
The menu leads with the milestone's pages (Requests, the product page; Ask the analyst, the console; Explore data;
Run traces), each with a tooltip; Threads, Queue and Approvals sit under "More". The Requests page shows the
distributor names, counts, the three steps, the drafts with Review/Send/Discard, and an "Ask the analyst" button
per request that opens a chat with "Handle <id>." in the message box, sent only when the operator sends it.
Explore data (`/query`) shows no data until the operator presses Show, then the totals, the previous quarter and the change as tiles, quarter arrows, and a
change column per product. Run traces lists runs with pass/fail badges and arm, task and failed-only filters, and
chat sessions by their first message; a run's page shows its check result and a filterable timeline, a readable
line per trace line (numbered as in the `.trace.jsonl` file) with the full line under it.
M1.md Part 1 again names the core task's six use cases and the console, and states the approval line as a
ranking with the line drawn and the trifecta; the build table's console row names the chat page; the AI line
names `app/templates/`. Part 1 (user and success check, test tasks, sandbox, console and product page) and the
critique section were restored to fuller prose from `e121df6`, updated to the current code. From the same commit,
with each fact rechecked against the code: the reasoning-effort reason, the planner's two development sweeps, the
most-called tool counts and their source, the strict-mode source and read date, what the definition tokens bought,
the exact key formula, and where the key is checked (with what could change between the read and the write).
Parts 1 to 3 and the team come to about 2,255 words, against the handout's "about 2,000".

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
