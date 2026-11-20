"""The stop and its three commands, read before any model sees the message (Milestone 2; owner: abraham, B5).

    handle_command(session_id, text) -> Reply | None     None: the text is not a command
        /stop            every live run of the session        /stop <n>     run n
        /cancel <n>      end it for good, keeping what it did
        /resume <n>      lift the flag (with its time), ask again any approval the stop withdrew, carry on
        /rollback <n>    each write's compensation, newest first, "none" where there is none
                         (agent.registry's compensate(call_record)), logged as the operator's command

The stop writes policy.flags, which the hook reads first. Setup stub: /stop writes the flag; the
other commands answer that they are not built yet.
"""

from __future__ import annotations

import re

from agent import events
from harness import runtime
from harness.turns import Reply
from policy import flags

COMMAND = re.compile(r"^\s*/(stop|cancel|resume|rollback)(?:\s+(\d+))?\s*$", re.I)


def handle_command(session_id: str, text: str) -> Reply | None:
    match = COMMAND.match(text or "")
    if not match:
        return None
    command, number = match.group(1).lower(), match.group(2)
    if command == "stop":
        target = flags.set_stop(session_id, int(number) if number else None)
        runtime.trace(session_id).event(events.STOP, run_key=target, command="stop", set_at=runtime_now())
        return Reply(f"Stopped {'run ' + number if number else 'every live run in this session'}.")
    return Reply(f"/{command} is not built yet.")


def runtime_now() -> str:
    from harness.trace import now
    return now()
