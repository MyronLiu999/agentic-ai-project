import json
import tempfile
import unittest
from pathlib import Path

from experiments.analysis.basic_analyze import analyze, load_records


class AnalysisTest(unittest.TestCase):
    def test_recomputes_arm_and_cross_path_measures(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for arm, path, passed, cost in (
                ("before", "workflow", False, 1.0),
                ("after", "agent", True, 2.0),
            ):
                arm_dir = root / arm
                arm_dir.mkdir()
                run_id = f"{arm}-task-s01"
                record = {
                    "run_id": run_id, "arm": arm, "task_id": "task", "sweep": 1,
                    "path": path, "cost_usd": cost, "turn_latency_s": [1.0, 3.0],
                    "check": {"passed": passed}, "end_reason": "done", "end_reasons": ["done"],
                    "tool_calls": [
                        {"name": "query", "input": {"x": 1}},
                        {"name": "query", "input": {"x": 1}},
                    ],
                }
                (arm_dir / f"{run_id}.json").write_text(json.dumps(record), encoding="utf-8")
                (arm_dir / f"{run_id}.trace.jsonl").write_text(
                    json.dumps({"type": "critique", "round": 1,
                                "verdict": "held" if arm == "before" else "pass"}) + "\n",
                    encoding="utf-8",
                )
            self.assertEqual(len(load_records(root / "after")), 1)
            summary = analyze(load_records(root))
        self.assertEqual(summary["arms"]["before"]["false_finishes"], 1)
        self.assertEqual(summary["arms"]["after"]["runs_with_exact_repeat"], 1)
        self.assertEqual(summary["arms"]["before"]["held_drafts"], 1)
        self.assertEqual(summary["cross_path"]["m_agent_over_workflow_mean_cost"], 2.0)
        self.assertEqual(summary["cross_path"]["f_agent_pass_workflow_fail"], 1.0)


if __name__ == "__main__":
    unittest.main()
