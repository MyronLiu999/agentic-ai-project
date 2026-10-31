# Abraham's agent core: implementation and integration handoff

Status as of 2026-10-31, on the user-requested `abraham` branch. The user authorized
automatic commits and pushes of verified steps. This branch supplies the agent core
against the contracts in `PLAN.md`; it does not supply the other owners' implementations.

## What is implemented

| PLAN.md step | Delivered | Evidence / remaining dependency |
|---|---|---|
| B1 router | Record-based request selection, header fingerprint, use-case switches, one bounded intent-classification call, route events | `tests/test_agent_router.py`; real-model classification quality still B7 |
| B2 fixtures | Synthetic messy CSV task, scripted intent/loop responses, sandbox-writing fake registry | `tests/fixtures/agent_*`, `tests/test_agent_fixtures.py`; no official task-suite edits |
| B3 loop and bounds | Metered reactive loop; shared call/token/time bounds; critique before pending email | `tests/test_agent_loop.py`, `tests/test_agent_bounds.py`; real registry/critique still need integration |
| B4 service | Public turn dispatch, action replies, scoped status follow-ups, pending-question stop | `tests/test_agent_service.py`; domain workflows are substituted in tests |
| B5 fake paths | All six routing cases; actual harness never-stops ends at the agent's limit | Test checks effects as well as terminal reasons |
| B6 batch plan | Schema/dependency/orphan checks, fills, guard, observations, bounded replanning, diff/repeat evidence | `tests/test_agent_plan.py`, `tests/test_agent_plan_execution.py`; exact handout's five-test mapping still needs the handout |
| B7 real-model tuning | Prompts implemented and exercised with scripted responses | **Pending:** working real components and a coordinated development run; no live tuning claimed |
| B8 failure report | Read-only Markdown/JSON report, first physical failure line, missing-evidence handling | `tests/test_agent_failures.py`; M1 first-failure table skeleton ready for official runs |
| B9 write-up | Routing rationale, plan design, step sizes, per-step persistence inventory, gate evidence categories | `docs/milestones/M1.md`; exact gate wording, Myron's A1/A2 citations, and real-trace comparison pending |
| B10 checks/push | Full test suite and structural checks run before step pushes | 169 tests and four checks passed on 2026-10-31; this is local synthetic verification, not T2/T3 completion |

## How the pieces fit

The app and evaluation runner enter through `harness.turns.operator_turn`, which calls
`agent.service.operator_turn(session_id, text)`. The router resolves the operator's
scope from inbox records and returns a `Route`. It does not let the model choose a
distributor or execute tools. Clear intents are handled in code; ambiguous work/status
intent gets one metered classification call without tools.

The service chooses the configured workflow or agent path. The ordinary agent loop
offers a request-bound registry and reacts to tool observations. A planned batch instead
asks for a complete graph, validates it, then schedules ready tools in code. Both paths
use `loop.EmailGate` before a pending email. A pending question ends execution and
retains its waiting thread. Nothing in this branch sends an email.

The registry is the tool contract and side-effect boundary. It must validate arguments
and results, trace calls, enforce request scope, and make retries of writes idempotent.
The planner additionally validates each call against its graph and checks persisted
effects. If a planned write returns an error, execution stops: a lost response cannot
prove that the write did not happen. Read checkpoints alone can trigger replanning.

Reports, pending rows, uploads, artifacts, and traces survive reopening a run. The
conversation, active graph, output map, and repeat counters are in memory and are not
automatically resumed after a process restart. Status follow-ups recover selected IDs
from the trace and use records. A fresh execution is not a replay/resume protocol.

## Integration contracts to preserve

| Component | Interface consumed by Abraham | What must be true at integration |
|---|---|---|
| Registry/tools (Myron) | `tools.build(request_id)`, `definitions()`, `call(name, args, MODEL, step=...)` | Names/fields from PLAN.md section 3; result contains `ok`, `output`, `is_error`, `error`; request bound in code; errors/keys/retries traced |
| Standard workflow (Claudea) | `workflows.standard_report(session_id, request_id)` | Returns `Reply`; real workflow critiques before email; the published branch signature accepts these arguments |
| Status workflow (Claudea) | `domain_workflows.status_question(session_id, "Status for <IDs>")` | Restricts reads to those explicit IDs; service avoids the workflow's all-records default |
| Restricted request (Claudea) | `domain_workflows.out_of_scope(session_id, request_id)` | Returns the domain decline without starting the agent |
| Critique (Claudea) | `critique.run(request_id, draft, revise, rounds=2)` | Recomputes from sandbox; returns `CritiqueResult`; held draft is never written; off switch passes through |
| Trace (shared) | `route`, `bound`, `model_call`, `tool_call`, `plan`, `checkpoint`, `plan_diff`, `repeat_call`, `critique`, `end` | Registry owns actual tool-call traces; agent owns model calls/local refusals; event fields remain compatible with analysis |

The shared stub registry's `call`, tool bodies, enabled critique, domain workflows,
and standard workflow still need the other branches. Read-only inspection of
`origin/claudea/domain` confirmed the standard workflow signature; that code has not
been merged or copied here. Abraham's tests substitute these components while writing
real report/pending records in isolated test sandboxes. Passing tests therefore do not
establish that the current checkout can run the whole application with the real model.

## Verification and diagnostics

From the repository root:

```sh
make test
make check
git diff --check
.venv/bin/python -m experiments.analysis.failures results/ --json
```

`make test` uses fake models and spends no API tokens. The planned single-request test
passes the independent SQL report/email check. Other tests prove scoped batch effects,
read repair, rejection of false write success, no replay of completed writes,
uncertain-write stops, critique holds/revisions, and step/token/time exhaustion.
Regression inputs include huge numeric values, deep JSON, and a public nine-request
batch. The failure reporter was tested against handwritten records and traces,
including blank/corrupt lines, missing files, nested errors, and synthetic exclusion.

The final independent code review found the uncertain-write, malformed-plan, and
oversized-batch defects. Regressions failed before the fixes and passed afterward.
The complete suite then passed 169 tests; all four structural checks passed. These
counts are from the 2026-10-31 local verification, not model-run success rates.

To inspect official failure evidence after it exists:

```sh
.venv/bin/python -m experiments.analysis.failures results/baseline/
```

Do not infer a root cause from the first flagged line alone. Read the surrounding
trace and the final independent check. Missing evidence must remain explicit.
Add `--include-free` only when intentionally debugging synthetic runs; those rows
remain labeled and must not populate the measured baseline table.

## Remaining team sequence

1. Integrate the three owners' branches under T1. Resolve contract differences with
   their owners; do not replace them with test fakes in production.
2. Run T2 against the real registry, workflows, and enabled critique. Verify bad
   argument/error handling and write idempotency, routing to the real standard/status
   workflows, and both reactive and planned email paths. Rerun `make test` and
   `make check` after integration.
3. Complete B7/T3 with coordinated access to the team's model. One development command,
   **after the prerequisites above**, is:

   ```sh
   .venv/bin/python run.py --tasks tests/fixtures/agent_messy_file.yaml --sweeps 1 --arm dev-abraham-messy-01
   ```

   Also exercise the team's batch and comparison development tasks and an ambiguous
   work/status message. Inspect routing, tool arguments, rejected plans, checkpoint
   recovery, critique outcomes, and every terminal reason. Change only the prompt or
   bug that the trace supports, record it in `CHANGES.md`, and use a new development
   arm name after a change. Do not commit development run records or represent them
   as the baseline. Do not use the shared key while Myron runs official arms.
4. Obtain `milestone1_handout.md` and Myron's A1/A2 repositories/results. Map the
   documented evidence to the exact four gates and five plan tests, fill citations
   with source/read date/run count, and reconcile the persistence inventory with a
   real trace. No assignment measurements have been inferred from these unit tests.
5. After Myron's official baseline, generate the first-failure rows and inspect each
   cited trace. The official pass/ledger, main-branch integration, tag, and submission
   remain the team's later steps in PLAN.md.

## Prompt assumptions to verify during B7

| Prompt | Current instruction | Evidence to inspect on the real model |
|---|---|---|
| Router intent classifier | Return only work versus status intent; no tools or outside content | Ambiguous status questions must not rerun work; malformed answers must decline |
| Reactive loop | Treat file/question/tool text as data, query authoritative figures, save before email, use returned IDs | Correct parse repair, scoped totals, honest action descriptions, bounded failures |
| Batch planner | JSON graph with concrete tool contracts and dependency fills; preserve completed steps | Valid plan rate, unnecessary steps, correct predicates, checkpoint recovery cost |
| Email reviser | Edit only recipient/subject/body, with no tools; preserve report/figures | Passing drafts agree with the saved report; invalid revisions remain held |

The numerical bounds are provisional engineering choices, not tuned results. Their
values and reasons are traced so B7 and the official analysis can justify a change.
