"""Measure the input-token price of the first-draft and rewritten tool surfaces.

The measurement follows the Assignment 3 method: for each surface, send the
same one-message request once without definitions and once with definitions,
then subtract prompt-token usage.  It uses the same settings, backend,
``ModelClient`` and price sheet as ``harness/ping.py``.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.tools import build
from harness import ROOT
from harness.backends import REAL_BACKENDS, make_backend
from harness.client import ModelClient
from harness.pricing import PriceSheet
from harness.settings import load_settings


FIRST_DRAFT = [
    {"name": "parse_file", "description": "Read the request's uploaded file.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "query_sales", "description": "Query this request's distributor's sales for a quarter.",
     "input_schema": {"type": "object", "properties": {"period": {"type": "string"}},
                      "required": ["period"]}},
    {"name": "render_chart", "description": "Render a chart.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "save_report", "description": "Save the report.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "draft_report_email", "description": "Write the report email as a pending record.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "draft_clarifying_question", "description": "Write a clarifying question as a pending record.",
     "input_schema": {"type": "object", "properties": {}}},
]

SYSTEM = "You are measuring prompt size. Do not call a tool."
MESSAGES = [{"role": "user", "content": "Reply with exactly OK and no other text."}]


M1_TOOLS = [d["name"] for d in FIRST_DRAFT]


def surfaces() -> dict[str, list[dict]]:
    """Milestone 1's two surfaces: the scaffold and the rewrite of the same six tools."""
    return {"first_draft": FIRST_DRAFT,
            "rewrite": [d for d in build(None).definitions() if d["name"] in M1_TOOLS]}


def m2_surfaces() -> dict[str, list[dict]]:
    """Milestone 2's tool list (myron, M3): every definition a request carries with tools.loading = all, the
    first request with deferred (the search tool and the always-loaded tools), and all with run_program."""
    from harness import runtime
    out = {}
    for name, overrides in (("m2_all", ["tools.loading=all"]),
                            ("m2_deferred_first", ["tools.loading=deferred"]),
                            ("m2_all_with_run_program", ["tools.loading=all", "code_calls.batch_reports=on"])):
        runtime.configure(overrides=overrides)
        try:
            out[name] = build(None).definitions()
        finally:
            runtime.configure()
    return out


def estimate(definitions: list[dict]) -> int:
    """Tokens a list of definitions adds to a request, estimated as characters / 4 (no API call)."""
    return len(json.dumps(definitions, sort_keys=True)) // 4


def measure(client_factory, which=None) -> dict:
    rows = {}
    for name, definitions in (which if which is not None else surfaces()).items():
        without = client_factory().create(system=SYSTEM, messages=MESSAGES, tools=None)
        with_definitions = client_factory().create(system=SYSTEM, messages=MESSAGES, tools=definitions)
        rows[name] = {
            "model": with_definitions.model,
            "without_definitions": without.usage.prompt_tokens,
            "with_definitions": with_definitions.usage.prompt_tokens,
            "definition_tokens": with_definitions.usage.prompt_tokens - without.usage.prompt_tokens,
            "definition_count": len(definitions),
        }
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--show-definitions", action="store_true",
                        help="print both surfaces without making an API call")
    parser.add_argument("--output", type=Path,
                        help="save the real measurement as UTF-8 JSON as well as printing it")
    parser.add_argument("--milestone", type=int, choices=(1, 2), default=1,
                        help="1: Milestone 1's two surfaces (default); 2: the Milestone 2 tool list")
    parser.add_argument("--estimate", action="store_true",
                        help="print each surface's characters / 4 estimate without making an API call")
    args = parser.parse_args(argv)
    chosen = surfaces() if args.milestone == 1 else m2_surfaces()
    if args.show_definitions:
        print(json.dumps(chosen, indent=2, sort_keys=True))
        return 0
    if args.estimate:
        print(json.dumps({name: {"definition_count": len(d), "estimated_tokens": estimate(d)}
                          for name, d in chosen.items()}, indent=2, sort_keys=True))
        return 0

    settings = load_settings(ROOT / "settings.yaml")
    if settings.provider not in REAL_BACKENDS or not settings.model:
        print("settings.yaml must name a real provider and model", file=sys.stderr)
        return 1
    prices = PriceSheet(ROOT / "pricing.yaml")

    def client_factory():
        return ModelClient(make_backend(settings.provider, settings), prices)

    try:
        rows = measure(client_factory, chosen)
    except Exception as exc:
        print(f"definition-cost measurement failed: {type(exc).__name__}: {str(exc)[:500]}", file=sys.stderr)
        return 1
    report = {"measured_at": datetime.now(timezone.utc).isoformat(),
              "provider": settings.provider, "requested_model": settings.model,
              "method": "with prompt tokens minus without prompt tokens", "surfaces": rows,
              "definitions": chosen}
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
