"""Every number our tables and the ledger give that the summarizer does not (owner: claudea).

    python experiments/analysis/analyze.py results/baseline
    python experiments/analysis/analyze.py results/arm-a results/arm-b
    python experiments/analysis/analyze.py results/arm-agent results/arm-workflow --agent arm-agent --workflow arm-workflow
    python experiments/analysis/analyze.py results/baseline --json

Read from the committed run records (results/<arm>/<run_id>.json) and the traces beside them, nothing else.
Per arm:

  runs, passes, per task (passed of sweeps), and runs per sweep
  turn latency       median and slowest of every turn_latency_s (one operator_turn each)
  tokens, cost       mean per run, and mean cost per task
  sequences          distinct tool-call sequences (tool names in order), per task and in all
  repeats            runs with an exact repeated call (tool + arguments hashed from the record's tool_calls),
                     and the repeat_call events the detector wrote
  false finishes     runs that ended `done` whose check failed
  plan               plan_diff labels (executed, skipped, out_of_order, extra), plans written, revisions
                     (plan versions after the first), plan_rejected and replan_bound ends, off-plan refusals,
                     checkpoints failed
  critique           rounds (critique events), rounds per run, drafts held (critique_held ends), misses
                     (a run whose critique passed a draft and whose check then failed)
  routing            route events, and misroutes: a route whose use_case differs from the task file's use_case
  bound              runs ended at step_limit, wall_clock or agent_budget
  boundary           tool calls returned as errors, and those rejected at the registry's boundary
                     (error kind "protocol")
  measures           the sum of every count the checks returned

Across two arms (--agent A --workflow B, on the tasks both ran): m, the agent arm's mean cost per run over
the workflow arm's, and f, the share of those tasks the agent passed in at least two of three sweeps and
the workflow in at most one (Part 4; Assignment 1, Part C).

Free runs (results/_free/) are tests, not evidence: name them only to try the script.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

UNFINISHED = ("quota", "rate_limited", "not_built")
BOUND_ENDS = ("step_limit", "wall_clock", "agent_budget")
PLAN_LABELS = ("executed", "skipped", "out_of_order", "extra")
# Older Registry traces retain error_type even when output is only a summary.
# Match Registry's public kind mapping without importing executable agent code.
LEGACY_ERROR_KINDS = {
    "unknown_tool": "protocol", "invalid_caller": "protocol", "caller_denied": "protocol",
    "invalid_arguments": "protocol", "hook_denied": "protocol", "invalid_result": "protocol",
    "transient_failure": "transient", "permanent_failure": "permanent",
    "ambiguous_write": "permanent", "execution_failure": "permanent",
}


def load_arm(folder: Path) -> list[dict]:
    """The arm's finished records, each with its trace lines under `_trace`."""
    out = []
    for path in sorted(Path(folder).glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict) or "run_id" not in record or record.get("outcome") in UNFINISHED:
            continue
        trace = path.with_name(f"{record['run_id']}.trace.jsonl")
        record["_trace"] = _read_trace(trace) if trace.exists() else []
        out.append(record)
    return sorted(out, key=lambda r: (str(r.get("started", "")), r["run_id"]))


def _read_trace(path: Path) -> list[dict]:
    lines = []
    for text in path.read_text(encoding="utf-8").splitlines():
        try:
            lines.append(json.loads(text))
        except json.JSONDecodeError:
            pass
    return lines


def _of(record: dict, kind: str) -> list[dict]:
    return [x for x in record["_trace"] if x.get("type") == kind]


def call_hash(call: dict) -> str:
    return hashlib.sha256(json.dumps([call.get("name"), call.get("input") or {}], sort_keys=True,
                                     default=str).encode()).hexdigest()[:16]


def _error_kind(call: dict) -> str | None:
    """Prefer structured error data; recover legacy summaries from metadata.

    Error prose is never classification evidence. Unknown failures still count
    as tool errors, but cannot establish a protocol/boundary rejection.
    """
    if not call.get("is_error"):
        return None
    out = call.get("output")
    if isinstance(out, str):
        try:
            out = json.loads(out)
        except json.JSONDecodeError:
            out = None
    err = {}
    if isinstance(out, dict):
        err = out.get("error") if isinstance(out.get("error"), dict) else out
        if err.get("kind"):
            return str(err["kind"])
    error_type = err.get("type") or call.get("error_type")
    return LEGACY_ERROR_KINDS.get(error_type, "error") if isinstance(error_type, str) else "error"


_use_cases: dict[str, str | None] = {}


def task_use_case(record: dict) -> str | None:
    """The use case the task file names (use_case:), the route's right answer."""
    file = record.get("task_file")
    if not file:
        return None
    if file not in _use_cases:
        import yaml
        path = Path(file) if Path(file).is_absolute() else ROOT / file
        try:
            _use_cases[file] = (yaml.safe_load(path.read_text()) or {}).get("use_case")
        except (OSError, yaml.YAMLError):
            _use_cases[file] = None
    return _use_cases[file]


def _median(xs):
    return statistics.median(xs) if xs else None


def analyze_arm(folder: Path) -> dict:
    runs = load_arm(folder)
    # the latest finished run of each (task, sweep), as the summarizer counts them
    by_pair = {}
    for r in runs:
        by_pair[(r["task"], r["sweep"])] = r
    counted = list(by_pair.values())
    tasks = sorted({r["task"] for r in counted})
    sweeps = sorted({r["sweep"] for r in counted})

    turns = [t for r in counted for t in r.get("turn_latency_s") or []]
    sequences = defaultdict(set)
    repeat_runs, repeat_events = 0, 0
    plan = Counter()
    critique = {"rounds": 0, "runs_with_critique": 0, "held": 0, "misses": 0, "verdicts": Counter()}
    routing = {"routes": 0, "misroutes": 0, "misrouted_runs": []}
    bound = Counter()
    boundary = {"tool_errors": 0, "boundary_rejections": 0}
    measures = Counter()
    false_finishes, per_run = [], []

    for r in counted:
        calls = r.get("tool_calls") or []
        seq = tuple(c.get("name") for c in calls)
        sequences[r["task"]].add(seq)
        hashes = Counter(call_hash(c) for c in calls)
        repeated = sum(n - 1 for n in hashes.values() if n > 1)
        repeat_runs += bool(repeated)
        repeat_events += len(_of(r, "repeat_call"))

        reasons = r.get("end_reasons") or []
        if r.get("end_reason") == "done" and not r.get("passed"):
            false_finishes.append(r["run_id"])
        for reason in reasons:
            if reason in BOUND_ENDS:
                bound[reason] += 1

        for line in _of(r, "plan_diff"):
            plan[f"diff_{line.get('label')}"] += 1
        plans = _of(r, "plan")
        plan["plans"] += bool(plans)
        plan["revisions"] += max(0, len(plans) - 1)
        plan["plan_rejected"] += reasons.count("plan_rejected")
        plan["replan_bound"] += reasons.count("replan_bound")
        plan["off_plan_refused"] += len(_of(r, "off_plan_refused"))
        plan["checkpoints_failed"] += sum(1 for c in _of(r, "checkpoint") if not c.get("passed"))

        crit = _of(r, "critique")
        critique["rounds"] += len(crit)
        critique["runs_with_critique"] += bool(crit)
        critique["verdicts"].update(c.get("verdict") for c in crit)
        critique["held"] += reasons.count("critique_held")
        if any(c.get("verdict") == "pass" for c in crit) and not r.get("passed"):
            critique["misses"] += 1

        expected = task_use_case(r)
        for route in _of(r, "route"):
            routing["routes"] += 1
            if expected and route.get("use_case") != expected:
                routing["misroutes"] += 1
                routing["misrouted_runs"].append(f"{r['run_id']}: {route.get('use_case')} for {expected}")

        for c in calls:
            kind = _error_kind(c)
            if kind:
                boundary["tool_errors"] += 1
                boundary["boundary_rejections"] += kind == "protocol"
        for name, value in (r.get("measures") or {}).items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                measures[name] += value
            elif isinstance(value, bool):
                measures[name] += int(value)

        per_run.append({"run_id": r["run_id"], "task": r["task"], "sweep": r["sweep"], "passed": bool(r.get("passed")),
                        "end_reasons": reasons, "tool_calls": len(calls), "repeats": repeated,
                        "critique_rounds": len(crit), "cost_usd": r.get("cost_usd") or 0.0,
                        "tokens": (r.get("tokens") or {}).get("total", 0)})

    cost_by_task = {t: statistics.mean(x["cost_usd"] for x in per_run if x["task"] == t) for t in tasks}
    return {
        "arm": Path(folder).name, "runs": len(counted), "passes": sum(1 for r in counted if r.get("passed")),
        "tasks": tasks, "sweeps": sweeps,
        "per_task": {t: [sum(1 for s in sweeps if by_pair.get((t, s), {}).get("passed")),
                         sum(1 for s in sweeps if (t, s) in by_pair)] for t in tasks},
        "per_sweep": {s: [sum(1 for t in tasks if by_pair.get((t, s), {}).get("passed")),
                          sum(1 for t in tasks if (t, s) in by_pair)] for s in sweeps},
        "turns": len(turns), "turn_median_s": _median(turns), "turn_slowest_s": max(turns) if turns else None,
        "slow_turns_over_10s": sum(1 for t in turns if t > 10),
        "tokens_per_run": statistics.mean(x["tokens"] for x in per_run) if per_run else None,
        "cost_per_run": statistics.mean(x["cost_usd"] for x in per_run) if per_run else None,
        "cost_per_task": cost_by_task,
        "sequences_per_task": {t: len(s) for t, s in sorted(sequences.items())},
        "sequences_total": len({(t, s) for t, ss in sequences.items() for s in ss}),
        "runs_with_repeat": repeat_runs, "repeat_events": repeat_events,
        "false_finishes": len(false_finishes), "false_finish_runs": false_finishes,
        "plan": dict(plan),
        "critique": {**{k: v for k, v in critique.items() if k != "verdicts"},
                     "rounds_per_run": (critique["rounds"] / critique["runs_with_critique"])
                     if critique["runs_with_critique"] else 0.0,
                     "verdicts": dict(critique["verdicts"])},
        "routing": routing, "bound_ends": dict(bound), "bound_runs": sum(bound.values()),
        "boundary": boundary, "measures": dict(measures), "per_run": per_run,
    }


def compare(agent: dict, workflow: dict) -> dict:
    """m and f on the tasks both arms ran."""
    shared = sorted(set(agent["tasks"]) & set(workflow["tasks"]))
    if not shared:
        return {"tasks": [], "m": None, "f": None}
    def mean_cost(arm):
        xs = [x["cost_usd"] for x in arm["per_run"] if x["task"] in shared]
        return statistics.mean(xs) if xs else None
    a, w = mean_cost(agent), mean_cost(workflow)
    gained = [t for t in shared if agent["per_task"][t][0] >= 2 and workflow["per_task"][t][0] <= 1]
    return {"tasks": shared, "agent_cost_per_run": a, "workflow_cost_per_run": w,
            "m": (a / w) if a is not None and w else None,
            "f": len(gained) / len(shared), "f_tasks": gained}


def _fmt(x, digits=2, unit=""):
    if x is None:
        return "n/a"
    return f"{x:.{digits}f}{unit}" if isinstance(x, float) else f"{x}{unit}"


def report(arms: list[dict], cross: dict | None) -> str:
    out = []
    for a in arms:
        out += [f"## {a['arm']}  ({a['runs']} runs: {len(a['tasks'])} tasks x {len(a['sweeps'])} sweeps)", "",
                f"passes {a['passes']} of {a['runs']}; per sweep: "
                + ", ".join(f"s{s} {p}/{n}" for s, (p, n) in a["per_sweep"].items()),
                f"turn latency: median {_fmt(a['turn_median_s'], unit=' s')}, slowest {_fmt(a['turn_slowest_s'], unit=' s')}"
                f" ({a['turns']} turns, {a['slow_turns_over_10s']} over 10 s)",
                f"tokens per run {_fmt(a['tokens_per_run'], 0)}; cost per run ${_fmt(a['cost_per_run'], 4)}",
                f"distinct tool-call sequences: {a['sequences_total']} in all",
                f"runs with an exact repeated call: {a['runs_with_repeat']}; repeat_call events: {a['repeat_events']}",
                f"false finishes (ended done, check failed): {a['false_finishes']}"
                + (f"  {', '.join(a['false_finish_runs'])}" if a["false_finish_runs"] else ""),
                "plan: " + (", ".join(f"{k} {v}" for k, v in sorted(a["plan"].items())) or "none"),
                f"critique: rounds {a['critique']['rounds']} over {a['critique']['runs_with_critique']} runs "
                f"({_fmt(a['critique']['rounds_per_run'])} per run), held {a['critique']['held']}, "
                f"misses {a['critique']['misses']}, verdicts {a['critique']['verdicts']}",
                f"routing: {a['routing']['routes']} routes, {a['routing']['misroutes']} misrouted"
                + (f"  ({'; '.join(a['routing']['misrouted_runs'])})" if a["routing"]["misrouted_runs"] else ""),
                f"ended at the bound: {a['bound_runs']} {a['bound_ends'] or ''}",
                f"tool errors {a['boundary']['tool_errors']}, rejected at the boundary {a['boundary']['boundary_rejections']}",
                "check measures: " + (", ".join(f"{k} {v}" for k, v in sorted(a["measures"].items())) or "none"),
                "", "| Task | Passed | Mean cost per run | Distinct sequences |", "|---|---|---|---|"]
        for t in a["tasks"]:
            p, n = a["per_task"][t]
            out.append(f"| {t} | {p} of {n} | ${a['cost_per_task'][t]:.4f} | {a['sequences_per_task'].get(t, 0)} |")
        out.append("")
    if cross:
        out += ["## m and f", "",
                f"tasks both arms ran: {', '.join(cross['tasks']) or 'none'}",
                f"agent cost per run ${_fmt(cross.get('agent_cost_per_run'), 4)}, workflow "
                f"${_fmt(cross.get('workflow_cost_per_run'), 4)}",
                f"m = {_fmt(cross['m'])}; f = {_fmt(cross['f'])}"
                + (f" ({', '.join(cross.get('f_tasks') or [])})" if cross.get("f_tasks") else "")]
    return "\n".join(out)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("arms", nargs="+", help="results/<arm> folders")
    p.add_argument("--agent", help="the arm (folder name) on the agent path, for m and f")
    p.add_argument("--workflow", help="the arm (folder name) on the workflow path, for m and f")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    arms = []
    for folder in a.arms:
        if not Path(folder).is_dir():
            print(f"{folder}: no such folder", file=sys.stderr)
            return 2
        arms.append(analyze_arm(Path(folder)))
    cross = None
    if a.agent or a.workflow:
        named = {x["arm"]: x for x in arms}
        if a.agent not in named or a.workflow not in named:
            print("--agent and --workflow must each name one of the arms given", file=sys.stderr)
            return 2
        cross = compare(named[a.agent], named[a.workflow])
    if a.json:
        print(json.dumps({"arms": arms, "m_f": cross}, indent=2, default=str))
    else:
        print(report(arms, cross))
    return 0


if __name__ == "__main__":
    sys.exit(main())
