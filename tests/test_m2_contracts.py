"""The Milestone 2 setup's shared contracts (PLAN_M2.md section 3), pinned so a branch that breaks one
fails here, on its own branch, and not at the merge. Each module's owner adds their own tests elsewhere;
change these only with the contract (tell the other two first)."""

import json
import unittest
from unittest import mock

from tests.support import ScratchTest, fixed_run


def _registry(specs, hook=None):
    from agent.registry import Registry
    return Registry(specs, key_context="REQ-test", pre_call_hook=hook, sleep=lambda s: None)


def _spec(name, fn, writes=False, **kw):
    from agent.registry import CODE, MODEL, ToolSpec
    schema = kw.pop("schema", {"type": "object", "properties": {}, "additionalProperties": True})
    return ToolSpec(name, f"{name} (test)", schema, fn, callers=(MODEL, CODE), writes=writes, **kw)


class EventNamesTest(unittest.TestCase):
    def test_no_event_kind_is_a_line_the_harness_writes(self):
        from agent import events
        from harness.formats import RESERVED_TYPES
        names = [v for k, v in vars(events).items() if k.isupper() and isinstance(v, str)]
        self.assertEqual([n for n in names if n in RESERVED_TYPES], [])
        self.assertEqual(len(names), len(set(names)))


class RunKeysAndCheckpointsTest(ScratchTest):
    def test_run_keys(self):
        from agent import runs
        self.assertEqual(runs.key(run_id="R1"), "R1")
        self.assertEqual(runs.key(session_id="S", run_no=3), "S#3")
        self.assertEqual(runs.session_of("S#3"), "S")
        self.assertTrue(runs.first_turn("S"))
        first, second = runs.new_run("S"), runs.new_run("S")
        self.assertEqual((first, second), ("S#1", "S#2"))
        self.assertFalse(runs.first_turn("S"))
        self.assertEqual(runs.current_key("S"), "S#2")
        runs.end("S#1", "done")
        runs.end("S#2", "needs_answer")          # a waiting run stays live
        self.assertEqual(runs.live("S"), ["S#2"])
        self.assertIsNone(runs.current_key("nobody"))

    def test_checkpoint_store(self):
        from agent import checkpoints
        self.assertIsNone(checkpoints.load("S#1"))
        checkpoints.save("S#1", {"path": "agent", "current_step": "a", "completed_calls": []})
        checkpoints.update("S#1", current_step="b")
        self.assertEqual(checkpoints.load("S#1")["current_step"], "b")
        self.assertEqual([s["current_step"] for s in checkpoints.history("S#1")], ["a", "b"])
        with self.assertRaises(TypeError):
            checkpoints.save("S#1", {"open": object()})       # everything must serialize
        with self.assertRaises(ValueError):
            checkpoints.save("S#1", {}, mode="later")

    def test_journal_and_waits(self):
        from agent import checkpoints
        ok = {"ok": True, "output": {"report_id": 7}, "is_error": False, "error": None}
        checkpoints.after_call("S#1", {"tool": "save_report", "args": {"kind": "standard"}, "key": "k1"}, ok)
        checkpoints.after_call("S#1", {"tool": "save_report", "args": {}, "key": "k1"}, ok)   # once per key
        self.assertEqual(checkpoints.completed("S#1", "k1"), ok)
        self.assertIsNone(checkpoints.completed("S#1", "k2"))
        self.assertEqual(len(checkpoints.load("S#1")["completed_calls"]), 1)
        checkpoints.set_wait("S#1", "approval", "apr-1", deadline="2026-11-21T00:00:00+00:00")
        self.assertEqual([(w["kind"], w["ref"]) for w in checkpoints.waiting("S")], [("approval", "apr-1")])
        self.assertEqual(checkpoints.load("S#1")["waiting_for"]["ref"], "apr-1")
        checkpoints.clear_wait("S#1")
        self.assertEqual(checkpoints.waiting(), [])

    def test_sandbox_reset_clears_control_state(self):
        from agent import checkpoints, runs
        from sandbox import seed
        runs.new_run("S")
        checkpoints.save("S#1", {"path": "agent"})
        seed.reset()
        self.assertIsNone(checkpoints.load("S#1"))
        self.assertTrue(runs.first_turn("S"))


class FlagsAndRulesTest(ScratchTest):
    def test_session_stop_reaches_earlier_runs_only(self):
        from agent import runs
        from policy import flags
        earlier = runs.new_run("S")
        flags.set_stop("S", at="2999-01-01T00:00:00.000+00:00")
        self.assertTrue(flags.is_stopped(earlier))
        with mock.patch("sandbox.control.now", return_value="3000-01-01T00:00:00.000+00:00"):
            later = runs.new_run("S")
        self.assertFalse(flags.is_stopped(later))
        flags.clear_stop(earlier)
        self.assertFalse(flags.is_stopped(earlier))
        self.assertFalse(flags.is_stopped(None))

    def test_one_run_stop(self):
        from agent import runs
        from policy import flags
        a, b = runs.new_run("S"), runs.new_run("S")
        flags.set_stop("S", 2)
        self.assertEqual((flags.is_stopped(a), flags.is_stopped(b)), (False, True))

    def test_rules(self):
        from policy import rules
        rules.add_rule("S", {"action_class": "send_report_email/*", "effect": "deny",
                             "source_text": "send nothing until I have read it"})
        self.assertEqual(rules.rules_for("S")[0]["effect"], "deny")
        self.assertEqual(rules.rules_for("other"), [])
        with self.assertRaises(ValueError):
            rules.add_rule("S", {"action_class": "x", "effect": "maybe"})


class DisclosureAndHookTest(ScratchTest):
    def test_disclosure_line(self):
        from agent import disclosure
        once = disclosure.with_disclosure("Which column holds units?")
        self.assertTrue(disclosure.has_line(once))
        self.assertEqual(disclosure.with_disclosure(once), once)
        self.assertFalse(disclosure.check({"name": "ask_stranger", "args": {"question": "Which column?"}}))
        self.assertTrue(disclosure.check({"name": "ask_stranger", "args": {"question": once}}))
        self.assertTrue(disclosure.check({"name": "parse_file", "args": {}}))

    def test_hook_order_stop_first(self):
        from agent import runs
        from policy import flags, hook
        run_key = runs.new_run("S")
        flags.stop_run(run_key)
        decision = hook.decide({"name": "ask_stranger", "args": {"question": "no line"}}, {"run_key": run_key})
        self.assertEqual((decision["answer"], decision["error_type"]), ("deny", "stopped"))

    def test_registry_refuses_an_undisclosed_send(self):
        from policy import hook
        sent = []
        reg = _registry([_spec("ask_stranger", lambda question, key: sent.append(question) or {"thread_id": "t"},
                               writes=True)], hook=hook.registry_hook("REQ-test"))
        result = reg.call("ask_stranger", {"question": "Which column holds units?"}, "model")
        self.assertEqual((result["ok"], result["error"]["type"]), (False, "undisclosed"))
        self.assertEqual(sent, [])
        from agent import disclosure
        self.assertTrue(reg.call("ask_stranger", {"question": disclosure.with_disclosure("Which column?")},
                                 "model")["ok"])

    def test_registry_ask_puts_up_an_approval_and_runs_nothing(self):
        from tests.fakes import FakeApprovals, FakeHook
        ran = []
        reg = _registry([_spec("send_report_email", lambda key, **a: ran.append(a) or {"sent_id": 1}, writes=True)],
                        hook=FakeHook({"send_report_email": "ask"}))
        with FakeApprovals().install() as approvals:
            result = reg.call("send_report_email", {"pending_id": 3}, "model")
        self.assertEqual((result["error"]["type"], result["error"]["kind"]), ("approval_required", "approval_required"))
        self.assertEqual(ran, [])
        self.assertEqual([i["id"] for i in approvals.pending()], [result["error"]["approval_id"]])

    def test_a_hook_answer_that_is_not_allow_denies(self):
        from tests.fakes import FakeHook
        reg = _registry([_spec("parse_file", lambda: {"rows": []})], hook=FakeHook({"parse_file": "maybe"}))
        self.assertEqual(reg.call("parse_file", {}, "model")["error"]["type"], "policy_denied")

    def test_journal_is_read_only_while_resuming(self):
        from agent import checkpoints, runs
        calls = []
        reg = _registry([_spec("save_report", lambda key, **a: calls.append(key) or {"report_id": len(calls)},
                               writes=True)])
        with mock.patch("agent.runs.current_key", return_value="S#1"):
            first = reg.call("save_report", {"kind": "standard"}, "code", step="4-save")
            self.assertEqual(len(calls), 1)
            self.assertIsNotNone(checkpoints.completed("S#1", calls[0]))
            with runs._resume_scope("S#1"):
                again = reg.call("save_report", {"kind": "standard"}, "code", step="4-save")
        self.assertEqual(len(calls), 1)                      # not run twice
        self.assertEqual(again["output"], first["output"])

    def test_compensate(self):
        reg = _registry([_spec("save_report", lambda key, **a: {}, writes=True,
                               compensate=lambda record: {"reverted": record["key"]}),
                         _spec("send_report_email", lambda key, **a: {}, writes=True)])
        self.assertEqual(reg.compensate({"tool": "save_report", "key": "k"})["result"], {"reverted": "k"})
        self.assertEqual(reg.compensate({"tool": "send_report_email", "key": "k"})["compensated_by"], "none")


class DisclosureInChecksTest(ScratchTest):
    def test_the_checks_copy_of_the_line_is_the_agents(self):
        from agent import disclosure
        from checks import helpers
        self.assertEqual(helpers.DISCLOSURE, disclosure.LINE)

    def test_every_check_fails_an_undisclosed_message(self):
        import channel
        from checks.helpers import requires_disclosure

        @requires_disclosure
        def always_passes(run):
            return True, "fine", {"n": 1}

        def plant(run):
            channel.send("T-undisclosed", "Your report is ready.")      # the agent, without the line

        result = self.run_check("tasks/standard_report_clean.yaml", plant)
        self.assertFalse(result["passed"])          # the real check fails too: nothing was saved
        with mock.patch("checks.helpers.undisclosed", return_value=[object()]):
            self.assertEqual(always_passes(None)[0], False)
        with mock.patch("checks.helpers.undisclosed", return_value=[]):
            self.assertEqual(always_passes(None), (True, "fine", {"n": 1}))

    def test_undisclosed_send_through_the_registry_leaves_the_thread_unchanged(self):
        import channel
        from policy import hook
        sends = lambda question, key: {"message_id": channel.send("T-1", question).id}
        reg = _registry([_spec("ask_stranger", sends, writes=True)], hook=hook.registry_hook("REQ-test"))
        with fixed_run("tasks/standard_report_clean.yaml", "m2-disclosure"):
            before = len(channel.messages("T-1"))
            result = reg.call("ask_stranger", {"question": "Which column holds units?"}, "model")
            self.assertEqual(len(channel.messages("T-1")), before)
            from harness import runtime
            lines = runtime.trace().lines()
        self.assertEqual(result["error"]["type"], "undisclosed")
        self.assertTrue(any(l.get("type") == "hook_decision" and l.get("answer") == "deny" for l in lines))
        self.assertTrue(any(l.get("type") == "tool_call" and l.get("outcome") == "denied" for l in lines))


class PlanApprovalAndCompensationContractTest(ScratchTest):
    def test_plan_approval_covers_only_the_listed_call(self):
        from tests.fakes import FakeApprovals
        approvals = FakeApprovals()
        step = {"step_id": "s5", "tool": "send_report_email", "args": {"pending_id": 3},
                "action_class": "send_report_email/own_contact"}
        approval_id = approvals.put_up_plan("S#1", "S", {"steps": [step]}, [step])
        self.assertFalse(approvals.plan_covers("S#1", {"name": "send_report_email", "args": {"pending_id": 3}}))
        approvals.decide(approval_id, True)
        self.assertTrue(approvals.plan_covers("S#1", {"name": "send_report_email", "args": {"pending_id": 3}}))
        self.assertFalse(approvals.plan_covers("S#1", {"name": "send_report_email", "args": {"pending_id": 4}}))

    def test_the_real_module_has_the_contract(self):
        from agent import approvals, compensations
        for name in ("put_up", "pending", "decide", "is_approved", "withdraw", "put_up_plan", "plan_covers"):
            self.assertTrue(callable(getattr(approvals, name)), name)
        self.assertEqual(compensations.compensate({"tool": "send_report_email"})["compensated_by"], "none")
        self.assertIsNone(compensations.UNDO["send_report_email"])


class ServiceDelegationTest(ScratchTest):
    def test_decide_approval_resumes_the_run(self):
        from agent import service
        from tests.fakes import FakeApprovals, FakeResume
        with FakeApprovals().install() as approvals, FakeResume().install() as resume:
            approval_id = approvals.put_up("S#1", "S", {"name": "send_report_email", "args": {}, "key": "k"},
                                           "send_report_email/own_contact", {})
            self.assertEqual([i["id"] for i in service.pending_approvals()], [approval_id])
            service.decide_approval(approval_id, True, "ok")
        self.assertEqual(resume.calls, [("S#1", {"kind": "approval", "approval_id": approval_id,
                                                 "approved": True, "note": "ok"})])

    def test_stop_command_is_read_before_routing(self):
        from agent import service
        from policy import flags
        with mock.patch("agent.router.route_operator_message", side_effect=AssertionError("routed")):
            reply = service.operator_turn("S", "/stop")
        self.assertIn("Stopped", reply.text)
        self.assertTrue(flags.log("S#1"))


class EndsImmediately:
    """A fake model that ends its turn at once."""
    name, free = "ends", True

    def __init__(self, settings=None):
        pass

    def create(self, *, system, messages, tools=None):
        from harness.client import Usage
        return [{"type": "text", "text": "Carried on."}], "end_turn", self.name, Usage(10, 2)


class MinimalResumeTest(ScratchTest):
    def test_resume_from_restores_the_conversation(self):
        from agent import checkpoints, runs
        from sandbox import inbox
        with fixed_run("tasks/messy_file_semicolon.yaml", "m2-resume", backend="tests.test_m2_contracts:EndsImmediately"):
            request_id = inbox.all_requests()[0]["id"]
            checkpoints.save("m2-resume", {"path": "agent", "request_id": request_id, "operator_text": "Report it.",
                                           "conversation": [{"role": "user", "content": json.dumps({"x": 1})}]})
            reply = runs.resume("m2-resume", {"kind": "operator_turn", "text": "Carry on."})
        self.assertEqual(reply.text, "Carried on.")


if __name__ == "__main__":
    unittest.main()
