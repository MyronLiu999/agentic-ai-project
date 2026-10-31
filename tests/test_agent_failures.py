"""Handwritten records/traces keep failure analysis independent of agent logic."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from experiments.analysis import failures


class AgentFailuresTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def record(self, name="run-one", folder="baseline", lines=None, **changes):
        target = self.root / "results" / folder
        target.mkdir(parents=True, exist_ok=True)
        trace = target / f"{name}.trace.jsonl"
        if lines is not None:
            trace.write_text("\n".join(json.dumps(line) if isinstance(line, dict) else line for line in lines) + "\n")
        record = {"run_id": name, "arm": folder, "task": "synthetic-task", "outcome": "completed", "passed": False,
                  "end_reasons": ["step_limit"], "check": {"passed": False, "reason": "No report"},
                  "trace": str(trace.relative_to(self.root)), **changes}
        path = target / f"{name}.json"
        path.write_text(json.dumps(record))
        return path

    def collect(self, **kwargs):
        return failures.collect(self.root / "results", repo_root=self.root, **kwargs)

    def test_first_nested_tool_error_has_the_physical_trace_line(self):
        self.record(lines=[{"type": "operator"}, "", {"type": "tool_call", "name": "parse_file", "is_error": False,
                    "output": {"ok": False, "is_error": True, "error": {"kind": "protocol", "message": "Bad delimiter"}}},
                    {"type": "end", "terminal_reason": "step_limit"}])
        row = self.collect()["failures"][0]
        self.assertEqual(row["first_failure"], {"line": 3, "kind": "tool_error", "message": "parse_file: Bad delimiter"})
        self.assertEqual(row["end_reasons"], ["step_limit"])

    def test_missing_trace_keeps_failed_run_and_reports_absent_evidence(self):
        self.record()
        row = self.collect()["failures"][0]
        self.assertIsNone(row["first_failure"]["line"])
        self.assertEqual(row["first_failure"]["kind"], "record_only")
        self.assertIn("No report", row["first_failure"]["message"])
        self.assertTrue(row["evidence_issues"])

    def test_malformed_trace_lines_do_not_shift_later_line_numbers(self):
        self.record(lines=["not JSON", {"type": "error", "kind": "RuntimeError", "message": "Broken tool"}])
        row = self.collect()["failures"][0]
        self.assertEqual(row["first_failure"]["line"], 2)
        self.assertIn("line 1", row["evidence_issues"][0])

    def test_first_observed_failure_can_precede_the_terminal_bound(self):
        self.record(lines=[{"type": "checkpoint", "step_id": "query", "passed": False, "reason": "Wrong scope"},
                           {"type": "end", "terminal_reason": "replan_bound"}], end_reasons=["replan_bound"])
        first = self.collect()["failures"][0]["first_failure"]
        self.assertEqual((first["line"], first["kind"]), (1, "checkpoint_failed"))

    def test_check_failure_and_crash_are_not_confused_with_successful_end_turns(self):
        self.record("failed-check", lines=[{"type": "end", "terminal_reason": "done"},
                                           {"type": "run_end", "outcome": "completed", "passed": False}], end_reasons=["done"])
        self.record("crashed", lines=[{"type": "error", "kind": "RuntimeError", "message": "Crash"}],
                    outcome="crashed", passed=True)
        self.record("passed", lines=[{"type": "end", "terminal_reason": "done"}], passed=True)
        rows = self.collect()["failures"]
        self.assertEqual({r["run_id"] for r in rows}, {"failed-check", "crashed"})
        checked = next(r for r in rows if r["run_id"] == "failed-check")
        self.assertEqual(checked["first_failure"]["line"], 2)
        self.assertEqual(checked["first_failure"]["kind"], "check_failed")

    def test_synthetic_and_discarded_runs_are_excluded_unless_requested(self):
        self.record("measured", lines=[])
        self.record("fake", folder="_free/smoke", lines=[], free=True)
        self.record("discarded", folder="discarded/old", lines=[])
        self.assertEqual([r["run_id"] for r in self.collect()["failures"]], ["measured"])
        report = self.collect(include_free=True, include_discarded=True)
        self.assertEqual(len(report["failures"]), 3)
        self.assertTrue(next(r for r in report["failures"] if r["run_id"] == "fake")["synthetic"])

    def test_invalid_record_is_reported_without_hiding_other_failures(self):
        path = self.record(lines=[])
        path.with_name("broken.json").write_text("{")
        report = self.collect()
        self.assertEqual(len(report["failures"]), 1)
        self.assertEqual(len(report["issues"]), 1)

    def test_cli_json_and_markdown_include_trace_evidence(self):
        self.record(lines=[{"type": "end", "terminal_reason": "agent_budget"}])
        command = [sys.executable, "-m", "experiments.analysis.failures", str(self.root / "results"),
                   "--repo-root", str(self.root)]
        data = subprocess.run(command + ["--json"], text=True, capture_output=True, check=True)
        self.assertEqual(json.loads(data.stdout)["failures"][0]["first_failure"]["line"], 1)
        markdown = subprocess.run(command, text=True, capture_output=True, check=True)
        self.assertIn("run-one.trace.jsonl:1", markdown.stdout)
        self.assertIn("agent_budget", markdown.stdout)

    def test_invalid_and_held_plan_lines_are_explicit_failure_signals(self):
        for number, line in enumerate(({"type": "plan", "accepted": False, "reason": "Cycle"},
                                       {"type": "critique", "verdict": "held", "reason": "Wrong recipient"},
                                       {"type": "off_plan_refused", "tool": "send_report"})):
            self.record(f"case-{number}", lines=[line])
        self.assertEqual({r["first_failure"]["kind"] for r in self.collect()["failures"]},
                         {"plan_rejected", "critique_held", "off_plan_refused"})

    def test_evidence_notes_do_not_interrupt_the_markdown_table(self):
        self.record("a-missing")
        self.record("z-last", lines=[{"type": "end", "terminal_reason": "step_limit"}])
        rendered = failures.markdown(self.collect())
        self.assertLess(rendered.index("| z-last |"), rendered.index("Evidence issue"))
