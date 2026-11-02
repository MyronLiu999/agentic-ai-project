"""Archiving preserves evidence bytes while allowing portable LF/CRLF hashes."""
import hashlib
import json

from scripts import archive_dev_evidence
from tests.support import ScratchTest


class ArchiveEvidenceTest(ScratchTest):
    def test_existing_lf_copy_matches_crlf_source_without_replacing_evidence(self):
        folder = self.tmp / "results/dev-synthetic"
        folder.mkdir(parents=True)
        record = {"run_id": "sample", "arm": "dev-synthetic", "free": False,
                  "tool_calls": [{"name": "synthetic"}]}
        (folder / "sample.json").write_text(json.dumps(record))
        original = b'{"type":"run_start","run_id":"sample"}\r\n'
        (folder / "sample.trace.jsonl").write_bytes(original)
        destination = self.tmp / "traces"
        destination.mkdir()
        copied = destination / "sample.trace.jsonl"
        copied.write_bytes(original.replace(b"\r\n", b"\n"))
        before = copied.read_bytes()
        report = archive_dev_evidence.archive_runs([folder], root=self.tmp)
        self.assertEqual(copied.read_bytes(), before)
        self.assertEqual(report["runs"][0]["trace_sha256"], hashlib.sha256(before).hexdigest())
        self.assertEqual(report["runs"][0]["original_trace_sha256"], hashlib.sha256(original).hexdigest())
        copied.write_bytes(b'{"changed": true}\n')
        with self.assertRaisesRegex(ValueError, "different evidence"):
            archive_dev_evidence.archive_runs([folder], root=self.tmp)
