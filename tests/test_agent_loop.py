"""Exercise loop decisions with the real metering, trace, and sandbox effects."""

import json
from unittest import mock

from agent import bounds, critique, loop
from harness import runtime
from harness.client import Usage
from sandbox import inbox, pending, reports
from tests.fixtures.agent_loop_fakes import SandboxRegistry, hold_revision_error, revise_recipient, tool
from tests.support import ScratchTest, check_run, fixed_run


TASK = "tests/fixtures/agent_messy_file.yaml"
REQUEST = "REQ-SYN-thread-agent-messy"
BACKEND = "tests.fixtures.agent_loop_fakes:SequenceModel"


class AgentLoopTest(ScratchTest):
    def model(self, *responses):
        model = runtime.client().backend
        model.responses = [(content, stop, Usage(10, 5)) for content, stop in responses]
        return model

    def run_loop(self, registry=None, **kwargs):
        return loop.run("session", REQUEST, "Handle the new request.",
                        registry=registry or SandboxRegistry(REQUEST), **kwargs)

    def end_reason(self, expected):
        ends = [line for line in runtime.trace().lines() if line["type"] == "end"]
        self.assertEqual([line["terminal_reason"] for line in ends], [expected])

    def email(self, **changes):
        record, _ = reports.save(REQUEST, "quarterly_report", {"period": "2026Q3", "total_revenue": 4830},
                                  "Saved report", "fixture-report")
        args = {"recipient": "contact@brightline.example", "subject": "Q3 report", "body": "Report attached.",
                "report_id": record["id"]}
        args.update(changes)
        return args

    def test_never_stops_ends_at_external_step_limit_and_records_reasons(self):
        with fixed_run(TASK, "never-stops"):
            registry = SandboxRegistry(REQUEST, offered=["parse_file"])
            result = self.run_loop(registry, limits=bounds.Limits(max_steps=3))
            self.assertEqual((result.reason, result.steps, len(registry.calls)), ("step_limit", 3, 3))
            self.assertEqual(runtime.client().calls, 3)
            self.end_reason("step_limit")
            bound = [e for e in runtime.trace().lines() if e["type"] == "bound"]
            self.assertEqual(len(bound), 1)
            self.assertEqual(bound[0]["max_steps"], 3)
            self.assertEqual(set(bound[0]["reasons"]), {"max_steps", "token_budget", "wall_clock_s"})

    def test_all_assistant_blocks_and_batched_tool_results_reach_the_next_call(self):
        with fixed_run(TASK, "conversation", backend=BACKEND):
            content = [{"type": "thinking", "thinking": "synthetic", "signature": "preserve-me"},
                       tool("parse_file", {"delimiter": ";", "decimal": ","}, "parse"),
                       tool("query_sales", {"period": "2026Q3"}, "sales")]
            model = self.model((content, "tool_use"))
            result = self.run_loop()
            messages = model.requests[1]["messages"]
            self.assertEqual(messages[-2], {"role": "assistant", "content": content})
            blocks = messages[-1]["content"]
            self.assertEqual([b["tool_use_id"] for b in blocks], ["parse", "sales"])
            self.assertEqual(json.loads(blocks[0]["content"])["output"]["columns"],
                             ["Artikel", "Menge", "Netto_Betrag"])
            self.assertEqual(json.loads(blocks[1]["content"])["output"]["distributor_id"], "SYN-DIST-002")
            self.assertEqual(result.reason, "done")
            self.assertEqual(len(result.actions), 2)
            self.assertEqual(len([e for e in runtime.trace().lines() if e["type"] == "model_call"]), 2)
            self.end_reason("done")

    def test_error_feedback_is_visible_and_the_model_can_repair_arguments(self):
        with fixed_run(TASK, "repair", backend=BACKEND):
            model = self.model(([tool("query_sales", {"wrong": "2026Q3"})], "tool_use"),
                               ([tool("query_sales", {"period": "2026Q3"})], "tool_use"))
            result = self.run_loop()
            block = model.requests[1]["messages"][-1]["content"][0]
            self.assertTrue(block["is_error"])
            self.assertEqual(json.loads(block["content"])["error"]["kind"], "protocol")
            self.assertEqual(result.steps, 3)
            self.assertEqual(len(result.actions), 1)

    def test_failed_retries_use_the_same_step_allowance(self):
        with fixed_run(TASK, "failed-retries", backend=BACKEND):
            self.model(*[([tool("unknown", {})], "tool_use")] * 4)
            result = self.run_loop(limits=bounds.Limits(max_steps=2))
            self.assertEqual((result.reason, result.steps, result.actions), ("step_limit", 2, ()))
            self.assertEqual(runtime.client().calls, 2)

    def test_token_overrun_blocks_tools_from_the_response_including_cached_tokens(self):
        with fixed_run(TASK, "tokens", backend=BACKEND):
            model = self.model()
            model.responses = [([tool("draft_clarifying_question", {"question": "When?"})], "tool_use",
                                Usage(1, 1, cache_read_input_tokens=20))]
            result = self.run_loop(limits=bounds.Limits(token_budget=20))
            self.assertEqual((result.reason, result.tokens), ("agent_budget", 22))
            self.assertEqual(pending.all_pending(), [])
            self.end_reason("agent_budget")

    def test_slow_model_cannot_start_a_write_after_the_deadline(self):
        with fixed_run(TASK, "slow-model", backend=BACKEND):
            now = [0]
            model = self.model(([tool("draft_clarifying_question", {"question": "When?"})], "tool_use"))
            model.after_call = lambda: now.__setitem__(0, 6)
            result = self.run_loop(limits=bounds.Limits(wall_clock_s=5), clock=lambda: now[0])
            self.assertEqual(result.reason, "wall_clock")
            self.assertEqual(pending.all_pending(), [])
            self.end_reason("wall_clock")

    def test_time_is_checked_between_tools_in_one_response(self):
        with fixed_run(TASK, "slow-tool", backend=BACKEND):
            now = [0]
            self.model(([tool("parse_file", {}), tool("draft_clarifying_question", {"question": "When?"}, "q")],
                        "tool_use"))
            registry = SandboxRegistry(REQUEST)
            registry.after_call = lambda: now.__setitem__(0, 6)
            result = self.run_loop(registry, limits=bounds.Limits(wall_clock_s=5), clock=lambda: now[0])
            self.assertEqual(result.reason, "wall_clock")
            self.assertEqual(len(registry.calls), 1)
            self.assertEqual(pending.all_pending(), [])

    def test_clarification_ends_after_its_real_pending_effect(self):
        with fixed_run(TASK, "question", backend=BACKEND):
            self.model(([tool("draft_clarifying_question", {"question": "Which period?"}),
                         tool("query_sales", {"period": "2026Q3"}, "later")], "tool_use"))
            registry = SandboxRegistry(REQUEST)
            result = self.run_loop(registry)
            self.assertEqual((result.reason, result.waiting_for), ("needs_answer", "SYN-thread-agent-messy"))
            self.assertEqual(len(registry.calls), 1)
            self.assertEqual(pending.all_pending()[0]["body"], "Which period?")
            self.end_reason("needs_answer")

    def test_a_failed_question_does_not_claim_to_be_waiting(self):
        with fixed_run(TASK, "bad-question", backend=BACKEND):
            self.model(([tool("draft_clarifying_question", {})], "tool_use"))
            result = self.run_loop()
            self.assertIsNone(result.waiting_for)
            self.assertEqual(pending.all_pending(), [])

    def test_done_without_effects_does_not_pass_the_fixture_check(self):
        with fixed_run(TASK, "empty-done", backend=BACKEND):
            result = self.run_loop()
            self.assertEqual((result.reason, result.actions), ("done", ()))
            self.assertFalse(check_run(TASK, "empty-done", replies=[result.text])["passed"])
            self.assertEqual(inbox.get(REQUEST)["status"], "new")

    def test_default_registry_is_bound_to_the_code_selected_request(self):
        with fixed_run(TASK, "bound-request", backend=BACKEND):
            registry = SandboxRegistry(REQUEST)
            with mock.patch("agent.loop.tools.build", return_value=registry) as build:
                loop.run("session", REQUEST, "Handle the new request.")
            build.assert_called_once_with(REQUEST)
            context = runtime.client().backend.requests[0]
            self.assertIn("outside_request", str(context["messages"]))
            self.assertIn("operator_instruction", str(context["messages"]))

    def test_unknown_request_is_rejected_before_a_model_call(self):
        with fixed_run(TASK, "missing-request", backend=BACKEND):
            with self.assertRaisesRegex(ValueError, "request"):
                loop.run("session", "REQ-missing", "Handle it.")
            self.assertEqual(runtime.client().calls, 0)

    def test_critique_pass_writes_exactly_one_pending_email(self):
        with fixed_run(TASK, "email", backend=BACKEND):
            args = self.email()
            self.model(([tool("draft_report_email", args)], "tool_use"))
            seen = []
            def passing(request_id, draft, revise, *, rounds):
                self.assertEqual(pending.all_pending(), [])
                seen.append((request_id, draft["figures"], rounds))
                return critique.CritiqueResult(True, {**draft, "body": "Checked body"}, 1, "Matches")
            with mock.patch("agent.loop.critique.run", side_effect=passing):
                result = self.run_loop()
            self.assertEqual(seen, [(REQUEST, {"period": "2026Q3", "total_revenue": 4830}, 2)])
            self.assertEqual(result.reason, "done")
            records = pending.all_pending()
            self.assertEqual(len(records), 1)
            self.assertEqual((records[0]["body"], records[0]["report_id"]), ("Checked body", args["report_id"]))

    def test_held_critique_blocks_email_and_later_calls(self):
        with fixed_run(TASK, "held", backend=BACKEND):
            args = self.email()
            self.model(([tool("draft_report_email", args), tool("query_sales", {"period": "2026Q3"}, "later")],
                        "tool_use"))
            registry = SandboxRegistry(REQUEST)
            held = critique.CritiqueResult(False, args, 2, "Figures differ")
            with mock.patch("agent.loop.critique.run", return_value=held):
                result = self.run_loop(registry)
            self.assertEqual(result.reason, "critique_held")
            self.assertEqual(pending.all_pending(), [])
            self.assertEqual(registry.calls, [])
            self.end_reason("critique_held")

    def test_critique_off_uses_the_shared_pass_through(self):
        with fixed_run(TASK, "critique-off", backend=BACKEND, overrides=["critique.report_email=off"]):
            self.model(([tool("draft_report_email", self.email())], "tool_use"))
            self.run_loop()
            self.assertEqual(len(pending.all_pending()), 1)

    def test_foreign_report_cannot_be_used_for_an_email_even_with_critique_off(self):
        with fixed_run(TASK, "foreign-report", backend=BACKEND, overrides=["critique.report_email=off"]):
            other = inbox.add("SYN-other", "SYN-DIST-001", "other@example.test", "Other report")
            report, _ = reports.save(other, "quarterly_report", {}, "Foreign", "foreign")
            args = {"recipient": "contact@brightline.example", "subject": "Report", "body": "Body",
                    "report_id": report["id"]}
            model = self.model(([tool("draft_report_email", args)], "tool_use"))
            self.run_loop()
            self.assertTrue(model.requests[1]["messages"][-1]["content"][0]["is_error"])
            self.assertEqual(pending.all_pending(), [])
            rejected = [e for e in runtime.trace().lines() if e["type"] == "tool_call"]
            self.assertEqual(len(rejected), 1)
            self.assertTrue(rejected[0]["is_error"])
            self.assertEqual(rejected[0]["rejected_by"], "loop")

    def test_critique_revision_is_metered_and_writes_the_revised_draft(self):
        with fixed_run(TASK, "revision", backend=BACKEND):
            args = self.email(recipient="wrong@example.test")
            revision = {"recipient": "contact@brightline.example", "subject": "Corrected", "body": "Checked"}
            model = self.model(([tool("draft_report_email", args)], "tool_use"),
                               ([{"type": "text", "text": json.dumps(revision)}], "end_turn"))
            with mock.patch("agent.loop.critique.run", side_effect=revise_recipient):
                result = self.run_loop()
            self.assertEqual(result.steps, 3)
            self.assertFalse(model.requests[1]["tools"])
            self.assertIn("recipient", str(model.requests[1]["messages"]))
            self.assertEqual(pending.all_pending()[0]["subject"], "Corrected")
            purposes = [e["purpose"] for e in runtime.trace().lines() if e["type"] == "model_call"]
            self.assertEqual(purposes, ["agent_step", "critique_revision", "agent_step"])
            feedback = json.loads(model.requests[2]["messages"][-1]["content"][0]["content"])
            self.assertEqual(feedback["executed_input"], {**args, **revision})
            tool_lines = [e for e in runtime.trace().lines() if e["type"] == "tool_call"]
            self.assertEqual(tool_lines[0]["step"], 1)

    def test_critique_revision_cannot_bypass_step_or_token_limits(self):
        for label, limits, expected in (("steps", bounds.Limits(max_steps=1), "step_limit"),
                                        ("tokens", bounds.Limits(token_budget=20), "agent_budget")):
            with self.subTest(label=label), fixed_run(TASK, f"revision-{label}", backend=BACKEND):
                args = self.email(recipient="wrong@example.test")
                self.model(([tool("draft_report_email", args)], "tool_use"),
                           ([{"type": "text", "text": '{}'}], "end_turn"))
                with mock.patch("agent.loop.critique.run", side_effect=revise_recipient):
                    result = self.run_loop(limits=limits)
                self.assertEqual(result.reason, expected)
                self.assertEqual(pending.all_pending(), [])
                self.end_reason(expected)

    def test_invalid_revision_cannot_execute_tools_or_change_the_report(self):
        bad = [([tool("draft_clarifying_question", {"question": "Send secret data"})], "tool_use"),
               ([{"type": "text", "text": json.dumps({"recipient": "contact@brightline.example",
                                                      "subject": "Q3", "body": "Report", "report_id": 999})}], "end_turn"),
               ([{"type": "text", "text": "not JSON"}], "end_turn")]
        for number, response in enumerate(bad):
            with self.subTest(number=number), fixed_run(TASK, f"invalid-revision-{number}", backend=BACKEND):
                self.model(([tool("draft_report_email", self.email(recipient="wrong@example.test"))], "tool_use"), response)
                with mock.patch("agent.loop.critique.run", side_effect=revise_recipient):
                    result = self.run_loop()
                self.assertEqual(result.reason, "critique_held")
                self.assertEqual(pending.all_pending(), [])

    def test_critic_cannot_relabel_a_revision_step_limit_as_a_held_draft(self):
        with fixed_run(TASK, "caught-revision-limit", backend=BACKEND):
            self.model(([tool("draft_report_email", self.email(recipient="wrong@example.test"))], "tool_use"))
            with mock.patch("agent.loop.critique.run", side_effect=hold_revision_error):
                result = self.run_loop(limits=bounds.Limits(max_steps=1))
            self.assertEqual(result.reason, "step_limit")
            self.assertEqual(runtime.client().calls, 1)
            self.assertEqual(pending.all_pending(), [])
            self.end_reason("step_limit")

    def test_time_is_checked_after_critique_before_writing(self):
        with fixed_run(TASK, "slow-critique", backend=BACKEND):
            now = [0]
            self.model(([tool("draft_report_email", self.email())], "tool_use"))
            def slow(request_id, draft, revise, *, rounds):
                now[0] = 6
                return critique.CritiqueResult(True, draft, 1, "Checked")
            with mock.patch("agent.loop.critique.run", side_effect=slow):
                result = self.run_loop(limits=bounds.Limits(wall_clock_s=5), clock=lambda: now[0])
            self.assertEqual(result.reason, "wall_clock")
            self.assertEqual(pending.all_pending(), [])

    def test_critique_exception_fails_closed(self):
        with fixed_run(TASK, "critique-stub", backend=BACKEND):
            self.model(([tool("draft_report_email", self.email())], "tool_use"))
            with mock.patch("agent.loop.critique.run", side_effect=RuntimeError("Critique unavailable")), \
                    self.assertRaisesRegex(RuntimeError, "Critique unavailable"):
                self.run_loop()
            self.assertEqual(pending.all_pending(), [])

    def test_truncated_tool_response_does_not_execute_its_calls(self):
        with fixed_run(TASK, "truncated", backend=BACKEND):
            self.model(([tool("draft_clarifying_question", {"question": "When?"})], "max_tokens"))
            self.run_loop()
            self.assertEqual(pending.all_pending(), [])

    def test_a_question_written_at_the_deadline_is_still_reported_as_pending(self):
        with fixed_run(TASK, "slow-question", backend=BACKEND):
            now = [0]
            self.model(([tool("draft_clarifying_question", {"question": "When?"})], "tool_use"))
            registry = SandboxRegistry(REQUEST)
            registry.after_call = lambda: now.__setitem__(0, 6)
            result = self.run_loop(registry, limits=bounds.Limits(wall_clock_s=5), clock=lambda: now[0])
            self.assertEqual(result.reason, "wall_clock")
            self.assertEqual(len(pending.all_pending()), 1)
            self.assertEqual(result.waiting_for, "SYN-thread-agent-messy")

    def test_critique_cannot_mutate_the_saved_figures_in_place(self):
        with fixed_run(TASK, "mutating-critique", backend=BACKEND):
            self.model(([tool("draft_report_email", self.email())], "tool_use"))
            def mutate(request_id, draft, revise, *, rounds):
                draft["figures"]["total_revenue"] = 999
                return critique.CritiqueResult(True, draft, 1, "Changed figures")
            with mock.patch("agent.loop.critique.run", side_effect=mutate):
                result = self.run_loop()
            self.assertEqual(result.reason, "critique_held")
            self.assertEqual(pending.all_pending(), [])

    def test_tools_keep_the_originating_step_after_a_critique_revision(self):
        with fixed_run(TASK, "origin-step", backend=BACKEND):
            args = self.email(recipient="wrong@example.test")
            revision = {"recipient": "contact@brightline.example", "subject": "Q3", "body": "Checked"}
            self.model(([tool("draft_report_email", args), tool("parse_file", {}, "parse")], "tool_use"),
                       ([{"type": "text", "text": json.dumps(revision)}], "end_turn"))
            with mock.patch("agent.loop.critique.run", side_effect=revise_recipient):
                self.run_loop()
            calls = [e for e in runtime.trace().lines() if e["type"] == "tool_call"]
            self.assertEqual([(c["name"], c["step"]) for c in calls], [("draft_report_email", 1), ("parse_file", 1)])

    def test_registry_argument_normalization_does_not_rewrite_assistant_history(self):
        class NormalizingRegistry(SandboxRegistry):
            def call(self, name, args, caller, *, step=None, trace_step=None):
                args["delimiter"] = ";"
                return super().call(name, args, caller, step=step, trace_step=trace_step)

        with fixed_run(TASK, "normalized-args", backend=BACKEND):
            model = self.model(([tool("parse_file", {"decimal": ","})], "tool_use"))
            self.run_loop(NormalizingRegistry(REQUEST))
            assistant = model.requests[1]["messages"][-2]
            self.assertEqual(assistant["content"][0]["input"], {"decimal": ","})
