"""The app: your product's pages (app/product.py) and the operator's pages.

    /console    the operator's chat: sessions and their history. Each message goes to
                agent.service.operator_turn through harness.turns, the path run.py takes.
    /queue      the work waiting: your sandbox's queue, the threads waiting for an
                outside reply, and what waits for approval.
    /threads    the outside channel's conversations. You can write as the stranger,
                to try a conversation by hand; in experiments the task file plays
                them. Each message goes once to agent.service.on_outside_reply, or to
                a turn waiting on the thread in channel.wait_for_reply.
    /approvals  what waits for the operator's answer, from pending_approvals(): empty
                until you build an approval gate.
    /traces     the run records in results/ (the free ones in results/_free/ marked
                free) and every session's trace.

Change your product's pages freely: they read and write your domain data through
sandbox/ modules, the same ones your agent's tools wrap. These pages keep their
contract: they reach the agent only through harness.turns, and app/ imports
nothing from agent/ but agent.service. `make check` tests it.
"""

from __future__ import annotations

import json
import re
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlencode

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

import channel
from app import product, templates
from harness import records, runtime, turns
from harness.paths import results_dir, traces_dir
from harness.trace import SessionTrace, read_trace

SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,120}$")
CONSOLE_LINES = ("operator", "reply", "progress", "outside", "error", "approval")


@asynccontextmanager
async def lifespan(_app):
    runtime.configure()          # settings, prices and switches, loaded once at start-up
    yield


app = FastAPI(title="Project", lifespan=lifespan)
app.include_router(product.router)


def page(request: Request, name: str, **context):
    return templates.TemplateResponse(request, name, {"page": name.split(".")[0], **context})


def _safe(value: str) -> str:
    if not SAFE_ID.match(value or ""):
        raise HTTPException(404, "no such item")
    return value


def _agent_error(exc: Exception) -> str:
    if isinstance(exc, NotImplementedError):
        return turns.NOT_BUILT.format(name=str(exc).split(":")[0] or "this function")
    return f"The agent raised {type(exc).__name__}: {exc}"


# -- the console ----------------------------------------------------------------------------

def _sessions() -> list[dict]:
    out = []
    for path in traces_dir().glob("*.jsonl"):
        lines = read_trace(path)
        if not lines or lines[0].get("type") != "session_start" or lines[0].get("source") != "console":
            continue
        first = next((x.get("text", "") for x in lines if x.get("type") == "operator"), "")
        out.append({"id": lines[0]["session_id"], "started": lines[0]["at"], "turns":
                    sum(1 for x in lines if x.get("type") == "operator"), "first": first[:120]})
    return sorted(out, key=lambda s: s["started"], reverse=True)


def _history(session_id: str) -> list[dict]:
    """The session's lines; each agent reply carries cards for the requests it names (product.py)."""
    path = traces_dir() / f"{runtime.safe_name(session_id)}.jsonl"
    lines = [x for x in read_trace(path) if x.get("type") in CONSOLE_LINES] if path.exists() else []
    for line in lines:
        if line.get("type") == "reply":
            try:
                rids = product.request_ids(line.get("text", ""), *line.get("actions") or [])
                line["cards"] = product.request_cards(rids)
            except Exception:  # a card is a convenience; the reply still shows without it
                line["cards"] = []
    return lines


def _console(request: Request, session_id: str | None):
    try:
        open_requests = product.open_requests()
    except Exception:
        open_requests = []
    return page(request, "console.html", sessions=_sessions(), session_id=session_id,
                history=_history(session_id) if session_id else [], open_requests=open_requests)


@app.get("/console", response_class=HTMLResponse)
def console_list(request: Request):
    return _console(request, None)


@app.post("/console/new")
def console_new(prompt: str = Form("")):
    """A new session. `prompt`, from a request's "Ask the analyst" button, is only put in the
    message box for the operator to send; nothing goes to the agent until they do."""
    session_id = f"s-{time.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(2)}"
    SessionTrace(traces_dir() / f"{session_id}.jsonl", session_id).write(
        {"type": "session_start", "source": "console", "switches": runtime.switches()})
    query = f"?{urlencode({'q': prompt[:300]})}" if prompt.strip() else ""
    return RedirectResponse(f"/console/{session_id}{query}", status_code=303)


@app.get("/console/{session_id}", response_class=HTMLResponse)
def console_session(request: Request, session_id: str):
    _safe(session_id)
    return _console(request, session_id)


@app.get("/console/{session_id}/history", response_class=HTMLResponse)
def console_history(request: Request, session_id: str):
    _safe(session_id)
    return templates.TemplateResponse(request, "_history.html", {"history": _history(session_id)})


@app.post("/console/{session_id}/turn")
def console_turn(request: Request, session_id: str, text: str = Form(...)):
    _safe(session_id)
    reply, error = None, None
    try:
        reply = turns.operator_turn(session_id, text)
    except Exception as exc:  # the trace has the error; the console shows it
        error = _agent_error(exc)
    if "application/json" in request.headers.get("accept", ""):
        return JSONResponse({"ok": error is None, "reply": reply.as_dict() if reply else None, "error": error})
    return RedirectResponse(f"/console/{session_id}", status_code=303)


# -- the queue -------------------------------------------------------------------------------

@app.get("/queue", response_class=HTMLResponse)
def queue(request: Request):
    items, item_error, approvals, approval_error = [], None, [], None
    try:
        from sandbox import queue as sandbox_queue
        items = [dict(i) for i in sandbox_queue.waiting() or []]
    except Exception as exc:
        item_error = f"sandbox/queue.py raised {type(exc).__name__}: {exc}"
    try:
        approvals = turns.pending_approvals()
    except Exception as exc:
        approval_error = _agent_error(exc)
    waiting = [t for t in channel.threads() if t["waiting_for_outside"]]
    return page(request, "queue.html", items=items, item_error=item_error, waiting=waiting,
                approvals=approvals, approval_error=approval_error)


# -- the outside channel --------------------------------------------------------------------

@app.get("/threads", response_class=HTMLResponse)
def threads(request: Request, thread: str | None = None):
    messages = product.thread_messages(thread) if thread else []
    return page(request, "threads.html", threads=channel.threads(), thread=thread, messages=messages, notice=None)


@app.post("/threads/reply", response_class=HTMLResponse)
def thread_reply(request: Request, thread_id: str = Form(...), text: str = Form(...), sender: str = Form("outside")):
    notice = None
    try:
        reply = turns.outside_reply(thread_id, text, sender=(sender.strip() or "outside"))
        if reply is None:
            notice = "A turn waiting on this thread (wait_for_reply) took the message; on_outside_reply was not called."
        else:
            notice = f"The agent replied: {reply.text}" if reply.text else "The agent took the reply."
    except Exception as exc:
        notice = _agent_error(exc)
    return page(request, "threads.html", threads=channel.threads(), thread=thread_id,
                messages=product.thread_messages(thread_id), notice=notice)


# -- approvals -------------------------------------------------------------------------------

@app.get("/approvals", response_class=HTMLResponse)
def approvals(request: Request):
    return _approvals_page(request, None)


@app.post("/approvals", response_class=HTMLResponse)
def approvals_decide(request: Request, approval_id: str = Form(...), decision: str = Form(...), note: str = Form("")):
    try:
        reply = turns.decide_approval(approval_id, decision == "approve", note, session_id=_approval_session(approval_id))
        notice = f"Recorded: {decision}." + (f" The agent replied: {reply.text}" if reply and reply.text else "")
    except Exception as exc:
        notice = _agent_error(exc)
    return _approvals_page(request, notice)


def _approval_session(approval_id: str) -> str | None:
    """The console session a waiting approval came from, if pending_approvals() names it
    as `session_id`: the answer is traced, metered and resumed in that session."""
    try:
        items = turns.pending_approvals()
    except Exception:
        return None
    return next((str(i["session_id"]) for i in items if str(i.get("id")) == approval_id and i.get("session_id")), None)


def _approvals_page(request: Request, notice: str | None):
    items, error = [], None
    try:
        items = turns.pending_approvals()
    except Exception as exc:
        error = _agent_error(exc)
    return page(request, "approvals.html", items=items, error=error, notice=notice)


# -- traces -----------------------------------------------------------------------------------

@app.get("/traces", response_class=HTMLResponse)
def traces(request: Request):
    runs = []
    for prefix, folders in (("", records.arms()), (f"{records.FREE}/", records.arms(records.free_dir()))):
        for folder in folders:
            for r in records.read(folder):
                runs.append({k: r.get(k) for k in ("run_id", "task", "sweep", "outcome", "passed", "started",
                                                   "latency_s", "cost_usd")}
                            | {"tokens": (r.get("tokens") or {}).get("total"), "arm": prefix + folder.name,
                               "link": f"/traces/run/{prefix}{folder.name}/{r['run_id']}"})
    runs.sort(key=lambda r: str(r["started"]), reverse=True)
    sessions = sorted(({"id": p.stem, "lines": sum(1 for _ in p.open()), "modified": time.strftime(
        "%Y-%m-%d %H:%M", time.localtime(p.stat().st_mtime)), "first": _first_message(p)}
        for p in traces_dir().glob("*.jsonl")), key=lambda s: s["modified"], reverse=True)
    return page(request, "traces.html", runs=runs[:300], more=max(0, len(runs) - 300), sessions=sessions)


# A plain name and a colour group for each trace line type, for the trace page's timeline.
LINE_KINDS = {"operator": ("You", "user"), "reply": ("Reply", "agent"), "route": ("Route", "agent"),
              "model_call": ("Model call", "model"), "tool_call": ("Tool call", "tool"), "tool_use": ("Tool use", "tool"),
              "critique": ("Critique", "check"), "checkpoint": ("Checkpoint", "check"), "plan": ("Plan", "plan"),
              "plan_diff": ("Plan diff", "plan"), "bound": ("Bound", "meta"), "end": ("End", "end"),
              "error": ("Error", "bad"), "invalid_arguments": ("Invalid arguments", "bad"), "progress": ("Progress", "meta")}


def _summary(x: dict) -> str:
    """One readable line for a trace line; the full line stays under it."""
    t = x.get("type")
    if t in ("operator", "progress", "text"):
        return str(x.get("text", ""))
    if t == "reply":
        return str(x.get("text", ""))
    if t == "route":
        return f"{x.get('use_case')} → {x.get('path')} path ({', '.join(x.get('request_ids') or [])})"
    if t == "model_call":
        usage = x.get("usage") or {}
        tokens = (usage.get("input_tokens") or 0) + (usage.get("output_tokens") or 0)
        return f"{x.get('purpose') or 'model'} · {tokens} tokens · {x.get('latency_s')} s"
    if t == "tool_call":
        mark = "✗" if x.get("is_error") else "✓"
        return f"{mark} {x.get('name')} · {x.get('outcome') or ''} · {x.get('latency_s')} s"
    if t == "critique":
        return f"round {x.get('round')}: {x.get('verdict')}" + (f": {x.get('reason')}" if x.get("reason") else "")
    if t == "checkpoint":
        return f"{x.get('step_id')}: {'passed' if x.get('passed') else 'failed'} ({x.get('reason')})"
    if t == "plan":
        steps = (x.get("plan") or {}).get("steps") or []
        return f"version {x.get('version')}: {len(steps)} steps, {'accepted' if x.get('accepted') else 'rejected'}"
    if t == "plan_diff":
        return f"{x.get('step_id')}: {x.get('label')}"
    if t == "end":
        return f"{x.get('terminal_reason')}" + (f": {x.get('detail')}" if x.get("detail") else "")
    if t in ("run_start", "run_end", "session_start", "sandbox"):
        return ", ".join(f"{k} {x[k]}" for k in ("task", "arm", "sweep", "outcome", "seeded", "source") if x.get(k) is not None)
    return ""


def _first_message(path: Path) -> str:
    try:
        return next((str(x.get("text", "")) for x in read_trace(path) if x.get("type") == "operator"), "")[:120]
    except Exception:
        return ""


def _lines(path: Path) -> list[dict]:
    out = []
    for x in read_trace(path):
        rest = {k: v for k, v in x.items() if k not in ("at", "type", "session_id", "run_id")}
        label, kind = LINE_KINDS.get(x.get("type"), (str(x.get("type", "")).replace("_", " ").capitalize(), "meta"))
        try:
            summary = _summary(x)
        except Exception:
            summary = ""
        out.append({"at": str(x.get("at", ""))[11:23], "type": x.get("type"), "label": label, "kind": kind,
                    "summary": summary[:300], "detail": json.dumps(rest, default=str, indent=1)[:4000]})
    return out


@app.get("/traces/run/{arm}/{run_id}", response_class=HTMLResponse)
def trace_run(request: Request, arm: str, run_id: str):
    return _run_page(request, results_dir() / _safe(arm), run_id)


@app.get("/traces/run/_free/{arm}/{run_id}", response_class=HTMLResponse)
def trace_free_run(request: Request, arm: str, run_id: str):
    return _run_page(request, records.free_dir() / _safe(arm), run_id)


def _run_page(request: Request, folder: Path, run_id: str):
    record_path, trace_path = folder / f"{_safe(run_id)}.json", folder / f"{run_id}.trace.jsonl"
    if not record_path.exists():
        raise HTTPException(404, "no such run")
    record = json.loads(record_path.read_text())
    summary = {"task": record.get("task"), "arm": record.get("arm"), "sweep": record.get("sweep"),
               "passed": record.get("passed"), "outcome": record.get("outcome"), "end_reason": record.get("end_reason"),
               "tokens": (record.get("tokens") or {}).get("total"), "latency_s": record.get("latency_s"),
               "cost_usd": record.get("cost_usd"), "model": record.get("model"),
               "check": (record.get("check") or {}).get("reason"), "model_calls": record.get("model_calls"),
               "tool_calls": len(record.get("tool_calls") or [])}
    return page(request, "trace.html", title=f"Run {run_id}", record=json.dumps(record, indent=2), summary=summary,
                lines=_lines(trace_path) if trace_path.exists() else [])


@app.get("/traces/session/{session_id}", response_class=HTMLResponse)
def trace_session(request: Request, session_id: str):
    path = traces_dir() / f"{_safe(session_id)}.jsonl"
    if not path.exists():
        raise HTTPException(404, "no such session")
    return page(request, "trace.html", title=f"Session {session_id}", record=None, summary=None, lines=_lines(path),
                session_id=session_id)
