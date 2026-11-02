# M1 submission status

Updated 2026-11-01. Repository: https://github.com/MyronLiu999/agentic-ai-project

The final release marker is `m1`. It includes the post-measurement code,
documentation and UI corrections; the historical baseline and Pass 1 still cite
their original commits and unchanged records. Pass 1's negative result remains
reported, and `examples.save_report` stays off. No second measured pass is claimed.

Verified during finalization:

- The full 380-test suite passed. After the greeting fix and bundle consistency
  regression were added, all 21 focused workflow/demo/credential tests passed.
- All four `harness.check` checks passed; `experiments.analysis.recompute --check`
  verified six derived artifacts without changing raw runs/traces.
- M1 has approximately 1,800 prose words, retaining all 19 tables and contributor
  disclosures. The decision table has no empty cells or draft introduction.
- A live API connectivity check succeeded using the configured model. The local
  400 error came from a control character in the process API key, not the CSV.
- A live standard-report Console turn created a report, chart and pending email
  after the greeting correction. Its prior placeholder hold was retained in local
  history. These smoke checks are not a new measured pass or a reliability estimate.
- The local demo uses the team's requested contacts. Repository fixtures remain
  synthetic; local overrides and their matching download stay under ignored state.
- A separate clone installed requirements into a new virtual environment, seeded
  its own demo, and served all six checked pages with HTTP 200. Its ten focused
  credential/demo/chart-email tests passed.
- Final `main` and annotated `m1` are published together. The previous remote
  `m1` target was `e121df6`; that commit remains in main's history. The tag now
  includes the final submission fixes, rather than an earlier document revision.

**Canvas remains unverified.** The assignment link opens the university login
landing page in this session. No submission or submission receipt is visible.
The team must sign in, post/confirm the repository URL at
[the M1 assignment](https://canvas.uchicago.edu/courses/75218/assignments/921328),
and retain the receipt. This checklist does not claim that Canvas was submitted.

Real mailbox delivery, automatic continuation after outside replies, and
automatic restoration of interrupted execution remain outside the implemented
M1 scope. Report emails can be downloaded with embedded PNG charts; sending
inside the app writes to the simulated local channel.
