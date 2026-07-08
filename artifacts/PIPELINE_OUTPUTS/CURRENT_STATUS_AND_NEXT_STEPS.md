# Current Status And Next Steps

Updated: 2026-07-07

This is the current human-facing status register for the policy pipeline. It is intentionally short. Historical pilot, drill, and regression notes live in `artifacts/PILOTS/url_discovery/historical_testing_log/README.md`. Current Step 1 production-construction reporting lives in `artifacts/PIPELINE_OUTPUTS/01_url_discovery/reports/prior_discovery_source_reconstruction_rollup/README.md`.

## Current Step 1 Strategy

The active Step 1 lane is `prior-discovery source reconstruction`: rebuild URL/source evidence for institutions with prior discovery evidence using the clean production runner, reviewed source evidence, package-local release files, and explicit unresolved-row accounting. Existing reviewed artifact IDs still contain `prior_valid_reverification`; treat that as a frozen run identifier, not the preferred process name.

This lane is not a clean no-legacy benchmark. It is also not a journal-ready release because downstream text extraction, policy classification, adjudication, final panel construction, and final replication packaging are later-stage work.

## Taxonomy Correction Status

Project-management finding: the old selector allowed some private automated/LLM workbook-tab URLs to enter the legacy reconstruction lane through `legacy_covered_years > 0`. That was incorrect. Automated/LLM tabs are historical lead/search-hint material, not human legacy evidence, and they must not satisfy `prior_valid_legacy_reverification`.

The source/test fix has passed review and is merged in main as `31428db`. The fixed path separates true legacy reconstruction from `historical_lead_source_reconstruction`. The historical-lead benchmark guard fix has passed review and is merged in main as `a298899`. The empty-source-ledger and AI provenance release-packaging fixes have passed review and are merged in main as `e9fea9f`. Already reviewed source evidence is not automatically invalidated, but any accepted row that entered through the automated/LLM-as-legacy path needs provenance relabeling or audit before it is used as legacy reconstruction evidence or final Step 2/journal-stage input.

## Latest Reviewed URL-Stage Packet

```text
step1_historical_lead_source_reconstruction_packet_033_036
production_chunk_step1_historical_lead_source_reconstruction_test_batch_033
production_chunk_step1_historical_lead_source_reconstruction_test_batch_034
production_chunk_step1_historical_lead_source_reconstruction_test_batch_035
production_chunk_step1_historical_lead_source_reconstruction_test_batch_036
```

Packet 033-036 is the latest Step 1 URL-stage historical-lead source reconstruction packet accepted by process review. It adds 103 institutions, 1,231 target institution-years, 66 accepted source-ledger rows, 1,165 explicit unresolved rows, 0 benchmark denominator rows, and 0 unresolved benchmark misses.

Packet 033-036 uses `historical_lead_source_reconstruction`: imported LLM/programmatic leads are search hints only, not human legacy evidence or legacy benchmark rows. Process review confirmed `legacy_covered_years=0`, benchmark denominator `0`, no unresolved rows treated as accepted evidence, AI/API provenance packaged for all four releases, and release-local verification passing for all four releases.

## Current Production-Construction Totals

- Accepted batches: 36 (001-036)
- Institutions covered/targeted in accepted packets: 942
- Institutions with at least one accepted source-ledger row: 599
- Institutions covered but not yet accepted into the source ledger: 343
- Institution-years targeted: 13,049
- Accepted source-ledger rows ready for Step 2 text extraction: 5,374
- Explicit unresolved rows: 7,675
- Overall ready/source-ledger rate: 41.2%
- Benchmark rows: 2,898
- Current-run benchmark recovered: 2,526
- Benchmark rows invalidated by review: 371
- Benchmark rows source-ledger-resolved by other evidence: 1
- Unresolved benchmark misses: 0

Accepted-batch sector split:

| Sector | Targeted institutions | Institutions with accepted source row | Targeted without accepted source row | Target institution-years | Accepted source-ledger rows | Ready/source-ledger rate |
|---|---:|---:|---:|---:|---:|---:|
| Public | 427 | 241 | 186 | 5,942 | 2,298 | 38.7% |
| Private nonprofit | 515 | 358 | 157 | 7,107 | 3,076 | 43.3% |
| Total | 942 | 599 | 343 | 13,049 | 5,374 | 41.2% |

Full batch-by-batch reporting is in `artifacts/PIPELINE_OUTPUTS/01_url_discovery/reports/prior_discovery_source_reconstruction_rollup/README.md`.

## Next Action

Packet 033-036 has passed process review. The reviewed source/test fixes through `e9fea9f` are merged into main.

Recommended next move: continue with packet 037-040 in the `historical_lead_source_reconstruction` lane, starting from main at or after `e9fea9f`.

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
- Review records for batches 001-036 were produced in their batch worktrees; publishing ignored review artifacts into canonical `process_reviews/` remains a review-stream task, not a project-management task.

## Where Details Live

- Current Step 1 rollup: `artifacts/PIPELINE_OUTPUTS/01_url_discovery/reports/prior_discovery_source_reconstruction_rollup/README.md`
- URL discovery folder map: `artifacts/PIPELINE_OUTPUTS/01_url_discovery/README.md`
- Historical testing log: `artifacts/PILOTS/url_discovery/historical_testing_log/README.md`
- Step 1 run contract and standards: `docs/replication_standards/codex_goals/step_1_url_discovery_run_contract.md`
