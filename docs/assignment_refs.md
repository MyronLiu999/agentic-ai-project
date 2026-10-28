# Assignment references (owner: myron)

Every assignment citation used in `docs/milestones/M1.md` comes from this file. Repository contents
and committed run records were read on **2026-10-27**. Percentages below always include their run
counts; `not measured` means the source repository contains no defensible value for that field.

## Assignment 1 (feeds Part 1, the four gates; claudea, abraham)

- Repository / commit: [MyronLiu999/agentic-ai-assignment1](https://github.com/MyronLiu999/agentic-ai-assignment1),
  commit `65125727e233902e9d69ba9655e4fe1a6ec4c715`.
- Provider and model: OpenAI through the OpenAI-compatible Chat Completions backend,
  `gpt-4.1-mini` (`settings.yaml`; served runs report `gpt-4.1-mini-2025-04-14`).
- Source records: `reports/LAB_01.json` and the 240 evaluation traces in `runs/` (60 per arm).

| Arm | Success | Mean cost/run | Mean latency/run |
|---|---:|---:|---:|
| Direct call | 20/60 (33.3%) | $0.000436867 | 0.784 s |
| Workflow | 16/60 (26.7%) | $0.000595960 | 1.172 s |
| Agent loop | 15/60 (25.0%) | $0.001991660 | 4.502 s |
| Hybrid | 17/60 (28.3%) | $0.001353560 | 3.079 s |

- **m:** `agent mean cost / workflow mean cost = 0.00199166 / 0.00059596 = 3.342`.
- **f:** `0/6 = 0.000`. The assignment defines this as the share of six issues where workflow passed
  fewer than 5/10 runs and agent passed at least 5/10. No issue met both conditions.
- **c:** workflow mean cost per run, `$0.000595960`.
- The resulting blended cost at this measured `f` is `$0.000595960` per run, versus
  `$0.001991660` for all-agent.
- Agent-path entropy: **19 distinct tool-call sequences** across 60 agent runs; the three most common
  sequences covered **37/60 (61.7%)**. This was recomputed from ordered `tool_call.name` values.

## Assignment 2 (feeds Part 2, the plan and the critique; abraham)

- Repository / commit: [MyronLiu999/agentic-ai-assignment2](https://github.com/MyronLiu999/agentic-ai-assignment2),
  commit `df425ccbbf25814a66234af045a1901852c8e18e`.
- Provider and model: OpenAI through the OpenAI-compatible Chat Completions backend,
  `gpt-4.1-mini`.
- Source: `reports/LAB_02.md` and `reports/LAB_02.json`; each configuration has 18 runs.

| Configuration | Success | Mean tokens/run | Runs with an exact repeat | False finishes |
|---|---:|---:|---:|---:|
| Agent | 7/18 (38.9%) | 14,135 | 8/18 | not measured |
| Planned, critique off | 5/18 (27.8%) | 5,280 | 3/18 | not measured |
| Planned, self critique | 3/18 (16.7%) | 4,992 | 1/18 | not measured |
| Planned, external critique | 2/18 (11.1%) | 4,508 | 3/18 | not measured |

- What the plan bought: a validated and logged artifact, an execution boundary, checkpoint revision,
  and a 62.6% token reduction for planned/off versus agent. It cost 2 passes (5/18 versus 7/18), and
  some savings came from stopping before all planned work completed.
- Bounds: `MAX_REPLANS = 1`, `MAX_REVISIONS = 1`; planned runs averaged exactly 1.00 revision and
  never exceeded one. The checkpoint revised after a search returned no relevant TypeScript source
  file under `src/`.
- Critique bound: `MAX_ROUNDS = 2`. Self and external modes averaged 0.22 and 0.17 rounds/run;
  changed/fixed/broken/held drafts were `0/0/0/0` for both. The second passes therefore bought no
  measured correction in this sample. The external pass checked parseability, file existence,
  whether the run had seen the file, and label/file agreement.
- False finishes were not aggregated in the committed report. Its `s49` specimen did show one:
  the agent claimed completion while a test still failed and plan step 6 was skipped.

## Assignment 3, Part D (feeds Part 3, the tools; myron)

- Repository / commit: [MyronLiu999/agentic-ai-assignment3](https://github.com/MyronLiu999/agentic-ai-assignment3),
  commit `eb6b35703b212474b561099ec265c427174c7a4b`.
- Provider and model: OpenAI through the OpenAI-compatible Chat Completions backend,
  `gpt-4.1-mini`.
- Source: `reports/LAB_03.md` and `reports/LAB_03.json`; 12 harness and 12 control runs.
- Definition tokens, first draft versus rewrite: **195 → 1,682 tokens** for all five definitions;
  the planner's text list was **106 → 1,280 tokens**. Counts are input-token differences between
  otherwise identical calls with and without definitions.
- Duplicates: derived keys plus read-back left **0/12 runs with duplicate comments** and 12 comments
  total. UUID keys without read-back left **6/12 duplicate-comment runs** and 17 comments total,
  i.e. five duplicate effects beyond one comment per run.
- The rewrite was more expensive: mean definition-only cost was `$0.002597367/run`, versus
  `$0.000273967/run` for the first draft. Its measured benefit was a narrower, explicit contract,
  not lower token cost.

## Code and design reused

- From Myron's Assignment 3 repository: the **design pattern**, not copied source, of deriving a
  stable write key from canonical run/step/effect identity and returning short protocol errors.
  This project changes the domain to report and pending-email writes, uses the course project's
  `Registry.call` result contract, and records through `SessionTrace.tool_call`.
- Assignment 1 and 2 results are cited as evidence only; no code from those repositories is reused.
