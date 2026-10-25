import unittest

from sandbox import inbox, margins, pending, reports, sales, seed
from tests.support import ScratchTest


class SandboxTest(ScratchTest):
    def setUp(self):
        super().setUp()
        seed.reset()
        seed.seed(None)

    def test_demo_data_has_requests_and_synthetic_ids(self):
        ids = [r["id"] for r in inbox.all_requests()]
        self.assertEqual(len(ids), 3)
        self.assertTrue(all("SYN-" in i for i in ids))

    def test_sales_are_scoped_to_one_distributor_and_carry_no_margin(self):
        data = sales.distributor_sales("SYN-DIST-001", "2026Q3")
        self.assertGreater(data["total_revenue"], 0)
        self.assertNotIn("margin", str(data).lower())
        self.assertNotEqual(data["total_revenue"], sales.distributor_sales("SYN-DIST-002", "2026Q3")["total_revenue"])

    def test_a_repeated_key_is_one_effect(self):
        rid = inbox.request_id("SYN-thread-2001")
        _, first = reports.save(rid, "standard", {"total_revenue": 1}, "body", key="k1")
        _, second = reports.save(rid, "standard", {"total_revenue": 1}, "body", key="k1")
        self.assertEqual((first, second), (True, False))
        self.assertEqual(len(reports.for_request(rid)), 1)
        _, p1 = pending.add("report_email", rid, "SYN-thread-2001", "a@b", "s", "b", key="p1")
        _, p2 = pending.add("report_email", rid, "SYN-thread-2001", "a@b", "s", "b", key="p1")
        self.assertEqual((p1, p2), (True, False))

    def test_bad_period_is_a_value_error(self):
        with self.assertRaises(ValueError):
            sales.period_bounds("last quarter")

    def test_margins_exist_but_only_in_their_own_module(self):
        self.assertTrue(margins.by_sku())


if __name__ == "__main__":
    unittest.main()
