"""Free long-session model; reads its prompt and real tool results, never expectations."""
import json
import re
from harness.client import Usage


class LongSessionModel:
    free = True

    def __init__(self, settings=None):
        self.calls = 0

    def create(self, *, system, messages, tools):
        self.calls += 1
        usage = Usage(input_tokens=(len(system) + len(json.dumps(messages)) + len(json.dumps(tools))) // 4,
                      output_tokens=100)
        def reply(text):
            return [{'type':'text','text':text}], 'end_turn', 'says-done', usage
        def call(name, args):
            return [{'type':'tool_use','id':f'long-{self.calls}','name':name,'input':args}], 'tool_use', 'says-done', usage
        if 'Classify the operator' in system:
            return reply('status_question' if 'What revenue' in messages[-1]['content'] else 'new_task')
        if not system.startswith('Work on the one request'):
            raise AssertionError('Unexpected long-session prompt: ' + system[:100])
        prompt = json.loads(messages[0]['content'])
        scope = prompt['request_scope']
        seen = {}
        outputs = {}
        for message in messages:
            if not isinstance(message['content'], list):
                continue
            for block in message['content']:
                if block['type'] == 'tool_use':
                    seen[block['id']] = block
                if block['type'] == 'tool_result':
                    result = json.loads(block['content'])
                    if not result.get('ok'):
                        raise AssertionError(result)
                    operation = seen[block['tool_use_id']]
                    outputs[(operation['name'], operation['input'].get('period'))] = result['output']
        current = outputs.get(('query_sales', scope['period']))
        if current is None:
            return call('query_sales', {'period':scope['period']})
        previous = outputs.get(('query_sales','2026Q2'))
        if previous is None:
            return call('query_sales', {'period':'2026Q2'})
        saved = outputs.get(('save_report', None))
        marker = re.search(r'SYN-CAMPAIGN-[A-Z]+', system + json.dumps(messages[0]))
        code = marker[0] if marker else 'UNRESOLVED'
        if saved is None:
            return call('save_report', {'kind':'comparison', 'figures':{
                'period':scope['period'], 'total_revenue':current['total_revenue'],
                'total_units':current['total_units'], 'previous_period':'2026Q2',
                'previous_total_revenue':previous['total_revenue'],
                'revenue_change':current['total_revenue'] - previous['total_revenue'],
                'campaign_code':code},
                'body':f"Campaign {code}. {scope['period']} revenue {current['total_revenue']:.2f}; "
                       f"2026Q2 revenue {previous['total_revenue']:.2f}."})
        if ('draft_report_email', None) not in outputs:
            return call('draft_report_email', {'recipient':scope['contact_email'], 'report_id':saved['report_id'],
                'subject':scope['period']+' sales report',
                'body':f"Your {scope['period']} revenue was {current['total_revenue']:.2f} on {current['total_units']} units. "
                       f"2026Q2 revenue was {previous['total_revenue']:.2f}."})
        return reply('Report and email draft saved.')
