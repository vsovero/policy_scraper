# Current Status And Next Steps

Updated: 2026-07-04

This is the current human-facing status register for the policy pipeline. It is intentionally short. Historical pilot, drill, and regression notes live in `artifacts/PILOTS/url_discovery/historical_testing_log/README.md`. Current Step 1 production-construction reporting lives in `artifacts/PIPELINE_OUTPUTS/01_url_discovery/reports/prior_discovery_source_reconstruction_rollup/README.md`.

## Current Step 1 Strategy

The active Step 1 lane is `prior-discovery source reconstruction`: rebuild URL/source evidence for institutions with prior discovery evidence using the clean production runner, reviewed source evidence, package-local release files, and explicit unresolved-row accounting. Existing reviewed artifact IDs still contain `prior_valid_reverification`; treat that as a frozen run identifier, not the preferred process name.

This lane is not a clean no-legacy benchmark. It is also not a journal-ready release because downstream text extraction, policy classification, adjudication, final panel construction, and final replication packaging are later-stage work.

## Latest Reviewed URL-Stage Packet

```text
step1_prior_discovery_source_reconstruction_packet_009_012
production_chunk_step1_prior_valid_reverification_test_batch_009
production_chunk_step1_prior_valid_reverification_test_batch_010
production_chunk_step1_prior_valid_reverification_test_batch_011
production_chunk_step1_prior_valid_reverification_test_batch_012
```

Packet 009-012 is the latest Step 1 URL-stage prior-discovery source reconstruction packet accepted by process review. It adds 112 institutions, 1,664 target institution-years, 701 accepted source-ledger rows, 963 explicit unresolved rows, 440 benchmark rows, 329 current-run benchmark recoveries, 111 benchmark rows invalidated by review, 0 benchmark rows resolved by other source-ledger evidence, and 0 unresolved benchmark misses.

The fetch-bound and Python 3.10 compatibility fixes from the packet review have been integrated on `main` through `5d71061`.

## Current Production-Construction Totals

- Accepted batches: 12 (001-012)
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

Full batch-by-batch reporting is in `artifacts/PIPELINE_OUTPUTS/01_url_discovery/reports/prior_discovery_source_reconstruction_rollup/README.md`.

## Next Action

Run the next managed testing packet, `step1_prior_discovery_source_reconstruction_packet_013_016`, from clean `origin/main` after this packet-status update. The testing packet should run batches 013-016 sequentially, preserve run-local artifacts, avoid project-management docs, and hand off to a packet-level process review.

Project management should update this file only after the packet-level process review reaches acceptance.

## Step 2 Handoff Decision

Do more reviewed Step 1 prior-discovery source reconstruction batches before building the unified URL/source dataset for Step 2. The accepted batch releases currently contain the source-ledger pieces, but the canonical main repo does not yet contain a consolidated Step 2 input table. Build that combined handoff only after more batches receive process-review acceptance, so the aggregation is a deliberate release step rather than a small partial bundle.

## Current Boundaries

- Do not claim clean no-legacy benchmark success from this lane.
- Do not claim journal-release readiness from Step 1 URL-stage artifacts alone.
- Do not use unresolved rows as if they were accepted source evidence.
- Do not count source-ledger-resolved-by-other-evidence rows as current-run benchmark recoveries.
- Do not build the unified Step 2 handoff until more Step 1 batches are accepted.
- Review records for batches 001-012 were produced in their batch worktrees; publishing ignored review artifacts into canonical `process_reviews/` remains a review-stream task, not a project-management task.

## Where Details Live

- Current Step 1 rollup: `artifacts/PIPELINE_OUTPUTS/01_url_discovery/reports/prior_discovery_source_reconstruction_rollup/README.md`
- URL discovery folder map: `artifacts/PIPELINE_OUTPUTS/01_url_discovery/README.md`
- Historical testing log: `artifacts/PILOTS/url_discovery/historical_testing_log/README.md`
- Step 1 run contract and standards: `docs/replication_standards/codex_goals/step_1_url_discovery_run_contract.md`
