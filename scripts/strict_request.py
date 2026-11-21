"""Strict mode, as sent (Milestone 2, Part 1 task 3; owner: myron, M2).

Sends ONE request to the vendor carrying every tool the decision table makes strict (switches.yaml, the
`strict` group set to "on"), with each definition exactly as the registry sends it (agent/tools.build, then
harness.backends.to_openai_tools, the conversion every model call uses), and keeps the vendor's answer:
accepted, or refused with what it names.

    python scripts/strict_request.py --dry-run          # write the request only; no API call, no key needed
    python scripts/strict_request.py                    # one metered call; needs OPENAI_API_KEY in the shell

Writes experiments/evidence/strict_request.json (or --output): the date, the model, the request's tools, and
the answer. The key is never written anywhere.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness import ROOT

DEFAULT_OUTPUT = ROOT / "experiments" / "evidence" / "strict_request.json"


def strict_definitions() -> list[dict]:
    """Every strict definition the registry can send, in the registry's order (the union of all loadings,
    with run_program on, so no strict tool is missed)."""
    from agent import tools
    from harness import runtime
    seen, out = set(), []
    for overrides in (["tools.loading=all", "code_calls.batch_reports=on"], ["tools.loading=deferred"]):
        runtime.configure(overrides=overrides)
        try:
            for definition in tools.build(None).definitions():
                if definition.get("strict") and definition["name"] not in seen:
                    seen.add(definition["name"])
                    out.append(definition)
        finally:
            runtime.configure()
    order = [s.name for s in tools.specs(None)] + ["run_program"]
    return sorted(out, key=lambda d: order.index(d["name"]) if d["name"] in order else len(order))


def request_body(model: str) -> dict:
    from harness.backends import to_openai_tools
    return {"model": model, "max_tokens": 5,
            "messages": [{"role": "user", "content": "Reply with exactly OK. Do not call a tool."}],
            "tools": to_openai_tools(strict_definitions())}


def send(body: dict) -> dict:
    """One Chat Completions call; the answer is accepted or refused, with the vendor's own words."""
    from openai import OpenAI
    from harness.settings import load_settings
    settings = load_settings(ROOT / "settings.yaml")
    key = os.environ.get(settings.api_key_env or "OPENAI_API_KEY")
    if not key:
        raise SystemExit("set OPENAI_API_KEY (or settings.yaml's api_key_env) in this shell first")
    client = OpenAI(api_key=key.strip(), base_url=settings.base_url or None)
    try:
        response = client.chat.completions.create(**body)
    except Exception as exc:                     # the vendor refused the request: keep exactly what it said
        status = getattr(exc, "status_code", None)
        response = getattr(exc, "response", None)
        try:
            raw = response.json() if response is not None else None
        except Exception:
            raw = getattr(response, "text", None)
        detail = raw or getattr(exc, "body", None) or getattr(exc, "message", None) or str(exc)
        return {"answer": "refused", "http_status": status, "error": detail}
    return {"answer": "accepted", "response_model": response.model, "response_id": response.id,
            "finish_reason": response.choices[0].finish_reason if response.choices else None}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="write the request without sending it")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    from harness.settings import load_settings
    settings = load_settings(ROOT / "settings.yaml")
    body = request_body(settings.model)
    record = {"checked_at": datetime.now(timezone.utc).isoformat(), "provider": settings.provider,
              "model": settings.model, "strict_tools": [t["function"]["name"] for t in body["tools"]],
              "request": body}
    record["vendor"] = {"answer": "not sent (dry run)"} if args.dry_run else send(body)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"strict_tools": record["strict_tools"], "vendor": record["vendor"]}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
