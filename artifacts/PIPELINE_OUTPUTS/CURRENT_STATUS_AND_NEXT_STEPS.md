# Current Status And Next Steps

Updated: 2026-07-03

This is the current human-facing status register for the policy pipeline. It is intentionally short. Historical pilot, drill, and regression notes were moved to `artifacts/PILOTS/url_discovery/historical_testing_log/README.md`. Current Step 1 production-construction reporting lives in `artifacts/PIPELINE_OUTPUTS/01_url_discovery/reports/prior_discovery_source_reconstruction_rollup/README.md`.

## Current Step 1 Strategy

The active Step 1 lane is `prior-discovery source reconstruction`: rebuild URL/source evidence for institutions with prior discovery evidence using the clean production runner, reviewed source evidence, package-local release files, and explicit unresolved-row accounting. Existing reviewed artifact IDs still contain `prior_valid_reverification`; treat that as a frozen run identifier, not the preferred process name.

This lane is not a clean no-legacy benchmark. It is also not a journal-ready release because downstream text extraction, policy classification, adjudication, final panel construction, and final replication packaging are later-stage work.

## Latest Reviewed URL-Stage Artifact

```text
production_chunk_step1_prior_valid_reverification_test_batch_004
production_release_step1_prior_valid_reverification_test_batch_004
```

Batch 004 is the latest Step 1 URL-stage prior-discovery source reconstruction batch accepted by process review. It has 28 institutions, 420 target institution-years, 224 accepted source-ledger rows, 196 explicit unresolved rows, 178 benchmark rows, 165 current-run benchmark recoveries, 13 benchmark rows invalidated by review, and 0 unresolved benchmark misses.

## Current Production-Construction Totals

- Accepted batches: 4 (001-004)
- Institutions covered: 112
- Institution-years targeted: 1,671
- Accepted source-ledger rows ready for Step 2 text extraction: 1,118
- Explicit unresolved rows: 553
- Overall ready/source-ledger rate: 66.9%
- Benchmark rows: 675
- Current-run benchmark recovered: 634
- Benchmark rows invalidated by review: 41
- Unresolved benchmark misses: 0

Full batch-by-batch reporting is in `artifacts/PIPELINE_OUTPUTS/01_url_discovery/reports/prior_discovery_source_reconstruction_rollup/README.md`.

## Next Action

Run the next managed testing packet, `step1_prior_discovery_source_reconstruction_packet_005_008`, from clean `origin/main` after this reporting-cleanup update. The testing packet should run batches 005-008 sequentially, preserve run-local artifacts, avoid project-management docs, and hand off to a packet-level process review.

Project management should update this file only after the packet-level process review reaches acceptance.

## Step 2 Handoff Decision

Do more reviewed Step 1 prior-discovery source reconstruction batches before building the unified URL/source dataset for Step 2. The accepted batch releases currently contain the source-ledger pieces, but the canonical main repo does not yet contain a consolidated Step 2 input table. Build that combined handoff only after more batches receive process-review acceptance, so the aggregation is a deliberate release step rather than a small partial bundle.

## Current Boundaries

- Do not claim clean no-legacy benchmark success from this lane.
- Do not claim journal-release readiness from Step 1 URL-stage artifacts alone.
- Do not use unresolved rows as if they were accepted source evidence.
- Do not build the unified Step 2 handoff until more Step 1 batches are accepted.
- Review records for batches 001-004 were produced in their batch worktrees; publishing ignored review artifacts into canonical `process_reviews/` remains a review-stream task, not a project-management task.

## Where Details Live

- Current Step 1 rollup: `artifacts/PIPELINE_OUTPUTS/01_url_discovery/reports/prior_discovery_source_reconstruction_rollup/README.md`
- URL discovery folder map: `artifacts/PIPELINE_OUTPUTS/01_url_discovery/README.md`
- Historical testing log: `artifacts/PILOTS/url_discovery/historical_testing_log/README.md`
- Step 1 run contract and standards: `docs/replication_standards/codex_goals/step_1_url_discovery_run_contract.md`
