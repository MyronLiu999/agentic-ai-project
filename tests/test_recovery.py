"""The recovery test (Milestone 2, Part 1 task 2; owner: claudea, C5).

On every test task that makes a write, kill the process with SIGKILL during its last write, after the sandbox
commits it and before the system records it; resume in a new process under the same run ID. Then: the task's
check passes, the sandbox holds one effect per intended write, and the resume repeated no completed call.

RECOVERY_TASKS is the list. To cover a new task that writes, add one line: its file, and the sandbox function its
last write commits through. (abraham adds his and myron's new tasks here at the merge, T2c, with their
before / after crash / after resume rows in M2.md.)
"""

import json
import os
import subprocess
import sys
import unittest

from tests.support import ScratchTest, check_run

RECOVERY_TASKS = [
    # (task file, the sandbox function the task's last write commits through)
    ("tasks/standard_report_clean.yaml", "sandbox.pending:add"),        # workflow: 6-email is the last write
    ("tasks/out_of_scope_margins.yaml", "sandbox.pending:add"),         # workflow: the one decline
    ("tasks/messy_file_semicolon.yaml", "sandbox.pending:add"),         # agent loop: the email draft
    ("tasks/compare_check_last_quarter.yaml", "sandbox.pending:add"),   # agent loop: the email draft
    ("tasks/memory_subject_preference.yaml", "sandbox.pending:add"),    # workflow, a later session's task
    # MERGE-CHECK (abraham): tasks/batch_reports_two.yaml runs on agent/plan.py, which saves no checkpoint yet;
    # add it here once plan.py calls checkpoints.before_step / start (PLAN_M2.md 3.3).
]

# One effect per intended write: what each task's run should leave, in rows stamped with its run ID.
EXPECTED = {
    "standard_report_clean": {"reports": 1, "pending": 1, "charts": 1},
    "out_of_scope_margins": {"reports": 0, "pending": 1, "charts": 0},
    "messy_file_semicolon": {"pending": 1, "reports": 1},
    "compare_check_last_quarter": {"pending": 1, "reports": 1},
    "memory_subject_preference": {"reports": 1, "pending": 1, "charts": 1},
}


def _child(*args, env):
    return subprocess.run([sys.executable, "-m", "tests.recovery_child", *args], env=env, capture_output=True,
                          text=True, timeout=120)


class RecoveryTest(ScratchTest):
    def _crash_and_resume(self, task_file, die_on):
        from harness import tasks
        from tests.recovery_child import counts

        task_id = tasks.read(task_file)["id"] if hasattr(tasks, "read") else os.path.basename(task_file)[:-5]
        run_id = f"recover-{task_id}"
        snapshot = str(self.tmp / f"{task_id}.before.json")
        env = dict(os.environ)

        crashed = _child("crash", task_file, run_id, die_on, snapshot, env=env)
        self.assertEqual(crashed.returncode, -9, f"the kill never fired:\n{crashed.stdout}\n{crashed.stderr}")
        with open(snapshot) as fh:
            before = json.load(fh)
        after_crash = counts(run_id)

        resumed = _child("resume", task_file, run_id, env=env)
        self.assertEqual(resumed.returncode, 0, resumed.stderr[-2000:])
        after_resume = counts(run_id)
        return task_id, run_id, before, after_crash, after_resume, resumed

    def test_every_task_that_writes_survives_a_kill_during_its_last_write(self):
        from tests.support import _trace_path
        rows = []
        for task_file, die_on in RECOVERY_TASKS:
            with self.subTest(task=task_file):
                task_id, run_id, before, after_crash, after_resume, resumed = self._crash_and_resume(task_file, die_on)
                rows.append((task_id, before, after_crash, after_resume))

                result = check_run(task_file, run_id)
                self.assertTrue(result["passed"], result["reason"])

                for table, n in EXPECTED[task_id].items():
                    self.assertEqual(after_resume[table], n, f"{table}: one effect per intended write")
                self.assertEqual(after_crash["pending"], 1, "the crash came after the sandbox committed the write")

                with open(_trace_path(run_id)) as fh:
                    lines = [json.loads(l) for l in fh if l.strip()]
                resume_at = next(i for i, l in enumerate(lines) if l.get("type") == "resume")
                done_before = {(l["name"], json.dumps(l.get("input"), sort_keys=True))
                               for l in lines[:resume_at] if l.get("type") == "tool_call" and l.get("outcome") == "ok"}
                again = [(l["name"], json.dumps(l.get("input"), sort_keys=True))
                         for l in lines[resume_at:] if l.get("type") == "tool_call" and l.get("outcome") == "ok"]
                self.assertEqual([c for c in again if c in done_before], [], "the resume repeated a completed call")
                if os.environ.get("RECOVERY_TABLE"):
                    after = [(l["name"], l.get("outcome")) for l in lines[resume_at:] if l.get("type") == "tool_call"]
                    hits = [l.get("type") for l in lines[resume_at:] if l.get("type") in ("journal_hit",)]
                    print(f"| {task_id} | {before} | {after_crash} | {after_resume} | resume calls: {after} | "
                          f"{json.loads(resumed.stdout)} |")


if __name__ == "__main__":
    unittest.main()
