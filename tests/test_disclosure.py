"""Tell the stranger an agent wrote it (Milestone 2, Part 2 task 8; owner: claudea, C8).

The line is added in code (agent/disclosure.py), never by a prompt; the hook refuses a send without it
(policy/hook.py, through disclosure.check); every task's check fails an agent message without it
(checks/helpers.requires_disclosure). The registry-level refusal is pinned in tests/test_m2_contracts.py."""

import unittest

from tests.support import ScratchTest, fixed_run

TASK = "tasks/standard_report_clean.yaml"


class DisclosureLineTest(unittest.TestCase):
    def test_the_line_names_an_agent_and_a_way_to_reach_a_person(self):
        from agent import disclosure
        self.assertIn("automated agent", disclosure.LINE)
        self.assertIn("reach a person", disclosure.LINE)

    def test_added_once_at_the_end(self):
        from agent import disclosure
        text = disclosure.with_disclosure("Which column holds the units?")
        self.assertTrue(text.endswith(disclosure.LINE))
        self.assertEqual(disclosure.with_disclosure(text).count(disclosure.LINE), 1)

    def test_every_send_tool_is_checked_and_nothing_else(self):
        from agent import disclosure
        self.assertEqual(set(disclosure.SENDS), {"ask_stranger", "send_report_email"})
        for tool in ("parse_file", "query_sales", "save_report", "draft_report_email", "render_chart"):
            self.assertTrue(disclosure.check({"name": tool, "args": {}}), tool)

    def test_a_send_whose_text_cannot_be_read_is_refused(self):
        from agent import disclosure
        self.assertFalse(disclosure.check({"name": "send_report_email", "args": {"pending_id": 999999}}))


class SendReportEmailTextTest(ScratchTest):
    def test_the_pending_records_body_is_what_the_hook_checks(self):
        from agent import disclosure
        from sandbox import pending
        with fixed_run(TASK, "disclose-pending"):
            bare, _ = pending.add("report_email", "REQ-SYN-thread-1001", "SYN-thread-1001", "contact@acme.example",
                                  "s", "Your revenue was 1.00.", key="k-bare")
            signed, _ = pending.add("report_email", "REQ-SYN-thread-1001", "SYN-thread-1001", "contact@acme.example",
                                    "s", disclosure.with_disclosure("Your revenue was 1.00."), key="k-signed")
            self.assertFalse(disclosure.check({"name": "send_report_email", "args": {"pending_id": bare["id"]}}))
            self.assertTrue(disclosure.check({"name": "send_report_email", "args": {"pending_id": signed["id"]}}))


class ChecksReadTheChannelTest(ScratchTest):
    def test_the_operators_own_hand_sent_mail_needs_no_line(self):
        import channel
        from checks.helpers import undisclosed
        with fixed_run(TASK, "disclose-operator") as run:
            channel.send("SYN-thread-1001", "Hi, the report is attached.", sender=channel.OPERATOR)
            self.assertEqual(undisclosed(run), [])
            channel.send("SYN-thread-1001", "Which column holds the units?")            # the agent, no line
            self.assertEqual(len(undisclosed(run)), 1)


if __name__ == "__main__":
    unittest.main()
