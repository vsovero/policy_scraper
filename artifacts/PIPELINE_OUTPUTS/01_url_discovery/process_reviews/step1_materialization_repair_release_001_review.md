# Step 1 Materialization Repair Release 001 Review

Goal ID: `review_step1_materialization_repair_release_001`

Decision: PASS

Commit reviewed: `41115e22bfdc83f02640e0b9317fe11c48f8e13e`

Review date: 2026-07-08

Cleanup re-check date: 2026-07-08

Review question: Did the controlled materialization repair release correctly process only the reviewed stronger-evidence repair universe, without promoting weak historical leads or bypassing current retrieval/source review?

## Summary

The controlled release correctly ran the stronger-evidence repair universe through current candidate materialization, retrieval, source review, chunk packaging, and release-local verification. I found no evidence that imported LLM/programmatic lead-only rows entered the release, no evidence of human-legacy labeling without `validated_human_legacy` provenance, no evidence of unresolved rows treated as accepted current evidence, no Step 2 handoff table, and no journal-readiness claim.

The prior CONDITIONAL PASS item is resolved. The active `artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_inputs/step1_materialization_repair_release_001/historical_materialization_decisions.csv` now has 833 rows, all `materialized_candidate`, with the expected provenance split: 471 `prior_programmatic` and 362 `validated_human_legacy`. The stale all-`not_materialized` file has been moved to attempt history at `artifacts/PIPELINE_OUTPUTS/01_url_discovery/build_reports/step1_materialization_repair_release_001/attempt_history/historical_materialization_decisions_STALE_SUPERSEDED_all_not_materialized.csv`.

PM can accept and status-promote this repair release as a Step 1 URL-stage materialization repair release. This is not a journal-readiness claim and does not build a Step 2 handoff table.

## Cleanup Re-Check

Cleanup review goal ID: `review_step1_materialization_repair_release_001_cleanup`

Verified cleanup facts:

- Active materialization-decision rows: 833.
- Active decision count: 833 `materialized_candidate`.
- Active provenance split: 471 `prior_programmatic`; 362 `validated_human_legacy`.
- The active decision file matches `selected_stronger_evidence_rows.csv` exactly on `unitid`, `academic_year`, `candidate_url`, `provenance_label`, `historical_evidence_class`, and `materialization_decision`.
- The active decision file matches the 833 `materialized_candidate` rows in `step1_historical_materialization_repair/historical_materialization_repair_ledger.csv` exactly on the same fields.
- Row keys and provenance match the current-run candidate ledger and source-review log. There are 128 expected current-run URL string differences where the candidate/review ledgers use Wayback recovery URLs or child policy links for retrieval while the materialization-decision file preserves the originally materialized repair URL.
- The superseded stale file in attempt history still has 833 `not_materialized` rows and blank provenance/evidence fields, which clearly documents the resolved stale artifact.
- `MATERIALIZATION_DECISIONS_STATUS.md` documents that the active file was corrected and the stale file is superseded.
- `CLEANUP_CHECK_STATUS.md` documents the cleanup, but its `final_build_guard` text preserves an earlier protected-doc residue failure. The current review-stream guard result below supersedes that review-record residue for this review decision.

## Files Reviewed

- `artifacts/PIPELINE_OUTPUTS/01_url_discovery/build_reports/step1_materialization_repair_release_001/FINAL_RUN_STATUS.md`
- `artifacts/PIPELINE_OUTPUTS/01_url_discovery/build_reports/step1_materialization_repair_release_001/FINAL_RUN_STATUS.json`
- `artifacts/PIPELINE_OUTPUTS/01_url_discovery/build_reports/step1_materialization_repair_release_001/MATERIALIZATION_DECISIONS_STATUS.md`
- `artifacts/PIPELINE_OUTPUTS/01_url_discovery/build_reports/step1_materialization_repair_release_001/MATERIALIZATION_DECISIONS_STATUS.json`
- `artifacts/PIPELINE_OUTPUTS/01_url_discovery/build_reports/step1_materialization_repair_release_001/CLEANUP_CHECK_STATUS.md`
- `artifacts/PIPELINE_OUTPUTS/01_url_discovery/build_reports/step1_materialization_repair_release_001/CLEANUP_CHECK_STATUS.json`
- `artifacts/PIPELINE_OUTPUTS/01_url_discovery/build_reports/step1_materialization_repair_release_001/attempt_history/historical_materialization_decisions_STALE_SUPERSEDED_all_not_materialized.csv`
- `artifacts/PIPELINE_OUTPUTS/01_url_discovery/build_reports/step1_materialization_repair_release_001/selected_stronger_evidence_rows.csv`
- `artifacts/PIPELINE_OUTPUTS/01_url_discovery/build_reports/step1_materialization_repair_release_001/stronger_evidence_raw_legacy_input.csv`
- `artifacts/PIPELINE_OUTPUTS/01_url_discovery/build_reports/step1_historical_materialization_repair/historical_materialization_repair_ledger.csv`
- `artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_selection/step1_materialization_repair_release_001/selected_target_panel.csv`
- `artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_selection/step1_materialization_repair_release_001/selected_institutions.csv`
- `artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_inputs/step1_materialization_repair_release_001/target_panel.csv`
- `artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_inputs/step1_materialization_repair_release_001/candidate_url_ledger.csv`
- `artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_inputs/step1_materialization_repair_release_001/source_review_log.csv`
- `artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_inputs/step1_materialization_repair_release_001/source_evidence_manifest.csv`
- `artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_inputs/step1_materialization_repair_release_001/benchmark_key.csv`
- `artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_inputs/step1_materialization_repair_release_001/historical_materialization_decisions.csv`
- `artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_chunks/production_chunk_step1_materialization_repair_release_001/OUTPUT_source_ledger_delta.csv`
- `artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_chunks/production_chunk_step1_materialization_repair_release_001/UNRESOLVED_ROWS.csv`
- `artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_chunks/production_chunk_step1_materialization_repair_release_001/BENCHMARK_RECOVERY.csv`
- `artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_chunks/production_chunk_step1_materialization_repair_release_001/BENCHMARK_MISSES.csv`
- `artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_chunks/production_chunk_step1_materialization_repair_release_001/REQUIREMENTS_STATUS.csv`
- `artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_chunks/production_chunk_step1_materialization_repair_release_001/CHUNK_REPORT.md`
- `artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_materialization_repair_release_001/README.md`
- `artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_materialization_repair_release_001/code_state.csv`
- `artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_materialization_repair_release_001/release_status.csv`
- `artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_materialization_repair_release_001/rebuild_check.csv`

## Selection And Universe

Verified:

- Selected target-year rows: 833.
- Unique selected institutions in the target/candidate ledgers: 116.
- Validated human legacy rows: 362.
- Prior-programmatic accepted rows: 471.
- Imported LLM/programmatic lead-only rows excluded: 893 total, consisting of 821 `imported_llm_candidate_lead` rows and 72 `historical_programmatic_lead` rows in the repair ledger.
- No-materializable-URL rows excluded: 10, consisting of 9 blank/unknown rows and 1 `programmatic_attempt_no_valid_discovery` row without a URL.

The release target, candidate, source-review, source-ledger, benchmark, and raw legacy input files contain only `validated_human_legacy` and `prior_programmatic` provenance. I did not find `imported_llm_candidate_lead` or `historical_programmatic_lead` rows in the selected repair-release run.

Note: `selected_institutions.csv` has 172 rows but 116 unique `unitid` values. The authoritative run universe is still 116 institutions because `selected_target_panel.csv`, `target_panel.csv`, and `candidate_url_ledger.csv` each contain 833 target-year rows across 116 unique institutions.

## Hard Gates

Verified:

- No imported LLM/programmatic lead-only rows entered the repair release.
- No output column using `human_legacy` labels was found in the candidate ledger, source review log, source ledger, benchmark recovery file, or release-facing source ledger. The provenance values present are `validated_human_legacy` and `prior_programmatic`.
- All 743 source-ledger rows match a current source-review row by `unitid`, `academic_year`, and reviewed `candidate_url`.
- Source-ledger review decisions are 704 `accept_exact_year_catalog` and 39 `needs_text_validation`; the latter are validated-human rows preserved for text extraction/final validation, not wrong-institution invalidations.
- No Step 2 or journal-named handoff table was present in the chunk or release package.
- The final status and chunk report state that this is URL-stage only and does not claim journal readiness.

## Output And Accounting

Verified output presence:

- Production inputs exist.
- Candidate URL ledger exists: 833 rows.
- Source review log exists: 833 rows.
- Source evidence manifest exists: 833 rows.
- Benchmark key and benchmark recovery files exist.
- Production chunk exists.
- Production release exists.
- Final run status exists.
- Release-local verification passes.

Final accounting:

- Source-ledger rows: 743.
- Unresolved rows: 90.
- Benchmark recovered by current chunk: 694.
- Benchmark invalidated by current review: 90.
- Unresolved benchmark misses: 0.

The apparent difference between 743 source-ledger rows and 694 current-run benchmark recoveries is explained by 49 `source_ledger_resolved_by_other_evidence` rows in `BENCHMARK_RECOVERY.csv`. These rows are source-ledger resolved/invalidated for accounting, but are not counted as direct recovery of the original benchmark URL.

## Invalidation Review

The 90 invalidated benchmark rows break down as follows:

- By provenance: 52 `validated_human_legacy`; 38 `prior_programmatic`.
- By review decision: 55 `reject_dead_or_unretrievable`; 30 `reject_institution_not_confirmed_from_current_evidence`; 3 `reject_confirmed_wrong_institution`; 2 `reject_not_catalog_or_policy_source`.
- Cross-tab:
  - `validated_human_legacy`: 49 `reject_dead_or_unretrievable`; 3 `reject_confirmed_wrong_institution`.
  - `prior_programmatic`: 30 `reject_institution_not_confirmed_from_current_evidence`; 6 `reject_dead_or_unretrievable`; 2 `reject_not_catalog_or_policy_source`.

I did not find validated-human rows invalidated merely because current evidence was thin/truncated. The thin/truncated validated-human cases are the 39 `needs_text_validation` rows in the source ledger, where the review reason explicitly preserves them for text extraction/final validation instead of wrong-institution invalidation.

Prior-programmatic rows were allowed to be invalidated when current retrieval/source review failed or did not confirm the target institution/source.

## Columbus State Regression

For `unitid=139366`:

- The repair proof ledger has 15 `materialized_candidate` rows, all `prior_programmatic_accepted_needs_current_reverification`.
- The candidate URL ledger has 15 rows.
- The source review log has 15 rows.
- The unresolved table has 15 rows.
- The source ledger has 0 rows.
- Benchmark recovery has 15 `row_invalidated_by_current_review` rows and 0 unresolved benchmark misses.

All 15 Columbus State rows were materialized and reviewed; this is no longer a candidate-materialization failure in the authoritative repair proof, candidate ledger, review log, unresolved table, or benchmark accounting. The current-review result is a real rejection under the repair-release rules: all 15 URLs retrieved with HTTP 200, had source type and year coverage confirmed, but `institution_match_confirmed=False`; review decision was `reject_institution_not_confirmed_from_current_evidence`.

The cleanup re-check confirms the active `historical_materialization_decisions.csv` now also reports these 15 Columbus State rows as `materialized_candidate` with `prior_programmatic` provenance. Columbus State is no longer represented as a candidate-materialization failure in the active production inputs.

## Checks Run

- Start guard: `PYTHONPATH=src ../.venv/bin/python -m course_policy.codex_scope_guard init --scope review --baseline /private/tmp/codex_scope_review_step1_materialization_repair_release_001.json` - passed.
- Clean import: `PYTHONPATH=src ../.venv/bin/python -c "import course_policy.step1_proof_to_scale_url_production; import course_policy.step1_historical_materialization_repair; import course_policy.production_release_url_stage; import course_policy.production_quality_gate; print('import ok')"` - passed.
- Focused tests: `PYTHONPATH=src ../.venv/bin/python -m pytest tests/test_step1_proof_to_scale_url_production.py tests/test_step1_production_runner.py tests/test_production_release_url_stage.py tests/test_production_quality_gate.py tests/test_production_streams.py -q` - 67 passed.
- Release-local verifier from release README: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=code/source_snapshot/src python -m course_policy.production_release_url_stage --release-root . --verify-only` - passed; `files_checked=889`, `unmanifested_failures=0`, `local_absolute_path_failures=0`, `status=pass`.
- `git diff --check` - passed.
- Cleanup review start guard: `PYTHONPATH=src ../.venv/bin/python -m course_policy.codex_scope_guard init --scope review --baseline /private/tmp/codex_scope_review_step1_materialization_repair_release_001_cleanup.json` - passed.
- Cleanup release-local verifier from release README: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=code/source_snapshot/src python -m course_policy.production_release_url_stage --release-root . --verify-only` - passed; `files_checked=889`, `unmanifested_failures=0`, `local_absolute_path_failures=0`, `status=pass`.
- Cleanup `git diff --check` - passed.

## Required Next Action

No blocker remains for Step 1 URL-stage repair-release acceptance. PM may accept/status-promote the repair release, with the usual caveat that this is URL-stage evidence only and not journal readiness or downstream Step 2 completion.
