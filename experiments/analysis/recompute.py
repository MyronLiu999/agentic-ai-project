"""Regenerate historical evidence without running agents or rewriting recorded outcomes.

    python -m experiments.analysis.recompute [--check] [--repo-root PATH]

Inputs are the recorded runs/traces, analysis_inputs.json (prospective protocol,
original hash provenance, frozen input schemas and archived development metadata),
and semantic_annotations.json (reviewed, trace-backed argument classifications).
Hashes normalize CRLF to LF only; no JSON reserialization or whitespace stripping.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re

from experiments.analysis.analyze import ROOT, _error_kind, analyze_arm, load_arm, task_metrics
from experiments.analysis.failures import collect
from harness.schema import errors as schema_errors

HASH_POLICY = "sha256 of bytes after CRLF-to-LF normalization only; preserve all other bytes"


def normalize_lf(content: bytes) -> bytes:
    return content.replace(b"\r\n", b"\n")


def lf_sha256(content: bytes) -> str:
    return hashlib.sha256(normalize_lf(content)).hexdigest()


def verified_hash(path: Path, original_sha256: str) -> dict:
    """Verify content against the original LF or CRLF byte hash, then hash LF."""
    normalized = normalize_lf(path.read_bytes())
    digest = hashlib.sha256(normalized).hexdigest()
    original_crlf = hashlib.sha256(normalized.replace(b"\n", b"\r\n")).hexdigest()
    if original_sha256 not in (digest, original_crlf):
        raise ValueError(f"Content does not match original hash provenance: {path}")
    return {"sha256": digest, "original_sha256": original_sha256,
            "original_line_endings": "LF" if original_sha256 == digest else "CRLF"}


def _inside(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"Evidence path escapes repository: {relative}")
    return path


def _select(value, selector):
    for key in selector:
        value = value[key]
    return value


def validate_annotations(root: Path, entries: list[dict]) -> list[dict]:
    """Validate physical line, source hash, event/tool, and exact argument snapshot.

    A plan candidate counts once per model-produced plan step. Critique-approved
    plan copies are not new proposals. A revision is a new argument candidate;
    executed calls and pre-execution candidates have distinct stages in output.
    Classification is explicit human review, never inferred from error prose.
    """
    seen = set()
    for entry in entries:
        key = (entry["trace"], entry["line"], tuple(entry["selector"]))
        if key in seen:
            raise ValueError(f"Duplicate argument candidate: {key}")
        seen.add(key)
        if entry["count_unit"] != "argument_candidate" or not entry.get("category") or not entry.get("reason"):
            raise ValueError(f"Annotation needs category, count unit and rationale: {key}")
        path = _inside(root, entry["trace"])
        if lf_sha256(path.read_bytes()) != entry["trace_sha256_lf"]:
            raise ValueError(f"Annotation source hash changed: {path}")
        try:
            source = json.loads(path.read_text(encoding="utf-8").splitlines()[entry["line"] - 1])
            if entry["line"] < 1 or source.get("type") != entry["event_type"]:
                raise ValueError("Wrong physical event line")
            if source.get("run_id") != entry["run_id"]:
                raise ValueError("Wrong run")
            value = json.loads(source["text"]) if entry.get("decode_text") else source
            if _select(value, entry["selector"]) != entry["observed"]:
                raise ValueError("Annotation observed arguments differ from source")
            if source["type"] == "tool_call" and source.get("name") != entry["tool"]:
                raise ValueError("Wrong tool")
            if source["type"] == "plan":
                step = _select(source, entry["selector"][:-1])
                if step.get("tool") != entry["tool"] or source.get("approved_by") == "critique":
                    raise ValueError("Wrong tool or copied amendment")
            if "model_line" in entry:
                model = json.loads(path.read_text(encoding="utf-8").splitlines()[entry["model_line"] - 1])
                if (model.get("type") != "model_call" or model.get("run_id") != entry["run_id"]
                        or entry["model_line"] > entry["line"]):
                    raise ValueError("Wrong model source")
                if source["type"] == "tool_call" and not any(
                        call.get("name") == source.get("name")
                        and call.get("input") == source.get("input") for call in model.get("tool_calls", [])):
                    raise ValueError("Cited model did not propose the annotated call")
                if source["type"] == "plan" and (model.get("purpose") != "batch_plan"
                        or entry["model_line"] != entry["line"] - 1):
                    raise ValueError("Cited model did not produce the annotated plan")
                if source["type"] == "model_call" and (model.get("purpose") != "critique_revision"
                        or entry["model_line"] != entry["line"]):
                    raise ValueError("Cited model is not the annotated revision")
            for fact in entry.get("facts", []):
                fact_path = _inside(root, fact["path"])
                if lf_sha256(fact_path.read_bytes()) != fact["sha256_lf"]:
                    raise ValueError("Annotation fact source hash changed")
                if "line" in fact:
                    fact_value = json.loads(fact_path.read_text(encoding="utf-8").splitlines()[fact["line"] - 1])
                    if fact["line"] < 1:
                        raise ValueError("Invalid physical fact line")
                else:
                    import yaml
                    fact_value = yaml.safe_load(fact_path.read_text(encoding="utf-8"))
                if _select(fact_value, fact["selector"]) != fact["observed"]:
                    raise ValueError("Annotation fact observed value differs from source")
        except (IndexError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid physical annotation source: {key}") from exc
    return entries


def _argument_schema_errors(value, schema, path="input"):
    """Frozen tools also use pattern/maxItems/minimum, beyond harness shape rules."""
    problems = schema_errors(value, schema)

    def constraints(item, contract, location):
        if isinstance(item, str) and "pattern" in contract and not re.search(contract["pattern"], item):
            problems.append(f"{location}: does not match pattern {contract['pattern']}")
        if isinstance(item, (int, float)) and not isinstance(item, bool) and "minimum" in contract:
            if item < contract["minimum"]:
                problems.append(f"{location}: below minimum {contract['minimum']}")
        if isinstance(item, list):
            if "maxItems" in contract and len(item) > contract["maxItems"]:
                problems.append(f"{location}: exceeds maxItems {contract['maxItems']}")
            for index, child in enumerate(item):
                constraints(child, contract.get("items", {}), f"{location}[{index}]")
        if isinstance(item, dict):
            for name, child in item.items():
                constraints(child, contract.get("properties", {}).get(name, {}), f"{location}.{name}")

    constraints(value, schema, path)
    return problems


def argument_metrics(runs: list[dict], annotations: list[dict], schemas: dict) -> dict:
    """Malformed = dispatched/tool-attempt inputs violating frozen input schema.

    Semantic annotations include pre-execution plan and revision candidates;
    they can overlap a boundary rejection, e.g. a well-typed wrong report ID.
    """
    per_run = []
    for run in runs:
        entries = [entry for entry in annotations if entry["run_id"] == run["run_id"]]
        calls = run.get("tool_calls") or []
        malformed = []
        for index, call in enumerate(calls, 1):
            schema = schemas.get(call.get("name"))
            if schema is None:
                raise ValueError(f"No frozen schema for {call.get('name')}")
            problems = _argument_schema_errors(call.get("input"), schema)
            if problems:
                malformed.append({"tool_call_ordinal": index, "tool": call["name"], "problems": problems})
        per_run.append({"run_id": run["run_id"], "malformed_calls": len(malformed),
                        "malformed_call_details": malformed,
                        "boundary_rejections": sum(_error_kind(call) == "protocol" for call in calls),
                        "semantic_wrong_argument_candidates": len(entries),
                        "semantic_categories": dict(sorted(Counter(e["category"] for e in entries).items())),
                        "semantic_stages": dict(sorted(Counter(e["event_type"] for e in entries).items()))})
    return {"runs": len(runs), "malformed_calls": sum(r["malformed_calls"] for r in per_run),
            "malformed_call_runs": sum(r["malformed_calls"] > 0 for r in per_run),
            "boundary_rejections": sum(r["boundary_rejections"] for r in per_run),
            "semantic_wrong_argument_candidates": sum(r["semantic_wrong_argument_candidates"] for r in per_run),
            "semantic_wrong_argument_runs": sum(r["semantic_wrong_argument_candidates"] > 0 for r in per_run),
            "semantic_categories": dict(sorted(Counter(e["category"] for e in annotations).items())),
            "semantic_stages": dict(sorted(Counter(e["event_type"] for e in annotations).items())),
            "per_run": per_run}


def difference(before, after):
    return {"absolute": after - before, "percent": (after / before - 1) * 100 if before else None}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def build_audit(root: Path, protocol: dict, provenance: dict) -> dict:
    """Check coverage, settings, chronology and source hashes from the declared protocol."""
    expected = {(task, sweep) for task in protocol["tasks"] for sweep in protocol["sweeps"]}
    arm_runs, settings, switches, files, metrics = {}, [], [], [], {}
    prediction = datetime.fromisoformat(protocol["prediction_committed_at"])
    for arm in protocol["arms"]:
        paths = sorted((root / "results" / arm).glob("*.json"))
        rows = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
        _require(len(rows) == len(expected) and {(r["task"], r["sweep"]) for r in rows} == expected,
                 f"Invalid task/sweep coverage: {arm}")
        for path, run in zip(paths, rows):
            _require(run.get("outcome") == "completed" and run.get("free") is False
                     and run.get("dirty") is False and run.get("commit") == protocol["commit"],
                     f"Non-comparable record: {path}")
            _require(datetime.fromisoformat(run["started"].replace("Z", "+00:00")) > prediction,
                     f"Run preceded prediction: {path}")
            settings.append({k: run.get(k) for k in ("settings", "backend", "price_sheet", "model")})
            switch = dict(run["switches"])
            _require(switch.pop("examples.save_report") == protocol["arms"][arm], f"Wrong switch arm: {path}")
            switches.append(switch)
            for source in (path, path.with_suffix(".trace.jsonl")):
                relative = source.relative_to(root).as_posix()
                _require(relative in provenance, f"Missing original provenance: {relative}")
                files.append({"path": relative, **verified_hash(source, provenance[relative])})
            trace = [json.loads(line) for line in path.with_suffix(".trace.jsonl").read_text(encoding="utf-8").splitlines()]
            _require(all(isinstance(line, dict) for line in trace), f"Non-object trace: {path}")
            start = trace[0]
            _require(start.get("type") == "run_start" and start.get("run_id") == run["run_id"], f"Wrong trace pair: {path}")
            for key in ("arm", "task", "sweep", "switches", "commit", "dirty", "free", "settings", "backend", "price_sheet", "model"):
                _require(start.get(key) == run.get(key), f"Trace/record {key} differs: {path}")
        arm_runs[arm] = rows
        analysis = analyze_arm(root / "results" / arm, repo_root=root)
        target = task_metrics(analysis, protocol["target_task"])
        metrics[arm] = {"task_turn_false_finishes": analysis["initial_task_false_finish_runs"],
                        "held_then_status_done": [r["run_id"] for r in load_arm(root / "results" / arm)
                                                  if not r.get("passed") and r.get("end_reasons", [])[:1] == ["critique_held"]
                                                  and r.get("end_reason") == "done"],
                        "target_mean_tokens": target["mean_tokens"], "target_mean_cost_usd": target["mean_cost_usd"]}
    _require(all(setting == settings[0] for setting in settings), "Settings/backend/price/model differ")
    _require(all(switch == switches[0] for switch in switches), "More than examples.save_report switch differs")
    _require(settings[0] == protocol["configuration"], "Configuration differs from declared protocol")
    return {"commit": protocol["commit"], "prediction_committed_at": protocol["prediction_committed_at"],
            "hash_policy": HASH_POLICY,
            "invariants_checked": [f"{len(expected)} unique task/sweep pairs per arm",
                "all completed, non-free, clean and identical commit", "identical settings/backend/price sheet/model",
                "only examples.save_report switch differs", "all run starts after prediction commit",
                f"all {sum(map(len, arm_runs.values()))} traces parse as JSONL and match run metadata",
                "all file contents match original LF/CRLF hash provenance"], "metrics": metrics, "files": files}


def development_manifest(root: Path, seeds: list[dict], provenance: dict) -> dict:
    runs = []
    for seed in seeds:
        relative = seed["trace"]
        path = _inside(root, relative)
        hashes = verified_hash(path, provenance[relative])
        trace = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        _require(trace[0].get("run_id") == seed["run_id"], f"Wrong development trace: {path}")
        end = next(line for line in reversed(trace) if line.get("type") == "run_end")
        _require(end.get("passed") == seed["passed"], f"Historical check changed: {path}")
        runs.append({**seed, "trace_sha256": hashes["sha256"],
                     "original_trace_sha256": hashes["original_sha256"],
                     "original_line_endings": hashes["original_line_endings"],
                     "tool_counts": dict(sorted(Counter(line["name"] for line in trace
                                                       if line.get("type") == "tool_call").items()))})
    return {"purpose": "Real development diagnostics; not baseline or pass evidence",
            "hash_policy": HASH_POLICY, "runs": runs}


def baseline_provenance(root: Path, inputs: dict) -> dict:
    """Verify every frozen baseline source before computing historical scores.

    This baseline inventory was newly established during the audit correction;
    its recorded origin names the unchanged tracked blobs, not an earlier audit.
    """
    inventory = inputs["baseline_provenance"]
    actual = sorted(path.relative_to(root).as_posix() for path in (root / "results/baseline").iterdir()
                    if path.is_file() and (path.suffix == ".json" or path.name.endswith(".trace.jsonl")))
    expected = inventory["files"]
    _require(actual == sorted(expected) and len(expected) == len(set(expected)),
             "Baseline provenance file inventory differs from actual baseline sources")
    files = []
    for relative in expected:
        path = _inside(root, relative)
        files.append({"path": relative, **verified_hash(path, inputs["original_sha256"][relative])})
    return {"origin": inventory["origin"], "commit": inventory["commit"],
            "hash_policy": HASH_POLICY, "files": files}


def build_outputs(root: Path) -> dict[str, dict]:
    evidence = root / "experiments/evidence"
    inputs = json.loads((evidence / "analysis_inputs.json").read_text(encoding="utf-8"))
    baseline_sources = baseline_provenance(root, inputs)
    manifest = json.loads((evidence / "semantic_annotations.json").read_text(encoding="utf-8"))
    entries = validate_annotations(root, manifest["annotations"])
    protocol = inputs["pass1_protocol"]
    arms = [analyze_arm(root / "results" / arm, repo_root=root) for arm in protocol["arms"]]
    all_analyses = [analyze_arm(root / "results/baseline", repo_root=root), *arms]
    argument = {a["arm"]: argument_metrics(load_arm(root / "results" / a["arm"]),
                [e for e in entries if e["arm"] == a["arm"]], inputs["argument_schemas"]) for a in all_analyses}
    before, after = arms
    before_target, after_target = (task_metrics(a, protocol["target_task"]) for a in arms)
    deltas = {"overall_passes": after["passes"] - before["passes"],
              "overall_pass_percentage_points": 100 * (after["passes"] / after["runs"] - before["passes"] / before["runs"]),
              "mean_tokens": difference(before["tokens_per_run"], after["tokens_per_run"]),
              "mean_cost_usd": difference(before["cost_per_run"], after["cost_per_run"]),
              "target_passes": after_target["passes"] - before_target["passes"],
              "target_mean_tokens": difference(before_target["mean_tokens"], after_target["mean_tokens"]),
              "target_mean_cost_usd": difference(before_target["mean_cost_usd"], after_target["mean_cost_usd"]),
              "initial_task_false_finishes": after["initial_task_false_finishes"] - before["initial_task_false_finishes"],
              "critique_misses": after["critique"]["misses"] - before["critique"]["misses"],
              "proposal_rejections": after["plan"]["proposal_rejections"] - before["plan"]["proposal_rejections"],
              "boundary_rejections": after["boundary"]["boundary_rejections"] - before["boundary"]["boundary_rejections"]}
    reports = [collect(root / "results" / arm, repo_root=root) for arm in protocol["arms"]]
    failures = {"records": sum(report["records"] for report in reports),
                "failures": [row for report in reports for row in report["failures"]],
                "issues": [issue for report in reports for issue in report["issues"]]}
    # Artifacts must be byte-identical after checkout relocation.
    for row in failures["failures"]:
        for field in ("record", "trace"):
            row[field] = Path(row[field]).relative_to(root).as_posix()
    return {"baseline_summary.json": {"arms": [all_analyses[0]], "m_f": None, "provenance": baseline_sources},
            "pass1_summary.json": {"arms": arms, "m_f": None},
            "pass1_audit.json": build_audit(root, protocol, inputs["original_sha256"]),
            "development_manifest.json": development_manifest(root, inputs["development_runs"], inputs["original_sha256"]),
            "pass1_failures.json": failures,
            "additional_metrics.json": {"definitions": manifest["definitions"], "hash_policy": HASH_POLICY,
                "argument_quality": argument, "target": {a["arm"]: task_metrics(a, protocol["target_task"]) for a in arms},
                "differences_on_minus_off": deltas}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--check", action="store_true", help="Verify source contents and require current derived artifacts")
    args = parser.parse_args(argv)
    root = args.repo_root.resolve()
    try:
        outputs = build_outputs(root)
        stale = []
        for name, value in outputs.items():
            path = root / "experiments/evidence" / name
            content = (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
            if args.check:
                if not path.exists() or normalize_lf(path.read_bytes()) != content:
                    stale.append(name)
            else:
                path.write_bytes(content)
        if stale:
            parser.exit(1, "Stale derived evidence: " + ", ".join(stale) + "\n")
    except (ValueError, KeyError, OSError, StopIteration) as exc:
        parser.exit(1, f"Evidence verification failed: {exc}\n")
    print(f"{'Verified' if args.check else 'Regenerated'} {len(outputs)} derived artifacts; raw runs/traces unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
