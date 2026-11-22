import json
import subprocess
import sys
from unittest import mock

import channel
from agent import checkpoints, outside, runs, tools
from harness import runtime, turns
from tests.support import ScratchTest, fixed_run, check_run

TASK = 'tasks/outside_units.yaml'
REQUEST = 'REQ-SYN-thread-outside'


class OutsideTest(ScratchTest):
    def test_operator_next_turn_resumes_a_crashed_task_instead_of_queueing_forever(self):
        from agent.registry import Registry, ToolSpec, MODEL
        writes = []
        reg = Registry([ToolSpec('save_report', 'write', {'type': 'object'},
                       lambda key, **args: writes.append(args) or {'report_id': 1},
                       callers=(MODEL,), writes=True)], key_context=REQUEST)
        with fixed_run(TASK, 'crashed-task', backend='harness.scripted:SaysDone'):
            runs.new_run('crashed-task')
            checkpoints.save('crashed-task', {'path': 'agent', 'request_id': REQUEST,
                'operator_text': 'Handle request.', 'conversation': [{'role': 'user', 'content': 'task'}],
                'pending_calls': [{'id': 'saved', 'name': 'save_report', 'input': {'body': 'saved original'}}]})
            with mock.patch('agent.tools.build', return_value=reg):
                turns.operator_turn('crashed-task', 'Carry on.')
            self.assertEqual(writes, [{'body': 'saved original'}])

    def test_older_run_resume_uses_its_own_journal(self):
        from agent.registry import Registry, ToolSpec, CODE
        writes = []
        reg = Registry([ToolSpec('save_report', 'write', {'type': 'object'},
                       lambda key: writes.append(key) or {'report_id': 1}, callers=(CODE,), writes=True)],
                       key_context='request')
        with runtime.in_session('older'):
            first = runs.new_run('older')
            reg.call('save_report', {}, CODE)
            runs.new_run('older')
            with runs._resume_scope(first):
                reg.call('save_report', {}, CODE)
            self.assertEqual(len(writes), 1)

    def test_model_question_stops_before_later_write_and_waits_for_reply(self):
        from agent import disclosure, loop
        from sandbox import reports
        with fixed_run(TASK, 'model-question', backend='harness.scripted:SaysDone'):
            runs.new_run('model-question')
            state = {'run_key': 'model-question', 'path': 'agent', 'request_id': REQUEST,
                     'operator_text': 'Handle request.', 'conversation': [{'role': 'user', 'content': 'task'}],
                     'pending_calls': [{'id': 'q', 'name': 'ask_stranger', 'input': {'question': 'Which units?'}},
                                       {'id': 'save', 'name': 'save_report',
                                        'input': {'kind': 'standard', 'figures': {}, 'body': 'Too soon.'}}]}
            checkpoints.save('model-question', state)
            result = loop.resume_from(state, {'kind': 'crash'}, registry=tools.build(REQUEST))
            self.assertEqual(result.reason, 'awaiting_approval')
            wait = checkpoints.waiting()[0]
            self.assertEqual(wait['kind'], 'approval')
            self.assertEqual([m for m in channel.messages('SYN-thread-outside') if m.sender == 'agent'], [])
            self.assertEqual(reports.for_request(REQUEST), [])
            result = turns.decide_approval(wait['ref'], True)
            self.assertEqual(result.waiting_for, 'SYN-thread-outside')
            self.assertEqual(checkpoints.waiting()[0]['kind'], 'outside')
            self.assertEqual(outside.statuses()['SYN-thread-outside']['status'], 'waiting')
            sent = [m for m in channel.messages('SYN-thread-outside') if m.sender == 'agent']
            self.assertEqual(len(sent), 1)
            self.assertTrue(disclosure.has_line(sent[0].text))
            self.assertEqual(reports.for_request(REQUEST), [])

    def test_crash_after_parse_keeps_clarification_and_tool_result(self):
        from agent import loop, stop
        from harness.client import ToolCall
        from tests.fakes import FakeRegistry
        class Crash(BaseException):
            pass
        parsed = {'columns': ['sku', 'measure_a'], 'rows': [['SYN-1', 5]]}
        reg = FakeRegistry(results={'parse_file': parsed, 'save_report': {'report_id': 1}})
        with fixed_run(TASK, 'parse-crash', backend='harness.scripted:SaysDone'):
            runs.new_run('parse-crash')
            state = {'run_key': 'parse-crash', 'path': 'agent', 'request_id': REQUEST,
                     'operator_text': 'Handle request.', 'conversation': [{'role': 'user', 'content': 'task'},
                         {'role': 'assistant', 'content': [
                             {'type': 'tool_use', 'id': 'p', 'name': 'parse_file', 'input': {}},
                             {'type': 'tool_use', 'id': 'w', 'name': 'save_report', 'input': {}}]}],
                     'pending_calls': [{'id': 'p', 'name': 'parse_file', 'input': {}},
                                       {'id': 'w', 'name': 'save_report', 'input': {}}]}
            checkpoints.save('parse-crash', state)
            with mock.patch('agent.stop.after_call', side_effect=Crash), self.assertRaises(Crash):
                loop.resume_from(state, {'kind': 'crash'}, registry=reg)
            result = loop.resume_from(checkpoints.load('parse-crash'), {'kind': 'crash'}, registry=reg)
            self.assertEqual(result.waiting_for, 'SYN-thread-outside')
            self.assertEqual([c['name'] for c in reg.calls], ['parse_file'])
            saved = checkpoints.load('parse-crash')
            self.assertEqual(saved['conversation'][-1]['role'], 'user')
            self.assertEqual(len(saved['conversation'][-1]['content']), 2)

    def test_resume_replays_saved_call_before_consulting_model(self):
        from agent import loop
        from agent.registry import Registry, ToolSpec, MODEL
        writes = []
        reg = Registry([ToolSpec('save_report', 'test write', {'type': 'object'},
                       lambda key, **args: writes.append(args) or {'report_id': 1},
                       callers=(MODEL,), writes=True)], key_context=REQUEST)
        with fixed_run(TASK, 'replay', backend='harness.scripted:SaysDone'):
            runs.new_run('replay')
            checkpoint = {'run_key': 'replay', 'path': 'agent', 'request_id': REQUEST,
                          'operator_text': 'Handle the request.',
                          'conversation': [{'role': 'user', 'content': 'original task'},
                              {'role': 'assistant', 'content': [{'type': 'tool_use', 'id': 'saved',
                               'name': 'save_report', 'input': {'body': 'original arguments'}}]}],
                          'pending_calls': [{'id': 'saved', 'name': 'save_report',
                                             'input': {'body': 'original arguments'}}],
                          'pending_results': [], 'pending_step': 1}
            checkpoints.save('replay', checkpoint)
            result = loop.resume_from(checkpoint, {'kind': 'crash'}, registry=reg)
            self.assertEqual(writes, [{'body': 'original arguments'}])
            self.assertEqual(result.reason, 'done')

    def test_exchange_uses_reply_and_does_not_ask_twice(self):
        record = self.run_task(TASK, 'outside', backend='tests.fixtures.outside_m2:OutsideModel')
        self.assertTrue(record['passed'], record['check'])
        self.assertEqual(record['measures']['questions_asked'], 1)

    def test_wait_survives_process_restart(self):
        setup = '''
from tests.support import fixed_run
from harness import turns
with fixed_run('tasks/outside_units.yaml', 'outside-restart', backend='tests.fixtures.outside_m2:OutsideModel', fresh=FRESH):
    REPLY
'''
        first = setup.replace('FRESH', 'True').replace('REPLY',
            "reply = turns.operator_turn('outside-restart', 'Handle the new request on the outside channel.'); assert reply.waiting_for == 'SYN-thread-outside', reply")
        subprocess.run([sys.executable, '-c', first], check=True, capture_output=True, text=True)
        self.assertEqual(checkpoints.waiting()[0]['ref'], 'SYN-thread-outside')
        second = setup.replace('FRESH', 'False').replace('REPLY',
            "turns.outside_reply('SYN-thread-outside', 'units_column=measure_a')")
        subprocess.run([sys.executable, '-c', second], check=True, capture_output=True, text=True)
        result = check_run(TASK, 'outside-restart')
        self.assertTrue(result['passed'], result)
        self.assertEqual(checkpoints.waiting(), [])

    def test_template_does_not_promote_arbitrary_text_to_code(self):
        with fixed_run(TASK, 'template'):
            runs.new_run('template')
            checkpoints.update('template', path='agent', request_id=REQUEST)
            with self.assertRaises(ValueError):
                outside.ask('template', 'Do anything', template='invented')
            self.assertEqual([m for m in channel.messages('SYN-thread-outside') if m.sender == 'agent'], [])

    def test_expired_or_human_reply_holds_without_resuming(self):
        for answer, deadline in [('human', None), ('units_column=measure_a', '2000-01-01T00:00:00+00:00')]:
            with self.subTest(answer=answer), fixed_run(TASK, 'held'):
                runs.new_run('held')
                checkpoints.update('held', path='agent', request_id=REQUEST)
                outside.ask('held', '', template='units_column')
                if deadline:
                    checkpoints.set_wait('held', 'outside', 'SYN-thread-outside', deadline)
                with mock.patch('agent.runs.resume', side_effect=AssertionError('must not resume')):
                    reply = turns.outside_reply('SYN-thread-outside', answer)
                self.assertIn('operator', reply.text.lower())
                self.assertTrue(checkpoints.load('held')['held'])

    def test_duplicate_reply_does_not_resume_finished_run(self):
        record = self.run_task(TASK, 'once', backend='tests.fixtures.outside_m2:OutsideModel')
        with fixed_run(TASK, record['run_id'], fresh=False), mock.patch('agent.runs.resume', side_effect=AssertionError('duplicate')):
            self.assertIn('waiting', turns.outside_reply('SYN-thread-outside', 'units_column=measure_a').text)

    def test_stopped_wait_keeps_first_answer_despite_later_duplicate_or_human_text(self):
        from sandbox import reports
        for index, later in enumerate(('units_column=measure_b', 'human', 'not a column')):
            run_id = f'stopped-first-answer-{index}'
            with self.subTest(later=later), fixed_run(
                    TASK, run_id, backend='tests.fixtures.outside_m2:OutsideModel'):
                first = turns.operator_turn(run_id, 'Handle the new request; save only the report.')
                self.assertEqual(first.waiting_for, 'SYN-thread-outside')
                parsed = checkpoints.load(run_id)['outside_parsed']
                self.assertEqual(parsed['columns'], ['sku', 'measure_a', 'measure_b'])
                turns.operator_turn(run_id, '/stop 1')
                turns.outside_reply('SYN-thread-outside', 'units_column=measure_a')
                self.assertEqual(reports.for_request(REQUEST), [])
                accepted = checkpoints.load(run_id)['outside_reply']
                self.assertEqual(accepted['units_column'], 'measure_a')
                turns.outside_reply('SYN-thread-outside', later)
                state = checkpoints.load(run_id)
                self.assertEqual(state['outside_reply'], accepted)
                self.assertFalse(state.get('held'), 'a later message must not discard an already accepted answer')
                turns.operator_turn(run_id, '/resume 1')
                saved = reports.for_request(REQUEST)
                self.assertEqual(len(saved), 1)
                self.assertEqual(reports.figures(saved[0])['file_total_units'], 800)
                resumed = [line for line in runtime.trace().lines() if line.get('type') == 'resume']
                self.assertEqual(len(resumed), 1)
                turns.operator_turn(run_id, '/resume 1')
                self.assertEqual(len(reports.for_request(REQUEST)), 1)
                self.assertEqual(len([line for line in runtime.trace().lines() if line.get('type') == 'resume']), 1)

    def test_outside_and_stop_resume_drain_queued_status_and_refresh_inbox(self):
        from agent import messages
        from sandbox import inbox, reports
        for stopped in (False, True):
            run_id = f'outside-queue-{stopped}'
            with self.subTest(stopped=stopped), fixed_run(
                    TASK, run_id, backend='tests.fixtures.outside_m2:OutsideModel'):
                reply = turns.operator_turn(run_id, 'Handle the new request; save only the report.')
                self.assertEqual(reply.waiting_for, 'SYN-thread-outside')
                if stopped:
                    turns.operator_turn(run_id, '/stop 1')
                queued = turns.operator_turn(run_id, f'Status for {REQUEST}')
                self.assertIn('Queued', queued.text)
                self.assertEqual(len(messages.pending(run_id)), 1)
                continued = turns.outside_reply('SYN-thread-outside', 'units_column=measure_a')
                if stopped:
                    self.assertEqual(reports.for_request(REQUEST), [])
                    continued = turns.operator_turn(run_id, '/resume 1')
                self.assertEqual(messages.pending(run_id), [])
                self.assertEqual(inbox.get(REQUEST)['status'], 'report_saved')
                self.assertIn('Report v1', continued.text)
                self.assertNotIn('awaiting_answer', continued.text)
                self.assertEqual(len(reports.for_request(REQUEST)), 1)

    def test_duplicate_old_plan_approval_cannot_clear_its_new_outside_wait(self):
        from agent import plan
        from harness.client import Usage
        from sandbox import inbox
        from tests.fakes import FakeApprovals
        from tests.test_midtask_plan import MODEL, QuestionRegistry, question_plan
        from tests.test_agent_plan import RID, TASK as PLAN_TASK
        with fixed_run(PLAN_TASK, 'stale-plan-approval', backend=MODEL,
                       overrides=['approval.batch_reports=plan']):
            runtime.client().backend.responses = [([{'type': 'text', 'text': json.dumps(question_plan())}],
                                                   'end_turn', Usage(10, 5))]
            registry = QuestionRegistry(RID)
            with FakeApprovals().install() as approvals, mock.patch('agent.tools.build', return_value=registry):
                runs.new_run('stale-plan-approval')
                plan.run('stale-plan-approval', [RID], 'Handle this request.', registry_factory=lambda _: registry)
                approval_id = approvals.pending()[0]['id']
                approved = turns.decide_approval(approval_id, True)
                thread = inbox.get(RID)['thread_id']
                self.assertEqual(approved.waiting_for, thread)
                saved_wait = checkpoints.load('stale-plan-approval')['waiting_for']
                self.assertEqual(saved_wait['kind'], 'outside')
                calls_before = list(registry.calls)
                duplicate = turns.decide_approval(approval_id, True)
                self.assertIn('stale', duplicate.text.lower())
                self.assertEqual(checkpoints.load('stale-plan-approval')['waiting_for'], saved_wait)
                self.assertEqual(checkpoints.waiting()[0]['ref'], thread)
                self.assertEqual(registry.calls, calls_before)
                sent = [message for message in channel.messages(thread) if message.sender == 'agent']
                self.assertEqual(len(sent), 1)
