# Abraham's agent core: implementation and evidence handoff

Updated 2026-11-01. The agent core, sandbox, workflows and tools are integrated
on `main`. The earlier tool-contract mismatches are resolved.

The router selects scope from stored records. The reactive agent is bounded by
calls, tokens and time. The batch planner receives allowlisted inputs; its
validator rejects invalid dependencies, and execution preserves completed work
across checkpoint revisions. Both paths gate report emails before writing a
pending record. An operator reviews and sends through the simulated channel.
Durable records survive restart; the active plan and tool conversation do not
automatically resume.

Evidence previously listed as pending is now available:

- Live development traces and metadata are in `traces/dev-myron-live-*` and
  `experiments/evidence/development_manifest.json`. They are diagnostic,
  not official performance estimates.
- The live batch planner specimen, step-size discussion and persistence
  inventory are in `docs/milestones/M1.md`, Part 2.
- The clean baseline has 18 runs, with 17 passes. The failure table cites the
  failed run and trace. Pass 1 has 18 runs per arm; its negative/inconclusive
  result is in `experiments/LEDGER.md` and Part 4 of the report.
- The official tasks and scripted plan/boundary tests are in `tasks/` and
  `tests/`. Scripted tests demonstrate mechanisms, not live-model reliability.

The measured runs exposed literal example recipients and incomplete comparison
figures. Later code binds recipients and strengthens figure validation, with
regression tests; no new live-model performance is claimed for those fixes.
Pending emails remain subject to human review; the critic does not establish
the truth of every statement.

Before submission, run tests and structural checks on the final commit, verify
a fresh-clone app startup, complete contributor disclosures, and tag and submit
according to `PLAN.md`.
