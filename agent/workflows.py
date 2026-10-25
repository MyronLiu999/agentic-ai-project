"""Workflows: your code picks each step and ends the run. One function per workflow use case
(standard_report, status_question, out_of_scope). Every tool call goes through the registry, and
every run ends with trace.end(<reason you name>)."""
