# Current Status And Next Steps

Updated: 2026-07-08

This is the current human-facing status register for the policy pipeline. It is intentionally short. Historical pilot, drill, and regression notes live in `artifacts/PILOTS/url_discovery/historical_testing_log/README.md`. Current Step 1 production-construction reporting lives in `artifacts/PIPELINE_OUTPUTS/01_url_discovery/reports/prior_discovery_source_reconstruction_rollup/README.md`.

## Current Step 1 Strategy

The active Step 1 lane is `prior-discovery source reconstruction`: rebuild URL/source evidence for institutions with prior discovery evidence using the clean production runner, reviewed source evidence, package-local release files, and explicit unresolved-row accounting. Existing reviewed artifact IDs still contain `prior_valid_reverification`; treat that as a frozen run identifier, not the preferred process name.

This lane is not a clean no-legacy benchmark. It is also not a journal-ready release because downstream text extraction, policy classification, adjudication, final panel construction, and final replication packaging are later-stage work.

## Taxonomy Correction Status

Project-management finding: the old selector allowed some private automated/LLM workbook-tab URLs to enter the legacy reconstruction lane through `legacy_covered_years > 0`. That was incorrect. Automated/LLM tabs are historical lead/search-hint material, not human legacy evidence, and they must not satisfy `prior_valid_legacy_reverification`.

The source/test fix has passed review and is merged in main as `31428db`. The fixed path separates true legacy reconstruction from `historical_lead_source_reconstruction`. The historical-lead benchmark guard fix has passed review and is merged in main as `a298899`. The empty-source-ledger and AI provenance release-packaging fixes have passed review and are merged in main as `e9fea9f`. Already reviewed source evidence is not automatically invalidated, but any accepted row that entered through the automated/LLM-as-legacy path needs provenance relabeling or audit before it is used as legacy reconstruction evidence or final Step 2/journal-stage input.

## Latest Reviewed URL-Stage Packet

```text
step1_historical_lead_source_reconstruction_packet_037_040
production_chunk_step1_historical_lead_source_reconstruction_test_batch_037
production_chunk_step1_historical_lead_source_reconstruction_test_batch_038
production_chunk_step1_historical_lead_source_reconstruction_test_batch_039
production_chunk_step1_historical_lead_source_reconstruction_test_batch_040
```

Packet 037-040 is the latest Step 1 URL-stage historical-lead source reconstruction packet accepted by process review. It adds 106 institutions, 1,220 target institution-years, 139 accepted source-ledger rows, 18 institutions with accepted source-ledger rows, 1,081 explicit unresolved rows, 0 benchmark denominator rows, and 0 unresolved benchmark misses.

Packet 037-040 uses `historical_lead_source_reconstruction`: imported LLM/programmatic leads are search hints only, not human legacy evidence or legacy benchmark rows. Process review confirmed `legacy_covered_years=0`, benchmark denominator `0`, no validated-human legacy in the source ledger, no unresolved rows treated as accepted evidence, AI/API provenance packaged for all four releases, and release-local verification passing for all four releases.

## Primary Step 1 Target Universe

Use the 2002-2016 complete-outcome/control panel as the Step 1 target universe. An institution is in this universe if it is public or private nonprofit four-year and has at least two complete institution-years in 2002-2016. A complete year has nonmissing controls and at least one nonmissing graduation outcome among `grad4per`, `grad5per`, and `grad6per`. Required controls are in-state tuition, out-of-state tuition, faculty, revenue, costs, Black share, Hispanic share, White share, and any-aid share.

| Sector | Target-universe institutions | Complete institution-years | Old collected-policy institutions | Never-collected institutions |
|---|---:|---:|---:|---:|
| Public | 577 | 7,941 | 427 | 150 |
| Private nonprofit | 1,233 | 15,918 | 243 | 990 |
| Total | 1,810 | 23,853 | 670 | 1,140 |

This table is now the main denominator for Step 1 recovery and expansion planning. The older `411` public count is a baseline-2002 representativeness subset, not the full Step 1 target universe. Of those 411 public baseline institutions, 391 are inside the target universe and 20 are outside it; the target universe also contains 186 public institutions outside the old 411.

## Current Production-Construction Totals

- Accepted batches: 40 (001-040)
- Institutions covered/targeted in accepted packets: 1,048
- Institutions with at least one accepted source-ledger row: 617
- Institutions covered but not yet accepted into the source ledger: 431
- Institution-years targeted: 14,269
- Accepted source-ledger rows ready for Step 2 text extraction: 5,513
- Explicit unresolved rows: 8,756
- Overall ready/source-ledger rate: 38.6%
- Benchmark rows: 2,898
- Current-run benchmark recovered: 2,526
- Benchmark rows invalidated by review: 371
- Benchmark rows source-ledger-resolved by other evidence: 1
- Unresolved benchmark misses: 0

Accepted-batch sector split:

| Sector | Targeted institutions | Institutions with accepted source row | Targeted without accepted source row | Target institution-years | Accepted source-ledger rows | Ready/source-ledger rate |
|---|---:|---:|---:|---:|---:|---:|
| Public | 486 | 256 | 230 | 6,645 | 2,419 | 36.4% |
| Private nonprofit | 562 | 361 | 201 | 7,624 | 3,094 | 40.6% |
| Total | 1,048 | 617 | 431 | 14,269 | 5,513 | 38.6% |

Important counting note: the sector split above is a packet-sum construction status table. It is useful for batch throughput, but the primary denominator is the target-universe table above. The old public `411` remains useful only as a baseline-2002 representativeness diagnostic.

## Human-Legacy URL Recovery Diagnostic

The human-legacy benchmark did not disappear, but it is a diagnostic inside the broader target-universe audit. Packets 029-040 are historical/programmatic/LLM-lead reconstruction packets with benchmark denominator `0`, so they do not test recovery of human legacy URLs. The table below uses accepted batches 001-028 and classifies institutions by the accepted batch selection metadata. It excludes historical/programmatic/LLM lead packets.

| Sector | Valid-human-legacy institutions targeted | Institutions with accepted source row | Target institution-years | Accepted source rows | Benchmark institutions | Benchmark rows | Current-run recovered | Invalidated by review | Other evidence | Unresolved benchmark misses | Raw benchmark recovery | Closure after invalidation/review |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Public | 301 | 212 | 4,313 | 1,988 | 170 | 417 | 380 | 37 | 0 | 0 | 91.1% | 100.0% |
| Private nonprofit | 254 | 188 | 3,748 | 1,737 | 176 | 1,326 | 1,136 | 189 | 1 | 0 | 85.7% | 100.0% |
| Total | 555 | 400 | 8,061 | 3,725 | 346 | 1,743 | 1,516 | 226 | 1 | 0 | 87.0% | 100.0% |

Old public `411` diagnostic: the `301` public valid-human-legacy targeted institutions above are not a pure subset of the old 411 public baseline table. They include 268 institutions from the old 411 and 33 public institutions outside that baseline-2002 representativeness set. The old 411 therefore has to be reconciled directly, but it should not be treated as the Step 1 target universe:

| Old 411 public-floor disposition | Institutions |
|---|---:|
| Valid-human-legacy lane, accepted source row | 185 |
| Valid-human-legacy lane, targeted but no accepted source row | 83 |
| Historical/programmatic lead lane, accepted source row | 2 |
| Historical/programmatic lead lane, targeted but no accepted source row | 3 |
| Not yet selected in accepted Step 1 packets | 138 |
| Total old public baseline subset | 411 |

Interpretation: the reviewed public benchmark rows themselves have `0` unresolved misses and raw row recovery above 90%, but that does not establish recovery of the target universe. Within the old 411 public baseline subset, only 187 institutions currently have an accepted Step 1 source row in accepted packets: 185 through the valid-human-legacy lane and 2 through the historical/programmatic lead lane. Another 86 were targeted but remain unresolved, and 138 old-baseline institutions have not yet been selected in accepted Step 1 packets.

The older generated artifacts still require a provenance relabel/audit before journal-stage use because some pre-taxonomy outputs have blank row-level `legacy_input_provenance`; the table above uses the batch selection metadata to classify the accepted artifacts for management reporting.

## Reviewed Attrition Audit Findings

The Step 1 attrition audit over the primary target universe and accepted batches 001-040 has passed process review after the URL-evidence fix. The audit distinguishes rows that are accepted, rows where historical URL-field/evidence values failed to materialize into current candidates, rows with no upstream URL evidence, retrieval/review failures, and provenance conflicts.

| Attrition class | Institution-years |
|---|---:|
| Accepted source row | 16,345 |
| Candidate materialization failure | 1,736 |
| Candidate retrieval failure | 822 |
| Provenance taxonomy conflict | 125 |
| Source review rejected wrong scope/year | 23 |
| Source review rejected wrong institution | 20 |
| Source review rejected insufficient evidence | 6 |
| True no upstream URL evidence | 4,776 |
| Total target institution-years | 23,853 |

The secondary `dropped_historical_url_evidence` count is 1,736. Process review notes that this means historical URL-field/evidence values, not necessarily strict fetchable `http(s)` URLs; 26 of those rows contain legacy filename/title-style values. Columbus State University (`unitid=139366`) remains the required regression example: its 15 target rows are candidate materialization failures with historical URL evidence upstream and zero current candidate, benchmark, or source-ledger rows.

Planning interpretation: candidate materialization failure is a real Step 1 process flaw and must be fixed before Step 2 handoff. Failed historical attempts with no URL are no longer counted as dropped URL evidence; they are now part of the true no-upstream-evidence path unless another URL-bearing source exists.

## Reviewed Materialization Repair Proof

The Step 1 historical materialization repair proof has passed process review and is now preserved in the main repo. It examined the 1,736 candidate-materialization-failure institution-years from the reviewed attrition audit.

| Repair proof class | Institution-years |
|---|---:|
| True human legacy materialized | 362 |
| Prior programmatic accepted materialized | 471 |
| Imported LLM/programmatic lead only | 893 |
| No materializable URL after stricter rules | 10 |
| Total examined | 1,736 |

Planning interpretation: 833 target-year rows have stronger historical URL evidence that can be fed into a controlled materialization repair release with explicit provenance. The 893 imported LLM/programmatic lead-only rows remain a separate historical-lead lane; they should not be relabeled as human legacy or prior accepted evidence. The materialized candidate ledger has 1,726 target-year materializations, not 1,726 unique URL strings, because some multi-year catalog candidates repeat across affected target years.

Columbus State University (`unitid=139366`) is the required regression example: the proof materializes 15 candidate rows with `prior_programmatic` provenance, not human legacy provenance.

Full batch-by-batch reporting is in `artifacts/PIPELINE_OUTPUTS/01_url_discovery/reports/prior_discovery_source_reconstruction_rollup/README.md`.

## Next Action

Packet 037-040 has passed process review. The Step 1 attrition audit 001-040 and the historical materialization repair proof have also passed process review.

Recommended next move: build and review a controlled materialization repair release for the 833 stronger-evidence target-year rows, then decide separately how to queue the 893 imported LLM/programmatic lead-only rows. Do not resume ordinary historical-lead packet expansion or build the Step 2 handoff until PM decides how materialization failures, provenance conflicts, and retrieval/review failures will be corrected or explicitly carried forward.

## Step 2 Handoff Decision

Do not build the unified URL/source dataset for Step 2 until the reviewed attrition audit's candidate-materialization and provenance corrections are resolved through a reviewed repair release or explicitly carried forward. The accepted batch releases currently contain useful source-ledger pieces, but the canonical main repo does not yet contain a consolidated Step 2 input table.

## Current Boundaries

- Do not claim clean no-legacy benchmark success from this lane.
- Do not claim journal-release readiness from Step 1 URL-stage artifacts alone.
- Do not treat automated/LLM workbook tabs as human legacy evidence or legacy coverage.
- Do not let imported LLM/programmatic leads satisfy `prior_valid_legacy_reverification`; they belong in a separate historical-lead reconstruction lane.
- Do not use unresolved rows as if they were accepted source evidence.
- Do not treat `no_candidate_found` as true source failure when eligible historical URL-field/evidence values exist upstream and were not materialized into the current candidate ledger.
- Do not count source-ledger-resolved-by-other-evidence rows as current-run benchmark recoveries.
- Do not build the unified Step 2 handoff until the reviewed attrition audit's materialization/provenance corrections are resolved.
- Review records for batches 001-040 were produced in their batch worktrees; publishing ignored review artifacts into canonical `process_reviews/` remains a review-stream task, not a project-management task.

## Where Details Live

- Current Step 1 rollup: `artifacts/PIPELINE_OUTPUTS/01_url_discovery/reports/prior_discovery_source_reconstruction_rollup/README.md`
- URL discovery folder map: `artifacts/PIPELINE_OUTPUTS/01_url_discovery/README.md`
- Historical testing log: `artifacts/PILOTS/url_discovery/historical_testing_log/README.md`
- Step 1 run contract and standards: `docs/replication_standards/codex_goals/step_1_url_discovery_run_contract.md`
