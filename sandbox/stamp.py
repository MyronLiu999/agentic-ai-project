"""Who made a write: the run's ID in a run.py run, the console session's ID in the app,
and "manual" for a write made by hand on a product page."""

from __future__ import annotations

from harness import runtime


def current() -> str:
    run = runtime.current_run()
    return run.run_id if run else (runtime.current_session() or "manual")
