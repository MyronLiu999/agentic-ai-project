"""Recompute the Milestone 1 evidence measures from committed run records."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path


SKIP_FOLDERS = {"_free", "discarded"}


def _read_json(path: Path) -> dict | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) and value.get("run_id") else None


def _read_trace(record: dict) -> list[dict]:
    record_path = Path(record["_path"])
    candidates = [record_path.with_suffix(".trace.jsonl")]
    if record.get("trace_path"):
        candidates.insert(0, Path(record["trace_path"]))
    path = next((candidate for candidate in candidates if candidate.exists()), None)
    if path is None:
        return []
    lines = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            lines.append(value)
    return lines


def load_records(root: Path) -> list[dict]:
    records = []
    if not root.exists():
        return records
    if any(root.glob("*.json")):
        arm_dirs = [root]
    else:
        arm_dirs = sorted(path for path in root.iterdir()
                          if path.is_dir() and path.name not in SKIP_FOLDERS)
    for arm_dir in arm_dirs:
        for path in sorted(arm_dir.glob("*.json")):
            record = _read_json(path)
            if record is not None:
                record["_path"] = str(path)
                record["_arm"] = str(record.get("arm") or arm_dir.name)
                record["_trace"] = _read_trace(record)
                records.append(record)
    return records


def _passed(record: dict) -> bool:
    check = record.get("check") or {}
    if isinstance(check, dict) and "passed" in check:
        return bool(check["passed"])
    return bool(record.get("passed"))


def _repeat(record: dict) -> bool:
    seen = set()
    for call in record.get("tool_calls") or []:
        key = (call.get("name"), json.dumps(call.get("input") or {}, sort_keys=True, default=str))
        if key in seen:
            return True
        seen.add(key)
    return False


def _path(record: dict) -> str | None:
    if record.get("path") in ("agent", "workflow"):
        return record["path"]
    for line in record.get("_trace") or []:
        candidate = line.get("path")
        if candidate in ("agent", "workflow") and line.get("type") in ("route", "routing", "path"):
            return candidate
    use_case = str(record.get("use_case") or "")
    task_id = str(record.get("task_id") or record.get("task") or "")
    switches = record.get("switches") or {}
    for name, value in switches.items():
        if not str(name).startswith("control.") or value not in ("agent", "workflow"):
            continue
        case = str(name).split(".", 1)[1]
        if case == use_case or case in task_id:
            return value
    return None


def analyze(records: list[dict]) -> dict:
    by_arm: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        by_arm[record["_arm"]].append(record)

    arms = {}
    for arm, rows in sorted(by_arm.items()):
        turns = [float(value) for row in rows for value in (row.get("turn_latency_s") or [])]
        critique_counts = [sum(1 for line in row.get("_trace") or [] if line.get("type") == "critique")
                           for row in rows]
        held = [row for row in rows if "critique_held" in (row.get("end_reasons") or []) or
                any(line.get("type") == "critique" and line.get("verdict") == "held"
                    for line in row.get("_trace") or [])]
        false_finishes = [row for row in rows if not _passed(row) and
                          (row.get("end_reason") == "done" or "done" in (row.get("end_reasons") or []))]
        costs = [float(row.get("cost_usd") or 0.0) for row in rows]
        arms[arm] = {
            "runs": len(rows),
            "passes": sum(_passed(row) for row in rows),
            "median_turn_s": round(statistics.median(turns), 6) if turns else None,
            "mean_cost_usd": round(statistics.fmean(costs), 9) if costs else None,
            "false_finishes": len(false_finishes),
            "runs_with_exact_repeat": sum(_repeat(row) for row in rows),
            "critique_rounds_mean": round(statistics.fmean(critique_counts), 6) if critique_counts else 0.0,
            "critique_rounds_max": max(critique_counts, default=0),
            "held_drafts": len(held),
        }

    agent = [row for row in records if _path(row) == "agent"]
    workflow = [row for row in records if _path(row) == "workflow"]
    agent_cost = statistics.fmean(float(row.get("cost_usd") or 0.0) for row in agent) if agent else None
    workflow_cost = statistics.fmean(float(row.get("cost_usd") or 0.0) for row in workflow) if workflow else None
    m = agent_cost / workflow_cost if agent_cost is not None and workflow_cost else None

    paired: dict[tuple[str, int], dict[str, list[bool]]] = defaultdict(lambda: defaultdict(list))
    for row in records:
        path = _path(row)
        if path:
            task_id = str(row.get("task_id") or row.get("task") or "")
            paired[(task_id, int(row.get("sweep") or 0))][path].append(_passed(row))
    comparable = [paths for paths in paired.values() if "agent" in paths and "workflow" in paths]
    agent_only_wins = sum(any(paths["agent"]) and not any(paths["workflow"]) for paths in comparable)
    f = agent_only_wins / len(comparable) if comparable else None

    return {
        "arms": arms,
        "cross_path": {
            "agent_runs": len(agent),
            "workflow_runs": len(workflow),
            "m_agent_over_workflow_mean_cost": round(m, 6) if m is not None else None,
            "f_agent_pass_workflow_fail": round(f, 6) if f is not None else None,
            "f_pairs": len(comparable),
            "f_definition": "matched task_id+sweep pairs where agent passed and workflow failed",
        },
    }


def _print_table(summary: dict) -> None:
    print("arm\truns\tpasses\tmedian_turn_s\tmean_cost_usd\tfalse_finishes\trepeats\trounds_mean\theld")
    for arm, row in summary["arms"].items():
        print(f"{arm}\t{row['runs']}\t{row['passes']}\t{row['median_turn_s']}\t{row['mean_cost_usd']}\t"
              f"{row['false_finishes']}\t{row['runs_with_exact_repeat']}\t"
              f"{row['critique_rounds_mean']}\t{row['held_drafts']}")
    cross = summary["cross_path"]
    print(f"m={cross['m_agent_over_workflow_mean_cost']}  f={cross['f_agent_pass_workflow_fail']}  "
          f"matched_pairs={cross['f_pairs']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default="results", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    summary = analyze(load_records(args.root))
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        _print_table(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
