"""Code that calls the tools (Milestone 2, Part 1 task 4; owner: myron, M3), on a fake model.

The handout's tests: each call a program makes passes through the registry, a write in it is keyed, a call the
hook refuses is refused, and none of its results along the way reaches the context; a program that raises
returns an error the model can repair from, and one that reaches for the network or a file outside its folder
is stopped.
"""

import json
import unittest

from agent.registry import MODEL
from harness.client import Usage
from harness.scripted import estimate_tokens
from sandbox import inbox, reports, seed
from tests.support import ScratchTest, fixed_run

LOOPING_PROGRAM = """
totals = {}
for quarter in ["2026Q2", "2026Q3"]:
    got = call("query_sales", {"period": quarter})
    totals[quarter] = got["output"]["total_revenue"]
print("this line never reaches anyone")
result = {"best_quarter": max(totals, key=totals.get)}
"""


class RunsAProgram:
    """Calls run_program once with LOOPING_PROGRAM, then ends; keeps every request's messages."""
    name, free = "runs-a-program", True
    seen: list = []

    def __init__(self, settings=None):
        self.calls = 0

    def create(self, *, system, messages, tools):
        RunsAProgram.seen.append(json.dumps(messages, default=str))
        self.calls += 1
        prompt = estimate_tokens({"system": system, "tools": tools, "messages": messages})
        if self.calls == 1:
            return ([{"type": "tool_use", "id": "toolu_prog", "name": "run_program",
                      "input": {"code": LOOPING_PROGRAM}}], "tool_use", self.name, Usage(prompt, 10))
        return [{"type": "text", "text": "Done."}], "end_turn", self.name, Usage(prompt, 3)


def trace_lines(run) -> list[dict]:
    return [json.loads(l) for l in run.trace_path.read_text(encoding="utf-8").splitlines()]


class CodeCallsTest(ScratchTest):
    def setUp(self):
        super().setUp()
        seed.reset()
        seed.seed(None)
        self.request_id = inbox.request_id("SYN-thread-2001")

    def registry(self, on="on"):
        from agent import tools
        from harness import runtime
        runtime.configure(overrides=[f"code_calls.batch_reports={on}"])
        try:
            return tools.build(self.request_id)
        finally:
            runtime.configure()

    def program(self, code, registry=None):
        from agent import code_calls
        return code_calls.run_program("R-test", code, registry or self.registry())

    def test_offered_only_where_a_code_calls_switch_is_on(self):
        self.assertIn("run_program", [d["name"] for d in self.registry("on").definitions()])
        self.assertNotIn("run_program", [d["name"] for d in self.registry("off").definitions()])

    def test_only_the_final_result_comes_back(self):
        out = self.program(LOOPING_PROGRAM)
        self.assertEqual(out, {"result": {"best_quarter": "2026Q2"}, "calls": 2})

    def test_a_write_in_a_program_is_keyed_and_leaves_one_effect(self):
        program = ('args = {"kind": "standard", "body": "SYNTHETIC.", '
                   '"figures": {"period": "2026Q3", "total_revenue": 1.0}}\n'
                   'a = call("save_report", args)\nb = call("save_report", args)\n'
                   'result = [a["output"]["report_id"], b["output"]["created"]]')
        out = self.program(program)
        self.assertEqual(out["calls"], 2)
        self.assertEqual(out["result"][1], False)            # the second call met the first call's key
        self.assertEqual(len(reports.for_request(self.request_id)), 1)

    def test_a_call_the_hook_refuses_is_refused_inside_the_program(self):
        program = 'r = call("send_report_email", {"pending_id": 999})\nresult = r["error"]["type"]'
        out = self.program(program)
        self.assertEqual(out["result"], "policy_denied")      # send_report_email/unknown_draft is prohibited

    def test_a_program_cannot_call_run_program(self):
        out = self.program('result = call("run_program", {"code": "result = 1"})["error"]["type"]')
        self.assertEqual(out["result"], "caller_denied")

    def test_a_program_that_raises_returns_an_error_to_repair_from(self):
        out = self.program("x = 1\ny = x / 0\n")
        self.assertIn("ZeroDivisionError", out["error"])
        self.assertEqual(out["line"], 2)
        registry = self.registry()
        failed = registry.call("run_program", {"code": "x = 1\ny = x / 0\n"}, MODEL)
        self.assertEqual(failed["error"]["type"], "permanent_failure")
        self.assertIn("line 2", failed["error"]["repair"])

    def test_network_and_outside_files_are_stopped(self):
        net = self.program('import socket\nsocket.create_connection(("example.com", 80), timeout=2)')
        self.assertIn("network access is not allowed", net["error"])
        outside = self.program('result = open(r"%s").read()' % (__file__,))
        self.assertIn("outside the program's scratch folder", outside["error"])
        spawn = self.program('import subprocess\nsubprocess.run(["python", "-V"])')
        self.assertIn("not allowed", spawn["error"])
        inside = self.program('open("notes.txt", "w").write("ok")\nresult = open("notes.txt").read()')
        self.assertEqual(inside["result"], "ok")

    def test_a_send_from_a_program_gets_the_disclosure_line_from_code(self):
        from agent import code_calls, disclosure
        self.assertTrue(disclosure.has_line(code_calls._disclosed("ask_stranger", {"question": "Units?"})["question"]))


class CodeCallsLoopTest(ScratchTest):
    def test_inner_calls_go_through_the_registry_and_stay_out_of_the_context(self):
        from agent import loop
        RunsAProgram.seen = []
        with fixed_run("tasks/messy_file_semicolon.yaml", "code-call-loop", backend="tests.test_code_calls:RunsAProgram",
                       overrides=["code_calls.batch_reports=on"]) as run:
            rid = inbox.all_requests()[0]["id"]
            result = loop.run("code-call-loop", rid, "Which quarter sold more?")
        self.assertEqual(result.reason, "done")
        lines = trace_lines(run)
        inner = [l for l in lines if l.get("type") == "tool_call" and l.get("caller") == "code"]
        self.assertEqual([l["name"] for l in inner], ["query_sales", "query_sales"])
        self.assertEqual(sum(l.get("type") == "hook_decision" and l.get("tool") == "query_sales" for l in lines), 2)
        code_events = [l for l in lines if l.get("type") == "code_call"]
        self.assertEqual(code_events[0]["calls"], 2)
        second_request = RunsAProgram.seen[1]
        self.assertNotIn("by_product", second_request)        # no inner result reached the model
        # what came back to the model is the tool result alone: the final value and the count of calls
        returned = json.loads(second_request)[-1]["content"][0]["content"]
        self.assertEqual(json.loads(returned)["output"], {"result": {"best_quarter": "2026Q2"}, "calls": 2})
        self.assertNotIn("never reaches anyone", returned)    # what the program printed stayed out


if __name__ == "__main__":
    unittest.main()
