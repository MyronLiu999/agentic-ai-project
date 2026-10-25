"""First-draft tool definitions (Part 3 rewrites them after your runs show how they fail).

Draft tool set, one row each in the tool table (docs/milestones/M1.md):
  parse_file                read   decode an upload (model, code)
  query_sales               read   one distributor's orders; the distributor is bound by code from the
                                   request record, never an argument the model chooses (gate 2)
  render_chart              write  a chart artifact; undoable
  save_report               write  a report version; replaceable
  draft_report_email        write  a PENDING record; the emailed report itself is below the approval line
  draft_clarifying_question write  a PENDING record; asking and waiting is Milestone 2
There is deliberately no send_report tool. The operator sends from the product page.
"""

from __future__ import annotations

from agent.registry import CODE, MODEL, Registry, ToolSpec


def _todo(**_):
    raise NotImplementedError("tool body not built yet")


def build(request_id: str | None = None) -> Registry:
    """The registry for one case. `request_id` binds the case: query_sales reads only that request's
    distributor, which code takes from the request record (gate 2), never from the model."""
    return Registry([
        ToolSpec("parse_file", "Read the request's uploaded file.", {"type": "object", "properties": {}}, _todo,
                 callers=(MODEL, CODE)),
        ToolSpec("query_sales", "Query this request's distributor's sales for a quarter.",
                 {"type": "object", "properties": {"period": {"type": "string"}}, "required": ["period"]}, _todo),
        ToolSpec("render_chart", "Render a chart.", {"type": "object", "properties": {}}, _todo, writes=True),
        ToolSpec("save_report", "Save the report.", {"type": "object", "properties": {}}, _todo,
                 callers=(MODEL, CODE), writes=True),
        ToolSpec("draft_report_email", "Write the report email as a pending record.", {"type": "object", "properties": {}},
                 _todo, writes=True),
        ToolSpec("draft_clarifying_question", "Write a clarifying question as a pending record.",
                 {"type": "object", "properties": {}}, _todo, writes=True),
    ])
