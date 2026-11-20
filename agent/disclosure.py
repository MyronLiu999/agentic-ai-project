"""The line that tells a stranger an agent wrote the message (Milestone 2, Part 2 task 8; owner: claudea).

Code adds it, never a prompt. Every send passes with_disclosure() before it reaches the registry,
whether the agent loop, a workflow or a code-call program makes it, so the approval screen's dry run
shows it too; the hook (policy/hook.py) refuses a send whose text lacks it. A message the operator
writes and sends by hand from the product page is the operator's own and needs none.

    LINE                         the fixed text; never retype it anywhere else
    with_disclosure(text) -> str
    has_line(text) -> bool
    check(call) -> bool          False only for a send whose text lacks LINE
    SENDS                        the tools that send to a stranger, and where their text is
"""

from __future__ import annotations

LINE = ("This message was written by an automated agent for the sales analytics team. "
        "To reach a person, reply to this thread with \"human\" and an analyst will answer.")

# tool -> the argument holding the text it sends; None: the text is in the pending record it names
SENDS = {"ask_stranger": "question", "send_report_email": None}


def has_line(text) -> bool:
    return isinstance(text, str) and LINE in text


def with_disclosure(text: str) -> str:
    text = str(text or "").rstrip()
    return text if has_line(text) else f"{text}\n\n{LINE}"


def _sent_text(name: str, args: dict):
    field = SENDS[name]
    if field is not None:
        return (args or {}).get(field)
    from sandbox import pending
    record = pending.get(int((args or {}).get("pending_id", 0) or 0))
    return record.get("body") if record else None


def check(call: dict) -> bool:
    name = call.get("name")
    if name not in SENDS:
        return True
    try:
        return has_line(_sent_text(name, call.get("args") or {}))
    except Exception:
        return False        # a send whose text cannot be read is refused, like any doubt at the hook
