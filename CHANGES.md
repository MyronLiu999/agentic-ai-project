# Changes

## Milestone 1

**Added:** (scaffold) SQLite sandbox for a sales database, uploads, requests, reports and pending
records (`sandbox/`); seed and demo data; product pages (requests, request, query); agent stubs
(`agent/router.py`, `bounds.py`, `registry.py`, `tools.py`, `workflows.py`, `loop.py`); switch groups;
test task `standard_report_clean` with its check and tests.

**Added (myron, tools/evidence):** a validating registry with fixed tool order, caller allowlists,
fail-closed hook, bounded transient retries, result validation, derived write keys and bounded trace
records; six request-scoped sandbox tools; per-tool examples/strict switches; registry, tool,
definition-cost and analysis tests; `scripts/definition_cost.py` and
`experiments/analysis/analyze.py`; complete assignment references and the Part 3 tool evidence.

**Removed:** `tasks/example.yaml`, `checks/example.py`.

**Limited:** the agent has no send tool; the emailed report is a pending record the operator sends.
`sandbox/margins.py` is imported by no tool. File and sales reads return at most 50 rows; SVG charts
render at most 20 bars and report truncation. Known transient tool failures get at most two retries.

**Fixes after the baseline:** none yet.

**Reused code/design:** no source was copied. The stable canonical write-key and short protocol-error
design was adapted from Myron Liu's Assignment 3 repository
(`MyronLiu999/agentic-ai-assignment3`, commit `eb6b35703b212474b561099ec265c427174c7a4b`): this project
uses request/report/pending identities, the `Registry.call` contract and `SessionTrace.tool_call`.
Assignment 1 and 2 repositories supply cited measurements only.
