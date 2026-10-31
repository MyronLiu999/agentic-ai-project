"""Read failing run records and cite the first explicit failure's physical trace line.

Usage: python -m experiments.analysis.failures results/ [--json] [--include-free]
This identifies the first observed failure, not a proven root cause. It writes nothing.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BOUNDS = {"step_limit", "wall_clock", "agent_budget", "token_budget", "plan_rejected", "replan_bound", "critique_held"}


def _first_signal(line, check_reason):
    kind = line.get("type")
    if kind == "error":
        return str(line.get("kind") or "error"), str(line.get("message") or line.get("detail") or "Recorded error")
    if kind == "tool_call":
        output = line.get("output")
        if isinstance(output, str):
            try:
                output = json.loads(output)
            except ValueError:
                pass
        output = output if isinstance(output, dict) else {}
        if line.get("is_error") or output.get("is_error") or output.get("ok") is False:
            error = output.get("error") or line.get("error") or {}
            message = error.get("message", str(error)) if isinstance(error, dict) else str(error)
            return "tool_error", f"{line.get('name', 'tool')}: {message or 'Tool failed'}"
    if kind == "checkpoint" and line.get("passed") is False:
        return "checkpoint_failed", str(line.get("reason") or "Observable outcome failed")
    if kind == "plan" and line.get("accepted") is False:
        return "plan_rejected", str(line.get("reason") or "Plan validation failed")
    if kind == "critique" and line.get("verdict") in ("revise", "held"):
        return "critique_" + line["verdict"], str(line.get("reason") or "Draft did not pass critique")
    if kind == "off_plan_refused":
        return kind, f"Call refused: {line.get('tool', 'unknown tool')}"
    if kind == "plan_diff" and line.get("label") in ("out_of_order", "extra"):
        return "plan_diff", f"{line.get('step_id', '?')}: {line['label']}"
    if kind == "end" and line.get("terminal_reason") in BOUNDS:
        return line["terminal_reason"], str(line.get("detail") or line["terminal_reason"])
    if kind == "run_end":
        if line.get("outcome") != "completed":
            return str(line.get("outcome") or "unfinished"), str(line.get("error") or "Run did not complete")
        if line.get("passed") is False:
            return "check_failed", check_reason or "The independent check failed"
    return None


def inspect_record(record, path: Path, repo_root: Path):
    trace = Path(record.get("trace") or path.with_suffix(".trace.jsonl"))
    trace = trace if trace.is_absolute() else repo_root / trace
    issues, first = [], None
    check_reason = str((record.get("check") or {}).get("reason") or "")
    try:
        with trace.open(encoding="utf-8") as stream:
            for number, text in enumerate(stream, 1):
                if not text.strip():
                    continue
                try:
                    line = json.loads(text)
                    if not isinstance(line, dict):
                        raise ValueError("Not a JSON object")
                except ValueError:
                    issues.append(f"Malformed trace JSON at line {number}")
                    continue
                signal = _first_signal(line, check_reason)
                if signal and first is None:
                    first = {"line": number, "kind": signal[0], "message": signal[1]}
    except (OSError, UnicodeError) as exc:
        issues.append(f"Trace unavailable: {exc}")
    if first is None:
        first = {"line": None, "kind": "record_only",
                 "message": str(record.get("error") or check_reason or "No failure detail in the available trace")}
        if not issues:
            issues.append("No explicit failure signal in the available trace; using the run record")
    return {"run_id": record["run_id"], "arm": record.get("arm"), "task": record.get("task"),
            "outcome": record.get("outcome"), "end_reasons": record.get("end_reasons") or [record.get("end_reason")],
            "check_reason": check_reason, "record": str(path), "trace": str(trace), "first_failure": first,
            "evidence_issues": issues, "synthetic": bool(record.get("free") or "_free" in path.parts)}


def collect(target: Path, *, repo_root: Path = ROOT, include_free=False, include_discarded=False):
    target, repo_root = Path(target).resolve(), Path(repo_root).resolve()
    report = {"records": 0, "failures": [], "issues": []}
    if not target.exists():
        report["issues"].append(f"No results at {target}")
        return report
    paths = [target] if target.is_file() else sorted(target.rglob("*.json"))
    for path in paths:
        if not include_free and "_free" in path.parts or not include_discarded and "discarded" in path.parts:
            continue
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError) as exc:
            report["issues"].append(f"Unreadable record {path}: {exc}")
            continue
        if not isinstance(record, dict) or "run_id" not in record:
            continue
        if record.get("free") and not include_free:
            continue
        report["records"] += 1
        passed = record.get("passed", (record.get("check") or {}).get("passed"))
        if passed is True and record.get("outcome") == "completed":
            continue
        report["failures"].append(inspect_record(record, path, repo_root))
    return report


def markdown(report):
    def cell(value):
        return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")
    lines = [f"{len(report['failures'])} failed or unfinished runs among {report['records']} included records.", "",
             "| Run | End reasons | First observed failure | Evidence |",
             "|---|---|---|---|"]
    notes = []
    for row in report["failures"]:
        failure = row["first_failure"]
        location = f"{row['trace']}:{failure['line']}" if failure["line"] is not None else f"{row['record']} (record only)"
        run_id = str(row["run_id"]) + (" [synthetic]" if row["synthetic"] else "")
        lines.append("| " + " | ".join(cell(v) for v in (run_id, ", ".join(str(r) for r in row["end_reasons"] if r),
                     f"{failure['kind']}: {failure['message']}", location)) + " |")
        for issue in row["evidence_issues"]:
            notes.append(f"Evidence issue for {cell(row['run_id'])}: {cell(issue)}")
    if notes:
        lines += [""] + [f"- {note}" for note in notes]
    if report["issues"]:
        lines += ["", "Input issues:", ""] + [f"- {cell(issue)}" for issue in report["issues"]]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", nargs="?", type=Path, default=ROOT / "results")
    parser.add_argument("--repo-root", type=Path, default=ROOT, help="Base for trace paths stored relative to the repository")
    parser.add_argument("--include-free", action="store_true", help="Include and label synthetic runs")
    parser.add_argument("--include-discarded", action="store_true")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable output")
    args = parser.parse_args(argv)
    report = collect(args.target, repo_root=args.repo_root, include_free=args.include_free,
                     include_discarded=args.include_discarded)
    print(json.dumps(report, indent=2) if args.json else markdown(report), end="\n" if args.json else "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
