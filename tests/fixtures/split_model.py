"""Free role model driven only by request scope, handoffs and tool results."""

import json

from harness.client import Usage
from tests.fixtures.agent_milestone_model import MilestoneModel


class SplitModel(MilestoneModel):
    def __init__(self, settings=None):
        super().__init__(settings)
        self.requests = []
        self.bad_return = False
        self.unauthorized_read_role = False
        self.bad_writer_type = False

    def create(self, *, system, messages, tools):
        if not system.startswith("Split role:"):
            return super().create(system=system, messages=messages, tools=tools)
        self.calls += 1
        self.requests.append({"system": system, "messages": messages, "tools": tools})
        scope = json.loads(messages[0]["content"])
        request = scope["request"]
        results, calls = {}, {}
        for message in messages:
            if not isinstance(message["content"], list):
                continue
            for block in message["content"]:
                if block["type"] == "tool_use":
                    calls[block["id"]] = block
                elif block["type"] == "tool_result":
                    result = json.loads(block["content"])
                    if not result["ok"]:
                        raise AssertionError(result)
                    results[calls[block["tool_use_id"]]["name"]] = result["output"]
        def call(name, args):
            return [{"type": "tool_use", "id": f"split-call-{self.calls}", "name": name, "input": args}], \
                "tool_use", "says-done", Usage(100, 50)
        def finish(result):
            if self.bad_writer_type and "report_id" in result:
                result["report_id"] = True
            value = {"result": result, "status": "found", "searched": ["invented-search"],
                     "not_searched": ["invented-omission"], "spent": {"tool_calls": 999, "tokens": 999},
                     "not_determined": []}
            if self.bad_return:
                del value["status"]
            return [{"type": "text", "text": json.dumps(value)}], "end_turn", "says-done", Usage(100, 50)
        if system.startswith("Split role: analyst"):
            if self.unauthorized_read_role:
                return call("save_report", {"kind": "batch", "figures": {}, "body": "Unauthorized"})
            if "parse_file" not in results:
                return call("parse_file", {})
            if "query_sales" not in results:
                return call("query_sales", {"period": request["period"]})
            parsed, queried = results["parse_file"], results["query_sales"]
            units_index = [str(c).lower() for c in parsed["columns"]].index("units_sold")
            return finish({"request_id": request["id"], "figures": {
                "period": request["period"], "total_revenue": queried["total_revenue"],
                "total_units": queried["total_units"], "file_row_count": parsed["row_count"],
                "file_total_units": sum(int(row[units_index]) for row in parsed["rows"])}})
        figures = scope["analyst_return"]["result"]["figures"]
        if "render_chart" not in results:
            return call("render_chart", {"title": request["period"] + " revenue", "labels": ["Total"],
                                         "values": [figures["total_revenue"]]})
        if "save_report" not in results:
            return call("save_report", {"kind": "batch", "figures": {
                **figures, "chart_id": results["render_chart"]["chart_id"]},
                "body": f"Quarter {figures['period']}: revenue {figures['total_revenue']:.2f}, "
                        f"units {figures['total_units']}."})
        if "draft_report_email" not in results:
            return call("draft_report_email", {"recipient": request["contact_email"],
                "report_id": results["save_report"]["report_id"], "subject": request["period"] + " report",
                "body": f"Your {figures['period']} revenue was {figures['total_revenue']:.2f} "
                        f"on {figures['total_units']} units."})
        return finish({"request_id": request["id"], "report_id": results["save_report"]["report_id"],
                       "pending_id": results["draft_report_email"]["pending_id"],
                       "chart_id": results["render_chart"]["chart_id"]})
