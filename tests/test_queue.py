"""The queue page's data (Milestone 2, Part 2 task 4; owner: myron, M6): what has arrived, each item's status,
held runs, runs waiting, and calls waiting for approval; rows of an earlier sandbox never come back."""

import unittest
from unittest import mock

from sandbox import seed
from tests.support import ScratchTest


class QueueTest(ScratchTest):
    def setUp(self):
        super().setUp()
        seed.reset()
        seed.seed(None)

    def test_every_kind_of_waiting_work_is_listed(self):
        from agent import approvals, checkpoints, escalation, runs
        from sandbox import queue
        a, b, c = runs.new_run("S"), runs.new_run("S"), runs.new_run("S")
        approvals.put_up(a, "S", {"name": "send_report_email", "args": {"pending_id": 1}, "key": "k1"},
                         "send_report_email/own_contact", {"lines": []})
        escalation.signal(b, "failed_check", "the report email", "the figure is wrong", "a decision")
        checkpoints.set_wait(c, "outside", "SYN-thread-2001")
        kinds = {(i["kind"], i["id"]) for i in queue.waiting()}
        self.assertIn(("request", "REQ-SYN-thread-2001"), kinds)
        self.assertIn(("held run", b), kinds)
        self.assertIn(("run waiting (outside)", c), kinds)
        self.assertIn(("approval", "apr-1"), kinds)
        self.assertFalse(any(k == "run waiting (escalation)" for k, _ in kinds))   # shown once, with its packet

    def test_rows_of_an_earlier_sandbox_do_not_come_back_when_a_run_key_repeats(self):
        from agent import approvals, runs
        first = runs.new_run("S")
        approvals.put_up(first, "S", {"name": "send_report_email", "args": {}, "key": "k"}, "send_report_email/own_contact",
                         {"lines": []})
        self.assertEqual(len(approvals.pending()), 1)
        seed.reset()                                       # make app: the sandbox and the control state start again
        with mock.patch("sandbox.control.now", return_value="2999-01-01T00:00:00.000+00:00"):
            self.assertEqual(runs.new_run("S"), first)     # the same key, a new run
        self.assertEqual(approvals.pending(), [])


if __name__ == "__main__":
    unittest.main()
