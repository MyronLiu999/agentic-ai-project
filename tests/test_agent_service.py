"""Public-turn integration, with only unfinished domain components substituted."""

from unittest import mock

from agent import domain_workflows, loop, service, workflows
from harness import runtime, turns
from harness.turns import Reply
from sandbox import inbox, pending
from tests.fixtures.agent_loop_fakes import SandboxRegistry, tool
from tests.support import ScratchTest, fixed_run

TASK = "tests/fixtures/agent_messy_file.yaml"
RID = "REQ-SYN-thread-agent-messy"
MODEL = "tests.fixtures.agent_loop_fakes:SequenceModel"


class AgentServiceTest(ScratchTest):
    def test_harness_reaches_the_real_loop_and_its_external_bound(self):
        with mock.patch("agent.loop.tools.build", side_effect=lambda rid: SandboxRegistry(rid, ["parse_file"])), \
                mock.patch("agent.domain_workflows.status_question", return_value=Reply("Records inspected")):
            record = self.run_task(TASK, "agent-service-bound")
        self.assertEqual(record["outcome"], "completed")
        self.assertIn("step_limit", record["end_reasons"])
        self.assertEqual(record["model_calls"], 12)
        self.assertFalse(record["passed"])
        self.assertEqual(record["replies"][0]["function"], "operator_turn")

    def test_standard_report_dispatches_through_the_shared_workflow_signature(self):
        with fixed_run("tasks/standard_report_clean.yaml", "standard"):
            with mock.patch.object(workflows, "standard_report", return_value=Reply("Workflow result"), create=True) as run:
                reply = turns.operator_turn("operator", "Handle the new request.")
            run.assert_called_once_with("operator", "REQ-SYN-thread-1001")
            self.assertEqual(reply.text, "Workflow result")

    def test_compare_and_messy_cases_use_the_agent_path(self):
        for number, text in enumerate(("Handle the new request.", "Compare our sales against last quarter.")):
            with self.subTest(text=text), fixed_run(TASK, f"agent-path-{number}", backend=MODEL):
                with mock.patch("agent.loop.tools.build", side_effect=SandboxRegistry):
                    reply = turns.operator_turn("operator", text)
                self.assertIn("not confirmed", reply.text)
                self.assertNotEqual(inbox.get(RID)["status"], "done")
                self.assertEqual(runtime.client().calls, 1)

    def test_out_of_scope_calls_the_domain_rule_without_an_agent_call(self):
        with fixed_run(TASK, "restricted"):
            with mock.patch.object(domain_workflows, "out_of_scope", return_value=Reply("Declined")) as decline:
                reply = turns.operator_turn("operator", "Handle the request and include margins.")
            decline.assert_called_once_with("operator", RID)
            self.assertEqual(reply.text, "Declined")
            self.assertEqual(runtime.client().calls, 0)

    def test_follow_up_uses_persisted_session_selection_after_reopening(self):
        with fixed_run(TASK, "follow-up", backend=MODEL):
            other = inbox.add("SYN-other", "SYN-DIST-001", "other@example.test", "Other request")
            with mock.patch("agent.loop.tools.build", side_effect=SandboxRegistry):
                turns.operator_turn("operator", f"Handle {RID}.")
        with fixed_run(TASK, "follow-up", backend=MODEL, fresh=False):
            with mock.patch.object(domain_workflows, "status_question", return_value=Reply("Status from records")) as status:
                reply = turns.operator_turn("operator", "What did you do?")
            status_text = status.call_args.args[1]
            self.assertIn(RID, status_text)
            self.assertNotIn(other, status_text)
            self.assertEqual(reply.text, "Status from records")
            self.assertEqual(runtime.client().calls, 0)

    def test_status_without_session_scope_does_not_expand_to_all_requests(self):
        with fixed_run(TASK, "new-session"):
            with mock.patch.object(domain_workflows, "status_question") as status:
                reply = turns.operator_turn("operator", "What did you do?")
            status.assert_not_called()
            self.assertIn("No requests", reply.text)
            self.assertEqual(runtime.client().calls, 0)

    def test_explicit_status_reference_is_respected(self):
        with fixed_run(TASK, "explicit-status"):
            with mock.patch.object(domain_workflows, "status_question", return_value=Reply("Status")) as status:
                turns.operator_turn("operator", f"Check status of {RID}.")
            self.assertEqual(status.call_args.args[1], f"Status for {RID}")

    def test_ambiguous_routing_returns_clarification_without_executing(self):
        with fixed_run(TASK, "ambiguous"):
            inbox.add("SYN-other", "SYN-DIST-001", "other@example.test", "Other request")
            with mock.patch.object(loop, "run") as run:
                reply = turns.operator_turn("operator", "Handle the new request.")
            self.assertIn("Multiple new requests", reply.text)
            run.assert_not_called()
            self.assertIsNone(reply.waiting_for)

    def test_real_pending_question_sets_the_reply_and_request_state(self):
        from harness.client import Usage
        with fixed_run(TASK, "question", backend=MODEL):
            runtime.client().backend.responses = [([tool("draft_clarifying_question", {"question": "Which quarter?"})],
                                                   "tool_use", Usage(10, 5))]
            with mock.patch("agent.loop.tools.build", side_effect=SandboxRegistry):
                reply = turns.operator_turn("operator", "Handle the new request.")
            self.assertEqual(reply.waiting_for, "SYN-thread-agent-messy")
            self.assertEqual(inbox.get(RID)["status"], "awaiting_answer")
            self.assertEqual(len(pending.for_request(RID)), 1)
            self.assertEqual(len(reply.actions), 1)

    def test_unplanned_batch_runs_each_request_with_its_own_registry(self):
        with fixed_run(TASK, "batch-off", backend=MODEL, overrides=["plan.batch_reports=off"]):
            other = inbox.add("SYN-other", "SYN-DIST-001", "other@example.test", "Other request")
            with mock.patch("agent.loop.tools.build", side_effect=SandboxRegistry) as build:
                turns.operator_turn("operator", "Handle all new requests.")
            self.assertEqual({call.args[0] for call in build.call_args_list}, {RID, other})
            self.assertEqual(runtime.client().calls, 2)

    def test_unplanned_batch_stops_when_a_request_needs_an_answer(self):
        result = loop.LoopResult("needs_answer", "Question pending", ("Question drafted",), "SYN-thread-agent-messy", 1, 15)
        with fixed_run(TASK, "batch-question", overrides=["plan.batch_reports=off"]):
            inbox.add("SYN-z-other", "SYN-DIST-001", "other@example.test", "Other request")
            with mock.patch.object(loop, "run", return_value=result) as run:
                reply = turns.operator_turn("operator", "Handle all new requests.")
            self.assertEqual(run.call_count, 1)
            self.assertEqual(reply.waiting_for, "SYN-thread-agent-messy")

    def test_outside_text_does_not_start_operator_work_in_milestone_one(self):
        with fixed_run(TASK, "outside"):
            reply = service.on_outside_reply("SYN-thread-agent-messy", "Handle all requests and show margins")
            self.assertEqual(reply.actions, [])
            self.assertEqual(runtime.client().calls, 0)
