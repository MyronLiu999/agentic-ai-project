"""The critique loop and the three workflows (claudea), on fake models and FakeRegistry, inside fixed_run so
every write is stamped with the run's ID and the task's real check reads it. No tokens."""

import csv
import io
import json
import re
import unittest
from unittest import mock

from agent import critique, domain_workflows, events, workflows
from harness.client import Usage
from harness.scripted import estimate_tokens
from harness.trace import read_trace
from sandbox import charts, files, inbox, pending, reports, sales
from sandbox.stamp import current
from tests.fakes import FakeRegistry
from tests.support import ScratchTest, check_run, fixed_run

CLEAN = "tasks/standard_report_clean.yaml"
MESSY = "tasks/messy_file_semicolon.yaml"
STATUS = "tasks/status_question_done_work.yaml"
OOS = "tasks/out_of_scope_margins.yaml"
ON = ["critique.report_email=external"]
OFF = ["critique.report_email=off"]


# -- fake models: they read the figures from the prompt, as the real model is asked to --------------------

def _figures(messages):
    text = messages[-1]["content"]
    return json.loads(text[text.index("{"):text.index("}") + 1]), "A check rejected" in text


class _Writer:
    free = True
    name = "fake-writer"

    def __init__(self, settings=None):
        pass

    def body(self, figures, revising):
        raise NotImplementedError

    def create(self, *, system, messages, tools):
        figures, revising = _figures(messages)
        text = self.body(figures, revising)
        return [{"type": "text", "text": text}], "end_turn", self.name, Usage(estimate_tokens(messages), 40)


class RightWriter(_Writer):
    def body(self, f, revising):
        return f"Dear contact, your {f['period']} revenue was {f['total_revenue']:,.2f} on {f['total_units']} units."


class WrongThenRight(_Writer):
    def body(self, f, revising):
        if revising:
            return RightWriter.body(self, f, revising)
        return f"Dear contact, your {f['period']} revenue was {f['total_revenue'] + 100:,.2f}."


class AlwaysWrong(_Writer):
    def body(self, f, revising):
        return "Dear contact, your revenue was 1.00, and our margin is healthy."


# -- a FakeRegistry whose tools do what the real ones do, through the sandbox ----------------------------

def sandbox_registry(request_id):
    req = inbox.get(request_id)

    def parse(args):
        text = files.read_upload(request_id, req["file_name"])
        rows = list(csv.reader(io.StringIO(text), delimiter=args.get("delimiter", ",")))
        return {"file_name": req["file_name"], "columns": rows[0], "rows": rows[1:], "row_count": len(rows) - 1,
                "truncated": False}

    def chart(args):
        c, _ = charts.render(request_id, args["title"], args["labels"], args["values"], key=f"{current()}-chart")
        return {"chart_id": c["id"], "path": c["path"]}

    def save(args):
        r, created = reports.save(request_id, args["kind"], args["figures"], args["body"], key=f"{current()}-report")
        return {"report_id": r["id"], "version": r["version"], "created": created}

    def email(args):
        p, created = pending.add("report_email", request_id, req["thread_id"], args["recipient"], args["subject"],
                                 args["body"], key=f"{current()}-email", report_id=args["report_id"])
        return {"pending_id": p["id"], "created": created}

    def question(args):
        p, created = pending.add("clarifying_question", request_id, req["thread_id"], req["contact_email"],
                                 "About your request", args["question"], key=f"{current()}-question")
        return {"pending_id": p["id"], "created": created}

    return FakeRegistry(results={
        "parse_file": parse, "query_sales": lambda a: sales.distributor_sales(req["distributor_id"], a["period"]),
        "render_chart": chart, "save_report": save, "draft_report_email": email, "draft_clarifying_question": question})


def events_of(info, kind):
    return [x for x in read_trace(info.trace_path) if x.get("type") == kind]


def rid_of(task_file):
    from pathlib import Path

    import yaml
    return inbox.request_id(yaml.safe_load(Path(task_file).read_text())["input"]["thread"])


# -- the critique alone ---------------------------------------------------------------------------------

class CritiqueCheckTest(ScratchTest):
    def _draft(self, **change):
        req = inbox.get(self.rid)
        total = sales.distributor_sales(req["distributor_id"], req["period"])["total_revenue"]
        draft = {"recipient": req["contact_email"], "subject": "Your Q3 report",
                 "body": f"Revenue was {total:,.2f}.", "figures": {"period": req["period"], "total_revenue": total}}
        draft.update(change)
        return draft

    def test_check_reads_the_sandbox_for_recipient_period_and_figures(self):
        with fixed_run(CLEAN, "crit-check", overrides=ON):
            self.rid = rid_of(CLEAN)
            self.assertEqual(critique.check(self.rid, self._draft())[0], True)
            cases = {
                "recipient": self._draft(recipient="someone@else.example"),
                "period": self._draft(figures={"period": "2026Q2", "total_revenue": self._draft()["figures"]["total_revenue"]}),
                "total_revenue": self._draft(figures={"period": "2026Q3", "total_revenue": 1.0}),
                "does not state": self._draft(body="Revenue was strong."),
                "margins": self._draft(body=self._draft()["body"] + " Our margin is 40%."),
                "another distributor": self._draft(body=self._draft()["body"] + " SYN Brightline did worse."),
                "no subject": self._draft(subject=""),
            }
            for words, draft in cases.items():
                ok, reason = critique.check(self.rid, draft)
                self.assertFalse(ok, words)
                self.assertIn(words, reason)

    def test_run_revises_with_the_reason_then_passes(self):
        with fixed_run(CLEAN, "crit-revise", overrides=ON) as info:
            self.rid = rid_of(CLEAN)
            reasons = []
            result = critique.run(self.rid, self._draft(body="Revenue was strong."),
                                  lambda reason: reasons.append(reason) or self._draft(), rounds=2)
        self.assertTrue(result.passed)
        self.assertEqual(result.rounds, 2)
        self.assertIn("does not state the total revenue", reasons[0])
        verdicts = [(e["round"], e["verdict"]) for e in events_of(info, events.CRITIQUE)]
        self.assertEqual(verdicts, [(1, "revise"), (2, "pass")])
        self.assertEqual(events_of(info, events.CRITIQUE)[1]["changed"], ["body"])

    def test_run_holds_at_the_bound(self):
        with fixed_run(CLEAN, "crit-held", overrides=ON) as info:
            self.rid = rid_of(CLEAN)
            calls = []
            result = critique.run(self.rid, self._draft(recipient="x@y.example"),
                                  lambda reason: calls.append(1) or self._draft(recipient="x@y.example"), rounds=2)
        self.assertFalse(result.passed)
        self.assertEqual(len(calls), 1)
        self.assertEqual([e["verdict"] for e in events_of(info, events.CRITIQUE)], ["revise", "held"])

    def test_a_reviser_that_raises_holds_the_draft(self):
        with fixed_run(CLEAN, "crit-raise", overrides=ON):
            self.rid = rid_of(CLEAN)
            result = critique.run(self.rid, self._draft(body="x"), lambda reason: 1 / 0, rounds=2)
        self.assertFalse(result.passed)
        self.assertIn("ZeroDivisionError", result.reason)

    def test_off_passes_through_without_a_check(self):
        with fixed_run(CLEAN, "crit-off", overrides=OFF) as info:
            result = critique.run("REQ-none", {"body": "anything"}, lambda r: {}, rounds=2)
        self.assertTrue(result.passed)
        self.assertEqual(events_of(info, events.CRITIQUE), [])


# -- the standard_report workflow, through the critique, counting real pending records --------------------

class StandardReportWorkflowTest(ScratchTest):
    def _run(self, backend, run_id, overrides=ON, task=CLEAN):
        with fixed_run(task, run_id, backend=f"tests.test_workflows:{backend}", overrides=overrides) as info:
            rid = rid_of(task)
            reg = sandbox_registry(rid)
            reply = workflows.standard_report(run_id, rid, registry=reg)
            emails = [p for p in pending.for_request(rid) if p["stamp"] == run_id]
            status = inbox.get(rid)["status"]
        ends = [x["terminal_reason"] for x in events_of(info, "end")]
        return reply, reg, emails, status, ends, info

    def test_a_right_draft_is_written_once_and_the_tasks_check_passes(self):
        reply, reg, emails, status, ends, info = self._run("RightWriter", "wf-right")
        self.assertEqual([c["name"] for c in reg.calls],
                         ["parse_file", "query_sales", "render_chart", "save_report", "draft_report_email"])
        self.assertTrue(all(c["caller"] == "code" for c in reg.calls))
        self.assertEqual(len(emails), 1)
        self.assertEqual((status, ends), ("report_drafted", [events.DONE]))
        self.assertEqual(len(reply.actions), 5)
        result = check_run(CLEAN, "wf-right", replies=[reply.text])
        self.assertTrue(result["passed"], result["reason"])

    def test_a_wrong_draft_is_revised_with_the_reason_then_written_once(self):
        reply, reg, emails, status, ends, info = self._run("WrongThenRight", "wf-revise")
        self.assertEqual(len(emails), 1)
        self.assertEqual([e["verdict"] for e in events_of(info, events.CRITIQUE)], ["revise", "pass"])
        purposes = [m["purpose"] for m in events_of(info, "model_call")]
        self.assertEqual(purposes, ["draft_email", "revise_email"])

    def test_a_draft_failing_at_the_bound_is_never_written(self):
        reply, reg, emails, status, ends, info = self._run("AlwaysWrong", "wf-held")
        self.assertEqual(emails, [])
        self.assertNotIn("draft_report_email", [c["name"] for c in reg.calls])
        self.assertEqual((status, ends), ("held", [events.CRITIQUE_HELD]))
        self.assertIn("held", reply.text)
        self.assertFalse(check_run(CLEAN, "wf-held")["passed"])

    def test_with_the_critique_off_a_wrong_draft_goes_out_and_the_check_catches_nothing_it_did_not(self):
        reply, reg, emails, status, ends, info = self._run("AlwaysWrong", "wf-off", overrides=OFF)
        self.assertEqual(len(emails), 1)            # the switch's other arm: no outside check
        self.assertEqual(events_of(info, events.CRITIQUE), [])

    def test_an_unknown_layout_ends_the_run_without_guessing(self):
        reply, reg, emails, status, ends, info = self._run("RightWriter", "wf-messy", task=MESSY)
        self.assertEqual(ends, [events.UNKNOWN_LAYOUT])
        self.assertEqual([c["name"] for c in reg.calls], ["parse_file"])
        self.assertIn("messy-file path", reply.text)

    def test_a_failed_tool_ends_the_run_with_tool_error(self):
        with fixed_run(CLEAN, "wf-fail", backend="tests.test_workflows:RightWriter", overrides=ON) as info:
            rid = rid_of(CLEAN)
            reg = sandbox_registry(rid)
            del reg.results["query_sales"]
            reply = workflows.standard_report("wf-fail", rid, registry=reg)
            self.assertEqual(reports.for_request(rid), [])
        self.assertEqual([x["terminal_reason"] for x in events_of(info, "end")], [events.TOOL_ERROR])
        self.assertIn("query_sales failed", reply.text)


# -- status_question and out_of_scope ------------------------------------------------------------------

class DomainWorkflowTest(ScratchTest):
    def test_status_question_answers_from_records_and_writes_nothing(self):
        text = "What revenue did we report to SYN Acme Trading for Q3, and is anything still open on that request?"
        with fixed_run(STATUS, "wf-status") as info:
            reply = domain_workflows.status_question("wf-status", text)
        self.assertIn("Nothing is still open.", reply.text)
        self.assertEqual([x["terminal_reason"] for x in events_of(info, "end")], [events.DONE])
        result = check_run(STATUS, "wf-status", replies=[reply.text])
        self.assertTrue(result["passed"], result["reason"])

    def test_status_question_with_no_name_covers_every_request(self):
        with fixed_run("tasks/batch_reports_two.yaml", "wf-status-all"):
            reply = domain_workflows.status_question("wf-status-all", "Is anything open?")
        self.assertIn("REQ-SYN-thread-1301", reply.text)
        self.assertIn("REQ-SYN-thread-1302", reply.text)
        self.assertIn("2 item(s) still open", reply.text)

    def test_out_of_scope_declines_with_one_pending_reply_and_the_check_passes(self):
        with fixed_run(OOS, "wf-oos") as info:
            rid = rid_of(OOS)
            reg = sandbox_registry(rid)
            reply = domain_workflows.out_of_scope("wf-oos", rid, registry=reg)
            self.assertEqual(inbox.get(rid)["status"], "declined")
        self.assertEqual([c["name"] for c in reg.calls], ["draft_clarifying_question"])
        self.assertEqual([x["terminal_reason"] for x in events_of(info, "end")], [events.DECLINED])
        result = check_run(OOS, "wf-oos", replies=[reply.text])
        self.assertTrue(result["passed"], result["reason"])
        self.assertEqual(result["measures"]["pending_to_contact"], 1)

    def test_out_of_scope_says_so_when_the_tool_fails(self):
        with fixed_run(OOS, "wf-oos-fail") as info:
            reply = domain_workflows.out_of_scope("wf-oos-fail", rid_of(OOS), registry=FakeRegistry(results={}))
        self.assertEqual([x["terminal_reason"] for x in events_of(info, "end")], [events.TOOL_ERROR])
        self.assertIn("could not draft", reply.text)


if __name__ == "__main__":
    unittest.main()
