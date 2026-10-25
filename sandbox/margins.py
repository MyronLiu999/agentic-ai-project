"""The company's margins: private. Only the operator's own pages may import this module. No agent
tool, workflow or report builder does, so a distributor's file cannot steer a margin out
(the trifecta's private-data leg). Add a test that asserts it if you keep this rule."""

from __future__ import annotations

from sandbox import db


def by_sku() -> list[dict]:
    with db.connect() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM margins ORDER BY sku")]
