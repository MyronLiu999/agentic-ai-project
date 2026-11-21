"""The MCP server (Milestone 2, Part 1 task 3; owner: myron, M1).

The handout's tests: every tool call reaches the server through the registry; the tool list comes back twice in
the same order; a write retried under its key leaves one effect. Plus the server's own rules: no session (a
fresh server answers any request), an execution error as isError, a protocol error as JSON-RPC, and a lost
request for a write is an unknown outcome, never a blind retry.
"""

import json
import unittest
from unittest import mock

from agent.registry import CODE, MODEL
from harness.paths import state_dir
from sandbox import inbox, reports, seed
from tests.support import ScratchTest


def calls_logged() -> list[dict]:
    path = state_dir() / "mcp_calls.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []


class McpServerTest(ScratchTest):
    def setUp(self):
        super().setUp()
        seed.reset()
        seed.seed(None)
        self.request_id = inbox.request_id("SYN-thread-2001")

    def registry(self):
        from agent import tools
        return tools.build(self.request_id)

    def test_every_tool_call_reaches_the_server_through_the_registry(self):
        registry = self.registry()
        self.assertTrue(all(spec.fn.__name__.startswith("mcp:") for spec in registry._ordered))
        before = len(calls_logged())
        registry.call("parse_file", {}, MODEL)
        query = registry.call("query_sales", {"period": "2026Q3"}, MODEL)
        registry.call("save_report", {"kind": "standard", "body": "SYNTHETIC report.",
                                      "figures": {"period": "2026Q3",
                                                  "total_revenue": query["output"]["total_revenue"]}}, CODE,
                      step="save")
        logged = calls_logged()[before:]
        self.assertEqual([c["tool"] for c in logged], ["parse_file", "query_sales", "save_report"])
        self.assertTrue(all(c["request_id"] == self.request_id for c in logged))
        self.assertIsNone(logged[0]["key"])                    # a read carries no key
        self.assertTrue(logged[2]["key"].startswith("save_report:v1:"))   # the registry's key, never the model's

    def test_a_call_the_registry_rejects_never_reaches_the_server(self):
        registry = self.registry()
        before = len(calls_logged())
        result = registry.call("query_sales", {"period": "2026Q3", "distributor_id": "SYN-DIST-003"}, MODEL)
        self.assertEqual(result["error"]["type"], "invalid_arguments")
        self.assertEqual(len(calls_logged()), before)

    def test_the_tool_list_comes_back_twice_in_the_same_order(self):
        from agent import tools
        from mcp_server import client
        first = [t["name"] for t in client.list_tools()]
        second = [t["name"] for t in client.list_tools()]
        self.assertEqual(first, second)
        self.assertEqual(first, [s.name for s in tools.specs(None)])
        annotations = {t["name"]: t.get("annotations") or {} for t in client.list_tools()}
        self.assertTrue(annotations["send_report_email"].get("destructiveHint"))
        self.assertTrue(annotations["query_sales"].get("readOnlyHint"))

    def test_a_write_retried_under_its_key_leaves_one_effect(self):
        from mcp_server import client
        args = {"kind": "standard", "figures": {"period": "2026Q3", "total_revenue": 1.0}, "body": "SYNTHETIC."}
        first = client.call("save_report", args, request_id=self.request_id, key="retry-key-1", writes=True)
        again = client.call("save_report", args, request_id=self.request_id, key="retry-key-1", writes=True)
        self.assertEqual(first["report_id"], again["report_id"])
        self.assertEqual((first["created"], again["created"]), (True, False))
        self.assertEqual(len(reports.for_request(self.request_id)), 1)

    def test_no_session_a_fresh_server_answers_the_next_call(self):
        from mcp_server import client
        registry = self.registry()
        self.assertTrue(registry.call("parse_file", {}, MODEL)["ok"])
        started = client.server().started
        client.server().stop()                      # nothing a call needs lived in that process
        self.assertTrue(registry.call("query_sales", {"period": "2026Q3"}, MODEL)["ok"])
        self.assertEqual(client.server().started, started + 1)

    def test_every_request_carries_its_own_envelope_and_no_initialize(self):
        from mcp_server import client
        sent = []
        real = client._server.request

        def spy(method, params):
            sent.append((method, params))
            return real(method, params)

        with mock.patch.object(client._server, "request", side_effect=spy):
            self.registry().call("parse_file", {}, MODEL)
        self.assertEqual([m for m, _ in sent], ["tools/call"])
        context = sent[0][1]["_meta"]["agentic-ai-project/context"]
        self.assertEqual(context["request_id"], self.request_id)
        self.assertEqual(context["state_dir"], str(state_dir()))

    def test_an_execution_error_comes_back_with_is_error(self):
        from mcp_server import client
        response = client.server().request("tools/call", {
            "name": "render_chart", "arguments": {"title": "t", "labels": ["a"], "values": [1.0]},
            "_meta": {"agentic-ai-project/context": {"state_dir": str(state_dir()), "request_id": "REQ-missing",
                                                     "key": "k-missing"}}})
        self.assertNotIn("error", response)
        self.assertTrue(response["result"]["isError"])
        self.assertEqual(response["result"]["structuredContent"]["error"]["class"], "permanent")

    def test_a_protocol_error_is_a_json_rpc_error_and_the_registry_routes_it(self):
        from agent.registry import Registry, ToolSpec
        from mcp_server import client
        unknown = client.server().request("tools/call", {"name": "no_such_tool", "arguments": {},
                                                         "_meta": {"agentic-ai-project/context": {
                                                             "state_dir": str(state_dir())}}})
        self.assertEqual(unknown["error"]["code"], -32602)
        no_context = client.server().request("tools/call", {"name": "parse_file", "arguments": {}})
        self.assertEqual(no_context["error"]["code"], -32602)
        registry = Registry([ToolSpec("no_such_tool", "x", {"type": "object", "properties": {}},
                                      client.remote("no_such_tool", self.request_id), callers=(CODE,))])
        result = registry.call("no_such_tool", {}, CODE)
        self.assertEqual((result["error"]["type"], result["error"]["kind"]), ("protocol_error", "protocol"))

    def test_a_lost_request_is_an_unknown_outcome_for_a_write_and_a_retry_for_a_read(self):
        from mcp_server import client
        registry = self.registry()
        registry._sleep = lambda s: None
        with mock.patch.object(client._server, "request", side_effect=client.BrokenStream("closed")):
            write = registry.call("save_report", {"kind": "standard", "body": "x",
                                                  "figures": {"period": "2026Q3", "total_revenue": 1.0}}, CODE,
                                  step="lost")
            read = registry.call("parse_file", {}, MODEL)
        self.assertEqual(write["error"]["type"], "ambiguous_write")
        self.assertTrue(write["error"]["ambiguous"])
        self.assertEqual(read["error"]["type"], "transient_failure")

    def test_the_server_stamps_writes_and_messages_as_the_callers_run(self):
        from harness import runtime
        from tests.support import fixed_run
        from agent import tools
        with fixed_run("tasks/standard_report_clean.yaml", "mcp-stamp"):
            rid = inbox.request_id("SYN-thread-1001")
            registry = tools.build(rid)
            saved = registry.call("save_report", {"kind": "standard", "body": "SYNTHETIC.",
                                                  "figures": {"period": "2026Q3", "total_revenue": 1.0}}, CODE,
                                  step="stamp")
            self.assertTrue(saved["ok"], saved)
            self.assertEqual(reports.for_request(rid)[0]["stamp"], runtime.current_run().run_id)


if __name__ == "__main__":
    unittest.main()
