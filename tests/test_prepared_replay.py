"""Prepared plan calls survive interruption without changing authorized arguments."""

from copy import deepcopy
from unittest import mock

from agent import checkpoints, plan, runs, tools
from harness import runtime
from sandbox import pending, reports
from tests.support import ScratchTest, fixed_run
from tests.test_agent_plan import RID, TASK


class PreparedReplayTest(ScratchTest):
    def test_plan_resume_writes_the_prepared_email_without_preparing_it_again(self):
        # Re-entering EmailGate on replay can change a checked draft and its
        # idempotency key. Interrupt after real critique saves its exact call.
        class InterruptedAfterPreparation(BaseException):
            pass

        run_key = "prepared-plan-email"
        with fixed_run(TASK, run_key, backend="tests.fixtures.agent_milestone_model:MilestoneModel"):
            runs.new_run(run_key)

            def interrupt_before_draft(request_id):
                registry = tools.build(request_id)
                real_call = registry.call

                def call(name, args, caller, **kwargs):
                    if name == "draft_report_email":
                        raise InterruptedAfterPreparation
                    return real_call(name, args, caller, **kwargs)

                registry.call = call
                return registry

            with self.assertRaises(InterruptedAfterPreparation):
                plan.run(run_key, [RID], "Prepare the report and its email draft.",
                         registry_factory=interrupt_before_draft)

            state = checkpoints.load(run_key)
            saved_call = deepcopy(state["plan_state"]["pending_call"])
            self.assertEqual(saved_call["tool"], "draft_report_email")
            self.assertNotEqual(saved_call["args"]["body"], "Report prepared.")
            self.assertEqual(len(reports.for_request(RID)), 1)
            self.assertEqual(pending.for_request(RID), [])
            calls_before_resume = runtime.client().calls
            revisions = [line for line in runtime.trace().lines()
                         if line.get("type") == "model_call" and line.get("purpose") == "critique_revision"]
            self.assertEqual(len(revisions), 1)

            with mock.patch("agent.loop.EmailGate", side_effect=AssertionError("prepared email entered EmailGate again")):
                runs.resume(run_key, {"kind": "crash"})

            self.assertEqual(checkpoints.load(run_key)["end_reason"], "done")
            self.assertEqual(runtime.client().calls, calls_before_resume)
            drafted = pending.for_request(RID)
            self.assertEqual(len(drafted), 1)
            self.assertEqual({key: drafted[0][key] for key in ("recipient", "subject", "body", "report_id")},
                             saved_call["args"])
            self.assertEqual(len(reports.for_request(RID)), 1)
            completed_calls = [line["name"] for line in runtime.trace().lines()
                               if line.get("type") == "tool_call"]
            self.assertEqual(completed_calls,
                             ["parse_file", "query_sales", "render_chart", "save_report", "draft_report_email"])
