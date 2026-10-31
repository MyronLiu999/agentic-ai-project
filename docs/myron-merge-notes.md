# Myron merge notes

These items were moved out of the four shared conflict files so `myron` can merge
`claudea/domain` without another text conflict. Apply them to the final merged
documents after the branch merge.

## CHANGES.md additions

- Validating registry with fixed tool order, caller allowlists, fail-closed hook,
  bounded transient retries, result validation, derived write keys and bounded
  trace records.
- Six request-scoped sandbox tools and per-tool examples/strict switches.
- Registry, tool, definition-cost and basic-analysis tests.
- `scripts/definition_cost.py`, assignment references and the completed Part 3
  tool evidence.
- File and sales reads return at most 50 rows; SVG charts render at most 20 bars
  and report truncation; known transient failures get at most two retries.
- Stable canonical write-key and protocol-error design adapted from Myron Liu's
  Assignment 3 repository, commit
  `eb6b35703b212474b561099ec265c427174c7a4b`.

## README.md addition

Definition-token measurement:

```bash
python scripts/definition_cost.py
```

## M1.md addition

The full pre-merge M1 text, including the completed Myron Part 3, is preserved
in `docs/milestones/M1-myron-contribution.md`.

## Analysis compatibility

Claudea's richer CLI remains at `experiments/analysis/analyze.py`. Myron's
earlier root-oriented `load_records()` / `analyze()` API is preserved at
`experiments/analysis/basic_analyze.py` with its test import updated.
