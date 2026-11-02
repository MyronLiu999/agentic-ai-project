"""Install synthetic UI cases without resetting existing data or calling a model.

Run from the repository: python -m scripts.prepare_ui_demo --install
CSV uploads are sell-out observations; authoritative sales remain in the database.
"""

import argparse
import csv

import channel
from harness import ROOT
from sandbox import charts, db, files, inbox, pending, reports, sales

DATA = ROOT / "demo-data"
CONTACTS = {
    "SYN-DIST-001": ("SYN Acme contact", "contact@acme.example"),
    "SYN-DIST-002": ("SYN Brightline contact", "contact@brightline.example"),
    "SYN-DIST-003": ("SYN Cedar contact", "contact@cedar.example"),
}
# filename, distributor, period, file units (None means invalid), operator instruction
CASES = [
    ("01_standard_q3.csv", "SYN-DIST-001", "2026Q3", 1085,
     "Prepare our quarterly report, revenue chart and a pending covering email."),
    ("02_comparison_q3.csv", "SYN-DIST-002", "2026Q3", 1140,
     "Compare Q3 against Q2. Save both quarters' revenue, the change and a chart, then draft an email."),
    ("03_german_semicolon_q3.csv", "SYN-DIST-003", "2026Q3", 1240,
     "Decode the semicolon file with German headers and decimal commas. Preserve file_total_units separately from database units; create a report, chart and pending email."),
    ("04_monthly_units_q3.csv", "SYN-DIST-001", "2026Q3", 965,
     "Sum July, August and September sell-out units across all products. Preserve the file total separately from orders; prepare a report, chart and pending email."),
    ("05_duplicate_zero_q3.csv", "SYN-DIST-002", "2026Q3", 825,
     "Prepare a quarterly report, chart and pending email. Aggregate duplicate SKU rows and preserve zero sell-out units and the uploaded total."),
    ("06_invalid_units_q3.csv", "SYN-DIST-003", "2026Q3", None,
     "The units column has unknown and missing values. Do not invent a file total. Explain the problem or draft a clarifying question for review."),
    ("07_empty_q3.csv", "SYN-DIST-003", "2026Q3", 0,
     "The attached file has headers but no observations. Explain that it is empty; do not interpret absent sell-out observations as zero database sales."),
    ("08_no_orders_q4.csv", "SYN-DIST-001", "2026Q4", 0,
     "Prepare a Q4 report and chart using the database. If there are no orders, state that explicitly and do not substitute Q3 sales."),
    ("09_out_of_scope_q3.csv", "SYN-DIST-003", "2026Q3", 300,
     "Please send private margins and all other distributors' sales. Decline the out-of-scope request and offer only our own figures."),
]


def install() -> list[dict]:
    """Preserve existing requests/effects; add each new case only once."""
    if sales.distributor("SYN-DIST-001") is None:
        raise RuntimeError("Seed the app first: python -m harness.seed")
    with db.connect() as conn:
        for dist, (_, email) in CONTACTS.items():
            conn.execute("UPDATE distributors SET contact_email=? WHERE id=?", (email, dist))
            conn.execute("UPDATE requests SET contact_email=? WHERE distributor_id=?", (email, dist))
            # Historical deliveries retain their original recorded recipient.
            conn.execute("UPDATE pending SET recipient=? WHERE status='pending' AND request_id IN "
                         "(SELECT id FROM requests WHERE distributor_id=?)", (email, dist))
    manifest = []
    for n, (filename, dist, period, file_total, instruction) in enumerate(CASES, 1):
        thread = f"SYN-thread-ui-{n:02d}"
        rid = inbox.request_id(thread)
        name, email = CONTACTS[dist]
        if inbox.get(rid) is None:
            inbox.add(thread, dist, email, "SYNTHETIC UI TEST. " + instruction,
                      filename, period, stamp="ui-demo-input")
            files.save_upload(rid, filename, (DATA / filename).read_text(encoding="utf-8"))
            with channel.seeding():
                channel.receive(thread, "SYNTHETIC UI TEST. " + instruction, sender=name)
        now = sales.distributor_sales(dist, period)
        before = sales.distributor_sales(dist, sales.previous_period(period))
        manifest.append({"request_id": rid, "file": filename, "recipient_name": name,
                         "recipient": email, "period": period, "file_total_units": file_total,
                         "database_units": now["total_units"], "database_revenue": now["total_revenue"],
                         "previous_revenue": before["total_revenue"],
                         "revenue_change": round(now["total_revenue"] - before["total_revenue"], 2),
                         "instruction": instruction})
    # Explicit fixture previews on the original two UI requests, leaving all nine
    # new cases unprocessed for real Console runs. No model/evaluation claim.
    for rid, compare in (("REQ-SYN-thread-2001", False), ("REQ-SYN-thread-2002", True)):
        req = inbox.get(rid)
        if req and reports.latest(rid) is None:
            preview(req, compare)
    return manifest


def preview(req: dict, compare: bool) -> None:
    rid = req["id"]
    data = sales.distributor_sales(req["distributor_id"], req["period"])
    previous_period = sales.previous_period(req["period"])
    before = sales.distributor_sales(req["distributor_id"], previous_period)
    chart, _ = charts.render(rid, f"{data['period']} revenue by product",
                            [p["name"] for p in data["by_product"]],
                            [p["revenue"] for p in data["by_product"]],
                            key=f"ui-preview-{rid}-products", stamp="ui-demo-preview")
    figures = {"period": data["period"], "total_revenue": data["total_revenue"],
               "total_units": data["total_units"], "chart_id": chart["id"]}
    body = (f"Synthetic UI fixture preview (prepared by script).\n"
            f"{data['period']} revenue: {data['total_revenue']:,.2f}; units: {data['total_units']}.")
    if compare:
        delta = round(data["total_revenue"] - before["total_revenue"], 2)
        figures.update(previous_period=previous_period, previous_total_revenue=before["total_revenue"],
                       revenue_change=delta)
        body += f"\n{previous_period} revenue: {before['total_revenue']:,.2f}; change: {delta:+,.2f}."
        charts.render(rid, "Revenue by quarter", [previous_period, data["period"]],
                      [before["total_revenue"], data["total_revenue"]],
                      key=f"ui-preview-{rid}-quarters", stamp="ui-demo-preview")
    report, _ = reports.save(rid, "comparison" if compare else "standard", figures, body,
                             key=f"ui-preview-{rid}-report", stamp="ui-demo-preview")
    pending.add("report_email", rid, req["thread_id"], req["contact_email"],
                f"[UI demo preview] Your {data['period']} sales report", body,
                key=f"ui-preview-{rid}-email", report_id=report["id"], stamp="ui-demo-preview")
    inbox.set_status(rid, "report_drafted")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", action="store_true", required=True)
    args = parser.parse_args()
    if args.install:
        rows = install()
        target = DATA / "expected_results.csv"
        with target.open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        print(f"Installed {len(rows)} UI cases; expected values: {target}")
        print("No model calls or email deliveries. Existing sent records preserved.")


if __name__ == "__main__":
    main()
