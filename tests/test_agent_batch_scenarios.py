"""Milestone's five plan scenarios on the official plan=yes batch task."""

import json
from unittest import mock

from agent import bounds, plan
from harness import runtime, tasks, turns, ROOT
from sandbox import pending, reports
from tests.fixtures.agent_milestone_model import MilestoneModel
from tests.support import ScratchTest, fixed_run

TASK = "tasks/batch_reports_two.yaml"
MODEL = "tests.test_agent_batch_scenarios:ScenarioModel"
IDS = ("REQ-SYN-thread-1301", "REQ-SYN-thread-1302")


class ScenarioModel(MilestoneModel):
    mode = "valid"
    plans = 0

    def create(self, *, system, messages, tools):
        if not system.startswith("Plan reports"):
            return super().create(system=system, messages=messages, tools=tools)
        self.plans += 1
        content, stop, end, usage = super().create(system=system, messages=messages, tools=tools)
        raw = json.loads(content[0]["text"])
        if self.mode == "invalid" or (self.mode == "invalid_revision" and self.plans > 1):
            raw = {"steps": []}
        elif self.mode in ("checkpoint", "invalid_revision"):
            if self.plans == 1:
                raw["steps"][1]["expect"] = {"field": "total_revenue", "op": "gte", "value": 10**12}
            else:
                # The successful parse remains immutable in code, without exposing its rows.
                raw["steps"] = raw["steps"][1:]
        return [{"type": "text", "text": json.dumps(raw)}], stop, end, usage


class AgentBatchScenariosTest(ScratchTest):
    def turn(self, mode="valid"):
        self.assertEqual(runtime.switch("plan.batch_reports"), "on")
        runtime.client().backend.mode = mode
        return turns.operator_turn("operator", tasks.load(ROOT / TASK)["operator"][0])

    def events(self, kind):
        return [e for e in runtime.trace().lines() if e["type"] == kind]

    def test_invalid_official_batch_plan_stops_without_any_writes(self):
        with fixed_run(TASK, "batch-invalid", backend=MODEL):
            self.turn("invalid")
            self.assertEqual(self.events("end")[-1]["terminal_reason"], "replan_bound")
            self.assertEqual(runtime.client().backend.plans, 3)
            self.assertEqual(self.events("tool_call"), [])
            self.assertEqual(pending.all_pending(), [])
            self.assertTrue(all(not reports.for_request(rid) for rid in IDS))

    def test_off_plan_call_is_refused_and_traced_before_registry_execution(self):
        authorize = plan.Guard.authorize
        def attempt_extra(guard, sid, rid, tool, args):
            return authorize(guard, "not_in_plan", rid, "save_report", args)
        with fixed_run(TASK, "batch-off-plan", backend=MODEL):
            with mock.patch.object(plan.Guard, "authorize", attempt_extra):
                self.turn()
            self.assertEqual(self.events("end")[-1]["terminal_reason"], "plan_rejected")
            self.assertEqual(self.events("tool_call"), [])
            self.assertEqual(self.events("off_plan_refused")[0]["step_id"], "not_in_plan")
            self.assertIn("extra", [e["label"] for e in self.events("plan_diff")])
            self.assertEqual(pending.all_pending(), [])

    def test_official_batch_executes_the_exact_logged_order(self):
        with fixed_run(TASK, "batch-order", backend=MODEL):
            self.turn()
            calls = self.events("tool_call")
            self.assertEqual([e["plan_step"] for e in calls],
                [f"r{i}_{name}" for i in range(2) for name in ("parse", "query", "chart", "save", "email")])
            self.assertEqual(self.events("end")[-1]["terminal_reason"], "done")
            self.assertEqual(len(pending.all_pending()), 2)
            lines = runtime.trace().lines()
            self.assertLess(next(i for i, e in enumerate(lines) if e["type"] == "plan"),
                            next(i for i, e in enumerate(lines) if e["type"] == "tool_call"))
            for rid in IDS:
                figures = reports.figures(reports.latest(rid))
                self.assertEqual(figures["file_row_count"], 2)
                self.assertIsInstance(figures["chart_id"], int)

    def test_failed_checkpoint_revises_remaining_steps_and_preserves_completed_parse(self):
        with fixed_run(TASK, "batch-checkpoint", backend=MODEL):
            self.turn("checkpoint")
            self.assertEqual(self.events("end")[-1]["terminal_reason"], "done")
            versions = [e for e in self.events("plan") if e.get("accepted") and not e.get("approved_by")]
            self.assertEqual(len(versions), 2)
            calls = self.events("tool_call")
            self.assertEqual(sum(e["plan_step"] == "r0_parse" for e in calls), 1)
            self.assertEqual(sum(e["plan_step"] == "r0_query" for e in calls), 2)
            self.assertEqual(len(pending.all_pending()), 2)
            self.assertEqual(len(self.events("repeat_call")), 1)

    def test_invalid_checkpoint_revision_never_executes_its_remaining_writes(self):
        with fixed_run(TASK, "batch-invalid-revision", backend=MODEL):
            self.turn("invalid_revision")
            self.assertEqual(self.events("end")[-1]["terminal_reason"], "replan_bound")
            self.assertEqual([e["name"] for e in self.events("tool_call")], ["parse_file", "query_sales"])
            self.assertEqual(pending.all_pending(), [])
            self.assertTrue(all(not reports.for_request(rid) for rid in IDS))

    def test_bound_labels_unreached_batch_steps_as_skipped(self):
        limits = bounds.Limits(max_steps=1)
        with fixed_run(TASK, "batch-skipped", backend=MODEL):
            with mock.patch("agent.plan.bounds.Limits", return_value=limits):
                self.turn()
            self.assertEqual(self.events("end")[-1]["terminal_reason"], "step_limit")
            skipped = {e["step_id"] for e in self.events("plan_diff") if e["label"] == "skipped"}
            self.assertEqual(skipped, {"r0_email", "r1_parse", "r1_query", "r1_chart", "r1_save", "r1_email"})
            self.assertEqual(pending.all_pending(), [])
