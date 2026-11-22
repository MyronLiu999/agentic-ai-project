# 0006: Keep one agent for the sales analyst

Owner: Abraham. Decision date: 2026-11-20. Status: single agent by default. The experimental split code is
included in `main` at the 2026-11-22 integration; the merged task matrix still needs the fixes recorded in
`docs/superpowers/plans/2026-11-22-m2-integration.md`. No matched-budget benefit has been established.

## What would have to cross between components?

The components considered are file decoder (D), sales querier (Q), report writer (W), reviewer (R),
and independent per-distributor batch workers (B). A frozen request ID, period and contact may be
passed at dispatch; the table distinguishes that from information needed while work is running.

| Pair | Information needed mid-task | How it would cross; consequence |
|---|---|---|
| D–Q | Neither needs the other's data to read an upload or the scoped sales table | Independent reads after dispatch; a coordinator combines them |
| D–W | Column mapping, units, row counts and corrections when interpretation fails | Structured handoff plus another decoder call if missing; a lossy return loses evidence |
| D–R | Whether figures attributed to the upload actually came from its parsed rows | Reviewer reads the same immutable upload; otherwise another handoff is required |
| D–B | A batch worker needs its own file interpretation before it can finish | Own-request handoff; splitting adds another context for a short read |
| Q–W | Current/previous totals and period; a discrepancy may need a second query | Structured facts through the coordinator, then a correction round if needed |
| Q–R | Authoritative totals and request scope to reject invented figures | Reviewer recomputes directly from the sandbox; no need to ask the query agent |
| Q–B | Each worker needs its distributor's totals | Scoped read result; a separate agent adds no new capability |
| W–R | Draft, check failures and revised draft | Repeated correction rounds; keep the code critic beside the writer |
| W–B | Each worker needs its own report/draft and IDs | Request-owned effects; do not share write authority between workers |
| R–B | Each worker needs a verified output before completion | Code checks the sandbox per request and again for the combined batch |
| B₁–B₂ | None for different requests, distributors and artifact namespaces | No messages or shared mutable records; duplicate request IDs must be refused |

```mermaid
flowchart LR
  D[File decoder] -->|Columns and file units| W[Report writer]
  Q[Sales querier] -->|Period and authoritative totals| W
  W -->|Draft| R[Code reviewer]
  R -->|Failed checks and revisions| W
  D -->|Upload evidence| R
  Q -->|Sandbox facts| R
  C[Coordinator] -->|Request scope| B1[Distributor worker 1]
  C -->|Different request scope| B2[Distributor worker 2]
  B1 -->|Verified return| E[Combined sandbox check]
  B2 -->|Verified return| E
```

## Gates, in order

Stop at the first failure; a later gate is not claimed to pass by default.

| Candidate component | Gate 1: little mid-task communication | Gate 2: independently checkable | Gate 3: cheaper capability unavailable to one agent | Gate 4: worth multiplier | Verdict |
|---|---|---|---|---|---|
| File decoder separated from writer | No for ambiguous columns: writer depends on interpretation and clarification before choosing its next step | Not reached | Not reached | Not reached | Keep together |
| Sales querier | Yes: request ID and period bind a read | Yes: recompute `sales.distributor_sales` | No: `query_sales` is already one bounded tool call; a separate model adds no parallel work | Not reached | Keep as a tool |
| Report writer separated from reviewer | No: check/revise cycles exchange the draft and failures | Not reached | Not reached | Not reached | Keep the code critic |
| Reviewer as another model | No for the same correction cycle | Not reached | Not reached | Not reached | Deterministic recomputation is cheaper and independently grounded |
| Per-distributor batch workers | Yes only for disjoint request IDs and artifacts | Yes: check each report/draft against its request, upload and sales rows | No demonstrated need: `tasks/batch_reports_two.yaml` has two short chains that the existing plan executor handles | Not reached | Single pending evidence |
| Read-only analyst → artifact writer experiment | No in the general case: an ambiguous upload or a discrepancy needs another analyst/writer correction round; the branch only proceeds with a frozen validated handoff | Not reached | Not reached | Not reached | Build the closest candidate on the branch, do not merge |

The experiment's two roles have different **tool surfaces**: analyst gets `parse_file` and `query_sales`;
writer gets `render_chart`, `save_report` and `draft_report_email` for the selected request. The coordinator
owns the handoff and the combined end-state check. A prompt-only second reviewer would duplicate one model's
errors without an independent oracle, so it is rejected.

## Benefit and condition

The plausible benefit is context isolation: the writer receives checked facts instead of every upload row
and unsuccessful parse. It requires a compact return that carries all necessary evidence and IDs. What the
return cannot express is lost; it must explicitly report omitted searches and facts not determined. There
is no parallelism claim for the dependent analyst → writer chain. Distributor workers could save elapsed
time only on a larger batch of disjoint requests run concurrently; that is a different measured condition.

One agent can often obtain the same context benefit from a bounded tool result, notes, compaction and the
queryable session log. Splitting loses easy correction of an interpretation and adds coordination, return
validation and a shared-budget mechanism. Not splitting loses potential parallelism on a sufficiently
large independent batch and separately bounded contexts.

## Assignment evidence and spend check

Source: `docs/assignment_refs.md`, Assignment 6, read 2026-11-20, copied by claudea from
[claudea24/agentic-ai-assignment6](https://github.com/claudea24/agentic-ai-assignment6) commit
`7013cb1ea4e3f9ba4ecea84fdabd97f81015135f`, `reports/LAB_06.md`, `LAB_06.json`, and
`results/runs_06.jsonl`. Model: `gemini-3.5-flash-lite`, not this project's `gpt-4o-mini`.
There were 72 runs, 24 per arm (18 single and 6 batch, three sweeps). These were the third measurements
after two split stopping-rule changes; the source records discarded earlier runs.

| Kind | Split/single mean-token multiplier | Original single | Split | Matched arm | Actual spend match |
|---|---|---|---|---|---|
| Single tasks | 0.70 (38,218 / 54,918) | 12/18 passed | 15/18 | 11/18 | Matched arm spent 28% less than split |
| Batches | 0.51 (182,138 / 357,222) | 4/6 passed | 0/6 | 1/6 | Matched arm spent 17% less than split |

The split did not spend more in either kind. Higher spend improved the single-agent batch result, but
the purported matched arm was not matched in actual spend. A single-task comparison within ±10% was
not measured. The numbers justify caution and the source's single-agent decision; they do not predict
a gain for this sales domain or establish equal-budget superiority here.

No published multi-agent performance claim is relied on for this decision. The lecture's reported
15×-chat multiplier is not used as a measurement of this project.

## Branch evidence and reopening condition

The branch must include a JSON-schema-validated return for every role, searched/not-searched fields and
spend computed from calls, one trace with parent IDs, a sandbox check of the combined end state, and one
150,000-token task allowance shared by all roles and the coordinator. A malformed return is rejected;
planted divergent state must fail even when each local result says success. No role waits on another:
the coordinator sequences them. Workers cannot write the same request; request scope is unique and every
write remains keyed in the common registry, with the run key in its logical identity. The combined checker uses captured per-run writer outputs rather than session-wide stamps; each claimed ID must appear in that writer’s successful ledger. Its chart contract is one current-revenue bar, and both stored values and the rendered SVG must match.

Build evidence: `tests/test_split.py` on `abraham-split`, 21 tests passing on 2026-11-21. The matrix runs all eight current official task files through their sandbox checks with `topology=split`; only batch reports use the split. The seven ordinary tasks stay within 150,000 tokens; the four-task long session uses its 400,000-token session ceiling. Focused tests cover malformed returns, boolean record IDs, role surfaces, observed spend, shared-budget exhaustion, exact action approvals, and stopped-write resume. Regression cases verify durable paid responses and final returns (including critique), rejection of writer IDs absent from its successful ledger, independent effects for consecutive console runs, restoration of a mismatched approval wait, persisted subject/report/chart/SVG validation, and operator additions surviving role transitions and the mailbox-consumption crash window. These are free-model correctness tests, not a timing or quality comparison. At the team merge the branch
will be based on the real policy, checkpoint and MCP implementations, then tested/tagged as `m2-split-final`
by the assigned review steps. No current-build matched-budget pass has been run.

Reopen only with at least eight independent distributor requests whose selected inputs exceed one
configured context budget, with a per-request sandbox oracle and a combined check. Run single and split
on identical tasks, model, tools and evaluator, three sweeps, at the same enforced total task allowance.
Report actual tokens, success per sweep and wall-clock time. Merge only if the gates pass, every safety
test passes, actual spend is comparable (predeclare ±10%), and the split improves checked success or
reduces median latency by at least 20% without lowering checked success. These thresholds are a proposed
decision rule, not a measured result.
