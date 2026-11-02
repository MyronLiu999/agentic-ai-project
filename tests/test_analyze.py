"""experiments/analysis/analyze.py (claudea) on run records written by hand, so every number it prints is
checked against a count done by eye. No model."""

import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from harness import ROOT

spec = importlib.util.spec_from_file_location("analyze", ROOT / "experiments" / "analysis" / "analyze.py")
analyze = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analyze)


def write_run(folder, run_id, task, sweep, *, passed, cost, turns=(1.0,), calls=(), ends=("done",), trace=(),
              measures=None, task_file=None, outcome="completed"):
    record = {"run_id": run_id, "task": task, "sweep": sweep, "passed": passed, "cost_usd": cost,
              "tokens": {"total": int(cost * 1000)}, "turn_latency_s": list(turns), "outcome": outcome,
              "tool_calls": [{"name": n, "input": i, "is_error": e, "output": o} for n, i, e, o in calls],
              "end_reasons": list(ends), "end_reason": ends[-1] if ends else None, "measures": measures or {},
              "started": f"2026-10-30T10:{sweep:02d}:{len(run_id):02d}", "task_file": task_file}
    (folder / f"{run_id}.json").write_text(json.dumps(record))
    (folder / f"{run_id}.trace.jsonl").write_text("".join(json.dumps(x) + "\n" for x in trace))


Q = ("query_sales", {"period": "2026Q3"}, False, {})
P = ("parse_file", {}, False, {})
BAD = ("query_sales", {"period": "Q3"}, True, {"error": {"kind": "protocol", "message": "bad period"}})


class AnalyzeTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.agent, self.workflow = self.tmp / "agent", self.tmp / "workflow"
        self.agent.mkdir(), self.workflow.mkdir()
        task_file = self.tmp / "t.yaml"
        task_file.write_text("use_case: messy_file\n")
        crit_pass = {"type": "critique", "round": 1, "verdict": "pass"}
        # agent arm: task a passes 3 of 3, task b 1 of 3
        write_run(self.agent, "a1", "a", 1, passed=True, cost=0.04, turns=(2.0, 12.0), calls=(P, Q, Q),
                  trace=[{"type": "repeat_call"}, {"type": "route", "use_case": "standard_report"}],
                  task_file=str(task_file), measures={"duplicate_emails": 1})
        write_run(self.agent, "a2", "a", 2, passed=True, cost=0.04, turns=(3.0,), calls=(P, Q),
                  trace=[{"type": "route", "use_case": "messy_file"}], task_file=str(task_file))
        write_run(self.agent, "a3", "a", 3, passed=True, cost=0.04, turns=(4.0,), calls=(P, Q))
        write_run(self.agent, "b1", "b", 1, passed=False, cost=0.08, calls=(P, BAD), ends=("step_limit",))
        write_run(self.agent, "b2", "b", 2, passed=False, cost=0.08, calls=(P,), ends=("done",),
                  trace=[crit_pass])
        write_run(self.agent, "b3", "b", 3, passed=True, cost=0.08, calls=(P,),
                  trace=[{"type": "critique", "round": 1, "verdict": "revise"},
                         {"type": "critique", "round": 2, "verdict": "held"}], ends=("critique_held",))
        write_run(self.agent, "q1", "b", 3, passed=False, cost=9.0, outcome="quota")          # not counted
        # workflow arm: task a passes 1 of 3, task b 0 of 3
        for s in (1, 2, 3):
            write_run(self.workflow, f"wa{s}", "a", s, passed=(s == 1), cost=0.01, calls=(P, Q))
            write_run(self.workflow, f"wb{s}", "b", s, passed=False, cost=0.01, calls=(P, Q),
                      trace=[{"type": "plan", "version": 1}, {"type": "plan", "version": 2},
                             {"type": "plan_diff", "label": "skipped"}, {"type": "off_plan_refused"}],
                      ends=("replan_bound",))

    def tearDown(self):
        self._tmp.cleanup()

    def test_every_number_matches_the_hand_count(self):
        a = analyze.analyze_arm(self.agent)
        self.assertEqual((a["runs"], a["passes"]), (6, 4))
        self.assertEqual(a["per_task"], {"a": [3, 3], "b": [1, 3]})
        self.assertEqual(a["turn_median_s"], 2.0)          # turns 1, 1, 1, 2, 3, 4, 12
        self.assertEqual(a["turn_slowest_s"], 12.0)
        self.assertEqual(a["slow_turns_over_10s"], 1)
        self.assertAlmostEqual(a["cost_per_run"], 0.06)
        self.assertEqual(a["sequences_per_task"], {"a": 2, "b": 2})
        self.assertEqual((a["runs_with_repeat"], a["repeat_events"]), (1, 1))
        self.assertEqual(a["false_finish_runs"], ["b2"])
        self.assertEqual(a["bound_ends"], {"step_limit": 1})
        self.assertEqual(a["boundary"], {"tool_errors": 1, "boundary_rejections": 1})
        self.assertEqual((a["critique"]["rounds"], a["critique"]["held"], a["critique"]["misses"]), (3, 1, 1))
        self.assertEqual(a["critique"]["rounds_per_run"], 0.5)                # 3 rounds over all 6 runs
        self.assertEqual(a["critique"]["rounds_per_critiqued_run"], 1.5)       # over the 2 runs with a critique
        self.assertEqual((a["routing"]["routes"], a["routing"]["misroutes"]), (2, 1))
        self.assertEqual(a["measures"], {"duplicate_emails": 1})

    def test_plan_counts(self):
        w = analyze.analyze_arm(self.workflow)
        self.assertEqual(w["plan"]["plans"], 3)
        self.assertEqual(w["plan"]["revisions"], 3)
        self.assertEqual(w["plan"]["diff_skipped"], 3)
        self.assertEqual(w["plan"]["off_plan_refused"], 3)
        self.assertEqual(w["plan"]["replan_bound"], 3)

    def test_m_and_f(self):
        cross = analyze.compare(analyze.analyze_arm(self.agent), analyze.analyze_arm(self.workflow))
        self.assertAlmostEqual(cross["m"], 6.0)          # 0.06 / 0.01
        self.assertEqual((cross["f"], cross["f_tasks"]), (0.5, ["a"]))

    def test_the_command_prints_the_tables(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = analyze.main([str(self.agent), str(self.workflow), "--agent", "agent", "--workflow", "workflow"])
        self.assertEqual(code, 0)
        self.assertIn("m = 6.00; f = 0.50", out.getvalue())
        self.assertIn("| a | 3 of 3 |", out.getvalue())


class AnalyzeCountingTest(unittest.TestCase):
    """The counting fixes of 2026-10-31: each would give another number on the old code."""
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.agent, self.workflow = self.tmp / "agent", self.tmp / "workflow"
        self.agent.mkdir(), self.workflow.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def test_relocated_root_reads_its_own_relative_task_metadata(self):
        (self.tmp / "tasks").mkdir()
        (self.tmp / "tasks/t.yaml").write_text("use_case: messy_file\n")
        write_run(self.agent, "r1", "a", 1, passed=True, cost=0, task_file=r"tasks\t.yaml",
                  trace=[{"type": "route", "use_case": "messy_file"}])
        routing = analyze.analyze_arm(self.agent, repo_root=self.tmp)["routing"]
        self.assertEqual(routing["scored_routes"], 1)
        self.assertEqual(routing["misroutes"], 0)

    def test_proposal_rejections_and_terminal_rejections_are_separate(self):
        write_run(self.agent, "repaired", "a", 1, passed=True, cost=0,
                  trace=[{"type": "plan", "accepted": False}, {"type": "plan", "accepted": True}])
        write_run(self.agent, "stopped", "b", 1, passed=False, cost=0, ends=("plan_rejected",),
                  trace=[{"type": "plan", "accepted": False}])
        plan = analyze.analyze_arm(self.agent)["plan"]
        self.assertEqual(plan["proposal_rejections"], 2)
        self.assertEqual(plan["plan_rejected"], 1)

    def test_false_finish_counts_only_done_in_initial_task_turn(self):
        write_run(self.agent, "held", "a", 1, passed=False, cost=0, ends=("critique_held", "done"),
                  trace=[{"type": "operator"}, {"type": "end", "terminal_reason": "critique_held"},
                         {"type": "operator"}, {"type": "end", "terminal_reason": "done"}])
        write_run(self.agent, "false", "b", 1, passed=False, cost=0, ends=("done", "done"),
                  trace=[{"type": "operator"}, {"type": "end", "terminal_reason": "done"},
                         {"type": "operator"}, {"type": "end", "terminal_reason": "done"}])
        result = analyze.analyze_arm(self.agent)
        self.assertEqual(result["false_finishes"], 2)
        self.assertEqual(result["initial_task_false_finish_runs"], ["false"])
        self.assertEqual(result["initial_task_false_finishes"], 1)

    def test_target_costs_and_tokens_use_only_selected_task_runs(self):
        write_run(self.agent, "one", "target", 1, passed=True, cost=0.02)
        write_run(self.agent, "two", "target", 2, passed=False, cost=0.04)
        write_run(self.agent, "other", "other", 1, passed=True, cost=7)
        target = analyze.task_metrics(analyze.analyze_arm(self.agent), "target")
        self.assertEqual((target["runs"], target["passes"], target["mean_tokens"]), (2, 1, 30))
        self.assertAlmostEqual(target["mean_cost_usd"], 0.03)

    def test_a_run_ended_at_two_bounds_is_one_bounded_run(self):
        write_run(self.agent, "r1", "a", 1, passed=False, cost=0.01, ends=("step_limit", "wall_clock"))
        a = analyze.analyze_arm(self.agent)
        self.assertEqual(a["bound_runs"], 1)
        self.assertEqual(a["bound_ends"], {"step_limit": 1, "wall_clock": 1})

    def test_f_leaves_out_a_task_without_three_sweeps(self):
        for s in (1, 2, 3):
            write_run(self.agent, f"a{s}", "a", s, passed=True, cost=0.02)
            write_run(self.workflow, f"wa{s}", "a", s, passed=False, cost=0.01)
        for s in (1, 2):   # task b: two sweeps only, in both arms
            write_run(self.agent, f"b{s}", "b", s, passed=True, cost=0.02)
            write_run(self.workflow, f"wb{s}", "b", s, passed=False, cost=0.01)
        cross = analyze.compare(analyze.analyze_arm(self.agent), analyze.analyze_arm(self.workflow))
        self.assertEqual((cross["f"], cross["f_tasks"], cross["f_incomplete"]), (1.0, ["a"], ["b"]))

    def test_a_follow_up_turn_routed_elsewhere_is_not_a_misroute(self):
        task_file = self.tmp / "t.yaml"
        task_file.write_text("use_case: standard_report\n")
        write_run(self.agent, "r1", "a", 1, passed=True, cost=0.01, task_file=str(task_file),
                  trace=[{"type": "operator"}, {"type": "route", "use_case": "standard_report"},
                         {"type": "operator"}, {"type": "route", "use_case": "status_question"}])
        write_run(self.agent, "r2", "b", 1, passed=False, cost=0.01, task_file=str(task_file),
                  trace=[{"type": "operator"}, {"type": "route", "use_case": "messy_file"},
                         {"type": "operator"}, {"type": "route", "use_case": "standard_report"}])
        # r3: the first turn was declined before any route; only the follow-up routed
        write_run(self.agent, "r3", "c", 1, passed=False, cost=0.01, task_file=str(task_file),
                  trace=[{"type": "operator"}, {"type": "end", "terminal_reason": "declined"},
                         {"type": "operator"}, {"type": "route", "use_case": "status_question"}])
        routing = analyze.analyze_arm(self.agent)["routing"]
        self.assertEqual((routing["routes"], routing["scored_routes"], routing["misroutes"], routing["unrouted"]),
                         (5, 2, 1, 1))
        self.assertEqual(routing["misrouted_runs"], ["r2: messy_file for standard_report"])
        self.assertEqual(routing["unrouted_runs"], ["r3"])

    def test_a_registry_rejection_from_its_trace_line_is_a_boundary_rejection(self):
        # as agent/registry.py traces it: error_type, and an output with no error kind
        record_call = ("query_sales", {"period": "Q3"}, True, {"message": "bad period", "repair": "use 2026Q3"})
        write_run(self.agent, "r1", "a", 1, passed=False, cost=0.01, calls=(record_call,))
        rec = json.loads((self.agent / "r1.json").read_text())
        rec["tool_calls"][0]["error_type"] = "invalid_arguments"
        (self.agent / "r1.json").write_text(json.dumps(rec))
        self.assertEqual(analyze.analyze_arm(self.agent)["boundary"], {"tool_errors": 1, "boundary_rejections": 1})


if __name__ == "__main__":
    unittest.main()
