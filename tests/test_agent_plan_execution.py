"""Batch execution proves effects in the sandbox, never from the planner's prose."""

from copy import deepcopy
import json
from unittest import mock

from agent import bounds, critique, plan
from harness import runtime, turns
from harness.client import Usage
from sandbox import inbox, pending, reports
from tests.fixtures.agent_loop_fakes import SandboxRegistry, hold_revision_error, revise_recipient
from tests.test_agent_plan import RID, TASK, sample_plan
from tests.support import ScratchTest, check_run, fixed_run

MODEL = "tests.fixtures.agent_loop_fakes:SequenceModel"


class AgentPlanExecutionTest(ScratchTest):
    def script(self, *plans):
        model = runtime.client().backend
        model.responses = [([{"type": "text", "text": json.dumps(p)}], "end_turn", Usage(10, 5)) for p in plans]
        return model

    def run_plan(self, ids=(RID,), factory=SandboxRegistry, **kwargs):
        return plan.run("operator", ids, "Handle all new requests.", registry_factory=factory, **kwargs)

    def reason(self):
        return [e["terminal_reason"] for e in runtime.trace().lines() if e["type"] == "end"][-1]

    def batch(self):
        other = inbox.add("SYN-other", "SYN-DIST-001", "contact@acme.example", "Prepare a report", period="2026Q3")
        raw = sample_plan()
        extra = sample_plan(other, "other_")
        extra["steps"][-1]["args"]["recipient"] = "contact@acme.example"
        raw["steps"] += extra["steps"]
        return other, raw

    def test_planned_report_passes_the_independent_effects_check(self):
        with fixed_run(TASK, "planned-pass", backend=MODEL, overrides=["critique.report_email=off"]):
            self.script(sample_plan())
            reply = self.run_plan()
            self.assertEqual(self.reason(), "done")
            self.assertEqual(len(reply.actions), 3)
            self.assertEqual(inbox.get(RID)["status"], "report_drafted")
            checked = check_run(TASK, "planned-pass", replies=[reply.text])
            self.assertTrue(checked["passed"], checked["reason"])
            lines = runtime.trace().lines()
            self.assertTrue(any(e["type"] == "plan" and e.get("accepted") for e in lines))
            self.assertTrue(any(e["type"] == "checkpoint" and e.get("resolved_args") for e in lines))

    def test_service_batch_switch_reaches_the_planner_with_separate_request_scopes(self):
        with fixed_run(TASK, "planned-batch", backend=MODEL, overrides=["critique.report_email=off"]):
            other, raw = self.batch()
            self.script(raw)
            with mock.patch("agent.plan.tools.build", side_effect=SandboxRegistry):
                reply = turns.operator_turn("operator", "Handle all new requests.")
            self.assertEqual(len(reply.actions), 6)
            self.assertEqual(len(reports.for_request(RID)), 1)
            self.assertEqual(len(reports.for_request(other)), 1)
            self.assertEqual({(p["request_id"], p["recipient"]) for p in pending.all_pending()},
                             {(RID, "contact@brightline.example"), (other, "contact@acme.example")})

    def test_invalid_plans_exhaust_the_replan_bound_before_any_effect(self):
        with fixed_run(TASK, "bad-planner", backend=MODEL):
            self.script({"steps": []}, {"steps": []}, {"steps": []})
            self.run_plan()
            self.assertEqual(self.reason(), "replan_bound")
            self.assertEqual(runtime.client().calls, 3)
            self.assertEqual(reports.for_request(RID), [])
            self.assertEqual(pending.all_pending(), [])

    def test_checkpoint_repairs_parse_arguments_before_writes(self):
        with fixed_run(TASK, "checkpoint", backend=MODEL, overrides=["critique.report_email=off"]):
            raw = sample_plan()
            raw["steps"][0]["depends_on"] = ["parse"]
            raw["steps"].insert(0, {"id": "parse", "request_id": RID, "tool": "parse_file", "args": {},
                                     "depends_on": [], "checkpoint": True,
                                     "expect": {"field": "columns", "op": "eq",
                                                "value": ["Artikel", "Menge", "Netto_Betrag"]}})
            repaired = deepcopy(raw)
            repaired["steps"][0]["args"] = {"delimiter": ";", "decimal": ","}
            self.script(raw, repaired)
            self.run_plan()
            self.assertEqual(self.reason(), "done")
            self.assertEqual(runtime.client().calls, 2)
            checks = [e for e in runtime.trace().lines() if e["type"] == "checkpoint" and e["step_id"] == "parse"]
            self.assertEqual([e["passed"] for e in checks], [False, True])
            self.assertEqual(len(pending.all_pending()), 1)

    def test_checkpoint_replan_preserves_completed_writes_and_counts_repeats(self):
        with fixed_run(TASK, "preserve", backend=MODEL, overrides=["critique.report_email=off"]):
            other, raw = self.batch()
            raw["steps"][3]["expect"]["value"] = 10**12
            revised = deepcopy(raw)
            revised["steps"][3]["expect"]["value"] = 0
            self.script(raw, revised)
            self.run_plan((RID, other))
            self.assertEqual(self.reason(), "done")
            self.assertEqual(len(reports.for_request(RID)), 1)
            self.assertEqual(len(pending.for_request(RID)), 1)
            self.assertEqual(len(pending.for_request(other)), 1)
            self.assertTrue(any(e["type"] == "repeat_call" for e in runtime.trace().lines()))

    def test_replanner_cannot_rewrite_completed_effects(self):
        with fixed_run(TASK, "change-completed", backend=MODEL, overrides=["critique.report_email=off"]):
            other, raw = self.batch()
            raw["steps"][3]["expect"]["value"] = 10**12
            changed = deepcopy(raw)
            changed["steps"][1]["args"]["body"] = "Rewrite a completed report"
            self.script(raw, changed, changed)
            self.run_plan((RID, other))
            self.assertEqual(self.reason(), "replan_bound")
            self.assertEqual(len(pending.all_pending()), 1)
            self.assertEqual(len(reports.for_request(RID)), 1)

    def test_fabricated_write_success_is_rejected_by_the_sandbox_observation(self):
        with fixed_run(TASK, "false-effect", backend=MODEL):
            self.script(sample_plan())
            def factory(rid):
                registry = SandboxRegistry(rid)
                registry.handlers["save_report"] = lambda **args: {"report_id": 999, "version": 1, "created": True}
                return registry
            self.run_plan(factory=factory)
            self.assertEqual(self.reason(), "plan_rejected")
            self.assertEqual(pending.all_pending(), [])
            self.assertEqual(runtime.client().calls, 1)

    def test_write_error_after_persistence_stops_without_replanning_or_duplicate_effects(self):
        with fixed_run(TASK, "uncertain-write", backend=MODEL, overrides=["critique.report_email=off"]):
            revised = sample_plan()
            revised["steps"][1]["args"]["body"] = "A different report body"
            self.script(sample_plan(), revised)
            registry = SandboxRegistry(RID)
            save = registry.handlers["save_report"]
            def uncertain_save(**args):
                save(**args)
                raise ValueError("Response lost after persistence")
            registry.handlers["save_report"] = uncertain_save
            reply = self.run_plan(factory=lambda rid: registry)
            self.assertEqual(self.reason(), "plan_rejected")
            self.assertIn("uncertain", reply.text)
            self.assertEqual(runtime.client().calls, 1)
            self.assertEqual(len(reports.for_request(RID)), 1)
            self.assertEqual(pending.all_pending(), [])

    def test_excessive_json_nesting_is_rejected_within_the_revision_bound(self):
        with fixed_run(TASK, "deep-plan", backend=MODEL):
            raw = sample_plan()
            nested = {}
            for _ in range(600):
                nested = {"x": nested}
            raw["steps"][1]["args"]["figures"] = {
                "period": "2026Q3", "total_revenue": 0, "nested": nested}
            self.script(raw, raw, raw)
            self.run_plan()
            self.assertEqual(self.reason(), "replan_bound")
            self.assertEqual(runtime.client().calls, 3)
            self.assertEqual(reports.for_request(RID), [])

    def test_oversized_public_batch_is_rejected_before_model_or_tool_calls(self):
        with fixed_run(TASK, "oversized-batch", backend=MODEL):
            for number in range(8):
                inbox.add(f"SYN-extra-{number}", "SYN-DIST-001", "contact@acme.example", "Prepare a report")
            with mock.patch("agent.plan.tools.build") as build:
                reply = turns.operator_turn("operator", "Handle all new requests.")
            self.assertEqual(self.reason(), "plan_rejected")
            self.assertIn("8", reply.text)
            self.assertEqual(runtime.client().calls, 0)
            build.assert_not_called()
            self.assertEqual(pending.all_pending(), [])

    def test_held_critique_blocks_planned_email(self):
        with fixed_run(TASK, "planned-held", backend=MODEL):
            self.script(sample_plan())
            with mock.patch("agent.loop.critique.run", return_value=critique.CritiqueResult(False, {}, 2, "Wrong figures")):
                self.run_plan()
            self.assertEqual(self.reason(), "critique_held")
            self.assertEqual(inbox.get(RID)["status"], "held")
            self.assertEqual(pending.all_pending(), [])

    def test_critique_amendment_is_recorded_before_executing_changed_arguments(self):
        with fixed_run(TASK, "planned-revision", backend=MODEL):
            raw = sample_plan()
            raw["steps"][-1]["args"]["recipient"] = "wrong@example.test"
            model = self.script(raw, {"recipient": "contact@brightline.example", "subject": "Revised", "body": "Checked"})
            with mock.patch("agent.loop.critique.run", side_effect=revise_recipient):
                self.run_plan()
            self.assertEqual(self.reason(), "done")
            self.assertEqual(pending.all_pending()[0]["recipient"], "contact@brightline.example")
            self.assertEqual(len(model.requests), 2)
            lines = runtime.trace().lines()
            amended = next(i for i, e in enumerate(lines) if e["type"] == "plan" and e.get("approved_by") == "critique")
            written = next(i for i, e in enumerate(lines) if e["type"] == "tool_call" and e["name"] == "draft_report_email")
            self.assertLess(amended, written)

    def test_planner_tokens_stop_execution_before_any_tools(self):
        with fixed_run(TASK, "plan-budget", backend=MODEL):
            self.script(sample_plan())
            self.run_plan(limits=bounds.Limits(token_budget=15))
            self.assertEqual(self.reason(), "agent_budget")
            self.assertEqual(reports.for_request(RID), [])

    def test_critic_cannot_hide_the_shared_planner_revision_step_limit(self):
        with fixed_run(TASK, "plan-caught-limit", backend=MODEL):
            self.script(sample_plan())
            with mock.patch("agent.loop.critique.run", side_effect=hold_revision_error):
                self.run_plan(limits=bounds.Limits(max_steps=1))
            self.assertEqual(self.reason(), "step_limit")
            self.assertEqual(runtime.client().calls, 1)
            self.assertEqual(pending.all_pending(), [])

    def test_uncooperative_planner_stops_without_calling_its_proposed_tools(self):
        with fixed_run(TASK, "never-plan"):
            self.run_plan()
            self.assertEqual(self.reason(), "replan_bound")
            self.assertEqual(runtime.client().calls, 3)
            self.assertEqual(pending.all_pending(), [])

    def test_clarification_plan_stops_with_a_real_pending_question(self):
        with fixed_run(TASK, "plan-question", backend=MODEL):
            raw = sample_plan()
            raw["steps"] = [raw["steps"][0], {"id": "ask", "request_id": RID, "tool": "draft_clarifying_question",
                "args": {"question": "Which comparison do you need?"}, "depends_on": ["query"],
                "expect": {"field": "pending_id", "op": "exists"}}]
            self.script(raw)
            reply = self.run_plan()
            self.assertEqual(self.reason(), "needs_answer")
            self.assertEqual(reply.waiting_for, "SYN-thread-agent-messy")
            self.assertEqual(len(pending.all_pending()), 1)
