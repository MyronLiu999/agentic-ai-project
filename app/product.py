"""The product without the agent: the requests, one request with its file and thread, a query page
with bars, and a form to send an email by hand. Everything goes through sandbox/ modules; nothing
here imports the agent. A write made here is stamped "manual", and a reply the operator sends goes
out as the operator's."""

from __future__ import annotations

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

import channel
from app import templates
from sandbox import files, inbox, pending, reports, sales

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
        "reports": reports.for_request(rid), "pending": pending.for_request(rid)})


@router.post("/pending/{pid}/send")
def send_pending(pid: int):
    """Do a pending record by hand: the operator sends it, as the operator."""
    record = pending.get(pid)
    if not record or record["status"] != "pending":
        raise HTTPException(404, "no such pending record, or already sent")
    channel.send(record["thread_id"], record["body"], sender="operator")
    pending.mark_sent(pid)
    return RedirectResponse(f"/requests/{record['request_id']}", status_code=303)


@router.get("/query")
def query_page(request: Request, distributor: str = "SYN-DIST-001", period: str = "2026Q3"):
    data, error = None, None
    try:
        data = sales.distributor_sales(distributor, period)
    except ValueError as exc:
        error = str(exc)
    top = max((r["revenue"] for r in data["by_product"]), default=0) if data else 0
    return templates.TemplateResponse(request, "query.html", {
        "page": "home", "data": data, "error": error, "distributor": distributor, "period": period, "top": top})
