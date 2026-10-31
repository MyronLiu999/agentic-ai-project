"""The shared contracts exist and behave as PLAN.md section 3 says, so each member can code against
them before the others' parts are built."""

import unittest
from unittest import mock

from agent import critique, events
from tests.fakes import FakeRegistry, ScriptedTools


class ContractTest(unittest.TestCase):
    def test_fake_registry_keeps_a_fixed_order_and_records_calls(self):
        reg = FakeRegistry([{"name": "b"}, {"name": "a"}], {"a": lambda args: args["x"] * 2})
        self.assertEqual([d["name"] for d in reg.definitions()], ["a", "b"])
        self.assertEqual(reg.call("a", {"x": 2}, "model")["output"], 4)
        self.assertTrue(reg.call("nope", {}, "model")["is_error"])
        self.assertEqual(len(reg.calls), 2)

    def test_critique_off_passes_the_draft_through(self):
        with mock.patch("agent.critique.runtime.switch", return_value="off"):
            result = critique.run("REQ-x", {"body": "b"}, revise=lambda reason: {})
        self.assertTrue(result.passed)
        self.assertEqual(result.rounds, 0)

    def test_scripted_tools_calls_its_script_then_ends(self):
        class Two(ScriptedTools):
            script = [("parse_file", {}), ("query_sales", {"period": "2026Q3"})]
        model = Two()
        kinds = [model.create(system="", messages=[], tools=[])[1] for _ in range(3)]
        self.assertEqual(kinds, ["tool_use", "tool_use", "end_turn"])

    def test_end_reasons_never_use_the_runner_name(self):
        names = [v for k, v in vars(events).items() if k.isupper()]
        self.assertNotIn("token_budget", names)


if __name__ == "__main__":
    unittest.main()
