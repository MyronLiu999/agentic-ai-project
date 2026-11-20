# Milestone 2 plan

**Project:** Data analyst (carried on from M1, every switch at its M1 verdict). **Team:** claudea, abraham, myron.
**Due:** Sun Nov 22, 2026 (tag `m2` pushed + repo URL on Canvas). **Target:** all 100 points.
**Handout:** `../milestone2_handout.md` (Parts 1 to 4, Submitting, rubric). **M1 plan for reference:** `PLAN.md`.

## 0. How it works (timeline)

Start each block **as soon as the one before it is done**; the times are the latest it may finish. If everyone
is early, the chain moves earlier. Canvas deadline assumed Sun 11:59 pm; **the team aims to submit by Sun 9 pm**.

| Block | Who | Earliest start | Latest done | Hands off with |
|---|---|---|---|---|
| **Setup on `main`** (section 4): contracts, seams, stubs, fakes, switches, policy skeleton, `M2.md` skeleton, A4–A6 numbers in `docs/assignment_refs.md` | claudea | Fri Nov 20 morning | **Fri 2 pm** | "setup pushed" in the chat |
| **Build on own branch** (sections 5, 6, 7). **Nobody waits on anybody**: code against the stubs/fakes on `main`, never another branch. If setup is late, start with the steps that are writing only: abraham B1 and B7, myron M4 and M8 | all three | "setup pushed" | **Sat Nov 21, 8 pm** | "pushed + tests pass" |
| **Sat 2 pm check-in**: each posts the steps done and any contract problem. **Sat afternoon trial merge**: abraham merges whatever is pushed into a scratch branch (never pushed to `main`) and posts the conflicts; nobody waits for it | all three / abraham | Sat 2 pm | Sat 5 pm | conflicts list |
| **Merge** all three branches into `main`, integrate, one dev sweep (section 8.1) | abraham | all three branches pushed | **Sat Nov 21, 11 pm** | "merged" |
| **Buffer**: each owner fixes what the merge broke in their own files | all three | "merged" | Sun 9 am | |
| **First pass**: code freeze, the build runs, Part 4's two improvement passes, the split's branch and tag, review against the rubric (section 8.2). abraham reads the runs (P3) once m2-build is committed | myron (+ abraham) | "merged" (Sun 9 am at the latest) | **Sun 3 pm** | the gaps list in the chat |
| **Final pass**: recompute every number (F2 once the ledger is filled), finish the write-up, fresh clone, tag `m2`, push, Canvas (section 8.3) | claudea | the gaps list | **Sun 9 pm** (3 hours of slack before midnight) | tag `m2` pushed + Canvas |

Words used here: a **review pass** (Sunday's first/final pass) checks the repo is ready to submit. An
**improvement pass** is Part 4's measured loop (prediction → two arms → verdict), logged in `LEDGER.md`.

## 1. Who owns what

| Member | Branch | Builds (handout) | Write-up in `docs/milestones/M2.md` | Merge → submit | ≈ rubric pts |
|---|---|---|---|---|---|
| **claudea** | `claudea/m2` (setup on `main`) | Setup · P1 t2 checkpoints, three exits, irreversible last, recovery test · P1 t7 memory + later session (`make serve`) · P2 t8 disclosure | P1 t1 diagram + lifetimes · P1 t2 · P1 t7 · P1 t8 abstraction · P1 t9 "Which boundary lost it?" · P2 t8 the Act + two states · build table, decision table, team, AI line | **Final pass** + submit | 30 + setup + final |
| **abraham** | `abraham/m2` and `abraham/split` | P1 t5 outside exchange + wait · P1 t6 context budget, notes, compaction, long session · P2 t6 stop + cancel/resume/rollback · P2 t7 mid-task messages · P3 split on a branch | P1 t5 · P1 t6 · P2 t6 five-condition table · P2 t7 · P3 inventory, gates, sketch, benefit · `decisions/0006-topology.md` | **Merge** + P4 t1 first-failure table | 34 + merge |
| **myron** | `myron/m2` | P1 t3 MCP server + strict-mode request · P1 t4 deferred loading + code calls · P2 t1–3 ranking, policy, hook, stated limits · P2 t4 approval gate, approvals page, queue page · P2 t5 escalation · P4 analysis-script additions | P1 t3 · P1 t4 bill · P2 t1–2 ranking + three columns · P2 t4–5 · P2 t9 "Who is going to read this?" + tiers | **First pass** + P4 passes + ledger | 36 + review |

Citations, all in `docs/assignment_refs.md` (setup copied them from **claudea's** repositories, which may be
private; model `gemini-3.5-flash-lite`, a different vendor from our `gpt-4o-mini`, so every citation names it):
**A2 Part G** (notes against compaction) -> abraham; **A4** (kill at every step, lost facts) -> claudea; **A5**
(approval replay, stop latency) -> myron; **A6** (multiplier, matched budget) -> abraham. Cite only from that
file; if a number you need is missing, ask claudea.

## 2. Rules (same as M1, plus M2's)

1. **Your own branch, your own files** (section 3). Nothing merges into `main` before the merge (Sat night) except the setup.
2. **Code against the contracts in section 3** (stubs, `tests/fakes.py`, the tool table). Exact names,
   arguments, fields. **To change a contract, tell the other two first** and update section 3 the same day.
3. **`make test` and `make check` pass before every push.** Neither spends tokens. Tests use fake models
   (`free = True`) and `tests/support.py` `fixed_run` / `check_run`.
4. **Never commit the API key.** `export OPENAI_API_KEY=...`. The model (`gpt-4o-mini`) is set on `main` only.
5. **Real-model dev runs** use `--arm dev-<yourname>` and are **never committed** (no `results/dev-*`, no stray `traces/`).
6. **Every new switch carries `added: 2026-11-20`** (or the day it is added), on the switch itself; a plain value
   takes the long form: `context_budget: {setting: 16000, added: 2026-11-20}`.
7. **Placeholders** for anything that cites another person's work: `[claudea: ...]`, `[abraham: ...]`,
   `[myron: ...]`, `[run: ...]`, `[A4: ...]`. Filled after the merge.
8. **Every number** in the write-up has its source, read date and run count.
9. **M1 rules still hold**: `app/` imports the agent only as `agent.service`; `harness/`, `channel/`, `run.py`
   are not edited; `sandbox/margins.py` is never imported by a tool or workflow; all data is synthetic (`SYN-`).
10. **Shared files** (`switches.yaml`, `M2.md`, `CHANGES.md`, `app/main.py`, `requirements.txt`): edit only your own
    groups / sections / bullets / marked route block. `docs/assignment_refs.md` is read-only except for claudea's A4–A6 sections.
11. **Sunday, while myron runs measured arms, nobody else uses the key**, and only `results/`, `traces/`,
    `experiments/`, `docs/`, `decisions/`, `README.md`, `CHANGES.md` are committed (plus a pass's fix behind its switch).

## 3. Files and the shared contracts

### 3.1 File ownership (M2)

| Owner | Files |
|---|---|
| claudea | `agent/checkpoints.py`, `agent/runs.py`, `agent/workflows.py`, `agent/domain_workflows.py`, `agent/critique.py`, `agent/memory.py`, `sandbox/memory.py`, `agent/disclosure.py`, `sandbox/` (except `queue.py`), `tasks/` (except abraham's and myron's new tasks below), `checks/`, `app/templates/console.html` + `_history.html` (session list, memory read), top of `README.md`, the `memory` group in `switches.yaml`, `tests/test_checkpoints*.py`, `tests/test_recovery*.py`, `tests/test_memory*.py`, `tests/test_disclosure*.py`, the A4–A6 sections of `docs/assignment_refs.md` (written in setup; abraham and myron read them and ask claudea if a number they need is missing) |
| abraham | `agent/service.py`, `agent/router.py`, `agent/loop.py`, `agent/bounds.py`, `agent/plan.py`, `agent/context.py`, `agent/notes.py`, `agent/outside.py`, `agent/stop.py`, `agent/messages.py`, `app/templates/threads.html`, `tasks/outside_*.yaml`, `tasks/sessions/`, their checks (`checks/outside_*.py`, `checks/session_*.py`), `experiments/analysis/failures.py`, `decisions/0006-topology.md`, the split on `abraham/split` → `m2-split`, switches `context_budget`, `compaction_threshold`, the `notes` group, `topology`, `tests/test_outside*.py`, `test_context*.py`, `test_stop*.py`, `test_midtask*.py`, `test_split*.py` |
| myron | `agent/registry.py`, `agent/tools.py`, `mcp_server/`, `agent/code_calls.py`, `policy/` (`autonomy.yaml`, `hook.py`, `limits.py`), `agent/approvals.py`, `agent/escalation.py`, `sandbox/queue.py`, `app/templates/approvals.html` + `queue.html`, `tasks/approval_*.yaml`, `tasks/escalation_*.yaml` + their checks, `settings.yaml`, `pricing.yaml`, `scripts/`, `experiments/LEDGER.md`, `experiments/analysis/analyze.py` (M2 additions), the `tools`, `code_calls`, `approval`, `examples`, `strict` groups in `switches.yaml`, `requirements.txt` (MCP SDK), `tests/test_mcp*.py`, `test_deferred*.py`, `test_code_calls*.py`, `test_policy*.py`, `test_hook*.py`, `test_approval*.py`, `test_queue*.py`, `test_escalation*.py` |
| everyone | your own sections of `docs/milestones/M2.md`, your own bullets in `CHANGES.md`, your own route block in `app/main.py` |
| setup (claudea, Fri) | the seams in other owners' files (section 3.3); after setup, the file's owner owns the seam. `policy/flags.py` -> abraham, `policy/rules.py` -> myron, `sandbox/control.py` -> claudea. `tests/test_m2_contracts.py` pins the contracts: change it only with the contract (tell the other two first) |

### 3.2 New modules and their contracts (built in the setup, with these exact signatures)

All state is keyed by the **run key**: in a `run.py` run, the run ID; in the app, `"<session_id>#<run_no>"`.
The same key names the run's checkpoint, wait, stop flag and hold. Control state lives in one SQLite file,
`state/control.sqlite3` (`sandbox/control.py`): reset with the sandbox (`make app`, `make seed`, every run.py
run), kept by `make serve`. It is not the memory store.

| Module (owner) | Contract (exact signatures) | Setup ships |
|---|---|---|
| `agent/runs.py` (claudea) | `key(run_id=None, session_id=None, run_no=None) -> str`; `session_of(run_key)`; `new_run(session_id) -> str` (the next run of a console session; the run ID in run.py); `current_key(session_id=None) -> str\|None` (the run in scope); `first_turn(session_id) -> bool`; `live(session_id) -> list[str]`; `end(run_key, reason)` (a reason in `WAITING` = needs_answer, awaiting_approval, held, stopped leaves the run live); `resuming() -> str\|None`; **`resume(run_key, event) -> Reply`: the one resume entry**. `event = {"kind": "outside_reply"\|"approval"\|"operator_turn"\|"stop_resume"\|"crash", ...}`. It loads the checkpoint, clears the wait and, while the resume is in scope, the registry reads the journal; an agent run calls `loop.resume_from(checkpoint, event)`, a workflow run raises `NotImplementedError` until claudea's C3 | **working**, except workflow resume |
| `agent/checkpoints.py` (claudea) | `save(run_key, state, mode="sync"\|"async"\|"exit")`, `update(run_key, mode="sync", **fields)`, `load(run_key) -> dict\|None`, `history(run_key)`, `before_step(run_key, step: dict)` (the placement rule), `after_call(run_key, call, result)` (journal a completed keyed write), `completed(run_key, key) -> result\|None`, `set_wait(run_key, kind, ref, deadline=None)`, `clear_wait(run_key)`, `waiting(session_id=None)`, `to_trace(trace, run_key)`. State: `{"run_key","use_case","path","request_id","plan","step_status","completed_calls":[{"tool","args","key","result"}],"findings","current_step","conversation","operator_text","waiting_for","held","stopped"}`; JSON only | **working**; `before_step` saves on every step it is given until claudea's C2 narrows it |
| `loop.resume_from(checkpoint, event, *, registry=None, limits=None, clock=None) -> LoopResult` (abraham) | carry on an agent-path run: restore the conversation saved at the start of the last model round, append what the event brings as a labelled user turn, run the round again; completed writes come back from the journal | **minimal working**; abraham extends it (B2, B5) |
| `agent/memory.py` (claudea) | `write(record) -> dict` (the one write policy), `for_session(session_id, budget_tokens=2000) -> list[dict]`, `read_log(session_id)`. Record: `{"id","kind":"episodic"\|"semantic"\|"procedural","fact","source":"operator"\|"stranger"\|"system"\|"private_data","written_at","derived_or_ingested","confirmed":bool,"supersedes":id\|None}` | stub: stores and reads nothing |
| `agent/context.py` (abraham) | `create(session_id, *, purpose, system, messages, tools=None)`: **the one way the loop and the workflows call the model** (plan.py and router.py still call the client directly: abraham routes them); `assemble(session_id, *, purpose, system, messages, tools) -> (system, messages, left_out)`; `estimate_tokens(value)` (chars / 4) | stub: passes everything through |
| `agent/notes.py` (abraham) | `for_call(session_id, call_kind) -> str`, `update(session_id, *, done=None, open_items=None, ids=None)` | stub |
| `policy/hook.py` (myron) | `decide(call, ctx) -> Decision`; `call = {"name","args","caller","step","key","request_id"}`, `ctx = {"run_key","session_id"}`; `Decision = {"answer":"allow"\|"ask"\|"deny","action_class":"tool/circumstance","reason", "error_type" (optional: "stopped" for a stop, "undisclosed"), "screen" (optional, for "ask")}`. Order: stop flag first, then prohibited, then stated limits (`policy.rules.rules_for`), then `disclosure.check(call)`, then the columns. `registry_hook(request_id)` adapts it to the registry; keep it. **A hook that raises denies.** For a resumed call the operator approved, ask `approvals.is_approved(run_key, key)` | stub: stop -> deny; a send without the line -> deny; else allow |
| `policy/flags.py` (abraham after setup) | `set_stop(session_id, run_no=None, at=None)` (a session-wide stop reaches the runs that started before it), `stop_run(run_key, at=None)`, `clear_stop(run_key, at=None)`, `is_stopped(run_key) -> bool`, `log(run_key)` | **working** |
| `policy/rules.py` (myron after setup) | `add_rule(session_id, rule)`, `rules_for(session_id)`; rule `{"action_class","effect":"deny"\|"ask","source_text","created"}` | **working** |
| `policy/limits.py` (myron) | `parse_limit(text) -> rule\|None` (code, never the model) | stub: `None` |
| `agent/approvals.py` (myron) | `put_up(run_key, session_id, call, action_class, screen) -> approval_id`, `pending() -> list[dict]` (each with `id`, `session_id`), `decide(approval_id, approved, note, who="operator") -> dict` (returns the item with its `run_key`; logs class, screen facts, decision, who, seconds, switch setting, run key), `is_approved(run_key, key) -> bool`, `withdraw(run_key) -> list[str]` | stubs |
| `agent/escalation.py` (myron) | `signal(run_key, name, attempted, why, needs) -> packet` (`{"run_key","signal","attempted","why","needs","over_cap"}`), `held(session_id=None)` | stub: marks the checkpoint held, traces it |
| `agent/disclosure.py` (claudea) | `LINE`, `with_disclosure(text) -> str`, `has_line(text)`, `check(call) -> bool` (False only for a send whose text lacks LINE), `SENDS` (`ask_stranger` -> `question`; `send_report_email` -> the pending record's body). `checks/helpers.DISCLOSURE` is a copy (checks never import agent/); a test pins them equal | **working** |
| `agent/outside.py` (abraham) | `ask(run_key, question, template=None) -> Reply(waiting_for=thread_id)`, `on_reply(thread_id, text) -> Reply` | stub |
| `agent/stop.py` (abraham) | `handle_command(session_id, text) -> Reply\|None` (None: not a command): `/stop`, `/stop <n>`, `/cancel <n>`, `/resume <n>`, `/rollback <n>`; rollback calls `registry.compensate(call_record)` newest first | stub: `/stop` writes the flag |
| `agent/messages.py` (abraham) | `intercept(session_id, text) -> Reply\|None` (None lets the message through as a new task), `classify(session_id, text) -> "add"\|"replace"\|"queue"\|"reject"` | stub: lets everything through |
| `agent/code_calls.py` (myron) | `run_program(run_key, code, registry) -> dict` | stub |
| `mcp_server/` (myron) | stateless MCP server the registry starts itself; `tools/list` in a fixed order | none |
| `agent/events.py` (shared) | the M2 trace event kinds and end reasons are listed there. **Never a field named `type`, `at`, `session_id` or `run_id`, and never a kind the harness writes** (`approval`, `reply`, ...): a test fails if one clashes | **working** |

Registry results for the new cases (all with the usual `{"ok", "output", "is_error", "error"}` shape):
`error.type == "approval_required"` (`kind` the same, with `approval_id` and `action_class`; outcome
`awaiting_approval`), `"stopped"`, `"undisclosed"`, `"policy_denied"` (kind `protocol`, outcome `denied`); a
journal hit on resume returns the recorded result (outcome `journal`).

### 3.3 Seams (already in the code after setup; the file's owner owns the seam from then on)

- `agent/service.py` `operator_turn`, in order: `stop.handle_command` (before any model), then
  `limits.parse_limit` and `rules.add_rule`, then `messages.intercept` if `runs.live(session)`, then
  `memory.for_session` on the session's first turn, then `runs.new_run(session)`, then routing as in M1.
  `on_outside_reply` -> `outside.on_reply`; `pending_approvals` -> `approvals.pending`; `decide_approval` ->
  `approvals.decide`, then `runs.resume(run_key, {"kind": "approval", ...})`.
- `agent/tools.py` `build`: every registry gets `pre_call_hook=policy.hook.registry_hook(request_id)`.
- `agent/registry.py` `call`: after validation, the hook's Decision (`ask` -> `approvals.put_up` and
  `approval_required`; anything but `allow` is refused, failing closed; each decision traced as `hook_decision`);
  a keyed write while `runs.resuming()` is this run reads `checkpoints.completed` first; a successful keyed
  write calls `checkpoints.after_call`. `compensate(call_record)` uses `ToolSpec.compensate` (None: "none").
- `agent/loop.py`: `checkpoints.before_step` at the start of every model round (the conversation so far); model
  calls through `context.create`; an `approval_required` result -> `set_wait(run_key, "approval", id)` and
  `finish(awaiting_approval)`; a `stopped` result -> `finish(stopped)`; `finish` writes `checkpoints.to_trace`
  and `runs.end`.
- `agent/workflows.py`: `_call` runs `checkpoints.before_step` before each step and handles `approval_required`
  and `stopped` like the loop; the email is drafted through `context.create`; every end goes through `_end`
  (`to_trace`, `runs.end`).
- `agent/critique.py` `run`: a draft still failing at the bound -> `escalation.signal(run_key, "failed_check", ...)`.
- `sandbox/seed.py` `reset`: also resets `sandbox/control.py`.
- `checks/*.py`: every task check is wrapped in `checks.helpers.requires_disclosure`.

### 3.4 Tool contract additions (owner: myron; M1's six tools are unchanged)

| Tool | Arguments | Output (`ok` true) | Writes? | Proposed column |
|---|---|---|---|---|
| `ask_stranger` | `question` | `thread_id`, `message_id`, `created` | yes, keyed, on the outside channel; disclosure line added by code | independent if fixed template; ask if model-written |
| `send_report_email` | `pending_id` | `sent_id`, `recipient`, `created` | yes, **irreversible** | requires approval (own contact); **prohibited** to any other recipient |
| `search_tools` | `query` | `matches` (names), `note` ("nothing matched" when empty) | no | independent |
| `run_program` | `code` | `result` (final only), `calls` (count) | via the registry only | independent (each inner call hooked) |

Compensations (for rollback; **registry-internal, never offered to the model**, called only through `registry.compensate`): `save_report` → `revert_report(report_id, to_version)`; `draft_report_email` →
`discard_pending(pending_id)`; `render_chart` → `delete_chart(chart_id)`; `send_report_email`, `ask_stranger` →
**none**. Prohibited (proposed): `query_sales` for another distributor, any read of margins, a send to a recipient
that is not the request's contact. `FakeRegistry` (setup) accepts the new tools and `compensate`; `FakeHook(answers)`
and `FakeApprovals` live in `tests/fakes.py`.

### 3.5 Fixed text and switches

- Disclosure line (setup fixes it in `agent/disclosure.py`): *"This message was written by an automated agent for
  the sales analytics team. To reach a person, reply to this thread with "human" and an analyst will answer."*
  No company name or email is needed: M1's data names no company (contacts are synthetic, `SYN-contact-*`), and the
  thread is a real way to reach the analyst, who reads it on the threads page. A reply of "human" is the stranger's
  text like any other: it routes the thread to the operator, it approves or stops nothing.
- Setup adds to `switches.yaml`, each with `added: 2026-11-20` and a provisional setting the owner finalizes:
  `tools.loading: all|deferred` (myron), `code_calls.batch_reports: off|on` (myron), `context_budget` (abraham),
  `compaction_threshold` (abraham), `notes.console` and `notes.<run kind>` replacing the flat `notes` (abraham),
  `memory.preferences`, `memory.standing_rules` (claudea), `approval.batch_reports: per_action|plan` (myron).
  `topology` is added on `main` at the merge by abraham (`{setting: single, values: [single], added: ..., about: "m2-split-final"}`).

## 4. Friday setup (claudea, push by Fri 2 pm)

| Step | What |
|---|---|
| S1 | `git pull` on `main`. Copy this file into the repo as `PLAN_M2.md`; update `project_rules.md` for M2 (point at `PLAN_M2.md`, the new branches, the new owners). |
| S2 | Create every module in 3.2 with its final signature (working where 3.2 says "fully working" or "minimal working"; else a documented stub). Includes the minimal `loop.resume_from` and the registry's journal seam, so claudea's agent-path recovery test and abraham's wait both run on Friday without waiting on each other. |
| S3 | Insert the seams of 3.3 into `loop.py`, workflows, `service.py`, `registry.py`, `critique.py` as pass-through calls; existing M1 tests must still pass. |
| S4 | Extend `tests/fakes.py`: `FakeRegistry` knows the 3.4 tools + `compensate`, enforces their argument shapes; `FakeHook`, `FakeApprovals`, a `FakeStranger`, and **`FakeResume`** (records `runs.resume(run_key, event)` calls, so myron can test "the answer resumes the run" without the real resume). Add the run-key helper to `tests/support.py` usage notes. |
| S5 | Switches of 3.5 in `switches.yaml` with `added:`; `make check` passes. |
| S6 | `policy/autonomy.yaml` skeleton (three columns, action classes from 3.4 as proposals); `decisions/` folder. |
| S7 | `docs/milestones/M2.md` skeleton: build table (one row per piece, owner filled), decision table with the new columns (checkpoint, durability mode, code calls, loading, ask stranger, notes/compaction, memory, autonomy column, approval mode, escalation signal, topology), Parts 1–4 headings each with its owner, `## The team`, `## AI assistance`, appendix "Approval screens". |
| S8 | Add the disclosure check to every existing check (`checks.helpers.sent_by_agent` → fail a message without `LINE`). In `docs/assignment_refs.md`, add sections A4, A5, A6 from claudea's own repositories (repo URL, commit, model, source file, read date, run counts), with the numbers the handout asks each part to cite. **A4** (for P1 t1–2, t9): what the tracker held when killed at every step, with keys and with them broken; the boundary each lost fact crossed and the fix that brought it back. **A5** (for P2 t4–5): the replay's prompts per day and seconds per prompt, what one plan review would have saved, the approval rate on irreversible wide classes beside the overall rate, median seconds by class, the stop's latency over its stops. **A6** (for P3): its multiplier and what the matched-budget comparison showed. Write `not measured` where the repository has no defensible value. |
| S9 | `make test`, `make check`, commit, push. Create and push empty branches `abraham/m2`, `abraham/split`, `myron/m2`, `claudea/m2` from this commit. Post in the chat. |

## 5. claudea (after setup → Sat 8 pm, on `claudea/m2`)

| Step | What (handout) | Done when |
|---|---|---|
| C1 | **P1 t1 durability boundary:** what carries within a run, between runs, across a crash; Mermaid diagram of components, registry, MCP server, data, state, memory, control flow, app + runner → one entry point, console and outside channel as two ways in, three zones | Mermaid block in `M2.md` Part 1 |
| C2 | **P1 t2 checkpoints:** mark every step on every path (read / keyed write / unkeyed write); placement (`before_step`): a checkpoint where replay repeats an effect no key closes, the agent loop saves the call + args before it runs; one step that needs one, one that does not; durability mode per run kind (sync for runs with `send_report_email`, async/exit for read-only, a keyed+reversible-only run, an operator-answer run); conversation kept or not (console: trimmed last N turns); last checkpoint → trace on run end | table in M2.md; decision-table rows |
| C3 | **Resume** (`runs.resume`): replay from last checkpoint, skip calls whose key is completed, replay writes with saved args; say which call resumes each waiting kind and what resumes a crashed run (the operator's next turn) | tests |
| C4 | **Three exits** for every write that failed/timed out (read whether the effect happened → carry on / retry same key / `escalation.signal("unsettled_write")`, escalate to the operator); **irreversible steps last** in each workflow and plan, compensate in reverse | tests |
| C5 | **Recovery test** in `tests/`: `kill -9` after the sandbox commits and before the system records it, on every test task with a write, during its last write; new process same ID; check passes, one effect per write, no completed call repeated; record sandbox before / after crash / after resume → M1's "Did the effect happen?" table | `tests/test_recovery.py` |
| C6 | **P1 t7 memory** (`sandbox/memory.py`, `agent/memory.py`): kinds; one kind kept (operator's stated preference / standing rule) and one not (anything the sandbox holds, e.g. last quarter's revenue), argued; the write policy in one place (insert/merge, supersede with timestamp, provenance, at run end or once verified); stranger text stored only as ingested+unconfirmed and kept from the planner; invited failure + store size + eviction + lifetime at your write rate; switches `memory.*` | M2.md Part 1 t7 |
| C7 | **Later session:** after `make serve` the console lists earlier sessions with history; a new session reads the store and waiting checkpoints before its first model call, logs the read, shows records with age and source; a message in an old session carries on; tests: two sessions (second with `fixed_run(..., fresh=False)`) using a preference without being told; set → contradict → third session. Add one memory test task whose `seed(task)` writes the earlier session's records (for Part 4) | `tests/test_memory.py`, console page |
| C8 | **P2 t8 disclosure:** `with_disclosure` on every send path (loop, workflow, code-call program) so the approval dry run shows it; operator's hand-sent mail needs none; test: a send without the line through the registry directly leaves the thread unchanged, refusal logged; write-up: the EU AI Act's two questions, Article 50, Colorado/California human-review answer | `tests/test_disclosure.py`, M2.md |
| C9 | **P1 t8 abstraction:** slide 43's four questions → the abstraction per part; checkpoint/journal/supervisor and slide 40's three questions; honest verdict (expect: recovery aid, supervisor = operator) | M2.md |
| C10 | **P1 t9 "Which boundary lost it?"** draft: one row per fact (operator's task, plan, step status, stranger's reply, stated limit, preference...), boundary (attention / compaction / session / restart), what holds it; gaps listed; others' rows as placeholders | M2.md |
| C11 | Cite A4 (tracker at every kill step, with/without keys; lost fact boundaries). `make test`, `make check`, push by **Sat 8 pm** | chat confirmation |

## 6. abraham (Fri–Sat, on `abraham/m2` and `abraham/split`)

Left for abraham by the setup: `agent/plan.py` and `agent/router.py` still call the model client directly (route
them through `context.create` in B3), and `domain_workflows` and `plan.run` do not call `runs.end` yet, so in the
app their runs stay live (B6 decides what a live run means for a new message).

| Step | What (handout) | Done when |
|---|---|---|
| B1 | **P1 t5 when to ask:** a use case that asks (messy_file: a column whose meaning code can see is missing, e.g. no units/revenue header mapped) and one that does not (standard_report / status_question), each argued; trigger is a check in code, not the model's doubt; fixed-template question is above the line, a model-written one waits behind the gate. **Build the exchange with the fixed template**, so B2 never depends on myron's approval gate | M2.md |
| B2 | **The exchange + wait:** `ask_stranger` as a keyed write, checkpoint saved with `set_wait` before the turn ends, `Reply(waiting_for=thread_id)`; `on_outside_reply` resumes via `runs.resume` (implement `loop.resume_from`), in a new process if the app restarted; reply enters context labelled as the stranger's, never an instruction; deadline + what happens on no reply; threads page shows waiting → answered; test task `tasks/outside_*.yaml` with `asked_again`/`never_asked` + check reading the thread; test: ask, end process, `harness.turns.outside_reply` in a new process, `check_run` passes | `tests/test_outside.py` |
| B3 | **P1 t6 context:** `context.assemble` for every call on every path within `context_budget` (chars/4, tool definitions included); the rule (what first, shortened, together-or-not, ID-only), sources known, stranger labelled, left-out traced; long context vs retrieval per large input (big upload, many orders); session lengths per kind → `notes.console` on, one-run kinds off, argued; notes outside the conversation (IDs + status only from the outside channel); compaction past `compaction_threshold`: clear old tool results first, summarize older turns, keep recent verbatim and the current request whole; cite A2 | M2.md |
| B4 | **Long session** `tasks/sessions/long_*.yaml`: several × budget, under `session_token_ceiling`; early fact, several tasks, a late action that needs the fact, questions on earlier work with answer formats; check returns named counts; tests: over-budget assembly fits + labels + records left-out; compaction trace line, notes unchanged; no stranger words in notes/planner | `tests/test_context.py` |
| B5 | **P2 t6 stop:** `/stop`, `/stop <n>` read before any model, writes `policy.flags`; withdraws a waiting approval (`approvals.withdraw`); checkpoint at stop; `/cancel`, `/resume` (lift flag with time, re-ask withdrawn approval), `/rollback` (compensations newest first, "none" where none, logged as operator's command); notice to the operator before a run's first write and on resume; tests from a second thread while a turn runs and while waiting for a stranger/approval; ≥5 stops timed; five-condition table + the condition met only partly | `tests/test_stop.py`, M2.md |
| B6 | **P2 t7 mid-task messages:** read new messages before every model call; add / replace (list earlier effects, operator picks rollback) / queue (default, bounded) / reject; operator confirms a model's add-vs-replace; a limit becomes a rule; two tests (adding, replacing) from a second thread | `tests/test_midtask.py`, M2.md |
| B7 | **P3 inventory + gates** (write first): "Would these ever need to talk mid-task?" for every pair of candidate components (e.g. file decoder, sales querier, report writer, reviewer, per-distributor batch workers); sketch with arrows; the four gates per component, stop at first failure, evidence each; benefit + condition; cite A6 multiplier | M2.md Part 3 |
| B8 | **The split on `abraham/split`:** coordinator + ≥2 roles split by tool surface (best candidate: `batch_reports` one worker per distributor), all through the same registry + hook; return contract JSON schema validated on every return and traced (result, status found/candidate/out of budget, searched / not searched from tool calls, spent, not determined); end-state check from the sandbox; one trace with parent IDs + tokens per agent; one shared budget; `topology: single\|split`; tests: bad return rejected + traced, planted divergent end state fails, every test task end to end within budget | `tests/test_split.py` |
| B9 | **`decisions/0006-topology.md`:** gate verdicts + evidence, A6 result, the split's tests, decision (expect one agent), testable reopen condition, rejected alternative, what each choice loses, spend check | file on `abraham/m2` |
| B10 | Update `failures.py` for the new trace events (stop, hold, wait, compaction). `make test`, `make check`, push both branches by **Sat 8 pm** | chat confirmation |

## 7. myron (Fri–Sat, on `myron/m2`)

| Step | What (handout) | Done when |
|---|---|---|
| M1 | **P1 t3 MCP server** (`mcp_server/`): stateless; every call carries the IDs it needs, every result returns the next IDs (semantic); keys added by the registry, accepted once; no state in the server; `tools/list` fixed order; execution error `isError: true`, protocol error JSON-RPC; registry starts it as a child process (`make app`, `run.py` need nothing more); SDK in `requirements.txt` with version + revision + date checked; tests: every call reaches the server through the registry, list twice same order, retried keyed write leaves one effect | `tests/test_mcp.py` |
| M2 | **Strict mode as sent:** one request with every strict tool's definition as the registry sends it; keep OpenAI's answer (accepted / refused what) with date | `experiments/evidence/strict_request.json` |
| M3 | (M3a Fri: the bill + deferred loading; M3b Sat: code calls.) **P1 t4 the bill:** tokens per call and per run per agent (split roles included, from abraham's role list or a placeholder), calls per run + run count, share of window; the fixes in slide 28's order and which we need; **deferred loading**: `search_tools` in the MCP server, first request = search + always-needed tools, found definitions join the next request, "nothing matched" + logged misses; `tools.loading` set by count (≈10 tools → expect `all`), argued; **code calls**: `run_program` in a subprocess (no network, scratch folder), every inner call through the registry (hooked, keyed, recorded), only final result enters context; one use case it fits (closest: `batch_reports`, switch off if none truly loops) and one it does not; tests per handout P1 t4 | `tests/test_deferred.py`, `tests/test_code_calls.py` |
| M4 | **P2 t1 ranking:** every action (reads included) through remove/narrow → undo path → blast radius → gate only irreversible + wide; one row per action and circumstance; tools removed or narrowed and why | M2.md table |
| M5 | **P2 t2–3 policy + hook:** `policy/autonomy.yaml` three columns by action class (`send_report_email/own_contact`, `send_report_email/new_recipient`, `ask_stranger/template`, `ask_stranger/model_written`, ...), prohibited not empty; `policy/hook.py`: stop first, then prohibited, fails closed, never a yes from the app for a prohibited class, model never sees it; `parse_limit` ("send nothing until I have read it" → rule); tests: prohibited with every approval scripted yes leaves sandbox unchanged + denial logged; a split tool runs unasked in one circumstance and asks in the other; a stated limit blocks the call it names | `tests/test_hook.py` |
| M6 | **P2 t4 approval gate:** `approvals.py`, approvals page (starter's `approvals.html`) with each item's `session_id`; screen = dry run (effect exactly, with the disclosure line) → computed facts (who created target, who wrote the input, checks passed, reach, private record) → stranger's message labelled → model rationale labelled generated, short; gated call ends the turn, `decide_approval` resumes; survives restart (test the resume with `FakeResume`; the real resume is checked at the merge, T2); at plan vs per action per use case with a plan (`approval.batch_reports`), cite A5; what still checks each step's output; when the plan review is asked; every decision logged; **queue page** (`sandbox/queue.py`): arrived work, status, held runs, threads waiting, approvals waiting; scripted tests; a test task with `approvals:` | `tests/test_approval.py`, appendix screens |
| M7 | **P2 t5 escalation:** signals named in advance (build `failed_check` and `unsettled_write`; consider "same step blocked three times"), use cases each covers in the decision table, one covered and one not; never low confidence; packet on the console (attempted, why stopped, what it needs) + held run in the queue; hold: timeout ends held never approved, answer in a later session resumes; daily cap, over-cap runs wait marked; test: packet 3 non-empty fields + checkpoint + no write; silent → held no write; answered in new session → resumes, no duplicate (`FakeResume` on the branch; real resume at T2) | `tests/test_escalation.py` |
| M8 | **P2 t9 "Who is going to read this?":** row per approval point + escalation + stop notice + stranger; asks per run (placeholder until Sunday's runs), a real day, seconds per ask, rate by class, slide 24 shortcuts, slide 62 counts and what you did; the three frameworks and what our tier owes | M2.md |
| M9 | **Part 4 prep:** `analyze.py` additions that print every M2 number the summarizer doesn't (duplicates, re-asks, facts used, asks per run, escalations, malformed calls, input tokens per call, tools per call, search misses, model calls per run, compactions); ledger entry template drafts in `docs/drafts/` (not `LEDGER.md`); first-failure and passes table skeletons in M2.md Part 4 | tests on hand-written records |
| M10 | Cite A5. `make test`, `make check`, push by **Sat 8 pm** | chat confirmation |

## 8. Merge (Sat night), first pass and final pass (Sun)

### 8.1 Merge (abraham; earliest once all three are pushed, latest Sat 11 pm; Sun morning is buffer)

| Step | What |
|---|---|
| T0 | **Trial merge (Sat afternoon, before the real one):** merge whatever is pushed into a local scratch branch (`trial-m2`), run `make test`, post the conflicts and failing tests in the chat for their owners. Never push it; delete it after. |
| T1 | `git pull`; merge `claudea/m2` → `myron/m2` → `abraham/m2` into `main`; `make test` + `make check` after each. Resolve conflicts in shared files by keeping both owners' blocks. |
| T2 | **Integrate:** real hook/approvals/escalation replace stubs; real checkpoints/resume under abraham's wait and stop; real disclosure under myron's hook; real memory under abraham's context; every test task on fakes; the cross-owner tests below |
| T2b | Re-run myron's approval/escalation resume tests and claudea's recovery test with the **real** resume (they used `FakeResume` / the minimal resume on the branches). |
| T3 | Dev sweep: `python run.py --tasks tasks/ tasks/sessions/ --sweeps 1 --arm dev` (not committed); each owner fixes their own files |
| T4 | `git switch -c m2-split` from merged `main`, merge `abraham/split` in, `make test`; push; add `topology` switch on `main` |

What only the merge can check:

| To resolve | Who |
|---|---|
| Real tool outputs (via MCP) match the contract; callers handle `approval_required` and refusals | myron, claudea, abraham |
| `runs.resume` reaches `loop.resume_from` for waits, approvals, stops, escalations | claudea, abraham |
| The hook calls `disclosure.check`, flags, rules; the stop withdraws approvals | myron, abraham |
| Recovery test still passes through the MCP server | claudea |
| Context budget counts the real (deferred or all) tool definitions | abraham, myron |
| Trace event names match `analyze.py` and `failures.py` | myron, abraham |
| One console session recorded (wait, approval, stop, later session after `make serve`) for the write-up | claudea (Sun), anyone |

### 8.2 First pass (myron; earliest at "merged", latest Sun 3 pm; abraham helps read runs)

| Step | What |
|---|---|
| P1 | **Code freeze**, push. `make test`, `make check` on `main`. |
| P2 | **The build:** `python run.py --tasks tasks/ tasks/sessions/ --sweeps 3 --arm m2-build` (every switch at its setting). Commit `results/`. |
| P3 | **Read the runs** (abraham): `failures.py` + `analyze.py`; first thing that went wrong per failing run, lecture's words, run ID + trace line → M2.md Part 4 table; also what was slow, costly or asked too often. Too few problems: ≤3 harder tasks, run `m2-build-2`. |
| P4 | **Two improvement passes**, each from a problem in that table: pick the fix by the lecture's test (handout Part 4 table; likely candidates: `tools.loading` deferred if definitions dominate; `notes.console` if the long session's late action misses the early fact; `approval.batch_reports: plan` if asks per run are high; strict/examples on a new tool if malformed calls; a checkpoint/key if a duplicate). The code's owner builds the fix behind a switch (`added: 2026-11-22`). **Push the ledger prediction first** (`## Pass N · ...`, numbered after M1's, Results/Difference/Verdict pending), never amend it; then both arms, 3 sweeps each, differing only in that switch, scripted operator answering the same way. Fill the ledger (run IDs, trace lines, total tokens + per run, owner), set the switch to the verdict. |
| P5 | Table of passes in M2.md (problem, evidence, lecture test + answer, prediction, before/after with counts, verdict + switch now, link; assignment prediction vs ours). |
| P6 | **Split branch:** on `m2-split` run the split tests and every test task within the one budget; push; `git tag m2-split-final`; `git push origin m2-split-final` (unless a pass measured it beating one agent at the same budget). |
| P7 | (P6 and P7 run while P2's sweeps run.) **Review against the rubric** (section 9): every build-table piece's evidence runs; no owner's placeholders left in their parts; post the gaps list in the chat for claudea by 3 pm. |

### 8.3 Final pass (claudea; earliest at the gaps list, latest Sun 9 pm)

| Step | What |
|---|---|
| F1 | Fix the gaps from P7 (or ping the owner). Fill every placeholder (`[run: ...]`, asks per run, the bill per run, `[A*: ...]`). |
| F2 | **Recompute every number** in M2.md and the ledger with `analyze.py` from committed `results/`. |
| F3 | Build table (one row per piece with code location + runnable evidence), decision table (new rows/columns), `## The team` (owner by role and name; each part's owner under its heading and on each ledger entry), `## AI assistance` one line. Parts 1–3 + team ≈ 2,500 words. Appendix of approval screens present. |
| F4 | `CHANGES.md` M2 entry (added / removed / limited, reused assignment/course code with whose repo); `README.md`: `make serve` keeps the sandbox, how to run each pass's arms, the model. |
| F5 | Traces of cited console sessions committed in `traces/`. |
| F6 | Submit, exactly as the handout says: `make test`, `make check`, `git add -A`, `git commit -m "Milestone 2"`, `git clone . ../m2-check` → inside it `make setup`, `make app`, use it, stop, `make serve`, earlier session carries on; then `git tag m2`, `git push`, `git push origin m2`. Verify the tag on GitHub. Post the repo URL on Canvas. **A tag not pushed is not submitted.** |

## 9. Rubric checklist (100 pts) → owner

| Pts | Criterion | Owner |
|---|---|---|
| 2 | Clean checkout: `make app`, runner takes every task, `make check`, `make serve` session carries on | claudea (F6) |
| 5 | Checkpoints per decision table, three exits, one effect per write after resume, tested | claudea |
| 2 | MCP server + strict-mode request kept | myron |
| 3 | Deferred loading + code calls behind switches, tested | myron |
| 4 | Outside exchange + wait survives restart, tested | abraham |
| 3 | Context budget, notes, compaction, long session run to the end, tested | abraham |
| 3 | Memory with provenance + write policy, read first by later session, tested | claudea |
| 3 | Policy in the hook, stop first, prohibitions, fails closed, limits as rules | myron |
| 3 | Approval gate (plan / per action), computed screen, decisions logged, queue page | myron |
| 4 | Escalation (myron), stop + three commands, mid-task messages (abraham), tested from sandbox | myron, abraham |
| 2 | Disclosure in code, hook refuses without it, tested from channel | claudea |
| 4 | Split on branch: return contract, end-state check, one trace, one budget, tested | abraham |
| 12 | Two passes from problems seen, table of passes, numbers recompute | myron (runs), owners (fixes), claudea (recompute) |
| 5 | Durability boundary 3 zones + lifetimes + steps marked + one of each + modes + A4 | claudea |
| 2 | Tool list bill, fixes in order, loading switch by count, code-call one of each | myron |
| 3 | Asking the stranger one of each, deadline, reply labelled | abraham |
| 3 | Notes/compaction one of each from lengths, budget/rule/threshold, long ctx vs retrieval, A2 | abraham |
| 4 | Memory: kept/not kept, four write decisions, provenance, invited failure + eviction | claudea |
| 2 | Abstraction from four questions, honest verdict | claudea |
| 3 | "Which boundary lost it?" every fact, gaps listed | claudea |
| 5 | Every action ranked, three real columns, one alone + one asks, prohibited not empty | myron |
| 4 | Approval at plan + per action, each escalation signal one of each way, A5 | myron |
| 3 | Stop vs five conditions, partial one named, cancel/interrupt/rollback apart | abraham |
| 3 | "Who reads this?" asks per real day, seconds/ask, rate by class, shortcuts, tier; the Act + two states | myron (inventory), claudea (Act) |
| 3 | Topology inventory, gates per component, sketch, benefit, A6 | abraham |
| 4 | Decision record: testable reopen condition, real rejected alternative, spend check | abraham |
| 4 | Build's runs read: first thing that went wrong, run ID + trace line | abraham (Sun) |
| 2 | Ownership by role and name under each heading and on each ledger entry | claudea (F3) |

## 10. The prompt each member gives Claude

Start every session with: *"Read `PLAN_M2.md` sections 0–3 and section N, `../CLAUDE.md`, and
`../milestone2_handout.md` Part X. I am `<name>` on branch `<branch>`. Do steps `<ids>` only. Edit only my
files (section 3.1); code against the stubs/fakes on `main`, never another member's branch. Use placeholders
for others' work. Run `make test` and `make check` before you say you are done. Do not push; I push."*

| Who | Section | Branch | Steps | Handout parts to give it |
|---|---|---|---|---|
| claudea (setup) | 4 | `main` | S1–S9 | whole handout (to write the contracts) |
| claudea | 5 | `claudea/m2` | C1–C11 | Part 1 tasks 1, 2, 7, 8, 9; Part 2 task 8 |
| abraham | 6 | `abraham/m2`, `abraham/split` | B1–B10 | Part 1 tasks 5, 6; Part 2 tasks 6, 7; Part 3 |
| myron | 7 | `myron/m2` | M1–M10 | Part 1 tasks 3, 4; Part 2 tasks 1–5, 9; Part 4 (prep) |
| abraham (Sat trial merge, Sat night merge, Sun runs) | 8.1, 8.2 P3 | `trial-m2`, `main` | T0–T4, P3 | Part 4 task 1 |
| myron (Sun) | 8.2 | `main`, `m2-split` | P1–P7 | Part 4, Submitting |
| claudea (Sun) | 8.3, 9 | `main` | F1–F6 | Submitting, How it is read |
