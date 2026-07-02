# Step 1 Target Panel Materialization Fix Review

Reviewed on 2026-07-02 by the Step 1 review stream.

## Decision

**PASS.**

Commit `7eeff6508e08149c7049fb9bc288ff5c6b6f8d56` correctly fixes the clean
Step 1 production path so discovery receives `institution_year_targets.csv`
from explicit Step 1 production inputs before discovery runs. The fix is
general, traceable to the provided `target_panel`, and does not rely on hidden
dirty-worktree state or row-specific hardcoding.

## Commit Reviewed

- `7eeff6508e08149c7049fb9bc288ff5c6b6f8d56`
- Commit title: `Materialize Step 1 discovery year targets`
- Review worktree:
  `/Users/verosovero/Dropbox/Course repetition IPEDS/policy_scraper_step1_target_panel_fix`

## Files Reviewed

Changed by the commit:

- `src/course_policy/batch2_year_candidates.py`
- `src/course_policy/public_fresh_discovery.py`
- `src/course_policy/step1_proof_to_scale_url_production.py`
- `tests/test_public_fresh_discovery.py`
- `tests/test_step1_proof_to_scale_url_production.py`

No current-status files, standards documents, generated outputs, source files
outside the reviewed target-panel/helper slice, or unrelated tests are changed
by the reviewed commit.

## Diff Assessment

The commit closes the clean-runtime dependency on an already-existing
`artifacts/policy_data_internal/interim/institution_year_targets.csv` file.

`step1_proof_to_scale_url_production.py` now defines:

- `INSTITUTION_YEAR_TARGETS_RUNTIME_INPUT`, pointing to
  `artifacts/policy_data_internal/interim/institution_year_targets.csv`.
- `runtime_year_targets_from_target_panel(target_panel)`, which requires
  `unitid`, `institution_name`, and `academic_year`, then derives the runtime
  year-target rows from the explicit Step 1 target panel. It carries through
  optional `state`, `homepage_url` as `webaddr`, and `sector`, coerces `unitid`
  and `year`, drops invalid numeric keys, de-duplicates, and sorts the result.
- `write_runtime_year_targets(repo_root, target_panel)`, which writes that
  derived compatibility file.
- `write_discovery_inputs(repo_root, target_panel, sectors)`, which now calls
  `write_runtime_year_targets()` before stream discovery inputs are written.

This satisfies the requirement that
`artifacts/policy_data_internal/interim/institution_year_targets.csv` is
materialized deterministically from the explicit Step 1 `target_panel` before
discovery runs.

`public_fresh_discovery.py` now defines:

- `normalize_institution_year_targets(target_panel)`, which normalizes
  `year`, `target_year`, or `academic_year` to the runtime `year` field and
  enforces required `unitid`, `institution_name`, and `year` columns.
- `build_year_panel(..., target_panel=None)`, which uses the explicit
  `target_panel` argument when supplied and falls back to the compatibility file
  only when no explicit panel is provided.

This means Step 1 callers can pass the target panel directly and are not forced
to rely on the compatibility CSV file.

The `batch2_year_candidates.py` changes are general helper behavior:

- `is_archive_pagination_link(record)` separates archive-pagination links from
  root archive links.
- Candidate selection now includes `candidate_span_width` so narrower catalog
  spans are preferred deterministically when other priority fields are equal.

## Generality Check

The fix is general:

- No hard-coded institutions were added.
- No hard-coded URLs were added.
- No hard-coded batch rows were added.
- No dirty-worktree paths or uncommitted helper dependencies are required.
- The runtime target file is derived only from the explicit Step 1
  `target_panel` passed into the production/proof path.

## Required Checks

Clean import:

```text
PYTHONPATH=src ../.venv/bin/python -c "import course_policy.step1_proof_to_scale_url_production; print('import ok')"
```

Result: **passed** with `import ok`.

Focused tests:

```text
PYTHONPATH=src ../.venv/bin/python -m pytest tests/test_step1_production_runner.py tests/test_step1_production_input_builder.py tests/test_step1_proof_to_scale_url_production.py tests/test_public_fresh_discovery.py tests/test_public_fresh_discovery_pipeline.py tests/test_production_release_url_stage.py tests/test_production_quality_gate.py tests/test_production_streams.py
```

Result: **49 passed, 1 warning**.

The warning is the existing pandas string-dtype deprecation warning in
`public_fresh_discovery_pipeline.py`; it does not affect this target-panel
materialization decision.

Touched-helper test:

```text
PYTHONPATH=src ../.venv/bin/python -m pytest tests/test_batch2_year_candidates.py
```

Result: **7 passed**.

## Scope Decision

**Pass.** The commit is limited to the named target-panel materialization and
helper-ranking slice. The tests added or changed directly exercise explicit
target-panel materialization, explicit `build_year_panel(target_panel=...)`
behavior, and the touched helper behavior.

## Remaining Risks

- This review verifies the clean target-panel materialization blocker and the
  focused Step 1 tests. It is not a full rerun of Drill 012 or the next larger
  production chunk.
- The compatibility file remains available as a fallback for older callers, so
  future production entry points should prefer the explicit `target_panel`
  argument or call `write_discovery_inputs()` before discovery.
- Generated reports remain evidence, not authority. The next production run
  still requires process review before any ready-to-scale or journal-grade
  claim.

## Required Next Action

Accept commit `7eeff6508e08149c7049fb9bc288ff5c6b6f8d56` as the Step 1
target-panel materialization fix. Project management can update status only
after this review is incorporated; the review stream should not update
`CURRENT_STATUS_AND_NEXT_STEPS.md`.
