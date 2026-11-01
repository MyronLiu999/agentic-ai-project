# The ledger

One entry per pass: copy the template to the end of this file, under `## Pass N · <the
problem, in a few words>`. The Project page says what each field holds and when to commit
it. `make check` reads every `##` section but the template: see the README's "make check".

## Template

- **Pass:** <its number, the problem, the fix>
- **Owner:** <a member>
- **Problem:** <the symptom>
- **Evidence:** <run IDs and trace lines>
- **Why this fix:** <your reason>
- **Prediction:** <per arm, with a number>
- **Arms:** <each arm's folder and switches>
- **Held constant:** <what did not change>
- **Tasks and sweeps:** <test tasks, sweeps per arm>
- **Results:** <per arm, with counts>
- **Difference:** <after minus before>
- **Verdict:** <keep or drop, and the switch's setting>
- **Links:** <results/<arm>/ for every arm>

## Pass 1 · Preserve uploaded unit totals in saved reports

- **Pass:** 1; add a concrete save_report argument example behind examples.save_report (Lecture 3, slide 18).
- **Owner:** Myron Liu.
- **Problem:** One of three baseline messy-file runs saved database totals but omitted the parsed file's distinct unit total, so a completed report failed the independent check.
- **Evidence:** baseline-messy_file_semicolon-s01-1799cc; results/baseline/baseline-messy_file_semicolon-s01-1799cc.trace.jsonl:7 reads the upload, :15 saves figures without file_total_units, :18 passes the narrower email critique, and :28 records the independent failure. Baseline was 17/18 overall, messy_file_semicolon 2/3, with one false finish and one critique miss.
- **Why this fix:** The caller chose the correct write but supplied incomplete business figures. A concrete argument example can teach the missing distinction (L3 slide 18) without changing the task, checks or tools. The existing prose did not reliably induce preservation of the parsed total. The example uses unrelated synthetic numbers and instructs replacement with actual request/query/file facts. A1/A2 results are not used to claim an example benefit; A3's larger definitions warn that added examples cost tokens.
- **Prediction:** Off: messy_file_semicolon 2/3 and 17/18 overall; on: messy_file_semicolon 3/3 and 18/18 overall. Predict one fewer missing-file-total failure, false finish and critique miss; malformed-call counts remain zero. Predict on-arm mean tokens/run no more than 25% above off. Keep on only if target passes increase, total passes do not fall, and mean token growth stays within 25%; otherwise retain off, labeling equal or mixed results inconclusive at this size. These are prospective small-sample predictions, not guaranteed outcomes.
- **Arms:** results/pass1-examples-off/ with --set examples.save_report=off; results/pass1-examples-on/ with --set examples.save_report=on. Both arms start only after this prediction commit is pushed. Alternate completed sweeps off1,on1,off2,on2,off3,on3 using increasing --sweeps limits (the runner skips finished runs). Baseline is historical evidence, never reused as the before arm.
- **Held constant:** Same clean code and model configuration (gpt-4o-mini; served snapshot recorded per run), provider/key, tool order, schemas, all other switches, fixtures/checks, bounds, jobs=1 and runner. Only examples.save_report changes. Coding and measured pass runs use myron per the user's hold on main; both arms run the identical commit. Baseline was run on clean main, commit 71b13b9.
- **Tasks and sweeps:** All six official tasks, 3 sweeps per arm (18 runs each): batch_reports_two, compare_check_last_quarter, messy_file_semicolon, out_of_scope_margins, standard_report_clean, status_question_done_work. The first three belong to the agent path; the target problem appeared in messy_file_semicolon. Record target and remaining-task effects separately.
- **Results:** Both arms completed 18 runs (6 tasks x 3 sweeps), all non-free and dirty=false on commit 2e18da0dca47b211ea516fe1a0fa1e1dd49d08c2, after prediction commit 2026-10-31T16:08:46-05:00. Off: 15/18 overall (sweeps 4/6,5/6,6/6); on: 14/18 (5/6,5/6,4/6). Target messy_file_semicolon: 3/3 in both arms, zero missing-file-total failures. Other tasks off/on: batch 1/3 vs 0/3; comparison 2/3 vs 2/3; standard/status/out-of-scope each 3/3 vs 3/3. Off/on total tokens 66,030/64,615, mean tokens/run 3,668.33/3,589.72, total cost $0.010039/$0.009143, mean cost/run $0.00055772/$0.00050794. Target-only mean tokens 8,089.67/9,847.33. Boundary rejections 0/1 (the on-arm comparison s02 prematurely used report_id=0, recovered and passed); critique misses 0/1, held task turns 3/3. Analyzer endpoint false-finishes are 3/4 because the final status follow-up says done after held work; inspecting the initial task turn gives 0/1 false finishes, with the other three per arm explicitly held. No request-scoped exact repeats, initial misroutes or bound endings. Summary, audit/hash inventory and every failed-run signal are in experiments/evidence/pass1_summary.json, pass1_audit.json and pass1_failures.json.
- **Difference:** On minus off: target passes 0, overall passes -1 (-5.56 percentage points); mean tokens -78.61 (-2.14%), mean cost -$0.00004978 (-8.93%); target-only mean tokens +1,757.67 (+21.73%). Critique misses +1, task-turn false finishes +1, boundary rejections +1. The aggregate token reduction accompanies fewer completed batch steps and is not evidence of more efficient successful work. The original target failure did not recur in either fresh arm. Batch failures retained the planner's literal example recipient after revision (2 off, 3 on); this shared-path issue is outside the tested save_report description. Three repeats per task cannot establish a causal regression or benefit.
- **Verdict:** Drop activation; retain examples.save_report=off, already the default in switches.yaml. The predeclared target-improvement condition is not met and total passes fell, although the aggregate token cap was met. Keep the dormant switch implementation and all runs for reproducibility; no extra retries, post-hoc changes or substitute runs. This is an inconclusive/negative result at this sample size, not a claim that examples never help. Batch recipient binding and comparison figure completeness remain separate future work; no merge to main.
- **Links:** [before](../results/pass1-examples-off/), [after](../results/pass1-examples-on/)
