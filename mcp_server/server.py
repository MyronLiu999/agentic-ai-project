"""The MCP server: agent/tools.py's tools over stdio, stateless (Milestone 2; owner: myron, M1).

    tools/list   every tool in the catalogue's fixed order (agent.tools.specs), the same on every request
    tools/call   one tool, with the context the registry put in `_meta`; nothing survives the request

Two classes of error (Lecture 3, slide 34):
  - an execution error (the tool ran and failed) comes back as a result with isError: true, its
    structuredContent naming the failure class the registry routes on: transient (safe to retry),
    ambiguous (a write may have happened: the three exits), permanent (fix the arguments) or execution;
  - a protocol error (an unknown tool, a request without the registry's context) is a JSON-RPC error,
    raised as MCPError, and nothing runs.

Each call runs inside the caller's sandbox: the state folder named in its context, and a run scope with
that run's ID (or the console session's), so its writes and channel messages are stamped as the caller's
own. The server opens nothing it keeps: every sandbox module opens and closes its own connection.
"""

from __future__ import annotations

import contextlib
import inspect
import json
import os
from types import SimpleNamespace

import anyio
import mcp.server.stdio
import mcp_types as types
from mcp.server.lowlevel.server import Server
from mcp.shared.exceptions import MCPError

from mcp_server import CONTEXT_KEY, SERVER_NAME

INVALID_PARAMS = -32602
IRREVERSIBLE = ("send_report_email", "ask_stranger")     # nothing undoes them (agent/compensations.py)
CALL_LOG = "mcp_calls.jsonl"                             # one line per call, in the caller's state folder


class _NullTrace:
    """The registry records every call in the caller's trace; the server writes none of its own."""

    def __getattr__(self, _name):
        return lambda *args, **kwargs: None


def _catalogue(request_id=None):
    from agent import tools
    return tools.specs(request_id)


def tool_list() -> list[types.Tool]:
    """The catalogue as MCP tools, in the registry's fixed order. The annotations are hints the server
    states about itself; the policy never reads them (Part 2, task 1)."""
    out = []
    for spec in _catalogue():
        out.append(types.Tool(
            name=spec.name, description=spec.description, inputSchema=spec.input_schema,
            annotations=types.ToolAnnotations(readOnlyHint=not spec.writes,
                                              destructiveHint=spec.name in IRREVERSIBLE,
                                              idempotentHint=spec.writes or None),
        ))
    return out


async def list_tools(ctx, params) -> types.ListToolsResult:
    return types.ListToolsResult(tools=tool_list())


def _context(params) -> dict:
    meta = params.meta or {}
    context = meta.get(CONTEXT_KEY) if isinstance(meta, dict) else None
    if not isinstance(context, dict) or not context.get("state_dir"):
        raise MCPError(INVALID_PARAMS, f"tools/call needs the registry's context in _meta[{CONTEXT_KEY!r}]")
    return context


@contextlib.contextmanager
def _caller_scope(context: dict):
    """Run as the caller: its sandbox folder, and its run (or console session) for stamps."""
    from harness import runtime
    from harness.paths import STATE_ENV

    previous = os.environ.get(STATE_ENV)
    os.environ[STATE_ENV] = str(context["state_dir"])
    try:
        with contextlib.ExitStack() as stack:
            if context.get("run_id"):
                scope = SimpleNamespace(run_id=str(context["run_id"]), switches={}, trace=_NullTrace(),
                                        add_wait=lambda s: None, add_throttled=lambda s: None)
                stack.enter_context(runtime.run_scope(scope))
            stack.enter_context(runtime.in_session(context.get("session_id")))
            yield
    finally:
        if previous is None:
            os.environ.pop(STATE_ENV, None)
        else:
            os.environ[STATE_ENV] = previous


def _failure_class(spec, exc: Exception) -> str:
    from agent.registry import AmbiguousToolError, TransientToolError
    if isinstance(exc, AmbiguousToolError):
        return "ambiguous"
    transient = isinstance(exc, TransientToolError)
    if not transient and spec.retryable is not None:
        try:
            transient = bool(spec.retryable(exc))
        except Exception:
            transient = False
    if transient:
        return "transient"
    if isinstance(exc, (ValueError, KeyError, FileNotFoundError)):
        return "permanent"
    return "execution"


def _log_call(name: str, context: dict, outcome: str) -> None:
    """Evidence that the call reached the server, in the caller's own sandbox folder (not server state)."""
    from harness.paths import state_dir
    from harness.trace import now
    line = {"at": now(), "tool": name, "request_id": context.get("request_id"), "key": context.get("key"),
            "run_id": context.get("run_id"), "session_id": context.get("session_id"), "outcome": outcome}
    with (state_dir() / CALL_LOG).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line, sort_keys=True) + "\n")


def call(name: str, arguments: dict, context: dict) -> types.CallToolResult:
    """One tools/call, synchronously (the handler and the tests use it)."""
    with _caller_scope(context):
        catalogue = {spec.name: spec for spec in _catalogue(context.get("request_id"))}
        spec = catalogue.get(name)
        if spec is None:
            raise MCPError(INVALID_PARAMS, f"unknown tool {name!r}")
        kwargs = dict(arguments or {})
        if spec.writes:
            if not context.get("key"):
                raise MCPError(INVALID_PARAMS, f"{name} is a write: its call needs the registry's key")
            kwargs["key"] = str(context["key"])
        try:
            inspect.signature(spec.fn).bind(**kwargs)
        except TypeError as exc:     # arguments the tool does not take: the request is malformed, nothing runs
            _log_call(name, context, "protocol_error")
            raise MCPError(INVALID_PARAMS, f"{name}: {exc}") from exc
        try:
            output = spec.fn(**kwargs)
        except Exception as exc:
            failure = _failure_class(spec, exc)
            _log_call(name, context, failure)
            error = {"class": failure, "exception": type(exc).__name__, "message": str(exc)[:300]}
            return types.CallToolResult(content=[types.TextContent(type="text", text=json.dumps({"error": error}))],
                                        structuredContent={"error": error}, isError=True)
        _log_call(name, context, "ok")
        text = json.dumps(output, sort_keys=True, default=str)
        return types.CallToolResult(content=[types.TextContent(type="text", text=text)],
                                    structuredContent=output, isError=False)


async def call_tool(ctx, params) -> types.CallToolResult:
    return call(params.name, params.arguments or {}, _context(params))


def build_server() -> Server:
    return Server(SERVER_NAME, on_list_tools=list_tools, on_call_tool=call_tool)


def main() -> None:
    server = build_server()

    async def serve():
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    anyio.run(serve)
