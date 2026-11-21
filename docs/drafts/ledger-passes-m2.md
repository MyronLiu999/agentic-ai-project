# Ledger drafts for Milestone 2's passes (myron, M9)

Not the ledger. `make check` reads only `experiments/LEDGER.md`. On Sunday (PLAN_M2.md 8.2, P4), once the
build's runs are read and two problems are picked with abraham, copy one block per pass to the end of
`experiments/LEDGER.md`. Fill **Problem**, **Evidence**, **Why this fix** and **Prediction** from those
runs, and push before the first measured run. Never amend it afterwards.

The predictions are the team's own reading of the runs. Nothing below predicts a number: every `<...>` is
filled from `m2-build`'s records and traces. The candidate fixes and their measures come from the handout's
Part 4 table, so each pass names the lecture's test and the measure `analyze.py` already prints
("Milestone 2:" lines, experiments/analysis/m2.py).

| If the build shows | Candidate switch (owner builds the fix) | The fix's own measure (analyze.py / the check) |
|---|---|---|
| Definitions take much of each call, or a wrong tool picked | `tools.loading=deferred` (myron; built) | input tokens per call, tools per call, search misses, model calls per run |
| More asks than a person reads | `approval.batch_reports=plan` (myron; built) | asks per run, and per day on M2.md's real day |
| Malformed calls on a new tool | `strict.<tool>` / `examples.<tool>` (myron) | malformed calls per run, rejected at the boundary |
| Many calls on a case that loops | `code_calls.batch_reports=on` (myron; built) | model calls per run, input tokens per call |
| A late action ignores an early fact | `notes.console` (abraham) | facts used, questions answered right |
| An effect done twice | a key or checkpoint (claudea) | duplicates, from the checks |

## Pass 2 · <the problem, in a few words>

- **Pass:** 2; <the fix, behind its switch>
- **Owner:** <member who builds the fix>; runs: myron
- **Problem:** <the symptom, as the first-failure table names it>
- **Evidence:** <run IDs from results/m2-build/ and trace lines, file:line>
- **Why this fix:** <the lecture's test and its answer for this problem>
- **Prediction:** <per arm, with a number, and what the assignment's result predicts for us>
- **Arms:** results/pass2-<off>/ with --set <switch>=<before>; results/pass2-<on>/ with --set <switch>=<after>; both after this commit is pushed
- **Held constant:** <model gpt-4o-mini, code commit, every other switch, tasks, checks, bounds, scripted operator answering every ask the same way>
- **Tasks and sweeps:** <every test task including tasks/sessions/>, 3 sweeps per arm
- **Results:** pending
- **Difference:** pending
- **Verdict:** pending
- **Links:** [before](../results/pass2-<off>/), [after](../results/pass2-<on>/)

## Pass 3 · <the problem, in a few words>

- **Pass:** 3; <the fix, behind its switch>
- **Owner:** <member>; runs: myron
- **Problem:** <the symptom>
- **Evidence:** <run IDs and trace lines>
- **Why this fix:** <the lecture's test and its answer>
- **Prediction:** <per arm, with a number>
- **Arms:** results/pass3-<off>/ with --set <switch>=<before>; results/pass3-<on>/ with --set <switch>=<after>
- **Held constant:** <as Pass 2>
- **Tasks and sweeps:** <every test task>, 3 sweeps per arm
- **Results:** pending
- **Difference:** pending
- **Verdict:** pending
- **Links:** [before](../results/pass3-<off>/), [after](../results/pass3-<on>/)

When the results come in, report runs passed sweep by sweep, total and per-run tokens, median and slowest
turn latency, and the fix's own measure. Label every result a pilot.
