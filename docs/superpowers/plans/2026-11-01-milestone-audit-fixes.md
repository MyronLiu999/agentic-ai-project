# Milestone audit fixes implementation plan

**Goal:** Resolve audit items 1–6 approved on 2026-11-01.
**Spec:** The six findings in the conversation and Project Milestone 1, especially independent success checks, trusted scope, keyed writes and reproducible Part 4 measurements.
**Architecture:** Preserve the existing service/registry/sandbox boundaries. Make checks read named facts, bind trusted metadata in code, serialize pending sends, and derive analysis from immutable recorded evidence.
**Tech stack:** Python, unittest, SQLite, FastAPI, JSON/JSONL.

## Constraints

- Work on the existing main branch; no branch creation, commits or pushes.
- No paid model runs. Preserve all historical results/traces and the Pass 1 prediction/verdict.
- Existing checker scores remain historical; do not overwrite them with stricter current results.
- Add regressions demonstrating each defect before implementation; run the full suite after integration.
- Keep unrelated item 7 editorial/submission work outside this change.

## Tasks

1. **Business validation:** checks/common.py, messy_file.py, compare_check.py and agent/critique.py; focused new tests. Reject nonfinite headline numbers, incorrect named file/comparison values, inactive pending records, misleading revenue/period prose and incorrect contextual direction claims. Retain valid standard, messy, comparison and batch flows. Critique uses sandbox facts, never task expectations.
2. **Batch recipient binding:** agent/plan.py and focused plan execution tests. Bind planned email recipients to request.contact_email in code, log the executable plan, retain fixed recipient through critique revisions, and keep scope/readability constraints.
3. **Chart identity:** agent/tools.py/registry.py as needed and tests. Reactive identity derives from request and structured chart data, excluding display title; identical effects deduplicate, materially different data do not silently return stale artifacts. Fixed logical-step retries preserve their existing identity.
4. **Operator sends:** sandbox/pending.py, app/product.py and tests. Atomically claim one pending send, protect against concurrent duplicate delivery and send/discard races, and close only work fulfilled by the sent report. Preserve newer pending work and explicit failures.
5. **Portable failure reports:** experiments/analysis/failures.py and tests. Resolve Windows/POSIX relative paths and paired traces after checkout relocation without editing evidence.
6. **Reproducible experiment analysis:** experiments/analysis and evidence tooling/tests. Count proposal rejections separately from terminal bounds; classify malformed versus semantic wrong arguments with trace-backed definitions; output target metrics, initial-turn false finishes and differences. Regenerate derived summaries/audit with explicit LF hash normalization while preserving original hash provenance.

## Verification and review focus

- Correct data elsewhere must not mask a wrong headline or missing required field.
- Valid email phrasing and quarter comparisons must remain usable; unknown or contradictory assertions fail closed with actionable reasons.
- Wrong planner recipient literals and model revisions cannot change trusted contact scope.
- Reworded chart titles are the same effect; changed numerical data are different effects.
- Concurrent sends and discard/send races create at most one outbound message; failed sends remain inspectable.
- Windows paths and CRLF/LF copies reproduce the same analysis; annotations cite existing physical trace lines.
- Independently review changes, run make test, make check and integration probes; update M1/CHANGES only for affected implementations and evidence.

## Progress

- [x] 1. Business validation
- [x] 2. Batch binding
- [x] 3. Chart identity
- [x] 4. Operator sending
- [x] 5. Portable failures
- [x] 6. Reproducible metrics
- [x] Integrated verification and review

## Verification results (2026-11-01)

- `make test`: 368 tests passed.
- `make check`: all four structural checks passed.
- `python -m unittest tests.test_agent_official_flows tests.fixtures.agent_integration_probe`:
  13 tests passed (three official-flow tests and ten manual integration probes).
- `python -m experiments.analysis.recompute --check`: all six derived artifacts verified.
- Failure analysis: 54 historical records, eight failures with physical trace citations,
  zero missing/corrupt evidence issues.
- `git diff --check` passed; raw results, archived traces and the experiment ledger are unchanged.
- Independent runtime review found three prose-validation cases; each was reproduced,
  fixed and rechecked. Independent evidence review found missing baseline hash coverage
  and stale absolute-path precedence; both were reproduced, fixed and rechecked.
- Baseline hash provenance now covers all 36 source files from unchanged `f3461a9` blobs.
  The manifest explicitly records that this inventory was established during this audit.
- No new model-quality measurement: historical check scores and the negative Pass 1
  decision remain unchanged. Prose validation handles explicit revenue/quarter assertions;
  it is not a general natural-language fact checker.
- Work remains uncommitted on the existing main branch; no branch or push was performed.
