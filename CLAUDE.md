# Project rules for Claude Code sessions

This is the team's Milestone 1 project (a data analyst agent). Read `PLAN.md` first: it names the
owners, branches, interfaces and the timeline (regroup and merge on Oct 30, due Nov 1). The handout is
`../milestone1_handout.md`.

- Work on your own branch (`claudea/domain`, `abraham/agent-core`, `myron/tools-evidence`) and edit only
  the files your role owns (`PLAN.md`, section 1). Shared files: `switches.yaml`, `docs/milestones/M1.md`,
  `CHANGES.md`: edit only your own groups, sections and bullets.
- Keep to the interfaces in `PLAN.md` section 3. Tell the others before changing one.
- `make test` and `make check` must pass before every push. Neither spends tokens.
- Never commit an API key (the OpenAI key is shared privately; set it with `export OPENAI_API_KEY=...`).
  All data is synthetic (`SYN-` IDs). The model is set only on `main`, by myron.
- Real-model dev runs use `--arm dev-<yourname>` and are never committed (no `results/dev-*`, no stray
  `traces/`). The baseline and the pass's arms are run by myron only, from a clean `main`; nobody else uses
  the key during them.
- Assignment citations (A1, A2, A3) come from `docs/assignment_refs.md` (myron's repositories).
- The agent has no tool that sends the emailed report: it writes a pending record, and the operator
  sends it from the product page. `sandbox/margins.py` is never imported by a tool or workflow.
- `app/` imports the agent only as `agent.service`. `harness/`, `channel/` and `run.py` are not edited.
- After the Oct 30 code freeze, only logged bug and prompt fixes. While the pass's arms run, commit only
  `results/`, `traces/`, `experiments/`, `docs/`, `README.md` and `CHANGES.md`.
- Every number written up needs its source, read date and run count.
