# Changes

## Milestone 1

**Added:** (scaffold) SQLite sandbox for a sales database, uploads, requests, reports and pending
records (`sandbox/`); seed and demo data; product pages (requests, request, query); agent stubs
(`agent/router.py`, `bounds.py`, `registry.py`, `tools.py`, `workflows.py`, `loop.py`); switch groups;
test task `standard_report_clean` with its check and tests.

**Removed:** `tasks/example.yaml`, `checks/example.py`.

**Limited:** the agent has no send tool; the emailed report is a pending record the operator sends.
`sandbox/margins.py` is imported by no tool.

**Fixes after the baseline:** none yet.

**Reused code:** none yet (name each assignment and whose repository).
