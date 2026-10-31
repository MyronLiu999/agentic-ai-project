"""The sandbox's own rules (claudea): margins reach no agent code, charts are keyed artifacts, and a task's
history seeds work already done. No model."""

import ast
import unittest
from pathlib import Path

from harness import ROOT
from harness.tasks import load
from sandbox import charts, inbox, pending, reports, seed
from tests.support import ScratchTest


def imports_of(path: Path) -> set[str]:
    names = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names |= {f"{node.module}.{a.name}" for a in node.names}
    return names


class MarginsStayPrivateTest(unittest.TestCase):
    def test_no_agent_code_imports_the_margins_module(self):
        files = sorted((ROOT / "agent").rglob("*.py")) + sorted((ROOT / "checks").glob("*.py"))
        self.assertTrue(files)
        for f in files:
            found = {n for n in imports_of(f) if n == "sandbox.margins" or n.endswith(".margins")}
            self.assertFalse(found, f"{f.relative_to(ROOT)} imports {found}")

    def test_nothing_the_agent_can_reach_imports_it_either(self):
        # the sandbox modules the tools wrap must not pull margins in behind them
        for name in ("sales", "inbox", "files", "reports", "pending", "charts"):
            self.assertNotIn("sandbox.margins", imports_of(ROOT / "sandbox" / f"{name}.py"), name)


class DomainSandboxTest(ScratchTest):
    def test_a_chart_is_an_svg_and_a_repeated_key_is_one_effect(self):
        seed.reset()
        seed.seed(None)
        rid = inbox.request_id("SYN-thread-2001")
        first, created = charts.render(rid, "Q3 revenue", ["Widget S", "Widget M"], [100.0, 50.5], key="c1")
        again, created_again = charts.render(rid, "Q3 revenue", ["x"], [1.0], key="c1")
        self.assertEqual((created, created_again, first["id"]), (True, False, again["id"]))
        self.assertIn("<svg", charts.read_svg(first))
        self.assertEqual(len(charts.for_request(rid)), 1)
        with self.assertRaises(ValueError):
            charts.render(rid, "bad", ["a", "b"], [1.0], key="c2")

    def test_reset_removes_charts_and_uploads(self):
        seed.reset()
        seed.seed(None)
        charts.render(inbox.request_id("SYN-thread-2001"), "t", ["a"], [1.0], key="c")
        seed.reset()
        self.assertFalse((self.state_dir / "charts").exists())
        self.assertFalse((self.state_dir / "uploads").exists())

    def test_history_seeds_a_report_and_a_sent_email(self):
        task = load(ROOT / "tasks" / "status_question_done_work.yaml")
        seed.reset()
        seed.seed(task)
        rid = inbox.request_id(task["input"]["thread"])
        self.assertEqual(inbox.get(rid)["status"], "done")
        self.assertGreater(reports.figures(reports.latest(rid))["total_revenue"], 0)
        self.assertEqual([p["status"] for p in pending.for_request(rid)], ["sent"])

    def test_operator_text_names_requests_by_distributor(self):
        seed.reset()
        seed.seed(None)
        self.assertEqual([r["id"] for r in inbox.mentioned("What did we send Acme?")], ["REQ-SYN-thread-2001"])
        self.assertEqual(inbox.mentioned("anything open?"), [])

    def test_every_task_seeds(self):
        for path in sorted((ROOT / "tasks").rglob("*.yaml")):
            seed.reset()
            seed.seed(load(path))
            self.assertTrue(inbox.all_requests(), path.name)


if __name__ == "__main__":
    unittest.main()
