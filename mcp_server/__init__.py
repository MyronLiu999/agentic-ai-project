"""The project's MCP server (Milestone 2, Part 1 task 3; owner: myron, M1).

The tools of agent/tools.py, served over MCP by the official Python SDK (`mcp`, see requirements.txt) on the
2026-07-28 revision, the stateless one: every request carries its own envelope in `params._meta`, there is no
`initialize` handshake and no session, and the server keeps nothing between requests.

    mcp_server/server.py   the server: tools/list (a fixed order) and tools/call
    mcp_server/client.py   what the registry uses: it starts the server as a child process of its own process
                           the first time a tool is called, and sends each call over stdio
    python -m mcp_server   runs the server on stdin/stdout (the registry does this; nobody needs to)

The registry (agent/registry.py) stays in our code and in front of every call: its validation, its keys, its
hook and its call record hold for every call before the request reaches the server (Lecture 3, slide 47).

Every call carries the IDs it needs, in `_meta["agentic-ai-project/context"]`, written by the registry and
never seen by the model: the request it is bound to, the run or console session that stamps its writes, the
state folder of that run's sandbox, and, for a write, its key. Every result returns the IDs the next call
needs (request_id, thread_id, report_id, pending_id, chart_id, ...), as names that survive compaction.
The sandbox behind the server accepts each key once (UNIQUE key columns; sandbox/pending.py, reports.py,
charts.py), so a write retried under its key leaves one effect.

Not used: Roots, Sampling, Logging (the revision deprecated them) and server-to-client requests (the
revision forbids them); nothing a call needs is kept in a connection.
"""

PROTOCOL_VERSION = "2026-07-28"
CONTEXT_KEY = "agentic-ai-project/context"
SERVER_NAME = "agentic-ai-project-tools"
