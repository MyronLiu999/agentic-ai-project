"""Dependency, scope, observation, and call-enforcement contracts for batch plans."""

from copy import deepcopy

from agent import plan
from harness import runtime
from tests.support import ScratchTest, fixed_run

TASK = "tests/fixtures/agent_messy_file.yaml"
RID = "REQ-SYN-thread-agent-messy"


def sample_plan(rid=RID, prefix=""):
    query, save, email = (prefix + name for name in ("query", "save", "email"))
    return {"steps": [
        {"id": query, "request_id": rid, "tool": "query_sales", "args": {"period": "2026Q3"},
         "depends_on": [], "expect": {"field": "total_revenue", "op": "gte", "value": 0}, "checkpoint": True},
        {"id": save, "request_id": rid, "tool": "save_report",
         "args": {"kind": "quarterly_report", "figures": {"$fill": query}, "body": "Quarterly report"},
         "depends_on": [query], "expect": {"field": "report_id", "op": "exists"}},
        {"id": email, "request_id": rid, "tool": "draft_report_email",
         "args": {"recipient": "contact@brightline.example", "subject": "Q3 report", "body": "Report ready.",
                  "report_id": {"$fill": save + ".report_id"}},
         "depends_on": [save], "expect": {"field": "pending_id", "op": "exists"}},
    ]}


class AgentPlanTest(ScratchTest):
    def test_dependency_only_artifact_is_an_orphan_without_downstream_use(self):
        raw = sample_plan()
        raw["steps"].insert(1, {"id": "chart", "request_id": RID, "tool": "render_chart",
            "args": {"title": "Revenue", "labels": ["Total"], "values": [{"$fill": "query.total_revenue"}]},
            "depends_on": ["query"], "expect": {"field": "chart_id", "op": "exists"}})
        raw["steps"][2]["depends_on"].append("chart")
        with self.assertRaisesRegex(plan.PlanError, "Orphan|consumed|used"):
            plan.validate(raw, [RID])

    def test_request_bindings_resolve_only_scoped_period_and_contact(self):
        raw = sample_plan()
        raw["steps"][0]["args"]["period"] = {"$fill": "request.period"}
        raw["steps"][2]["args"]["recipient"] = {"$fill": "request.contact_email"}
        steps = plan.validate(raw, [RID])
        request = {"period": "2026Q3", "contact_email": "contact@brightline.example", "question": "OUTSIDE"}
        self.assertEqual(plan.resolve(steps[0]["args"], {}, request=request), {"period": "2026Q3"})
        raw["steps"][2]["args"]["recipient"] = {"$fill": "request.question"}
        with self.assertRaises(plan.PlanError):
            plan.validate(raw, [RID])

    def test_forward_dependencies_are_rejected_even_when_graph_is_acyclic(self):
        raw = sample_plan()
        raw["steps"].reverse()
        with self.assertRaisesRegex(plan.PlanError, "earlier|later|order"):
            plan.validate(raw, [RID])

    def test_guard_refuses_an_independent_later_step(self):
        other = "REQ-other"
        raw = sample_plan()
        raw["steps"] += sample_plan(other, "other_")["steps"]
        with fixed_run(TASK, "independent-order"):
            guard = plan.Guard(plan.validate(raw, [RID, other]), runtime.trace())
            self.assertFalse(guard.authorize("other_query", other, "query_sales", {"period": "2026Q3"}))
            self.assertEqual([s["id"] for s in guard.ready()], ["query"])
            self.assertEqual(runtime.trace().lines()[-1]["label"], "out_of_order")

    def test_revision_cannot_move_completed_steps_or_insert_before_them(self):
        other = "REQ-other"
        raw = sample_plan()
        raw["steps"] += sample_plan(other, "other_")["steps"]
        old = plan.validate(raw, [RID, other])
        moved = {"steps": raw["steps"][3:] + raw["steps"][:3]}
        with self.assertRaisesRegex(plan.PlanError, "Completed|prefix|order"):
            plan.validate(moved, [RID, other], completed={s["id"]: s for s in old[:3]})

    def test_valid_plan_resolves_whole_outputs_and_fields_without_mutation(self):
        raw = sample_plan()
        steps = plan.validate(raw, [RID])
        output = {"period": "2026Q3", "total_revenue": 123}
        args = plan.resolve(steps[1]["args"], {"query": output})
        self.assertEqual(args["figures"], {"period": "2026Q3", "total_revenue": 123})
        args["figures"]["total_revenue"] = 999
        self.assertEqual(output["total_revenue"], 123)
        self.assertEqual(raw["steps"][1]["args"]["figures"], {"$fill": "query"})
        self.assertEqual(plan.resolve(steps[2]["args"], {"save": {"report_id": 7}})["report_id"], 7)

    def test_rejects_cycles_unknown_dependencies_and_orphaned_work(self):
        variants = []
        cyclic = sample_plan()
        cyclic["steps"][0]["depends_on"] = ["email"]
        variants.append(cyclic)
        unknown = sample_plan()
        unknown["steps"][0]["depends_on"] = ["missing"]
        variants.append(unknown)
        orphan = sample_plan()
        orphan["steps"].append({"id": "orphan", "request_id": RID, "tool": "parse_file", "args": {},
                                 "depends_on": [], "expect": {"field": "row_count", "op": "gte", "value": 1}})
        variants.append(orphan)
        for number, raw in enumerate(variants):
            with self.subTest(number=number), self.assertRaises(plan.PlanError):
                plan.validate(raw, [RID])

    def test_rejects_scope_tool_argument_and_observation_inventions(self):
        for field, value in (("request_id", "REQ-other"), ("tool", "send_report"),
                             ("args", {"period": "2026Q3", "distributor_id": "SYN-DIST-999"}),
                             ("args", {"period": "forever"}),
                             ("expect", {"field": "hallucinated", "op": "exists"})):
            raw = sample_plan()
            raw["steps"][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(plan.PlanError):
                plan.validate(raw, [RID])

    def test_every_request_needs_a_terminal_and_a_read_checkpoint(self):
        with self.assertRaises(plan.PlanError):
            plan.validate(sample_plan(), [RID, "REQ-other"])
        raw = sample_plan()
        raw["steps"][0]["checkpoint"] = False
        with self.assertRaises(plan.PlanError):
            plan.validate(raw, [RID])

    def test_fill_must_refer_to_a_same_request_ancestor(self):
        raw = sample_plan()
        raw["steps"][1]["depends_on"] = []
        with self.assertRaises(plan.PlanError):
            plan.validate(raw, [RID])
        raw = sample_plan()
        raw["steps"][1]["args"]["figures"] = {"$fill": "missing.total_revenue"}
        with self.assertRaises(plan.PlanError):
            plan.validate(raw, [RID])

    def test_duplicate_ids_oversized_plans_and_raw_placeholders_are_rejected(self):
        variants = [sample_plan(), sample_plan(), sample_plan()]
        variants[0]["steps"][1]["id"] = "query"
        variants[1]["steps"] *= 50
        variants[2]["steps"][1]["args"]["figures"] = "$fill"
        for number, raw in enumerate(variants):
            with self.subTest(number=number), self.assertRaises(plan.PlanError):
                plan.validate(raw, [RID])

    def test_revised_plan_cannot_remove_or_change_completed_steps(self):
        old = plan.validate(sample_plan(), [RID])
        raw = sample_plan()
        raw["steps"][0]["args"]["period"] = "2026Q2"
        with self.assertRaises(plan.PlanError):
            plan.validate(raw, [RID], completed={"query": old[0]})

    def test_missing_fill_output_fails_closed(self):
        with self.assertRaises(plan.PlanError):
            plan.resolve({"report_id": {"$fill": "save.report_id"}}, {"save": {}})

    def test_gate_refuses_extra_out_of_order_and_mismatched_calls(self):
        with fixed_run(TASK, "plan-gate"):
            gate = plan.Guard(plan.validate(sample_plan(), [RID]), runtime.trace())
            self.assertFalse(gate.authorize("email", RID, "draft_report_email", {}))
            self.assertFalse(gate.authorize("missing", RID, "send_report", {}))
            self.assertFalse(gate.authorize("query", RID, "query_sales", {"period": "2026Q2"}))
            self.assertTrue(gate.authorize("query", RID, "query_sales", {"period": "2026Q3"}))
            gate.record("query", {"total_revenue": 10, "period": "2026Q3"})
            self.assertFalse(gate.authorize("query", RID, "query_sales", {"period": "2026Q3"}))
            labels = [e["label"] for e in runtime.trace().lines() if e["type"] == "plan_diff"]
            self.assertIn("out_of_order", labels)
            self.assertIn("extra", labels)
            self.assertIn("executed", labels)
            gate.finish()
            self.assertEqual(len([e for e in runtime.trace().lines()
                                  if e["type"] == "plan_diff" and e["label"] == "skipped"]), 2)

    def test_repeats_are_request_scoped_and_canonicalize_argument_order(self):
        with fixed_run(TASK, "repeat"):
            gate = plan.Guard(plan.validate(sample_plan(), [RID]), runtime.trace())
            gate.track(RID, "save_report", {"a": 1, "b": 2})
            gate.track("REQ-other", "save_report", {"a": 1, "b": 2})
            gate.track(RID, "save_report", {"b": 2, "a": 1})
            repeats = [e for e in runtime.trace().lines() if e["type"] == "repeat_call"]
            self.assertEqual(len(repeats), 1)
            self.assertEqual(repeats[0]["count"], 2)

    def test_observation_predicates_require_real_values_not_truthy_claims(self):
        self.assertTrue(plan.matches({"field": "report_id", "op": "exists"}, {"report_id": 3}))
        self.assertFalse(plan.matches({"field": "report_id", "op": "exists"}, {"report_id": None}))
        self.assertFalse(plan.matches({"field": "total_revenue", "op": "gte", "value": 0}, {"total_revenue": "Done"}))

    def test_malformed_predicate_types_are_validation_errors(self):
        for key in ("field", "op"):
            raw = sample_plan()
            raw["steps"][0]["expect"][key] = []
            with self.subTest(key=key), self.assertRaises(plan.PlanError):
                plan.validate(raw, [RID])

    def test_unrepresentable_numeric_values_are_rejected_without_overflow(self):
        with self.assertRaises(plan.PlanError):
            plan.validate_args("render_chart", {"title": "Totals", "labels": ["A"], "values": [10**400]})
        raw = sample_plan()
        raw["steps"][0]["expect"]["value"] = 10**400
        with self.assertRaises(plan.PlanError):
            plan.validate(raw, [RID])
        self.assertFalse(plan.matches({"field": "total_revenue", "op": "gte", "value": 0},
                                      {"total_revenue": 10**400}))

    def test_a_request_cannot_plan_duplicate_terminal_or_report_writes(self):
        for source in (1, 2):
            raw = sample_plan()
            extra = deepcopy(raw["steps"][source])
            extra["id"] = "duplicate"
            if source == 1:
                raw["steps"][-1]["depends_on"].append("duplicate")
            raw["steps"].append(extra)
            with self.subTest(source=source), self.assertRaises(plan.PlanError):
                plan.validate(raw, [RID])
