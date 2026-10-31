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


def surfaces() -> dict[str, list[dict]]:
    return {"first_draft": FIRST_DRAFT, "rewrite": build(None).definitions()}


def measure(client_factory) -> dict:
    rows = {}
    for name, definitions in surfaces().items():
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
    args = parser.parse_args(argv)
    if args.show_definitions:
        print(json.dumps(surfaces(), indent=2, sort_keys=True))
        return 0

    settings = load_settings(ROOT / "settings.yaml")
    if settings.provider not in REAL_BACKENDS or not settings.model:
        print("settings.yaml must name a real provider and model", file=sys.stderr)
        return 1
    prices = PriceSheet(ROOT / "pricing.yaml")

    def client_factory():
        return ModelClient(make_backend(settings.provider, settings), prices)

    try:
        rows = measure(client_factory)
    except Exception as exc:
        print(f"definition-cost measurement failed: {type(exc).__name__}: {str(exc)[:500]}", file=sys.stderr)
        return 1
    report = {"measured_at": datetime.now(timezone.utc).isoformat(),
              "provider": settings.provider, "requested_model": settings.model,
              "method": "with prompt tokens minus without prompt tokens", "surfaces": rows,
              "definitions": surfaces()}
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
