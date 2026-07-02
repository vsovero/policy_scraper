# Step 1 Clean Runtime Import Fix Review

Reviewed on 2026-07-02 by the Step 1 review stream.

## Decision

**PASS.**

Commit `c1779aaa0526ee5d6ca1c1c03e2f040f046fc0bc` correctly fixes the
clean-runtime Step 1 import blocker. The committed Step 1 production path now
imports from a clean checkout with `PYTHONPATH=src`, the focused tests pass, and
the helper fix is general rather than row-specific.

## Commit Reviewed

- `c1779aaa0526ee5d6ca1c1c03e2f040f046fc0bc`
- Commit title: `Restore Step 1 clean import helpers`
- Review worktree:
  `/Users/verosovero/Dropbox/Course repetition IPEDS/policy_scraper_step1_import_fix`

## Files Reviewed

Changed by the commit:

- `src/course_policy/batch2_year_candidates.py`
- `tests/test_batch2_year_candidates.py`
- `tests/test_step1_proof_to_scale_url_production.py`

The commit does not edit current status files, standards documents, generated
outputs, source code outside the helper slice, or unrelated tests.

## Diff Assessment

The commit restores the clean dependency closure needed by
`course_policy.step1_proof_to_scale_url_production`:

- `catalog_year_range(text: object)` is added as a public helper for
  catalog-like academic year spans. It handles long historical spans such as
  `1970-2012`, full-year and two-digit end-year ranges, compact catalog file
  names, and older 18xx/19xx/20xx ranges, while rejecting malformed or
  out-of-bounds ranges.
- `candidate_priority(text)` is made object-safe through `clean_text`.
- `candidate_document_priority(row)`,
  `candidate_selection_sort_columns(prefix_columns)`, and
  `add_candidate_selection_rank_columns(candidates)` are restored as general
  candidate-ranking helpers for catalog/document selection.

The fix is not row-specific. It does not name Drill 012 rows, institutions,
states, URLs, sectors, or one-off target years. The logic is reusable parsing
and ranking code based on catalog-year and document-type evidence.

## Required Checks

Mandatory clean-runtime import check:

```text
PYTHONPATH=src ../.venv/bin/python -c "import course_policy.step1_proof_to_scale_url_production; print('import ok')"
```

Result: **passed** with `import ok`.

Focused tests:

```text
PYTHONPATH=src ../.venv/bin/python -m pytest tests/test_batch2_year_candidates.py tests/test_clean_no_legacy_benchmark.py tests/test_step1_proof_to_scale_url_production.py tests/test_step1_production_input_builder.py tests/test_step1_production_runner.py tests/test_production_release_url_stage.py tests/test_production_quality_gate.py tests/test_production_streams.py
```

Result: **124 passed**.

## Scope Decision

**Pass.** The commit is limited to the named import-fix slice and its focused
tests. It makes the committed clean runtime self-contained for the reviewed Step
1 import path and does not rely on helper definitions present only in the dirty
original worktree.

## Remaining Risks

- This review verifies the import blocker and focused Step 1 test slice. It is
  not a full rerun of Drill 012 or the next larger production chunk.
- The catalog-year parser is intentionally permissive for production recovery
  use. Future parser edge cases should be addressed with general tests, not
  row-specific exceptions.
- Generated reports must remain evidence rather than authority; ready-to-scale
  claims still require process review after future production runs.

## Required Next Action

Accept commit `c1779aaa0526ee5d6ca1c1c03e2f040f046fc0bc` as the clean-runtime
Step 1 import fix. Project management can update status only after this review
is incorporated; the review stream should not update
`CURRENT_STATUS_AND_NEXT_STEPS.md`.
