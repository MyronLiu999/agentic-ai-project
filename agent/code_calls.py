"""Code that calls the tools (Milestone 2, Part 1 task 4; owner: myron, M3).

    run_program(run_key, code, registry) -> dict
        runs the model's short program in a process of its own: no network, no files outside a scratch
        folder; every call it makes goes through `registry` (so the hook, keys and call record hold);
        only its final result returns. A program that raises returns an error the model can repair from.

Switches: code_calls.<use_case>, off | on. Setup stub: not built.
"""

from __future__ import annotations


def run_program(run_key, code, registry) -> dict:
    raise NotImplementedError("code_calls.run_program is myron's M3")
