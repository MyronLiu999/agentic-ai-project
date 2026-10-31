# Changes

## Milestone 1

**Added:** (scaffold) SQLite sandbox for a sales database, uploads, requests, reports and pending
records (`sandbox/`); seed and demo data; product pages (requests, request, query); agent stubs
(`agent/router.py`, `bounds.py`, `registry.py`, `tools.py`, `workflows.py`, `loop.py`); switch groups;
test task `standard_report_clean` with its check and tests.
- (claudea) Sandbox: `sandbox/charts.py` (keyed SVG charts, a `charts` table), report and request helpers, seed
  `history:` for work already done. Five more test tasks and a dev task, one check each (`checks/common.py` holds
  the shared reads) with their tests. The critique loop (`agent/critique.py`), the `standard_report` workflow
  (`agent/workflows.py`), `status_question` and `out_of_scope` (`agent/domain_workflows.py`). Product page: charts,
  the change from last quarter, a form to email a report by hand. `experiments/analysis/analyze.py`. End reasons
  `tool_error` and `unknown_layout` in `agent/events.py`.

**Removed:** `tasks/example.yaml`, `checks/example.py`.

**Limited:** the agent has no send tool; the emailed report is a pending record the operator sends.
`sandbox/margins.py` is imported by no tool.
- (claudea) The hand email form always sends to the request's own contact (no free recipient). The
  `standard_report` workflow refuses a file that is not the known layout (`unknown_layout`) rather than guess.

**Fixes after the baseline:** none yet.

**Reused code:** none yet (name each assignment and whose repository).
