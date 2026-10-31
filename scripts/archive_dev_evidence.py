"""Copy cited real development traces without committing entire dev arms.

The manifest preserves run/check metadata and hashes of verbatim trace copies.
These diagnostic samples never become official baseline/pass records.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("arms", nargs="+", help="development arm folders under results/")
    parser.add_argument("--output", type=Path, default=ROOT / "experiments/evidence/development_manifest.json")
    args = parser.parse_args()
    destination = ROOT / "traces"
    destination.mkdir(exist_ok=True)
    runs = []
    for folder_name in args.arms:
        folder = (ROOT / folder_name).resolve()
        if not folder.is_relative_to(ROOT / "results") or not folder.name.startswith("dev-"):
            parser.error("Only explicitly named results/dev-* folders can be archived.")
        for path in sorted(folder.glob("*.json")):
            record = json.loads(path.read_text(encoding="utf-8"))
            trace = path.with_suffix(".trace.jsonl")
            if not trace.is_file() or record.get("free"):
                parser.error(f"Expected a real-model development trace beside {path.name}.")
            copied = destination / trace.name
            if copied.exists() and copied.read_bytes() != trace.read_bytes():
                parser.error(f"Refusing to replace different evidence: {copied.name}")
            shutil.copyfile(trace, copied)
            runs.append({**{k: record.get(k) for k in (
                "run_id", "arm", "task", "sweep", "model", "commit", "dirty", "passed",
                "cost_usd", "turn_latency_s", "end_reasons", "check")},
                "trace": copied.relative_to(ROOT).as_posix(),
                "source_record": path.relative_to(ROOT).as_posix(),
                "trace_sha256": hashlib.sha256(copied.read_bytes()).hexdigest(),
                "tool_counts": dict(Counter(call["name"] for call in record.get("tool_calls", [])))})
    report = {"purpose": "Real development diagnostics; not baseline or pass evidence", "runs": runs}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Archived {len(runs)} verbatim development traces with manifest.")


if __name__ == "__main__":
    main()
