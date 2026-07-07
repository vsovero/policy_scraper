# Current Status And Next Steps

Updated: 2026-07-07

This is the current human-facing status register for the policy pipeline. It is intentionally short. Historical pilot, drill, and regression notes live in `artifacts/PILOTS/url_discovery/historical_testing_log/README.md`. Current Step 1 production-construction reporting lives in `artifacts/PIPELINE_OUTPUTS/01_url_discovery/reports/prior_discovery_source_reconstruction_rollup/README.md`.

## Current Step 1 Strategy

The active Step 1 lane is `prior-discovery source reconstruction`: rebuild URL/source evidence for institutions with prior discovery evidence using the clean production runner, reviewed source evidence, package-local release files, and explicit unresolved-row accounting. Existing reviewed artifact IDs still contain `prior_valid_reverification`; treat that as a frozen run identifier, not the preferred process name.

This lane is not a clean no-legacy benchmark. It is also not a journal-ready release because downstream text extraction, policy classification, adjudication, final panel construction, and final replication packaging are later-stage work.

## Taxonomy Correction Status

Project-management finding: the old selector allowed some private automated/LLM workbook-tab URLs to enter the legacy reconstruction lane through `legacy_covered_years > 0`. That was incorrect. Automated/LLM tabs are historical lead/search-hint material, not human legacy evidence, and they must not satisfy `prior_valid_legacy_reverification`.

The source/test fix has passed review and is merged in main as `31428db`. The fixed path separates true legacy reconstruction from `historical_lead_source_reconstruction`. Already reviewed source evidence is not automatically invalidated, but any accepted row that entered through the automated/LLM-as-legacy path needs provenance relabeling or audit before it is used as legacy reconstruction evidence or final Step 2/journal-stage input.

## Latest Reviewed URL-Stage Packet

```text
step1_prior_discovery_source_reconstruction_packet_021_024
production_chunk_step1_prior_valid_reverification_test_batch_021
production_chunk_step1_prior_valid_reverification_test_batch_022
production_chunk_step1_prior_valid_reverification_test_batch_023
production_chunk_step1_prior_valid_reverification_test_batch_024
```

Packet 021-024 is the latest Step 1 URL-stage prior-discovery source reconstruction packet accepted by process review. It adds 100 institutions, 1,303 target institution-years, 526 accepted source-ledger rows, 777 explicit unresolved rows, 161 benchmark rows, 145 current-run benchmark recoveries, 16 benchmark rows invalidated by review, 0 benchmark rows resolved by other source-ledger evidence, and 0 unresolved benchmark misses.

No source/test commits were produced by packet 021-024; it ran from `origin/main` at `607276f`.

## Current Production-Construction Totals

- Accepted batches: 24 (001-024)
- Institutions covered: 660
- Institution-years targeted: 9,384
- Accepted source-ledger rows ready for Step 2 text extraction: 4,552
- Explicit unresolved rows: 4,832
- Overall ready/source-ledger rate: 48.5%
- Benchmark rows: 2,811
- Current-run benchmark recovered: 2,445
- Benchmark rows invalidated by review: 365
- Benchmark rows source-ledger-resolved by other evidence: 1
- Unresolved benchmark misses: 0

Accepted-batch sector split:

| Sector | Institutions | Target institution-years | Accepted source-ledger rows | Ready/source-ledger rate |
|---|---:|---:|---:|---:|
| Public | 221 | 3,137 | 1,531 | 48.8% |
| Private nonprofit | 439 | 6,247 | 3,021 | 48.4% |
| Total | 660 | 9,384 | 4,552 | 48.5% |

Full batch-by-batch reporting is in `artifacts/PIPELINE_OUTPUTS/01_url_discovery/reports/prior_discovery_source_reconstruction_rollup/README.md`.

## Next Action

Allow the already-started managed testing packet, `step1_prior_discovery_source_reconstruction_packet_025_028`, to finish only if it stays within true public `valid_human_legacy` selection. The testing packet should preserve run-local artifacts, avoid project-management docs, and hand off to a packet-level process review.

The next packet after 025-028 should run from main at or after `31428db`, so automated/LLM workbook tabs cannot be treated as legacy coverage. If the next work targets imported LLM/programmatic leads, it should use the explicit `historical_lead_source_reconstruction` lane rather than `prior_valid_legacy_reverification`.

## Step 2 Handoff Decision

Do more reviewed Step 1 prior-discovery source reconstruction batches before building the unified URL/source dataset for Step 2. The accepted batch releases currently contain the source-ledger pieces, but the canonical main repo does not yet contain a consolidated Step 2 input table. Build that combined handoff only after more batches receive process-review acceptance, so the aggregation is a deliberate release step rather than a small partial bundle.

## Current Boundaries

- Do not claim clean no-legacy benchmark success from this lane.
- Do not claim journal-release readiness from Step 1 URL-stage artifacts alone.
- Do not treat automated/LLM workbook tabs as human legacy evidence or legacy coverage.
- Do not let imported LLM/programmatic leads satisfy `prior_valid_legacy_reverification`; they belong in a separate historical-lead reconstruction lane.
- Do not use unresolved rows as if they were accepted source evidence.
- Do not count source-ledger-resolved-by-other-evidence rows as current-run benchmark recoveries.
- Do not build the unified Step 2 handoff until more Step 1 batches are accepted.
- Review records for batches 001-024 were produced in their batch worktrees; publishing ignored review artifacts into canonical `process_reviews/` remains a review-stream task, not a project-management task.

## Where Details Live

- Current Step 1 rollup: `artifacts/PIPELINE_OUTPUTS/01_url_discovery/reports/prior_discovery_source_reconstruction_rollup/README.md`
- URL discovery folder map: `artifacts/PIPELINE_OUTPUTS/01_url_discovery/README.md`
- Historical testing log: `artifacts/PILOTS/url_discovery/historical_testing_log/README.md`
- Step 1 run contract and standards: `docs/replication_standards/codex_goals/step_1_url_discovery_run_contract.md`
