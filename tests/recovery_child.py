"""A child process for tests/test_recovery.py (owner: claudea). Not a test itself.

    python -m tests.recovery_child crash  <task file> <run id> <module:function> <snapshot file>
    python -m tests.recovery_child resume <task file> <run id>

crash   opens the run fresh (seeds the test task), writes the sandbox's counts before the run to the snapshot
        file, then plays the task's first operator turn with `module:function` (the sandbox function the task's
        last write commits through, such as sandbox.pending:add) wrapped so that, right after the sandbox commits
        the write and before the registry records it, the process kills itself with SIGKILL, as Assignment 4's
        --die-during-step did. Exits 3 if the kill never fired.
resume  opens the same run ID in a new process with the sandbox kept, finds the run the crash stopped
        (agent.runs.crashed) and resumes it (agent.runs.resume, {"kind": "crash"}), as the operator's next turn would.
"""

from __future__ import annotations

import importlib
import json
import os
import signal
import sys

MODEL = "tests.fixtures.agent_milestone_model:MilestoneModel"


def counts(run_id: str) -> dict:
    """This run's effects in the sandbox: rows stamped with its run ID."""
    from sandbox import db
    with db.connect() as conn:
        return {table: conn.execute(f"SELECT COUNT(*) FROM {table} WHERE stamp = ?", (run_id,)).fetchone()[0]
                for table in ("reports", "pending", "charts")}


def main(argv: list[str]) -> int:
    from tests.support import fixed_run

    phase, task_file, run_id = argv[:3]
    with fixed_run(task_file, run_id, backend=MODEL, fresh=(phase == "crash")) as run:
        if phase == "crash":
            die_on, snapshot = argv[3], argv[4]
            with open(snapshot, "w") as fh:
                json.dump(counts(run_id), fh)
            module_name, function = die_on.split(":")
            module = importlib.import_module(module_name)
            original = getattr(module, function)

            def commit_then_die(*args, **kwargs):
                original(*args, **kwargs)                # the sandbox commits the write
                os.kill(os.getpid(), signal.SIGKILL)     # before the registry records it

            setattr(module, function, commit_then_die)
            from harness import turns
            turns.operator_turn(run_id, run.task["operator"][0])
            return 3
        from agent import runs
        stopped = runs.crashed(run_id)
        reply = runs.resume(stopped[0] if stopped else run_id, {"kind": "crash"})
        print(json.dumps({"crashed": stopped, "reply": reply.text}))
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
