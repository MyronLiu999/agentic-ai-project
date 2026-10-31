"""The product without the agent (owner: claudea): the requests and the pending records waiting to be
sent, one request with its file, thread, reports, charts and a form to email a report by hand, and a
query page with a chart and the change from last quarter. Everything goes through sandbox/ modules; nothing
here imports the agent. A write made here is stamped "manual", and a reply the operator sends goes
out as the operator's."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse, Response

import channel
from app import templates
from sandbox import charts, db, files, inbox, pending, reports, sales

router = APIRouter()


@router.get("/")
def home(request: Request):
    return templates.TemplateResponse(request, "home.html", {
        "page": "home", "requests": inbox.all_requests(), "pending": pending.all_pending("pending")})


@router.get("/requests/{rid}")
def request_page(request: Request, rid: str):
    req = inbox.get(rid)
    if not req:
        raise HTTPException(404, f"no request {rid}")
    upload = files.read_upload(rid, req["file_name"]) if req["file_name"] else ""
    return templates.TemplateResponse(request, "request.html", {
        "page": "home", "req": req, "upload": upload, "messages": channel.messages(req["thread_id"]),
        "reports": reports.for_request(rid), "pending": pending.for_request(rid),
        "charts": [c | {"svg": charts.read_svg(c)} for c in charts.for_request(rid)],
        "draft": _hand_draft(req)})


def _hand_draft(req: dict) -> dict:
    """What the hand form starts with: the request's own contact and figures from the database."""
    body = ""
    if req["period"]:
        try:
            data = sales.distributor_sales(req["distributor_id"], req["period"])
            body = (f"Hello,\n\nYour {req['period']} revenue was {data['total_revenue']:,.2f} on "
                    f"{data['total_units']} units.\n\nThe sales analytics team")
        except ValueError:
            pass
    return {"recipient": req["contact_email"], "subject": f"Your {req['period'] or ''} sales report".replace("  ", " "),
            "body": body}


@router.post("/requests/{rid}/email")
def email_by_hand(rid: str, subject: str = Form(...), body: str = Form(...)):
    """The core task by hand: the operator writes and sends the report email. It is recorded as a pending
    record stamped "manual" and marked sent, so the request page shows what left. The recipient is always the
    request's own contact, never typed."""
    req = inbox.get(rid)
    if not req:
        raise HTTPException(404, f"no request {rid}")
    latest = reports.latest(rid)
    record, _ = pending.add("report_email", rid, req["thread_id"], req["contact_email"], subject, body,
                            key=f"manual-{secrets.token_hex(6)}", report_id=latest["id"] if latest else None,
                            stamp="manual")
    channel.send(req["thread_id"], body, sender="operator")
    pending.mark_sent(record["id"])
    inbox.set_status(rid, "done")
    return RedirectResponse(f"/requests/{rid}", status_code=303)


@router.get("/charts/{chart_id}.svg")
def chart_svg(chart_id: int):
    chart = charts.get(chart_id)
    if not chart:
        raise HTTPException(404, "no such chart")
    return Response(charts.read_svg(chart), media_type="image/svg+xml")


@router.post("/pending/{pid}/send")
def send_pending(pid: int):
    """Do a pending record by hand: the operator sends it, as the operator."""
    record = pending.get(pid)
    if not record or record["status"] != "pending":
        raise HTTPException(404, "no such pending record, or already sent")
    channel.send(record["thread_id"], record["body"], sender="operator")
    pending.mark_sent(pid)
    if record["kind"] == "report_email":
        # the report has gone out: the request is done, as the hand email form marks it
        inbox.set_status(record["request_id"], "done")
    return RedirectResponse(f"/requests/{record['request_id']}", status_code=303)


@router.post("/pending/{pid}/discard")
def discard_pending(pid: int):
    """Undo a draft by hand: the operator discards a pending record, which is then never sent."""
    record = pending.get(pid)
    if not record or not pending.discard(pid):
        raise HTTPException(404, "no such pending record, or already sent or discarded")
    return RedirectResponse(f"/requests/{record['request_id']}", status_code=303)


@router.get("/query")
def query_page(request: Request, distributor: str = "SYN-DIST-001", period: str = "2026Q3"):
    data, before, error, chart = None, None, None, ""
    try:
        data = sales.distributor_sales(distributor, period)
        before = sales.distributor_sales(distributor, sales.previous_period(period))
        chart = charts.svg(f"{distributor} {period} revenue by product", [r["name"] for r in data["by_product"]],
                           [r["revenue"] for r in data["by_product"]])
    except (ValueError, IndexError) as exc:
        error = str(exc)
    prev = {r["sku"]: r for r in (before or {}).get("by_product", [])}
    rows = [r | {"prev_revenue": prev.get(r["sku"], {}).get("revenue")} for r in (data or {}).get("by_product", [])]
    return templates.TemplateResponse(request, "query.html", {
        "page": "home", "data": data, "before": before, "rows": rows, "error": error, "distributor": distributor,
        "period": period, "chart": chart, "distributors": [d for d in _distributors()]})


def _distributors() -> list[dict]:
    with db.connect() as conn:
        return [dict(r) for r in conn.execute("SELECT id, name FROM distributors ORDER BY id")]
