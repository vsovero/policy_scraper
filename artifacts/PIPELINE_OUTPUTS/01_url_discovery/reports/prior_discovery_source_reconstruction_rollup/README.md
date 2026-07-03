# Step 1 Prior-Discovery Source Reconstruction Rollup

Updated: 2026-07-03

This is the current production-construction reporting table for Step 1 URL/source discovery. It covers reviewed prior-discovery source reconstruction batches only. It does not include old pilot/drill metrics, and it does not claim clean no-legacy benchmark success or journal-release readiness.

## Current Totals

- Accepted batches: 4
- Institutions covered: 112
- Institution-years targeted: 1,671
- Accepted source-ledger rows ready for Step 2 text extraction: 1,118
- Explicit unresolved rows: 553
- Overall ready/source-ledger rate: 66.9%
- Benchmark rows: 675
- Current-run benchmark recovered: 634
- Benchmark rows invalidated by review: 41
- Unresolved benchmark misses: 0

## Batch Rollup

| Batch | Institutions | Target rows | Accepted source rows | Unresolved rows | Ready rate | Private ready | Public ready | Benchmark rows | Recovered | Invalidated | Unresolved misses | Files checked | Review status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 001 | 28 | 411 | 284 | 127 | 69.1% | 68.2% | 71.4% | 161 | 150 | 11 | 0 | 995 | accepted |
| 002 | 28 | 420 | 313 | 107 | 74.5% | 77.0% | 68.3% | 198 | 183 | 15 | 0 | 881 | accepted |
| 003 | 28 | 420 | 297 | 123 | 70.7% | 75.7% | 58.3% | 138 | 136 | 2 | 0 | 819 | accepted |
| 004 | 28 | 420 | 224 | 196 | 53.3% | 64.7% | 25.0% | 178 | 165 | 13 | 0 | 818 | accepted |
| TOTAL | 112 | 1,671 | 1,118 | 553 | 66.9% |  |  | 675 | 634 | 41 | 0 |  | accepted batches only |

## Interpretation

These batches are source reconstruction over institutions with prior discovery evidence. They are useful for building the Step 1 URL/source ledger and for checking prior benchmark accounting. They are not a clean out-of-sample discovery benchmark.

The accepted source-ledger rows are the rows that can eventually feed Step 2 text retrieval/extraction. The unresolved rows remain visible in the Step 1 output and should not be silently filled.

## Step 2 Handoff Status

No unified Step 2 URL/source handoff table has been built yet. The reviewed batch releases hold the current source-ledger pieces. Build the consolidated Step 2 handoff only after more Step 1 batches receive process-review acceptance.

## Release Locations

- Batch 001: `policy_scraper_worktrees/completed/policy_scraper_step1_prior_valid_reverification_001/artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_prior_valid_reverification_test_batch_001/`
- Batch 002: `policy_scraper_worktrees/completed/policy_scraper_step1_prior_valid_reverification_002/artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_prior_valid_reverification_test_batch_002/`
- Batch 003: `policy_scraper_worktrees/completed/policy_scraper_step1_prior_valid_reverification_003/artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_prior_valid_reverification_test_batch_003/`
- Batch 004: `policy_scraper_worktrees/completed/policy_scraper_step1_prior_valid_reverification_004/artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_step1_prior_valid_reverification_test_batch_004/`
