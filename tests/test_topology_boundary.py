"""A preserved split checkpoint must never become ordinary single-agent work."""

from dataclasses import asdict

from agent import bounds, checkpoints, events, loop, runs
from harness import runtime
from sandbox import reports
from tests.support import ScratchTest, fixed_run


class TopologyBoundaryTest(ScratchTest):
    def test_split_checkpoint_refuses_execution_and_keeps_its_saved_state(self):
        with fixed_run('tasks/standard_report_clean.yaml', 'split-boundary',
                       backend='tests.fixtures.agent_loop_fakes:SequenceModel'):
            key = runs.new_run('split-boundary')
            saved = checkpoints.save(key, {
                'path': 'agent', 'request_id': 'REQ-SYN-thread-1001',
                'split_state': {'request_ids': ['REQ-SYN-thread-1001'], 'text': 'Continue split work.',
                    'limits': asdict(bounds.Limits(max_steps=48)), 'request_index': 0, 'role': 'analyst',
                    'messages': [], 'ledger': [], 'returns': {}, 'actions': [], 'tokens': 0, 'rounds': 0,
                    'role_tokens': 0, 'pending_calls': [], 'pending_results': [], 'prepared_args': None,
                    'approval_id': None, 'reserved_tokens': 0, 'model_response': None, 'role_return': None,
                    'evidence': {}, 'operator_additions': [], 'role_additions_seen': 0}})
            result = loop.resume_from(saved, {'kind': 'crash'})
            self.assertEqual(result.reason, events.HELD)
            self.assertIn('m2-split-final', result.text)
            self.assertEqual(checkpoints.load(key), saved)
            self.assertEqual(runtime.client().calls, 0)
            self.assertEqual(reports.for_request('REQ-SYN-thread-1001'), [])
