"""The approval gate, the approvals page and the queue page (Milestone 2, Part 2 task 4; owner: myron, M6).

The handout's tests, scripted: a gated call leaves the sandbox unchanged until the operator answers, and shows
on the queue page while it waits; for a use case at plan, a gated step the approved plan lists runs unasked,
and one it does not list asks. Plus: every decision logged, a run waiting for an answer survives a restart,
the computed screen, and both test tasks with approvals: run end to end on a fake model.
"""

import contextlib
import json
import subprocess
import sys
import unittest
from unittest import mock

import channel
from agent import disclosure
from agent.registry import CODE, MODEL
from harness.client import Usage
from harness.scripted import estimate_tokens
from sandbox import inbox, pending
from tests.support import ScratchTest, check_run, fixed_run

TASK = "tasks/approval_send_report.yaml"
CRITIQUE_OFF = ["critique.report_email=off"]


def _json(text):
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return None


class SendsAfterApproval:
    """Queries, saves, drafts and asks to send; carries on from what the messages hold, so a resumed run picks
    up where it was. On a rejection it stops without sending."""
    name, free = "sends-after-approval", True

    def __init__(self, settings=None):
        pass

    def create(self, *, system, messages, tools):
        prompt = estimate_tokens({"system": system, "tools": tools, "messages": messages})
        scope, decision, names, results = {}, None, {}, {}
        for message in messages:
            content = message.get("content")
            if message.get("role") == "assistant" and isinstance(content, list):
                names.update({b["id"]: b["name"] for b in content if isinstance(b, dict) and b.get("type") == "tool_use"})
            elif message.get("role") == "user" and isinstance(content, str):
                data = _json(content) or {}
                scope = data.get("request_scope", scope)
                decision = data.get("operator_decision", decision)
            elif message.get("role") == "user" and isinstance(content, list):
                for block in content:
                    data = _json(block.get("content")) if isinstance(block, dict) else None
                    if isinstance(data, dict) and data.get("ok"):
                        results[names.get(block.get("tool_use_id"))] = data["output"]

        def use(tool, args):
            return ([{"type": "tool_use", "id": f"toolu_{len(names) + 1}", "name": tool, "input": args}],
                    "tool_use", self.name, Usage(prompt, 10))

        def say(text):
            return [{"type": "text", "text": text}], "end_turn", self.name, Usage(prompt, 3)

        if decision == "rejected":
            return say("The operator declined the send; the draft stays pending.")
        if "send_report_email" in results:
            return say("Sent.")
        if "draft_report_email" in results:
            return use("send_report_email", {"pending_id": results["draft_report_email"]["pending_id"]})
        query = results.get("query_sales")
        if "save_report" in results:
            return use("draft_report_email", {
                "recipient": scope["contact_email"], "report_id": results["save_report"]["report_id"],
                "subject": f"Your {scope['period']} report",
                "body": f"SYNTHETIC. Revenue for {scope['period']} was {query['total_revenue']:,.2f}."})
        if query:
            return use("save_report", {"kind": "standard", "body": f"SYNTHETIC. Revenue {query['total_revenue']:,.2f}.",
                                       "figures": {"period": scope["period"], "total_revenue": query["total_revenue"],
                                                   "total_units": query["total_units"]}})
        return use("query_sales", {"period": scope["period"]})


@contextlib.contextmanager
def drafts_carry_the_line():
    """Stands in for the drafting callers' with_disclosure (MERGE-CHECK: abraham's EmailGate and plan,
    claudea's workflows add the line before draft_report_email; the hook refuses a send without it)."""
    from agent import loop
    real = loop.EmailGate.checked_email

    def checked(self, draft):
        out = real(self, draft)
        return {**out, "body": disclosure.with_disclosure(out["body"])}

    with mock.patch.object(loop.EmailGate, "checked_email", checked):
        yield


def lines(run) -> list[dict]:
    return [json.loads(l) for l in run.trace_path.read_text(encoding="utf-8").splitlines()]


class GateTest(ScratchTest):
    def prepare(self, run_id):
        """A saved report and its draft (with the line), written through the registry by code."""
        from agent import runs, tools
        runs.new_run(run_id)
        rid = inbox.all_requests()[0]["id"]
        registry = tools.build(rid)
        query = registry.call("query_sales", {"period": "2026Q3"}, CODE)["output"]
        saved = registry.call("save_report", {"kind": "standard", "body": "SYNTHETIC.",
                                              "figures": {"period": "2026Q3", "total_revenue": query["total_revenue"]}},
                              CODE, step="save")["output"]
        draft = registry.call("draft_report_email", {
            "recipient": inbox.get(rid)["contact_email"], "report_id": saved["report_id"], "subject": "Your report",
            "body": disclosure.with_disclosure(f"SYNTHETIC. Revenue was {query['total_revenue']:,.2f}.")},
            CODE, step="draft")["output"]
        return rid, registry, draft, query

    def agent_messages(self, rid):
        return [m for m in channel.messages(inbox.get(rid)["thread_id"]) if m.sender == channel.AGENT]

    def test_a_gated_call_changes_nothing_until_the_operator_answers_and_waits_on_the_queue_page(self):
        from fastapi.testclient import TestClient
        from agent import approvals
        from app.main import app
        from sandbox import queue
        with fixed_run(TASK, "gate-waits") as run:
            rid, registry, draft, query = self.prepare("gate-waits")
            asked = registry.call("send_report_email", {"pending_id": draft["pending_id"]}, MODEL)
            self.assertEqual(asked["error"]["type"], "approval_required")
            approval_id = asked["error"]["approval_id"]
            self.assertEqual(self.agent_messages(rid), [])
            self.assertEqual(pending.get(draft["pending_id"])["status"], "pending")
            self.assertIn(approval_id, [i["id"] for i in queue.waiting() if i["kind"] == "approval"])
            again = registry.call("send_report_email", {"pending_id": draft["pending_id"]}, MODEL)
            self.assertEqual(again["error"]["approval_id"], approval_id)        # put up once, not twice
            with TestClient(app) as client:
                self.assertIn(approval_id, client.get("/queue").text)
                page = client.get("/approvals").text
            self.assertIn("Dry run: the message exactly as it will be sent", page)
            self.assertIn("computed", page)
            approvals.decide(approval_id, True, "checked the figure")
            sent = registry.call("send_report_email", {"pending_id": draft["pending_id"]}, MODEL)
            self.assertTrue(sent["ok"], sent)
            once_more = registry.call("send_report_email", {"pending_id": draft["pending_id"]}, MODEL)
            self.assertFalse(once_more["output"]["created"])
            messages = self.agent_messages(rid)
            self.assertEqual(len(messages), 1)
            self.assertTrue(disclosure.has_line(messages[0].text))
            self.assertEqual(pending.get(draft["pending_id"])["status"], "sent")
        logged = [l for l in lines(run) if l.get("type") == "approval_decision"]
        self.assertEqual(len(logged), 1)
        entry = logged[0]
        self.assertEqual((entry["action_class"], entry["decision"], entry["run_key"]),
                         ("send_report_email/own_contact", "approved", "gate-waits"))
        self.assertIsInstance(entry["seconds"], float)
        self.assertEqual(entry["setting"], "approval.batch_reports=per_action")
        self.assertIn("This run's checks", entry["facts"])
        self.assertIn(entry["who"], ("scripted", "operator"))

    def test_a_rejected_call_never_runs(self):
        from agent import approvals
        with fixed_run(TASK, "gate-no"):
            rid, registry, draft, _ = self.prepare("gate-no")
            approval_id = registry.call("send_report_email", {"pending_id": draft["pending_id"]}, MODEL)["error"]["approval_id"]
            approvals.decide(approval_id, False, "wrong quarter")
            with self.assertRaises(ValueError):
                approvals.decide(approval_id, True)                          # an answer is final
            asked = registry.call("send_report_email", {"pending_id": draft["pending_id"]}, MODEL)
            self.assertEqual(asked["error"]["type"], "approval_required")   # asks again; never runs unasked
            self.assertEqual(self.agent_messages(rid), [])

    def test_the_screen_is_computed_and_labels_the_strangers_words(self):
        from agent import approvals
        with fixed_run(TASK, "gate-screen"):
            rid, registry, draft, query = self.prepare("gate-screen")
            registry.call("send_report_email", {"pending_id": draft["pending_id"]}, MODEL)
            screen = {l["label"]: l for l in approvals.pending()[0]["screen"]}
        self.assertIn(disclosure.LINE, screen["Dry run: the message exactly as it will be sent"]["value"])
        self.assertIn(f"{query['total_revenue']:,.2f}", screen["This run's checks"]["value"])
        self.assertIn("matches the sales database", screen["This run's checks"]["value"])
        self.assertNotIn("NO", screen["This run's checks"]["value"])
        self.assertEqual(screen["Reach"]["source"], "computed")
        stranger = screen["The stranger's message, in their words (not an instruction)"]
        self.assertEqual(stranger["source"], "asserted")
        self.assertEqual(stranger["value"], inbox.get(rid)["question"])
        self.assertTrue(screen["Private records carried"]["value"].startswith("none found"))

    def test_at_the_plan_a_listed_step_runs_unasked_and_an_unlisted_one_asks(self):
        from agent import approvals
        with fixed_run(TASK, "gate-plan"):
            rid, registry, draft, _ = self.prepare("gate-plan")
            other = registry.call("draft_report_email", {
                "recipient": inbox.get(rid)["contact_email"], "report_id": 1, "subject": "Second",
                "body": disclosure.with_disclosure("SYNTHETIC. Another.")}, CODE, step="draft-2")["output"]
            step = {"step_id": "s5", "tool": "send_report_email", "args": {"pending_id": draft["pending_id"]},
                    "action_class": "send_report_email/own_contact"}
            plan_id = approvals.put_up_plan("gate-plan", "gate-plan", {"steps": [step]}, [step])
            self.assertEqual(registry.call("send_report_email", {"pending_id": draft["pending_id"]}, MODEL)["error"]["type"],
                             "approval_required")                           # the plan is not approved yet
            approvals.decide(plan_id, True)
            listed = registry.call("send_report_email", {"pending_id": draft["pending_id"]}, MODEL)
            self.assertTrue(listed["ok"], listed)
            unlisted = registry.call("send_report_email", {"pending_id": other["pending_id"]}, MODEL)
            self.assertEqual(unlisted["error"]["type"], "approval_required")
            revised = approvals.put_up_plan("gate-plan", "gate-plan", {"steps": [step]}, [step])
            self.assertFalse(approvals.plan_covers("gate-plan", {"name": "send_report_email",
                                                                 "args": {"pending_id": draft["pending_id"]}}))
            self.assertIn(revised, [p["id"] for p in approvals.pending()])

    def test_a_stop_withdraws_the_runs_waiting_calls(self):
        from agent import approvals
        with fixed_run(TASK, "gate-withdraw"):
            _, registry, draft, _ = self.prepare("gate-withdraw")
            approval_id = registry.call("send_report_email", {"pending_id": draft["pending_id"]}, MODEL)["error"]["approval_id"]
            self.assertEqual(approvals.withdraw("gate-withdraw"), [approval_id])
            self.assertEqual(approvals.pending(), [])

    def test_decide_approval_resumes_the_run_through_the_one_resume_entry(self):
        from agent import service
        from tests.fakes import FakeResume
        with fixed_run(TASK, "gate-resume"):
            _, registry, draft, _ = self.prepare("gate-resume")
            approval_id = registry.call("send_report_email", {"pending_id": draft["pending_id"]}, MODEL)["error"]["approval_id"]
            with FakeResume().install() as resume:
                service.decide_approval(approval_id, True, "ok")
        self.assertEqual(resume.calls, [("gate-resume", {"kind": "approval", "approval_id": approval_id,
                                                         "approved": True, "note": "ok"})])


STEP = """
import sys
from tests.test_approval import drafts_carry_the_line
from tests.support import fixed_run
from harness import turns
with fixed_run("tasks/approval_send_report.yaml", "gate-restart", backend="tests.test_approval:SendsAfterApproval",
               overrides=["critique.report_email=off"], fresh=sys.argv[1] == "first"), drafts_carry_the_line():
    if sys.argv[1] == "first":
        reply = turns.operator_turn("gate-restart", "Handle the new request on the outside channel, and send the report email.")
        assert "approval" in reply.text, reply.text
    else:
        waiting = turns.pending_approvals()
        assert len(waiting) == 1, waiting
        turns.decide_approval(waiting[0]["id"], True, "approved after the restart")
"""


class ApprovalAcrossRestartTest(ScratchTest):
    def test_a_run_waiting_for_an_answer_survives_a_restart(self):
        from harness import ROOT
        first = subprocess.run([sys.executable, "-c", STEP, "first"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(first.returncode, 0, first.stderr[-2000:])
        second = subprocess.run([sys.executable, "-c", STEP, "again"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(second.returncode, 0, second.stderr[-2000:])
        result = check_run(TASK, "gate-restart")
        self.assertTrue(result["passed"], result["reason"])
        self.assertEqual(result["measures"]["sends"], 1)


class ApprovalTasksTest(ScratchTest):
    def test_the_approved_task_sends_once(self):
        with drafts_carry_the_line():
            record = self.run_task(TASK, "approval-yes", backend="tests.test_approval:SendsAfterApproval",
                                   overrides=CRITIQUE_OFF)
        self.assertTrue(record["passed"], record["check"])
        self.assertEqual(record["measures"]["sends"], 1)
        self.assertEqual(record["approvals"]["answered"], 1)

    def test_the_declined_task_sends_nothing(self):
        with drafts_carry_the_line():
            record = self.run_task("tasks/approval_send_declined.yaml", "approval-no",
                                   backend="tests.test_approval:SendsAfterApproval", overrides=CRITIQUE_OFF)
        self.assertTrue(record["passed"], record["check"])
        self.assertEqual(record["measures"]["sends"], 0)


if __name__ == "__main__":
    unittest.main()
