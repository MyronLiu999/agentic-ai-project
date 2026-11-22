"""Event-controlled model for real threaded service tests, with no network calls."""

import json
import threading

from harness.client import Usage


class ControlledModel:
    free = True

    def __init__(self, settings=None):
        self.entered = threading.Event()
        self.release = threading.Event()
        self.mode = "add"
        self.blocked_once = False
        self.calls = 0

    def create(self, *, system, messages, tools=None):
        self.calls += 1
        scope = None
        instructions = []
        calls = {}
        outputs = {}
        for message in messages:
            content = message.get("content")
            if isinstance(content, str):
                try:
                    value = json.loads(content)
                except ValueError:
                    continue
                if isinstance(value, dict):
                    scope = value.get("request_scope", scope)
                    for key in ("operator_instruction", "operator_instruction_addition"):
                        if value.get(key):
                            instructions.append(value[key])
            elif isinstance(content, list):
                for block in content:
                    if block.get("type") == "tool_use":
                        calls[block["id"]] = block
                    elif block.get("type") == "tool_result":
                        result = json.loads(block["content"])
                        if not result["ok"]:
                            raise AssertionError(result)
                        call = calls[block["tool_use_id"]]
                        outputs[(call["name"], call["input"].get("period"))] = result["output"]
        if scope is None:
            raise AssertionError("Threaded test expects the real agent path's request scope.")
        original = scope["id"].endswith("control-old")
        def invoke(name, args):
            return [{"type": "tool_use", "id": f"control-{self.calls}", "name": name, "input": args}], "tool_use", "says-done", Usage(100, 20)
        def wait_once():
            self.blocked_once = True
            self.entered.set()
            if not self.release.wait(timeout=10):
                raise TimeoutError("Test did not release the in-flight model call")
        if self.mode == "stop" and original and not self.blocked_once:
            wait_once()
            return invoke("render_chart", {"title": "Must not be written", "labels": ["Total"], "values": [1]})
        current = outputs.get(("query_sales", scope["period"]))
        if current is None:
            return invoke("query_sales", {"period": scope["period"]})
        if ("render_chart", None) not in outputs:
            return invoke("render_chart", {"title": "Earlier effect", "labels": ["Total"],
                                            "values": [current["total_revenue"]]})
        if original and not self.blocked_once:
            wait_once()
            if self.mode == "add":
                # This response was computed before the addition. The next model
                # round must receive it; the harmless read keeps the task active.
                return invoke("query_sales", {"period": "2026Q2"})
        if ("save_report", None) not in outputs:
            body = "Replacement task report." if not original else "Original task report."
            if any("validation note" in item for item in instructions):
                body += " Includes the validation note requested mid-task."
            return invoke("save_report", {"kind": "standard", "figures": {
                "period": scope["period"], "total_revenue": current["total_revenue"],
                "total_units": current["total_units"]}, "body": body})
        return [{"type": "text", "text": "The report is saved."}], "end_turn", "says-done", Usage(100, 10)
