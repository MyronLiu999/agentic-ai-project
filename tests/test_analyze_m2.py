"""analyze.py's Milestone 2 numbers (experiments/analysis/m2.py; owner: myron, M9), on hand-written records."""

import json
import tempfile
import unittest
from pathlib import Path

from experiments.analysis.analyze import analyze_arm, report


def write(folder: Path, run_id: str, sweep: int, trace: list[dict], *, measures=None, asked=0, loading="all"):
    record = {"run_id": run_id, "task": "approval_send_report", "sweep": sweep, "passed": True, "cost_usd": 0.001,
              "tokens": {"total": 1000}, "turn_latency_s": [1.0], "outcome": "completed", "tool_calls": [],
              "end_reasons": ["done"], "end_reason": "done", "measures": measures or {},
              "approvals": {"asked": asked, "answered": asked, "unanswered": 0},
              "switches": {"tools.loading": loading}, "started": f"2026-11-22T10:0{sweep}:00"}
    (folder / f"{run_id}.json").write_text(json.dumps(record), encoding="utf-8")
    (folder / f"{run_id}.trace.jsonl").write_text("".join(json.dumps(x) + "\n" for x in trace), encoding="utf-8")


class AnalyzeM2Test(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.arm = Path(self._tmp.name) / "m2-build"
        self.arm.mkdir()
        model = lambda i, c=0: {"type": "model_call", "usage": {"input_tokens": i, "cache_read_input_tokens": c}}
        write(self.arm, "r1", 1, [
            model(900, 100), model(1000),
            {"type": "hook_decision", "tool": "send_report_email", "action_class": "send_report_email/own_contact",
             "answer": "ask"},
            {"type": "hook_decision", "tool": "parse_file", "answer": "allow"},
            {"type": "approval_decision", "action_class": "send_report_email/own_contact", "decision": "approved",
             "who": "operator", "seconds": 12.0},
            {"type": "tool_call", "name": "query_sales", "error_type": "invalid_arguments"},
            {"type": "escalation", "signal": "failed_check", "over_cap": False},
        ], measures={"duplicate_reports": 1, "sends": 1}, asked=1)
        write(self.arm, "r2", 2, [
            model(700),
            {"type": "search_tools", "query": "chart", "matches": ["render_chart"], "offered": 6},
            {"type": "search_tools", "query": "teleport", "matches": [], "offered": 6},
            {"type": "approval_decision", "action_class": "send_report_email/own_contact", "decision": "rejected",
             "who": "scripted", "seconds": 0.01},
            {"type": "escalation", "signal": "failed_check", "over_cap": True},
            {"type": "code_call", "calls": 3},
            {"type": "compaction"},
        ], measures={"duplicate_emails": 2, "irreversible_after_signal": 0}, asked=1, loading="deferred")

    def tearDown(self):
        self._tmp.cleanup()

    def test_every_m2_number_from_the_records(self):
        m = analyze_arm(self.arm)["m2"]
        self.assertEqual(m["runs"], 2)
        self.assertEqual(m["duplicates"], 3)
        self.assertEqual((m["approvals_asked"], m["asks"], m["asks_per_run"]), (2, 3, 1.5))   # 1 packet over cap
        self.assertEqual(m["asks_by_class"], {"send_report_email/own_contact": 1})
        person = m["approval_decisions"]["send_report_email/own_contact (person)"]
        self.assertEqual((person["decided"], person["approved"], person["median_seconds"]), (1, 1, 12.0))
        scripted = m["approval_decisions"]["send_report_email/own_contact (scripted)"]
        self.assertEqual((scripted["approved"], scripted["rate"]), (0, 0.0))
        self.assertEqual((m["escalations"], m["escalations_over_cap"]), (2, 1))
        self.assertEqual((m["malformed_calls"], m["model_calls"], m["model_calls_per_run"]), (1, 3, 1.5))
        self.assertEqual(m["input_tokens_per_call"], (1000 + 1000 + 700) / 3)
        self.assertEqual((m["searches"], m["search_misses"], m["tools_per_call_after_search"]), (2, 1, 6))
        self.assertEqual(m["tools_loading"], {"all": 1, "deferred": 1})
        self.assertEqual((m["compactions"], m["code_calls"], m["code_inner_calls"]), (1, 1, 3))
        self.assertEqual(m["hook_decisions"], {"ask": 1, "allow": 1})

    def test_the_report_prints_them(self):
        text = report([analyze_arm(self.arm)], None)
        self.assertIn("Milestone 2:", text)
        self.assertIn("asks 3 (1.50 per run)", text)
        self.assertIn("searches 2, misses 1", text)


if __name__ == "__main__":
    unittest.main()
