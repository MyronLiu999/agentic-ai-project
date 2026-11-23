"""Pass 3 (tools.computed_figures; owner: myron): code, not the model, computes save_report's database figures.

off stores the figures as the caller gave them (the build). on replaces total_revenue, total_units and, for a
comparison, previous_period, previous_total_revenue and revenue_change with values computed from the sales
database for the request's own distributor, before the call reaches the server. Every other figure is kept.
The definitions the model reads and the write's key are the same in both settings. Effects are read from the
sandbox (reports), through the real registry and MCP server.
"""

from agent.registry import MODEL
from sandbox import reports, sales
from tests.support import ScratchTest, fixed_run

TASK = "tests/fixtures/agent_messy_file.yaml"
RID = "REQ-SYN-thread-agent-messy"
DIST = "SYN-DIST-002"
WRONG = {"period": "2026Q3", "total_revenue": 1.0, "total_units": 2, "file_total_units": 140,
         "previous_period": "2026Q2", "previous_total_revenue": 0, "revenue_change": -3777.9}


class ComputedFiguresTest(ScratchTest):
    def save(self, setting, args, run_id):
        from agent import tools
        overrides = [f"tools.computed_figures={setting}"] if setting else []
        with fixed_run(TASK, run_id, overrides=overrides):
            registry = tools.build(RID)
            result = registry.call("save_report", args, MODEL)
            stored = [reports.figures(r) for r in reports.for_request(RID)]
            return result, stored, registry

    def test_off_stores_the_callers_figures(self):
        result, stored, _ = self.save("off", {"kind": "comparison", "figures": WRONG, "body": "Q3."}, "cf-off")
        self.assertTrue(result["ok"], result)
        self.assertEqual(stored, [WRONG])

    def test_default_is_on_by_the_pass_verdict(self):
        """switches.yaml sets it on (ledger, Pass 3's verdict): with no override the figures are computed."""
        result, stored, _ = self.save(None, {"kind": "comparison", "figures": WRONG, "body": "Q3."}, "cf-default")
        self.assertTrue(result["ok"], result)
        self.assertEqual(stored[0]["total_revenue"], sales.distributor_sales(DIST, "2026Q3")["total_revenue"])
        self.assertNotEqual(stored, [WRONG])

    def test_on_computes_the_comparison_from_the_database(self):
        result, stored, _ = self.save("on", {"kind": "comparison", "figures": WRONG, "body": "Q3."}, "cf-on")
        self.assertTrue(result["ok"], result)
        now, before = sales.distributor_sales(DIST, "2026Q3"), sales.distributor_sales(DIST, "2026Q2")
        self.assertEqual(stored, [{
            "period": "2026Q3", "total_revenue": now["total_revenue"], "total_units": now["total_units"],
            "file_total_units": 140, "previous_period": "2026Q2",
            "previous_total_revenue": before["total_revenue"],
            "revenue_change": round(now["total_revenue"] - before["total_revenue"], 2)}])
        self.assertNotEqual(now["total_revenue"], WRONG["total_revenue"])

    def test_on_adds_no_comparison_to_a_standard_report_that_asks_none(self):
        args = {"kind": "standard", "figures": {"period": "2026Q3", "total_revenue": 5.0}, "body": "Q3."}
        result, stored, _ = self.save("on", args, "cf-standard")
        self.assertTrue(result["ok"], result)
        now = sales.distributor_sales(DIST, "2026Q3")
        self.assertEqual(stored, [{"period": "2026Q3", "total_revenue": now["total_revenue"],
                                   "total_units": now["total_units"]}])

    def test_on_keeps_the_key_so_a_retry_is_the_same_effect(self):
        from agent import tools
        with fixed_run(TASK, "cf-retry", overrides=["tools.computed_figures=on"]):
            registry = tools.build(RID)
            first = registry.call("save_report", {"kind": "comparison", "figures": WRONG, "body": "A"}, MODEL)
            again = registry.call("save_report", {"kind": "comparison", "figures": {**WRONG, "revenue_change": 9},
                                                  "body": "B"}, MODEL)
            self.assertTrue(first["ok"] and again["ok"], (first, again))
            self.assertEqual(len(reports.for_request(RID)), 1)
            from harness import runtime
            keys = [e["key"] for e in runtime.trace().lines() if e["type"] == "tool_call"]
            self.assertEqual(len(keys), 2)
            self.assertEqual(keys[0], keys[1])

    def test_on_still_refuses_what_the_validation_refuses(self):
        result, stored, _ = self.save("on", {"kind": "comparison", "figures": {"period": "2026Q3"}, "body": "Q3."},
                                      "cf-invalid")
        self.assertFalse(result["ok"])
        self.assertEqual(stored, [])

    def test_on_a_dropped_comparison_is_filled_from_the_database_in_a_full_run(self):
        """The on side of test_report_validation_regressions' MissingComparison (which runs with off): the fake
        model saves the comparison report without previous_total_revenue; code fills it, the check passes."""
        from tests.test_domain_checks import COMPARE
        record = self.run_task(COMPARE, "cf-missing-comparison",
                               backend="tests.test_report_validation_regressions:MissingComparison",
                               overrides=["tools.computed_figures=on"])
        self.assertTrue(record["passed"], record["check"])
        from sandbox import inbox
        rid = inbox.request_id("SYN-thread-1201")
        saved = reports.figures(reports.for_request(rid)[-1])
        request = inbox.get(rid)
        self.assertEqual(saved["previous_total_revenue"],
                         sales.distributor_sales(request["distributor_id"], "2026Q2")["total_revenue"])

    def test_the_definitions_are_the_same_in_both_settings(self):
        from agent import tools
        from harness import runtime
        seen = []
        for setting in ("off", "on"):
            runtime.configure(overrides=[f"tools.computed_figures={setting}"])
            try:
                seen.append(tools.build(RID).definitions())
            finally:
                runtime.configure()
        self.assertEqual(seen[0], seen[1])
