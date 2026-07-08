# Step 1 Forensic Attrition Audit 001-040

Diagnostic audit only. Prior accepted releases are read, not rewritten.

## Inputs

- Accepted batch input directories found: 40/40
- Accepted batch release directories found: 40/40
- Target universe source: `Stata Files/Data/step2_ipeds_universe_with_policy_flags.dta`
- Old public 411 diagnostic source: `Stata Files/Data/step2_baseline_2002_representativeness_sample.dta`
- Historical inventory used: `policy_scraper_worktrees/completed/policy_scraper_step1_historical_lead_source_reconstruction_packet_029_032/artifacts/AUDIT_TRAILS/url_discovery_historical_inventory`

## Target-Universe Disposition

| Sector | Target-universe institutions | Complete institution-years | Old collected-policy institutions | Never-collected institutions |
|---|---:|---:|---:|---:|
| Public | 577 | 7941 | 427 | 150 |
| Private nonprofit | 1233 | 15918 | 243 | 990 |
| Total | 1810 | 23853 | 670 | 1140 |

- Target-universe count check: matched expected 1,810 / 23,853 denominator
- Sector institution-year subtotals are membership counts. The total complete institution-year count is the de-duplicated unitid-year denominator.

## Old Collected-Policy vs Never-Collected

- Old collected-policy sector-institution memberships: 670
- Never-collected sector-institution memberships: 1140
- Old collected-policy memberships with accepted source rows: 513
- Never-collected memberships with accepted source rows: 963

## Attrition Class Counts

| class | rows |
|---|---:|
| accepted_source_row | 16345 |
| candidate_materialization_failure | 3293 |
| true_no_upstream_url_evidence | 2423 |
| candidate_retrieval_failure | 1598 |
| provenance_taxonomy_conflict | 125 |
| source_review_rejected_wrong_scope_or_year | 35 |
| source_review_rejected_wrong_institution | 27 |
| source_review_rejected_insufficient_evidence | 7 |

## Secondary Attrition Flags

| class | rows |
|---|---:|
| dropped_historical_url_evidence | 3293 |

## Old Public 411 Diagnostic Subset

- Old public diagnostic institutions: 411
- Inside target universe: 391
- Outside target universe: 20
- Accepted source in target universe: 304
- Selected but unresolved in target universe: 87
- Not selected in target universe: 0
- Old public floor reference: 411; diagnostic only, not the primary Step 1 denominator.

## Valid-Human-Legacy Disposition

- Institutions with valid-human/raw legacy evidence: 529
- Valid-human rows with candidate materialization failure: 362

## Historical/Programmatic/LLM Lead Disposition

- Historical-lead-only institutions: 800
- Historical-lead-only rows not selected yet: 0

## Unresolved Cases With Upstream Evidence

- Candidate materialization failures: 3293
- Dropped historical URL evidence flags: 3293
- Provenance/taxonomy conflicts: 125
- Needs text validation: 0

## Columbus State Regression

- Selected batches: 005
- Year rows: 15
- Attrition classes: `{"candidate_materialization_failure": 15}`
- Secondary flags: `{"dropped_historical_url_evidence": 15}`
- Institution class: `candidate_materialization_failure`
- Required finding: Columbus State is a candidate-materialization/dropped-historical-URL process failure, not a true no-evidence failure.

## Hard-Gate Recommendations

- A selected institution with eligible historical URL evidence cannot have an empty candidate ledger unless an explicit exclusion reason is recorded.
- True human legacy, prior programmatic accepted, imported LLM candidate lead, failed historical attempt, and unreviewed candidate lead must remain separate provenance classes.
- `no_candidate_found` cannot be interpreted as true source failure when upstream eligible URL evidence exists.
- Step 2 handoff must exclude or flag unresolved/provenance-conflicted rows.
- Columbus State (`unitid=139366`) must remain a regression test.

## Output Files

- `institution_attrition_ledger.csv`
- `institution_year_attrition_ledger.csv`
- `attrition_summary.json`
