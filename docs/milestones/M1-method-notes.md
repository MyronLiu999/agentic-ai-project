# M1 measurement notes

These details accompany the concise [main report](M1.md) and preserve source,
chronology and counting context from the expanded team write-up.

### A1 source and benefit definition

Prior evidence comes from Myron's A1 commit `65125727e233902e9d69ba9655e4fe1a6ec4c715`, using OpenAI
`gpt-4.1-mini`, with 60 runs per arm (six issues, ten runs each). Source and read date:
[A1 report JSON](https://github.com/MyronLiu999/agentic-ai-assignment1/blob/65125727e233902e9d69ba9655e4fe1a6ec4c715/reports/LAB_01.json),
2026-10-31. These are issue-triage results, not measurements of this sales analyst or its
configured `gpt-4o-mini` model.



Recomputed from that JSON: `m = agent mean cost / workflow mean cost = 3.34194` and
`c = $0.000595960`. The source defines `f` precisely as the fraction of six issues for which
workflow passes fewer than five of ten runs and agent passes at least five of ten. None qualify:
`f = 0/6 = 0`. This is not a per-run fallback probability. The report's analysis fields are null;
these values are explicitly derived from its cost and per-issue counts using the
[A1 format definitions](https://github.com/MyronLiu999/agentic-ai-assignment1/blob/65125727e233902e9d69ba9655e4fe1a6ec4c715/checks/FORMATS.md)
(read 2026-10-31).

### Development repairs before measurement

The first real development sweep passed 3/6 cases; its batch proposals omitted
write outcomes and exhausted planning retries. The pre-baseline prompt repair
required an explicit predicate on every step and supplied a complete scoped
five-step example. The second sweep passed 5/6. Its first proposal still omitted
chart output bindings; validation caught this and the replacement fixed it.
Neither dependency declarations nor a parse row count alone establish semantic
correctness. In particular, the remaining messy-file failure ignored file unit
facts despite structurally correct parsing, which the independent check caught.

### Semantic argument counting

Argument counting uses the recorded schemas, not today's checker outcomes. The on-arm
`report_id=0` call is schema-valid but fails the report-ownership gate: it contributes one
boundary rejection and one semantic error, not a malformed-schema call. Semantic counts
cover wrong recipients in model plan steps/revisions, missing/incorrect named report figures,
and invalid report references. Each argument candidate counts once, including rejected or
unexecuted proposals; copied critique-approved plans do not count again. The inventory excludes
free prose and parsing-option judgments. `semantic_annotations.json` cites physical trace
lines, exact observed arguments and supporting facts; the generator verifies those citations.
Baseline has 14 such candidates across 7 runs and 2 rejected plan proposals. These additional
diagnostics do not change the historical scores or the pass's prospective decision rule.
