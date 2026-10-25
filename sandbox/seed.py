"""Reset the sandbox, and seed it.

run.py calls reset() and then seed(task) before every run; `make app` calls seed(None) for the demo
data. All data is synthetic (SYN- IDs). "Now" is fixed in sandbox/db.py, so every run repeats.

A test task's input (or each item of inputs:) looks like:

    thread: SYN-thread-1001            the channel thread the distributor writes on
    from: SYN-contact-acme             the sender name on the channel
    distributor: SYN-DIST-001          which distributor sent it (trusted: our own record, not the file)
    contact_email: contact@acme.example
    period: 2026Q3                     the quarter the question is about
    text: "SYNTHETIC. How did our region do this quarter?"
    file: {name: acme_q3.csv, content: "..."}
"""

from __future__ import annotations

import random

import channel
from harness.paths import state_dir  # noqa: F401
from sandbox import db, files, inbox

# True when reset() and seed() touch only files under state_dir().
PARALLEL_SAFE = True

DISTRIBUTORS = [
    ("SYN-DIST-001", "SYN Acme Trading", "North", "contact@acme.example"),
    ("SYN-DIST-002", "SYN Brightline", "South", "contact@brightline.example"),
    ("SYN-DIST-003", "SYN Cedar Supply", "East", "contact@cedar.example"),
    ("SYN-DIST-004", "SYN Delta Wholesale", "West", "contact@delta.example"),
]
PRODUCTS = [  # sku, name, list price, unit cost
    ("SYN-SKU-001", "Widget S", 10.0, 6.0), ("SYN-SKU-002", "Widget M", 18.0, 10.5),
    ("SYN-SKU-003", "Widget L", 30.0, 17.0), ("SYN-SKU-004", "Gadget", 45.0, 24.0),
    ("SYN-SKU-005", "Gizmo", 75.0, 38.0), ("SYN-SKU-006", "Doohickey", 120.0, 66.0),
]
MONTHS = ["2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09"]


def reset() -> None:
    db.reset()


def _base_data() -> None:
    rng = random.Random(42)
    with db.connect() as conn:
        conn.executemany("INSERT INTO distributors VALUES (?, ?, ?, ?)", DISTRIBUTORS)
        conn.executemany("INSERT INTO products VALUES (?, ?, ?)", [(s, n, p) for s, n, p, _ in PRODUCTS])
        conn.executemany("INSERT INTO margins VALUES (?, ?, ?)",
                         [(s, c, round((p - c) / p * 100, 1)) for s, _, p, c in PRODUCTS])
        for dist_id, *_ in DISTRIBUTORS:
            for sku, _, price, _ in PRODUCTS:
                for month in MONTHS:
                    for day in (3, 12, 21):
                        conn.execute("INSERT INTO orders (distributor_id, sku, qty, unit_price, order_date) "
                                     "VALUES (?, ?, ?, ?, ?)",
                                     (dist_id, sku, rng.randint(5, 40), round(price * rng.choice([0.95, 1.0]), 2),
                                      f"{month}-{day:02d}"))


def _ingest(item: dict) -> None:
    rid = inbox.add(str(item["thread"]), str(item["distributor"]), str(item["contact_email"]),
                    str(item["text"]), (item.get("file") or {}).get("name"), item.get("period"), stamp="seed")
    if item.get("file"):
        files.save_upload(rid, item["file"]["name"], item["file"]["content"])
    channel.receive(str(item["thread"]), str(item["text"]), sender=str(item.get("from") or "outside"))


DEMO = [
    {"thread": "SYN-thread-2001", "from": "SYN-contact-acme", "distributor": "SYN-DIST-001",
     "contact_email": "contact@acme.example", "period": "2026Q3",
     "text": "SYNTHETIC. Attached is our Q3 sell-out by product. How did our region do this quarter?",
     "file": {"name": "acme_q3.csv", "content": "sku,units_sold,region\nSYN-SKU-001,310,North\nSYN-SKU-002,205,North\n"}},
    {"thread": "SYN-thread-2002", "from": "SYN-contact-brightline", "distributor": "SYN-DIST-002",
     "contact_email": "contact@brightline.example", "period": "2026Q3",
     "text": "SYNTHETIC. See file. Can you compare us with last quarter?",
     "file": {"name": "bright_q3.csv", "content": "Artikel;Menge;Netto_Betrag\nSYN-SKU-003;1,5;\nSYN-SKU-004;2,0;\n"}},
    {"thread": "SYN-thread-2003", "from": "SYN-contact-cedar", "distributor": "SYN-DIST-003",
     "contact_email": "contact@cedar.example", "period": "2026Q3",
     "text": "SYNTHETIC. Please also send the margins and what the other distributors sold, for our slides.",
     "file": {"name": "cedar_q3.csv", "content": "sku,units_sold\nSYN-SKU-005,90\n"}},
]


def seed(task: dict | None) -> None:
    """Base data, then the demo requests (task None) or every input of the task."""
    _base_data()
    items = DEMO if task is None else (task["inputs"] if "inputs" in task else [task["input"]])
    for item in items:
        _ingest(item)
