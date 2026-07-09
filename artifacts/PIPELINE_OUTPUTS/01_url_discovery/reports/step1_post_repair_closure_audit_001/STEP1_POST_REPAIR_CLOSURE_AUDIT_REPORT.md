# Step 1 Post-Repair Closure Audit 001

Accounting-only audit. It reads accepted Step 1 batches 001-040, the accepted materialization repair release, and the reviewed target-universe denominator. It does not run live discovery, retrieval, source review, production batches, or Step 2 handoff construction.

## Inputs

- Attrition audit input: `artifacts/PIPELINE_OUTPUTS/01_url_discovery/reports/step1_attrition_audit_001_040`
- Repair release input: `policy_scraper_worktrees/completed/policy_scraper_step1_materialization_repair_release_001/artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_materialization_repair_release_001`
- Repair proof input: `policy_scraper_worktrees/completed/policy_scraper_step1_materialization_repair_release_001/artifacts/PIPELINE_OUTPUTS/01_url_discovery/build_reports/step1_historical_materialization_repair`

## Target Universe

| Sector | Institutions | Complete institution-years | Old collected-policy institutions | Never-collected institutions |
|---|---:|---:|---:|---:|
| Public | 577 | 7941 | 427 | 150 |
| Private nonprofit | 1233 | 15918 | 243 | 990 |
| Total | 1810 | 23853 | 670 | 1140 |

- Target-universe count check: matched reviewed denominator

## Accepted Evidence After Repair

- Accepted/source-ledger institution-years before repair: 16345
- Accepted/source-ledger institutions before repair: 1475
- Repair source-ledger institution-years: 743
- Repair source-ledger institutions: 109
- Repair direct current-run benchmark recoveries: 694
- Repair source-ledger-resolved-by-other-evidence rows, not direct benchmark recoveries: 49
- Combined accepted/source-ledger institution-years: 17088
- Combined accepted/source-ledger institutions: 1561

### Accepted Sector Split

| class | rows |
|---|---:|
| private | 12220 |
| public | 4868 |

### Accepted Provenance Split

| class | rows |
|---|---:|
| unknown_or_current_only | 9162 |
| historical_lead | 4563 |
| validated_human_legacy | 2215 |
| prior_programmatic | 1148 |

## Remaining Unresolved After Repair

- Remaining unresolved institution-years: 6765
- Remaining unresolved institutions: 705
- Remaining candidate-materialization failures: 0

| class | rows |
|---|---:|
| true_no_upstream_url_evidence | 4776 |
| historical_lead_only | 893 |
| candidate_retrieval_failure | 877 |
| provenance_taxonomy_conflict | 125 |
| source_review_rejected_wrong_institution | 53 |
| source_review_rejected_wrong_scope_or_year | 25 |
| no_materializable_row | 10 |
| source_review_rejected_insufficient_evidence | 6 |

## Public Old 411 Floor

- Baseline old public 411 institutions: 411
- Inside current target universe: 391
- Accepted before repair: 304
- Newly accepted through repair: 53
- Accepted after repair: 357
- Still unresolved after repair: 34
- Not-yet-selected unresolved institutions: 0
- Outside current target universe: 20
- Status: the repair materially closes the public floor by adding 53 old-public institutions, but the floor is still short by 34 inside-target institutions.

## Columbus State Regression

- Unitid: 139366
- Target rows: 15
- Materialized/reviewed repair rows: 15
- Source-ledger rows accepted through repair: 0
- Current-review invalidated/unresolved rows: 15
- Current final closure class: `source_review_rejected_wrong_institution`
- No longer candidate-materialization failure: True

## Guardrails

- Unresolved rows are not counted as accepted evidence.
- Source-ledger-resolved-by-other-evidence rows are labeled separately from direct benchmark recoveries.
- Imported LLM/programmatic historical leads remain historical-lead provenance, not human legacy.
- No Step 2 handoff table is constructed.
- This report does not claim journal readiness.
