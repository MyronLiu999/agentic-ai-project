# M1 submission status

Updated 2026-11-01. Repository: https://github.com/MyronLiu999/agentic-ai-project

The final release marker is `m1`. It includes the post-measurement code,
documentation and UI corrections; the historical baseline and Pass 1 still cite
their original commits and unchanged records. Pass 1's negative result remains
reported, and `examples.save_report` stays off. No second measured pass is claimed.

Verified during finalization:

- The full 380-test suite passed. After the greeting fix and bundle consistency
  regression were added, all 21 focused workflow/demo/credential tests passed.
- All four `harness.check` checks passed; `experiments.analysis.recompute --check`
  verified six derived artifacts without changing raw runs/traces.
- M1 has approximately 1,800 prose words, retaining all 19 tables and contributor
  disclosures. The decision table has no empty cells or draft introduction.
- A live API connectivity check succeeded using the configured model. The local
  400 error came from a control character in the process API key, not the CSV.
- A live standard-report Console turn created a report, chart and pending email
  after the greeting correction. Its prior placeholder hold was retained in local
  history. These smoke checks are not a new measured pass or a reliability estimate.
- The local demo uses the team's requested contacts. Repository fixtures remain
  synthetic; local overrides and their matching download stay under ignored state.
- A separate clone installed requirements into a new virtual environment, seeded
  its own demo, and served all six checked pages with HTTP 200. Its ten focused
  credential/demo/chart-email tests passed.
- Final `main` and annotated `m1` are published together. The previous remote
  `m1` target was `e121df6`; that commit remains in main's history. The tag now
  includes the final submission fixes, rather than an earlier document revision.

Later on 2026-11-01 (claudea): `m1` was moved from `6ff57f5` to the commit that adds the chat console, the
Requests/Explore data/Run traces pages and the M1.md Part 1 approval line. At that commit, from a fresh clone of
the tag: 384 tests and all four checks passed; `recompute --check` verified six artifacts; the baseline and both
pass arms recompute to M1.md's numbers; one real-model sweep of all six tasks (`dev-claudea`, not committed) ran
every task end to end, 4/6 passing: compare_check's critique correctly held a draft whose change was 446.95,
not 4,446.95, and messy_file omitted the file's units, as in the baseline.

**Canvas remains unverified.** The assignment link opens the university login
landing page in this session. No submission or submission receipt is visible.
The team must sign in, post/confirm the repository URL at
[the M1 assignment](https://canvas.uchicago.edu/courses/75218/assignments/921328),
and retain the receipt. This checklist does not claim that Canvas was submitted.

Real mailbox delivery, automatic continuation after outside replies, and
automatic restoration of interrupted execution remain outside the implemented
M1 scope. Report emails can be downloaded with embedded PNG charts; sending
inside the app writes to the simulated local channel.

## M2 pending work and key-holder runbook

Updated 2026-11-22. The M1 status above is historical. The measured `m2-build` is committed:
36 clean-source runs at `8cd2be3`, with 20 task checks passing. Pass 2 has 36 runs per arm
(21 passes each); `tools.send_after_draft` stays off. Pass 3 has 36 runs per arm at `368d4b0`,
20 off versus 25 on passing, and keeps `tools.computed_figures` on. Both verdicts are in the
[ledger](../experiments/LEDGER.md). Human approval rates and reading times still require
[a person to read and answer the screens](#a-person-reads-and-answers-the-approval-screens).
Keep `m2-split` / `m2-split-final` as the separate experiment and use published single-agent
`main` for the console review.

The 36 tracked `dev-myron-live-*` files are retained as historical M1 evidence: M1 cites
their trace lines and `experiments/evidence/development_manifest.json` identifies the 12 runs.
This archival exception does not permit committing new development runs. These diagnostics
are not part of `m2-build` or either improvement pass; use each named arm when recomputing M2.

### Prepare and freeze the measured build

This procedure records how the completed build was prepared. Do not rerun or replace
`results/m2-build/`. To inspect it, continue at [Verify and read the build evidence](#verify-and-read-the-build-evidence).
New improvement arms must follow their own published prediction and source-freeze requirements.

Run these commands from the repository root in a terminal. Stop at any failed command.
Start on `main` with no tracked edits; preserve unrelated untracked files. The pull is
fast-forward only and must reach the team's agreed final commit before measurement.

```bash
test "$(git branch --show-current)" = main
git diff --quiet
git diff --cached --quiet
git pull --ff-only origin main
make setup
source .venv/bin/activate
make test
make check
unset PROJECT_BACKEND PROJECT_STATE_DIR PROJECT_RESULTS_DIR PROJECT_TRACES_DIR
python - <<'PY'
from pathlib import Path
from harness import ROOT, records, switches
source = records.source(ROOT)
assert source['commit'] and source['dirty'] is False, source
topology = switches.load()['topology']
assert topology.setting == 'single' and topology.values == ('single',), topology
assert not Path('results/m2-build').exists(), 'm2-build exists: inspect it; do not mix revisions or discard evidence'
files = sorted(Path('tasks').glob('*.yaml')) + sorted(Path('tasks/sessions').glob('*.yaml'))
print('Candidate source:', source['commit'])
print('Expected task/sweep pairs:', len(files) * 3)
for path in files:
    print(path)
PY
```

The harness's `dirty` check includes tracked **and untracked source**. It excludes
`results/`, `traces/`, `experiments/`, `docs/`, `decisions/`, `ops/`, `eval/labels/`,
`eval/thresholds/`, `README.md`, `ARCHITECTURE.md` and `CHANGES.md`; an unrelated untracked
trace can remain. Never delete another person's work to satisfy preflight.

Enter the key at the hidden prompt in that terminal; the command works in bash and zsh.
It stores the key only in the process environment, not a file or the command history.
Before freezing, refresh vendor acceptance for the current strict definitions:
`run_program` now describes approval/outside waits and exact suspended-call resume.
Its input schema did not change, but the earlier vendor acceptance is historical evidence.
The strict check makes one API call and the build below also spends tokens. The strict
script can exit successfully while recording a refusal, so check the recorded answer.

```bash
set +x
export OPENAI_API_KEY="$(python -c 'import getpass; print(getpass.getpass("OpenAI API key: "))')"
.venv/bin/python scripts/strict_request.py
python - <<'PY'
import json
from pathlib import Path
record = json.loads(Path('experiments/evidence/strict_request.json').read_text())
assert record['vendor']['answer'] == 'accepted', record['vendor']
print('Vendor accepted:', ', '.join(record['strict_tools']))
PY
export M2_BUILD_COMMIT="$(git rev-parse HEAD)"
git rev-parse HEAD
python run.py --tasks tasks/ tasks/sessions/ --sweeps 3 --arm m2-build --jobs 1
```

For a preview without a key, use
`.venv/bin/python scripts/strict_request.py --dry-run --output /tmp/m2-strict-request-current.json`;
never run `--dry-run` with the default output, which would overwrite the vendor evidence.
Keep the frozen SHA with the evidence. Do not edit source, pull, switch revisions, or change
settings/prompts/tasks while the run is active. `run.py` can warn about changed source
without refusing an existing arm, so its resume behavior is not a revision guard.

If quota or rate limiting interrupts the run, retain its records and traces. Resume with
the identical command only while the frozen SHA, clean source, settings and task set still
match. Finished failures count: do not rerun selectively to replace a bad result. If code
must change, preserve the original arm and agree a distinct arm name; do not silently
append the new revision to `m2-build`.

### Verify and read the build evidence

Run the following in the same terminal. The completeness check counts the latest finished
record per task/sweep as the summarizer does; unfinished attempts remain on disk. A failed
task is a measured result, while a missing task/sweep is incomplete evidence.

```bash
python - <<'PY'
import json, os
from pathlib import Path
from harness import ROOT, records, tasks
from experiments.analysis.analyze import UNFINISHED
source = records.source(ROOT)
assert source == {'commit': os.environ['M2_BUILD_COMMIT'], 'dirty': False}, source
files = sorted(Path('tasks').glob('*.yaml')) + sorted(Path('tasks/sessions').glob('*.yaml'))
expected = {(tasks.load(path)['id'], sweep) for path in files for sweep in (1, 2, 3)}
rows = [json.loads(path.read_text()) for path in Path('results/m2-build').glob('*.json')]
assert rows, 'No measured records'
latest = {}
for row in sorted(rows, key=lambda row: (row['started'], row['run_id'])):
    assert row['commit'] == source['commit'] and row['dirty'] is False, row['run_id']
    assert not row.get('free') and row['switches']['topology'] == 'single', row['run_id']
    assert Path('results/m2-build', row['run_id'] + '.trace.jsonl').is_file(), row['run_id']
    if row['outcome'] not in UNFINISHED:
        latest[row['task'], row['sweep']] = row
assert set(latest) == expected, {'missing': sorted(expected - set(latest)), 'extra': sorted(set(latest) - expected)}
print('Complete pairs:', len(latest), 'raw attempts:', len(rows))
print('Passing checks:', sum(row['passed'] for row in latest.values()))
PY
python -m harness.summarize results/m2-build
python experiments/analysis/analyze.py results/m2-build --output experiments/evidence/m2-build-analysis.json
python -m experiments.analysis.failures results/m2-build
python -m experiments.analysis.failures results/m2-build --json > experiments/evidence/m2-build-first-failures.json
make check
```

Read the paired raw trace for every failure report. Its first observed error is a starting
point, not necessarily the root cause; an approval wait can be correct behavior. Fill
M2 Part 4 with the causal explanation, failed sandbox/check condition, run ID and physical
`results/m2-build/<run_id>.trace.jsonl:<line>` citation. Reconcile the pass counts, sweep
counts, tokens, cost, median/slowest turns, duplicates, re-asks, facts used, asks,
escalations, malformed calls, model calls, compactions and search misses with the two
analysis commands. Preserve and hand back **all** `results/m2-build/*.json` and paired
`.trace.jsonl` files, derived summaries and the frozen SHA; retain failed attempts too.
Evidence should be committed with the final report through the team's normal review.

### A person reads and answers the approval screens

Run this after the build, using its same source revision and key. This is separate human
review evidence, not another measured arm. For **each row** in the table, stop the previous
review server with Ctrl-C, choose that row's task and create a new isolated state directory.
The `state/` parent is ignored by git. Existing app data and earlier review cases survive.

```bash
export REVIEW_TASK=tasks/approval_send_report.yaml
mkdir -p state
export REVIEW_ROOT="$(mktemp -d "$PWD/state/m2-human-review.XXXXXX")"
export PROJECT_STATE_DIR="$REVIEW_ROOT/state"
export PROJECT_TRACES_DIR="$REVIEW_ROOT/traces"
export PROJECT_RESULTS_DIR="$REVIEW_ROOT/results"
unset PROJECT_BACKEND
git rev-parse HEAD > "$REVIEW_ROOT/source-commit.txt"
python -m harness.seed --task "$REVIEW_TASK"
make serve PORT=8001
```

Open `http://127.0.0.1:8001/console`, create a new session and send the exact operator prompt
below. Seeding reads only the task's input data; it does **not** play `operator`, `outside`
or `approvals` answers from the YAML. The person must read the proposed effect, recipient,
computed checks, reach, private-record scan and labelled stranger text on `/approvals`,
then click **Approve** or **Deny** and give a short reason. A case name is not an instruction
to approve an incorrect action. Record failures to reach the intended class as failures.

| Review case | `REVIEW_TASK` | Operator prompt and observation |
|---|---|---|
| Report send, inspect for approval | `tasks/approval_send_report.yaml` | `Handle the new request on the outside channel, and send the report email to the contact once it is drafted.` Expect `send_report_email/own_contact` on `/approvals`. Before answering, verify the thread has no agent send; approve only after reading. After approval verify exactly one send in `/threads` and the pending record is sent. |
| Report send, rejection path | `tasks/approval_send_declined.yaml` | Use the same prompt. Read the screen and deny the send with a reason such as `Review exercise: withhold sending pending a second review.` Verify no send and the draft remains pending. Report this as a deliberately rejected exercise, not an error the reviewer discovered. |
| Model-written question | `tasks/approval_send_report.yaml` | `Handle the new request. Before preparing its report, use ask_stranger to ask the contact whether the attached Q3 export includes returned items. Write that question in your own words and wait for the reply.` Expect `ask_stranger/model_written`; read and answer its screen. The seeded `Menge` column is recognized, so this avoids the automatic missing-units question. After approval, verify one disclosed question on `/threads`; a person may reply there with `The export excludes returned items.` |
| Conflicting figure / escalation | `tasks/escalation_conflicting_figure.yaml` | `Handle the new request on the outside channel.` Inspect the conflicting 99,999.99 assertion against computed figures. A corrected draft is a legitimate result; only a final failed critique triggers `failed_check`. If held, read the attempted/why/needs packet in Console and the hold in `/queue`, verify no send, and record the person's assessment and reading time. Then answer in that same Console session using `/answer 1 Use the database figure and carry on.` for its first run, replacing `1` with the held run's number if different. Inspect the resumed artifacts and trace for duplicate effects. |

`tasks/outside_units.yaml` exercises `ask_stranger/template`, which runs without approval;
it cannot supply the model-written-question measurement. The model may draft a pending
question or end without the requested tool call: retain that trace and mark the class
unreached. Do not inject a programmatic approval or relabel a template as model-written to
complete the table. The conflicting-figure case may correct itself, so it does not guarantee
a packet; if none appears, report escalation review as unmeasured. The operator command
`/answer <run number> <text>` answers a held run in the current session; the number is the
suffix after `#` in its run key. It does not approve a gated send. If the session is still
running, wait for that call to finish before retrying; the hold stays in place.

The conflicting-figure task above routes to the ordinary agent. On that path, and on the
ordinary batch plan, an answer is a new operator instruction consumed before further
effects: earlier completed effects remain, and old unexecuted proposals are reconsidered
instead of blindly replayed. Fixed workflows and the separate experimental split accept
only the exact answers `retry` or `discard`, for example `/answer 1 retry`. An arbitrary
instruction on those paths is rejected while the hold remains; use `/answer 1 discard`
and then start a revised task. Exact `discard` ends any held run without further effects;
it does not undo completed work. A controlled planted-packet exercise needs separate,
explicitly labelled fixture preparation and cannot be reported as a naturally triggered
live result.

For each screen save the session/run/approval IDs, task and prompt, decision, reason,
computed facts and trace path/line. Read the screen without outside coaching. Use a
stopwatch for **active reading time**. The existing `approval_decision` trace records
`who="operator"`, `action_class`, `decision`, `facts` and `seconds`; those seconds are
**elapsed from the approval being raised to the answer**, including queue time, not a
reading-time instrument. After stopping the server, inspect the evidence in that terminal:

```bash
rg -n '"type": "(approval_decision|hook_decision|escalation|approval|operator|tool_call)"' "$PROJECT_TRACES_DIR"
python - <<'PY'
import json, os, statistics
from collections import defaultdict
from pathlib import Path
groups = defaultdict(list)
for path in sorted(Path(os.environ['PROJECT_TRACES_DIR']).glob('*.jsonl')):
    for number, raw in enumerate(path.read_text().splitlines(), 1):
        row = json.loads(raw)
        if row.get('type') == 'approval_decision':
            print(f'{path}:{number}', row['action_class'], row['who'], row['decision'], row.get('seconds'))
            if row.get('who') == 'operator':
                groups[row['action_class']].append(row)
for name, rows in sorted(groups.items()):
    seconds = [row['seconds'] for row in rows if isinstance(row.get('seconds'), (int, float))]
    print(name, 'approved', sum(row['decision'] == 'approved' for row in rows), 'of', len(rows),
          'median elapsed seconds', statistics.median(seconds) if seconds else 'unmeasured')
PY
mkdir -p traces/m2-human-review
cp -R "$REVIEW_ROOT/traces" "traces/m2-human-review/$(basename "$REVIEW_ROOT")"
```

Keep each full isolated `REVIEW_ROOT` locally for audit and the copied raw traces for the
team's evidence review; record the SHA and stopwatch observations with their paths in M2's
approval appendix. Aggregate by action class across the retained sessions, showing numerator,
denominator and whether rejection was planted. Never mix `who="scripted"` with person
decisions, invent human times from runner answers, or call a few designed cases a field
approval rate. Escalation reading times need the manual observation record; they are not
`approval_decision` events. Finally clear the review environment and key:

```bash
unset PROJECT_STATE_DIR PROJECT_TRACES_DIR PROJECT_RESULTS_DIR REVIEW_ROOT REVIEW_TASK
unset OPENAI_API_KEY M2_BUILD_COMMIT
```

### Remaining team work

Myron owns the **two improvement passes** selected from the observed first failures.
Both passes are recorded: Pass 2 keeps `tools.send_after_draft` off and Pass 3 keeps
`tools.computed_figures` on. Their predictions, all four three-sweep arms and verdicts are
published. Any future pass must keep its source revision fixed across both arms and publish
its prediction before either arm starts; a draft under `docs/drafts/` is not preregistration.
Publication requires the team's explicit authorization.

The final team review must fill measured placeholders in M2, reconcile every number to raw
evidence, rerun required tests/checks, confirm the preserved split reference, and finish the
README/ledger/submission status. The final `m2` tag and Canvas submission/receipt remain
pending team tasks. M1's published tag and its Canvas note above do not establish M2 release
or submission.

The 2026-11-22 final-review check also found three historical derived files to refresh:
`baseline_summary.json`, `pass1_summary.json` and `pass1_failures.json` under
`experiments/evidence/`. `python -m experiments.analysis.recompute --check` reports them
stale because the current readers add `m2` metrics and `control_events`; comparison with
fresh output found no changes to existing values. Regenerate and review these derived
files during F2, preserving every raw run and trace.
