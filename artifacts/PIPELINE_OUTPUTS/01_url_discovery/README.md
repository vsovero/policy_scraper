# Step 1 URL Discovery Outputs

Open this folder for current URL-discovery production-facing outputs. This README is a map, not the detailed reporting log.

## Current Lane

Use `prior-discovery source reconstruction` for the current Step 1 lane. Existing reviewed artifact IDs still contain `prior_valid_reverification` for traceability; treat that phrase as a frozen run identifier, not the preferred process name.

Latest reviewed URL-stage packet:

```text
step1_prior_discovery_source_reconstruction_packet_013_016
production_chunk_step1_prior_valid_reverification_test_batch_013
production_chunk_step1_prior_valid_reverification_test_batch_014
production_chunk_step1_prior_valid_reverification_test_batch_015
production_chunk_step1_prior_valid_reverification_test_batch_016
```

Packet 013-016 is the current accepted Step 1 URL-stage prior-discovery source reconstruction packet. It does not claim clean no-legacy benchmark success or full journal-release readiness.

## Current Reporting

- Current status and next action: `../CURRENT_STATUS_AND_NEXT_STEPS.md`
- Batch rollup table: `reports/prior_discovery_source_reconstruction_rollup/README.md`
- Historical pilot/drill/regression log: `../../PILOTS/url_discovery/historical_testing_log/README.md`

Current accepted totals are 16 batches, 448 institutions, 6,550 target institution-years, 3,226 accepted source-ledger rows, 3,324 explicit unresolved rows, 1 benchmark row source-ledger-resolved by other evidence, and 0 unresolved benchmark misses.

## Step 2 Handoff Decision

Continue running reviewed Step 1 prior-discovery source reconstruction batches before creating a unified URL/source input for Step 2. The reviewed batch releases hold the current source-ledger pieces; the canonical main repo does not yet contain a consolidated Step 2 handoff table.

## Folder Roles

```text
production_chunks/       Clean production-runner chunk outputs when published here.
production_releases/     Frozen Step 1 release packages when published here.
process_reviews/         Review records published by the review stream.
historical_inventory/    URL-free historical planning/precheck memory.
reports/                 Current production-construction reporting.
```

Completed batch release artifacts currently live in `policy_scraper_worktrees/completed/` until a deliberate publication or aggregation step moves them into a canonical release bundle.
