"""Copy cited real development traces without committing entire dev arms.

The manifest preserves run/check metadata, portable LF hashes and original byte hashes.
These diagnostic samples never become official baseline/pass records.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from experiments.analysis.recompute import HASH_POLICY, lf_sha256, normalize_lf



def archive_runs(arms, *, root=ROOT):
    root = Path(root).resolve()
    destination = root / "traces"
    destination.mkdir(exist_ok=True)
    runs = []
    for folder_name in arms:
        folder = (root / folder_name).resolve()
        if not folder.is_relative_to(root / "results") or not folder.name.startswith("dev-"):
            raise ValueError("Only explicitly named results/dev-* folders can be archived.")
        for path in sorted(folder.glob("*.json")):
            record = json.loads(path.read_text(encoding="utf-8"))
            trace = path.with_suffix(".trace.jsonl")
            if not trace.is_file() or record.get("free"):
                raise ValueError(f"Expected a real-model development trace beside {path.name}.")
            copied = destination / trace.name
            if copied.exists() and normalize_lf(copied.read_bytes()) != normalize_lf(trace.read_bytes()):
                raise ValueError(f"Refusing to replace different evidence: {copied.name}")
            if not copied.exists():
                shutil.copyfile(trace, copied)
            runs.append({**{k: record.get(k) for k in (
                "run_id", "arm", "task", "sweep", "model", "commit", "dirty", "passed",
                "cost_usd", "turn_latency_s", "end_reasons", "check")},
                "trace": copied.relative_to(root).as_posix(),
                "source_record": path.relative_to(root).as_posix(),
                "trace_sha256": lf_sha256(copied.read_bytes()),
                "original_trace_sha256": hashlib.sha256(trace.read_bytes()).hexdigest(),
                "original_line_endings": "CRLF" if b"\r\n" in trace.read_bytes() else "LF",
                "tool_counts": dict(Counter(call["name"] for call in record.get("tool_calls", [])))})
    return {"purpose": "Real development diagnostics; not baseline or pass evidence",
            "hash_policy": HASH_POLICY, "runs": runs}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("arms", nargs="+", help="development arm folders under results/")
    parser.add_argument("--output", type=Path, default=ROOT / "experiments/evidence/development_manifest.json")
    args = parser.parse_args(argv)
    try:
        report = archive_runs(args.arms)
    except ValueError as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Archived {len(report['runs'])} development traces with portable hashes and original-byte provenance.")


if __name__ == "__main__":
    main()
