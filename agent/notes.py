"""Durable session notes and a searchable, provenance-labelled event record.

The shared checkpoint table gives this data the sandbox's reset/restart lifetime.
Structured notes contain code-supplied IDs and status. Outside words belong only
in source-labelled events, never in planner notes or operator instructions.
"""
from __future__ import annotations

import hashlib
import json
import re

from harness import runtime
from harness.client import BudgetExceeded
from sandbox import control


def _key(session_id):
    run = runtime.current_run()
    return '__context__:' + (run.run_id if run else str(session_id))


def _state(conn, session_id):
    row = conn.execute('SELECT state_json FROM checkpoints WHERE run_key = ? ORDER BY id DESC LIMIT 1',
                       (_key(session_id),)).fetchone()
    return json.loads(row[0]) if row else {'done': [], 'open_items': [], 'ids': [], 'events': [], 'tokens': 0}


def _change(session_id, change):
    with control.connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        state = _state(conn, session_id)
        result = change(state)
        conn.execute('INSERT INTO checkpoints (run_key,saved_at,mode,state_json) VALUES (?,?,?,?)',
                     (_key(session_id), control.now(), 'sync', json.dumps(state, ensure_ascii=False)))
        # This is a session record, not a replay journal. Retain only its latest snapshot.
        conn.execute('DELETE FROM checkpoints WHERE run_key = ? AND id < '
                     '(SELECT MAX(id) FROM checkpoints WHERE run_key = ?)', (_key(session_id), _key(session_id)))
    return result


def snapshot(session_id):
    with control.connect() as conn:
        return _state(conn, session_id)


def update(session_id: str, *, done=None, open_items=None, ids=None) -> None:
    """Merge trusted status/identifier lists; never call this with outside text."""
    def change(state):
        for name, value in [('done', done), ('open_items', open_items), ('ids', ids)]:
            if value is None:
                continue
            values = [value] if isinstance(value, str) else list(value)
            if not all(isinstance(item, str) and len(item) <= 200 for item in values):
                raise ValueError('notes contain short code-supplied identifiers and status strings')
            state[name] = list(dict.fromkeys(state.get(name, []) + values))[-100:]
        completed = set(state.get('done', []))
        state['open_items'] = [item for item in state.get('open_items', []) if item not in completed]
    _change(session_id, change)


def for_call(session_id: str, call_kind: str) -> str:
    if 'plan' in call_kind:
        return ''
    kind = 'console' if runtime.current_run() is None else 'task'
    enabled = runtime.switch('notes.' + kind, 'off')
    # Long-session test tasks use the same console policy as the app.
    run = runtime.current_run()
    if run and (run.task_id.startswith('long_') or call_kind == 'console'):
        enabled = runtime.switch('notes.console', 'off')
    if enabled != 'on':
        return ''
    state = snapshot(session_id)
    return json.dumps({name: state.get(name, []) for name in ('done', 'open_items', 'ids')}, sort_keys=True)


def record(session_id, source, content, *, deduplicate=False):
    """Append source-labelled events; history reassembly may deduplicate old copies."""
    if source not in ('operator', 'stranger', 'tool', 'assistant', 'conversation', 'system'):
        raise ValueError('unknown session event source')
    encoded = json.dumps(content, sort_keys=True, ensure_ascii=False)
    identity = hashlib.sha256((source + ':' + encoded).encode()).hexdigest()[:20]
    def change(state):
        entries = state.setdefault('events', [])
        if not deduplicate or not any(e.get('content_key', e['id']) == identity for e in entries):
            entries.append({'id': identity + '-' + str(len(entries) + 1), 'content_key': identity, 'source': source, 'content': content, 'recorded_at': control.now()})
        return identity
    return _change(session_id, change)


def search(session_id, query='', limit=8, *, sources=None):
    """Retrieve exact stored events for /history and automatic context retrieval.

    A nonempty query is an AND search over distinct words, not a generated answer.
    The caller sees each original source and timestamp, including stranger entries.
    """
    terms = set(re.findall(r'[\w-]+', str(query).casefold()))
    entries = snapshot(session_id).get('events', [])
    selected = [e for e in entries if (sources is None or e['source'] in sources)
                and all(term in json.dumps(e['content'], ensure_ascii=False).casefold() for term in terms)]
    return selected[-max(0, min(int(limit), 50)):] if limit else []


def reserve_tokens(session_id, amount, ceiling):
    """Reserve before sending; a crash leaves the reservation charged, failing safe."""
    def change(state):
        used = state.get('tokens', 0)
        if ceiling is not None and used + amount > ceiling:
            raise BudgetExceeded('Session token ceiling reached. Start a new console session; '
                                 'its memory read and /history preserve earlier work.')
        state['tokens'] = used + amount
    _change(session_id, change)


def settle_tokens(session_id, reserved, actual):
    _change(session_id, lambda state: state.update(tokens=max(0, state.get('tokens', 0) - reserved + actual)))
