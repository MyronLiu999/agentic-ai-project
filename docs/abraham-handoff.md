# Abraham's agent core: implementation and integration handoff

Status as of 2026-10-31, on the user-requested `abraham` branch. The user authorized
automatic commits and pushes of verified steps. This branch supplies the agent core
against the contracts in `PLAN.md`; it does not supply the other owners' implementations.

## Open note: is the missing material required for Abraham's part?

**Yes for completing the milestone write-up and checking it against the course
requirements; it does not block implementing or testing the agent core.**
The user requested that this dependency be recorded here on 2026-10-31.

| Required input | Why Abraham needs it | Current status / completion action |
|---|---|---|
| `../milestone1_handout.md` | B9 requires the four gates for `messy_file` and `standard_report`; B6 also references five plan tests whose exact definitions need verification | Obtain the handout from the team's course materials, then map the existing write-up and tests to its exact requirements |
| Myron's A1 measurements and repository/commit | Support the gate assessment with cost, success, latency, and tool-sequence evidence | Located on `origin/myron` at `4ab3d29`; raw report and format definitions verified on 2026-10-31; cost/success/latency citations now filled in Part 1 |
| Myron's A2 results and repository/commit | Support Part 2's planning/checkpoint discussion | Raw report verified on 2026-10-31; planning/checkpoint results now cited in Part 2 |

Abraham does **not** need to redo Myron's assignments. B9 explicitly permits A1
placeholders during individual work; T6 requires the team to fill the placeholders
before submission. The A1/A2 sources have now been located and cited; the missing
handout still prevents confirming the exact four-gate assessment and five-plan-test mapping.
Real-model prompt tuning (B7) is a separate outstanding task with its own integration
dependencies, described below.

## What is implemented

| PLAN.md step | Delivered | Evidence / remaining dependency |
|---|---|---|
| B1 router | Record-based request selection, named distributor/period status resolution, header fingerprint, use-case switches, one bounded intent-classification call, route events | `tests/test_agent_router.py`, `tests/test_agent_status_routing.py`; real-model classification quality still B7 |
| B2 fixtures | Synthetic messy CSV task, scripted intent/loop responses, sandbox-writing fake registry | `tests/fixtures/agent_*`, `tests/test_agent_fixtures.py`; no official task-suite edits |
| B3 loop and bounds | Metered reactive loop; shared call/token/time bounds; critique before pending email | `tests/test_agent_loop.py`, `tests/test_agent_bounds.py`; published real critique passes focused snapshot probes; full integration still needs compatible tools |
| B4 service | Public turn dispatch, action replies, scoped status follow-ups, pending-question stop | `tests/test_agent_service.py`; domain workflows are substituted in tests |
| B5 fake paths | All six routing cases; actual harness never-stops ends at the agent's limit | Test checks effects as well as terminal reasons |
| B6 batch plan | Schema/dependency/orphan checks, fills, guard, observations, bounded replanning, diff/repeat evidence | `tests/test_agent_plan.py`, `tests/test_agent_plan_execution.py`; exact handout's five-test mapping still needs the handout |
| B7 real-model tuning | Prompts implemented and exercised with scripted responses | **Pending:** reconcile published tool contracts, integrate components, and configure an API key for a coordinated run; no live tuning claimed |
| B8 failure report | Read-only Markdown/JSON report, first physical failure line, missing-evidence handling | `tests/test_agent_failures.py`; M1 first-failure table skeleton ready for official runs |
| B9 write-up | Routing rationale, A1/A2 citations, plan design, step sizes, per-step persistence inventory, gate evidence categories | `docs/milestones/M1.md`; exact gate wording and project real-model trace comparison pending |
| B10 checks/push | Full test suite and structural checks run before step pushes | 184 tests and four checks passed after the integration fixes on 2026-10-31; this is local synthetic verification, not T2/T3 completion |

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
automatically resumed after a process restart. Status questions resolve exact distributor
names/IDs (case-insensitive) and optional quarter/year references to a unique request.
A bare quarter must be unique across years; duplicate requests need explicit IDs.
Recognized generic follow-ups recover the latest selected IDs from the trace, including
status-only selections. Unrecognized named references must not reuse earlier scope;
unresolved alternatives/conjunctions ask for explicit IDs. This intentionally requires
clarification for unsupported phrasing. A fresh execution is not a replay/resume protocol.

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
and standard workflow still need the other branches. Those implementations exist on
the published branches, but the tool contract differs from PLAN.md; see the compatibility
findings below. Their code was tested in a temporary snapshot and is not merged into
`abraham`. Routine tests use substitutes with real sandbox effects. Neither those
tests nor the focused snapshot probes establish a fully integrated live-model system.

## Published-branch compatibility findings

Snapshot sources, inspected 2026-10-31:

- Abraham code plus fixtures from this branch.
- Claudea `aef4053167e38dab5b08881439702b09af0b132e`: sandbox, tasks/checks,
  workflows, critique, shared event constants.
- Myron `4ab3d29b4a617bc68a88bffd4232f12014c46927`: registry and tool bodies.

The manual probes in `tests/fixtures/agent_integration_probe.py` use scripted models.
Eight focused checks now pass: real critique accepts correct reactive and planned
emails, preserves the execution step limit on both paths, the real status workflow
keeps explicit scope, the real registry keeps two planned charts distinct, the published
named-status task passes its check with zero writes, and its follow-up retains scope
after reopening the session.
The critique/email probes still use sandbox-writing tool substitutes so they can
isolate that integration boundary from the tool-contract failures.

Two contract tests remain failing, with seven failed assertions: all six tools reject
one of their agreed PLAN.md call shapes, and the default parser returns dictionary
rows where the agreed contract and standard workflow expect positional lists.

| Tool | PLAN.md / current callers | Published Myron implementation | Owner action needed |
|---|---|---|---|
| `parse_file` | Optional delimiter/decimal; rows are lists | Accepts no arguments; rows are dictionaries | Restore options and row shape, or agree a coordinated caller/contract change |
| `query_sales` | `period`; flat `total_units` and `total_revenue` | Also requires `metric`; returns nested `totals` | Reconcile input and output shapes |
| `render_chart` | `title`, `labels`, `values`; `chart_id`, `path` | `title`, `period`, `metric`, `series`; `artifact` | Reconcile arguments and artifact output fields |
| `save_report` | `kind`, `figures`, `body`; `report_id` | Also requires top-level `period`; returns `id`; restricts `kind` | Reconcile report schema and identifier field |
| `draft_report_email` | `recipient`, `subject`, `body`, `report_id`; `pending_id` | Rejects `recipient` (binds it internally); returns `id` | Agree the recipient boundary and pending identifier together |
| `draft_clarifying_question` | `question`; `pending_id` | Requires `subject`, `body`; returns `id` | Reconcile question schema and identifier field |

The error envelope also differs: PLAN.md documents `kind/message/retry`; the published
registry returns `type/message/repair/transient/ambiguous`. The agent can detect its
error flags, but the team must align error meanings and write-retry behavior. The
published registry uses `step` as write identity. Planned calls now supply logical
step IDs; reactive model-round IDs and repeated writes still need a shared identity
policy verified during T2. Changing schemas only in Abraham's code would leave the
standard workflow incompatible, so the six-tool reconciliation belongs with Myron
and both callers. These findings are recorded here; no external message was sent.

To reproduce against the pinned implementations, run this from the repository root
after committing the current fixtures. It creates only a temporary directory, keeps
the configured model unchanged, and makes no API calls. Expected current outcome:
ten tests run, eight pass, two contract tests fail (seven failed assertions).

```sh
.venv/bin/python - <<'PY'
import io, subprocess, sys, tarfile, tempfile
from pathlib import Path
snapshot = Path(tempfile.mkdtemp(prefix="abraham-integration-", dir="/tmp"))
def overlay(ref, paths=()):
    data = subprocess.check_output(["git", "archive", ref, *paths])
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        archive.extractall(snapshot, filter="data")
overlay("HEAD")
overlay("aef4053167e38dab5b08881439702b09af0b132e", [
    "sandbox", "checks", "tasks", "agent/critique.py", "agent/domain_workflows.py",
    "agent/workflows.py", "agent/events.py"])
overlay("4ab3d29b4a617bc68a88bffd4232f12014c46927", ["agent/registry.py", "agent/tools.py"])
print(f"Temporary snapshot: {snapshot}", flush=True)
result = subprocess.run([sys.executable, "-m", "unittest",
                         "tests.fixtures.agent_integration_probe"], cwd=snapshot)
sys.exit(result.returncode)
PY
```

Retake these probes against new agreed commits after the tool owner reconciles the
contract; then run all real-component paths before B7. `OPENAI_API_KEY` was checked
for presence only on 2026-10-31 and was absent in this session.

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
The initial complete suite then passed 169 tests. The subsequent critique-limit and
planned-write-identity fixes brought it to 172 passing tests; the named-status and
follow-up fixes brought it to 184. All four structural checks passed. A temporary
full merge still has the pre-existing `tests.test_analysis` import error, seven tool
contract assertion failures, and failing standard-report/decline task checks. The
status task passes. These counts are local verification, not model-run success rates.

To inspect official failure evidence after it exists:

```sh
.venv/bin/python -m experiments.analysis.failures results/baseline/
```

Do not infer a root cause from the first flagged line alone. Read the surrounding
trace and the final independent check. Missing evidence must remain explicit.
Add `--include-free` only when intentionally debugging synthetic runs; those rows
remain labeled and must not populate the measured baseline table.

## Remaining team sequence

1. Resolve the published tool-contract differences above with their owners, then
   integrate the three branches under T1. Do not replace real tools with test fakes
   in production.
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
4. Obtain `milestone1_handout.md`. Myron's A1/A2 reports have now been verified and
   cited with source/read date/run count. Map that evidence to the exact four gates
   and five plan tests, and reconcile the persistence inventory with a real trace.
   No assignment measurements have been inferred from these unit tests.
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
