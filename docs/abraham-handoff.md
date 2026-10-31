# Abraham's agent core: implementation and evidence handoff

Status: 2026-10-31. The agent core, domain workflows, sandbox, registry and tools are
integrated on `main`. The earlier six tool-call mismatches and parser row-shape mismatch
are resolved. Their pre-merge diagnosis is preserved in Git history; it is not a current blocker.

## Course requirements and sources

The actual **Project Milestone 1** PDF is available and was read on 2026-10-31. Its course
source is [Canvas](https://canvas.uchicago.edu/courses/75218/assignments/921328).
The absent `../milestone1_handout.md` path in `plan.md` no longer blocks the audit.

- Part 1 task 5, pp. 5–7, defines the four gates: variable next steps, limited damage,
  timely detection/undo or prior human review, and the value of added correct cases.
  M1 now distinguishes `c*(m-1)/f` and break-even `f*=c*(m-1)/W` from routing cost
  `c*((1-r)+r*m)`. Domain `f`, routing share `r` and repair duration are labeled estimates.
- Part 2 task 1, pp. 9–10, requires a planner isolated from outside text, no later-step
  dependencies, execution in listed order, checkpoint-only revision, immutable completed
  steps, repeat detection on both agent paths, five fake-model scenarios, and a step-size
  assessment of **one plan the live planner wrote**.
- Myron's A1/A2 reports and commits are cited in `docs/assignment_refs.md` and M1. They are
  prior issue-triage results, not project measurements. No assignment needs to be rerun.

## Implemented interfaces and boundaries

The app and runner enter through `harness.turns.operator_turn`, then
`agent.service.operator_turn`. The router selects request scope from records and applies
`control.<use_case>`. Clear intent stays in code; ambiguous work/status intent uses one
bounded classification call with no tools or outside file contents. Named status questions
resolve a unique request; generic follow-ups recover selected IDs from the session trace.

The reactive loop uses a request-bound registry and shared call/token/time limits. The
batch planner receives the operator request, tool contracts and allowlisted record IDs/counts.
It receives no stranger questions, file text, period or contact address. The executor resolves
the two allowlisted `request.period` and `request.contact_email` runtime bindings. Replanning
receives code-owned status/counts/integer record IDs, never raw tool output or error messages. The validator
rejects forward dependencies; the executor follows the listed order and preserves the
completed prefix across revisions. Only a failed read checkpoint permits replanning;
an uncertain write stops because its effect may already exist.

Both paths call `loop.EmailGate` before a pending email. The gate fixes the saved report and
figures while the critic/reviser checks the draft; a held draft creates no pending email.
A pending question stops work with its waiting thread. Sending remains an operator action.

Both agent paths emit repeat diagnostics from request/tool/canonical arguments. Reactive
writes use effect identity for idempotency, with model-round origin recorded separately;
planned writes retain their logical step identity. The registry owns actual tool-call traces,
keys and retries. The executor additionally verifies persisted effects. None of these records
alone proves business correctness: independent task checks still read the sandbox.

Domain records and traces survive reopening a run. The tool conversation, active plan,
output map and repeat counters are not resumed automatically after restart. A new work
turn starts a new execution; a status follow-up can read durable records and recover scope.

| `plan.md` step | Evidence / remaining dependency |
|---|---|
| B1 router | `tests/test_agent_router.py`, `tests/test_agent_status_routing.py`; live ambiguous-intent quality still needs B7 |
| B2 fixtures | `tests/fixtures/agent_*`, `tests/test_agent_fixtures.py`; scripted responses, not live-model evidence |
| B3 loop/bounds | `tests/test_agent_loop.py`, `tests/test_agent_bounds.py`, `tests/test_agent_effects.py`; external stops, repeats, real effects and critique integration |
| B4 service | `tests/test_agent_service.py`; scope, effects, waiting questions and status follow-ups |
| B5 fake paths | Per-use-case routing and harness never-stops test; effects and terminal reasons checked |
| B6 plan | `tests/test_agent_plan.py`, `tests/test_agent_plan_execution.py`; all five required scenarios on the official plan-enabled task in `tests/test_agent_batch_scenarios.py`; scripted specimen/full flows in `tests/test_agent_official_flows.py` |
| B7 model tuning | **Pending:** coordinated API access; no live tuning claimed |
| B8 failure report | `tests/test_agent_failures.py`; official first-failure rows await Myron's baseline records/traces |
| B9 write-up | Actual four gates and A1/A2 citations filled; live planner step-size specimen and live-trace inventory comparison remain |
| B10 verification | Routine tests and structural checks are free; rerun after changes before recording completion |

## Verification and evidence limits

The post-audit fixes pass 278 routine tests, four structural checks and ten manual
integration probes. Routine discovery now includes exact official operator turns through
the real registry/critic, repeated-write effects, planner input isolation and all five
required plan scenarios on the official batch task. Models remain free/scripted.

The merge check at `fae559f` recorded 250 routine tests, four structural checks, ten manual
integration probes, and three scripted real-registry workflow checks passing. Those are
historical verification counts for that tree, not current performance results. Reverify the
current tree with:

```sh
make test
make check
.venv/bin/python -m unittest tests.fixtures.agent_integration_probe
git diff --check
```

Scripted tests can prove execution order, refusals, checkpoint repair, persisted effects,
critique holds and bounds. A hand-authored fixture does not satisfy the requirement to show
one **live planner-produced plan**, and does not establish valid-plan rate or task success.
A test-backed step-size example in M1 is labeled accordingly. No live run should be invented
to replace the missing API-backed evidence.

## Remaining evidence sequence

1. With coordinated access to the team's configured model, complete B7/T3 for messy-file,
   batch and comparison work, plus an ambiguous work/status message. A development command is:

   ```sh
   .venv/bin/python run.py --tasks tests/fixtures/agent_messy_file.yaml --sweeps 1 --arm dev-abraham-messy-01
   ```

   Inspect actual routing, arguments, rejected plans, checkpoint repairs, critique and end
   reasons. Record supported bug/prompt changes in `CHANGES.md`; use a new development arm
   after a change. Development evidence must remain labeled and separate from official arms.
   Do not compete for the shared key while Myron runs those arms.
2. Capture one actual batch planner proposal and its trace. For **each step**, state what its
   success/failure reveals and what breaks if it is removed. Repair unnecessary/opaque steps
   through the prompt/schema if observed. Add the real source and compare M1's persistence
   inventory with that trace; the scripted illustration is not a substitute.
3. After Myron's official baseline is committed, generate Abraham's first-failure table:

   ```sh
   .venv/bin/python -m experiments.analysis.failures results/baseline/
   ```

   Inspect each cited physical trace line, its surrounding events and the independent final
   check. The earliest flagged event can be a recovered failure, not the root cause. Missing
   traces remain explicit. Synthetic/free runs must not populate the measured table.
4. Myron owns baseline/pass runs, ledger and Part 3; Claudea owns the critique paragraph and
   aggregate analysis. Recompute official figures from committed records and set switches
   from the pass verdict before the team's final submission checks.

`OPENAI_API_KEY` was absent in this audit session. The external dependencies are coordinated
model access, a live planner/trace specimen, and official baseline evidence. The handout and
merged tool implementations are available. No official project success, cost or latency
measurement is claimed here.
