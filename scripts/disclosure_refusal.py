"""Record one real, logged hook refusal: a send whose pending text lacks the disclosure line, called through the
real registry (MCP server, policy hook). Fake model; no key. Run it with PROJECT_STATE_DIR, PROJECT_TRACES_DIR and
PROJECT_RESULTS_DIR pointing at a scratch folder; the trace lands in <traces>/disclosure-refusal-20261122.trace.jsonl."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.support import fixed_run
from agent import tools, disclosure
from sandbox import pending
import channel

RUN = "disclosure-refusal-20261122"
with fixed_run("tasks/standard_report_clean.yaml", RUN):
    bare, _ = pending.add("report_email", "REQ-SYN-thread-1001", "SYN-thread-1001", "contact@acme.example",
                          "Your 2026Q3 sales report", "Your 2026Q3 revenue was 51,264.85.", key="demo-bare")
    before = len(channel.thread("SYN-thread-1001")) if hasattr(channel, "thread") else None
    reg = tools.build("REQ-SYN-thread-1001", "standard_report")
    result = reg.call("send_report_email", {"pending_id": bare["id"]}, "model")
    after = len(channel.thread("SYN-thread-1001")) if hasattr(channel, "thread") else None
    print(json.dumps({"ok": result["ok"], "error": result.get("error"), "has_line": disclosure.has_line(bare["body"]) if "body" in bare else None,
                      "thread_before": before, "thread_after": after}, default=str)[:600])
