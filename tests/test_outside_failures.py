"""Normal compaction/waits are context, while actual interrupted endings are diagnoses."""
from pathlib import Path
import json
import tempfile
import unittest

from experiments.analysis.failures import inspect_record


class M2FailureAnalysisTest(unittest.TestCase):
    def test_compaction_and_wait_do_not_mask_first_failed_check(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'run.json'
            lines = [{'type': 'compaction', 'before_tokens': 18000, 'after_tokens': 8000},
                     {'type': 'wait', 'kind': 'outside'},
                     {'type': 'end', 'terminal_reason': 'held', 'detail': 'reply deadline expired'}]
            path.with_suffix('.trace.jsonl').write_text('\n'.join(json.dumps(v) for v in lines))
            result = inspect_record({'run_id': 'r', 'passed': False}, path, Path(folder))
            self.assertEqual(result['first_failure']['kind'], 'held')
            self.assertEqual(result['first_failure']['line'], 3)
            self.assertEqual(result['control_events'], {'compaction': 1, 'wait': 1})

    def test_stop_end_is_labelled_as_operator_control(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'run.json'
            path.with_suffix('.trace.jsonl').write_text(json.dumps(
                {'type': 'end', 'terminal_reason': 'stopped', 'detail': 'operator requested a stop'}))
            result = inspect_record({'run_id': 'r'}, path, Path(folder))
            self.assertEqual(result['first_failure']['kind'], 'stopped')
