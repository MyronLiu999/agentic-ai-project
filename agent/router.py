"""Routing: which use case is this case, and which path does the switch give it.

Tell a case's use case from data your code can trust where possible (the request record, the file's
header fingerprint, the thread); use a traced model call as a step of its own only for the operator's
free text. The path is read from switches.yaml, control.<use_case>, so the console and run.py agree.
"""

from __future__ import annotations

from harness import runtime

USE_CASES = ("standard_report", "messy_file", "compare_check", "status_question", "out_of_scope", "batch_reports")


def path_for(use_case: str) -> str:
    """'workflow' or 'agent', from the switch."""
    if use_case not in USE_CASES:
        raise ValueError(f"unknown use case {use_case!r}")
    return runtime.switch(f"control.{use_case}")


def classify_operator_message(session_id: str, text: str) -> str:
    """TODO(agent owner): a new task or a question about work done? Which use case is the case?"""
    raise NotImplementedError("router.classify_operator_message")
