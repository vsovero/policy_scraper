# Step 1 Prior-Discovery Source Reconstruction Rollup

Updated: 2026-07-04

This is the current production-construction reporting table for Step 1 URL/source discovery. It covers reviewed prior-discovery source reconstruction batches only. It does not include old pilot/drill metrics, and it does not claim clean no-legacy benchmark success or journal-release readiness.

## Current Totals

- Accepted batches: 12
- Institutions covered: 336
- Institution-years targeted: 4,947
- Accepted source-ledger rows ready for Step 2 text extraction: 2,529
- Explicit unresolved rows: 2,418
- Overall ready/source-ledger rate: 51.1%
- Benchmark rows: 1,607
- Current-run benchmark recovered: 1,396
- Benchmark rows invalidated by review: 210
- Benchmark rows source-ledger-resolved by other evidence: 1
- Unresolved benchmark misses: 0

## Packet Rollup

| Packet | Batches | Institutions | Target rows | Accepted source rows | Unresolved rows | Ready rate | Benchmark rows | Recovered | Invalidated | Other evidence | Unresolved misses | Files checked |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Prior reviewed batches | 4 | 112 | 1,671 | 1,118 | 553 | 66.9% | 675 | 634 | 41 | 0 | 0 | 3,513 |
| Packet 005-008 | 4 | 112 | 1,612 | 710 | 902 | 44.0% | 492 | 433 | 58 | 1 | 0 | 4,694 |
| Packet 009-012 | 4 | 112 | 1,664 | 701 | 963 | 42.1% | 440 | 329 | 111 | 0 | 0 | 6,526 |
| TOTAL | 12 | 336 | 4,947 | 2,529 | 2,418 | 51.1% | 1,607 | 1,396 | 210 | 1 | 0 | 14,733 |

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
| TOTAL | 001-012 | 336 | 4,947 | 2,529 | 2,418 | 51.1% |  |  | 1,607 | 1,396 | 210 | 1 | 0 | 14,733 | accepted batches only |

## Interpretation

These batches are source reconstruction over institutions with prior discovery evidence. They are useful for building the Step 1 URL/source ledger and for checking prior benchmark accounting. They are not a clean out-of-sample discovery benchmark.

The accepted source-ledger rows are the rows that can eventually feed Step 2 text retrieval/extraction. The unresolved rows remain visible in the Step 1 output and should not be silently filled. A source-ledger-resolved-by-other-evidence benchmark row is not counted as current-run benchmark recovered.

## Step 2 Handoff Status

No unified Step 2 URL/source handoff table has been built yet. The reviewed batch releases hold the current source-ledger pieces. Build the consolidated Step 2 handoff only after more Step 1 batches receive process-review acceptance.

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
