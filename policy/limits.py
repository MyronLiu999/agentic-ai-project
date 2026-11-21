"""Turn a limit the operator states into a rule (Milestone 2; owner: myron, M5).

    parse_limit(text) -> dict | None     a rule for policy/rules.py, or None if the text states no limit

Code only, never the model: a limit said in chat is only text that compaction can drop (Lecture 5,
slide 17), so agent/service.py calls this on every operator message before any model sees it, and the hook
reads the rule on every call. Each pattern below is a sentence an operator would type; anything else states
no limit. A rule's action_class is an fnmatch pattern over action classes, or "sends/*" for every tool that
sends to a stranger (agent/disclosure.SENDS).

    "send nothing until I have read it"        -> sends/*            ask
    "don't send anything" / "do not send emails" -> sends/* or send_report_email/*   deny
    "ask me before you send"                   -> sends/*            ask
    "don't ask the distributor" / "do not contact the distributor"  -> ask_stranger/*   deny
    "no charts" / "do not render charts"       -> render_chart/*     deny
"""

from __future__ import annotations

import re

_NEG = r"(?:do\s*not|don'?t|never|no(?:body)?)"

PATTERNS = [
    # (regex, action_class, effect), first match wins; ordered from the most specific
    (rf"\b(?:send|email|mail)\s+nothing\b.*\buntil\b|\b{_NEG}\s+send\b.*\b(?:until|before)\b.*\b(?:read|review|approve|check|see)",
     "sends/*", "ask"),
    (r"\bask\s+me\s+(?:first\s+)?before\b.*\bsend|\bcheck\s+with\s+me\s+before\b.*\bsend", "sends/*", "ask"),
    (rf"\b{_NEG}\s+send\b.*\b(?:e-?mails?|reports?)\b|\bno\s+(?:e-?mails?|report\s+e-?mails?)\s+(?:to\s+be\s+)?sent\b",
     "send_report_email/*", "deny"),
    (rf"\b{_NEG}\s+send\s+(?:anything|any\s+messages?|messages?)\b|\bsend\s+nothing\b", "sends/*", "deny"),
    (rf"\b{_NEG}\s+(?:ask|contact|message|write\s+to)\s+(?:the\s+|any\s+)?(?:distributors?|strangers?|contacts?|customers?)\b",
     "ask_stranger/*", "deny"),
    (rf"\bno\s+charts?\b|\b{_NEG}\s+(?:render|make|draw|create)\s+(?:a\s+|any\s+)?charts?\b", "render_chart/*", "deny"),
]


def parse_limit(text: str) -> dict | None:
    if not isinstance(text, str) or text.strip().startswith("/"):
        return None            # console commands (/stop, ...) are not limits
    lowered = " ".join(text.casefold().split())
    for pattern, action_class, effect in PATTERNS:
        if re.search(pattern, lowered):
            return {"action_class": action_class, "effect": effect, "source_text": text.strip()[:300]}
    return None
