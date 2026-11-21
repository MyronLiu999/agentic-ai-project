"""One factual outside exchange, persisted before waiting and resumed by run key."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import re

from agent import checkpoints, disclosure, events, runs, tools
from agent.registry import CODE, MODEL
from harness import runtime
from harness.turns import Reply
from policy import flags
from sandbox import control, inbox

TEMPLATES = {
    'units_column': ('Which column in your uploaded file contains the number of units sold? '
                     'Please reply units_column= followed by the exact column name.')
}
WAIT_HOURS = 48
UNIT_HEADERS = {'units', 'units_sold', 'quantity', 'qty', 'menge', 'quantity_sold'}


def needs_clarification(parsed):
    """A missing semantic header is observable; model uncertainty is not a trigger."""
    columns = parsed.get('columns', []) if isinstance(parsed, dict) else []
    if len(columns) < 2 or not parsed.get('rows'):
        return False
    names = {str(c).strip().lower().replace(' ', '_') for c in columns}
    return not any(c in UNIT_HEADERS or c.endswith('_units') for c in names)


def ask(run_key, question, template=None) -> Reply:
    state = checkpoints.load(run_key) or {}
    request = inbox.get(state.get('request_id'))
    if request is None:
        raise ValueError('A question needs a checkpoint with a known request.')
    if template is not None and template not in TEMPLATES:
        raise ValueError('Unknown fixed question template.')
    exchange = state.get('outside_exchange') or {}
    if exchange.get('status') == 'waiting':
        return Reply('The question is already awaiting a reply.', waiting_for=exchange['thread_id'])
    if exchange.get('status') in ('answered', 'held'):
        return Reply('This exchange is already answered or held for the operator.')
    caller = CODE if template is not None else MODEL
    text = disclosure.with_disclosure(TEMPLATES[template] if template else question)
    if flags.is_stopped(run_key):
        return Reply('The operator stopped this run. No question was sent.')
    deadline = (datetime.now(timezone.utc) + timedelta(hours=WAIT_HOURS)).isoformat()
    exchange = {'status': 'sending', 'thread_id': request['thread_id'], 'template': template,
                'question': text, 'deadline': deadline, 'caller': caller}
    checkpoints.update(run_key, outside_exchange=exchange)
    from agent import stop
    stop.notice(run_key)
    result = tools.build(request['id']).call('ask_stranger', {'question': text}, caller,
                                           step='outside-units' if template else 'outside-question')
    stop.after_call(run_key)
    if not result.get('ok') or result.get('is_error'):
        error = result.get('error') or {}
        if error.get('type') == 'approval_required':
            checkpoints.set_wait(run_key, 'approval', str(error.get('approval_id')))
            return Reply('The model-written question waits for operator approval.')
        checkpoints.update(run_key, outside_exchange={**exchange, 'status': 'failed'})
        runtime.trace().end(events.TOOL_ERROR, detail='The outside question was not sent.')
        return Reply('The question could not be sent; the operator must resolve the tool refusal.')
    output = result.get('output') or {}
    if output.get('thread_id') != request['thread_id']:
        checkpoints.update(run_key, held=True, outside_exchange={**exchange, 'status': 'held'})
        return Reply('The question returned another thread; held for the operator.')
    record_wait(run_key, result, text, template)
    inbox.set_status(request['id'], 'awaiting_answer')
    from agent import notes
    notes.update(runs.session_of(run_key), open_items=[request['id']], ids=[request['thread_id']])
    checkpoints.to_trace(runtime.trace(), run_key)
    return Reply('Asked which column holds units; waiting up to 48 hours for the stranger.',
                 ['Sent the fixed units-column question.'], request['thread_id'])


def _hold(run_key, state, why):
    exchange = state.get('outside_exchange') or {}
    checkpoints.update(run_key, held=True, outside_exchange={**exchange, 'status': 'held', 'why': why})
    checkpoints.clear_wait(run_key)
    runtime.trace().event(events.ESCALATION, run_key=run_key, signal='outside_unresolved',
                          attempted='clarify uploaded units', why=why, needs='operator review', over_cap=False)
    runtime.trace().end(events.HELD, detail=why)
    return Reply(f'Held for the operator: {why}')


def expire(session_id=None):
    """Lazy deadline check on the next console/thread event; no background auto-resume."""
    expired = []
    for wait in checkpoints.waiting(session_id):
        if wait['kind'] == 'outside' and _expired(wait.get('deadline')):
            _hold(wait['run_key'], checkpoints.load(wait['run_key']) or {}, 'the outside reply deadline passed')
            expired.append(wait['run_key'])
    return expired


def _expired(deadline):
    return bool(deadline and datetime.fromisoformat(deadline) <= datetime.now(timezone.utc))


def record_wait(run_key, result, question, template=None):
    """Persist an already-sent registry call; never send it a second time here."""
    state = checkpoints.load(run_key) or {}
    request = inbox.get(state.get('request_id'))
    output = result.get('output') or {}
    if not result.get('ok') or not request or output.get('thread_id') != request['thread_id']:
        raise ValueError('Cannot wait on an unsuccessful or wrong-thread question.')
    prior = state.get('outside_exchange') or {}
    deadline = prior.get('deadline') or (datetime.now(timezone.utc) + timedelta(hours=WAIT_HOURS)).isoformat()
    checkpoints.update(run_key, outside_exchange={'status': 'waiting', 'thread_id': request['thread_id'],
                       'question': question, 'template': template, 'deadline': deadline,
                       'message_id': output.get('message_id')})
    checkpoints.set_wait(run_key, 'outside', request['thread_id'], deadline)
    inbox.set_status(request['id'], 'awaiting_answer')


def on_reply(thread_id: str, text: str) -> Reply:
    waiting = [w for w in checkpoints.waiting() if w['kind'] == 'outside' and w['ref'] == thread_id]
    if len(waiting) != 1:
        return Reply('No unique run is waiting for this thread; the operator can inspect the reply.')
    wait = waiting[0]
    run_key = wait['run_key']
    if (checkpoints.load(run_key) or {}).get('cancelled'):
        return Reply('No run is waiting for this reply; the run was cancelled.')
    event = {'kind': 'outside_reply', 'thread_id': thread_id, 'text': text}
    # Claim the first reply even while stopped. Later duplicate/conflicting deliveries cannot replace it.
    with control.connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        claimed = conn.execute('DELETE FROM waits WHERE run_key = ? AND kind = ? AND ref = ?',
                               (run_key, 'outside', thread_id)).rowcount
        if not claimed:
            return Reply('No run is waiting for this reply now.')
        latest = conn.execute('SELECT state_json FROM checkpoints WHERE run_key = ? ORDER BY id DESC LIMIT 1',
                              (run_key,)).fetchone()
        state = json.loads(latest['state_json'])
        exchange = state.get('outside_exchange') or {}
        state.update(outside_reply=event, waiting_for=None,
                     outside_exchange={**exchange, 'status': 'received'})
        conn.execute('INSERT INTO checkpoints (run_key, saved_at, mode, state_json) VALUES (?, ?, ?, ?)',
                     (run_key, control.now(), 'sync', json.dumps(state)))
    if text.strip().lower() == 'human':
        return _hold(run_key, state, 'the stranger requested a person')
    if _expired(wait.get('deadline')):
        return _hold(run_key, state, 'the outside reply arrived after its deadline')
    if exchange.get('template') == 'units_column':
        match = re.fullmatch(r'\s*units_column\s*=\s*([^\r\n=]+)\s*', text)
        columns = (state.get('outside_parsed') or {}).get('columns', [])
        if not match or match[1].strip() not in columns:
            return _hold(run_key, state, 'the answer does not name one exact uploaded column')
        event['units_column'] = match[1].strip()
    checkpoints.update(run_key, outside_reply=event, outside_exchange={**exchange, 'status': 'answered'})
    from agent import notes
    notes.record(runs.session_of(run_key), 'stranger', text)
    if flags.is_stopped(run_key):
        return Reply('Reply saved as stranger data; the operator stopped this run. Resume is required.')
    from agent.service import continue_run
    return continue_run(run_key, event)


def statuses():
    """Only computed wait status reaches the threads page."""
    result = {}
    with control.connect() as conn:
        rows = conn.execute('SELECT state_json FROM checkpoints WHERE id IN '
                            '(SELECT MAX(id) FROM checkpoints GROUP BY run_key)').fetchall()
    for row in rows:
        state = json.loads(row['state_json'])
        exchange = state.get('outside_exchange') or {}
        if exchange.get('thread_id'):
            result[exchange['thread_id']] = {'status': exchange['status'], 'deadline': exchange.get('deadline')}
    return result
