"""The two small domain workflows (owner: claudea). Stubs until claudea builds them; the router
(abraham) calls them for the status_question and out_of_scope use cases.

    status_question(session_id, text) -> Reply     answers from records
    out_of_scope(session_id, request_id) -> Reply  declines as a pending record

Each ends the run with trace.end(...) and calls tools only through the registry.
"""

from __future__ import annotations

from harness.turns import Reply


def status_question(session_id: str, text: str) -> Reply:
    raise NotImplementedError("domain_workflows.status_question")


def out_of_scope(session_id: str, request_id: str) -> Reply:
    raise NotImplementedError("domain_workflows.out_of_scope")
