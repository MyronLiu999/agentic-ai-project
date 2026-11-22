"""Console answers release only the selected hold at an idle execution boundary."""
import copy
import json
import threading
from unittest import mock

import channel
from agent import bounds, checkpoints, escalation, events, plan, runs, service
from harness import ROOT, runtime, tasks, turns
from sandbox import queue, reports, seed
from tests.fixtures.agent_loop_fakes import SequenceModel, tool
from harness.client import Usage
from tests.support import ScratchTest


REQUEST = 'REQ-SYN-thread-1001'
BACKEND = 'tests.fixtures.agent_loop_fakes:SequenceModel'


class BlockingAnswerModel(SequenceModel):
    def __init__(self, settings=None):
        super().__init__(settings)
        self.entered = threading.Event()
        self.release = threading.Event()

    def create(self, **kwargs):
        self.entered.set()
        if not self.release.wait(timeout=10):
            raise AssertionError('The answer continuation was not released')
        return super().create(**kwargs)


class EscalationConsoleTest(ScratchTest):
    def setUp(self):
        super().setUp()
        runtime.configure(backend=BACKEND)
        channel.reset()
        seed.reset()
        with channel.seeding():
            seed.seed(tasks.load(ROOT / 'tasks/standard_report_clean.yaml'))
        self.session = 'escalation-console'

    def held_run(self, session=None):
        session = session or self.session
        with runtime.in_session(session):
            key = runs.new_run(session)
            args = {'kind': 'standard', 'figures': {'period': '2026Q3', 'total_revenue': 120.0},
                    'body': f'Report for {key}.'}
            call = {'id': 'prepared-save', 'name': 'save_report', 'input': copy.deepcopy(args)}
            checkpoints.save(key, {'path': 'agent', 'request_id': REQUEST,
                'operator_text': 'Save the prepared report.', 'pending_calls': [call],
                'conversation': [{'role': 'user', 'content': 'Save the prepared report.'},
                                 {'role': 'assistant', 'content': [{'type': 'tool_use', **call}]}]})
            escalation.signal(key, 'failed_check', 'save the report', 'the operator must resolve the figure',
                              'the corrected figure or an instruction to discard')
            return key

    def test_answer_resumes_the_selected_hold_and_preserves_another_hold(self):
        selected = self.held_run()
        other = self.held_run()
        other_wait = checkpoints.load(other)['waiting_for']
        answer = 'Use the checked figure and retain reference A-17.'
        turns.operator_turn(self.session, '/answer 1 ' + answer)
        self.assertIsNone(escalation.active_hold(selected))
        self.assertIsNotNone(escalation.active_hold(other))
        self.assertEqual(checkpoints.load(other)['waiting_for'], other_wait)
        self.assertEqual(reports.for_request(REQUEST), [])
        self.assertEqual(queue.holds(run_key=selected)[0]['answer'], answer)
        requests = runtime.client(self.session).backend.requests
        instructions = [json.loads(m['content']).get('operator_instruction')
                        for m in requests[-1]['messages']
                        if isinstance(m.get('content'), str) and m['content'].startswith('{')]
        self.assertIn(answer, instructions)
        self.assertEqual(runs.live(self.session), [other])

    def test_answer_is_read_before_any_previously_pending_write(self):
        key = self.held_run()
        answer = 'Discard this report. Do not save or retry it.'
        turns.operator_turn(self.session, '/answer 1 ' + answer)
        self.assertEqual(reports.for_request(REQUEST), [])
        request = runtime.client(self.session).backend.requests[0]
        self.assertIn(answer, json.dumps(request['messages']))
        result = next(block for msg in request['messages'] if isinstance(msg['content'], list)
                      for block in msg['content'] if block.get('type') == 'tool_result')
        self.assertEqual(result['tool_use_id'], 'prepared-save')
        self.assertTrue(result['is_error'])
        self.assertIsNone(checkpoints.load(key).get('pending_operator_answer'))

    def test_corrected_answer_can_produce_a_new_checked_call(self):
        self.held_run()
        model = runtime.client(self.session).backend
        model.responses = [([tool('save_report', {
            'kind': 'standard', 'figures': {'period': '2026Q3', 'total_revenue': 240.0},
            'body': 'Corrected report.'}, 'corrected-save')], 'tool_use', Usage(10, 5))]
        turns.operator_turn(self.session, '/answer 1 Use the corrected revenue 240.0.')
        saved = reports.for_request(REQUEST)
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]['body'], 'Corrected report.')

    def test_answer_precedes_an_unsettled_automatic_question(self):
        key = self.held_run()
        checkpoints.update(key, pending_calls=[], clarification_needed=True,
                           outside_parsed={'columns': ['a', 'b'], 'rows': [[1, 2]]},
                           outside_exchange={'status': 'sending'})
        instruction = 'Do not contact the stranger. Use column a as units and revise the report.'
        turns.operator_turn(self.session, '/answer 1 ' + instruction)
        sent = [m for m in channel.messages('SYN-thread-1001') if m.sender == channel.AGENT]
        self.assertEqual(sent, [])
        requests = runtime.client(self.session).backend.requests
        self.assertEqual(len(requests), 1)
        self.assertIn(instruction, json.dumps(requests[0]['messages']))

    def test_plan_keeps_answer_and_revision_requirement_across_another_crash(self):
        from tests.test_agent_plan import RID, TASK, sample_plan
        from tests.fixtures.agent_loop_fakes import SandboxRegistry
        from tests.support import fixed_run
        with fixed_run(TASK, 'answer-plan', backend=BACKEND):
            key = runs.new_run('answer-plan')
            factory = lambda rid: SandboxRegistry(rid)
            batch = plan._Batch('answer-plan', [RID], 'Handle the request.', factory, bounds.Limits(), None)
            batch.run_key = key
            batch.guard = plan.Guard(sample_plan()['steps'], batch.trace, requests=batch.requests)
            batch.save()
            event = {'kind': 'operator_turn', 'text': 'Discard the remaining report.', 'escalation': 17}
            checkpoints.update(key, pending_operator_answer=event)
            with mock.patch.object(plan._Batch, 'execute', side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    plan.resume_from(checkpoints.load(key), event, registry_factory=factory)
            saved = checkpoints.load(key)
            restored = plan._Batch('answer-plan', [RID], 'Handle the request.', factory, bounds.Limits(), None)
            restored.restore(saved['plan_state'])
            self.assertTrue(restored.revision_feedback)
            self.assertIn(event['text'], json.dumps(restored.messages))
            self.assertIsNone(saved.get('pending_operator_answer'))

    def test_invalid_or_unheld_targets_do_not_start_or_release_work(self):
        held = self.held_run()
        unheld = runs.new_run(self.session)
        checkpoints.save(unheld, {'path': 'agent', 'request_id': REQUEST})
        checkpoints.set_wait(unheld, 'outside', 'other-thread')
        before = runs.live(self.session)
        for command in ('/answer', '/answer 1', '/answer 1   ', '/answer nope Proceed',
                        '/answer 999 Proceed', '/answer 2 Proceed'):
            with self.subTest(command=command):
                reply = turns.operator_turn(self.session, command)
                self.assertIsNotNone(escalation.active_hold(held))
                self.assertEqual(runs.live(self.session), before)
                self.assertEqual(reports.for_request(REQUEST), [])
                self.assertEqual(runtime.client(self.session).calls, 0)
                self.assertTrue(reply.text)

    def test_run_numbers_are_scoped_to_the_console_session(self):
        other = self.held_run('another-console')
        reply = turns.operator_turn(self.session, '/answer 1 Carry on')
        self.assertTrue(reply.text)
        self.assertIsNotNone(escalation.active_hold(other))
        self.assertTrue(runs.first_turn(self.session))
        self.assertEqual(runs.live(self.session), [])
        self.assertEqual(reports.for_request(REQUEST), [])

    def test_only_nonempty_operator_answers_can_lift_a_hold(self):
        with runtime.in_session(self.session):
            for text, who in (('Carry on', 'model'), ('   ', 'operator')):
                with self.subTest(text=text, who=who):
                    key = self.held_run()
                    escalation.answer(key, text, who=who)
                    self.assertIsNotNone(escalation.active_hold(key))
                    self.assertEqual(reports.for_request(REQUEST), [])
            service.on_outside_reply('SYN-thread-1001', '/answer 1 Carry on')
        self.assertIsNotNone(escalation.active_hold(key))
        self.assertEqual(runtime.client(self.session).calls, 0)

    def test_busy_session_keeps_the_next_hold_until_an_explicit_retry(self):
        runtime.configure(backend='tests.test_escalation_console:BlockingAnswerModel')
        first = self.held_run()
        second = self.held_run()
        model = runtime.client(self.session).backend
        errors = []
        def answer_first():
            try:
                turns.operator_turn(self.session, '/answer 1 Proceed with the first report')
            except BaseException as exc:
                errors.append(exc)
        worker = threading.Thread(target=answer_first)
        worker.start()
        try:
            self.assertTrue(model.entered.wait(timeout=2), errors)
            reply = turns.operator_turn(self.session, '/answer 2 Proceed with the second report')
            self.assertIn('retry', reply.text.lower())
            self.assertIsNotNone(escalation.active_hold(second))
            self.assertEqual(queue.holds(run_key=second)[0]['status'], 'held')
            self.assertFalse(checkpoints.load(second).get('resume_requested'))
        finally:
            model.release.set()
            worker.join(timeout=12)
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors, [])
        self.assertIsNone(escalation.active_hold(first))
        turns.operator_turn(self.session, '/answer 2 Proceed with the second report')
        self.assertIsNone(escalation.active_hold(second))
        resumed = [e['run_key'] for e in runtime.trace(self.session).lines() if e['type'] == events.RESUME]
        self.assertEqual(resumed, [first, second])
