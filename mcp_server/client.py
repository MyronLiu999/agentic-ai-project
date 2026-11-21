"""The registry's side of the MCP server (Milestone 2; owner: myron, M1).

The registry's process starts the server itself (`python -m mcp_server`) as a child, the first time a tool
is called, so `make app` and run.py need nothing more; a server that died is started again on the next call.
Every request is a 2026-07-28 request: its envelope (protocol version, client capabilities, client info) is
in its own `_meta`, with no `initialize` and no session, so a fresh server can answer any request.

    remote(name, request_id, writes) -> fn     a ToolSpec's fn whose call reaches the server
    list_tools() -> list[dict]                 tools/list, as the server sends it

How each outcome reaches the registry (agent/registry.py routes it as in Milestone 1):
    a result                       -> the tool's output
    isError, class transient       -> TransientToolError       (the registry retries it, bounded)
    isError, class ambiguous       -> AmbiguousToolError       (the write may have happened: three exits)
    isError, class permanent       -> ValueError               (the model repairs the call)
    isError, class execution       -> RuntimeError             (no usable result)
    a JSON-RPC error               -> ProtocolToolError        (nothing ran)
    a broken stream or no answer   -> a read: TransientToolError; a write: AmbiguousToolError, since the
                                      request in flight is lost and its effect cannot be told (slide 46)
"""

from __future__ import annotations

import atexit
import itertools
import json
import os
import queue
import subprocess
import sys
import threading

from mcp_types import CLIENT_CAPABILITIES_META_KEY, CLIENT_INFO_META_KEY, PROTOCOL_VERSION_META_KEY

from mcp_server import CONTEXT_KEY, PROTOCOL_VERSION

TIMEOUT_S = float(os.environ.get("MCP_CALL_TIMEOUT_S") or 60)
ENVELOPE = {PROTOCOL_VERSION_META_KEY: PROTOCOL_VERSION, CLIENT_CAPABILITIES_META_KEY: {},
            CLIENT_INFO_META_KEY: {"name": "agentic-ai-project-registry", "version": "m2"}}


class BrokenStream(RuntimeError):
    """The server died, closed its stream or did not answer in time: the request in flight is lost."""


class _Server:
    """One child server per process, used by one call at a time (calls are short and local)."""

    def __init__(self):
        self._proc: subprocess.Popen | None = None
        self._lines: queue.Queue | None = None
        self._lock = threading.RLock()
        self._ids = itertools.count(1)
        self.started = 0                      # how many times this process started a server

    def _alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def _start(self) -> None:
        from harness import ROOT
        env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
        log = os.environ.get("MCP_SERVER_LOG")
        stderr = open(log, "ab") if log else subprocess.DEVNULL
        self._proc = subprocess.Popen([sys.executable, "-m", "mcp_server"], cwd=str(ROOT), env=env,
                                      stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr)
        if log:
            stderr.close()
        lines: queue.Queue = queue.Queue()
        stdout = self._proc.stdout

        def read():
            for raw in iter(stdout.readline, b""):
                lines.put(raw)
            lines.put(None)                    # end of stream

        threading.Thread(target=read, daemon=True, name="mcp-server-reader").start()
        self._lines = lines
        self.started += 1

    def stop(self) -> None:
        with self._lock:
            if self._proc is not None:
                try:
                    self._proc.kill()
                    self._proc.wait(timeout=5)
                except Exception:
                    pass
                for stream in (self._proc.stdin, self._proc.stdout):
                    try:
                        stream.close()
                    except Exception:
                        pass
            self._proc, self._lines = None, None

    def request(self, method: str, params: dict) -> dict:
        """Send one JSON-RPC request and return its whole response (result or error)."""
        with self._lock:
            if not self._alive():
                self._start()
            request_id = next(self._ids)
            frame = {"jsonrpc": "2.0", "id": request_id, "method": method,
                     "params": {**params, "_meta": {**ENVELOPE, **(params.get("_meta") or {})}}}
            try:
                self._proc.stdin.write((json.dumps(frame, ensure_ascii=False) + "\n").encode("utf-8"))
                self._proc.stdin.flush()
            except (BrokenPipeError, OSError) as exc:
                self.stop()
                raise BrokenStream(f"the server's stream is closed: {exc}") from exc
            while True:
                try:
                    raw = self._lines.get(timeout=TIMEOUT_S)
                except queue.Empty:
                    self.stop()
                    raise BrokenStream(f"no answer within {TIMEOUT_S:.0f} s") from None
                if raw is None:
                    self.stop()
                    raise BrokenStream("the server closed its stream")
                try:
                    message = json.loads(raw.decode("utf-8"))
                except ValueError:
                    continue                    # not a protocol frame
                if message.get("id") == request_id:
                    return message
                # a notification, or an answer to a request this process gave up on: not ours


_server = _Server()
atexit.register(_server.stop)


def server() -> _Server:
    return _server


def list_tools() -> list[dict]:
    response = _server.request("tools/list", {})
    if "error" in response:
        from agent.registry import ProtocolToolError
        raise ProtocolToolError(json.dumps(response["error"]))
    return response["result"]["tools"]


def _context(request_id: str | None, key: str | None) -> dict:
    from harness import runtime
    from harness.paths import state_dir
    run = runtime.current_run()
    return {"state_dir": str(state_dir()), "run_id": run.run_id if run else None,
            "session_id": runtime.current_session(), "request_id": request_id, "key": key}


def call(name: str, arguments: dict, *, request_id: str | None, key: str | None = None,
         writes: bool = False) -> dict:
    """One tools/call; returns the tool's output or raises the exception the registry routes on."""
    from agent.registry import AmbiguousToolError, ProtocolToolError, TransientToolError
    params = {"name": name, "arguments": arguments, "_meta": {CONTEXT_KEY: _context(request_id, key)}}
    try:
        response = _server.request("tools/call", params)
    except BrokenStream as exc:
        if writes:
            raise AmbiguousToolError(f"the request in flight was lost ({exc}); the write may have happened") from exc
        raise TransientToolError(f"the request in flight was lost ({exc})") from exc
    if "error" in response:
        error = response["error"] or {}
        raise ProtocolToolError(f"JSON-RPC {error.get('code')}: {error.get('message')}")
    result = response.get("result") or {}
    content = result.get("structuredContent")
    if result.get("isError"):
        failure = (content or {}).get("error") or {}
        message = str(failure.get("message") or "the tool failed")
        kind = failure.get("class")
        if kind == "transient":
            raise TransientToolError(message)
        if kind == "ambiguous":
            raise AmbiguousToolError(message)
        if kind == "permanent":
            raise ValueError(message)
        raise RuntimeError(f"{failure.get('exception') or 'error'}: {message}")
    if content is None:
        texts = [c.get("text", "") for c in result.get("content") or [] if c.get("type") == "text"]
        content = json.loads(texts[0]) if texts else {}
    return content


def remote(name: str, request_id: str | None, *, writes: bool = False):
    """A ToolSpec fn: the registry calls it with the validated arguments (and `key` for a write)."""
    def fn(**kwargs):
        key = kwargs.pop("key", None) if writes else None
        return call(name, kwargs, request_id=request_id, key=key, writes=writes)
    fn.__name__ = f"mcp:{name}"
    return fn
