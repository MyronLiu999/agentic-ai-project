# Milestone 1: supplementary evidence

Detailed supporting examples moved from the main report; see [M1](M1.md) for
the current decisions, critique limitations and results. These historical
sections preserve their original wording and trace citations; the main report
supersedes any earlier wording that overstates what critique can verify.

Additional [measurement notes](M1-method-notes.md) retain the pinned A1 source,
development-repair chronology and semantic argument-counting rules.


**Scripted step-size illustration, not a live planner result.**
`tests/fixtures/agent_milestone_model.py` supplies a hand-authored proposal for
`tasks/batch_reports_two.yaml`; `tests/test_agent_official_flows.py` executes it through
the real registry, critic and independent task check. `r0_` and `r1_` identify the first
and second selected request. Each saved report includes the parsed row count and chart ID,
as well as the scoped query's period, revenue and units.

| Step in the scripted proposal | What success/failure tells us | What removing it breaks |
|---|---|---|
| `r0_parse` | A structured, untruncated file was read; a failed read checkpoint permits bounded repair | The first report's `file_row_count` binding cannot resolve |
| `r0_query` | The selected request's quarter totals match the sandbox; a failed read checkpoint permits repair | The first chart value and saved figures cannot resolve |
| `r0_chart` | The returned chart path exists inside this run; failed/uncertain writing halts | The first report's `chart_id` binding cannot resolve |
| `r0_save` | The report row exists with matching request and figures; a success claim without that row fails | The first email has no saved `report_id` to bind |
| `r0_email` | The critic passes the draft and the pending row links to the saved report; a hold writes nothing | The first request lacks its pending email deliverable |
| `r1_parse` | The second file passes the same structured/untruncated read check, or requests bounded repair | The second report's `file_row_count` binding cannot resolve |
| `r1_query` | The second request's scoped totals match the sandbox, or its read checkpoint fails | The second chart value and saved figures cannot resolve |
| `r1_chart` | The second chart has an observed artifact, or execution halts on an uncertain write | The second report's `chart_id` binding cannot resolve |
| `r1_save` | The second request has its own verified report row; the first request's row cannot satisfy it | The second email's `report_id` cannot resolve |
| `r1_email` | A verified pending email completes the second request; a hold leaves it unfinished | The second request lacks its pending email deliverable |

The review changed the scripted proposal to consume parse/chart outputs; merely adding
`depends_on` edges had not shown that the final report needed them. The planner prompt
now requires downstream use, and validation rejects unused non-checkpoint artifacts.
This makes the fixture's deletion test meaningful; the separate live assessment
above applies the same test to an actual model-produced proposal.


### Scripted bad-argument trace evidence (owner: myron)

On 2026-10-31, `tests.fixtures.tool_bad_args_model:BadArgs` submitted one malformed
call for each of the six model-visible tools through `run.py`, the real service,
router, agent loop and tool boundary. It then checked the six error-result blocks
returned to the model before ending its turn. The independent check also read
the sandbox: no reports, charts or pending records were written with this run's
stamp, and no agent message was sent on the outside channel.

Run ID: `tool-bad-args-step3-tool_bad_arguments-s01-39e388`.
The record and trace are under `results/_free/tool-bad-args-step3/`; the trace is
`results/_free/tool-bad-args-step3/tool-bad-args-step3-tool_bad_arguments-s01-39e388.trace.jsonl`.
Physical trace lines below identify each `tool_call`; line 6 records the fake
model's six requests, and line 13 records its acknowledgement after checking
all six error responses.

| Tool | Deliberately wrong input | Repair fact returned to the model | Rejecting component | Trace line |
|---|---|---|---|---|
| `parse_file` | `delimiter: "??"` | Lists the accepted delimiter values | Registry | 7 |
| `query_sales` | `period: "third quarter"` | Requires a quarter such as `2026Q3` | Registry | 8 |
| `render_chart` | `values: ["not a number"]` | Values must be numbers | Registry | 9 |
| `save_report` | Empty `figures` | Requires `figures.period` and `figures.total_revenue` | Registry | 10 |
| `draft_report_email` | Only `subject` supplied | Requires recipient, subject, body and integer report ID | Loop's existing email gate, before Registry | 11 |
| `draft_clarifying_question` | `question: 42` | Question must be a string | Registry | 12 |

Every call has `is_error: true`; the five Registry rejections preserve the full
error/repair envelope, and the email gate returns its required-field message.
The analyzer counts six tool errors and six protocol rejections. This is a
negative-test pass, not a successful sales-report task. All six inputs were
intentionally scripted examples of **right tool, wrong arguments**. They do not
replace the separate live-model development failure table. `free: true` and
`dirty: true` in the record explicitly identify a local scripted test of
uncommitted probe additions, not baseline or measured-pass evidence; its token
counts are synthetic.

Reproduce it with the existing runner (a free backend; no API key required):

```sh
python run.py --tasks tests/fixtures/tool_bad_arguments.yaml --sweeps 1 --arm tool-bad-args-step3 --backend tests.fixtures.tool_bad_args_model:BadArgs
python experiments/analysis/analyze.py results/_free/tool-bad-args-step3 --json
```

`tests/test_tool_bad_args_probe.py` exercises this route in scratch state and
checks that a completion claim without the six calls fails the independent check.


### Measured-pass failures (owner: myron)

All 36 pass records and traces were reviewed; seven failed. For the five batch
failures, the ten-step plan's deliverables are appropriate, completed prefix
effects are not repeated, and any orphan chart proposal is rejected and repaired
before execution. The substantive remaining defect is an unbound literal
example recipient. Critique blocks that email, then stops the shared batch plan,
so the second request's otherwise appropriate chain is skipped. The second
request is missing because of that stop, not because it needed no report. This
is separate from the tested save_report description and needs a new pass.

| Run ID | First explicit signal / substantive failure | Trace path : physical line | Final result |
|---|---|---|---|
| pass1-examples-off-batch_reports_two-s01-b4d71f | Orphan chart proposal rejected and repaired; recipient@example.com survives the email revision | `results/pass1-examples-off/pass1-examples-off-batch_reports_two-s01-b4d71f.trace.jsonl:7`; critique :26/:28; skipped :29–34 | critique_held then status done; first email and second request unfinished |
| pass1-examples-off-batch_reports_two-s02-b6501f | Orphan chart proposal rejected and repaired; same literal recipient survives revision | `results/pass1-examples-off/pass1-examples-off-batch_reports_two-s02-b6501f.trace.jsonl:7`; critique :26/:28; skipped :29–34 | critique_held then status done; same missing effects |
| pass1-examples-off-compare_check_last_quarter-s01-8c0d0a | Correct current query ignored: save figures use zero revenue/units; email revision cannot repair saved figures | `results/pass1-examples-off/pass1-examples-off-compare_check_last_quarter-s01-8c0d0a.trace.jsonl:13` query; :15 save; :18/:20 critique | critique_held then status done; wrong report and no email, later status claims wrong direction |
| pass1-examples-on-batch_reports_two-s01-e6bbc7 | Valid plan uses literal example recipient; critique revision leaves it unchanged | `results/pass1-examples-on/pass1-examples-on-batch_reports_two-s01-e6bbc7.trace.jsonl:24`/:26; skipped :27–32 | critique_held then status done; first email and second request unfinished |
| pass1-examples-on-batch_reports_two-s02-32f1cf | Orphan chart proposal rejected and repaired; same literal recipient survives revision | `results/pass1-examples-on/pass1-examples-on-batch_reports_two-s02-32f1cf.trace.jsonl:7`; critique :26/:28; skipped :29–34 | critique_held then status done; same missing effects |
| pass1-examples-on-batch_reports_two-s03-5ed0c7 | Valid plan uses literal example recipient; revision leaves it unchanged | `results/pass1-examples-on/pass1-examples-on-batch_reports_two-s03-5ed0c7.trace.jsonl:24`/:26; skipped :27–32 | critique_held then status done; same missing effects |
| pass1-examples-on-compare_check_last_quarter-s03-83ec59 | Previous-quarter query is correct but saved figures omit previous revenue; narrower email critic passes | `results/pass1-examples-on/pass1-examples-on-compare_check_last_quarter-s03-83ec59.trace.jsonl:12` query; :17 save; :20 critique; :30 failed check | done then status done; true task-turn false finish and critique miss |

Baseline and pass numbers were recomputed by Myron using Claudea's analyzer
with the documented analysis corrections. `pass1_summary.json` contains all
per-run metrics; `pass1_audit.json` supplies task-turn interpretation without
changing the raw traces or the analyzer's endpoint metric.


## Detailed supporting context

**Gate 4 working.** We borrow A1's workflow cost as the provisional project estimate
`c=$0.000595960/run` and its multiplier `m=3.34194`, keeping the unrounded ratio in the
arithmetic. Neither has been measured on this project's configured `gpt-4o-mini`.
The extra cost is `c*(m-1)=$0.001395700` per case; the cost per extra correct case is
`c*(m-1)/f`, compared with the user's wrong-case cost `W`.

For unfamiliar layouts, estimate `f=0.10`: one in ten would need successful adaptive repair
beyond the known-layout workflow. This is an unmeasured domain assumption, motivated by
variable headers and decoding/clarification decisions, not inferred from the fixture mix or
A1's measured `f=0`. For clean layouts estimate `f=0`: more decisions add no needed step.
Use `W=$10.69`, assuming 15 minutes to correct an internal report before sending. The wage
proxy is the BLS May 2025 median for operations research analysts, $42.76/hour
([BLS Occupational Outlook Handbook](https://www.bls.gov/ooh/math/operations-research-analysts.htm),
read 2026-10-31). The occupation proxy and repair time are assumptions; this values labor only,
not leakage or harm after sending, which Gates 2–3 address.

- Messy-file estimate: `$0.001395700/0.10=$0.013957` per extra correct case, below `$10.69`.
- Break-even: `f*=c*(m-1)/W=0.00013056`, or `0.01306%`; the gate passes only when `f>f*`.
  At `f=0.001`, the cost is `$1.3957`; at `f=0.0001`, it is `$13.957`, so the verdict reverses.
  If correction takes only one minute, `W=$0.71267` and `f*=0.19584%`; at one hour,
  `W=$42.76` and `f*=0.003264%`. Higher project cost raises these thresholds proportionally.
- Standard-report estimate: `f=0` gives no extra correct cases, so the ratio has no finite
  value and Gate 4 fails. The A1 sample likewise supplies no measured economic benefit.

For the whole core reporting task, **routing share `r` is distinct from benefit share `f`**.
An illustrative workload estimate `r=0.10` sends 90% of requests through the known-layout
workflow and 10% through the agent. It gives `c*((1-r)+r*m)=$0.000735530/run`, beside
workflow-only `$0.000595960` and all-agent `$0.001991660`. At `r=0.50` the blend is
`$0.001293810`. These scenarios exclude routing overhead and are not observed hybrid costs;
actual routing frequency, correction time, cost and success must come from project runs.

A1's agent median/p95 of 4.953/5.687 seconds is below the handout's roughly ten-second
interactive threshold, but it does not predict this project's latency. If project turns exceed
that threshold, expose progress or choose the workflow where the gates allow it. Repeated
success on the same cases, tool-sequence evidence and the sandbox checks must validate or
reverse these provisional choices; a finite sample cannot establish such a small break-even
benefit precisely. Losses on cases the workflow already passed would further weaken the
agent's value and must be counted in the paired results.


## Detailed supporting context

Planning is enabled for `batch_reports`: the selected requests supply a finite set of report
deliverables, so the model can declare their ordered steps before tools run. The validator uses
the plan to reject missing request deliverables and the diff reveals skipped steps (Lecture 2,
slides 5 and 54). The reactive
`messy_file` path instead chooses its next tools from observations; an initial parse failure can
change the investigation (slide 17). A fixed standard report already has known steps, one of
slide 54's reasons to omit a plan. These choices remain hypotheses to test in this project's
real development sweep.

Myron's A2 supplies a caution about assuming that planning improves outcomes. At commit
`df425ccbbf25814a66234af045a1901852c8e18e`, OpenAI `gpt-4.1-mini` ran 18 cases per configuration
(six issues, three sweeps). The following values come from the
[A2 report JSON](https://github.com/MyronLiu999/agentic-ai-assignment2/blob/df425ccbbf25814a66234af045a1901852c8e18e/reports/LAB_02.json),
read 2026-10-31; they are prior issue-triage evidence, not this project's results.

| A2 configuration | Passes / runs | Mean tokens / run (rounded) | Runs with exact repeats | Median latency |
|---|---|---|---|---|
| Agent | 7/18 | 14,135 | 8/18 | 8.359 s |
| Planned, critique off | 5/18 | 5,280 | 3/18 | 5.270 s |
| Planned, self critique | 3/18 | 4,992 | 1/18 | 5.364 s |
| Planned, external critique | 2/18 | 4,508 | 3/18 | 5.352 s |

Planned/off used 62.6% fewer tokens, computed from the unrounded means, but lost two passes.
The [A2 report discussion](https://github.com/MyronLiu999/agentic-ai-assignment2/blob/df425ccbbf25814a66234af045a1901852c8e18e/reports/LAB_02.md)
(read 2026-10-31) attributes some savings to incomplete execution. Its checkpoint revised after
search found no relevant TypeScript file under `src/`; validation retries and checkpoint revisions
were each capped at one. All 54 planned runs averaged one revision, with maximum one. Its `s49`
specimen still had a failing test while step 6 was skipped and the agent claimed completion;
an aggregate false-finish rate was not measured. The project's separate predicates and sandbox
observations address that distinction between following a plan and finishing the task. They still
need project-local evidence before we claim a benefit.

The planner receives the operator's request, tool contracts, and allowlisted record IDs/counts.
It receives no distributor question, file text, contact address, period or arbitrary inbox
fields. The executor resolves `{"$fill": "request.period"}` and
`{"$fill": "request.contact_email"}` from the selected request at runtime. At a failed read
checkpoint, the reviser sees code-owned status/counts/integer record IDs, not raw tool output
or error text. Both planner inputs are constructed from allowlists; actual outputs remain
available only to the executor.

Each plan step names `id`, `request_id`, `tool`, `args`, `depends_on`, and an observable `expect`.
The latter checks a documented output field with `exists`, `eq`, or numeric `gte`.
`checkpoint: true` permits recovery at a read. Unknown IDs/totals are bindings such as
`{"$fill": "save.report_id"}` or `{"$fill": "query"}`; the binding stays in the plan, while the
checkpoint trace records resolved arguments. Output bindings must name successful ancestors
in the same request; the two `request.*` bindings above are the only metadata exceptions.
For example: query sales → save figures from the query → draft an email linked to
the saved report. The orphan check rejects steps outside the terminal action's dependency
graph. A declared dependency alone does not prove useful data flow; the per-step deletion
test must also ask whether the deliverable actually needs that result.

Validation checks tool/argument shapes, selected scope, unique IDs, cycles, missing or forward
dependencies, binding reachability, and orphan steps before any tool executes. Each request has a read
checkpoint, exactly one terminal email/question, and at most one save. The graph is capped at
eight requests and 48 tool steps; JSON is capped at 64,000 characters and 32 nesting levels.
These are implementation limits read from `agent/plan.py` on 2026-10-31, not measured optima.
The guard authorizes only the next listed step with matching request, tool, and resolved
arguments; independent ready steps cannot be reordered. Dependencies constrain that order;
they do not prove that the model chose the right business logic.

After a call, code checks its predicate and observes its result. Sales are compared with the
scoped sandbox query; reports and pending drafts must exist with matching fields; a chart path
must resolve to a file in the run's state directory. Parse observations require structured,
untruncated output, but do not prove every parsed value is semantically correct. Full domain
correctness remains the tools', critique's, and independent task checks' responsibility.

A failed read checkpoint can request a revised plan. The initial plan and all replacements
share an allowance of three planner attempts total. Completed steps form an immutable prefix,
including their positions; the revised plan may only change the unfinished suffix. Their
outputs remain available to the executor and completed writes are not executed again. A failed or unverified
write stops execution because an effect may already exist. The executor does not automatically
retry that write under changed arguments. A question stops the batch with its waiting thread;
remaining work is recorded as skipped.

`plan` events record accepted and rejected versions. `plan_diff` records executed, skipped,
extra, and out-of-order steps. Both planned and reactive paths hash request, tool, and canonical
arguments and emit `repeat_call` on an exact repeat; planned counts persist across revisions.
Reactive write identity follows the requested effect, not the model round; the trace separately
records the originating round. This lets a repeated identical write reuse its key while remaining
visible as a repeated call. A skipped step on a replaced plan records that version's history;
it does not alone prove the final run failed. A repeat is a diagnostic, not an automatic error:
an intentional read retry can repeat while a changed-argument write may evade a simple hash.
The uncertain-write stop and immutable completed steps handle those write cases.


## Detailed supporting context

The original analyzer falsely counted equal calls on different request scopes
as repeats and status follow-ups as misroutes. This ordinary post-baseline
analysis correction leaves raw records unchanged and is identical in both pass
arms; the corrected hash and first-route rules have regression tests.


## Detailed supporting context

The analyzer's endpoint false-finish metric is 3 off versus 4 on: final
end_reason=done with a failed whole-task check. All three off failures and
three on failures first ended critique_held, then correctly answered a status
follow-up with done. They are not claims that the held reports were completed.
Counting only the initial task turn gives 0 off versus 1 on false finish;
the audit lists both sets explicitly. The on comparison s03 is the genuine
task-turn false finish and critique miss. Boundary rejection on comparison s02
was recovered and passed; it is not one of the seven failed runs below.

The target omission never recurred in either fresh arm, so the predicted gain
was not observed. Overall passes fell by one (5.56 percentage points), while
mean tokens fell 2.14% and mean cost fell 8.93%; fewer completed batch steps
make that aggregate saving unsuitable as evidence of efficiency. Target-only
tokens rose 21.73%. By the unchanged prospective rule, leave the example off.
This small sample does not establish that examples caused the batch difference
or that examples never help. Baseline's 17/18 is historical; it is not reused
as the control. Both arms retain the same control paths, so they do not measure
an agent-versus-workflow cost multiplier m or capability gain f.

Recompute with `python experiments/analysis/analyze.py results/pass1-examples-off results/pass1-examples-on --output experiments/evidence/pass1_summary.json`.
`experiments/evidence/pass1_failures.json` preserves the failure reader's exact
signals; the following diagnosis distinguishes a recovered early signal from
the failure that prevented completion. No additional fix was applied during
measurement. The subsequent main integration retains the original prediction
and raw evidence. Its combined analyzer also distinguishes unrouted first turns
and the two critique denominators. Summary JSON was regenerated with that
analyzer; historical success counts still use the checks at each recorded
commit. Claudea's later stricter checks in `54a159c` were not retroactively
applied to these runs, and no new measured run is claimed for the merged code.


## Detailed supporting context

The 12 development cases are tuning diagnostics, not the official baseline.
`scripts/archive_dev_evidence.py` copied their cited traces verbatim and recorded
hashes/check summaries in `experiments/evidence/development_manifest.json`;
entire `results/dev-*` arms remain local. No observation is invented for an
unseen failure shape. The console's real two-turn report/status interaction is
`traces/s-20261031-155455-4410.jsonl`: tool calls and critique precede the saved
report reply, and the follow-up identifies the pending email (lines 13–18).
It used the actual Console HTTP routes with isolated synthetic state, not a
scripted model; that temporary domain state is not a restart-recovery claim.

A later measured example of right tool/wrong arguments is
`results/pass1-examples-on/pass1-examples-on-compare_check_last_quarter-s02-712c70.trace.jsonl:17`:
the real model called draft_report_email with report_id=0 before saving a
report. The loop returned a structured protocol error without executing the
write; the model subsequently saved a report and the run passed. This is one
observed, recovered boundary rejection, not a final task failure.


## Detailed supporting context

OpenAI's [Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs)
and [function-calling guide](https://developers.openai.com/api/docs/guides/function-calling),
read 2026-10-31, require closed objects and required properties for strict
schemas; optional values can use a required nullable field. Published schema
limits are 5,000 properties, 10 nesting levels, 1,000 enum values and 120,000
characters across schema identifiers/values. Our sole strict schema fits these
limits. The live development calls accepted this query schema; the connectivity
probe confirmed model `gpt-4o-mini-2024-07-18` and tool calling.


## Detailed supporting context

### First observed failures (Abraham)

`experiments/analysis/failures.py` reads run records and their traces without writing either.
Run `.venv/bin/python -m experiments.analysis.failures results/` for Markdown, or append
`--json` for structured output. Select a particular arm's directory to restrict the report.
Synthetic `_free` and discarded runs are excluded unless explicitly requested; included
synthetic rows are labeled. Evidence paths stored relative to the repository can be relocated
with `--repo-root PATH`.

For each failed/unfinished run, the report includes all terminal reasons and the physical,
one-based trace line of the earliest explicit error, failed checkpoint/plan validation,
critique revision/hold, off-plan call, bound, or failed run check. Blank or malformed trace
lines do not change later line numbers. Missing/malformed evidence is listed; if no signal is
available, the report cites the run record and leaves the trace line unset. The earliest
observed failure may have been recovered before a different final failure. It is evidence for
human diagnosis, not a claim about root cause.


## Detailed supporting context

Abraham: Codex implemented the agent core, synthetic fixtures/tests, failure report, and these
sections; scripted tests checked actual sandbox effects and bounds, and a separate code review
produced regression-tested fixes. Subsequent snapshot probes checked published team components
and exposed agent-side integration bugs, fixed with regressions, including named status scope and
restart follow-ups. Verification of the merged tree at `fae559f` on 2026-10-31: 250 routine tests, four structural
checks, all ten manual integration probes, and three real-registry workflow task checks passed.
The earlier tool-contract failures are resolved by Myron's integrated fixes. The current
handoff in `docs/abraham-handoff.md` separates verified implementation from remaining live evidence.
No live-model calls or official project performance estimates are claimed.
The subsequent milestone audit corrections passed 278 routine tests, four structural
checks and ten manual integration probes. Codex also corrected gate calculations and
reviewed batch scope. The later live planner specimen and official baseline are cited above;
those results are distinct from Abraham's scripted verification.


## Detailed supporting context

**The console and the product page.** The console is the starter's page; each message goes to
`agent.service.operator_turn` (abraham), as a task's scripted turns do. The router distinguishes work from status intent and resolves request scope
from stored records; ambiguous intent uses one bounded classification call. The product page (owner: claudea; `app/product.py`) needs no agent: `/` lists the
requests and the pending records waiting to be sent; `/requests/<id>` shows the file, the thread, the saved
reports, charts and pending records, a button to send each pending record as the operator, and a form to **email a
report by hand** (the core task without the agent: the body is prefilled from the database, the recipient is always
the request's contact, and what is sent is recorded as a `manual` pending record marked sent); `/query` shows one
distributor's quarter by product with a chart and the change from last quarter. `tests/test_product.py`.

**The workflows** (owner: claudea). `standard_report` (`agent/workflows.py`) runs six steps in a fixed order: parse,
query, chart, save, draft the email (one model call writes the words around figures code computed) through the
critique, then `draft_report_email`. A file whose header is not a SKU column plus a units column ends the run with
`unknown_layout` instead of a guess, so a misrouted messy file shows in the end reasons. A failed tool ends it with
`tool_error`. `status_question` (`agent/domain_workflows.py`) answers from the records and writes nothing;
`out_of_scope` writes one fixed-template reply declining and offering the distributor's own report, as a pending
record, and ends with `declined`.


## Detailed supporting context

**The check** (`agent/critique.py`, `check(request_id, draft)`) passes or fails with a reason, from the sandbox
alone, never a task's check or expected answer: the recipient equals the request's `contact_email`; `figures.period`
equals the request's period; `figures.total_revenue` (and `previous_total_revenue`, if the draft gives one) equals
the database's within 0.01; the subject or body contains the total; neither mentions margins or literally names another
distributor. **The bound:** `rounds=2` (`agent/workflows.py`, `CRITIQUE_ROUNDS`): the draft is checked, revised once
by the author with the reason, and checked again. Each round writes `critique` with its round, verdict (`pass`,
`revise`, `held`), reason and the fields that changed. A draft still failing is **held**: the caller writes no
pending record, sets the request to `held`, ends the run with `critique_held` and tells the operator why. A reviser
that raises also holds the draft; it never falls back to the old one. The switch `critique.report_email` takes
`off | external`; off passes drafts through untouched.

**Which paths draft the action.** Both: the `standard_report` workflow calls `critique.run` before
`draft_report_email` (tested), and the agent loop calls the same function before it drafts the email
through `EmailGate`. On 2026-10-31, `tests/fixtures/agent_integration_probe.py` passed with the
real critic on both reactive and planned paths; those email probes use scripted models and
sandbox-writing tool substitutes. A separate real-registry standard-report task also passed.

**Where it does not help: the `out_of_scope` decline** (`draft_clarifying_question` with a fixed template in
`agent/domain_workflows.py`). Code writes every word and fills the one fact (the distributor's own name and quarter)
from the request record. A check would read the same record the template did, so the critic knows nothing the
author did not: the second gate fails, and a critique there would only spend a round.

**Tests** (`tests/test_workflows.py`, on fake models, switch on): `check` alone fails each wrong field with its
reason; `run` with a fake reviser revises with the reason and passes on round 2, and holds at the bound with one
revision; through the workflow on a fake model, with `FakeRegistry`'s `draft_report_email` calling `pending.add`, a
right draft is written once (one real pending row, and the task's own check passes), a wrong-then-right draft is
revised and written once, and an always-wrong draft is never written and the run ends `critique_held`.
**Assignment 2's result** (Myron's repository, [MyronLiu999/agentic-ai-assignment2](https://github.com/MyronLiu999/agentic-ai-assignment2),
commit `df425cc`, `reports/LAB_02.json`, `gpt-4.1-mini`, 18 runs per configuration; read 2026-10-31 via
`docs/assignment_refs.md`). With the same bound of two rounds, self and external critique averaged 0.22 and 0.17
rounds per run and changed, fixed, broke or held no draft (0/0/0/0 each), while success went from 5/18 with the
critique off to 3/18 (self) and 2/18 (external). Its external check tested parseability, that the file existed and
had been seen, and label/file agreement: things the author already got right, so the check had nothing to catch.
What it predicts for us: a critique buys something only where the author can be wrong about a fact the critic can
see, which is why ours recomputes the revenue and reads the stored recipient and period. If the baseline's critique
also changes no draft (rounds per run, held drafts and misses from `analyze.py`), slide 43 says switch it off.


## Detailed supporting context

Both agent paths call the shared `EmailGate` before `draft_report_email`. It resolves the saved
report within the selected request and supplies saved figures to critique. Revisions cannot
change the report ID or figures. A passed planned-email revision is recorded as an amended
plan before the changed arguments execute. Held drafts produce no pending email. Critique's
actual sandbox recomputation and its detailed write-up remain claudea's responsibility; the
merged implementation now supplies the real sandbox critic; focused integration probes
exercise it alongside the agent paths, with scripted model responses.


## Detailed supporting context

**Action table and approval line** (owner: claudea; tool extensions: myron).
The unified action/tool table appears once, in Part 3. Reads change nothing;
local charts/reports can be superseded, drafts remain unsent, and operator sends
are irreversible. A trace confirms that a call happened, not that its figures
were correct; sandbox checks and operator review provide that evidence.
The grid decisions are: reads require no undo but need semantic review; charts and
reports are local and superseded by new versions, with correctness checked against
source data; pending drafts can be discarded and require operator review; a sent
message cannot be recalled and therefore requires approval before sending.

**The approval line** sits above the emailed report: local effects can be superseded or discarded and do not leave the sandbox;
the simulated sent message cannot be recalled, so slide 37 puts it below. The agent has no send
tool; the workflows and the loop stop at the pending record, and the operator sends it. No send in our system has
text written by a fixed template that reaches a distributor without the operator.

**Trifecta** (slide 49). Untrusted input: the distributor's message and file. Private data: margins and other
distributors' orders. Way out: the emailed report. All three legs exist, so we cut them in code rather than in the
prompt: (1) the private leg is narrowed at the tools: `query_sales` takes the distributor from the request record
via `tools.build(request_id)`, never from the model [myron], and no tool or workflow imports `sandbox/margins.py`
(tested); (2) the way out has a person on it: the email is a pending record; (3) when enabled, the email critique
rejects literal other-distributor names and margin mentions. It does not catch every possible disclosure. The leg we cannot remove is the analyst's own
judgment when they press send: they see the full text on the request page first.
