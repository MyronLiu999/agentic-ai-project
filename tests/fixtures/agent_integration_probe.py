"""Manual T2 probes for a snapshot containing the published team implementations.

Run with `python -m unittest tests.fixtures.agent_integration_probe` after assembling
the snapshot described in docs/abraham-handoff.md. Not part of routine discovery:
the Abraham-only checkout still has stubs. All model responses are scripted/free.
Contract assertions intentionally fail until the published tools match PLAN.md.
"""

import json
from agent import bounds, loop, plan, tools
from harness import runtime, turns
from harness.client import Usage
from sandbox import inbox, pending, reports, sales
from tests.support import ScratchTest, fixed_run
from tests.fixtures.agent_loop_fakes import SandboxRegistry, tool
from tests.test_agent_plan import RID, TASK, sample_plan

MODEL = 'tests.fixtures.agent_loop_fakes:SequenceModel'

class IntegrationProbe(ScratchTest):
    def test_published_named_status_task_passes_without_writes(self):
        record = self.run_task("tasks/status_question_done_work.yaml", "named-status-task",
                               backend="tests.fixtures.agent_intent_models:StatusIntent")
        self.assertTrue(record["passed"], record["check"]["reason"])
        self.assertEqual(record["measures"]["writes"], 0)

    def test_named_status_follow_up_keeps_scope_after_restart(self):
        task = "tasks/status_question_done_work.yaml"
        with fixed_run(task, "named-status-follow-up"):
            inbox.add("SYN-unrelated", "SYN-DIST-002", "other@example.test", "Other request", period="2026Q3")
            before = pending.all_pending()
            first = turns.operator_turn("operator", "Status for SYN Acme Trading in Q3.")
            self.assertIn("51,264.85", first.text)
        with fixed_run(task, "named-status-follow-up", fresh=False):
            follow_up = turns.operator_turn("operator", "What did you do?")
            self.assertIn("51,264.85", follow_up.text)
            self.assertNotIn("REQ-SYN-unrelated", follow_up.text)
            self.assertEqual(pending.all_pending(), before)

    def script(self, content, stop='tool_use'):
        runtime.client().backend.responses = [(content, stop, Usage(10, 5))]

    def draft(self):
        request = inbox.get(RID)
        figures = sales.distributor_sales(request['distributor_id'], request['period'])
        saved, _ = reports.save(RID, 'standard', figures, 'Report', 'probe-report')
        return {'recipient': request['contact_email'], 'subject': 'Report',
                'body': f"Revenue {figures['total_revenue']:,.2f}", 'report_id': saved['id']}

    def test_real_critique_allows_correct_loop_email(self):
        with fixed_run(TASK, 'real-critique-pass', backend=MODEL):
            self.script([tool('draft_report_email', self.draft())])
            result = loop.run('operator', RID, 'Handle the request', registry=SandboxRegistry(RID))
            self.assertEqual(result.reason, 'done')
            self.assertEqual(len(pending.all_pending()), 1)
            self.assertIn('pass', [e['verdict'] for e in runtime.trace().lines() if e['type']=='critique'])

    def test_real_critique_preserves_loop_step_limit(self):
        with fixed_run(TASK, 'real-critique-limit', backend=MODEL):
            draft = self.draft()
            draft['recipient'] = 'wrong@example.test'
            self.script([tool('draft_report_email', draft)])
            result = loop.run('operator', RID, 'Handle the request', registry=SandboxRegistry(RID),
                              limits=bounds.Limits(max_steps=1))
            self.assertEqual(result.reason, 'step_limit')
            self.assertEqual(pending.all_pending(), [])

    def test_real_critique_allows_correct_planned_email(self):
        with fixed_run(TASK, 'real-plan-pass', backend=MODEL):
            raw = sample_plan()
            request = inbox.get(RID)
            total = sales.distributor_sales(request['distributor_id'], request['period'])['total_revenue']
            raw['steps'][-1]['args']['body'] = f'Revenue {total:,.2f}'
            self.script([{'type':'text', 'text':json.dumps(raw)}], 'end_turn')
            plan.run('operator', [RID], 'Handle the request', registry_factory=SandboxRegistry)
            self.assertEqual(len(pending.all_pending()), 1)
            self.assertEqual(len(reports.for_request(RID)), 1)
            self.assertEqual([e['terminal_reason'] for e in runtime.trace().lines() if e['type']=='end'][-1], 'done')

    def test_real_critique_preserves_planner_step_limit(self):
        with fixed_run(TASK, 'real-plan-limit', backend=MODEL):
            raw = sample_plan()
            raw['steps'][-1]['args']['recipient'] = 'wrong@example.test'
            self.script([{'type':'text', 'text':json.dumps(raw)}], 'end_turn')
            plan.run('operator', [RID], 'Handle the request', registry_factory=SandboxRegistry,
                     limits=bounds.Limits(max_steps=1))
            self.assertEqual([e['terminal_reason'] for e in runtime.trace().lines() if e['type']=='end'][-1], 'step_limit')
            self.assertEqual(pending.all_pending(), [])

    def test_published_tools_accept_agreed_contract(self):
        with fixed_run(TASK, 'tool-contracts', backend=MODEL):
            draft = self.draft()
            registry = tools.build(RID)
            cases = [('parse_file', {'delimiter':';', 'decimal':','}),
                     ('query_sales', {'period':'2026Q3'}),
                     ('render_chart', {'title':'Sales', 'labels':['A'], 'values':[10]}),
                     ('save_report', {'kind':'standard', 'figures':{'period':'2026Q3','total_revenue':10},'body':'Report'}),
                     ('draft_report_email', draft),
                     ('draft_clarifying_question', {'question':'Which period?'})]
            for name, args in cases:
                with self.subTest(tool=name):
                    result = registry.call(name, args, 'model', step=name)
                    self.assertTrue(result['ok'], result['error'])

    def test_published_parser_returns_positional_rows(self):
        with fixed_run(TASK, 'parse-shape', backend=MODEL):
            result = tools.build(RID).call('parse_file', {}, 'model', step='parse')
            self.assertTrue(result['ok'], result['error'])
            self.assertIsInstance(result['output']['rows'][0], list)

    def test_published_workflow_status_scopes_explicit_ids(self):
        with fixed_run(TASK, 'status-scope', backend=MODEL):
            other = inbox.add('SYN-other', 'SYN-DIST-001', 'other@example.test', 'Other')
            reply = turns.operator_turn('operator', f'Check status of {RID}.')
            self.assertIn(RID, reply.text)
            self.assertNotIn(other, reply.text)

    def test_distinct_chart_steps_have_distinct_registry_write_keys(self):
        from agent.registry import Registry, ToolSpec
        from harness.paths import state_dir
        with fixed_run(TASK, 'chart-identities', backend=MODEL, overrides=['critique.report_email=off']):
            raw = sample_plan()
            charts = [{'id': sid, 'request_id': RID, 'tool':'render_chart',
                       'args': {'title': sid, 'labels':['A'], 'values':[value]},
                       'depends_on':['query'], 'expect':{'field':'path','op':'exists'}}
                      for sid, value in [('chart_a', 10), ('chart_b', 20)]]
            raw['steps'][1]['depends_on'] += ['chart_a', 'chart_b']
            raw["steps"][1]["args"]["figures"] = {
                "period": {"$fill": "query.period"}, "total_revenue": {"$fill": "query.total_revenue"},
                "charts": [{"$fill": "chart_a.path"}, {"$fill": "chart_b.path"}]}
            raw['steps'][1:1] = charts
            self.script([{'type':'text', 'text':json.dumps(raw)}], 'end_turn')
            def factory(rid):
                fake = SandboxRegistry(rid)
                def chart(title, labels, values, key):
                    path = state_dir() / f'{key}.svg'
                    if not path.exists():
                        path.write_text(json.dumps(values))
                    return {'chart_id':key, 'path':str(path)}
                def wrap(fn):
                    def call(**args):
                        args.pop('key', None)
                        return fn(**args)
                    return call
                handlers = {name: wrap(fn) for name, fn in fake.handlers.items()}
                handlers['render_chart'] = chart
                return Registry([ToolSpec(name, name, {'type':'object'}, fn,
                                          writes=name not in ('parse_file','query_sales'))
                                 for name, fn in handlers.items()], key_context=rid)
            plan.run('operator', [RID], 'Handle the request', registry_factory=factory)
            artifacts = list(state_dir().glob('*.svg'))
            self.assertEqual(len(artifacts), 2)
            self.assertEqual({p.read_text() for p in artifacts}, {'[10]', '[20]'})
