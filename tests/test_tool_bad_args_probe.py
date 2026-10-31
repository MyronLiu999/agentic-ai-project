"""The Part 3 negative probe uses the real service, loop, tools and trace writer."""

from experiments.analysis.analyze import analyze_arm
from tests.support import ScratchTest


TASK = "tests/fixtures/tool_bad_arguments.yaml"
MODEL = "tests.fixtures.tool_bad_args_model:BadArgs"


class ToolBadArgsProbeTest(ScratchTest):
    def test_real_system_returns_all_six_errors_without_writes(self):
        record = self.run_task(TASK, "bad-args-probe", backend=MODEL)
        self.assertTrue(record["free"])
        self.assertTrue(record["passed"], record["check"]["reason"])
        self.assertEqual(record["measures"],
                         {"rejected_tool_calls": 6, "writes": 0, "email_gate_rejections": 1})
        self.assertEqual(len(record["tool_calls"]), 6)
        summary = analyze_arm(self.tmp / "results" / "_free" / "bad-args-probe")
        self.assertEqual(summary["boundary"], {"tool_errors": 6, "boundary_rejections": 6})

    def test_success_claim_without_probe_calls_fails_the_check(self):
        result = self.run_check(TASK, lambda run: None, replies=["Done."])
        self.assertFalse(result["passed"])
