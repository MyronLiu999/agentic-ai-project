"""Free outside-exchange model; all tools use the production MCP registry."""
import json
import re

from harness.client import Usage
from tests.fixtures.agent_milestone_model import MilestoneModel


class OutsideModel(MilestoneModel):
    def create(self, *, system, messages, tools):
        # The test model derives the units header only from the labelled reply.
        messages = json.loads(json.dumps(messages))
        column = None
        for message in messages:
            content = message.get('content')
            if isinstance(content, str) and 'outside_reply_from_stranger' in content:
                match = re.search(r'units_column=([a-z_]+)', content)
                if match:
                    column = match[1]
        if column:
            for message in messages:
                if not isinstance(message.get('content'), list):
                    continue
                for block in message['content']:
                    if block.get('type') != 'tool_result':
                        continue
                    result = json.loads(block['content'])
                    output = result.get('output')
                    if isinstance(output, dict) and column in output.get('columns', []):
                        output['columns'][output['columns'].index(column)] = 'units_sold'
                        block['content'] = json.dumps(result)
        result = super().create(system=system, messages=messages, tools=tools)
        if column and result[0][0].get('name') == 'draft_report_email':
            return [{'type': 'text', 'text': 'Saved the requested report.'}], 'end_turn', 'outside-test', Usage(100, 10)
        return result
