"""The product without the agent (owner: claudea): the requests and the pending records waiting to be
sent, one request with its file, thread, reports, charts and a form to email a report by hand, and a
query page with a chart and the change from last quarter. Everything goes through sandbox/ modules; nothing
here imports the agent. A write made here is stamped "manual", and a reply the operator sends goes
out as the operator's."""

from __future__ import annotations

import re
import secrets
import base64

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse, Response

import channel
from app import templates
from sandbox import charts, db, email_packages, files, inbox, pending, reports, sales

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
        "page": "home", "req": req, "upload": upload, "messages": thread_messages(req["thread_id"]),
        "reports": reports.for_request(rid), "pending": [p | {"email_charts": email_packages.prepare(p)["charts"]}
                                                       for p in pending.for_request(rid)],
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
    return _deliver(record["id"])


def _manual_package(rid: str, subject: str, body: str) -> dict:
    req = inbox.get(rid)
    if not req:
        raise HTTPException(404, "no such request")
    latest = reports.latest(rid)
    return email_packages.prepare({"kind": "report_email", "request_id": rid, "status": "pending",
                                   "report_id": latest["id"] if latest else None,
                                   "recipient": req["contact_email"], "subject": subject, "body": body})


@router.post("/requests/{rid}/email/download")
def download_manual_email(rid: str, subject: str = Form(...), body: str = Form(...)):
    return _email_response(_manual_package(rid, subject, body))


def _email_response(payload: dict):
    return Response(email_packages.eml(payload), media_type="message/rfc822",
                    headers={"Content-Disposition": 'attachment; filename="sales-report.eml"'})


@router.get("/pending/{pid}/email.eml")
def download_pending_email(pid: int):
    record = pending.get(pid)
    if not record:
        raise HTTPException(404, "no such pending record")
    return _email_response(email_packages.prepare(record))


@router.get("/pending/{pid}/charts/{index}.png")
def email_chart(pid: int, index: int):
    record = pending.get(pid)
    if not record:
        raise HTTPException(404, "no such pending record")
    images = email_packages.prepare(record)["charts"]
    if not 0 <= index < len(images):
        raise HTTPException(404, "no such email chart")
    return Response(base64.b64decode(images[index]["png"]), media_type="image/png")


def thread_messages(thread_id: str) -> list[dict]:
    messages = channel.messages(thread_id)
    attachments = email_packages.message_charts([m.id for m in messages])
    return [m.as_dict() | {"from_outside": m.from_outside, "email_charts": attachments.get(m.id, [])}
            for m in messages]


@router.get("/charts/{chart_id}.svg")
def chart_svg(chart_id: int):
    chart = charts.get(chart_id)
    if not chart:
        raise HTTPException(404, "no such chart")
    return Response(charts.read_svg(chart), media_type="image/svg+xml")


@router.post("/pending/{pid}/send")
def send_pending(pid: int):
    """Do a pending record by hand: the operator sends it, as the operator."""
    return _deliver(pid)


def _deliver(pid: int):
    record = pending.claim_send(pid)
    if not record:
        raise HTTPException(404, "no such pending record, or unavailable for sending")
    try:
        package = email_packages.freeze(record)
        text = record["body"]
        if package["charts"]:
            text += "\n\nCharts included:\n" + "\n".join(
                f"{c['title']}: /pending/{pid}/charts/{i}.png" for i, c in enumerate(package["charts"]))
        message = channel.send(record["thread_id"], text, sender="operator")
        email_packages.link_message(pid, message.id)
        if not pending.complete_send(pid):
            raise RuntimeError("delivery claim could not be completed")
    except Exception as exc:
        pending.fail_send(pid)
        raise HTTPException(502, "Delivery could not be confirmed. Check the thread before sending another message; "
                            "this record cannot be retried automatically.") from exc
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
        "page": "query", "data": data, "before": before, "rows": rows, "error": error, "distributor": distributor,
        "period": period, "chart": chart, "distributors": [d for d in _distributors()]})


def _distributors() -> list[dict]:
    with db.connect() as conn:
        return [dict(r) for r in conn.execute("SELECT id, name FROM distributors ORDER BY id")]


# -- what the console shows under an agent reply ----------------------------------------------

REQUEST_ID = re.compile(r"\bREQ-[A-Za-z0-9][A-Za-z0-9_-]*[A-Za-z0-9]")
FIGURE_LABELS = (("period", "Period"), ("total_revenue", "Revenue"), ("total_units", "Units (database)"),
                 ("file_total_units", "Units (file)"), ("previous_period", "Previous period"),
                 ("previous_total_revenue", "Previous revenue"), ("revenue_change", "Change"))


def request_ids(*texts: str) -> list[str]:
    """The requests a reply is about, in the order it names them."""
    seen = []
    for text in texts:
        for rid in REQUEST_ID.findall(text or ""):
            if rid not in seen:
                seen.append(rid)
    return seen


def request_cards(rids: list[str]) -> list[dict]:
    """Each named request as it stands now: its latest report's figures, its charts and its drafts.
    Read from sandbox/ only, so the card shows what is really saved, not what the reply says."""
    cards = []
    for rid in rids:
        req = inbox.get(rid)
        if not req:
            continue
        latest = reports.latest(rid)
        figures = reports.figures(latest) if latest else {}
        cards.append({
            "req": req,
            "figures": [(label, _show(key, figures[key])) for key, label in FIGURE_LABELS if key in figures],
            "report": latest,
            "charts": [c | {"svg": charts.read_svg(c)} for c in charts.for_request(rid)][-1:],
            "pending": pending.for_request(rid)[-2:],
        })
    return cards


def _show(key: str, value) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        text = f"{value:,.2f}" if "revenue" in key else f"{value:,}"
        return f"+{text}" if key == "revenue_change" and value > 0 else text
    return str(value)


def open_requests() -> list[dict]:
    return [r for r in inbox.all_requests() if r["status"] != "done"]
