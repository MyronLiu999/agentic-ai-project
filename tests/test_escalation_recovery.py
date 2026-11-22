"""Accepted hold answers survive failures without losing or repeating their instruction."""
import json
import sqlite3
from unittest import mock

import channel
from agent import checkpoints, escalation, events, runs, service
from harness import ROOT, runtime, tasks, turns
from harness.client import Usage
from sandbox import control, queue, reports, seed
from tests.fixtures.agent_loop_fakes import tool
from tests.support import ScratchTest


REQUEST = 'REQ-SYN-thread-1001'
ANSWER = 'Retain the exact correction: revenue 120.00, reference A-17.'


class EscalationRecoveryTest(ScratchTest):
    def setUp(self):
        super().setUp()
        runtime.configure(backend='tests.fixtures.agent_loop_fakes:SequenceModel')
        channel.reset()
        seed.reset()
        with channel.seeding():
            seed.seed(tasks.load(ROOT / 'tasks/standard_report_clean.yaml'))
        self.session = 'escalation-recovery'

    def hold(self, **fields):
        with runtime.in_session(self.session):
            key = runs.new_run(self.session)
            checkpoints.save(key, {'path': 'agent', 'request_id': REQUEST,
                'operator_text': 'Handle this request.',
                'conversation': [{'role': 'user', 'content': 'Handle this request.'}], **fields})
            escalation.signal(key, 'failed_check', 'prepare the report', 'a checked figure needs correction',
                              'the corrected figure or an instruction to discard')
            return key, escalation.active_hold(key)['id']

    def accept(self, key, hold_id, text=ANSWER):
        return escalation._accept_answer(key, {'kind': 'escalation_answer', 'who': 'operator',
                                               'text': text, 'escalation': hold_id})

    def test_acceptance_atomically_saves_the_exact_answer_and_removes_the_wait(self):
        key, hold_id = self.hold()
        event = self.accept(key, hold_id)
        state = checkpoints.load(key)
        self.assertEqual(state.get('pending_operator_answer'),
                         {'kind': 'operator_turn', 'text': ANSWER, 'escalation': hold_id})
        self.assertEqual(state['pending_operator_answer'], event)
        self.assertIsNone(state.get('held'))
        self.assertIsNone(state.get('waiting_for'))
        self.assertEqual(checkpoints.waiting(self.session), [])
        self.assertEqual(queue.holds(run_key=key)[0]['answer'], ANSWER)
        self.assertEqual(runs.crashed(self.session), [key])
        self.assertEqual(reports.for_request(REQUEST), [])

    def test_failed_checkpoint_commit_keeps_the_hold_and_its_wait(self):
        key, hold_id = self.hold()
        before = checkpoints.load(key)
        with control.connect() as conn:
            conn.execute("CREATE TRIGGER reject_answer_checkpoint BEFORE INSERT ON checkpoints "
                         "BEGIN SELECT RAISE(ABORT, 'simulated checkpoint write failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.accept(key, hold_id)
        self.assertIsNotNone(escalation.active_hold(key))
        self.assertEqual(queue.holds(run_key=key)[0]['status'], 'held')
        self.assertEqual(checkpoints.load(key), before)
        self.assertEqual(checkpoints.waiting(self.session)[0]['ref'], hold_id)

    def test_crashes_before_executor_acknowledgment_replay_the_exact_operator_answer(self):
        key, hold_id = self.hold()
        with mock.patch('agent.runs.resume', side_effect=RuntimeError('crash after answer commit')):
            with self.assertRaisesRegex(RuntimeError, 'crash after answer commit'):
                turns.operator_turn(self.session, '/answer 1 ' + ANSWER)
        accepted = {'kind': 'operator_turn', 'text': ANSWER, 'escalation': hold_id}
        self.assertEqual(checkpoints.load(key).get('pending_operator_answer'), accepted)
        self.assertEqual(runs.crashed(self.session), [key])
        with runtime.in_session(self.session):
            with mock.patch('agent.loop.resume_from', side_effect=RuntimeError('crash before instruction checkpoint')):
                with self.assertRaisesRegex(RuntimeError, 'crash before instruction checkpoint'):
                    service.continue_run(key, {'kind': 'crash'})
        self.assertEqual(checkpoints.load(key).get('pending_operator_answer'), accepted)
        self.assertEqual(reports.for_request(REQUEST), [])
        backend = runtime.client(self.session).backend
        backend.responses = [([tool('save_report', {'kind': 'standard', 'body': ANSWER,
                               'figures': {'period': '2026Q3', 'total_revenue': 120.0}})],
                              'tool_use', Usage(10, 5))]
        with runtime.in_session(self.session):
            service.continue_run(key, {'kind': 'crash'})
        instructions = [json.loads(m['content']).get('operator_instruction')
                        for m in backend.requests[0]['messages']
                        if isinstance(m.get('content'), str) and m['content'].startswith('{')]
        self.assertIn(ANSWER, instructions)
        self.assertEqual([r['body'] for r in reports.for_request(REQUEST)], [ANSWER])
        self.assertEqual(queue.holds(run_key=key)[0]['status'], 'answered')

    def test_crash_after_instruction_checkpoint_does_not_append_the_answer_twice(self):
        key, hold_id = self.hold()
        event = self.accept(key, hold_id)
        self.assertEqual(checkpoints.load(key).get('pending_operator_answer'), event)
        with runtime.in_session(self.session), mock.patch('agent.loop._Loop.execute',
                                                          side_effect=RuntimeError('crash after instruction checkpoint')):
            with self.assertRaisesRegex(RuntimeError, 'crash after instruction checkpoint'):
                runs.resume(key, {'kind': 'crash'})
        state = checkpoints.load(key)
        self.assertIsNone(state.get('pending_operator_answer'))
        self.assertEqual(state.get('accepted_operator_answer'), event)
        self.assertEqual(reports.for_request(REQUEST), [])
        with runtime.in_session(self.session):
            service.continue_run(key, {'kind': 'crash'})
        first_request = runtime.client(self.session).backend.requests[0]
        instructions = [json.loads(m['content']).get('operator_instruction')
                        for m in first_request['messages']
                        if isinstance(m.get('content'), str) and m['content'].startswith('{')]
        self.assertEqual(instructions.count(ANSWER), 1)

    def test_fixed_executors_reject_corrections_without_releasing_the_hold(self):
        for fields in ({'path': 'workflow'}, {'split_state': {'phase': 'held'}}):
            with self.subTest(fields=fields):
                key, hold_id = self.hold(**fields)
                before = checkpoints.load(key)
                reply = self.accept(key, hold_id)
                self.assertIsNotNone(escalation.active_hold(key))
                self.assertEqual(checkpoints.load(key), before)
                self.assertIn('retry', reply.text.lower())
                self.assertIn('discard', reply.text.lower())

    def test_explicit_fixed_retry_is_acknowledged_before_normal_execution(self):
        for fields, target in (({'path': 'workflow'}, 'agent.workflows.resume'),
                               ({'split_state': {'phase': 'held'}}, 'agent.loop.resume_from')):
            with self.subTest(fields=fields):
                key, hold_id = self.hold(**fields)
                event = self.accept(key, hold_id, ' ReTrY ')
                with runtime.in_session(self.session), mock.patch(target, side_effect=RuntimeError('executor crash')):
                    with self.assertRaisesRegex(RuntimeError, 'executor crash'):
                        runs.resume(key, {'kind': 'crash'})
                state = checkpoints.load(key)
                self.assertEqual(state.get('accepted_operator_answer'), event)
                self.assertIsNone(state.get('pending_operator_answer'))
                self.assertEqual(reports.for_request(REQUEST), [])

    def test_explicit_discard_ends_fixed_runs_without_executing_them(self):
        for fields in ({'path': 'workflow'}, {'split_state': {'phase': 'held'}}):
            with self.subTest(fields=fields):
                key, hold_id = self.hold(**fields)
                self.accept(key, hold_id, ' DiScArD ')
                self.assertIsNotNone(checkpoints.load(key).get('pending_operator_answer'))
                with runtime.in_session(self.session):
                    runs.resume(key, {'kind': 'crash'})
                self.assertNotIn(key, runs.live(self.session))
                state = checkpoints.load(key)
                self.assertTrue(state.get('cancelled'))
                self.assertIsNone(state.get('pending_operator_answer'))
                with control.connect() as conn:
                    ended = conn.execute('SELECT end_reason FROM runs WHERE run_key=?', (key,)).fetchone()
                self.assertEqual(ended['end_reason'], events.CANCELLED)
                self.assertEqual(reports.for_request(REQUEST), [])
                self.assertEqual(runtime.client(self.session).calls, 0)

    def test_discard_is_terminal_even_if_its_acknowledgment_checkpoint_fails(self):
        key, hold_id = self.hold(path='workflow', workflow='standard_report')
        accepted = self.accept(key, hold_id, 'discard')
        with control.connect() as conn:
            conn.execute("CREATE TRIGGER reject_discard_checkpoint BEFORE INSERT ON checkpoints "
                         "BEGIN SELECT RAISE(ABORT, 'simulated discard acknowledgment failure'); END")
        with runtime.in_session(self.session), self.assertRaises(sqlite3.IntegrityError):
            runs.resume(key, {'kind': 'crash'})
        self.assertNotIn(key, runs.live(self.session))
        self.assertEqual(checkpoints.load(key).get('pending_operator_answer'), accepted)
        with control.connect() as conn:
            ended = conn.execute('SELECT end_reason FROM runs WHERE run_key=?', (key,)).fetchone()
            conn.execute('DROP TRIGGER reject_discard_checkpoint')
        self.assertEqual(ended['end_reason'], events.CANCELLED)
        with runtime.in_session(self.session):
            runs.resume(key, {'kind': 'crash'})
        self.assertIsNone(checkpoints.load(key).get('pending_operator_answer'))
        self.assertEqual(reports.for_request(REQUEST), [])
        self.assertEqual(runtime.client(self.session).calls, 0)
