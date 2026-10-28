import unittest

from agent.registry import CODE, MODEL, Registry, ToolSpec, TransientToolError
from agent.tools import build
from harness.trace import SessionTrace
from sandbox import inbox, reports, seed
from tests.support import ScratchTest, fixed_run


EMPTY = {"type": "object", "properties": {}, "additionalProperties": False}


class RegistryTest(ScratchTest):
    def setUp(self):
        super().setUp()
        seed.reset()
        seed.seed(None)
        self.request_id = inbox.request_id("SYN-thread-2001")

    def test_boundary_rejection_contains_a_repair_fact(self):
        result = build(self.request_id).call(
            "query_sales", {"period": "2026Q3"}, MODEL, step="sales"
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["type"], "invalid_arguments")
        self.assertIn("metric", result["error"]["repair"])

    def test_enum_values_are_compared_case_insensitively(self):
        result = build(self.request_id).call(
            "query_sales", {"period": "2026q3", "metric": "REVENUE"}, MODEL
        )
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["output"]["metric"], "revenue")

    def test_unknown_tool_is_logged_with_a_short_generic_result(self):
        trace = SessionTrace(self.tmp / "unknown.jsonl", "SYN-session")
        result = Registry([], trace=trace).call("secret_tool", {}, MODEL)
        self.assertEqual(result["error"]["type"], "unknown_tool")
        self.assertNotIn("parse_file", str(result))
        line = trace.lines()[-1]
        self.assertEqual((line["type"], line["name"], line["outcome"]),
                         ("tool_call", "secret_tool", "rejected"))

    def test_transient_failure_retries_to_the_cap(self):
        attempts = []

        def unavailable():
            attempts.append(1)
            raise TransientToolError("try later")

        registry = Registry(
            [ToolSpec("read", "read", EMPTY, unavailable, callers=(CODE,))],
            max_retries=2,
            sleep=lambda _: None,
        )
        result = registry.call("read", {}, CODE)
        self.assertEqual(len(attempts), 3)
        self.assertEqual(result["error"]["type"], "transient_failure")
        self.assertTrue(result["error"]["transient"])

    def test_write_retry_reuses_its_key_and_leaves_one_effect(self):
        attempts = []

        def flaky_save(kind, key):
            attempts.append(key)
            report, created = reports.save(self.request_id, kind, {}, "body", key=key)
            if len(attempts) == 1:
                raise TransientToolError("response lost before dispatch was confirmed")
            return {"id": report["id"], "created": created}

        schema = {
            "type": "object",
            "properties": {"kind": {"type": "string", "enum": ["standard"]}},
            "required": ["kind"],
            "additionalProperties": False,
        }
        registry = Registry(
            [ToolSpec("write", "write", schema, flaky_save, callers=(CODE,), writes=True,
                      key_fields=("kind",))],
            key_context=self.request_id,
            sleep=lambda _: None,
        )
        result = registry.call("write", {"kind": "standard"}, CODE, step="report")
        self.assertTrue(result["ok"], result)
        self.assertEqual(attempts[0], attempts[1])
        self.assertEqual(len(reports.for_request(self.request_id)), 1)

    def test_raising_hook_fails_closed(self):
        called = []

        def deny(**_):
            raise RuntimeError("policy service unavailable")

        registry = Registry(
            [ToolSpec("read", "read", EMPTY, lambda: called.append(True), callers=(CODE,))],
            pre_call_hook=deny,
        )
        result = registry.call("read", {}, CODE)
        self.assertEqual(result["error"]["type"], "hook_denied")
        self.assertEqual(called, [])

    def test_invalid_tool_result_is_rejected(self):
        result_schema = {
            "type": "object",
            "properties": {"count": {"type": "integer"}},
            "required": ["count"],
            "additionalProperties": False,
        }
        registry = Registry([
            ToolSpec("read", "read", EMPTY, lambda: {"count": "many"},
                     callers=(CODE,), result_schema=result_schema)
        ])
        result = registry.call("read", {}, CODE)
        self.assertEqual(result["error"]["type"], "invalid_result")

    def test_definition_order_is_fixed_for_every_request(self):
        expected = [
            "parse_file", "query_sales", "render_chart", "save_report",
            "draft_report_email", "draft_clarifying_question",
        ]
        first = [item["name"] for item in build(self.request_id).definitions()]
        second = [item["name"] for item in build(inbox.request_id("SYN-thread-2002")).definitions()]
        self.assertEqual(first, expected)
        self.assertEqual(second, expected)

    def test_every_model_visible_tool_rejects_and_traces_a_bad_argument(self):
        bad_calls = {
            "parse_file": {"unexpected": True},
            "query_sales": {},
            "render_chart": {},
            "save_report": {},
            "draft_report_email": {},
            "draft_clarifying_question": {"unexpected": True},
        }
        with fixed_run("tasks/standard_report_clean.yaml", "registry-bad-arguments") as run:
            registry = build(inbox.request_id("SYN-thread-1001"))
            results = [registry.call(name, args, MODEL, step=f"bad-{index}")
                       for index, (name, args) in enumerate(bad_calls.items(), start=1)]
        self.assertTrue(all(item["error"]["type"] == "invalid_arguments" for item in results))
        lines = run.trace_path.read_text().splitlines()
        tool_lines = [line for line in lines if '"type": "tool_call"' in line]
        self.assertEqual(len(tool_lines), 6)
        self.assertTrue(all('"outcome": "rejected"' in line for line in tool_lines))


if __name__ == "__main__":
    unittest.main()
