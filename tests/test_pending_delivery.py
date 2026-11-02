"""Operator delivery uses durable claims and only fulfills the report actually sent."""

from concurrent.futures import ThreadPoolExecutor
import subprocess
import sys
from threading import Event
from unittest import mock

import channel
from fastapi.testclient import TestClient

from app.main import app
from sandbox import inbox, pending, reports, seed
from tests.support import ScratchTest

RID = "REQ-SYN-thread-2001"
THREAD = "SYN-thread-2001"


class PendingDeliveryTest(ScratchTest):
    def setUp(self):
        super().setUp()
        channel.reset()
        seed.reset()
        seed.seed(None)
        self.client = TestClient(app, raise_server_exceptions=False)
        self.client.__enter__()
        inbox.set_status(RID, "report_drafted")

    def tearDown(self):
        self.client.__exit__(None, None, None)
        super().tearDown()

    def draft(self, key="first", kind="report_email", report=True):
        saved = reports.save(RID, "standard", {}, key, key=f"report-{key}")[0] if report else None
        return pending.add(kind, RID, THREAD, "contact@acme.example", key, key,
                           key=key, report_id=saved["id"] if saved else None)[0]

    def send(self, record):
        return self.client.post(f"/pending/{record['id']}/send", follow_redirects=False)

    def operator_messages(self):
        return [m for m in channel.messages(THREAD) if m.sender == "operator"]

    def while_sending(self, record, other):
        entered, release = Event(), Event()
        original = channel.send

        def paused_send(*args, **kwargs):
            if not entered.is_set():
                entered.set()
                if not release.wait(timeout=10):
                    raise TimeoutError("test did not release first delivery")
            return original(*args, **kwargs)

        with mock.patch.object(channel, "send", paused_send), ThreadPoolExecutor(max_workers=1) as pool:
            first = pool.submit(self.send, record)
            self.assertTrue(entered.wait(timeout=5), "first request never reached channel")
            try:
                result = other()
            finally:
                release.set()
            self.assertEqual(first.result(timeout=5).status_code, 303)
        return result

    def test_concurrent_http_sends_deliver_once(self):
        record = self.draft()
        second = self.while_sending(record, lambda: self.send(record))
        self.assertEqual(second.status_code, 404)
        self.assertEqual(len(self.operator_messages()), 1)
        self.assertEqual(pending.get(record["id"])["status"], "sent")

    def test_another_process_cannot_send_an_inflight_record(self):
        record = self.draft()
        script = ("from fastapi.testclient import TestClient; from app.main import app; "
                  f"print(TestClient(app).post('/pending/{record['id']}/send', "
                  "follow_redirects=False).status_code)")
        second = self.while_sending(record, lambda: subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True, check=True, timeout=10))
        self.assertEqual(second.stdout.strip(), "404")
        self.assertEqual(len(self.operator_messages()), 1)

    def test_discard_cannot_win_after_send_has_started(self):
        record = self.draft()
        discarded = self.while_sending(record, lambda: self.client.post(
            f"/pending/{record['id']}/discard", follow_redirects=False))
        self.assertEqual(discarded.status_code, 404)
        self.assertEqual(pending.get(record["id"])["status"], "sent")
        self.assertEqual(len(self.operator_messages()), 1)

    def test_channel_failure_before_effect_is_inspectable_and_cannot_retry(self):
        record = self.draft()
        with mock.patch.object(channel, "send", side_effect=RuntimeError("channel unavailable")):
            response = self.send(record)
        self.assertEqual(response.status_code, 502)
        self.assertEqual(pending.get(record["id"])["status"], "send_failed")
        self.assertEqual(self.send(record).status_code, 404)
        self.assertEqual(len(self.operator_messages()), 0)
        self.assertEqual(inbox.get(RID)["status"], "report_drafted")
        page = self.client.get(f"/requests/{RID}").text
        self.assertIn("send_failed", page)
        self.assertIn("Check the thread before sending another message", page)
        self.assertNotIn(f"/pending/{record['id']}/send", page)
        self.assertEqual(self.client.post(f"/pending/{record['id']}/discard").status_code, 404)

    def test_channel_failure_after_effect_does_not_duplicate_on_retry(self):
        record = self.draft()
        original = channel.send

        def sent_then_failed(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError("post-send callback failed")

        with mock.patch.object(channel, "send", sent_then_failed):
            response = self.send(record)
        self.assertEqual(response.status_code, 502)
        self.assertEqual(pending.get(record["id"])["status"], "send_failed")
        self.assertEqual(self.send(record).status_code, 404)
        self.assertEqual(len(self.operator_messages()), 1)
        self.assertNotEqual(inbox.get(RID)["status"], "done")

    def test_finalization_failure_after_delivery_cannot_retry_or_close(self):
        record = self.draft()
        with mock.patch.object(pending, "complete_send", side_effect=RuntimeError("database finalization failed")):
            response = self.send(record)
        self.assertEqual(response.status_code, 502)
        self.assertEqual(pending.get(record["id"])["status"], "send_failed")
        self.assertEqual(self.send(record).status_code, 404)
        self.assertEqual(len(self.operator_messages()), 1)
        self.assertEqual(inbox.get(RID)["status"], "report_drafted")

    def test_process_exit_after_claim_leaves_inspectable_nonretryable_state(self):
        record = self.draft()
        script = ("from sandbox import pending; "
                  f"assert pending.claim_send({record['id']})['status'] == 'sending'")
        subprocess.run([sys.executable, "-c", script], check=True, capture_output=True, text=True, timeout=10)
        self.assertEqual(pending.get(record["id"])["status"], "sending")
        self.assertEqual(self.send(record).status_code, 404)
        self.assertEqual(self.client.post(f"/pending/{record['id']}/discard").status_code, 404)
        self.assertEqual(len(self.operator_messages()), 0)
        page = self.client.get(f"/requests/{RID}").text
        self.assertIn("sending", page)
        self.assertIn("Check the thread before sending another message", page)

    def test_unresolved_delivery_failure_keeps_later_successful_send_open(self):
        failed = self.draft()
        with mock.patch.object(channel, "send", side_effect=RuntimeError("unavailable")):
            self.send(failed)
        latest = self.draft("latest")
        self.assertEqual(self.send(latest).status_code, 303)
        self.assertEqual(pending.get(failed["id"])["status"], "send_failed")
        self.assertEqual(inbox.get(RID)["status"], "report_drafted")

    def test_answer_still_required_after_sent_question_then_report(self):
        question = self.draft("question", kind="clarifying_question", report=False)
        self.assertEqual(self.send(question).status_code, 303)
        latest = self.draft("latest")
        self.assertEqual(self.send(latest).status_code, 303)
        self.assertEqual(inbox.get(RID)["status"], "awaiting_answer")

    def test_older_report_send_preserves_newer_draft_and_queue(self):
        first = self.draft()
        second = self.draft("second")
        self.assertEqual(self.send(first).status_code, 303)
        self.assertEqual(inbox.get(RID)["status"], "report_drafted")
        self.assertEqual(pending.get(second["id"])["status"], "pending")
        self.assertIn(RID, self.client.get("/queue").text)
        self.assertEqual(self.send(second).status_code, 303)
        self.assertEqual(inbox.get(RID)["status"], "done")

    def test_older_report_without_new_draft_does_not_close_new_report(self):
        first = self.draft()
        reports.save(RID, "standard", {}, "new version", key="new-version")
        self.assertEqual(self.send(first).status_code, 303)
        self.assertEqual(inbox.get(RID)["status"], "report_drafted")

    def test_newer_question_keeps_request_awaiting_answer(self):
        first = self.draft()
        question = self.draft("question", kind="clarifying_question", report=False)
        inbox.set_status(RID, "awaiting_answer")
        self.assertEqual(self.send(first).status_code, 303)
        self.assertEqual(self.send(question).status_code, 303)
        self.assertEqual(inbox.get(RID)["status"], "awaiting_answer")

    def test_new_work_added_during_send_prevents_closure(self):
        first = self.draft()
        second = self.while_sending(first, lambda: self.draft("second"))
        self.assertEqual(inbox.get(RID)["status"], "report_drafted")
        self.assertEqual(pending.get(second["id"])["status"], "pending")

    def test_new_draft_after_completion_reopens_request_and_queue(self):
        first = self.draft()
        self.send(first)
        self.assertEqual(inbox.get(RID)["status"], "done")
        self.draft("second")
        self.assertEqual(inbox.get(RID)["status"], "report_drafted")
        self.assertIn(RID, self.client.get("/queue").text)

    def test_new_question_after_completion_reopens_request_awaiting_answer(self):
        first = self.draft()
        self.send(first)
        self.assertEqual(inbox.get(RID)["status"], "done")
        self.draft("question", kind="clarifying_question", report=False)
        self.assertEqual(inbox.get(RID)["status"], "awaiting_answer")
        self.assertIn(RID, self.client.get("/queue").text)

    def test_reusing_sent_key_does_not_reopen_completed_work(self):
        first = self.draft()
        self.send(first)
        repeated, created = pending.add("report_email", RID, THREAD, "contact@acme.example", "first", "first",
                                        key=first["key"], report_id=first["report_id"])
        self.assertFalse(created)
        self.assertEqual(repeated["status"], "sent")
        self.assertEqual(inbox.get(RID)["status"], "done")

    def test_new_draft_does_not_override_held_or_declined_request(self):
        for status in ("held", "declined"):
            with self.subTest(status=status):
                inbox.set_status(RID, status)
                self.draft(status)
                self.assertEqual(inbox.get(RID)["status"], status)

    def test_hand_email_preserves_an_existing_pending_draft(self):
        first = self.draft()
        response = self.client.post(f"/requests/{RID}/email", data={"subject": "Manual", "body": "Manual"},
                                    follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertEqual(inbox.get(RID)["status"], "report_drafted")
        self.assertEqual(pending.get(first["id"])["status"], "pending")

    def test_hand_email_failure_is_also_blocked_from_retry(self):
        with mock.patch.object(channel, "send", side_effect=RuntimeError("channel unavailable")):
            response = self.client.post(f"/requests/{RID}/email", data={"subject": "Manual", "body": "Manual"},
                                        follow_redirects=False)
        self.assertEqual(response.status_code, 502)
        record = pending.for_request(RID)[0]
        self.assertEqual(record["status"], "send_failed")
        self.assertEqual(self.send(record).status_code, 404)
        self.assertNotEqual(inbox.get(RID)["status"], "done")
