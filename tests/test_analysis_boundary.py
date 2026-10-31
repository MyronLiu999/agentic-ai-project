"""Exercise error statistics with records emitted by the real Registry."""

import copy
import json

from agent.registry import MODEL, Registry, ToolSpec, TransientToolError
from experiments.analysis.analyze import _error_kind, analyze_arm
from harness.trace import SessionTrace
from tests.support import ScratchTest


EMPTY = {"type": "object", "properties": {}, "additionalProperties": False}


class AnalysisBoundaryTest(ScratchTest):
    def _calls(self):
        trace = SessionTrace(self.tmp / "registry.jsonl", "SYN-analysis")

        def permanent():
            raise ValueError("The requested record does not exist.")

        def transient():
            raise TransientToolError("Database temporarily unavailable.")

        registry = Registry([
            ToolSpec("read", "Read synthetic data.", EMPTY, lambda: {"value": "完整结果"}),
            ToolSpec("permanent", "Permanent failure.", EMPTY, permanent),
            ToolSpec("transient", "Transient failure.", EMPTY, transient),
        ], trace=trace, max_retries=0)
        registry.call("read", {"unexpected": True}, MODEL)
        registry.call("unknown", {}, MODEL)
        registry.call("read", {}, MODEL)
        registry.call("permanent", {}, MODEL)
        registry.call("transient", {}, MODEL)
        return trace.lines()

    def _summary(self, calls, name):
        folder = self.tmp / name
        folder.mkdir()
        record = {"run_id": "SYN-analysis", "task": "synthetic", "sweep": 1,
                  "passed": False, "tool_calls": calls}
        (folder / "SYN-analysis.json").write_text(
            json.dumps(record, ensure_ascii=False), encoding="utf-8"
        )
        (folder / "SYN-analysis.trace.jsonl").write_text(
            "".join(json.dumps(call, ensure_ascii=False) + "\n" for call in calls),
            encoding="utf-8",
        )
        return analyze_arm(folder)

    def test_full_registry_records_count_only_protocol_errors_as_rejections(self):
        calls = self._calls()
        self.assertEqual([_error_kind(call) for call in calls],
                         ["protocol", "protocol", None, "permanent", "transient"])
        summary = self._summary(calls, "full")
        self.assertEqual(summary["boundary"], {"tool_errors": 4, "boundary_rejections": 2})

    def test_legacy_registry_summaries_use_error_type_metadata(self):
        calls = copy.deepcopy(self._calls())
        for call in calls:
            # Before Step 1, Registry recorded only the output summary plus
            # error_type metadata, rather than the complete result envelope.
            call["output"] = json.dumps(call["output"]["output"], ensure_ascii=False)
        self.assertEqual([_error_kind(call) for call in calls],
                         ["protocol", "protocol", None, "permanent", "transient"])
        summary = self._summary(calls, "legacy")
        self.assertEqual(summary["boundary"], {"tool_errors": 4, "boundary_rejections": 2})

    def test_error_message_cannot_claim_a_protocol_rejection(self):
        self.assertEqual(_error_kind({"is_error": True, "output": "remote protocol timed out"}), "error")
        self.assertEqual(_error_kind({"is_error": False, "error_type": "invalid_arguments"}), None)

    def test_truncated_legacy_output_still_uses_metadata(self):
        self.assertEqual(_error_kind({"is_error": True, "output": '{"message": "truncated',
                                      "error_type": "invalid_arguments"}), "protocol")

    def test_json_encoded_error_envelope_and_explicit_kind_are_preserved(self):
        self.assertEqual(_error_kind({
            "is_error": True,
            "output": json.dumps({"error": {"kind": "permanent"}}),
            "error_type": "invalid_arguments",
        }), "permanent")
