import unittest

from harness.client import ModelResponse, Usage
from scripts.definition_cost import measure, surfaces


class _FakeClient:
    def create(self, *, system, messages, tools):
        tokens = 20 + (len(str(tools)) if tools else 0)
        return ModelResponse([{"type": "text", "text": "OK"}], "end_turn", "fake",
                             Usage(input_tokens=tokens, output_tokens=1), 0.0, 0.0)


class DefinitionCostTest(unittest.TestCase):
    def test_both_surfaces_are_measured_against_a_no_tool_call(self):
        rows = measure(_FakeClient)
        self.assertEqual(set(rows), {"first_draft", "rewrite"})
        self.assertTrue(all(row["definition_tokens"] > 0 for row in rows.values()))
        self.assertEqual(len(surfaces()["first_draft"]), 6)
        self.assertEqual(len(surfaces()["rewrite"]), 6)


if __name__ == "__main__":
    unittest.main()
