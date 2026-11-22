"""Model-authored programs cannot borrow a fixed code template's send permission."""
import json

import channel
from agent import approvals, checkpoints, disclosure, loop, outside, runs, service, tools
from harness import runtime
from harness.client import Usage
from sandbox import reports
from tests.fixtures.agent_loop_fakes import tool
from tests.support import ScratchTest, fixed_run

TASK = "tasks/outside_units.yaml"
REQUEST = "REQ-SYN-thread-outside"
THREAD = "SYN-thread-outside"
BACKEND = "tests.fixtures.agent_loop_fakes:SequenceModel"


class ProgramApprovalTest(ScratchTest):
    def tearDown(self):
        runtime.configure()
        super().tearDown()

    def begin(self, key, question):
        runs.new_run(key)
        program = ('answer = call("ask_stranger", ' + json.dumps({"question": question}) + ')\n'
                   'call("save_report", {"kind":"standard", "figures":{"period":"2026Q3",'
                   '"total_revenue":1}, "body":"must not run before the outside answer"})\nresult = answer')
        runtime.client().backend.responses = [([tool("run_program", {"code": program})],
                                                "tool_use", Usage(10, 5))]
        return loop.run(key, REQUEST, "Clarify the file before writing a report.", registry=tools.build(REQUEST))

    def agent_messages(self):
        return [m for m in channel.messages(THREAD) if m.sender == channel.AGENT]

    def test_program_question_requires_approval_even_when_its_text_matches_the_code_template(self):
        for i, question in enumerate(("Which currency should this report use?", outside.TEMPLATES["units_column"])):
            with self.subTest(question=question), fixed_run(TASK, f"program-gate-{i}", backend=BACKEND,
                                                           overrides=["code_calls.batch_reports=on"]):
                result = self.begin(f"program-gate-{i}", question)
                self.assertEqual(result.reason, "awaiting_approval")
                self.assertEqual(self.agent_messages(), [])
                self.assertEqual(reports.for_request(REQUEST), [])
                waiting = approvals.pending()
                self.assertEqual(len(waiting), 1)
                self.assertEqual(waiting[0]["action_class"], "ask_stranger/model_written")
                self.assertEqual(waiting[0]["call"]["args"]["question"], disclosure.with_disclosure(question))
                self.assertEqual(checkpoints.load(f"program-gate-{i}")["waiting_for"]["ref"], waiting[0]["id"])

    def test_rejected_program_question_cannot_send_or_continue_its_remaining_writes(self):
        with fixed_run(TASK, "program-rejected", backend=BACKEND, overrides=["code_calls.batch_reports=on"]):
            result = self.begin("program-rejected", "Which units?")
            self.assertEqual(result.reason, "awaiting_approval")
            service.decide_approval(approvals.pending()[0]["id"], False, "Do not send this question")
            self.assertEqual(self.agent_messages(), [])
            self.assertEqual(reports.for_request(REQUEST), [])
            self.assertEqual(approvals.pending(), [])

    def test_approved_program_survives_restart_sends_once_and_waits_before_later_writes(self):
        key = "program-restart"
        question = "Which column holds units?"
        with fixed_run(TASK, key, backend=BACKEND, overrides=["code_calls.batch_reports=on"]):
            result = self.begin(key, question)
            self.assertEqual(result.reason, "awaiting_approval")
            approval_id = approvals.pending()[0]["id"]
        with fixed_run(TASK, key, backend=BACKEND, fresh=False, overrides=["code_calls.batch_reports=on"]):
            reply = service.decide_approval(approval_id, True, "Send the displayed question")
            self.assertEqual(reply.waiting_for, THREAD)
            sent = self.agent_messages()
            self.assertEqual(len(sent), 1)
            self.assertEqual(sent[0].text, disclosure.with_disclosure(question))
            self.assertEqual(reports.for_request(REQUEST), [])
            self.assertEqual(checkpoints.load(key)["waiting_for"]["kind"], "outside")
            self.assertEqual(runtime.client().calls, 0, "approval replay must use the saved program")
            service.on_outside_reply(THREAD, "units_column=measure_a")
            self.assertEqual(len(self.agent_messages()), 1)
            self.assertEqual(approvals.pending(), [])

    def test_fixed_question_owned_by_code_still_runs_without_approval(self):
        with fixed_run(TASK, "code-template", backend=BACKEND):
            runs.new_run("code-template")
            checkpoints.start("code-template", path="agent", request_id=REQUEST)
            reply = outside.ask("code-template", "", template="units_column")
            self.assertEqual(reply.waiting_for, THREAD)
            self.assertEqual(len(self.agent_messages()), 1)
            self.assertEqual(approvals.pending(), [])

    def test_approval_replays_the_saved_inner_call_without_recomputing_prior_effects(self):
        from sandbox import charts, db
        key = "program-exact"
        program = ('import time\n'
                   'q = call("query_sales", {"period":"2026Q3"})["output"]\n'
                   'call("render_chart", {"title":"Revenue", "labels":["Q3"], '
                   '"values":[q["total_revenue"]]})\n'
                   'result = call("ask_stranger", {"question":"Units? " + str(time.time_ns())})')
        with fixed_run(TASK, key, backend=BACKEND, overrides=["code_calls.batch_reports=on"]):
            runs.new_run(key)
            runtime.client().backend.responses = [([tool("run_program", {"code": program})],
                                                    "tool_use", Usage(10, 5))]
            result = loop.run(key, REQUEST, "Clarify before proceeding", registry=tools.build(REQUEST))
            self.assertEqual(result.reason, "awaiting_approval")
            approval = approvals.pending()[0]
            shown = approval["call"]["args"]["question"]
            before = charts.for_request(REQUEST)
            self.assertEqual(len(before), 1)
            with db.connect() as conn:
                conn.execute("UPDATE orders SET unit_price = unit_price + 1")
            reply = service.decide_approval(approval["id"], True, "Send this exact displayed question")
            self.assertEqual(reply.waiting_for, THREAD)
            self.assertEqual(charts.for_request(REQUEST), before)
            self.assertEqual([m.text for m in self.agent_messages()], [shown])
            self.assertEqual(approvals.pending(), [])
