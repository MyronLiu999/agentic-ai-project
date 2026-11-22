"""Real MCP server with a test-only crash at one selected committed sandbox write.

The driver substitutes this module only in its child-process launcher. The normal
server, transport, catalogue, policy, sandbox, and registry remain in use.
"""

from __future__ import annotations

import importlib
import json
import os
import signal
from pathlib import Path


def write_json(path, value):
    """Replace the evidence file only after its contents have reached disk."""
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def main():
    from mcp_server import server

    target = json.loads(os.environ["RECOVERY_TARGET"])
    driver_pid = int(os.environ["RECOVERY_DRIVER_PID"])
    module_name, function = target["commit"].split(":")
    module = importlib.import_module(module_name)
    commit, call = getattr(module, function), server.call
    active, occurrences = {}, 0

    def selected_call(name, arguments, context):
        nonlocal occurrences
        matches = name == target["tool"] and context.get("request_id") == target["request_id"]
        if matches:
            occurrences += 1
        active.clear()
        if matches and occurrences == target["occurrence"]:
            active.update(tool=name, arguments=arguments, context=context, occurrence=occurrences)
        try:
            return call(name, arguments, context)
        finally:
            active.clear()

    def commit_then_kill(*args, **kwargs):
        result = commit(*args, **kwargs)
        if active:
            # A marker is written only after the real transaction has committed.
            # Killing the driver first prevents its broken-stream handling from
            # turning this into a live ambiguous-response test.
            write_json(os.environ["RECOVERY_BOUNDARY"], {
                **active, "commit": target["commit"], "committed_result": result,
                "server_pid": os.getpid(), "driver_pid": driver_pid,
                "boundary": "sandbox committed; MCP response and registry journal absent",
            })
            os.kill(driver_pid, signal.SIGKILL)
            os.kill(os.getpid(), signal.SIGKILL)
        return result

    server.call = selected_call
    setattr(module, function, commit_then_kill)
    server.main()


if __name__ == "__main__":
    main()
