"""Charts: an SVG bar chart saved for a request. An artifact, undoable (a new chart replaces it on the
report; the file can be deleted). The key makes a retried render one effect, as for reports."""

from __future__ import annotations

import json
from html import escape
from pathlib import Path

from harness.paths import state_dir
from sandbox import db
from sandbox.stamp import current

WIDTH, BAR_H, GAP, LEFT = 520, 22, 8, 150


def svg(title: str, labels: list[str], values: list[float]) -> str:
    """A plain horizontal bar chart, no dependencies."""
    top = max([abs(float(v)) for v in values] or [0]) or 1.0
    height = 40 + len(labels) * (BAR_H + GAP)
    rows = []
    for i, (label, value) in enumerate(zip(labels, values)):
        y = 34 + i * (BAR_H + GAP)
        w = int((WIDTH - LEFT - 90) * abs(float(value)) / top)
        rows.append(f'<text x="{LEFT - 6}" y="{y + 15}" text-anchor="end" font-size="12">{escape(str(label))}</text>'
                    f'<rect x="{LEFT}" y="{y}" width="{w}" height="{BAR_H}" fill="#4a7bd0"/>'
                    f'<text x="{LEFT + w + 4}" y="{y + 15}" font-size="12">{float(value):,.2f}</text>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}">'
            f'<text x="8" y="20" font-size="14" font-weight="bold">{escape(title)}</text>{"".join(rows)}</svg>')


def render(request_id: str, title: str, labels: list[str], values: list[float], key: str,
           stamp: str | None = None) -> tuple[dict, bool]:
    """Returns (chart, created). A repeat of `key` creates nothing and returns the first chart."""
    if len(labels) != len(values):
        raise ValueError(f"labels ({len(labels)}) and values ({len(values)}) must be the same length")
    with db.connect() as conn:
        first = conn.execute("SELECT * FROM charts WHERE key = ?", (key,)).fetchone()
        if first:
            return dict(first), False
        folder = state_dir() / "charts" / request_id.replace("/", "_")
        folder.mkdir(parents=True, exist_ok=True)
        cur = conn.execute("INSERT INTO charts (request_id, title, labels_json, values_json, path, key, stamp, created_at) "
                           "VALUES (?, ?, ?, ?, '', ?, ?, ?)",
                           (request_id, title, json.dumps(labels), json.dumps(values), key, stamp or current(), db.NOW))
        path = folder / f"chart-{cur.lastrowid}.svg"
        path.write_text(svg(title, labels, values), encoding="utf-8")
        conn.execute("UPDATE charts SET path = ? WHERE id = ?", (str(path), cur.lastrowid))
        return dict(conn.execute("SELECT * FROM charts WHERE id = ?", (cur.lastrowid,)).fetchone()), True


def get(chart_id: int) -> dict | None:
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM charts WHERE id = ?", (chart_id,)).fetchone()
    return dict(row) if row else None


def for_request(request_id: str) -> list[dict]:
    with db.connect() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM charts WHERE request_id = ? ORDER BY id", (request_id,))]


def read_svg(chart: dict) -> str:
    try:
        return Path(chart["path"]).read_text(encoding="utf-8")
    except OSError:
        return ""
