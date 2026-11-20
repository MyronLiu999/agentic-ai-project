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

# Milestone 2: Assignments 2 (Part G), 4, 5 and 6 (owner: claudea)

These come from **claudea's** repositories, which ran on `gemini-3.5-flash-lite`, not the project's
`gpt-4o-mini`: every M2 citation names the model. Only claudea edits this part; abraham (A6) and myron (A5)
cite from it. If a number you need is missing, ask claudea. Myron's Assignment 2 section above covers the
plan and the critique only, so the notes-against-compaction result abraham cites (Part 1 task 6) comes from
claudea's Assignment 2, below.

Repository contents and committed run records for Assignments 4 to 6 were read on **2026-11-20**.
Every number below was read from a file committed at the named commit (`git show <commit>:<path>`).
`not measured` means the repository has no defensible value for that field.

## Assignment 2, Part G: note-taking against compaction (feeds M2 Part 1 task 6; abraham)

- Repository / commit: [claudea24/agentic-ai-assignment2](https://github.com/claudea24/agentic-ai-assignment2),
  commit `51e98ca9cf6434c25a2a16444dfb0c3559389f66`.
- Provider and model: Google through the OpenAI-compatible Chat Completions backend, `gemini-3.5-flash-lite`.
- Source: `reports/LAB_02.md`, Part G (read 2026-11-20). 12 runs: issues 4203, 4204 and 4206, two sweeps each,
  with and without the progress file. Compaction was forced at `COMPACT_AT = 500` tokens (characters / 4), so
  every run compacted before its six questions.
- **Answers right: 32/36 without the progress file (6, 6, 4, 4, 6, 6), 36/36 with it.** The four misses were the
  two 4204 runs: the compaction summary kept the notification files and dropped `src/i18n/en.json` and
  `src/i18n/fr.json`, paths an early search had returned; with the file shown, both were still listed.
- Cost: the file averaged 385 characters (about 100 tokens) on every executor call and the questions call;
  10,286 tokens a run with it against 9,489 without (+797, +8.4%, 6 runs each, so partly noise).
- The report's own reading: at a real threshold compaction was not needed (the largest prompt in its 72 runs was
  4,787 tokens); the file paid only because compaction was forced.

## Assignment 4 (feeds M2 Part 1 tasks 1, 2 and 9; claudea)

- Repository / commit: [claudea24/agentic-ai-assignment4](https://github.com/claudea24/agentic-ai-assignment4),
  commit `a339ea21c4779a1f71311f883ca5d743cdadafad`.
- Provider and model: Google through the OpenAI-compatible Chat Completions backend,
  `gemini-3.5-flash-lite` (`settings.yaml`, `base_url: https://generativelanguage.googleapis.com/v1beta/openai/`).
- Source records: `reports/LAB_04.md` (Parts B, C and F) and `reports/LAB_04.json` (`matrix_derived`,
  `matrix_uuid`, `duplicate_comment_ids`, `forgetting`). The tracker counts were rechecked against the committed
  tracker databases: `tracker/archive/tracker-20261030-001803.db` (Part B, archived by `make reset`) and
  `tracker/tracker.db` (Part C onward). Traces and request records are in `runs/`.
- Plan under test: issue 4201, five steps (read issue, search, read file, `open_pr`, `post_comment`), sync
  checkpoints before both writes; uncrashed reference run `planned-4201-s01-5dda15`.

**Kill at every step.** One crashed-and-resumed run per cell: 10 runs with derived keys and 10 with
`KEY_MODE=uuid`. That is 20 table runs. Counts come from the tracker by run_id.

| Kill point | Derived keys: comments / open PRs / matches findings | Random (uuid) keys: comments (IDs) / open PRs |
|---|---|---|
| After step 1 | 1 / 1 / yes | 1 (10) / 1 |
| During step 1 | 1 / 1 / yes | 1 (1) / 1 |
| After step 2 | 1 / 1 / yes | 1 (2) / 1 |
| During step 2 | 1 / 1 / yes | 1 (3) / 1 |
| After step 3 | 1 / 1 / yes | 1 (11) / 1 |
| During step 3 | 1 / 1 / yes | 1 (4) / 1 |
| After step 4 (`open_pr`) | 1 / 1 / yes | 1 (5) / 1 |
| During step 4 | 1 / 1 / yes | 1 (12) / 1 |
| After step 5 (`post_comment`) | 1 / 1 / yes | **2 (6, 7)** / 1 |
| During step 5 | 1 / 1 / yes | **2 (8, 9)** / 1 |

- With derived keys: **0/10 kill points duplicated** anything. Every case left 1 comment and 1 PR matching
  its last checkpoint's findings. The resumes after crashes at steps 4 and 5 spent 0 tokens.
- With the keys broken: **2/10 kill points duplicated**, both at step 5 (`planned-4201-s01-bc406b`,
  `planned-4201-s01-53bf84`). That is 2 duplicate comments beyond one per run, and **0 duplicate PRs**: the
  `open_pr` check also looks up an open PR by branch, which is a second guard that does not depend on the key.
- Reruns excluded from the tables: 1 derived-key case and 6 uuid-key cases were run again. The planner left the
  tool arguments empty, so the first try wrote nothing or `--die-during-step 4` never fired. `LAB_04.md` names
  each excluded run.

**Part F: the boundary each lost fact crossed.** All runs are `--way planned` on issue 4192. The fact is "Ledgerline's
maintainers label every report about the Export button feature: they plan its fixes on the feature board." When a
run uses it, the comment says `label: feature`. For each boundary the table cites 1 lost run and 1 fixed run.

| Boundary | Lost run (result) | Where it was lost | Fix | Fixed run (result) |
|---|---|---|---|---|
| Attention | `planned-4192-s01-165f83` (`label: bug`) | The drafting call was sent the fact at character 54,388 of 96,396, buried in source files | A prominent maintainer's note right after the request, with a shorter context | `planned-4192-s01-79d143` (`label: feature`); the fact was at 1,647 of 4,862 |
| Compaction | `planned-4192-s01-05423f` (`label: bug`) | Dropped by the first `compaction` line (trace line 17). No call from request 6 on was sent it | A structured note kept outside the conversation, under the same compaction | `planned-4192-s01-078461` (`label: feature`) |
| Session | `planned-4192-s01-291d10` (`label: bug`) | `store_read` returned `[]`, and none of its 10 requests was sent the fact | The store: the rule written word for word (record 15) and read back before the first search | `planned-4192-s01-2f3cda` (`label: feature`); the stated run was `planned-4192-s01-1499a8` |
| Restart | no separate Part F run | The process is killed mid-run | Checkpoint plus derived keys | Part B: 10/10 kill points ended with 1 comment and 1 PR |

- Result: **3/3 Part F boundaries lost the fact and their fixes restored it**, 1 lost run and 1 fixed run each.
  The restart boundary is covered by Part B's 10 runs, not by its own Part F run.
- What the fixes took: 3 extra session runs (`-7b3690`, `-907448`, `-dcd379`) read record 15 and still
  said `bug`. Only after the prompt change and `rules_block` was the session fix itself fixed. Two
  attention runs were also not used (`-8f57ca` and `-c71d4a` said `bug`). 10 runs posted no comment
  because of the empty-arguments planner slip, which `LAB_04.md` lists.
- Pass rates for the Part F arms: `not measured`. Each arm is a single run, not a repeated sample.

## Assignment 5 (feeds M2 Part 2 tasks 4, 5 and 9; myron)

- Repository / commit: [claudea24/agentic-ai-assignment5](https://github.com/claudea24/agentic-ai-assignment5),
  commit `41106540168a336edb6f9253d15974e8ec03bc30`.
- Provider and model: Google through the OpenAI-compatible Chat Completions backend,
  `gemini-3.5-flash-lite` (`settings.yaml`, same endpoint as Assignment 4).
- Source records: `reports/LAB_05.md` (Parts A to C) and `reports/LAB_05.json` (`replay`, `diagnostics`,
  `batching`, `stop`). The rates and medians were recomputed from `logs/approvals.jsonl` (human rows only), and
  the latencies from `logs/stops.jsonl`. Note: the working copy has an uncommitted edit to `reports/LAB_05.md`,
  limited to Part D's disclosure count. Every number here is from the committed version.

**Replay of the recorded day** (`bin/replay_policy fixtures/rollup_2026-08-04.jsonl`, one recorded day: 520 calls,
40 issues): 502 independent, 14 gated and 4 prohibited.

- Prompts per day: **14** (9 `post_comment/human_active`, 5 `open_pr/unprotected_base`).
- Seconds per prompt at 10 minutes a day: **600 / 14 = 42.9 s**.

**One plan review** (`--batched`; it covers `open_pr/unprotected_base` and `post_comment/human_active` and is asked
once per run, after the checked draft and before the first write):

- Prompts per day **14 → 11** (3 prompts saved a day), and seconds per prompt **42.9 → 54.5 s**. 3 of the 11
  runs had both a PR and an active-thread comment.
- The report calls 11 a floor, because the recorded day has no plan revisions or rewritten drafts to ask again.
- On the live day queue the same rule would have given 15 reviews instead of 17 (4302 and 4315 each asked twice).

**Approval diagnostics**: 17 human decisions from one day queue (`--set day`, 40 runs). These are the only human
decisions; `logs/approvals.jsonl` also holds 15 scripted ones, which are excluded.

| | Decisions | Approval rate |
|---|---:|---:|
| All classes | 17 | 0.35 (6/17) |
| Irreversible, wide classes | 4 | 0.00 (0/4) |

- The irreversible, wide classes are those ranked `undo: none` and `blast: wide`: `post_comment/human_active`,
  `post_comment/unknown_thread`, `push_commit/own_branch`, `push_commit/protected`, `push_commit/foreign_branch`
  and `merge_pr`. Only `post_comment/human_active` received any decisions, all 4.

| Action class | Decisions | Approved | Median seconds |
|---|---:|---:|---:|
| `open_pr/unprotected_base` | 13 | 6 (0.46) | 33.5 |
| `post_comment/human_active` | 4 | 0 (0.00) | 27.2 |

- Median seconds for the other classes: `not measured` (they had no human decisions).

**Stop latency** (`bin/stop` request to first refused call). Measured over **10 stops** on development issues 4191
and 4192, all of which took effect and all 10 resumes completed:

- Median (p50) **2.045 s**, largest **7.59 s**, smallest 0.116 s.
- The 5 stops that landed during a model call took 2.6 to 7.6 s. The 5 that landed between tool calls took
  0.1 to 1.5 s. The report names "Fast" as the condition met only partly.

## Assignment 6 (feeds M2 Part 3; abraham)

- Repository / commit: [claudea24/agentic-ai-assignment6](https://github.com/claudea24/agentic-ai-assignment6),
  commit `7013cb1ea4e3f9ba4ecea84fdabd97f81015135f` (`main`). The split's code is on branch `lab-06-split`.
- Provider and model: Google through the OpenAI-compatible Chat Completions backend,
  `gemini-3.5-flash-lite` (`settings.yaml`); reviewer `scripted:approve-all`.
- Source records: `reports/LAB_06.md` (Part C), `reports/LAB_06.json` (`arms`, `multiplier`, `spend_check`),
  `results/summary_06.json` and `results/runs_06.jsonl` (72 runs: 24 per arm, which is 18 single and 6 batch,
  three sweeps over 8 tasks). Pass counts were recounted from `runs_06.jsonl` and agree.
- Constants: B = 250,000 tokens per issue (1,250,000 per batch task), `schemas_sha 703c0002892f27ec`,
  `checks_sha 55abcd67e6a3b208`, and the same `--jobs 2` for every arm.
- Caveat stated in the report: these are the **third** measurement of arms M and S-plus. The split's stopping rule
  was changed twice between measurements (`7a472de`, `dd340d7`). Earlier results are in `runs/discarded/`: M
  single 15/18 then 13/18, M batch 1/6 then 0/6, S-plus single 16/18 then 13/18, S-plus batch 0/6 then 1/6.

**Multiplier** (arm M mean tokens per task over arm S):

- Single tasks: **0.70×** (38,218 / 54,918).
- Batch tasks: **0.51×** (182,138 / 357,222).
- The lecture's 15× is measured against a chat. The report converts it to about 3.75× against one agent.

| Arm | Kind | Passes / runs | Sweep low to high | Tasks passed all 3 | Mean tokens | Mean wall-clock |
|---|---|---:|---|---:|---:|---:|
| S (one agent, budget B) | single | 12/18 | 3 to 5 of 6 | 3 of 6 | 54,918 | 7.1 s |
| S | batch | 4/6 | 1 to 2 of 2 | 1 of 2 | 357,222 | 27.8 s |
| M (split) | single | 15/18 | 4 to 6 of 6 | 3 of 6 | 38,218 | 10.7 s |
| M | batch | 0/6 | 0 to 0 of 2 | 0 of 2 | 182,138 | 14.1 s |
| S-plus (one agent at M's spend) | single | 11/18 | 3 to 4 of 6 | 2 of 6 | 27,627 | 7.4 s |
| S-plus | batch | 1/6 | 0 to 1 of 2 | 0 of 2 | 151,856 | 46.1 s |

- Issues passed inside batches (of 30 over 6 runs): S 28, M 20, S-plus 19.
- **Matched-budget comparison:** S-plus was budgeted at arm M's mean spend per task (`--match split`). It came in
  **under** that spend: −28% on single tasks and −17% on batches (−10% to −42% per task).
  - One issue: one agent passed 11/18 against the split's 15/18, at 28% less spend. This was not the same
    budget in fact.
  - Batch: one agent passed 1/6 against the split's 0/6, at 17% less spend. Both lost to arm S at 4/6.
- The report's slide-18 answers:
  - Did the split spend more? No on both kinds.
  - Does spending more raise the score? Yes on both: slightly for one issue, clearly for batches.
  - Given the same budget, did one agent do as well? No for one issue (under-matched); yes for batches.
- Recorded decision: single agent for both kinds (`decisions/0006-topology.md`, `LAB_06.json` `decision`).
- A spend-matched S-plus within ±10% of arm M on single tasks: `not measured`.

## Code and design reused

- From Myron's Assignment 3 repository: the **design pattern**, not copied source, of deriving a
  stable write key from canonical run/step/effect identity and returning short protocol errors.
  This project changes the domain to report and pending-email writes, uses the course project's
  `Registry.call` result contract, and records through `SessionTrace.tool_call`.
- Assignment 1 and 2 results are cited as evidence only; no code from those repositories is reused.
