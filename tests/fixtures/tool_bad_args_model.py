"""Free Part 3 probe: malformed calls through the real operator/agent path."""

import copy
import json

from harness.client import Usage


BAD_CALLS = [
    ("parse_file", {"delimiter": "??"}),
    ("query_sales", {"period": "third quarter"}),
    ("render_chart", {"title": "Bad series", "labels": ["Widget"], "values": ["not a number"]}),
    ("save_report", {"kind": "standard", "figures": {}, "body": "Invalid synthetic report."}),
    ("draft_report_email", {"subject": "Missing recipient and report"}),
    ("draft_clarifying_question", {"question": 42}),
]
ACKNOWLEDGEMENT = "BadArgs verified 6 error results; no successful action claimed."


class BadArgs:
    free = True
    name = "bad-args-probe"

    def __init__(self, settings=None):
        self.calls = 0

    def create(self, *, system, messages, tools):
        self.calls += 1
        if self.calls == 1:
            offered = {tool["name"] for tool in tools or []}
            expected = {name for name, _ in BAD_CALLS}
            if not expected <= offered:
                raise AssertionError("The real agent must offer all six tools to this probe.")
            blocks = [{"type": "tool_use", "id": f"badargs-{name}", "name": name,
                       "input": copy.deepcopy(args)} for name, args in BAD_CALLS]
            return blocks, "tool_use", self.name, Usage(100, 100)

        if self.calls != 2:
            raise AssertionError("The probe must finish after observing the six errors.")
        feedback = messages[-1].get("content")
        if not isinstance(feedback, list) or len(feedback) != len(BAD_CALLS):
            raise AssertionError("The agent did not return all six tool results to the model.")
        for block, (name, _) in zip(feedback, BAD_CALLS):
            result = json.loads(block["content"])
            if (block.get("tool_use_id") != f"badargs-{name}" or not block.get("is_error")
                    or result.get("ok") is not False or not result.get("is_error")
                    or not isinstance(result.get("error"), dict)):
                raise AssertionError(f"{name}: missing or misattributed error feedback.")
        return [{"type": "text", "text": ACKNOWLEDGEMENT}], "end_turn", self.name, Usage(100, 20)
