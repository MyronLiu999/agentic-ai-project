"""Uncertain effects are resolved from exact durable identities, never similar records."""
from unittest import mock

from tests.support import ScratchTest, fixed_run

TASK = "tasks/standard_report_clean.yaml"
BACKEND = "tests.fixtures.agent_milestone_model:MilestoneModel"
REQUEST = "REQ-SYN-thread-1001"
FAILED = {"ok": False, "is_error": True, "output": None,
          "error": {"type": "ambiguous_write"}}


class WriteRecoveryTest(ScratchTest):
    def test_nested_program_write_uses_three_exits_and_unknown_stops_the_enclosing_loop(self):
        from agent import checkpoints, escalation, loop, runs, tools
        from agent.registry import Registry
        from harness import runtime
        from harness.client import Usage
        from sandbox import reports
        from tests.fixtures.agent_loop_fakes import tool
        real_call = Registry.call
        program = ('call("save_report", {"kind":"standard", "figures":{"period":"2026Q3",'
                   '"total_revenue":1}, "body":"first"})\n'
                   'result = call("save_report", {"kind":"standard", "figures":{"period":"2026Q2",'
                   '"total_revenue":2}, "body":"second"})')
        for outcome in ("happened", "not_happened", "unknown"):
            with self.subTest(outcome=outcome):
                key, calls = "program-" + outcome, []
                def flaky(reg, name, args, caller, *, step=None, trace_step=None):
                    if name == "save_report":
                        calls.append(args.copy())
                        if len(calls) == 1:
                            if outcome == "happened":
                                real_call(reg, name, args, caller, step=step, trace_step=trace_step)
                            return FAILED
                    return real_call(reg, name, args, caller, step=step, trace_step=trace_step)
                with fixed_run(TASK, key, backend="tests.fixtures.agent_loop_fakes:SequenceModel",
                               overrides=["code_calls.batch_reports=on"]):
                    runs.new_run(key)
                    runtime.client().backend.responses = [([tool("run_program", {"code": program})],
                                                            "tool_use", Usage(10, 5))]
                    with mock.patch.object(Registry, "call", flaky):
                        if outcome == "unknown":
                            with mock.patch("agent.exits.settle", return_value=("unknown", "read unavailable")):
                                result = loop.run(key, REQUEST, "Handle request", registry=tools.build(REQUEST))
                        else:
                            result = loop.run(key, REQUEST, "Handle request", registry=tools.build(REQUEST))
                    if outcome == "unknown":
                        self.assertEqual(result.reason, "unsettled_write")
                        self.assertEqual(len(calls), 1)
                        self.assertEqual(reports.for_request(REQUEST), [])
                        self.assertIn(key, runs.live(key))
                        self.assertIsNotNone(escalation.active_hold(key))
                        self.assertEqual(checkpoints.load(key)["waiting_for"]["kind"], "escalation")
                    else:
                        self.assertEqual(result.reason, "done")
                        self.assertEqual(len(reports.for_request(REQUEST)), 2)
                        self.assertEqual(len(calls), 3 if outcome == "not_happened" else 2)

    def test_code_question_and_decline_paths_settle_instead_of_abandoning_uncertain_writes(self):
        from agent import checkpoints, escalation, runs
        from agent.registry import Registry
        from harness import turns
        from tests.fixtures.m2_tasks import task_backend
        real_call = Registry.call
        cases = [("tasks/outside_units.yaml", "ask_stranger", "REQ-SYN-thread-outside"),
                 ("tasks/out_of_scope_margins.yaml", "draft_clarifying_question", "REQ-SYN-thread-1501")]
        for task, target, request in cases:
            for outcome in ("happened", "not_happened", "unknown"):
                with self.subTest(task=task, outcome=outcome):
                    failed, calls = [], []
                    def flaky(reg, name, args, caller, *, step=None, trace_step=None):
                        if name == target:
                            calls.append(args.copy())
                            if not failed:
                                failed.append(name)
                                if outcome == "happened":
                                    real_call(reg, name, args, caller, step=step, trace_step=trace_step)
                                return FAILED
                        return real_call(reg, name, args, caller, step=step, trace_step=trace_step)
                    key = "direct-" + target + outcome
                    with fixed_run(task, key, backend=task_backend(task)):
                        with mock.patch.object(Registry, "call", flaky):
                            if outcome == "unknown":
                                with mock.patch("agent.exits.settle", return_value=("unknown", "read unavailable")):
                                    reply = turns.operator_turn(key, "Handle " + request)
                            else:
                                reply = turns.operator_turn(key, "Handle " + request)
                        self.assertEqual(failed, [target])
                        if outcome == "unknown":
                            self.assertIsNotNone(escalation.active_hold(key))
                            self.assertIn(key, runs.live(key))
                            self.assertEqual(checkpoints.load(key)["waiting_for"]["kind"], "escalation")
                        elif target == "ask_stranger":
                            self.assertEqual(reply.waiting_for, "SYN-thread-outside")
                        else:
                            self.assertIn("pending record", reply.text)
                        self.assertEqual(len(calls), 2 if outcome == "not_happened" else 1)

    def test_each_executor_settles_its_write_and_saves_exact_arguments_before_execution(self):
        from agent import checkpoints, runs
        from agent.registry import Registry
        from tests.fixtures.m2_tasks import task_backend
        cases = [("tasks/messy_file_semicolon.yaml", []), ("tasks/batch_reports_two.yaml", []),
                 ("tasks/batch_reports_two.yaml", ["topology=split"])]
        real_call = Registry.call
        for task, overrides in cases:
            for committed in (False, True):
                with self.subTest(task=task, topology=overrides, committed=committed):
                    failed = []
                    attempts = []

                    def flaky(reg, name, args, caller, *, step=None, trace_step=None):
                        if name == "draft_report_email":
                            snapshot = checkpoints.load(runs.current_key())
                            self.assertEqual(snapshot["kind"], "tool_call")
                            self.assertEqual(snapshot["args"], args)
                            attempts.append((reg._key_context, args.copy()))
                            if not failed:
                                failed.append(name)
                                if committed:
                                    real_call(reg, name, args, caller, step=step, trace_step=trace_step)
                                return FAILED
                        return real_call(reg, name, args, caller, step=step, trace_step=trace_step)

                    with mock.patch.object(Registry, "call", flaky):
                        record = self.run_task(task, "settle", backend=task_backend(task, split=bool(overrides)),
                                               overrides=overrides)
                    self.assertTrue(record["check"]["passed"], record["check"])
                    self.assertEqual(failed, ["draft_report_email"])
                    expected = 2 if "batch" in task else 1
                    self.assertEqual(len(attempts), expected + (0 if committed else 1))

    def test_three_exits_use_the_exact_key_and_journal_the_recovered_result(self):
        from agent import checkpoints, exits, tools
        from sandbox import reports
        with fixed_run(TASK, "exact", backend=BACKEND):
            reg = tools.build(REQUEST)
            args = {"kind": "standard", "figures": {"period": "2026Q3", "total_revenue": 1.0}, "body": "first"}
            old = reg.call("save_report", args, "code", step="old")
            # Identical contents from another step cannot stand in for this effect.
            new_args = {**args, "body": "second"}
            key = reg.write_key("save_report", new_args, step="new")
            self.assertEqual(exits.settle("save_report", new_args, REQUEST, key)[0], "not_happened")
            with mock.patch.object(reg, "call", wraps=reg.call) as call:
                result = exits.resolve(reg, "save_report", new_args, "code", FAILED,
                                       request_id=REQUEST, run_key="exact", step="new")
            self.assertEqual(call.call_count, 1)
            self.assertNotEqual(result["output"]["report_id"], old["output"]["report_id"])
            self.assertEqual(len(reports.for_request(REQUEST)), 2)
            # Lose the acknowledgement after the write, then settle without executing it again.
            with mock.patch.object(reg, "call", side_effect=AssertionError("duplicate write")):
                recovered = exits.resolve(reg, "save_report", new_args, "code", FAILED,
                                          request_id=REQUEST, run_key="exact", step="new")
            self.assertEqual(recovered["output"]["report_id"], result["output"]["report_id"])
            self.assertEqual(checkpoints.completed("exact", key)["output"]["report_id"], recovered["output"]["report_id"])

    def test_unknown_is_a_durable_live_hold_without_a_retry(self):
        from agent import checkpoints, escalation, exits, runs, tools
        with fixed_run(TASK, "unknown", backend=BACKEND):
            runs.new_run("unknown")
            reg = tools.build(REQUEST)
            args = {"kind": "standard", "figures": {}, "body": "body"}
            with mock.patch("agent.exits.settle", return_value=("unknown", "read unavailable")), \
                    mock.patch.object(reg, "call", side_effect=AssertionError("blind retry")):
                with self.assertRaises(exits.UnsettledWrite):
                    exits.resolve(reg, "save_report", args, "code", FAILED,
                                  request_id=REQUEST, run_key="unknown")
            runs.end("unknown", "unsettled_write")
            self.assertIn("unknown", runs.live("unknown"))
            self.assertEqual(checkpoints.load("unknown")["waiting_for"]["kind"], "escalation")
            self.assertIsNotNone(escalation.active_hold("unknown"))

    def test_app_runs_have_distinct_keys_and_resume_preserves_the_old_key(self):
        from agent import runs, tools
        from harness import runtime
        with fixed_run(TASK, "keys", backend=BACKEND):
            reg = tools.build(REQUEST)
            args = {"kind": "standard", "figures": {}, "body": "body"}
            with mock.patch.object(runtime, "current_run", return_value=None), \
                    mock.patch.object(runtime, "current_session", return_value="session"):
                first = runs.new_run("session")
                a = reg.write_key("save_report", args, step="save")
                runs.new_run("session")
                b = reg.write_key("save_report", args, step="save")
                self.assertNotEqual(a, b)
                with runs._resume_scope(first):
                    self.assertEqual(reg.write_key("save_report", args, step="save"), a)

    def test_send_receipt_settles_committed_delivery_without_resending(self):
        import channel
        from agent import disclosure, exits, tools
        from sandbox import inbox, pending
        with fixed_run(TASK, "send", backend=BACKEND):
            request = inbox.get(REQUEST)
            question = disclosure.with_disclosure("Which units?")
            # Commit delivery, then lose the acknowledgement before pending status changes.
            with mock.patch.object(pending, "complete_send", side_effect=RuntimeError("lost response")):
                with self.assertRaises(RuntimeError):
                    tools._ask_stranger(REQUEST, question, "send-key")
            outcome, output = exits.settle("ask_stranger", {"question": question}, REQUEST, "send-key")
            self.assertEqual(outcome, "happened")
            self.assertEqual(pending.get(output["pending_id"])["status"], "sent")
            self.assertEqual(len([m for m in channel.messages(request["thread_id"])
                                  if m.sender == channel.AGENT]), 1)
            replay = tools._ask_stranger(REQUEST, question, "send-key")
            self.assertEqual(replay["message_id"], output["message_id"])
            self.assertFalse(replay["created"])

    def test_claimed_send_without_a_receipt_stays_unknown_even_with_an_old_matching_message(self):
        import channel
        from agent import disclosure, exits
        from sandbox import inbox, pending
        with fixed_run(TASK, "send-unknown", backend=BACKEND):
            request = inbox.get(REQUEST)
            text = disclosure.with_disclosure("Which units?")
            channel.send(request["thread_id"], text)
            record, _ = pending.add("clarifying_question", REQUEST, request["thread_id"],
                                    request["contact_email"], "About your request", text, "uncertain")
            pending.claim_send(record["id"])
            self.assertEqual(exits.settle("ask_stranger", {"question": text}, REQUEST, "uncertain")[0], "unknown")

    def test_replayed_delivery_restores_chart_package_link_after_interrupted_bookkeeping(self):
        import channel
        from agent import disclosure, tools
        from sandbox import db, email_packages, inbox, pending, reports
        with fixed_run(TASK, "send-link", backend=BACKEND):
            request = inbox.get(REQUEST)
            report, _ = reports.save(REQUEST, "standard", {"period": "2026Q3", "total_revenue": 1}, "body", "report")
            draft, _ = pending.add("report_email", REQUEST, request["thread_id"], request["contact_email"],
                                   "Report", disclosure.with_disclosure("Body"), "draft", report_id=report["id"])
            with mock.patch.object(email_packages, "link_message", side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    tools._send_report_email(REQUEST, draft["id"], "send")
            replay = tools._send_report_email(REQUEST, draft["id"], "send")
            self.assertFalse(replay["created"])
            with db.connect() as conn:
                linked = conn.execute("SELECT message_id FROM email_packages WHERE pending_id=?", (draft["id"],)).fetchone()[0]
            self.assertEqual(linked, replay["sent_id"])
            self.assertEqual(len([m for m in channel.messages(request["thread_id"]) if m.sender == channel.AGENT]), 1)
