# Step 1 Prior-Discovery Source Reconstruction Rollup

Updated: 2026-07-08

This is the current production-construction reporting table for Step 1 URL/source discovery. It covers reviewed prior-discovery source reconstruction batches only. It does not include old pilot/drill metrics, and it does not claim clean no-legacy benchmark success or journal-release readiness.

## Current Totals

- Accepted batches: 40
- Institutions covered: 1,048
- Institution-years targeted: 14,269
- Accepted source-ledger rows ready for Step 2 text extraction: 5,513
- Explicit unresolved rows: 8,756
- Overall ready/source-ledger rate: 38.6%
- Benchmark rows: 2,898
- Current-run benchmark recovered: 2,526
- Benchmark rows invalidated by review: 371
- Benchmark rows source-ledger-resolved by other evidence: 1
- Unresolved benchmark misses: 0

## Primary Step 1 Target Universe

Use the 2002-2016 complete-outcome/control panel as the Step 1 target universe. An institution is in this universe if it is public or private nonprofit four-year and has at least two complete institution-years in 2002-2016. A complete year has nonmissing controls and at least one nonmissing graduation outcome among `grad4per`, `grad5per`, and `grad6per`. Required controls are in-state tuition, out-of-state tuition, faculty, revenue, costs, Black share, Hispanic share, White share, and any-aid share.

| Sector | Target-universe institutions | Complete institution-years | Old collected-policy institutions | Never-collected institutions |
|---|---:|---:|---:|---:|
| Public | 577 | 7,941 | 427 | 150 |
| Private nonprofit | 1,233 | 15,918 | 243 | 990 |
| Total | 1,810 | 23,853 | 670 | 1,140 |

This is the main denominator for Step 1 recovery and expansion planning. The older `411` public count is a baseline-2002 representativeness subset, not the full Step 1 target universe. Of those 411 public baseline institutions, 391 are inside the target universe and 20 are outside it; the target universe also contains 186 public institutions outside the old 411.

## Human-Legacy URL Recovery Diagnostic

This table separates the human-legacy recovery question from the broader Step 1 construction totals. It uses accepted batches 001-028 and accepted batch selection metadata. Historical/programmatic/LLM-lead packets 029-040 are excluded because their benchmark denominator is `0`. Treat this as a diagnostic inside the target-universe audit, not as the main denominator.

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

Interpretation: the reviewed public benchmark rows have `0` unresolved misses and raw row recovery above 90%, but the accepted artifacts do not yet establish recovery of the target universe. Within the old 411 public baseline subset, only 187 institutions currently have an accepted Step 1 source row in accepted packets: 185 through the valid-human-legacy lane and 2 through the historical/programmatic lead lane. Another 86 were targeted but remain unresolved, and 138 old-baseline institutions have not yet been selected in accepted Step 1 packets.

## Packet Rollup

| Packet | Batches | Institutions | Target rows | Accepted source rows | Unresolved rows | Ready rate | Benchmark rows | Recovered | Invalidated | Other evidence | Unresolved misses | Files checked |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Prior reviewed batches | 4 | 112 | 1,671 | 1,118 | 553 | 66.9% | 675 | 634 | 41 | 0 | 0 | 3,513 |
| Packet 005-008 | 4 | 112 | 1,612 | 710 | 902 | 44.0% | 492 | 433 | 58 | 1 | 0 | 4,694 |
| Packet 009-012 | 4 | 112 | 1,664 | 701 | 963 | 42.1% | 440 | 329 | 111 | 0 | 0 | 6,526 |
| Packet 013-016 | 4 | 112 | 1,603 | 697 | 906 | 43.5% | 518 | 453 | 65 | 0 | 0 | 4,769 |
| Packet 017-020 | 4 | 112 | 1,531 | 800 | 731 | 52.3% | 525 | 451 | 74 | 0 | 0 | 7,873 |
| Packet 021-024 | 4 | 100 | 1,303 | 526 | 777 | 40.4% | 161 | 145 | 16 | 0 | 0 | 5,081 |
| Packet 025-028 | 4 | 82 | 1,206 | 457 | 749 | 37.9% | 87 | 81 | 6 | 0 | 0 | 2,339 |
| Packet 029-032 | 4 | 97 | 1,228 | 299 | 929 | 24.3% | 0 | 0 | 0 | 0 | 0 | 920 |
| Packet 033-036 | 4 | 103 | 1,231 | 66 | 1,165 | 5.4% | 0 | 0 | 0 | 0 | 0 | 2,720 |
| Packet 037-040 | 4 | 106 | 1,220 | 139 | 1,081 | 11.4% | 0 | 0 | 0 | 0 | 0 | 1,230 |
| TOTAL | 40 | 1,048 | 14,269 | 5,513 | 8,756 | 38.6% | 2,898 | 2,526 | 371 | 1 | 0 | 39,665 |

## Batch Rollup

| Batch | Packet | Institutions | Target rows | Accepted source rows | Unresolved rows | Ready rate | Private ready | Public ready | Benchmark rows | Recovered | Invalidated | Other evidence | Unresolved misses | Files checked | Review status |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 001 | 001-004 | 28 | 411 | 284 | 127 | 69.1% | 68.2% | 71.4% | 161 | 150 | 11 | 0 | 0 | 995 | accepted |
| 002 | 001-004 | 28 | 420 | 313 | 107 | 74.5% | 77.0% | 68.3% | 198 | 183 | 15 | 0 | 0 | 881 | accepted |
| 003 | 001-004 | 28 | 420 | 297 | 123 | 70.7% | 75.7% | 58.3% | 138 | 136 | 2 | 0 | 0 | 819 | accepted |
| 004 | 001-004 | 28 | 420 | 224 | 196 | 53.3% | 64.7% | 25.0% | 178 | 165 | 13 | 0 | 0 | 818 | accepted |
| 005 | 005-008 | 28 | 405 | 231 | 174 | 57.0% | 63.5% | 38.7% | 197 | 172 | 25 | 0 | 0 | 930 | accepted |
| 006 | 005-008 | 28 | 388 | 162 | 226 | 41.8% | 46.8% | 28.7% | 127 | 98 | 28 | 1 | 0 | 1,185 | accepted |
| 007 | 005-008 | 28 | 402 | 145 | 257 | 36.1% | 36.7% | 34.3% | 84 | 79 | 5 | 0 | 0 | 1,569 | accepted |
| 008 | 005-008 | 28 | 417 | 172 | 245 | 41.2% | 41.3% | 41.2% | 84 | 84 | 0 | 0 | 0 | 1,010 | accepted |
| 009 | 009-012 | 28 | 412 | 183 | 229 | 44.4% | 37.3% | 63.4% | 98 | 78 | 20 | 0 | 0 | 1,325 | accepted |
| 010 | 009-012 | 28 | 419 | 201 | 218 | 48.0% | 42.5% | 61.7% | 150 | 104 | 46 | 0 | 0 | 1,540 | accepted |
| 011 | 009-012 | 28 | 419 | 182 | 237 | 43.4% | 48.3% | 31.1% | 121 | 96 | 25 | 0 | 0 | 1,808 | accepted |
| 012 | 009-012 | 28 | 414 | 135 | 279 | 32.6% | 28.1% | 43.7% | 71 | 51 | 20 | 0 | 0 | 1,853 | accepted |
| 013 | 013-016 | 28 | 401 | 114 | 287 | 28.4% | 33.8% | 13.9% | 44 | 39 | 5 | 0 | 0 | 1,562 | accepted |
| 014 | 013-016 | 28 | 390 | 73 | 317 | 18.7% | 12.5% | 36.6% | 13 | 13 | 0 | 0 | 0 | 586 | accepted |
| 015 | 013-016 | 28 | 399 | 258 | 141 | 64.7% | 74.6% | 41.7% | 243 | 205 | 38 | 0 | 0 | 1,131 | accepted |
| 016 | 013-016 | 28 | 413 | 252 | 161 | 61.0% | 61.4% | 60.0% | 218 | 196 | 22 | 0 | 0 | 1,490 | accepted |
| 017 | 017-020 | 28 | 403 | 248 | 155 | 61.5% | 68.2% | 44.7% | 194 | 175 | 19 | 0 | 0 | 1,622 | accepted |
| 018 | 017-020 | 28 | 402 | 231 | 171 | 57.5% | 52.8% | 68.6% | 153 | 127 | 26 | 0 | 0 | 2,153 | accepted |
| 019 | 017-020 | 28 | 346 | 176 | 170 | 50.9% | 36.9% | 82.9% | 105 | 85 | 20 | 0 | 0 | 1,895 | accepted |
| 020 | 017-020 | 28 | 380 | 145 | 235 | 38.2% | 34.8% | 47.1% | 73 | 64 | 9 | 0 | 0 | 2,203 | accepted |
| 021 | 021-024 | 28 | 343 | 121 | 222 | 35.3% | 34.1% | 37.5% | 44 | 41 | 3 | 0 | 0 | 1,536 | accepted |
| 022 | 021-024 | 27 | 337 | 53 | 284 | 15.7% | 8.3% | 29.2% | 21 | 17 | 4 | 0 | 0 | 1,542 | accepted |
| 023 | 021-024 | 23 | 312 | 146 | 166 | 46.8% |  | 46.8% | 39 | 33 | 6 | 0 | 0 | 1,120 | accepted |
| 024 | 021-024 | 22 | 311 | 206 | 105 | 66.2% |  | 66.2% | 57 | 54 | 3 | 0 | 0 | 883 | accepted |
| 025 | 025-028 | 21 | 302 | 141 | 161 | 46.7% |  | 46.7% | 42 | 40 | 2 | 0 | 0 | 980 | accepted |
| 026 | 025-028 | 21 | 304 | 142 | 162 | 46.7% |  | 46.7% | 40 | 36 | 4 | 0 | 0 | 967 | accepted |
| 027 | 025-028 | 20 | 300 | 76 | 224 | 25.3% |  | 25.3% | 5 | 5 | 0 | 0 | 0 | 216 | accepted |
| 028 | 025-028 | 20 | 300 | 98 | 202 | 32.7% |  | 32.7% | 0 | 0 | 0 | 0 | 0 | 176 | accepted |
| 029 | 029-032 | 28 | 313 | 85 | 228 | 27.2% | 23.1% | 29.3% | 0 | 0 | 0 | 0 | 0 | 207 | accepted |
| 030 | 029-032 | 25 | 303 | 77 | 226 | 25.4% | 2.8% | 37.9% | 0 | 0 | 0 | 0 | 0 | 239 | accepted |
| 031 | 029-032 | 21 | 305 | 78 | 227 | 25.6% | 5.3% | 40.8% | 0 | 0 | 0 | 0 | 0 | 187 | accepted |
| 032 | 029-032 | 23 | 307 | 59 | 248 | 19.2% | 14.0% | 21.7% | 0 | 0 | 0 | 0 | 0 | 287 | accepted |
| 033 | 033-036 | 29 | 307 | 0 | 307 | 0.0% | 0.0% | 0.0% | 0 | 0 | 0 | 0 | 0 | 708 | accepted |
| 034 | 033-036 | 24 | 307 | 0 | 307 | 0.0% | 0.0% | 0.0% | 0 | 0 | 0 | 0 | 0 | 715 | accepted |
| 035 | 033-036 | 26 | 313 | 29 | 284 | 9.3% | 6.1% | 10.7% | 0 | 0 | 0 | 0 | 0 | 863 | accepted |
| 036 | 033-036 | 24 | 304 | 37 | 267 | 12.2% | 0.0% | 19.1% | 0 | 0 | 0 | 0 | 0 | 434 | accepted |
| 037 | 037-040 | 25 | 305 | 81 | 224 | 26.6% | 12.9% | 34.9% | 0 | 0 | 0 | 0 | 0 | 433 | accepted |
| 038 | 037-040 | 28 | 310 | 15 | 295 | 4.8% | 0.0% | 7.5% | 0 | 0 | 0 | 0 | 0 | 439 | accepted |
| 039 | 037-040 | 25 | 300 | 40 | 260 | 13.3% | 2.5% | 20.8% | 0 | 0 | 0 | 0 | 0 | 195 | accepted |
| 040 | 037-040 | 28 | 305 | 3 | 302 | 1.0% | 0.0% | 2.2% | 0 | 0 | 0 | 0 | 0 | 163 | accepted |
| TOTAL | 001-040 | 1,048 | 14,269 | 5,513 | 8,756 | 38.6% |  |  | 2,898 | 2,526 | 371 | 1 | 0 | 39,665 | accepted batches only |

## Interpretation

These batches are source reconstruction over institutions with prior discovery evidence. They are useful for building the Step 1 URL/source ledger and for checking prior benchmark accounting. They are not a clean out-of-sample discovery benchmark.

The accepted source-ledger rows are the rows that can eventually feed Step 2 text retrieval/extraction. The unresolved rows remain visible in the Step 1 output and should not be silently filled. A source-ledger-resolved-by-other-evidence benchmark row is not counted as current-run benchmark recovered.

## Reviewed Attrition Audit

The Step 1 attrition audit over the primary target universe and accepted batches 001-040 has passed process review after the URL-evidence fix. The unresolved rows in this rollup are now separated into accepted source rows, candidate materialization failures, true no-upstream-evidence rows, retrieval/review failures, and provenance conflicts.

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

The secondary `dropped_historical_url_evidence` count is 1,736. Process review notes that this means historical URL-field/evidence values, not necessarily strict fetchable `http(s)` URLs; 26 of those rows contain legacy filename/title-style values. Columbus State University (`unitid=139366`) is the required regression example from the original audit: raw public legacy and historical inventory contained catalog URL evidence, but batch 005 had no `benchmark_key.csv` or `candidate_url_ledger.csv` rows for the institution and therefore marked its 15 target rows `no_candidate_found`.

Required hard-gate implication: a selected institution with eligible historical URL-field/evidence values cannot silently end with an empty candidate ledger and `no_candidate_found`; it must either materialize that evidence as a current candidate with correct provenance or record a specific exclusion reason.

## Reviewed Materialization Repair Proof and Release

The Step 1 historical materialization repair proof has passed process review and is preserved in the main repo. It examined all 1,736 candidate-materialization-failure institution-years from the reviewed attrition audit.

| Repair proof class | Institution-years |
|---|---:|
| True human legacy materialized | 362 |
| Prior programmatic accepted materialized | 471 |
| Imported LLM/programmatic lead only | 893 |
| No materializable URL after stricter rules | 10 |
| Total examined | 1,736 |

The proof supports a controlled repair path, not automatic promotion. The 833 true-human/prior-programmatic target-year rows have stronger historical URL evidence that can be materialized with explicit provenance and then rerun through current retrieval/review/release gates. The 893 imported LLM/programmatic lead-only rows remain historical-lead candidates and must not be relabeled as human legacy or prior accepted evidence.

Planning caveat: the materialized candidate ledger has 1,726 target-year materializations, not 1,726 unique URL strings, because some multi-year catalog candidates repeat across affected target years.

The controlled materialization repair release has passed process review and is accepted as Step 1 URL-stage repair evidence. It selected the 833 stronger-evidence target-year rows across 116 institutions, excluded the 893 imported LLM/programmatic lead-only rows and 10 no-materializable rows, and reran current retrieval/source review/release gates.

| Repair release result | Institution-years |
|---|---:|
| Source-ledger rows | 743 |
| Unresolved rows | 90 |
| Current-run benchmark recovered | 694 |
| Invalidated by current review | 90 |
| Unresolved benchmark misses | 0 |

The active materialization-decision file was cleaned before final review: all 833 rows are `materialized_candidate`, split between 471 `prior_programmatic` and 362 `validated_human_legacy`; the stale all-`not_materialized` file is superseded in attempt history. Columbus State University (`unitid=139366`) is no longer a candidate-materialization failure: 15 rows were materialized and reviewed, then all 15 were invalidated because current retrieval did not confirm the institution match.

## Step 2 Handoff Status

No unified Step 2 URL/source handoff table has been built yet. The reviewed batch releases and accepted repair release hold the current source-ledger pieces. Build the consolidated Step 2 handoff only after PM decides how to treat the remaining unresolved classes after the reviewed materialization repair release.

## Release Locations

- Batch 001: `policy_scraper_worktrees/completed/policy_scraper_step1_prior_valid_reverification_001/artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_prior_valid_reverification_test_batch_001/`
- Batch 002: `policy_scraper_worktrees/completed/policy_scraper_step1_prior_valid_reverification_002/artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_prior_valid_reverification_test_batch_002/`
- Batch 003: `policy_scraper_worktrees/completed/policy_scraper_step1_prior_valid_reverification_003/artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_prior_valid_reverification_test_batch_003/`
- Batch 004: `policy_scraper_worktrees/completed/policy_scraper_step1_prior_valid_reverification_004/artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_prior_valid_reverification_test_batch_004/`
- Batch 005: `policy_scraper_worktrees/completed/policy_scraper_step1_prior_discovery_source_reconstruction_packet_005_008/artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_prior_valid_reverification_test_batch_005/`
- Batch 006: `policy_scraper_worktrees/completed/policy_scraper_step1_prior_discovery_source_reconstruction_packet_005_008/artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_prior_valid_reverification_test_batch_006/`
- Batch 007: `policy_scraper_worktrees/completed/policy_scraper_step1_prior_discovery_source_reconstruction_packet_005_008/artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_prior_valid_reverification_test_batch_007/`
- Batch 008: `policy_scraper_worktrees/completed/policy_scraper_step1_prior_discovery_source_reconstruction_packet_005_008/artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_prior_valid_reverification_test_batch_008/`
- Batch 009: `policy_scraper_worktrees/completed/policy_scraper_step1_prior_discovery_source_reconstruction_packet_009_012/artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_prior_valid_reverification_test_batch_009/`
- Batch 010: `policy_scraper_worktrees/completed/policy_scraper_step1_prior_discovery_source_reconstruction_packet_009_012/artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_prior_valid_reverification_test_batch_010/`
- Batch 011: `policy_scraper_worktrees/completed/policy_scraper_step1_prior_discovery_source_reconstruction_packet_009_012/artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_prior_valid_reverification_test_batch_011/`
- Batch 012: `policy_scraper_worktrees/completed/policy_scraper_step1_prior_discovery_source_reconstruction_packet_009_012/artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_prior_valid_reverification_test_batch_012/`
- Batch 013: `policy_scraper_worktrees/completed/policy_scraper_step1_prior_discovery_source_reconstruction_packet_013_016/artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_prior_valid_reverification_test_batch_013/`
- Batch 014: `policy_scraper_worktrees/completed/policy_scraper_step1_prior_discovery_source_reconstruction_packet_013_016/artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_prior_valid_reverification_test_batch_014/`
- Batch 015: `policy_scraper_worktrees/completed/policy_scraper_step1_prior_discovery_source_reconstruction_packet_013_016/artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_prior_valid_reverification_test_batch_015/`
- Batch 016: `policy_scraper_worktrees/completed/policy_scraper_step1_prior_discovery_source_reconstruction_packet_013_016/artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_prior_valid_reverification_test_batch_016/`
- Batch 017: `policy_scraper_worktrees/completed/policy_scraper_step1_prior_discovery_source_reconstruction_packet_017_020/artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_prior_valid_reverification_test_batch_017/`
- Batch 018: `policy_scraper_worktrees/completed/policy_scraper_step1_prior_discovery_source_reconstruction_packet_017_020/artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_prior_valid_reverification_test_batch_018/`
- Batch 019: `policy_scraper_worktrees/completed/policy_scraper_step1_prior_discovery_source_reconstruction_packet_017_020/artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_prior_valid_reverification_test_batch_019/`
- Batch 020: `policy_scraper_worktrees/completed/policy_scraper_step1_prior_discovery_source_reconstruction_packet_017_020/artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_prior_valid_reverification_test_batch_020/`
- Batch 021: `policy_scraper_worktrees/completed/policy_scraper_step1_prior_discovery_source_reconstruction_packet_021_024/artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_prior_valid_reverification_test_batch_021/`
- Batch 022: `policy_scraper_worktrees/completed/policy_scraper_step1_prior_discovery_source_reconstruction_packet_021_024/artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_prior_valid_reverification_test_batch_022/`
- Batch 023: `policy_scraper_worktrees/completed/policy_scraper_step1_prior_discovery_source_reconstruction_packet_021_024/artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_prior_valid_reverification_test_batch_023/`
- Batch 024: `policy_scraper_worktrees/completed/policy_scraper_step1_prior_discovery_source_reconstruction_packet_021_024/artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_prior_valid_reverification_test_batch_024/`
- Batch 025: `policy_scraper_worktrees/completed/policy_scraper_step1_prior_discovery_source_reconstruction_packet_025_028/artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_prior_valid_reverification_test_batch_025/`
- Batch 026: `policy_scraper_worktrees/completed/policy_scraper_step1_prior_discovery_source_reconstruction_packet_025_028/artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_prior_valid_reverification_test_batch_026/`
- Batch 027: `policy_scraper_worktrees/completed/policy_scraper_step1_prior_discovery_source_reconstruction_packet_025_028/artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_prior_valid_reverification_test_batch_027/`
- Batch 028: `policy_scraper_worktrees/completed/policy_scraper_step1_prior_discovery_source_reconstruction_packet_025_028/artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_prior_valid_reverification_test_batch_028/`
- Batch 029: `policy_scraper_worktrees/completed/policy_scraper_step1_historical_lead_source_reconstruction_packet_029_032/artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_historical_lead_source_reconstruction_test_batch_029/`
- Batch 030: `policy_scraper_worktrees/completed/policy_scraper_step1_historical_lead_source_reconstruction_packet_029_032/artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_historical_lead_source_reconstruction_test_batch_030/`
- Batch 031: `policy_scraper_worktrees/completed/policy_scraper_step1_historical_lead_source_reconstruction_packet_029_032/artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_historical_lead_source_reconstruction_test_batch_031/`
- Batch 032: `policy_scraper_worktrees/completed/policy_scraper_step1_historical_lead_source_reconstruction_packet_029_032/artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_historical_lead_source_reconstruction_test_batch_032/`
- Batch 033: `policy_scraper_worktrees/completed/policy_scraper_step1_historical_lead_source_reconstruction_packet_033_036/artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_historical_lead_source_reconstruction_test_batch_033/`
- Batch 034: `policy_scraper_worktrees/completed/policy_scraper_step1_historical_lead_source_reconstruction_packet_033_036/artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_historical_lead_source_reconstruction_test_batch_034/`
- Batch 035: `policy_scraper_worktrees/completed/policy_scraper_step1_historical_lead_source_reconstruction_packet_033_036/artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_historical_lead_source_reconstruction_test_batch_035/`
- Batch 036: `policy_scraper_worktrees/completed/policy_scraper_step1_historical_lead_source_reconstruction_packet_033_036/artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_historical_lead_source_reconstruction_test_batch_036/`
- Batch 037: `policy_scraper_worktrees/completed/policy_scraper_step1_historical_lead_source_reconstruction_packet_037_040/artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_historical_lead_source_reconstruction_test_batch_037/`
- Batch 038: `policy_scraper_worktrees/completed/policy_scraper_step1_historical_lead_source_reconstruction_packet_037_040/artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_historical_lead_source_reconstruction_test_batch_038/`
- Batch 039: `policy_scraper_worktrees/completed/policy_scraper_step1_historical_lead_source_reconstruction_packet_037_040/artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_historical_lead_source_reconstruction_test_batch_039/`
- Batch 040: `policy_scraper_worktrees/completed/policy_scraper_step1_historical_lead_source_reconstruction_packet_037_040/artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_historical_lead_source_reconstruction_test_batch_040/`
