"""Scripted model and registry/critique substitutes while team components are stubs.

Effects use the real sandbox. These doubles are not production tool implementations.
"""

import copy
import csv
import hashlib
import io
import json

from agent import critique, events
from harness import runtime
from harness.client import Usage
from sandbox import files, inbox, pending, reports, sales


def tool(name, args, call_id="call-1"):
    return {"type": "tool_use", "id": call_id, "name": name, "input": args}


class SequenceModel:
    free = True

    def __init__(self, settings=None):
        self.responses = []
        self.requests = []
        self.after_call = lambda: None

    def create(self, *, system, messages, tools):
        self.requests.append(copy.deepcopy({"system": system, "messages": messages, "tools": tools}))
        content, stop, usage = self.responses.pop(0) if self.responses else (
            [{"type": "text", "text": "Done."}], "end_turn", Usage(10, 5))
        self.after_call()
        return content, stop, "says-done", usage


class SandboxRegistry:
    def __init__(self, request_id, offered=None):
        self.request = inbox.get(request_id)
        self.calls = []
        self.failures = {}
        self.after_call = lambda: None
        self.handlers = {"parse_file": self.parse_file, "query_sales": self.query_sales,
                         "save_report": self.save_report, "draft_report_email": self.draft_report_email,
                         "draft_clarifying_question": self.draft_clarifying_question}
        self.offered = offered or list(self.handlers)

    def definitions(self):
        return [{"name": name, "description": name, "input_schema": {"type": "object", "properties": {}}}
                for name in sorted(self.offered)]

    def call(self, name, args, caller, *, step=None):
        self.calls.append({"name": name, "args": copy.deepcopy(args), "caller": caller, "step": step})
        if name in self.failures:
            result = self.failures[name]
        else:
            try:
                if name not in self.offered:
                    raise ValueError(f"Unknown tool: {name}")
                output = self.handlers[name](**args)
                result = {"ok": True, "output": output, "is_error": False, "error": None}
            except (TypeError, ValueError) as exc:
                result = {"ok": False, "output": None, "is_error": True,
                          "error": {"kind": "protocol", "message": str(exc), "retry": False}}
        runtime.trace().tool_call(int(step), {"name": name, "input": args}, result,
                                  is_error=result["is_error"])
        self.after_call()
        return result

    def key(self, name, args):
        return hashlib.sha256(json.dumps([self.request["id"], name, args], sort_keys=True).encode()).hexdigest()

    def parse_file(self, delimiter=",", decimal="."):
        content = files.read_upload(self.request["id"], self.request["file_name"])
        rows = list(csv.reader(io.StringIO(content), delimiter=delimiter))
        return {"file_name": self.request["file_name"], "columns": rows[0], "rows": rows[1:51],
                "row_count": len(rows) - 1, "truncated": len(rows) > 51}

    def query_sales(self, period):
        return sales.distributor_sales(self.request["distributor_id"], period)

    def save_report(self, kind, figures, body):
        report, created = reports.save(self.request["id"], kind, figures, body,
                                       self.key("save", [kind, figures, body]))
        return {"report_id": report["id"], "version": report["version"], "created": created}

    def draft_report_email(self, recipient, subject, body, report_id):
        record, created = pending.add("report_email", self.request["id"], self.request["thread_id"],
                                      recipient, subject, body, self.key("email", [recipient, subject, body, report_id]),
                                      report_id=report_id)
        return {"pending_id": record["id"], "created": created}

    def draft_clarifying_question(self, question):
        record, created = pending.add("clarifying_question", self.request["id"], self.request["thread_id"],
                                      self.request["contact_email"], "Clarification", question,
                                      self.key("question", question))
        return {"pending_id": record["id"], "created": created}


def revise_recipient(request_id, draft, revise, *, rounds=2):
    """External recipient check that uses the real request, with the shared critique result."""
    expected = inbox.get(request_id)["contact_email"]
    for number in range(1, rounds + 1):
        if draft["recipient"] == expected:
            runtime.trace().event(events.CRITIQUE, round=number, verdict="pass", reason="Recipient matches", changed=False)
            return critique.CritiqueResult(True, draft, number, "Recipient matches")
        reason = f"Use the request's recipient: {expected}"
        runtime.trace().event(events.CRITIQUE, round=number, verdict="revise", reason=reason, changed=False)
        draft = revise(reason)
    return critique.CritiqueResult(False, draft, rounds, "Recipient still wrong")


def hold_revision_error(request_id, draft, revise, *, rounds=2):
    """Model the published critic's conversion of callback exceptions to held drafts."""
    try:
        revise("Fix the recipient")
    except Exception as exc:
        return critique.CritiqueResult(False, draft, rounds, str(exc))
    return critique.CritiqueResult(False, draft, rounds, "Still held")
