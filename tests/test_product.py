"""The product page without the agent (claudea): requests, one request with file, thread, charts and pending
records, the query page with a chart, and the core task done by hand. No model."""

import channel
from fastapi.testclient import TestClient

from app.main import app
from sandbox import charts, inbox, pending, seed
from tests.support import ScratchTest

RID = "REQ-SYN-thread-2001"


class ProductPageTest(ScratchTest):
    def setUp(self):
        super().setUp()
        channel.reset()
        seed.reset()
        seed.seed(None)
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        super().tearDown()

    def test_requests_and_one_request_show_file_thread_and_the_hand_form(self):
        home = self.client.get("/")
        self.assertIn(RID, home.text)
        page = self.client.get(f"/requests/{RID}")
        self.assertEqual(page.status_code, 200)
        for text in ("acme_q3.csv", "SYN-SKU-001,310", "How did our region do", "Email a report by hand",
                     "contact@acme.example"):
            self.assertIn(text, page.text)
        self.assertEqual(self.client.get("/requests/REQ-nope").status_code, 404)

    def test_query_page_has_a_chart_and_last_quarter(self):
        page = self.client.get("/query?distributor=SYN-DIST-002&period=2026Q3")
        self.assertEqual(page.status_code, 200)
        self.assertIn("<svg", page.text)
        self.assertIn("previous quarter (2026Q2)", page.text)
        self.assertIn("must look like 2026Q3", self.client.get("/query?period=last").text)

    def test_a_saved_chart_shows_on_the_request_and_as_svg(self):
        chart, _ = charts.render(RID, "Q3 revenue", ["Widget S"], [12.5], key="k")
        self.assertIn("Q3 revenue", self.client.get(f"/requests/{RID}").text)
        svg = self.client.get(f"/charts/{chart['id']}.svg")
        self.assertEqual(svg.headers["content-type"], "image/svg+xml")

    def test_emailing_a_report_by_hand_sends_as_the_operator_to_the_requests_contact(self):
        r = self.client.post(f"/requests/{RID}/email", data={"subject": "Q3", "body": "Your Q3 revenue."},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        sent = pending.for_request(RID)
        self.assertEqual([(p["status"], p["stamp"], p["recipient"]) for p in sent],
                         [("sent", "manual", "contact@acme.example")])
        self.assertEqual(channel.messages("SYN-thread-2001")[-1].sender, "operator")
        self.assertEqual(inbox.get(RID)["status"], "done")

    def test_a_pending_record_is_sent_once_from_the_page(self):
        record, _ = pending.add("report_email", RID, "SYN-thread-2001", "contact@acme.example", "s", "b", key="p")
        self.assertEqual(self.client.post(f"/pending/{record['id']}/send", follow_redirects=False).status_code, 303)
        self.assertEqual(pending.get(record["id"])["status"], "sent")
        self.assertEqual(self.client.post(f"/pending/{record['id']}/send").status_code, 404)
