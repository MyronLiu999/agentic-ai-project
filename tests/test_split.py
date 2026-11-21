"""Independent role returns and combined sandbox effects share one task budget."""

from copy import deepcopy
import json
from pathlib import Path
from unittest import mock

from agent import bounds, checkpoints, messages, runs, split, tools
from harness import ROOT, runtime
from sandbox import charts, db, inbox, pending, reports
from tests.support import ScratchTest, check_run, fixed_run

TASK = "tasks/batch_reports_two.yaml"
IDS = ("REQ-SYN-thread-1301", "REQ-SYN-thread-1302")
MODEL = "tests.fixtures.split_model:SplitModel"


class SplitTest(ScratchTest):
    def start(self, **kwargs):
        runs.new_run("operator")
        return split.run("operator", IDS, "Make the standard Q3 reports and draft each email.", **kwargs)

    def test_two_roles_use_distinct_tool_surfaces_and_observed_returns(self):
        with fixed_run(TASK, "split-batch", backend=MODEL):
            reply = self.start()
            checked = check_run(TASK, "split-batch", replies=[reply.text])
            self.assertTrue(checked["passed"], checked["reason"])
            self.assertEqual(checked["measures"]["reports"], 2)
            self.assertEqual(checked["measures"]["emails"], 2)
            model = runtime.client().backend
            for request in model.requests:
                offered = {tool["name"] for tool in request["tools"]}
                if request["system"].startswith("Split role: analyst"):
                    self.assertEqual(offered, {"parse_file", "query_sales"})
                elif request["system"].startswith("Split role: writer"):
                    self.assertEqual(offered, {"render_chart", "save_report", "draft_report_email"})
            returned = [line for line in runtime.trace().lines() if line["type"] == "split_return"]
            self.assertEqual(len(returned), 4)
            self.assertTrue(all(line["valid"] for line in returned))
            self.assertEqual([r["contract"]["spent"]["tool_calls"] for r in returned], [2, 3, 2, 3])
            self.assertTrue(all("invented-search" not in r["contract"]["searched"] for r in returned))
            self.assertEqual(sum(r["spent_tokens"] for r in returned), runtime.client().total_tokens)
            self.assertLessEqual(runtime.client().total_tokens, bounds.TOKEN_BUDGET)
            self.assertEqual({r["parent_id"] for r in returned}, {"split-batch"})
            calls = [r for r in runtime.trace().lines() if r["type"] == "model_call"]
            self.assertTrue(all(r.get("agent_id") and r.get("parent_id") == "split-batch" for r in calls))

    def test_malformed_return_is_rejected_and_traced_before_writer_effects(self):
        with fixed_run(TASK, "split-malformed", backend=MODEL):
            runtime.client().backend.bad_return = True
            self.start()
            self.assertEqual(reports.for_request(IDS[0]), [])
            returned = [line for line in runtime.trace().lines() if line["type"] == "split_return"]
            self.assertEqual(len(returned), 1)
            self.assertFalse(returned[0]["valid"])
            self.assertIn("status", str(returned[0]["errors"]))

    def test_unoffered_write_is_refused_before_registry_or_sandbox(self):
        with fixed_run(TASK, "split-surface", backend=MODEL):
            runtime.client().backend.unauthorized_read_role = True
            self.start()
            self.assertEqual(reports.for_request(IDS[0]), [])
            self.assertEqual(pending.all_pending(), [])
            self.assertTrue(any(r.get("rejected_by") == "split_surface" for r in runtime.trace().lines()))

    def test_combined_check_rejects_divergent_end_state_after_valid_role_returns(self):
        with fixed_run(TASK, "split-divergent", backend=MODEL):
            self.start()
            state = checkpoints.load("split-divergent")["split_state"]
            self.assertTrue(split.check_end_state(IDS, state["returns"])[0])
            record = reports.latest(IDS[1])
            figures = json.loads(record["figures_json"])
            figures["total_revenue"] += 1
            with db.connect() as conn:
                conn.execute("UPDATE reports SET figures_json = ? WHERE id = ?",
                             (json.dumps(figures), record["id"]))
            passed, problems = split.check_end_state(IDS, state["returns"])
            self.assertFalse(passed)
            self.assertIn(IDS[1], str(problems))

    def test_one_budget_refuses_a_call_that_cannot_fit_even_for_the_first_role(self):
        with fixed_run(TASK, "split-budget", backend=MODEL):
            self.start(limits=bounds.Limits(max_steps=48, token_budget=1000))
            self.assertEqual(runtime.client().calls, 0)
            self.assertEqual(reports.for_request(IDS[0]), [])
            state = checkpoints.load("split-budget")
            self.assertEqual(state["end_reason"], "agent_budget")
            returned = [line for line in runtime.trace().lines() if line["type"] == "split_return"]
            self.assertEqual(returned[-1]["status"], "out_of_budget")

    def test_budget_is_shared_across_roles_instead_of_reset_at_writer(self):
        with fixed_run(TASK, "split-shared-budget", backend=MODEL):
            model = runtime.client().backend
            original = model.create
            def costly(**kwargs):
                content, reason, name, usage = original(**kwargs)
                usage.input_tokens = 12000
                return content, reason, name, usage
            with mock.patch.object(model, "create", side_effect=costly):
                self.start(limits=bounds.Limits(max_steps=48, token_budget=50000))
            self.assertLessEqual(runtime.client().total_tokens, 50000)
            self.assertEqual(reports.for_request(IDS[0]), [])
            state = checkpoints.load("split-shared-budget")
            self.assertEqual(state["end_reason"], "agent_budget")

    def test_stop_after_write_records_result_and_resume_does_not_repeat_it(self):
        from policy import flags
        with fixed_run(TASK, "split-stop", backend=MODEL):
            def factory(rid):
                registry = tools.build(rid)
                original = registry.call
                def call(name, args, caller, **kwargs):
                    result = original(name, args, caller, **kwargs)
                    if name == "save_report" and rid == IDS[0]:
                        flags.stop_run("split-stop")
                    return result
                registry.call = call
                return registry
            self.start(registry_factory=factory)
            self.assertEqual(len(reports.for_request(IDS[0])), 1)
            self.assertEqual(pending.all_pending(), [])
            state = checkpoints.load("split-stop")
            self.assertEqual(state["end_reason"], "stopped")
            flags.clear_stop("split-stop")
            with runs._resume_scope("split-stop"):
                split.resume_from(state, {"kind": "stop_resume"})
            self.assertEqual(len(reports.for_request(IDS[0])), 1)
            self.assertEqual(len(pending.all_pending()), 2)
            calls = [r for r in runtime.trace().lines() if r["type"] == "tool_call"
                     and r.get("name") == "save_report"]
            self.assertEqual(len(calls), 2)

    def test_duplicate_scope_is_refused_before_any_model_or_tool(self):
        with fixed_run(TASK, "split-scope", backend=MODEL):
            runs.new_run("operator")
            reply = split.run("operator", [IDS[0], IDS[0]], "Prepare reports.")
            self.assertEqual(runtime.client().calls, 0)
            self.assertEqual(reports.for_request(IDS[0]), [])
            self.assertIn("distinct", reply.text)

    def test_every_writer_call_uses_the_registry_approval_hook_and_exact_resume(self):
        from tests.fakes import FakeApprovals
        with fixed_run(TASK, "split-approval", backend=MODEL), FakeApprovals().install() as approvals:
            def factory(rid):
                registry = tools.build(rid)
                original = registry._pre_call_hook
                def gate(**call):
                    decision = original(**call)
                    if decision.get("answer") == "allow" and call["spec"].name == "save_report":
                        if not approvals.is_approved("split-approval", call["key"]):
                            return {"answer": "ask", "action_class": "save_report/own_request",
                                    "reason": "operator rule", "screen": {"request_id": rid}}
                    return decision
                registry._pre_call_hook = gate
                return registry
            self.start(registry_factory=factory)
            self.assertEqual(reports.for_request(IDS[0]), [])
            first = approvals.pending()[0]
            state = checkpoints.load("split-approval")
            self.assertEqual(state["split_state"]["prepared_args"], first["call"]["args"])
            runs.resume("split-approval", {"kind": "approval", "approval_id": "wrong-id", "approved": True})
            self.assertEqual(reports.for_request(IDS[0]), [])
            self.assertEqual(checkpoints.waiting()[0]["ref"], first["id"])
            self.assertEqual(checkpoints.load("split-approval")["waiting_for"]["ref"], first["id"])
            for _ in range(2):
                item = approvals.pending()[0]
                approvals.decide(item["id"], True)
                with runs._resume_scope("split-approval"):
                    split.resume_from(checkpoints.load("split-approval"),
                        {"kind": "approval", "approval_id": item["id"], "approved": True}, registry_factory=factory)
            self.assertEqual(len(pending.all_pending()), 2)
            self.assertEqual(approvals.pending(), [])
            queries = [line for line in runtime.trace().lines()
                       if line["type"] == "tool_call" and line.get("name") == "query_sales"]
            self.assertEqual(len(queries), 2)

    def test_return_result_schema_rejects_boolean_record_ids(self):
        with fixed_run(TASK, "split-result-schema", backend=MODEL):
            runtime.client().backend.bad_writer_type = True
            self.start()
            returned = [r for r in runtime.trace().lines() if r["type"] == "split_return"]
            self.assertFalse(returned[-1]["valid"])
            self.assertIn("integer", str(returned[-1]["errors"]))


    def test_stop_during_first_model_response_resumes_without_paying_twice(self):
        from policy import flags
        with fixed_run(TASK, "split-response-stop", backend=MODEL):
            model, stopped = runtime.client().backend, []
            original = model.create
            def stop_after_response(**kwargs):
                response = original(**kwargs)
                if not stopped:
                    stopped.append(True)
                    flags.stop_run("split-response-stop")
                return response
            with mock.patch.object(model, "create", side_effect=stop_after_response):
                self.start()
                self.assertEqual(checkpoints.load("split-response-stop")["end_reason"], "stopped")
                self.assertEqual(runtime.client().calls, 1)
                flags.clear_stop("split-response-stop")
                runs.resume("split-response-stop", {"kind": "stop_resume"})
            self.assertEqual(checkpoints.load("split-response-stop")["end_reason"], "done")
            self.assertEqual(runtime.client().calls, 14)
            self.assertEqual(checkpoints.load("split-response-stop")["split_state"]["tokens"], 2100)

    def test_stop_during_final_role_response_reuses_the_saved_return(self):
        from policy import flags
        for role in ("analyst", "writer"):
            run_key = "split-final-stop-" + role
            with self.subTest(role=role), fixed_run(TASK, run_key, backend=MODEL):
                model, stopped = runtime.client().backend, []
                original = model.create
                def stop_after_response(**kwargs):
                    response = original(**kwargs)
                    if not stopped and kwargs["system"].startswith("Split role: " + role) and response[1] == "end_turn":
                        stopped.append(True)
                        flags.stop_run(run_key)
                    return response
                with mock.patch.object(model, "create", side_effect=stop_after_response):
                    self.start()
                    self.assertEqual(checkpoints.load(run_key)["end_reason"], "stopped")
                    flags.clear_stop(run_key)
                    runs.resume(run_key, {"kind": "stop_resume"})
                self.assertEqual(checkpoints.load(run_key)["end_reason"], "done")
                self.assertEqual(runtime.client().calls, 14)

    def test_stop_during_critique_revision_reuses_the_saved_response(self):
        from harness.client import Usage
        from policy import flags
        with fixed_run(TASK, "split-critique-stop", backend=MODEL):
            model, revisions, changed = runtime.client().backend, [], []
            original = model.create
            def revise_and_stop(**kwargs):
                if kwargs["system"].startswith("Revise this email"):
                    draft = json.loads(kwargs["messages"][0]["content"])["draft"]
                    revisions.append(True)
                    flags.stop_run("split-critique-stop")
                    result = {k: draft[k] for k in ("recipient", "subject", "body")}
                    result["subject"] = "Quarterly report"
                    return [{"type": "text", "text": json.dumps(result)}], "end_turn", "says-done", Usage(100, 50)
                response = original(**kwargs)
                if not changed and response[1] == "tool_use" and response[0][0].get("name") == "draft_report_email":
                    response[0][0]["input"]["subject"] = "Confidential margin details"
                    changed.append(True)
                return response
            with mock.patch.object(model, "create", side_effect=revise_and_stop):
                self.start()
                self.assertEqual(checkpoints.load("split-critique-stop")["end_reason"], "stopped")
                flags.clear_stop("split-critique-stop")
                resumed = runs.resume("split-critique-stop", {"kind": "stop_resume"})
            self.assertEqual(len(revisions), 1)
            self.assertEqual(checkpoints.load("split-critique-stop")["end_reason"], "done", resumed.text)
            self.assertEqual(runtime.client().calls, 15)

    def test_writer_cannot_claim_existing_artifacts_without_successful_calls(self):
        with fixed_run(TASK, "split-reuse", backend=MODEL):
            self.start()
            state = checkpoints.load("split-reuse")["split_state"]
            coordinator = split._Coordinator("operator", IDS, state["text"], tools.build,
                                             bounds.Limits(max_steps=48), None)
            coordinator.state.update(role="writer", returns=state["returns"], ledger=[])
            with self.assertRaisesRegex(split.SplitError, "observed|ledger|successful"):
                coordinator.return_contract(state["returns"][IDS[0]]["writer"])
            self.assertFalse([r for r in runtime.trace().lines() if r["type"] == "split_return"][-1]["valid"])

    def test_writer_cannot_substitute_an_id_from_another_successful_writer(self):
        with fixed_run(TASK, "split-reuse-other", backend=MODEL):
            self.start()
            state = checkpoints.load("split-reuse-other")["split_state"]
            coordinator = split._Coordinator("operator", IDS, state["text"], tools.build,
                                             bounds.Limits(max_steps=48), None)
            # The last role's ledger is from request two; request one's IDs are real
            # but were never returned by calls in that ledger.
            coordinator.state.update(role="writer", returns=state["returns"], ledger=state["ledger"])
            with self.assertRaisesRegex(split.SplitError, "observed|ledger|successful"):
                coordinator.return_contract(state["returns"][IDS[0]]["writer"])

    def test_console_runs_have_distinct_effects_and_independent_end_state_checks(self):
        with fixed_run(TASK, "seed-console", backend=MODEL), mock.patch.object(runtime, "_run", None), runtime.in_session("console"):
            keys = []
            for _ in range(2):
                keys.append(runs.new_run("console"))
                split.run("console", IDS, "Prepare the standard reports.")
                self.assertEqual(checkpoints.load(keys[-1])["end_reason"], "done")
            self.assertNotEqual(keys[0], keys[1])
            for rid in IDS:
                self.assertEqual(len(reports.for_request(rid)), 2)
                self.assertEqual(len(pending.for_request(rid)), 2)
                self.assertEqual(len(charts.for_request(rid)), 2)
            for key in keys:
                state = checkpoints.load(key)["split_state"]
                self.assertTrue(split.check_end_state(IDS, state["returns"], evidence=state["evidence"])[0])

    def test_combined_check_rechecks_persisted_subject_and_report_body(self):
        for target in ("subject", "report_body"):
            key = "split-tamper-" + target
            with self.subTest(target=target), fixed_run(TASK, key, backend=MODEL):
                self.start()
                state = checkpoints.load(key)["split_state"]
                with db.connect() as conn:
                    if target == "subject":
                        conn.execute("UPDATE pending SET subject = 'Confidential margin details' WHERE request_id = ?", (IDS[0],))
                    else:
                        conn.execute("UPDATE reports SET body = 'Revenue 9999999999.00 in 2025-Q3' WHERE request_id = ?", (IDS[0],))
                passed, problems = split.check_end_state(IDS, state["returns"])
                self.assertFalse(passed, problems)

    def test_combined_check_rechecks_persisted_chart_values_and_svg(self):
        for target in ("values", "svg"):
            key = "split-chart-" + target
            with self.subTest(target=target), fixed_run(TASK, key, backend=MODEL):
                self.start()
                state = checkpoints.load(key)["split_state"]
                chart = charts.for_request(IDS[0])[0]
                if target == "values":
                    with db.connect() as conn:
                        conn.execute("UPDATE charts SET values_json = '[9999999999]' WHERE id = ?", (chart["id"],))
                else:
                    Path(chart["path"]).write_text("<svg>9999999999</svg>")
                passed, problems = split.check_end_state(IDS, state["returns"])
                self.assertFalse(passed, problems)

    def test_addition_consumed_by_analyst_survives_writer_start_and_resume(self):
        from policy import flags
        with fixed_run(TASK, "split-addition", backend=MODEL):
            model, added = runtime.client().backend, []
            original = model.create
            def add_then_stop(**kwargs):
                response = original(**kwargs)
                if not added:
                    messages.intercept("operator", "/add Include the account reference in every draft.")
                    added.append(True)
                elif len(added) == 1:
                    added.append(True)
                    flags.stop_run("split-addition")
                return response
            with mock.patch.object(model, "create", side_effect=add_then_stop):
                self.start()
                self.assertEqual(messages.pending("operator"), [])
                flags.clear_stop("split-addition")
                runs.resume("split-addition", {"kind": "stop_resume"})
            self.assertEqual(checkpoints.load("split-addition")["end_reason"], "done")
            writer_starts = [r for r in model.requests if r["system"].startswith("Split role: writer")]
            self.assertTrue(writer_starts)
            for request in writer_starts:
                self.assertIn("Include the account reference in every draft.", json.dumps(request["messages"]))
            self.assertEqual(checkpoints.load("split-addition")["split_state"]["operator_additions"],
                             ["Include the account reference in every draft."])


    def test_addition_survives_a_crash_after_mailbox_consumption(self):
        with fixed_run(TASK, "split-addition-crash", backend=MODEL):
            model = runtime.client().backend
            original_model, original_consume = model.create, messages.consume
            injected = []
            def add(**kwargs):
                response = original_model(**kwargs)
                if not injected:
                    messages.intercept("operator", "/add Preserve the account reference in each draft.")
                    injected.append(True)
                return response
            def crash_after_consume(key):
                additions = original_consume(key)
                if additions:
                    raise RuntimeError("process lost after durable mailbox consumption")
                return additions
            with mock.patch.object(model, "create", side_effect=add), \
                    mock.patch.object(messages, "consume", side_effect=crash_after_consume):
                with self.assertRaisesRegex(RuntimeError, "process lost"):
                    self.start()
            state = checkpoints.load("split-addition-crash")
            self.assertEqual(state["split_state"]["operator_additions"], [])
            self.assertEqual(messages.pending("operator"), [])
            runs.resume("split-addition-crash", {"kind": "crash"})
            self.assertEqual(checkpoints.load("split-addition-crash")["end_reason"], "done")
            for request in model.requests[1:]:
                self.assertIn("Preserve the account reference in each draft.", json.dumps(request["messages"]))


class SplitTaskMatrixTest(ScratchTest):
    def test_every_official_task_runs_on_the_split_branch_configuration(self):
        from tests.fixtures.outside_m2 import install
        task_files = sorted((ROOT / "tasks").glob("*.yaml")) + sorted((ROOT / "tasks/sessions").glob("*.yaml"))
        for task in task_files:
            backend = MODEL
            if task.name.startswith("outside_"):
                backend = "tests.fixtures.outside_m2:OutsideModel"
            elif task.name.startswith("long_"):
                backend = "tests.fixtures.context_session_model:LongSessionModel"
            with self.subTest(task=task.name), install():
                record = self.run_task(str(task), "split-matrix-" + task.stem, backend=backend,
                                       overrides=["topology=split"])
                self.assertTrue(record["passed"], record.get("error") or record["check"])
                ceiling = 400000 if task.parent.name == "sessions" else bounds.TOKEN_BUDGET
                self.assertLessEqual(record["tokens"]["total"], ceiling)
                if task.name == "batch_reports_two.yaml":
                    self.assertEqual(record["measures"]["requests_done"], 2)
