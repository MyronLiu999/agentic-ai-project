import json
import subprocess
import sys
import threading

from agent import checkpoints, messages, runs, stop
from policy import flags
from sandbox import seed
from tests.support import ScratchTest


class MidtaskTest(ScratchTest):
    def make_run(self):
        key = runs.new_run("midtask")
        checkpoints.save(key, {"path": "agent", "request_id": "REQ-1", "completed_calls": [],
                               "conversation": [{"role": "user", "content": "Handle the request."}]})
        return key

    def test_adding_from_another_thread_keeps_the_previous_write_once(self):
        key = self.make_run()
        checkpoints.after_call(key, {"tool": "save_report", "args": {}, "key": "first"},
                               {"ok": True, "output": {"report_id": 8}, "is_error": False, "error": None})
        reply = []
        thread = threading.Thread(target=lambda: reply.append(messages.intercept("midtask", "/add Include the prior quarter.")))
        thread.start()
        thread.join(timeout=5)
        self.assertIsNotNone(reply[0], "mid-task additions must be intercepted rather than start a new run")
        self.assertEqual(messages.consume(key), ["Include the prior quarter."])
        self.assertEqual(messages.consume(key), [])
        self.assertEqual(len(checkpoints.load(key)["completed_calls"]), 1)
        self.assertIn("Include the prior quarter.", json.dumps(checkpoints.load(key)["conversation"]))
        self.assertFalse(flags.is_stopped(key))

    def test_replacing_from_another_thread_stops_old_run_and_queues_new_task(self):
        key = self.make_run()
        checkpoints.after_call(key, {"tool": "save_report", "args": {}, "key": "first"},
                               {"ok": True, "output": {"report_id": 8}, "is_error": False, "error": None})
        checkpoints.set_wait(key, "outside", "SYN-thread-1")
        reply = []
        thread = threading.Thread(target=lambda: reply.append(messages.intercept("midtask", "/replace Handle REQ-2 instead.")))
        thread.start()
        thread.join(timeout=5)
        self.assertIsNotNone(reply[0], "replacement must stop the old task before starting the new one")
        self.assertIn("save_report", reply[0].text)
        self.assertIn("rollback", reply[0].text)
        self.assertTrue(flags.is_stopped(key))
        self.assertEqual(runs.live("midtask"), [])
        self.assertEqual(checkpoints.waiting("midtask"), [])
        self.assertEqual(messages.next_queued("midtask"), "Handle REQ-2 instead.")
        self.assertEqual(messages.next_queued("midtask"), None)
        with self.assertRaises(stop.ControlStopped) as raised:
            stop.check(key)
        self.assertEqual(raised.exception.reason, "cancelled")

    def test_default_queue_is_bounded_and_does_not_run_until_live_task_ends(self):
        key = self.make_run()
        for n in range(8):
            reply = messages.intercept("midtask", f"Status question {n}?")
            self.assertIsNotNone(reply, "busy-session questions must be queued")
        self.assertIn("full", messages.intercept("midtask", "one too many").text.lower())
        self.assertIsNone(messages.next_queued("midtask"))
        runs.end(key, "done")
        self.assertEqual([messages.next_queued("midtask") for _ in range(8)],
                         [f"Status question {n}?" for n in range(8)])
        self.assertIsNone(messages.next_queued("midtask"))

    def test_ambiguous_add_and_empty_replace_do_not_stop_any_run(self):
        first, second = self.make_run(), self.make_run()
        self.assertEqual(messages.classify("midtask", "/replace"), "reject")
        reply = messages.intercept("midtask", "/add Include a chart.")
        self.assertIsNotNone(reply, "ambiguous run selection needs rejection")
        self.assertIn("number", reply.text)
        messages.intercept("midtask", "/add 2 Include a chart.")
        self.assertEqual(messages.consume(first), [])
        self.assertEqual(messages.consume(second), ["Include a chart."])
        self.assertFalse(flags.is_stopped(first))
        self.assertFalse(flags.is_stopped(second))

    def test_queued_messages_survive_process_restart_and_reset(self):
        key = self.make_run()
        reply = messages.intercept("midtask", "Show saved reports.")
        self.assertIsNotNone(reply)
        runs.end(key, "done")
        script = "from agent import messages; assert messages.next_queued('midtask') == 'Show saved reports.'"
        subprocess.run([sys.executable, "-c", script], check=True)
        self.make_run()
        messages.intercept("midtask", "Another message")
        seed.reset()
        self.assertEqual(messages.pending("midtask"), [])

    def test_addition_is_saved_in_checkpoint_before_it_is_acknowledged_consumed(self):
        key = self.make_run()
        reply = messages.intercept("midtask", "/add Keep figures in units.")
        self.assertIsNotNone(reply)
        self.assertEqual(messages.consume(key), ["Keep figures in units."])
        script = "from agent import checkpoints, messages; import json; assert 'Keep figures in units.' in json.dumps(checkpoints.load('midtask#1')['conversation']); assert messages.consume('midtask#1') == []"
        subprocess.run([sys.executable, "-c", script], check=True)


class ThreadedServiceControlTest(ScratchTest):
    def setUp(self):
        super().setUp()
        import channel
        from harness import runtime
        runtime.configure(backend="tests.fixtures.control_model:ControlledModel")
        channel.reset()
        seed.reset()
        inputs = [{"thread": f"SYN-thread-control-{name}", "from": "SYN-contact-test",
                   "distributor": distributor, "contact_email": contact, "period": "2026Q3",
                   "text": "SYNTHETIC. Please prepare a sales report.",
                   "file": {"name": f"{name}.csv", "content": "Artikel;Menge\nSYN-SKU-003;4\n"}}
                  for name, distributor, contact in [("old", "SYN-DIST-002", "contact@brightline.example"),
                                                     ("new", "SYN-DIST-001", "contact@acme.example")]]
        with channel.seeding():
            seed.seed({"inputs": inputs})
        self.session = "threaded-control"
        self.model = runtime.client(self.session).backend
        self.results, self.errors = [], []
        self.worker = None

    def tearDown(self):
        self.model.release.set()
        if self.worker:
            self.worker.join(timeout=12)
        super().tearDown()

    def start_turn(self, mode):
        from harness import turns
        self.model.mode = mode
        def work():
            try:
                self.results.append(turns.operator_turn(self.session, "Handle REQ-SYN-thread-control-old."))
            except Exception as exc:
                self.errors.append(exc)
        self.worker = threading.Thread(target=work)
        self.worker.start()
        self.assertTrue(self.model.entered.wait(timeout=10), f"The task never reached its call boundary: {self.errors}")

    def finish_turn(self):
        self.model.release.set()
        self.worker.join(timeout=12)
        self.assertFalse(self.worker.is_alive(), "The controlled turn did not finish")
        self.assertEqual(self.errors, [])

    def test_addition_changes_later_report_without_repeating_prior_write(self):
        from harness import turns
        from sandbox import charts, reports
        self.start_turn("add")
        self.assertEqual(len(charts.for_request("REQ-SYN-thread-control-old")), 1)
        added = turns.operator_turn(self.session, "/add Include the validation note.")
        self.assertIn("Added", added.text)
        self.finish_turn()
        saved = reports.for_request("REQ-SYN-thread-control-old")
        self.assertEqual(len(saved), 1)
        self.assertIn("validation note", saved[0]["body"])
        self.assertEqual(len(charts.for_request("REQ-SYN-thread-control-old")), 1)

    def test_replacement_blocks_old_response_and_saves_new_task_report(self):
        from harness import turns
        from sandbox import charts, reports
        self.start_turn("replace")
        self.assertEqual(len(charts.for_request("REQ-SYN-thread-control-old")), 1)
        replaced = turns.operator_turn(self.session, "/replace Handle REQ-SYN-thread-control-new.")
        self.assertIn("render_chart", replaced.text)
        self.assertIn("rollback", replaced.text)
        self.finish_turn()
        self.assertEqual(reports.for_request("REQ-SYN-thread-control-old"), [])
        self.assertEqual(len(charts.for_request("REQ-SYN-thread-control-old")), 1)
        new = reports.for_request("REQ-SYN-thread-control-new")
        self.assertEqual(len(new), 1)
        self.assertIn("Replacement task", new[0]["body"])

    def test_stop_during_model_call_leaves_no_writes_from_returned_tool(self):
        from harness import turns
        from sandbox import charts, pending, reports
        self.start_turn("stop")
        stopped = turns.operator_turn(self.session, "/stop")
        self.assertIn("Stopped", stopped.text)
        self.finish_turn()
        self.assertEqual(charts.for_request("REQ-SYN-thread-control-old"), [])
        self.assertEqual(reports.for_request("REQ-SYN-thread-control-old"), [])
        self.assertEqual(pending.for_request("REQ-SYN-thread-control-old"), [])
