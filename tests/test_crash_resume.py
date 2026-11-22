"""Operator crash recovery preserves other runs, queued work, and keyed effects."""
import copy
import threading

import channel
from agent import checkpoints, events, messages, runs, tools
from agent.registry import MODEL
from harness import ROOT, runtime, tasks, turns
from harness.scripted import SaysDone
from policy import flags
from sandbox import reports, seed
from tests.support import ScratchTest


REQUEST = 'REQ-SYN-thread-1001'
STATUS = f'Status for {REQUEST}.'
ARGS = {'kind': 'standard', 'figures': {'period': '2026Q3', 'total_revenue': 120.0},
        'body': 'The report prepared before interruption.'}


class BlockingDone(SaysDone):
    def __init__(self, settings=None):
        super().__init__(settings)
        self.entered = threading.Event()
        self.release = threading.Event()

    def create(self, **kwargs):
        self.entered.set()
        if not self.release.wait(timeout=10):
            raise AssertionError('The recovery model was not released')
        return super().create(**kwargs)


class CrashResumeTest(ScratchTest):
    def setUp(self):
        super().setUp()
        runtime.configure(backend='harness.scripted:SaysDone')
        channel.reset()
        seed.reset()
        with channel.seeding():
            seed.seed(tasks.load(ROOT / 'tasks/standard_report_clean.yaml'))
        self.session = 'crash-routing'

    def make_crashed_run(self, *, completed=False):
        with runtime.in_session(self.session):
            key = runs.new_run(self.session)
            call = {'id': 'prepared-save', 'name': 'save_report', 'input': copy.deepcopy(ARGS)}
            checkpoints.save(key, {'path': 'agent', 'request_id': REQUEST,
                'operator_text': 'Save the prepared report.', 'pending_calls': [call],
                'conversation': [{'role': 'user', 'content': 'Save the prepared report.'},
                                 {'role': 'assistant', 'content': [{'type': 'tool_use', **call}]}]})
            if completed:
                result = tools.build(REQUEST).call('save_report', ARGS, MODEL)
                self.assertTrue(result['ok'], result)
            return key

    def make_waiting_run(self):
        key = runs.new_run(self.session)
        checkpoints.save(key, {'path': 'agent', 'request_id': REQUEST})
        checkpoints.set_wait(key, 'outside', 'SYN-thread-unrelated', '2999-01-01T00:00:00+00:00')
        return key

    def resumes(self):
        return [e for e in runtime.trace(self.session).lines() if e['type'] == events.RESUME]

    def test_single_crash_replays_once_then_runs_the_incoming_status_question(self):
        key = self.make_crashed_run()
        reply = turns.operator_turn(self.session, STATUS)
        self.assertEqual([(e['run_key'], e['event_kind']) for e in self.resumes()], [(key, 'crash')])
        saved = reports.for_request(REQUEST)
        self.assertEqual([r['body'] for r in saved], [ARGS['body']])
        self.assertIn(REQUEST, reply.text)
        self.assertEqual(messages.pending(self.session), [])
        self.assertEqual(runs.live(self.session), [])

    def test_crash_beside_wait_reuses_completed_effect_and_preserves_incoming_work(self):
        key = self.make_crashed_run(completed=True)
        waiting = self.make_waiting_run()
        original_wait = checkpoints.load(waiting)['waiting_for']
        turns.operator_turn(self.session, STATUS)
        self.assertEqual([(e['run_key'], e['event_kind']) for e in self.resumes()], [(key, 'crash')])
        self.assertEqual(len(reports.for_request(REQUEST)), 1)
        replay = [e for e in runtime.trace(self.session).lines()
                  if e.get('type') == events.JOURNAL_HIT and e.get('tool') == 'save_report']
        self.assertEqual([e['run_key'] for e in replay], [key])
        self.assertEqual(checkpoints.load(waiting)['waiting_for'], original_wait)
        self.assertEqual(runs.live(self.session), [waiting])
        self.assertEqual([(m['way'], m['text']) for m in messages.pending(self.session)], [('queue', STATUS)])

    def test_active_recovery_queues_new_work_without_resuming_it_twice(self):
        runtime.configure(backend='tests.test_crash_resume:BlockingDone')
        key = self.make_crashed_run()
        waiting = self.make_waiting_run()
        model = runtime.client(self.session).backend
        errors = []
        def recover():
            try:
                turns.operator_turn(self.session, STATUS)
            except BaseException as exc:
                errors.append(exc)
        worker = threading.Thread(target=recover)
        worker.start()
        try:
            self.assertTrue(model.entered.wait(timeout=10), errors)
            turns.operator_turn(self.session, 'Show the saved report later.')
            self.assertEqual(len(self.resumes()), 1)
        finally:
            model.release.set()
            worker.join(timeout=12)
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual([e['run_key'] for e in self.resumes()], [key])
        self.assertEqual(len(reports.for_request(REQUEST)), 1)
        self.assertEqual(runs.live(self.session), [waiting])
        self.assertEqual([m['text'] for m in messages.pending(self.session)],
                         [STATUS, 'Show the saved report later.'])
        self.assertFalse(checkpoints.load(key).get('resume_requested'))

    def test_stop_flag_and_stopped_or_cancelled_checkpoint_prevent_automatic_resume(self):
        for guard in ('flag', 'stopped', 'cancelled'):
            with self.subTest(guard=guard):
                self.session = 'crash-routing-' + guard
                key = self.make_crashed_run()
                waiting = self.make_waiting_run()
                if guard == 'flag':
                    flags.stop_run(key)
                else:
                    checkpoints.update(key, **{guard: True})
                turns.operator_turn(self.session, STATUS)
                self.assertEqual(self.resumes(), [])
                self.assertEqual(reports.for_request(REQUEST), [])
                self.assertEqual(runs.live(self.session), [key, waiting])
                self.assertEqual([m['text'] for m in messages.pending(self.session)], [STATUS])

    def test_explicit_addition_is_consumed_by_recovery_without_becoming_a_new_task(self):
        key = self.make_crashed_run()
        self.make_waiting_run()
        turns.operator_turn(self.session, '/add 1 Preserve the audit reference.')
        turns.operator_turn(self.session, STATUS)
        self.assertEqual(checkpoints.load(key)['operator_additions'], ['Preserve the audit reference.'])
        self.assertEqual([(m['way'], m['text']) for m in messages.pending(self.session)], [('queue', STATUS)])
        self.assertEqual(len(reports.for_request(REQUEST)), 1)
