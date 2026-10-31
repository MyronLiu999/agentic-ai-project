# Myron pre-merge contribution

This preserves Myron's completed Milestone 1 text while the shared `M1.md` is aligned with `claudea/domain` to remove the three-way merge conflict. Reinsert the completed Part 3, Myron build/decision rows, Part 4 status, and AI-assistance statement into the final merged `M1.md`.

# Milestone 1: Data analyst

> Owners (by role and name) are in "The team". Every heading below names its owner too. DRAFT entries are
> the scaffold's proposals for the team to argue and replace. Every figure needs its source and read
> date, every number from runs its run count.

## Build table

Roles: **A** domain, sandbox and checks · **B** agent core, plan, critique · **C** tools, registry, evidence.

| Piece | Owner | Where | Evidence | Control flow / pattern / spectrum |
|---|---|---|---|---|
| Sandbox (SQLite, uploads, stamps) | A | `sandbox/db.py`, `sales.py`, `inbox.py`, `files.py`, `reports.py`, `pending.py`, `seed.py` | `tests/test_sandbox.py` | n/a |
| Three properties | A | untrusted: channel + uploads · private: `margins`, other distributors' orders · way out: pending email, operator sends | TODO | n/a |
| Console, product page | A | `agent/service.py`; `app/product.py` | TODO | n/a |
| Routing | B | `agent/router.py` | TODO | TODO |
| Agent path and bound | B | `agent/loop.py`, `agent/bounds.py` | TODO | TODO |
| Workflows | B | `agent/workflows.py` | TODO | TODO |
| Registry, keys | C | `agent/registry.py` | `tests/test_registry.py` | deterministic boundary / registry gateway / code-controlled |
| Rewritten tools | C | `agent/tools.py` | `tests/test_tools.py` | bounded domain adapters / code plus model callers / above approval line |
| Plan, checkpoint, detectors, diff | B | TODO | TODO | TODO |
| Critique loop | B | TODO | TODO | TODO |
| Test tasks and checks | A | `tasks/`, `checks/` | `tests/test_checks.py` | n/a |

## Decision table

DRAFT paths, from the switches. Each entry later gets: reason (slide), evidence, what would change it.

| Row | Path | Plan | Critique | Examples | Strict |
|---|---|---|---|---|---|
| standard_report | workflow (gate 1 fails) | | | | |
| messy_file | agent (gate 1 passes) | no (an investigation) | | | |
| compare_check | agent | | | | |
| status_question | workflow | | | | |
| out_of_scope | workflow | | | | |
| batch_reports | agent | yes (steps fixed once the request is read) | | | |
| draft_report_email | | | yes (outside signal: recompute from the sandbox) | | |
| send_ack (fixed template) | | | no (code fills the facts) | | |
| parse_file | | | | on (result-shape example) | off (no arguments) |
| query_sales | | | | on (quarter/metric calls) | on (required quarter + metric enum) |
| render_chart / save_report / pending writes | | | | off (plain contracts) | off (registry still validates) |

## Part 1: The first version (owner: A, B)

- **User, task, check.** Analyst on a sales team; distributors send a file and a question; the system
  compares with the sales database, saves a report with charts and prepares the email. TODO: the
  success check, the use cases, how the test tasks were chosen.
- **Boundary: four gates** for one agent use case and one workflow use case. TODO: Assignment 1 numbers
  (whose repository), m, f, c, break-even f, blended cost, latency.
- **Action table and approval line** (DRAFT; becomes the tool table in Part 3). Below the line: the
  emailed report. The agent has no send tool; it writes `draft_report_email`.

| Action | Tool | Read/write | Reaches | If wrong | Undo | Know? | Grid |
|---|---|---|---|---|---|---|---|
| decode file | parse_file | read | one upload | wrong figures downstream | n/a | yes | safe |
| query sales | query_sales | read | one distributor's orders | wrong data | n/a | yes | safe |
| chart | render_chart | write | artifact | wrong chart | overwrite | yes | safe |
| save report | save_report | write | report row | wrong report saved | replace by version | yes | safe |
| draft email | draft_report_email | write | pending record | none until sent | discard | yes | safe |
| draft question | draft_clarifying_question | write | pending record | none until sent | discard | yes | safe |
| email the report | none (operator, product page) | send | the distributor | wrong figures in their slides | none | partly | person approves |

- **Trifecta.** Untrusted input: the file and question. Private data: margins and other distributors'
  orders. Way out: the emailed report, behind a person. Closed by: the distributor is bound by code from
  the request record, `margins` is imported by no tool, and the email is a pending record.

## Part 2: Plan and critique (owner: B)

TODO: where each helps and where not; the Assignment 2 result cited; checkpoint; step-size lines; the
critique's check and bound; "does it know what it did?" inventory.

## Part 3: The tools (owner: C)

The model sees six tools in the fixed order below. Every model and code call crosses the same registry;
there is deliberately no send tool. `query_sales` obtains the distributor from trusted request metadata,
so a caller cannot name another distributor. T/P/A below mean transient, permanent and ambiguous.

The branch is configured for `gpt-4o-mini`; its official input/cached-input/output prices are
`$0.15/$0.075/$0.60` per million tokens in `pricing.yaml`, read 2026-10-27 from
<https://developers.openai.com/api/docs/models/gpt-4o-mini>. That page currently marks the model
deprecated. The team must confirm `make ping` succeeds or agree on a replacement on `main` before any
development/baseline call; the model must then remain fixed across every measured arm.

| Tool / action | R/W | Reach and failure consequence | Undo / know? / grid | Result bound | T / P / A contract | Callers; narrow credential |
|---|---|---|---|---|---|---|
| `parse_file` / decode upload | read | One request upload; a wrong parse corrupts later figures | n/a / explicit row count + truncation / safe | 50 rows | local I/O / missing or malformed file / none | model, code; one request's upload |
| `query_sales` / read orders | read | One bound distributor and quarter; a wrong query yields wrong report facts | n/a / totals + rows + truncation / safe | 50 product rows | locked DB / bad period or metric / none | model, code; read-only sales for bound distributor |
| `render_chart` / chart | write | One local SVG; wrong chart misstates figures | overwrite / artifact path + created flag / safe | one SVG, 20 bars | locked/local I/O / bad series / uncertain write requires read-back | model, code; one request's artifact folder |
| `save_report` / report version | write | One request report row; wrong report is saved | replace with new version / returned ID + DB read / safe | one report row | locked DB / bad kind, period or body / read DB before retry | model, code; reports for one request |
| `draft_report_email` / pending email | write | One pending record; nothing leaves until operator sends | discard / returned ID + pending read / safe above line | one pending row | locked DB / report not owned by request / read pending state before retry | model, code; pending email for one request |
| `draft_clarifying_question` / pending question | write | One pending record; no answer is fabricated | discard / returned ID + pending read / safe above line | one pending row | locked DB / invalid bounded text / read pending state before retry | model, code; pending question for one request |

The Registry checks the input schema and semantic rules before dispatch, canonicalizes string enums
case-insensitively, then validates the returned shape. A pre-call hook that raises or returns false denies
the call. Known transient failures retry twice (three attempts total) with capped exponential backoff;
ambiguous writes are never retried blindly. Unknown names receive a short generic error but are still
logged. Each trace record includes arguments, a bounded result summary, latency, derived key, attempt
count, outcome and local tool cost (`$0`). `tests/test_registry.py` includes one caller=`model` bad call
for every definition and asserts six rejected `tool_call` lines. A real-model bad-argument trace remains
pending until the shared key and Abraham's service loop are available.

### Failure shapes and the rewrite

| Misuse shape | Pre-run evidence | What the surface narrows | What remains |
|---|---|---|---|
| Right tool, wrong arguments | six bad-argument boundary tests | required fields, no unknown properties, semantic period/text checks and repair facts | valid but factually wrong values |
| Wrong tool, valid call | unknown-name and caller tests | fixed names, credentials and caller allowlists | the model may still choose the wrong valid tool |
| Correct call, misread result | result-schema test | named totals, counts, `truncated`, `created` and error flags | only an outside check can prove the model interpreted facts correctly |
| No call at all | not measurable before an integrated loop | none; plan/check diff can detect an expected missing effect | this is the standing failure shape |

`query_sales` is the expected most-used read; the baseline will replace that expectation with a measured
call count. Its first draft had one free-form `period` and a generic description. The rewrite removes
`distributor_id` from model control, makes both `period` and the `units|revenue|both` metric required,
documents empty/truncated results, gives two valid examples, binds a 50-row cap, and returns explicit
totals. The strict and examples treatments are separately switchable in `switches.yaml`.

Examples are on only for `parse_file` and `query_sales`; other schemas are plain enough that examples
would mostly spend tokens. Strict mode is on only for `query_sales`. Its schema has 2 properties, all
required, 0 optional parameters, 0 union types and one object nesting level. OpenAI's current Structured
Outputs guide, read **2026-10-27**, requires all fields and `additionalProperties: false`, and allows up
to 5,000 object properties and 10 nesting levels; it also documents up to 1,000 enum values. The schema
is therefore well inside the published limits. Source:
<https://developers.openai.com/api/docs/guides/structured-outputs>.

`scripts/definition_cost.py` builds the same backend/client as `harness/ping.py` and measures each
surface with two otherwise identical one-message calls, with and without definitions. The project-local
measurement is pending an API key. Prior evidence from Myron's Assignment 3 (repository and commit in
`docs/assignment_refs.md`) measured its five-tool first draft versus rewrite at **195 → 1,682 definition
tokens**; the derived-key arm left **0/12** duplicate-comment runs versus **6/12** in the UUID control.
Those are prior-assignment results, not this project's baseline.

### Write identity and environmental confirmation

The key is `tool:v1:sha256(canonical_json)`, where the canonical object contains the run ID (or console
session), bound request ID, tool name, and either the program-owned step ID or only the tool's declared
effect-naming fields. Report/email prose is deliberately excluded. The registry computes the key once
before retrying, and the sandbox accepts each report or pending key once.

| Write | Read that confirms the effect | If the read cannot answer |
|---|---|---|
| SVG chart | artifact path exists and has the same derived filename | return/propagate ambiguous outcome; do not create a second filename |
| report | `reports.for_request(request_id)`, matching returned ID/key | hold the run and inspect the DB before retry |
| pending report email | `pending.for_request(request_id)`, matching returned ID/key/report | hold it; the operator must not send an unconfirmed duplicate |
| pending clarification | `pending.for_request(request_id)`, matching returned ID/key/kind | hold it and ask the operator to inspect pending state |

## Part 4: Baseline and the pass (owner: C, with all)

The baseline has not been run yet. It requires the shared OpenAI key plus the merged task/check and
agent-core branches; neither is present on this branch on 2026-10-27. When integration is complete,
Myron runs `python run.py --tasks tasks/ --sweeps 3 --arm baseline` from a clean `main`, reads every
failure, commits the prediction before either measured pass arm, and recomputes this section with
`experiments/analysis/analyze.py`. No baseline number is reported before a committed run record exists.

## The team

| Part | Owner |
|---|---|
| A: domain, sandbox, product pages, test tasks, checks, action table | claudea (branch `claudea/domain`) |
| B: agent core, routing, bound, plan, critique | abraham (branch `abraham/agent-core`) |
| C: tools, registry, model config, runner, analysis, ledger, the pass | myron (branch `myron/tools-evidence`) |
| Report sections 1, 2, 3 | Part 1: claudea with boundary inputs from myron; Part 2: abraham; Part 3: myron |

## AI assistance

For owner C's work, Codex helped implement and document the registry, tools and evidence scripts. Myron
must review the schemas and claims; automated checks cover the boundary, retry/key behavior, sandbox
effects and analysis arithmetic. Real-model claims remain explicitly pending rather than inferred from
unit tests.
