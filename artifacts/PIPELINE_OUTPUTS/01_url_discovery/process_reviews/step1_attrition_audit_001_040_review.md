# Step 1 Attrition Audit 001-040 Review

Decision: FAIL

Reviewed commit: `c49b81efbd384d9d9a7ba317fff150ed73ea80b5`

Review worktree:
`/Users/verosovero/Dropbox/Course repetition IPEDS/policy_scraper_step1_attrition_audit_review`

## Scope Reviewed

Audit outputs:

- `artifacts/PIPELINE_OUTPUTS/01_url_discovery/reports/step1_attrition_audit_001_040/STEP1_ATTRITION_AUDIT_REPORT.md`
- `artifacts/PIPELINE_OUTPUTS/01_url_discovery/reports/step1_attrition_audit_001_040/attrition_summary.json`
- `artifacts/PIPELINE_OUTPUTS/01_url_discovery/reports/step1_attrition_audit_001_040/institution_attrition_ledger.csv`
- `artifacts/PIPELINE_OUTPUTS/01_url_discovery/reports/step1_attrition_audit_001_040/institution_year_attrition_ledger.csv`

Source/test files inspected:

- `src/course_policy/step1_attrition_audit.py`
- `tests/test_step1_attrition_audit.py`
- `src/course_policy/codex_scope_guard.py`

The scope-guard exception for integration is narrow: it permits only the Step 1 attrition audit source/test slice and the audit report CSV/JSON/Markdown outputs. Review scope remains limited to process reviews and the protected-doc manifest row for the review artifact.

## Findings

### Blocker: dropped-historical-URL evidence is overbroad

The report's headline `candidate_materialization_failure` and secondary `dropped_historical_url_evidence` count is not fully supported as valid upstream historical URL evidence.

The ledger reports:

- `candidate_materialization_failure`: 3,293 rows
- secondary `dropped_historical_url_evidence`: 3,293 rows

However, tracing those 3,293 rows back to the normalized historical inventory found:

- 1,736 rows with an actual historical URL value in `url`, `candidate_url`, or `final_url`
- 1,557 rows without any historical URL value
- all 1,557 no-URL rows have only `programmatic_attempt_no_valid_discovery`
- 0 duplicate unitid-year rows in the dropped-evidence set
- 0 dropped rows lacking a historical inventory row

This points to a definition problem, not duplicate inflation or a missing join. In `src/course_policy/step1_attrition_audit.py`, `has_historical_attempt_evidence` is built from all `historical_attempt_*` count fields, which includes `historical_attempt_failed_attempt_rows`. That then feeds `has_historical_url_evidence` and `has_upstream_url_evidence`, so failed historical attempts with no URL are classified as `candidate_materialization_failure` with secondary `dropped_historical_url_evidence`.

The affected logic is:

- `has_historical_attempt_evidence = out.filter(like="historical_attempt_").sum(axis=1).gt(0)`
- `has_historical_url_evidence = has_historical_attempt_evidence | has_historical_discovery_evidence`
- selected rows with upstream evidence but no current candidates/benchmark become `candidate_materialization_failure` and, if historical, `dropped_historical_url_evidence`

Because failed historical attempts are supposed to remain distinct from valid human legacy, prior programmatic accepted evidence, imported LLM leads, and unreviewed historical leads, the current classification collapses one taxonomy lane into URL-evidence materialization failure.

### Test gap

`tests/test_step1_attrition_audit.py` covers Columbus-style URL-bearing upstream evidence and true no-upstream evidence, but it does not include a case where the only historical evidence is `programmatic_attempt_no_valid_discovery` with no URL. That gap allows the overbroad URL-evidence definition to pass.

## Verified Items

The Step 1 target universe matches the required denominator:

- Public: 577 institutions, 7,941 complete institution-years, 427 old collected, 150 never collected
- Private nonprofit: 1,233 institutions, 15,918 complete institution-years, 243 old collected, 990 never collected
- Total: 1,810 sector-institution memberships, 23,853 de-duplicated complete institution-years, 670 old collected, 1,140 never collected

The report and ledgers mechanically contain the stated primary attrition counts:

- `accepted_source_row`: 16,345
- `candidate_materialization_failure`: 3,293
- `true_no_upstream_url_evidence`: 2,423
- `candidate_retrieval_failure`: 1,598
- `provenance_taxonomy_conflict`: 125

Columbus State University, `unitid=139366`, is correctly classified:

- 15 target rows
- all 15 rows are `candidate_materialization_failure`
- all 15 rows carry secondary `dropped_historical_url_evidence`
- 0 rows are `true_no_upstream_url_evidence`
- trace confirms prior-programmatic accepted historical discovery rows and imported LLM lead rows exist for 2002-2005, with zero current candidate rows, zero benchmark rows, and zero source-ledger rows

The ledger preserves separate count fields for:

- valid human legacy
- prior programmatic accepted
- imported LLM candidate lead
- failed historical attempt
- unreviewed prior/human candidate leads

But the final attrition classification does not preserve the failed-attempt distinction when assigning `has_historical_url_evidence`.

## PM Readiness Assessment

The audit is useful as a diagnostic draft, but the current outputs should not be used as the final PM planning denominator for the historical URL materialization fix. PM can see that Columbus is a real materialization failure and that Step 2 handoff should remain on hold for unresolved/provenance-conflicted rows, but PM cannot safely interpret all 3,293 dropped-historical-evidence rows as URL-bearing upstream evidence.

Required next fix:

1. Split URL-bearing historical evidence from failed historical attempts with no URL value.
2. Recompute `has_historical_url_evidence` and `has_upstream_url_evidence` so `programmatic_attempt_no_valid_discovery` alone does not create URL-evidence status.
3. Re-run the attrition audit outputs.
4. Add a regression test for a selected row whose only historical record is `programmatic_attempt_no_valid_discovery` with no URL.
5. Keep Columbus State as a regression test for true URL-bearing materialization failure.

## Checks Run

- `PYTHONPATH=src ../.venv/bin/python -c "import course_policy.step1_attrition_audit; print('import ok')"`: pass
- `PYTHONPATH=src ../.venv/bin/python -m pytest tests/test_step1_attrition_audit.py -q`: pass, `8 passed`, 1 known Stata Unicode warning
- `git diff --check`: pass before review-file edits
- Columbus trace from normalized historical inventory to final attrition class: reviewed
- Dropped-historical-evidence sample and full-count validation: reviewed
