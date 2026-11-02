from email import policy
from email.parser import BytesParser
from io import BytesIO

import channel
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from sandbox import charts, email_packages, inbox, pending, reports, seed
from tests.support import ScratchTest


RID = "REQ-SYN-thread-2001"


class EmailChartsTest(ScratchTest):
    def setUp(self):
        super().setUp()
        seed.seed(None)
        self.client = TestClient(app)
        self.client.__enter__()
        self.chart = charts.render(RID, "Quarter revenue", ["Q2", "Q3"], [120, 180], key="own")[0]
        charts.render("REQ-SYN-thread-2002", "PRIVATE OTHER CHART", ["Other"], [999], key="other")
        self.report = reports.save(RID, "standard", {"chart_id": self.chart["id"]}, "Report", key="report")[0]

    def tearDown(self):
        self.client.__exit__(None, None, None)
        super().tearDown()

    def test_manual_export_contains_self_contained_png_without_sending(self):
        response = self.client.post(f"/requests/{RID}/email/download",
                                    data={"subject": "Reviewed subject", "body": "My <edited> email"})
        self.assertEqual(response.status_code, 200)
        message = BytesParser(policy=policy.default).parsebytes(response.content)
        self.assertEqual(message["To"], "contact@acme.example")
        self.assertEqual(message["Subject"], "Reviewed subject")
        self.assertIn("My <edited> email", message.get_body(preferencelist=("plain",)).get_content())
        html = message.get_body(preferencelist=("html",)).get_content()
        self.assertIn("My &lt;edited&gt; email", html)
        self.assertIn("cid:chart-0", html)
        self.assertNotIn("PRIVATE OTHER CHART", html)
        self.assertNotIn("127.0.0.1", html)
        images = [p for p in message.walk() if p.get_content_type() == "image/png"]
        self.assertEqual(len(images), 1)
        Image.open(BytesIO(images[0].get_payload(decode=True))).verify()
        self.assertEqual(pending.all_pending(), [])
        self.assertFalse(any(m.sender == "operator" for m in channel.messages("SYN-thread-2001")))

    def test_pending_send_freezes_images_and_shows_them_in_threads(self):
        record = pending.add("report_email", RID, "SYN-thread-2001", inbox.get(RID)["contact_email"],
                             "Report", "Please review.", key="draft", report_id=self.report["id"])[0]
        response = self.client.post(f"/pending/{record['id']}/send", follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        original = email_packages.saved(record["id"])["charts"]
        image_response = self.client.get(f"/pending/{record['id']}/charts/0.png")
        Image.open(BytesIO(image_response.content)).verify()
        self.assertEqual(self.client.get(f"/pending/{record['id']}/charts/-1.png").status_code, 404)
        page = self.client.get("/threads?thread=SYN-thread-2001").text
        self.assertIn(f'/pending/{record["id"]}/charts/0.png', page)
        self.assertNotIn("PRIVATE OTHER CHART", page)
        charts.render(RID, "Quarter revenue", ["Changed"], [9999], key="new")
        self.assertEqual(email_packages.prepare(pending.get(record["id"]))["charts"], original)
        self.assertEqual(self.client.post(f"/pending/{record['id']}/send").status_code, 404)
        self.assertEqual(len([m for m in channel.messages("SYN-thread-2001") if m.sender == "operator"]), 1)

    def test_questions_and_historical_messages_do_not_gain_charts(self):
        question = pending.add("clarifying_question", RID, "SYN-thread-2001", "contact@acme.example",
                               "Question", "Which quarter?", key="question")[0]
        self.assertEqual(email_packages.prepare(question)["charts"], [])
        old = pending.add("report_email", RID, "SYN-thread-2001", "contact@acme.example",
                          "Old", "Already sent", key="old")[0]
        pending.mark_sent(old["id"])
        self.assertEqual(email_packages.prepare(pending.get(old["id"]))["charts"], [])

    def test_primary_chart_uses_report_binding_and_rejects_foreign_chart(self):
        charts.render(RID, "Quarter revenue", ["New data"], [1], key="later")
        record = {"kind": "report_email", "request_id": RID, "status": "pending",
                  "report_id": self.report["id"], "recipient": "contact@acme.example",
                  "subject": "Report", "body": "Figures"}
        self.assertEqual(email_packages.prepare(record)["charts"][0]["filename"], f"chart-{self.chart['id']}.png")
        other = charts.for_request("REQ-SYN-thread-2002")[0]
        bad = reports.save(RID, "standard", {"chart_id": other["id"]}, "bad", key="bad")[0]
        with self.assertRaises(ValueError):
            email_packages.prepare(record | {"report_id": bad["id"]})
