"""Contract stand-in for Myron's not-yet-merged send tool, with real channel effects."""
import json
import re
from unittest import mock

import channel
from agent import tools
from agent.registry import Registry, ToolSpec, CODE, MODEL
from harness.client import Usage
from policy.hook import registry_hook
from sandbox import inbox
from tests.fixtures.agent_milestone_model import MilestoneModel

_build = tools.build


def build(request_id):
    registry = _build(request_id)
    def send(question, key):
        request = inbox.get(request_id)
        prior = next((m for m in channel.messages(request['thread_id'])
                      if m.sender == 'agent' and m.text == question), None)
        message = prior or channel.send(request['thread_id'], question)
        return {'thread_id': request['thread_id'], 'message_id': message.id, 'created': prior is None}
    spec = ToolSpec('ask_stranger', 'Ask one factual question.',
                    {'type': 'object', 'properties': {'question': {'type': 'string'}},
                     'required': ['question'], 'additionalProperties': False}, send,
                    callers=(CODE, MODEL), writes=True)
    return Registry(list(registry._ordered) + [spec], key_context=request_id,
                    pre_call_hook=registry_hook(request_id))


def install():
    return mock.patch('agent.tools.build', build)


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
