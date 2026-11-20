"""What each model call carries, assembled within a budget (Milestone 2, Part 1 task 6; owner: abraham, B3).

    create(session_id, *, purpose, system, messages, tools=None)   assemble, then call the model:
        the ONE way the loop and the workflows make a model call (plan.py and router.py: abraham routes them)
    assemble(session_id, *, purpose, system, messages, tools) -> (system, messages, left_out)
        your rule: what comes first, what is shortened or left out, what goes in only as an ID;
        the stranger's text labelled as theirs; memory.for_session and notes.for_call put in where they belong
    estimate_tokens(value) -> int       characters / 4, tool definitions included

Setup stub: assemble passes everything through and leaves nothing out.
"""

from __future__ import annotations

import json

from harness import runtime


def estimate_tokens(value) -> int:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return max(1, len(text) // 4)


def assemble(session_id, *, purpose, system, messages, tools):
    return system, messages, []


def create(session_id, *, purpose, system, messages, tools=None):
    system, messages, left_out = assemble(session_id, purpose=purpose, system=system, messages=messages,
                                          tools=tools or [])
    client = runtime.client(session_id)
    if tools is None:
        return client.create(system=system, messages=messages)
    return client.create(system=system, messages=messages, tools=tools)
