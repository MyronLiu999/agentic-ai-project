"""The policy and the hook (Milestone 2, Part 2 tasks 1-3; owner: myron, M5). Tests read the sandbox.

The handout's tests: a prohibited action class called through the registry, with every approval scripted to
yes, leaves the sandbox unchanged and the denial logged; a tool the policy splits by circumstance runs unasked
in one circumstance and asks in the other; a stated limit blocks the call it names. Plus the order (the stop
first), failing closed, and the policy file's own shape.
"""

import json
import unittest
from unittest import mock

import channel
from agent import disclosure
from agent.registry import CODE, MODEL
from harness import runtime
from sandbox import inbox, pending
from tests.support import ScratchTest, fixed_run

TASK = "tasks/approval_send_report.yaml"


def lines(run) -> list[dict]:
    return [json.loads(l) for l in run.trace_path.read_text(encoding="utf-8").splitlines()]


class PolicyFileTest(unittest.TestCase):
    def test_three_columns_each_class_once_and_prohibited_not_empty(self):
        from policy import hook
        policy = hook.load_policy()
        self.assertTrue(policy["independent"] and policy["requires_approval"] and policy["prohibited"])
        self.assertEqual(hook.column_of("ask_stranger/template"), "independent")
        self.assertEqual(hook.column_of("ask_stranger/model_written"), "requires_approval")
        self.assertEqual(hook.column_of("send_report_email/new_recipient"), "prohibited")
        self.assertIsNone(hook.column_of("teleport/any"))

    def test_every_catalogue_tool_has_a_class_in_a_column(self):
        from agent import tools
        from policy import hook
        for spec in tools.specs(None):
            for caller in (MODEL, CODE):
                action_class = hook.classify({"name": spec.name, "args": {}, "caller": caller})
                self.assertIsNotNone(hook.column_of(action_class), action_class)

    def test_the_model_never_sees_the_policy(self):
        from agent import loop, tools
        surface = json.dumps(tools.build(None).definitions()) + loop.SYSTEM
        for word in ("autonomy.yaml", "requires_approval", "prohibited", "policy/"):
            self.assertNotIn(word, surface)


class LimitsTest(unittest.TestCase):
    def test_stated_limits_become_rules_in_code(self):
        from policy import limits
        cases = {
            "Send nothing until I have read it.": ("sends/*", "ask"),
            "Please don't send anything before I review it": ("sends/*", "ask"),
            "Ask me before you send anything": ("sends/*", "ask"),
            "Do not send any emails today": ("send_report_email/*", "deny"),
            "Don't send anything": ("sends/*", "deny"),
            "Do not contact the distributor": ("ask_stranger/*", "deny"),
            "No charts this time": ("render_chart/*", "deny"),
        }
        for text, (action_class, effect) in cases.items():
            rule = limits.parse_limit(text)
            self.assertIsNotNone(rule, text)
            self.assertEqual((rule["action_class"], rule["effect"], rule["source_text"]),
                             (action_class, effect, text.strip()), text)

    def test_ordinary_messages_and_commands_state_no_limit(self):
        from policy import limits
        for text in ("Handle the new request on the outside channel.", "What did you do, and is anything open?",
                     "/stop", "/rollback 2", "Make the reports for all new requests and draft their emails", ""):
            self.assertIsNone(limits.parse_limit(text), text)


class HookTest(ScratchTest):
    def draft(self, rid, recipient=None, body="SYNTHETIC. Revenue was 1.00."):
        """A drafted report email, written straight to the sandbox (with the line, as a caller adds it)."""
        from sandbox import reports
        request = inbox.get(rid)
        report, _ = reports.save(rid, "standard", {"period": "2026Q3", "total_revenue": 1.0}, "r", key=f"rep-{recipient}")
        record, _ = pending.add("report_email", rid, request["thread_id"], recipient or request["contact_email"],
                                "Your report", disclosure.with_disclosure(body), key=f"draft-{recipient}",
                                report_id=report["id"])
        return record

    def test_a_prohibited_class_with_every_approval_yes_leaves_the_sandbox_unchanged(self):
        from agent import runs, tools
        with fixed_run(TASK, "hook-prohibited") as run:
            runs.new_run(run.run_id)
            rid = inbox.all_requests()[0]["id"]
            record = self.draft(rid, recipient="someone.else@example.net")
            registry = tools.build(rid)
            before = len(channel.messages(record["thread_id"]))
            with mock.patch("agent.approvals.is_approved", return_value=True), \
                    mock.patch("agent.approvals.plan_covers", return_value=True):
                result = registry.call("send_report_email", {"pending_id": record["id"]}, MODEL)
            self.assertEqual(result["error"]["type"], "policy_denied")
            self.assertEqual(len(channel.messages(record["thread_id"])), before)
            self.assertEqual(pending.get(record["id"])["status"], "pending")
        denials = [l for l in lines(run) if l.get("type") == "hook_decision" and l.get("answer") == "deny"]
        self.assertEqual(denials[-1]["action_class"], "send_report_email/new_recipient")
        self.assertTrue(any(l.get("type") == "tool_call" and l.get("outcome") == "denied" for l in lines(run)))

    def test_another_distributor_and_margins_are_prohibited(self):
        from policy import hook
        with fixed_run(TASK, "hook-other"):
            rid = inbox.all_requests()[0]["id"]
            other = hook.decide({"name": "query_sales", "args": {"distributor_id": "SYN-DIST-001"},
                                 "caller": MODEL, "request_id": rid}, {"run_key": "hook-other"})
            margins = hook.decide({"name": "read_margins", "args": {}, "caller": CODE, "request_id": rid},
                                  {"run_key": "hook-other"})
        self.assertEqual((other["answer"], other["action_class"]), ("deny", "query_sales/other_distributor"))
        self.assertEqual((margins["answer"], margins["action_class"]), ("deny", "read_margins/any"))

    def test_a_split_tool_runs_unasked_in_one_circumstance_and_asks_in_the_other(self):
        from agent import approvals, runs, tools
        with fixed_run(TASK, "hook-split"):
            runs.new_run("hook-split")
            rid = inbox.all_requests()[0]["id"]
            thread = inbox.get(rid)["thread_id"]
            registry = tools.build(rid)
            question = disclosure.with_disclosure("SYNTHETIC. Which column holds the units?")
            template = registry.call("ask_stranger", {"question": question}, CODE)
            self.assertTrue(template["ok"], template)
            self.assertEqual(len([m for m in channel.messages(thread) if m.sender == channel.AGENT]), 1)
            written = registry.call("ask_stranger", {"question": disclosure.with_disclosure("SYNTHETIC. Why?")},
                                    MODEL)
            self.assertEqual(written["error"]["type"], "approval_required")
            self.assertEqual(written["error"]["action_class"], "ask_stranger/model_written")
            self.assertEqual(len([m for m in channel.messages(thread) if m.sender == channel.AGENT]), 1)
            self.assertEqual([p["action_class"] for p in approvals.pending()], ["ask_stranger/model_written"])

    def test_a_stated_limit_blocks_the_call_it_names(self):
        from agent import runs, tools
        from harness import turns
        from policy import rules
        with fixed_run(TASK, "hook-limit"):
            turns.operator_turn("hook-limit", "Send nothing until I have read it.")   # the service's seam parses it
            self.assertEqual(rules.rules_for("hook-limit")[0]["action_class"], "sends/*")
            runs.new_run("hook-limit")
            rid = inbox.all_requests()[0]["id"]
            thread = inbox.get(rid)["thread_id"]
            asked = tools.build(rid).call("ask_stranger", {"question": disclosure.with_disclosure("Units?")}, CODE)
            self.assertEqual(asked["error"]["type"], "approval_required")   # independent, until the limit
            self.assertFalse([m for m in channel.messages(thread) if m.sender == channel.AGENT])
            turns.operator_turn("hook-limit", "Do not send any emails.")
            record = self.draft(rid)
            sent = tools.build(rid).call("send_report_email", {"pending_id": record["id"]}, MODEL)
            self.assertEqual(sent["error"]["type"], "policy_denied")
            self.assertIn("Do not send any emails", sent["error"]["repair"])

    def test_the_stop_comes_first(self):
        from agent import runs
        from policy import flags, hook
        with fixed_run(TASK, "hook-stop"):
            key = runs.new_run("hook-stop")
            flags.stop_run(key)
            decision = hook.decide({"name": "read_margins", "args": {}, "caller": CODE}, {"run_key": key})
        self.assertEqual((decision["answer"], decision["error_type"]), ("deny", "stopped"))

    def test_a_hook_that_raises_denies(self):
        from agent import tools
        with fixed_run(TASK, "hook-raises"):
            rid = inbox.all_requests()[0]["id"]
            with mock.patch("policy.hook.classify", side_effect=RuntimeError("policy unreadable")):
                result = tools.build(rid).call("parse_file", {}, MODEL)
        self.assertEqual(result["error"]["type"], "hook_denied")

    def test_an_unclassified_tool_is_denied(self):
        from policy import hook
        decision = hook.decide({"name": "delete_everything", "args": {}, "caller": MODEL}, {"run_key": None})
        self.assertEqual((decision["answer"], decision["action_class"]), ("deny", "delete_everything/unclassified"))

    def test_an_undisclosed_send_is_refused_and_logged(self):
        from agent import tools
        with fixed_run(TASK, "hook-undisclosed") as run:
            rid = inbox.all_requests()[0]["id"]
            result = tools.build(rid).call("ask_stranger", {"question": "Which column holds units?"}, CODE)
        self.assertEqual(result["error"]["type"], "undisclosed")
        self.assertTrue(any(l.get("type") == "disclosure_refused" for l in lines(run)))


if __name__ == "__main__":
    unittest.main()
