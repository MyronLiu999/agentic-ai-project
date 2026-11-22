"""Eleven real-process crash/restart cases with task checks and exact effects.

Each target names the last intended write, its request, and its occurrence for
that request. The MCP child kills both processes after the sandbox commit and
before its response; a fresh driver resumes and finishes the durable task script.
"""

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest

from tests.recovery_mcp import write_json
from tests.support import ScratchTest, check_run


def case(task, thread, *, tool="draft_report_email", commit="sandbox.pending:add",
         reports=1, pending=1, charts=1, sent=0, messages=0, answers=0):
    return {"task": "tasks/" + task + ".yaml",
            "target": {"tool": tool, "request_id": "REQ-" + thread, "occurrence": 1, "commit": commit},
            "expected": {"reports": reports, "pending": pending, "charts": charts,
                         "sent_drafts": sent, "agent_messages": messages, "outside_answers": answers}}


RECOVERY_TASKS = [
    case("standard_report_clean", "SYN-thread-1001"),
    case("out_of_scope_margins", "SYN-thread-1501", tool="draft_clarifying_question", reports=0, charts=0),
    case("messy_file_semicolon", "SYN-thread-1101"),
    case("compare_check_last_quarter", "SYN-thread-1201"),
    case("memory_subject_preference", "SYN-thread-1601"),
    case("batch_reports_two", "SYN-thread-1302", reports=2, pending=2, charts=2),
    case("outside_units", "SYN-thread-outside", tool="save_report", commit="sandbox.reports:save",
         sent=1, messages=1, answers=1),
    case("approval_send_report", "SYN-thread-1401", tool="send_report_email",
         commit="sandbox.email_packages:link_message", charts=0, sent=1, messages=1),
    case("approval_send_declined", "SYN-thread-1402", charts=0),
    case("escalation_conflicting_figure", "SYN-thread-1403"),
    case("sessions/long_campaign", "SYN-thread-long-4", reports=4, pending=4, charts=0),
]


def _child(*args, env):
    return subprocess.run([sys.executable, "-m", "tests.recovery_child", *args], env=env,
                          capture_output=True, text=True, timeout=120)


def _lines(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def _completed_identity(line):
    return (line["name"], json.dumps(line.get("input"), sort_keys=True))


class RecoveryTest(ScratchTest):
    def test_every_task_that_writes_survives_a_kill_during_its_last_write(self):
        from agent import checkpoints
        from harness import tasks
        from harness.paths import state_dir
        from tests.recovery_child import counts
        from tests.support import _trace_path

        evidence_path = Path(os.environ.get("RECOVERY_EVIDENCE") or
                             (Path(tempfile.mkdtemp(prefix="m2-recovery-")) / "evidence.json"))
        evidence = {"kind": "free synthetic real-MCP crash/restart matrix", "cases": []}
        selected = os.environ.get("RECOVERY_TASK")
        cases = [c for c in RECOVERY_TASKS if not selected or Path(c["task"]).stem == selected]
        self.assertTrue(cases, f"Unknown RECOVERY_TASK: {selected}")
        for spec in cases:
            with self.subTest(task=spec["task"]):
                task = tasks.load(Path(spec["task"]))
                task_id, run_id = task["id"], "recover-" + task["id"]
                progress = self.tmp / (task_id + ".script.json")
                row = {"task": task_id, "target": spec["target"], "expected": spec["expected"], "passed": False}
                evidence["cases"].append(row)
                try:
                    crashed = _child("crash", spec["task"], run_id, json.dumps(spec["target"]), str(progress),
                                     env=dict(os.environ))
                    row["crash_returncode"] = crashed.returncode
                    self.assertEqual(crashed.returncode, -signal.SIGKILL,
                                     f"The selected MCP commit did not kill the driver:\n{crashed.stdout}\n{crashed.stderr}")
                    row["before"] = json.loads(progress.with_suffix(".before.json").read_text())
                    self.assertTrue(all(value == 0 for value in row["before"].values()))
                    row["after_crash"] = counts(run_id)
                    boundary = json.loads(progress.with_suffix(".boundary.json").read_text())
                    row["boundary"] = boundary
                    self.assertNotEqual(boundary["server_pid"], boundary["driver_pid"])
                    self.assertEqual(boundary["tool"], spec["target"]["tool"])
                    self.assertEqual(boundary["context"]["request_id"], spec["target"]["request_id"])
                    self.assertEqual(boundary["occurrence"], spec["target"]["occurrence"])
                    self.assertEqual(row["after_crash"], spec["expected"], "Crash must follow the last intended effect")
                    self.assertIsNone(checkpoints.completed(run_id, boundary["context"]["key"]),
                                      "The selected write must not have reached registry journaling")
                    before_lines = _lines(_trace_path(run_id))
                    before_mcp = _lines(state_dir() / "mcp_calls.jsonl")
                    resumed = _child("resume", spec["task"], run_id, str(progress), env=dict(os.environ))
                    row["resume_returncode"] = resumed.returncode
                    self.assertEqual(resumed.returncode, 0, resumed.stderr[-6000:])
                    result = json.loads(resumed.stdout)
                    row["after_resume"] = counts(run_id)
                    row["check"] = check_run(spec["task"], run_id, replies=result["replies"])
                    self.assertTrue(result["complete"])
                    self.assertTrue(row["check"]["passed"], row["check"]["reason"])
                    self.assertEqual(row["after_resume"], spec["expected"], "Exactly one effect per intended write")
                    self.assertEqual(sum(r["function"] == "operator_turn" for r in result["replies"]),
                                     len(task["operator"]), "Every scripted operator turn must retain its reply")
                    script = json.loads(progress.read_text())
                    row["script"] = {"operator_index": script["operator_index"],
                                     "approval_index": script["approval_index"], "outside": script["outside"],
                                     "complete": script["complete"], "replies": script["replies"],
                                     "events": [{k: v for k, v in e.items() if k not in ("text", "reply")}
                                                for e in script["events"]]}
                    self.assertEqual(script["approval_index"], len(tasks.scripted_answers(task)))
                    self.assertEqual(sum(e["resumed"] for e in script["events"]), 1)
                    after_lines = _lines(_trace_path(run_id))[len(before_lines):]
                    row["recovered_reply_count"] = sum(l.get("type") == "reply" and l.get("crash_resume", False)
                                                       for l in after_lines)
                    self.assertEqual(row["recovered_reply_count"], 1)
                    self.assertTrue(any(l.get("type") == "resume" and l.get("event_kind") == "crash"
                                        for l in after_lines))
                    # Subsequent operator turns can deliberately read the same
                    # data. Only the resumed interrupted execution is replay.
                    next_operator = next((i for i, l in enumerate(after_lines) if l.get("type") == "operator"),
                                         len(after_lines))
                    replay_lines = after_lines[:next_operator]
                    completed = {_completed_identity(l) for l in before_lines
                                 if l.get("type") == "tool_call" and l.get("outcome") == "ok"}
                    repeated = [_completed_identity(l) for l in replay_lines
                                if l.get("type") == "tool_call" and l.get("outcome") == "ok"
                                and _completed_identity(l) in completed]
                    row["repeated_completed_calls"] = repeated
                    self.assertEqual(repeated, [], "Resume repeated a call completed before the crash")
                    done_keys = {c["key"] for c in before_mcp if c.get("key") and c.get("outcome") == "ok"}
                    after_mcp = _lines(state_dir() / "mcp_calls.jsonl")[len(before_mcp):]
                    row["repeated_completed_mcp_writes"] = [c["key"] for c in after_mcp
                                                             if c.get("key") in done_keys]
                    self.assertEqual(row["repeated_completed_mcp_writes"], [],
                                     "A completed write physically reached the MCP server again")
                    row["resume_calls"] = [{"name": l["name"], "outcome": l.get("outcome")}
                                           for l in replay_lines if l.get("type") == "tool_call"]
                    if task_id == "escalation_conflicting_figure":
                        from checks.common import report_email_problems
                        from types import SimpleNamespace
                        problems, _ = report_email_problems(SimpleNamespace(run_id=run_id, state_dir=state_dir()),
                                                            task["input"])
                        self.assertEqual(problems, [], "The correction must match the database revenue")
                        self.assertEqual(row["check"]["measures"]["escalations"], 0)
                        self.assertIsNone((checkpoints.load(run_id) or {}).get("held"))
                    if task_id == "outside_units":
                        self.assertEqual(script["outside"][0]["answered"], 1)
                    if task_id.startswith("approval_send_"):
                        measures = row["check"]["measures"]
                        self.assertEqual(measures["approvals_asked"], 1)
                        self.assertEqual(measures["approvals_approved"], int(task_id == "approval_send_report"))
                        self.assertEqual(measures["approvals_rejected"], int(task_id == "approval_send_declined"))
                    row["passed"] = True
                except Exception as exc:
                    row["error"] = str(exc)
                    raise
                finally:
                    write_json(evidence_path, evidence)
        if os.environ.get("RECOVERY_TABLE"):
            print(f"Recovery evidence: {evidence_path}")
            for row in evidence["cases"]:
                print(f"| {row['task']} | {row.get('before')} | {row.get('after_crash')} | "
                      f"{row.get('after_resume')} | passed={row['passed']} |")


if __name__ == "__main__":
    unittest.main()
