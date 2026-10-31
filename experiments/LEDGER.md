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
- **Results:** pending
- **Difference:** pending
- **Verdict:** pending
- **Links:** [before](../results/pass1-examples-off/), [after](../results/pass1-examples-on/)
