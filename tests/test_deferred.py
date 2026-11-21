"""Deferred loading (Milestone 2, Part 1 task 4; owner: myron, M3), on a fake model.

With tools.loading = deferred: the first request carries only the search tool and the tools every case needs;
the definitions a search finds enter the next request; a search that finds nothing says so and is logged.
With all: every definition, and no search tool.
"""

import json
import unittest

from harness.client import Usage
from harness.scripted import estimate_tokens
from sandbox import inbox, seed
from tests.support import ScratchTest, fixed_run


class SearchesForChart:
    """Searches the catalogue for a chart, draws one, then ends; keeps the tool names of every request."""
    name, free = "searches-for-chart", True
    offered: list[list[str]] = []

    def __init__(self, settings=None):
        self.calls = 0

    def create(self, *, system, messages, tools):
        SearchesForChart.offered.append([t["name"] for t in tools or []])
        self.calls += 1
        script = [("search_tools", {"query": "make a bar chart"}),
                  ("render_chart", {"title": "Q3", "labels": ["SYN-SKU-003"], "values": [412]})]
        prompt = estimate_tokens({"system": system, "tools": tools, "messages": messages})
        if self.calls <= len(script):
            tool, args = script[self.calls - 1]
            return ([{"type": "tool_use", "id": f"toolu_{self.calls}", "name": tool, "input": args}], "tool_use",
                    self.name, Usage(prompt, 10))
        return [{"type": "text", "text": "Done."}], "end_turn", self.name, Usage(prompt, 3)


def trace_lines(run) -> list[dict]:
    return [json.loads(l) for l in run.trace_path.read_text(encoding="utf-8").splitlines()]


class DeferredRegistryTest(ScratchTest):
    def setUp(self):
        super().setUp()
        seed.reset()
        seed.seed(None)
        self.request_id = inbox.request_id("SYN-thread-2001")

    def build(self, loading):
        from agent import tools
        from harness import runtime
        runtime.configure(overrides=[f"tools.loading={loading}"])
        try:
            return tools.build(self.request_id)
        finally:
            runtime.configure()

    def test_first_request_carries_the_search_and_the_always_needed_tools(self):
        registry = self.build("deferred")
        names = [d["name"] for d in registry.definitions()]
        self.assertEqual(names, ["parse_file", "query_sales", "save_report", "draft_report_email", "search_tools"])
        self.assertNotIn("render_chart", names)

    def test_found_definitions_join_the_next_request(self):
        registry = self.build("deferred")
        kept = registry.definitions()                      # the loop keeps this list for the turn
        result = registry.call("search_tools", {"query": "chart"}, "model")
        self.assertEqual(result["output"]["matches"], ["render_chart"])
        self.assertIn("render_chart", [d["name"] for d in kept])
        self.assertEqual(registry.loaded, ("render_chart",))
        self.assertEqual([d["name"] for d in kept], [d["name"] for d in registry.definitions()])

    def test_a_search_that_finds_nothing_says_so(self):
        registry = self.build("deferred")
        result = registry.call("search_tools", {"query": "xyzzy plugh"}, "model")
        self.assertEqual(result["output"]["matches"], [])
        self.assertIn("nothing matched", result["output"]["note"])
        self.assertEqual(registry.loaded, ())

    def test_all_offers_every_definition_and_no_search(self):
        names = [d["name"] for d in self.build("all").definitions()]
        self.assertEqual(len(names), 8)
        self.assertNotIn("search_tools", names)


class DeferredLoopTest(ScratchTest):
    def test_on_a_fake_model_the_search_widens_the_next_request_and_is_logged(self):
        from agent import loop
        SearchesForChart.offered = []
        with fixed_run("tasks/messy_file_semicolon.yaml", "deferred-loop", backend="tests.test_deferred:SearchesForChart",
                       overrides=["tools.loading=deferred"]) as run:
            rid = inbox.all_requests()[0]["id"]
            result = loop.run("deferred-loop", rid, "Make a chart of the file's units.")
            miss = None
            from agent import tools
            registry = tools.build(rid)
            if registry.loading == "deferred":
                miss = registry.call("search_tools", {"query": "teleport"}, "model")
        self.assertEqual(result.reason, "done")
        first, second = SearchesForChart.offered[0], SearchesForChart.offered[1]
        self.assertNotIn("render_chart", first)
        self.assertIn("search_tools", first)
        self.assertIn("render_chart", second)
        searches = [l for l in trace_lines(run) if l.get("type") == "search_tools"]
        self.assertEqual(searches[0]["matches"], ["render_chart"])
        self.assertEqual(searches[-1]["matches"], [])         # the miss is logged, so misses can be counted
        self.assertIsNotNone(miss)
        charts = [l for l in trace_lines(run) if l.get("type") == "tool_call" and l.get("name") == "render_chart"]
        self.assertEqual(len(charts), 1)


if __name__ == "__main__":
    unittest.main()
