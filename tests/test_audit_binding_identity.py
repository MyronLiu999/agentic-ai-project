"""Regressions for trusted batch contacts and reactive chart effect identity."""

import json

from agent.registry import MODEL
from agent.tools import build
from harness import runtime, tasks, turns, ROOT
from sandbox import charts, inbox, pending, seed
from tests.fixtures.agent_milestone_model import MilestoneModel
from tests.support import ScratchTest, fixed_run


class LiteralRecipientModel(MilestoneModel):
    def create(self, *, system, messages, tools):
        content, stop, end, usage = super().create(system=system, messages=messages, tools=tools)
        if system.startswith('Plan reports'):
            proposal = json.loads(content[0]['text'])
            for step in proposal['steps']:
                if step['tool'] == 'draft_report_email':
                    step['args']['recipient'] = 'recipient@example.com'
            content[0]['text'] = json.dumps(proposal)
        elif system.startswith('Revise this email'):
            draft = json.loads(content[0]['text'])
            draft['recipient'] = 'still-wrong@example.com'
            content[0]['text'] = json.dumps(draft)
        return content, stop, end, usage


class MissingComparisonModel(MilestoneModel):
    def create(self, **kwargs):
        content, stop, end, usage = super().create(**kwargs)
        for block in content:
            if block.get('name') == 'save_report':
                args = block['input']
                args['kind'] = 'standard'
                args['figures'].pop('previous_total_revenue', None)
                args['body'] = 'Current quarter report.'
        return content, stop, end, usage


class ComparisonScopeTest(ScratchTest):
    def test_operator_comparison_requires_previous_figures_even_for_generic_request(self):
        from sandbox import db
        task = 'tasks/compare_check_last_quarter.yaml'
        with fixed_run(task, 'comparison-scope', backend=__name__ + ':MissingComparisonModel'):
            with db.connect() as conn:
                conn.execute("UPDATE requests SET question = 'Please prepare my report.'")
            turns.operator_turn(runtime.current_run().run_id, tasks.read(ROOT / task)['operator'][0])
            self.assertEqual(pending.all_pending(), [])
            ends = [e for e in runtime.trace().lines() if e['type'] == 'end']
            self.assertEqual(ends[-1]['terminal_reason'], 'critique_held')
            reasons = [e['reason'] for e in runtime.trace().lines() if e['type'] == 'critique']
            self.assertTrue(any('previous_total_revenue' in reason for reason in reasons))


class BatchContactBindingTest(ScratchTest):
    def test_literal_recipients_use_each_requests_trusted_contact(self):
        task = 'tasks/batch_reports_two.yaml'
        with fixed_run(task, 'trusted-batch-contact', backend=__name__ + ':LiteralRecipientModel'):
            turns.operator_turn(runtime.current_run().run_id, tasks.read(ROOT / task)['operator'][0])
            rows = pending.all_pending()
            self.assertEqual(len(rows), 2)
            for row in rows:
                self.assertEqual(row['recipient'], inbox.get(row['request_id'])['contact_email'])
            accepted = [e for e in runtime.trace().lines() if e['type'] == 'plan' and e.get('accepted')]
            first_emails = [s for s in accepted[0]['plan']['steps'] if s['tool'] == 'draft_report_email']
            self.assertTrue(first_emails)
            self.assertTrue(all(s['args']['recipient'] == {'$fill': 'request.contact_email'} for s in first_emails))
            self.assertEqual([e for e in runtime.trace().lines() if e['type'] == 'end'][-1]['terminal_reason'], 'done')


class ReactiveChartIdentityTest(ScratchTest):
    def setUp(self):
        super().setUp()
        seed.reset()
        seed.seed(None)
        self.rid = inbox.request_id('SYN-thread-2001')

    def chart(self, title, values, labels=None):
        result = build(self.rid).call('render_chart', {
            'title': title, 'labels': labels or ['Widget'], 'values': values}, MODEL)
        self.assertTrue(result['ok'], result)
        return result['output']

    def test_reworded_title_and_equivalent_number_reuse_chart(self):
        first = self.chart('Quarter revenue', [10])
        second = self.chart('Revenue for the quarter', [10.0])
        self.assertEqual(first['chart_id'], second['chart_id'])
        self.assertFalse(second['created'])
        self.assertEqual(len(charts.for_request(self.rid)), 1)

    def test_changed_data_with_same_title_creates_the_requested_chart(self):
        first = self.chart('Quarter revenue', [10])
        second = self.chart('Quarter revenue', [20])
        self.assertNotEqual(first['chart_id'], second['chart_id'])
        self.assertEqual(json.loads(charts.get(second['chart_id'])['values_json']), [20.0])

    def test_changed_category_with_same_title_and_value_is_distinct(self):
        first = self.chart('Quarter revenue', [10], ['Widget'])
        second = self.chart('Quarter revenue', [10], ['Gadget'])
        self.assertNotEqual(first['chart_id'], second['chart_id'])
