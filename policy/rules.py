"""Limits the operator stated in the console, as rules the hook reads (Milestone 2 setup).

A limit said in chat is only text that compaction can drop, so code turns it into a rule here
(policy/limits.py parses it, never the model) and the hook reads it on every call.

    add_rule(session_id, rule) -> dict
    rules_for(session_id) -> list[dict]
    matches(rule, action_class, tool=None) -> bool     (myron, M5) does the rule name this call?

    rule = {"action_class": "send_report_email/*", "effect": "deny" | "ask",
            "source_text": "send nothing until I have read it", "created": <time>}

A rule's action_class is an fnmatch pattern over action classes ("send_report_email/*"), or "sends/*": every
tool that sends to a stranger (agent/disclosure.SENDS), whatever its circumstance.
"""

from __future__ import annotations

import fnmatch
import json

from sandbox import control as state_store

EFFECTS = ("deny", "ask")
SENDS = "sends/*"


def matches(rule: dict, action_class: str, tool: str | None = None) -> bool:
    pattern = str(rule.get("action_class") or "")
    if pattern == SENDS:
        from agent import disclosure
        return (tool or action_class.split("/", 1)[0]) in disclosure.SENDS
    return fnmatch.fnmatchcase(action_class, pattern)


def add_rule(session_id: str, rule: dict) -> dict:
    if rule.get("effect") not in EFFECTS or not rule.get("action_class"):
        raise ValueError("a rule needs an action_class and an effect of 'deny' or 'ask'")
    rule = {**rule, "created": rule.get("created") or state_store.now()}
    with state_store.connect() as conn:
        conn.execute("INSERT INTO rules (session_id, rule_json, created) VALUES (?, ?, ?)",
                     (session_id, json.dumps(rule, sort_keys=True), rule["created"]))
    return rule


def rules_for(session_id: str | None) -> list[dict]:
    if not session_id:
        return []
    with state_store.connect() as conn:
        rows = conn.execute("SELECT rule_json FROM rules WHERE session_id = ? ORDER BY id", (session_id,)).fetchall()
    return [json.loads(r["rule_json"]) for r in rows]
