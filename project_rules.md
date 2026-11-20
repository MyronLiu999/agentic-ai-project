# Project rules

The team's project (a data analyst agent), now in **Milestone 2**. Read `PLAN_M2.md` first: it names the
owners, branches, contracts and the timeline (setup Fri Nov 20; branches pushed by Sat Nov 21, 8 pm; merge Sat
night; first pass and final pass Sun Nov 22). The handout is `../milestone2_handout.md`. Milestone 1's plan is
`PLAN.md`, kept for its history.

- Work on your own branch (`claudea/m2`, `abraham-m2` and `abraham-split`, `myron-m2`) and edit only the files
  your role owns (`PLAN_M2.md`, section 3.1). Shared files: `switches.yaml`, `docs/milestones/M2.md`,
  `CHANGES.md`, `app/main.py`, `requirements.txt`: edit only your own groups, sections, bullets and route block.
  `docs/assignment_refs.md` is read-only except for claudea's Milestone 2 sections.
- Keep to the contracts in `PLAN_M2.md` section 3. Code against the stubs and the fakes in `tests/fakes.py`
  (FakeRegistry, ScriptedTools, FakeHook, FakeApprovals, FakeResume, FakeStranger), not another member's branch.
  `tests/test_m2_contracts.py` pins the contracts; `agent/events.py` holds the shared trace event names and end
  reasons. Tell the others before changing a contract.
- Ownership: claudea checkpoints, the resume and the journal (`agent/checkpoints.py`, `agent/runs.py`,
  `sandbox/control.py`), memory, the disclosure, the workflows, the critique, `sandbox/`, `tasks/`, `checks/`;
  abraham the agent path (`service.py`, `router.py`, `loop.py`, `bounds.py`, `plan.py`), context and notes, the
  outside exchange, the stop (`agent/stop.py`, `policy/flags.py`), mid-task messages and the split; myron the
  tools (`registry.py`, `tools.py`), the MCP server, deferred loading and code calls, the policy (`policy/hook.py`,
  `limits.py`, `rules.py`, `autonomy.yaml`), approvals, escalation, the queue, model settings, `scripts/`, the
  ledger and `analyze.py`'s Milestone 2 numbers.
- `make test` and `make check` must pass before every push. Neither spends tokens.
- Never commit an API key (the OpenAI key is shared privately; set it with `export OPENAI_API_KEY=...`).
  All data is synthetic (`SYN-` IDs). The model is set only on `main`, by myron.
- Real-model dev runs use `--arm dev-<yourname>` and are never committed (no `results/dev-*`, no stray
  `traces/`). The build and the passes' arms are run by myron only, from a clean `main`; nobody else uses the
  key during them.
- Every tool call goes through the registry and its policy hook. A send to a stranger carries the disclosure line
  (`agent/disclosure.py`), added by code, never by a prompt. The model never sees `policy/`. An irreversible send
  is a tool only behind the approval gate; `sandbox/margins.py` is never imported by a tool or workflow.
- `app/` imports the agent only as `agent.service`. `harness/`, `channel/` and `run.py` are not edited.
- After the code freeze, only logged bug and prompt fixes. While the passes' arms run, commit only `results/`,
  `traces/`, `experiments/`, `docs/`, `decisions/`, `README.md` and `CHANGES.md`, plus a pass's fix behind its
  switch. Push each pass's ledger prediction before its first measured run, and never amend it.
- Every number written up needs its source, read date and run count. Assignment citations come only from
  `docs/assignment_refs.md`.
