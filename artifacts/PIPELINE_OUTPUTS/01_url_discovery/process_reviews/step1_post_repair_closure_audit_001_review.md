# Step 1 Post-Repair Closure Audit 001 Review

Goal ID: `review_step1_post_repair_closure_audit_001`

Decision: PASS

Commit reviewed: `1d92fb2cc112d0d34d2c38cbfb4336391b1bb286`

Review date: 2026-07-08

Review question: Does the post-repair closure audit correctly combine accepted batches 001-040 plus the accepted materialization repair release, without double counting accepted evidence or misclassifying unresolved rows?

## Summary

The audit correctly combines accepted Step 1 batches 001-040 with the accepted materialization repair release. I found no double counting between previously accepted rows and repair source-ledger rows, no unresolved rows counted as accepted evidence, no remaining candidate-materialization failures after the repair release, and no imported LLM/programmatic lead-only rows relabeled as human legacy.

The report is appropriate for PM Step 1 closure and handoff-strategy accounting. It is not a journal-readiness package: it is an accounting report that reads reviewed prior outputs and the accepted repair release, and it explicitly does not run live discovery, retrieval, source review, new production batches, or Step 2 handoff construction.

Residual portability note: the summary records repair-release inputs under `policy_scraper_worktrees/completed/policy_scraper_step1_materialization_repair_release_001/...`. This is acceptable for PM accounting in the current project workspace, but a later journal package should include or point to a durable package-local archive of those inputs if the audit is expected to be independently regenerated outside this workspace.

## Files Reviewed

- `src/course_policy/step1_post_repair_closure_audit.py`
- `tests/test_step1_post_repair_closure_audit.py`
- `src/course_policy/codex_scope_guard.py`
- `tests/test_codex_testing_write_scope.py`
- `artifacts/PIPELINE_OUTPUTS/01_url_discovery/reports/step1_post_repair_closure_audit_001/STEP1_POST_REPAIR_CLOSURE_AUDIT_REPORT.md`
- `artifacts/PIPELINE_OUTPUTS/01_url_discovery/reports/step1_post_repair_closure_audit_001/post_repair_summary.json`
- `artifacts/PIPELINE_OUTPUTS/01_url_discovery/reports/step1_post_repair_closure_audit_001/institution_closure_ledger.csv`
- `artifacts/PIPELINE_OUTPUTS/01_url_discovery/reports/step1_post_repair_closure_audit_001/institution_year_closure_ledger.csv`

## Target Universe

Verified denominator:

- Public: 577 institutions; 7,941 complete institution-years; 427 old collected; 150 never collected.
- Private nonprofit: 1,233 institutions; 15,918 complete institution-years; 243 old collected; 990 never collected.
- Total: 1,810 sector institution memberships; 23,853 complete institution-years; 670 old collected; 1,140 never collected.

The target definition remains inherited from the reviewed attrition audit: years 2002-2016, public/private nonprofit four-year institutions, complete controls, at least one nonmissing graduation outcome among `grad4per`, `grad5per`, `grad6per`, and at least two complete institution-years for sector membership. The report's target-universe expected-count check is `True`.

## Accepted After Repair

Verified accounting:

- Accepted before repair: 16,345 institution-years; 1,475 institutions.
- Repair source-ledger rows: 743 institution-years; 109 institutions.
- Combined accepted/source-ledger after repair: 17,088 institution-years; 1,561 institutions.
- Repair source rows overlapping accepted-before rows: 0.
- Newly accepted by repair: 743 institution-years; 109 institutions.
- Accepted/unresolved overlap: 0 rows.
- Source-ledger rows with `accepted_after_repair=False`: 0 rows.

Public/private split:

- Public: 4,868 accepted rows.
- Private: 12,220 accepted rows.

Accepted provenance split:

- `validated_human_legacy`: 2,215.
- `prior_programmatic`: 1,148.
- `historical_lead`: 4,563.
- `unknown_or_current_only`: 9,162.

Repair benchmark labels are separated:

- Direct current-run recoveries: 694.
- Source-ledger-resolved-by-other-evidence rows: 49.
- Repair invalidations: 90.

## Remaining Unresolved

Verified remaining unresolved after repair:

- `true_no_upstream_url_evidence`: 4,776.
- `historical_lead_only`: 893.
- `candidate_retrieval_failure`: 877.
- `provenance_taxonomy_conflict`: 125.
- `source_review_rejected_wrong_institution`: 53.
- `source_review_rejected_wrong_scope_or_year`: 25.
- `no_materializable_row`: 10.
- `source_review_rejected_insufficient_evidence`: 6.
- `candidate_materialization_failure`: 0.

Total remaining unresolved: 6,765 institution-years across 705 institutions.

## Public 411 Floor

Verified institution-level accounting:

- Baseline old public 411 institutions: 411.
- Inside current target universe: 391.
- Accepted before repair: 304.
- Newly accepted through repair: 53.
- Accepted after repair: 357.
- Still unresolved inside target universe: 34.
- Not-yet-selected unresolved: 0.
- Outside current target universe: 20.

Interpretation: the human/public floor is mostly reconstructed after the repair release, but it is not fully closed. PM should treat 357 of 391 in-target old-public institutions as accepted after repair, with 34 in-target old-public institutions still unresolved and no in-target old-public institutions left merely unselected.

## Columbus State

Verified `unitid=139366`:

- 15 target rows.
- 15 repair target/materialized/reviewed rows.
- 0 repair source-ledger accepted rows.
- 15 repair unresolved rows.
- 15 benchmark invalidated rows.
- Final closure class: `source_review_rejected_wrong_institution`.
- No longer candidate-materialization failure: `True`.

The row-level reason remains current review failure: `reject_institution_not_confirmed_from_current_evidence`; the audit correctly leaves these rows unresolved rather than accepted.

## Guardrails

Verified:

- No unresolved row is counted as accepted evidence.
- No repair source-ledger row overlaps with accepted-before rows.
- Imported LLM/programmatic lead-only rows are not relabeled as human legacy; lead-only accepted rows remain `historical_lead` or otherwise non-human-legacy.
- The audit source is accounting-only and contains no live network/discovery/retrieval/source-review runner.
- The report explicitly says no Step 2 handoff table is constructed and no journal-readiness claim is made.
- The scope-guard change adds the closure audit source/output paths to integration scope. It is narrow to this audit output directory, although it also allows the guard file/test update needed to record the exception.

## Checks Run

- Start guard: `PYTHONPATH=src ../.venv/bin/python -m course_policy.codex_scope_guard init --scope review --baseline /private/tmp/codex_scope_review_step1_post_repair_closure_audit_001.json` - passed.
- Clean import: `PYTHONPATH=src ../.venv/bin/python -c "import course_policy.step1_post_repair_closure_audit; print('import ok')"` - passed.
- Focused tests: `PYTHONPATH=src ../.venv/bin/python -m pytest tests/test_step1_post_repair_closure_audit.py tests/test_step1_attrition_audit.py tests/test_codex_testing_write_scope.py -q` - 16 passed, 1 skipped, 1 known Stata encoding warning.
- `git diff --check` - passed.
- CSV/JSON consistency checks: target rows, institution rows, combined accepted rows, remaining unresolved rows, Columbus rows, and repair-source rows match between ledgers and `post_repair_summary.json`.

## Recommendation

PM can use this audit to decide Step 1 closure and handoff strategy. The audit supports the conclusion that the materialization repair release eliminated candidate-materialization failures and raised accepted/source-ledger coverage to 17,088 of 23,853 complete institution-years, while leaving 6,765 unresolved institution-years for explicit closure decisions. It also shows the public 411 floor is mostly reconstructed but still has 34 unresolved in-target institutions.
