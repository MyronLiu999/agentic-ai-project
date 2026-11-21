"""A child process for tests that need each session in its own process (owner: claudea). Not a test itself.

    python -m tests.session_child <task file> <run id> <fresh 0|1> <operator text> [<request json to add>]

Opens the run (fresh=1 seeds the test task; fresh=0 keeps the sandbox the last process left, as `make serve`
does), optionally adds one more distributor request (a later day's mail), plays one operator turn through
harness.turns, and prints the reply as JSON.
"""

from __future__ import annotations

import json
import sys

MODEL = "tests.fixtures.agent_milestone_model:MilestoneModel"


def main(argv: list[str]) -> int:
    from tests.support import fixed_run

    task_file, run_id, fresh, text = argv[:4]
    with fixed_run(task_file, run_id, backend=MODEL, fresh=fresh == "1"):
        if len(argv) > 4:
            import channel
            from sandbox import seed
            with channel.seeding():
                seed._ingest(json.loads(argv[4]))
        from harness import turns
        reply = turns.operator_turn(run_id, text)
        print(json.dumps(reply.as_dict()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
