"""Self-contained report emails with request-scoped, frozen PNG chart images."""

import base64
from email.message import EmailMessage
from email.policy import SMTP
from html import escape
from io import BytesIO
import json

from sandbox import charts, db, reports


def chart_png(chart: dict) -> bytes:
    from PIL import Image, ImageDraw, ImageFont

    labels = json.loads(chart["labels_json"])
    values = [float(v) for v in json.loads(chart["values_json"])]
    image = Image.new("RGB", (1000, 100 + 48 * max(1, len(labels))), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 20)
    except OSError:
        font = ImageFont.load_default(size=20)
    draw.text((20, 20), chart["title"], fill="#182334", font=font)
    top = max([abs(v) for v in values] or [0]) or 1
    negative = any(v < 0 for v in values)
    origin, span = (560, 260) if negative else (240, 560)
    if not labels:
        draw.text((20, 65), "No orders for this period", fill="#555555", font=font)
    for i, (label, value) in enumerate(zip(labels, values)):
        y = 70 + i * 48
        draw.text((20, y), str(label)[:24], fill="#182334", font=font)
        end = origin + int(span * value / top)
        draw.rectangle((min(origin, end), y, max(origin, end), y + 28), fill="#4a7bd0")
        draw.text((max(origin, end) + 8, y), f"{value:,.2f}", fill="#182334", font=font)
    stream = BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


def saved(pid: int) -> dict | None:
    with db.connect() as conn:
        row = conn.execute("SELECT payload_json FROM email_packages WHERE pending_id=?", (pid,)).fetchone()
    return json.loads(row[0]) if row else None


def prepare(record: dict) -> dict:
    frozen = saved(record["id"]) if record.get("id") else None
    if frozen:
        return frozen
    selected = {}
    if record["kind"] == "report_email" and record.get("status", "pending") == "pending":
        for chart in charts.for_request(record["request_id"]):
            selected[chart["title"]] = chart
        # Preserve the primary chart bound to this saved report.
        if record.get("report_id"):
            report = next((r for r in reports.for_request(record["request_id"])
                           if r["id"] == record["report_id"]), None)
            if report is None:
                raise ValueError("The email report does not belong to this request.")
            chart_id = reports.figures(report).get("chart_id")
            if chart_id is not None:
                chart = charts.get(chart_id)
                if not chart or chart["request_id"] != record["request_id"]:
                    raise ValueError("The report chart does not belong to this request.")
                selected[chart["title"]] = chart
    images = [{"title": c["title"], "filename": f"chart-{c['id']}.png",
               "png": base64.b64encode(chart_png(c)).decode("ascii")}
              for c in selected.values()]
    return {"recipient": record["recipient"], "subject": record["subject"],
            "body": record["body"], "charts": images}


def freeze(record: dict) -> dict:
    payload = prepare({**record, "status": "pending"})
    with db.connect() as conn:
        conn.execute("INSERT OR IGNORE INTO email_packages (pending_id, payload_json) VALUES (?, ?)",
                     (record["id"], json.dumps(payload)))
    return saved(record["id"])


def link_message(pid: int, message_id: int) -> None:
    with db.connect() as conn:
        conn.execute("UPDATE email_packages SET message_id=? WHERE pending_id=?", (message_id, pid))


def message_charts(message_ids: list[int]) -> dict:
    if not message_ids:
        return {}
    with db.connect() as conn:
        rows = conn.execute("SELECT pending_id, message_id, payload_json FROM email_packages WHERE message_id IN ("
                            + ",".join("?" for _ in message_ids) + ")", message_ids).fetchall()
    return {r["message_id"]: [{"title": c["title"],
                              "url": f"/pending/{r['pending_id']}/charts/{i}.png"}
                             for i, c in enumerate(json.loads(r["payload_json"])["charts"])] for r in rows}


def eml(payload: dict) -> bytes:
    message = EmailMessage(policy=SMTP)
    message["To"] = payload["recipient"]
    message["Subject"] = payload["subject"]
    message["X-Unsent"] = "1"
    message.set_content(payload["body"])
    content = "<html><body><div style='white-space:pre-wrap'>" + escape(payload["body"]) + "</div>"
    for i, chart in enumerate(payload["charts"]):
        content += f"<h3>{escape(chart['title'])}</h3><img src='cid:chart-{i}' alt='{escape(chart['title'], quote=True)}' style='max-width:100%'>"
    message.add_alternative(content + "</body></html>", subtype="html")
    html = message.get_payload()[-1]
    for i, chart in enumerate(payload["charts"]):
        html.add_related(base64.b64decode(chart["png"]), maintype="image", subtype="png",
                         cid=f"<chart-{i}>", filename=chart["filename"], disposition="inline")
    return message.as_bytes()
