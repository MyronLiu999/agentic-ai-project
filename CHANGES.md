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

**Abraham — B2, first fixture:** added a synthetic messy-file request with semicolon-separated
headers and decimal-comma amounts. Tests exercise the real sandbox seed and existing report check:
the upload remains intact, an empty completion claim fails, and a correct report plus pending email
passes. The fixture stays outside the official evaluation tasks. Routing and agent execution follow
in later reviewed steps.

**Abraham — B1, routing:** added request/thread selection from stored records, use-case routing
from request questions and CSV headers, switch-controlled paths, and route trace events. An
ambiguous work-versus-status message uses one metered classification call with no tools. Unknown
references, ambiguous request selection, and invalid classifier replies require clarification.
Excluded/alternative IDs and qualified batch phrases cannot silently widen request selection;
ambiguous status questions beginning with "check" use classification before any rerun.
Tests cover all six use cases using the sandbox and free scripted model responses. Service dispatch
and agent execution remain the next implementation steps.

**Abraham — B3, bounded loop:** added a request-bound model/tool loop with externally
enforced step, token, and monotonic-time limits, traced values and rationales, bounded
repair attempts, and preserved assistant/tool history. Email writes require a passed
critique over the selected request's saved report; revisions consume the same budget.
Held drafts, malformed revisions, and foreign report references leave no pending email.
Successful clarifying questions retain their pending state even when a time limit expires.
Review fixes preserve tool-step attribution, trace local rejections, expose revised
executed inputs to the model, and isolate mutable arguments/figures. Tests use the real
sandbox, metering, and traces with scripted models and substitutes for team-owned stubs.
The initial 12-call/150,000-token/90-second limits are provisional; in-flight synchronous
operations are not interrupted. Service integration and batch planning follow separately.

**Abraham — B4/B5, service:** connected public operator turns to record-based routing,
the bounded loop, and the shared workflow signatures. Status follow-ups recover request
scope from the session trace after restart; ambiguous selection asks for clarification.
Replies preserve action lines and pending questions. Request states come from recorded
effects, not a model's completion claim. Harness-level tests exercise never-stops,
each dispatch path, session follow-ups, and isolated unplanned batch requests.
