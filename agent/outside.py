"""The outside exchange: ask the stranger, wait, carry on (Milestone 2, Part 1 task 5; owner: abraham, B1-B2).

    ask(run_key, question, template=None) -> Reply(waiting_for=thread_id)
        the question goes out as a keyed write (tool ask_stranger) after disclosure.with_disclosure;
        a checkpoint records what the run waits for (checkpoints.set_wait) before the turn ends
    on_reply(thread_id, text) -> Reply
        agent.service.on_outside_reply calls it; resumes the run through runs.resume, in a new process if
        the app restarted; the reply enters the context labelled as the stranger's, never an instruction

Setup stub: no question is asked, and a reply is acknowledged and ignored.
"""

from __future__ import annotations

from harness.turns import Reply


def ask(run_key, question, template=None) -> Reply:
    raise NotImplementedError("outside.ask is abraham's B2")


def on_reply(thread_id: str, text: str) -> Reply:
    return Reply()
