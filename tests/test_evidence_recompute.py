"""Portable provenance and trace annotations are checked against source bytes."""
import hashlib
import json
import unittest
from pathlib import Path

from tests.support import ScratchTest
from experiments.analysis import recompute


class EvidenceRecomputeTest(ScratchTest):
    def test_lf_hash_is_portable_but_original_crlf_hash_is_verified(self):
        original = b'{"value": 1}\r\n'
        legacy = hashlib.sha256(original).hexdigest()
        path = self.tmp / "record.json"
        path.write_bytes(original)
        windows = recompute.verified_hash(path, legacy)
        path.write_bytes(original.replace(b"\r\n", b"\n"))
        self.assertEqual(recompute.verified_hash(path, legacy), windows)
        self.assertEqual(windows["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(windows["original_sha256"], legacy)
        path.write_bytes(b'{"value": 2}\n')
        with self.assertRaisesRegex(ValueError, "provenance"):
            recompute.verified_hash(path, legacy)

    def _annotation(self):
        trace = self.tmp / "sample.trace.jsonl"
        event = {"type": "tool_call", "run_id": "sample", "name": "save_report",
                 "input": {"figures": {"total_revenue": 0}}}
        trace.write_text("\n" + json.dumps(event) + "\n", encoding="utf-8")
        return {"arm": "synthetic", "run_id": "sample", "category": "incorrect_report_figures",
                "count_unit": "argument_candidate", "trace": trace.name,
                "trace_sha256_lf": recompute.lf_sha256(trace.read_bytes()), "line": 2,
                "event_type": "tool_call", "tool": "save_report", "selector": ["input"],
                "observed": event["input"], "reason": "Synthetic zero differs from the named source figure."}

    def test_annotations_use_physical_lines_and_verify_exact_argument_candidate(self):
        entry = self._annotation()
        self.assertEqual(recompute.validate_annotations(self.tmp, [entry]), [entry])
        entry["line"] = 1
        with self.assertRaises(ValueError):
            recompute.validate_annotations(self.tmp, [entry])

    def test_annotation_drift_and_duplicate_candidates_are_rejected(self):
        entry = self._annotation()
        entry["observed"]["figures"]["total_revenue"] = 1
        with self.assertRaisesRegex(ValueError, "observed"):
            recompute.validate_annotations(self.tmp, [entry])
        entry = self._annotation()
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            recompute.validate_annotations(self.tmp, [entry, entry])
        trace = self.tmp / entry["trace"]
        trace.write_text(trace.read_text().replace('"total_revenue": 0', '"total_revenue": 2'))
        with self.assertRaisesRegex(ValueError, "hash"):
            recompute.validate_annotations(self.tmp, [entry])

    def test_semantic_candidate_can_overlap_boundary_rejection_without_being_malformed(self):
        entry = self._annotation()
        run = {"run_id": "sample", "tool_calls": [
            {"name": "save_report", "is_error": True, "rejected_by": "loop", "input": {"report_id": 0},
             "output": {"error": {"kind": "protocol"}}},
            {"name": "save_report", "is_error": True, "input": {"unexpected": 5},
             "error_type": "invalid_arguments", "output": {"error": {"kind": "protocol"}}}]}
        schemas = {"save_report": {"type": "object", "properties": {"report_id": {"type": "integer"}},
                                   "required": ["report_id"], "additionalProperties": False}}
        stats = recompute.argument_metrics([run], [entry], schemas)
        self.assertEqual(stats["malformed_calls"], 1)
        self.assertEqual(stats["boundary_rejections"], 2)
        self.assertEqual(stats["semantic_wrong_argument_candidates"], 1)
        self.assertEqual(stats["semantic_wrong_argument_runs"], 1)
        self.assertEqual(stats["per_run"][0]["malformed_calls"], 1)

    def test_fact_citation_checks_the_named_value_at_its_physical_line(self):
        entry = self._annotation()
        entry["facts"] = [{"path": entry["trace"], "sha256_lf": entry["trace_sha256_lf"],
                           "line": 2, "selector": ["input", "figures", "total_revenue"],
                           "observed": 999}]
        with self.assertRaisesRegex(ValueError, "fact"):
            recompute.validate_annotations(self.tmp, [entry])

    def test_model_citation_must_propose_the_annotated_tool_arguments(self):
        entry = self._annotation()
        path = self.tmp / entry["trace"]
        event = json.loads(path.read_text().splitlines()[1])
        event["id"] = "actual-call"
        model = {"type": "model_call", "run_id": "sample", "tool_calls": [
            {"id": "other-call", "name": "save_report", "input": {"figures": {"total_revenue": 9}}}]}
        path.write_text(json.dumps(model) + "\n" + json.dumps(event) + "\n")
        entry["line"], entry["model_line"] = 2, 1
        entry["trace_sha256_lf"] = recompute.lf_sha256(path.read_bytes())
        with self.assertRaisesRegex(ValueError, "model"):
            recompute.validate_annotations(self.tmp, [entry])

    def test_malformed_call_checks_frozen_pattern_and_numeric_array_constraints(self):
        runs = [{"run_id": "shape", "tool_calls": [
            {"name": "query", "input": {"period": "Q3"}},
            {"name": "chart", "input": {"values": [-1, 2, 3]}},
            {"name": "chart", "input": {"values": [0, 1]}}]}]
        schemas = {"query": {"type": "object", "properties": {"period": {
            "type": "string", "pattern": "^[0-9]{4}Q[1-4]$"}}},
            "chart": {"type": "object", "properties": {"values": {
                "type": "array", "maxItems": 2, "items": {"type": "number", "minimum": 0}}}}}
        metrics = recompute.argument_metrics(runs, [], schemas)
        self.assertEqual(metrics["malformed_calls"], 2)

    def test_percent_difference_keeps_task_specific_denominator(self):
        self.assertEqual(recompute.difference(10, 15), {"absolute": 5, "percent": 50.0})
        self.assertEqual(recompute.difference(0, 2), {"absolute": 2, "percent": None})

class HistoricalGeneratorTest(ScratchTest):
    """A tiny unrelated protocol exercises the generator without repo result totals."""
    def setUp(self):
        super().setUp()
        self.root = self.tmp / "checkout"
        self.evidence = self.root / "experiments/evidence"
        self.evidence.mkdir(parents=True)
        config = {"settings": "synthetic-settings", "backend": "synthetic", "price_sheet": "synthetic",
                  "model": "synthetic"}
        self.protocol = {"commit": "synthetic-commit", "prediction_committed_at": "2020-01-01T00:00:00+00:00",
                         "arms": {"control": "off", "treatment": "on"}, "tasks": ["other-task"],
                         "sweeps": [1], "target_task": "other-task", "configuration": config}
        self.provenance = {}
        for arm, switch in (("baseline", "off"), *self.protocol["arms"].items()):
            folder = self.root / "results" / arm
            folder.mkdir(parents=True)
            record = {"run_id": arm, "arm": arm, "task": "other-task", "sweep": 1, "passed": True,
                      "outcome": "completed", "commit": "synthetic-commit", "dirty": False, "free": False,
                      "started": "2020-01-02T00:00:00Z", "switches": {"examples.save_report": switch},
                      "tokens": {"total": 7 if switch == "off" else 11}, "cost_usd": 0.1,
                      "tool_calls": [], "end_reason": "done", "end_reasons": ["done"], **config}
            path = folder / f"{arm}.json"
            path.write_bytes((json.dumps(record) + "\r\n").encode())
            trace = [{"type": "run_start", **record}, {"type": "operator"},
                     {"type": "end", "terminal_reason": "done"}]
            path.with_suffix(".trace.jsonl").write_bytes(
                ("\r\n".join(json.dumps(event) for event in trace) + "\r\n").encode())
            for source in (path, path.with_suffix(".trace.jsonl")):
                self.provenance[source.relative_to(self.root).as_posix()] = hashlib.sha256(source.read_bytes()).hexdigest()
        inputs = {"pass1_protocol": self.protocol, "original_sha256": self.provenance,
                  "argument_schemas": {}, "development_runs": [],
                  "baseline_provenance": {"origin": "Synthetic fixture bytes frozen before mutation",
                    "commit": "synthetic-baseline-capture", "files": [
                        path for path in self.provenance if path.startswith("results/baseline/")]}}
        (self.evidence / "analysis_inputs.json").write_text(json.dumps(inputs))
        (self.evidence / "semantic_annotations.json").write_text(json.dumps({"definitions": {}, "annotations": []}))

    def test_generator_reproduces_outputs_after_relocation_and_newline_conversion(self):
        import shutil
        expected = recompute.build_outputs(self.root)
        relocated = self.tmp / "relocated"
        shutil.copytree(self.root, relocated)
        for path in relocated.rglob("*"):
            if path.is_file():
                path.write_bytes(recompute.normalize_lf(path.read_bytes()))
        self.assertEqual(recompute.build_outputs(relocated), expected)
        self.assertEqual(expected["additional_metrics.json"]["target"]["treatment"]["mean_tokens"], 11)
        self.assertEqual(expected["additional_metrics.json"]["differences_on_minus_off"]["target_mean_tokens"]["absolute"], 4)
        self.assertEqual(len(expected["pass1_audit.json"]["files"]), 4)

    def test_audit_rejects_duplicate_pairs_and_changed_configuration(self):
        path = self.root / "results/control/control.json"
        duplicate = path.with_name("duplicate.json")
        duplicate.write_bytes(path.read_bytes())
        with self.assertRaisesRegex(ValueError, "coverage"):
            recompute.build_audit(self.root, self.protocol, self.provenance)
        duplicate.unlink()
        record = json.loads(path.read_text())
        record["started"] = "2019-01-01T00:00:00Z"
        path.write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError, "prediction"):
            recompute.build_audit(self.root, self.protocol, self.provenance)

    def test_generator_rejects_baseline_record_mutation_before_recomputing_scores(self):
        record_path = self.root / "results/baseline/baseline.json"
        record = json.loads(record_path.read_text())
        record["passed"] = False
        record_path.write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError, "provenance"):
            recompute.build_outputs(self.root)

    def test_generator_rejects_unannotated_baseline_trace_mutation(self):
        trace = self.root / "results/baseline/baseline.trace.jsonl"
        trace.write_text(trace.read_text() + json.dumps({"type": "extra"}) + "\n")
        with self.assertRaisesRegex(ValueError, "provenance"):
            recompute.build_outputs(self.root)
