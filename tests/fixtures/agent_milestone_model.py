"""Free integration model driven by prompts and tool results, never task expectations.

Its batch plan is a scripted specimen, not evidence of live-model planning quality.
"""

import json
import re
from harness.client import Usage

class MilestoneModel:
    free = True
    def __init__(self, settings=None):
        self.calls = 0

    def create(self, *, system, messages, tools):
        self.calls += 1
        def text(value):
            return [{'type': 'text', 'text': value}], 'end_turn', 'says-done', Usage(100, 50)
        def tool(name, args):
            return [{'type': 'tool_use', 'id': f'audit-{self.calls}', 'name': name, 'input': args}], 'tool_use', 'says-done', Usage(100, 50)
        if 'Classify' in system or 'classify' in system:
            sentence = messages[-1]['content'].lower()
            return text('status_question' if any(word in sentence for word in ('still open', 'what did you', 'what changed', 'which reports')) else 'new_task')
        if system.startswith('You write the short covering email'):
            content = messages[-1]['content']
            figures, _ = json.JSONDecoder().raw_decode(content[content.index('{'):])
            return text(f"Hello, your {figures['period']} revenue was {figures['total_revenue']:,.2f} on {figures['total_units']} units. The sales analytics team")
        if system.startswith('Revise this email'):
            draft = json.loads(messages[-1]['content'])['draft']
            f = draft['figures']
            return text(json.dumps({'recipient': draft['recipient'], 'subject': draft['subject'], 'body': f"Your {f['period']} revenue was {f['total_revenue']:,.2f} on {f['total_units']} units."}))
        if system.startswith('Plan reports'):
            prompt = json.loads(messages[0]['content'])
            steps=[]
            for i, request in enumerate(prompt['requests']):
                prefix=f'r{i}_'
                def step(suffix, name, args, deps, field, checkpoint=False):
                    result={'id': prefix+suffix, 'request_id': request['id'], 'tool': name, 'args': args, 'depends_on': [prefix+d for d in deps], 'expect': {'field': field, 'op': 'exists'}}
                    if checkpoint: result['checkpoint']=True
                    steps.append(result)
                step('parse','parse_file',{},[],'row_count',True)
                step('query','query_sales',{'period': {'$fill': 'request.period'}},['parse'],'total_revenue',True)
                step('chart','render_chart',{'title':'Sales revenue','labels':['Total'], 'values':[{'$fill':prefix+'query.total_revenue'}]},['query'],'path')
                step('save','save_report',{'kind':'batch','figures':{'period':{'$fill':prefix+'query.period'}, 'total_revenue':{'$fill':prefix+'query.total_revenue'}, 'total_units':{'$fill':prefix+'query.total_units'}, 'file_row_count':{'$fill':prefix+'parse.row_count'}, 'chart_id':{'$fill':prefix+'chart.chart_id'}},'body':'Quarterly figures are recorded.'},['query','chart'],'report_id')
                step('email','draft_report_email',{'recipient':{'$fill': 'request.contact_email'},'subject':'Sales report','body':'Report prepared.','report_id':{'$fill':prefix+'save.report_id'}},['save'],'pending_id')
            return text(json.dumps({'steps':steps}))
        if system.startswith('Work on the one request'):
            prompt=json.loads(messages[0]['content'])
            scope=prompt['request_scope']
            calls={}
            outputs={}
            for message in messages[1:]:
                if not isinstance(message['content'],list): continue
                for block in message['content']:
                    if block['type']=='tool_use': calls[block['id']]=block
                    elif block['type']=='tool_result':
                        result=json.loads(block['content'])
                        if not result['ok']: raise AssertionError(result)
                        call=calls[block['tool_use_id']]
                        outputs[(call['name'],call['input'].get('period'))]=result['output']
            def get(name,period=None): return outputs.get((name,period))
            parsed=get('parse_file')
            if parsed is None: return tool('parse_file',{})
            current=get('query_sales',scope['period'])
            if current is None: return tool('query_sales',{'period':scope['period']})
            compare=bool(re.search(r'compare|against|last quarter',prompt['operator_instruction'],re.I))
            period=scope['period']; year=int(period[:4]); quarter=int(period[-1]); previous=f'{year if quarter>1 else year-1}Q{quarter-1 if quarter>1 else 4}'
            before=get('query_sales',previous)
            if compare and before is None: return tool('query_sales',{'period':previous})
            if get('render_chart') is None:
                return tool('render_chart',{'title':period+' revenue', 'labels':[row['name'] for row in current['by_product']], 'values':[row['revenue'] for row in current['by_product']]})
            report=get('save_report')
            if report is None:
                columns=[c.lower() for c in parsed['columns']]
                units_index=next(columns.index(c) for c in ('units_sold','menge','units') if c in columns)
                figures={**current, 'file_total_units':sum(int(row[units_index]) for row in parsed['rows'])}
                if compare: figures['previous_total_revenue']=before['total_revenue']
                body=f"Revenue {current['total_revenue']:,.2f}; file units {figures['file_total_units']}."
                if compare: body+=f" Previous revenue {before['total_revenue']:,.2f}."
                return tool('save_report',{'kind':'comparison' if compare else 'standard','figures':figures,'body':body})
            if get('draft_report_email') is None:
                return tool('draft_report_email',{'recipient':scope['contact_email'],'report_id':report['report_id'],'subject':period+' report','body':f"Your {period} revenue was {current['total_revenue']:,.2f} on {current['total_units']} units."})
            return text('Saved report and prepared its pending email.')
        raise AssertionError('Unknown model prompt: '+system)
