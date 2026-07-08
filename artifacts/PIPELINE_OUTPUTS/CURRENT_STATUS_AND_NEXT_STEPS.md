# Current Status And Next Steps

Updated: 2026-07-07

This is the current human-facing status register for the policy pipeline. It is intentionally short. Historical pilot, drill, and regression notes live in `artifacts/PILOTS/url_discovery/historical_testing_log/README.md`. Current Step 1 production-construction reporting lives in `artifacts/PIPELINE_OUTPUTS/01_url_discovery/reports/prior_discovery_source_reconstruction_rollup/README.md`.

## Current Step 1 Strategy

The active Step 1 lane is `prior-discovery source reconstruction`: rebuild URL/source evidence for institutions with prior discovery evidence using the clean production runner, reviewed source evidence, package-local release files, and explicit unresolved-row accounting. Existing reviewed artifact IDs still contain `prior_valid_reverification`; treat that as a frozen run identifier, not the preferred process name.

This lane is not a clean no-legacy benchmark. It is also not a journal-ready release because downstream text extraction, policy classification, adjudication, final panel construction, and final replication packaging are later-stage work.

## Taxonomy Correction Status

Project-management finding: the old selector allowed some private automated/LLM workbook-tab URLs to enter the legacy reconstruction lane through `legacy_covered_years > 0`. That was incorrect. Automated/LLM tabs are historical lead/search-hint material, not human legacy evidence, and they must not satisfy `prior_valid_legacy_reverification`.

The source/test fix has passed review and is merged in main as `31428db`. The fixed path separates true legacy reconstruction from `historical_lead_source_reconstruction`. The additional historical-lead benchmark guard fix has passed review and is merged in main as `a298899`. Already reviewed source evidence is not automatically invalidated, but any accepted row that entered through the automated/LLM-as-legacy path needs provenance relabeling or audit before it is used as legacy reconstruction evidence or final Step 2/journal-stage input.

## Latest Reviewed URL-Stage Packet

```text
step1_historical_lead_source_reconstruction_packet_029_032
production_chunk_step1_historical_lead_source_reconstruction_test_batch_029
production_chunk_step1_historical_lead_source_reconstruction_test_batch_030
production_chunk_step1_historical_lead_source_reconstruction_test_batch_031
production_chunk_step1_historical_lead_source_reconstruction_test_batch_032
```

Packet 029-032 is the latest Step 1 URL-stage historical-lead source reconstruction packet accepted by process review. It adds 97 institutions, 1,228 target institution-years, 299 accepted source-ledger rows, 929 explicit unresolved rows, 0 benchmark denominator rows, and 0 unresolved benchmark misses.

Packet 029-032 uses `historical_lead_source_reconstruction`: imported LLM/programmatic leads are search hints only, not human legacy evidence or legacy benchmark rows. Process review confirmed `legacy_covered_years=0`, benchmark denominator `0`, no validated-human legacy in the source ledger, no unresolved rows treated as accepted evidence, and release-local verification passing for all four releases.

## Current Production-Construction Totals

- Accepted batches: 32 (001-032)
- Institutions covered: 839
- Institution-years targeted: 11,818
- Accepted source-ledger rows ready for Step 2 text extraction: 5,308
- Explicit unresolved rows: 6,510
- Overall ready/source-ledger rate: 44.9%
- Benchmark rows: 2,898
- Current-run benchmark recovered: 2,526
- Benchmark rows invalidated by review: 371
- Benchmark rows source-ledger-resolved by other evidence: 1
- Unresolved benchmark misses: 0

Accepted-batch sector split:

| Sector | Institutions | Target institution-years | Accepted source-ledger rows | Ready/source-ledger rate |
|---|---:|---:|---:|---:|
| Public | 362 | 5,124 | 2,238 | 43.7% |
| Private nonprofit | 477 | 6,694 | 3,070 | 45.9% |
| Total | 839 | 11,818 | 5,308 | 44.9% |

Full batch-by-batch reporting is in `artifacts/PIPELINE_OUTPUTS/01_url_discovery/reports/prior_discovery_source_reconstruction_rollup/README.md`.

## Next Action

Packet 029-032 has passed process review. The reviewed source/test fix `a298899` is merged into main.

Recommended next move: continue with the next `historical_lead_source_reconstruction` packet for imported LLM/programmatic leads, starting from main at or after `a298899`.

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
- Review records for batches 001-032 were produced in their batch worktrees; publishing ignored review artifacts into canonical `process_reviews/` remains a review-stream task, not a project-management task.

## Where Details Live

- Current Step 1 rollup: `artifacts/PIPELINE_OUTPUTS/01_url_discovery/reports/prior_discovery_source_reconstruction_rollup/README.md`
- URL discovery folder map: `artifacts/PIPELINE_OUTPUTS/01_url_discovery/README.md`
- Historical testing log: `artifacts/PILOTS/url_discovery/historical_testing_log/README.md`
- Step 1 run contract and standards: `docs/replication_standards/codex_goals/step_1_url_discovery_run_contract.md`
