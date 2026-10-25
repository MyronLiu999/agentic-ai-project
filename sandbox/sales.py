"""Reads of the sales database that are safe to hand a distributor's request: one distributor's
own orders, never another's, never a margin. The agent's query tool wraps these; the distributor
is bound by your code from the request record, not chosen by the model (gate 2)."""

from __future__ import annotations

from sandbox import db

QUARTERS = {"Q1": ("01-01", "03-31"), "Q2": ("04-01", "06-30"), "Q3": ("07-01", "09-30"), "Q4": ("10-01", "12-31")}


def period_bounds(period: str) -> tuple[str, str]:
    """'2026Q3' -> ('2026-07-01', '2026-09-30')."""
    year, quarter = period[:4], period[4:].upper()
    if not (year.isdigit() and quarter in QUARTERS):
        raise ValueError(f"period {period!r} must look like 2026Q3 (year, then Q1 to Q4)")
    start, end = QUARTERS[quarter]
    return f"{year}-{start}", f"{year}-{end}"


def previous_period(period: str) -> str:
    year, q = int(period[:4]), int(period[5])
    return f"{year - 1}Q4" if q == 1 else f"{year}Q{q - 1}"


def distributor(distributor_id: str) -> dict | None:
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM distributors WHERE id = ?", (distributor_id,)).fetchone()
    return dict(row) if row else None


def distributor_sales(distributor_id: str, period: str) -> dict:
    """One distributor's orders in a quarter, by product: units and revenue, and the totals."""
    start, end = period_bounds(period)
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT o.sku, p.name, SUM(o.qty) AS units, ROUND(SUM(o.qty * o.unit_price), 2) AS revenue "
            "FROM orders o JOIN products p ON p.sku = o.sku "
            "WHERE o.distributor_id = ? AND o.order_date BETWEEN ? AND ? GROUP BY o.sku ORDER BY o.sku",
            (distributor_id, start, end)).fetchall()
    by_product = [dict(r) for r in rows]
    return {"distributor_id": distributor_id, "period": period, "by_product": by_product,
            "total_units": sum(r["units"] for r in by_product),
            "total_revenue": round(sum(r["revenue"] for r in by_product), 2)}
