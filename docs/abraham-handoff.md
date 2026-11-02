# Abraham's agent core: implementation and evidence handoff

Status: **2026-11-01**. The domain, agent paths, registry/tools and audit fixes are integrated
on the existing `main`. The [final Milestone 1 report](milestones/M1.md) records current
choices; [technical notes](milestones/M1-evidence.md) retain detailed specimens and methods.
`PLAN.md` is the original allocation/schedule, not a list of still-pending integration work.
The actual Project Milestone 1 PDF was read on 2026-10-31; its missing Markdown copy is not
a blocker. No new feature branch is needed.

## Interfaces and limits

The app and runner share `harness.turns.operator_turn` → `agent.service.operator_turn`.
Code selects request scope; ambiguous intent can use a bounded classifier. Status follows
durable records and the session's selected IDs. Reactive tools are request-bound. The batch
planner sees operator instructions/contracts/allowlisted IDs and counts, never stranger
questions/files/contact addresses. Replanning gets code-owned status/counts/IDs, not raw
outputs. Validation enforces listed order, same-request bindings and an immutable completed
prefix. Only failed read checkpoints can replan; an uncertain write stops for inspection.

Both email paths pin the saved report/figures and comparison requirement through critique.
Planned recipients remain bound to trusted contacts through revisions. Held email creates no
pending email, although earlier report/chart effects remain. Model-written questions have
scope/shape checks and operator review, not the report-email critique. A question stops with
its waiting thread. Sending is operator-only, atomically claimed per pending ID, and cannot close newer
unfinished work. Ambiguous delivery stays inspectable without automatic retry.

Records, artifacts and traces survive reopening a session. Active conversations/plans/output
maps and repeat counters are not automatically resumed. Outside-answer continuation is
Milestone 2. Business checks cover named figures and supported explicit revenue assertions;
no general natural-language correctness or leakage guarantee is claimed.

## Completed evidence

| Work | Current evidence |
|---|---|
| B1–B6 routing, loop, service, fake paths and planning | `tests/test_agent_*.py`, including official turns, status scope/restart, effects, bounds, input isolation and five batch scenarios |
| B7 development diagnostics | Twelve real diagnostic runs archived in `experiments/evidence/development_manifest.json`; trace-backed prompt repairs in M1/CHANGES. This does not establish every ambiguous-intent behavior. |
| B8 first failures | Eighteen baseline records plus thirty-six Pass 1 records; M1 cites the sole baseline failure and seven pass failures. Portable reader resolves all eight physical trace citations. |
| B9 live plan/inventory | `dev-myron-live-02-batch_reports_two-s01-792d75`, trace lines 7/9 and 10–58; per-step result/deletion assessment and planned/reactive persistence inventory in M1 |
| Official measurement | Baseline 17/18, examples-off 15/18, examples-on 14/18; target 3/3 in both pass arms. The negative predeclared verdict keeps `examples.save_report=off`. |

These measurements describe their recorded commits/checks. The later validation, contact,
chart and delivery fixes have regression coverage; current-code live quality has not been
remeasured. Myron's A1/A2 citations in `assignment_refs.md` are prior issue-triage evidence,
not sales-domain measurements. Comparison and homogeneous batch Gate 1 claims remain
provisional, explicitly documented; a configured agent route alone proves no necessity.

## Verification and submission

The 2026-11-01 clean-checkout check at runtime revision `39a10dd` installed an independent
virtual environment, passed 368 tests/four structural checks, and verified six derived
artifacts. All eight HTTP pages loaded; a scripted console request saved a report, chart and
pending email with independently matched database figures. That smoke test used a free fake
backend; archived live traces establish the separate historical model evidence. The exact
documented `make app` also started without a backend override and served all eight pages;
that default-backend check issued no model-triggering requests. The final report now has
1,838 prose words across Parts 1–3 and the team, excluding headings, tables and fenced code;
extended source/specimen details are separately linked, while required tables remain in M1.

```sh
make test
make check
.venv/bin/python -m unittest tests.test_agent_official_flows tests.fixtures.agent_integration_probe
.venv/bin/python -m experiments.analysis.recompute --check
git diff --check
```

Before release, commit the reviewed documentation, verify the exact committed tree, then
create/push `m1` only with the user's explicit Git authorization. Confirm that the remote tag
resolves to that checked commit. Collaborator access and the repository URL's Canvas
submission require their actual external state to be checked; this file does not claim either
is complete. No official baseline or live planner specimen needs rerunning merely because an
older handoff listed it as missing.
