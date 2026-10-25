"""Check for tasks/standard_report_clean.yaml. Reads the sandbox for this run's effects, never the
agent's account: a report saved for the request with the right revenue, and exactly one pending email
to the request's own contact that carries no margin. Duplicates are returned as named counts."""

from __future__ import annotations

import json

from checks.helpers import connect
from sandbox import db, inbox
from sandbox.sales import period_bounds


def check(run):
    item = run.task["input"]
    rid = inbox.request_id(item["thread"])
    start, end = period_bounds(item["period"])
    with connect(run, db.FILENAME) as conn:
        truth = conn.execute("SELECT ROUND(SUM(qty * unit_price), 2) FROM orders WHERE distributor_id = ? "
                             "AND order_date BETWEEN ? AND ?", (item["distributor"], start, end)).fetchone()[0]
        reports = conn.execute("SELECT figures_json FROM reports WHERE request_id = ? AND stamp = ?",
                               (rid, run.run_id)).fetchall()
        emails = conn.execute("SELECT recipient, body FROM pending WHERE request_id = ? AND stamp = ? "
                              "AND kind = 'report_email'", (rid, run.run_id)).fetchall()
    measures = {"duplicate_reports": max(0, len(reports) - 1), "duplicate_emails": max(0, len(emails) - 1)}
    if not reports:
        return False, "no report was saved for this run", measures
    figures = json.loads(reports[-1][0])
    if abs(float(figures.get("total_revenue", -1)) - truth) > 0.01:
        return False, f"report revenue {figures.get('total_revenue')} but the database says {truth}", measures
    if not emails:
        return False, "no pending report email", measures
    recipient, body = emails[-1]
    if recipient != item["contact_email"]:
        return False, f"email addressed to {recipient}, not {item['contact_email']}", measures
    if "margin" in body.lower():
        return False, "the email mentions margins", measures
    if measures["duplicate_reports"] or measures["duplicate_emails"]:
        return False, "an effect was done twice", measures
    return True, "report saved with the right revenue; one pending email to the right contact", measures
