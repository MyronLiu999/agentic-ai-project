"""Cooperative limits enforced by code, outside the model's decisions.

An in-flight synchronous model/tool call may exceed the time or token allowance.
Check again when it returns, before authorizing any more work.
"""

from dataclasses import dataclass
import math
import time

from agent import events

MAX_STEPS = 12
TOKEN_BUDGET = 150_000
WALL_CLOCK_S = 90
REASONS = {
    "max_steps": "Six tool rounds, a final answer, two critique revisions, and three repair rounds; provisional.",
    "token_budget": "A per-loop allowance below the 400000-token harness ceiling; includes cached tokens.",
    "wall_clock_s": "Stop further work after a 90-second interactive turn; in-flight calls finish first.",
}


@dataclass(frozen=True)
class Limits:
    max_steps: int = MAX_STEPS
    token_budget: int = TOKEN_BUDGET
    wall_clock_s: float = WALL_CLOCK_S

    def __post_init__(self):
        for name in ("max_steps", "token_budget"):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if (type(self.wall_clock_s) not in (int, float)
                or not math.isfinite(self.wall_clock_s) or self.wall_clock_s <= 0):
            raise ValueError("wall_clock_s must be a positive finite number")


class LimitReached(Exception):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


class Budget:
    def __init__(self, limits: Limits, *, initial_tokens: int, session_ceiling: int | None = None,
                 clock=None):
        self.limits = limits
        self.initial_tokens = initial_tokens
        self.token_ceiling = initial_tokens + limits.token_budget
        if session_ceiling is not None:
            self.token_ceiling = min(self.token_ceiling, session_ceiling)
        self.clock = clock or time.monotonic
        self.started = self.clock()
        self.steps = 0

    def tokens_used(self, total_tokens: int) -> int:
        return total_tokens - self.initial_tokens

    def check(self, total_tokens: int) -> None:
        if self.clock() - self.started >= self.limits.wall_clock_s:
            raise LimitReached(events.WALL_CLOCK)
        if total_tokens >= self.token_ceiling:
            raise LimitReached(events.AGENT_BUDGET)

    def start_step(self, total_tokens: int) -> int:
        self.check(total_tokens)
        if self.steps >= self.limits.max_steps:
            raise LimitReached(events.STEP_LIMIT)
        self.steps += 1
        return self.steps
