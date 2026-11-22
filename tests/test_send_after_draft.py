"""Pass 2 (tools.send_after_draft; owner: myron): only draft_report_email's description changes.

off keeps the description as built ("for the operator to review and send"); on tells the model to call
send_report_email next when the operator asked for a send, and says that send waits for approval.
No other definition, schema or strict flag differs between the arms.
"""

from sandbox import inbox, seed
from tests.support import ScratchTest


class SendAfterDraftTest(ScratchTest):
    def setUp(self):
        super().setUp()
        seed.reset()
        seed.seed(None)
        self.request_id = inbox.request_id("SYN-thread-2001")

    def definitions(self, setting=None):
        from agent import tools
        from harness import runtime
        runtime.configure(overrides=[f"tools.send_after_draft={setting}"] if setting else [])
        try:
            return {d["name"]: d for d in tools.build(self.request_id).definitions()}
        finally:
            runtime.configure()

    def test_default_is_off_and_keeps_the_built_description(self):
        from agent import tools
        default, off = self.definitions(), self.definitions("off")
        self.assertEqual(default, off)
        self.assertEqual(off["draft_report_email"]["description"], tools.DRAFT_EMAIL_REVIEW)
        self.assertIn("review and send", off["draft_report_email"]["description"])

    def test_on_points_at_the_send_and_its_approval(self):
        text = self.definitions("on")["draft_report_email"]["description"]
        self.assertNotIn("review and send", text)
        self.assertIn("call send_report_email next with this draft's pending_id", text)
        self.assertIn("operator asked for the email to be sent", text)
        self.assertIn("waits for the operator's approval", text)
        self.assertIn("cannot send email", text)

    def test_only_the_draft_description_differs(self):
        off, on = self.definitions("off"), self.definitions("on")
        self.assertEqual(off.keys(), on.keys())
        for name in off:
            a, b = dict(off[name]), dict(on[name])
            if name == "draft_report_email":
                a.pop("description"); b.pop("description")
            self.assertEqual(a, b, name)
