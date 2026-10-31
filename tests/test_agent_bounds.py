"""External budgets must stop work even when the model never cooperates."""

import unittest

from agent import bounds


class AgentBoundsTest(unittest.TestCase):
    def guard(self, **limits):
        self.now = 100.0
        return bounds.Budget(bounds.Limits(**limits), initial_tokens=200,
                             clock=lambda: self.now)

    def test_last_allowed_step_runs_but_the_next_one_does_not(self):
        budget = self.guard(max_steps=2)
        self.assertEqual(budget.start_step(200), 1)
        self.assertEqual(budget.start_step(201), 2)
        budget.check(202)  # Tools from the last allowed response may still run.
        with self.assertRaises(bounds.LimitReached) as raised:
            budget.start_step(202)
        self.assertEqual(raised.exception.reason, "step_limit")
        self.assertEqual(budget.steps, 2)

    def test_token_budget_counts_only_this_loop_and_stops_at_equality(self):
        budget = self.guard(token_budget=30)
        budget.check(229)
        with self.assertRaises(bounds.LimitReached) as raised:
            budget.check(230)
        self.assertEqual(raised.exception.reason, "agent_budget")
        self.assertEqual(budget.tokens_used(230), 30)

    def test_wall_clock_stops_at_the_deadline(self):
        budget = self.guard(wall_clock_s=5)
        self.now = 104.99
        budget.check(200)
        self.now = 105
        with self.assertRaises(bounds.LimitReached) as raised:
            budget.check(200)
        self.assertEqual(raised.exception.reason, "wall_clock")

    def test_remaining_harness_allowance_can_stop_a_loop_earlier(self):
        budget = bounds.Budget(bounds.Limits(token_budget=30), initial_tokens=200,
                               session_ceiling=210, clock=lambda: 0)
        budget.check(209)
        with self.assertRaises(bounds.LimitReached) as raised:
            budget.check(210)
        self.assertEqual(raised.exception.reason, "agent_budget")

    def test_invalid_limits_cannot_disable_enforcement(self):
        invalid = [{"max_steps": n} for n in (0, -1, True, 1.5)]
        invalid += [{"token_budget": n} for n in (0, -1, True, 1.5)]
        invalid += [{"wall_clock_s": n} for n in (0, -1, True, float("nan"), float("inf"))]
        for kwargs in invalid:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                bounds.Limits(**kwargs)
