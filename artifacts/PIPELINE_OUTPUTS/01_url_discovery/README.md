# Step 1 URL Discovery Outputs

Open this folder for current URL-discovery production-facing outputs. This README is a map, not the detailed reporting log.

## Current Lane

Use `prior-discovery source reconstruction` for the current Step 1 lane. Existing reviewed artifact IDs still contain `prior_valid_reverification` for traceability; treat that phrase as a frozen run identifier, not the preferred process name.

Latest reviewed URL-stage packet:

```text
step1_historical_lead_source_reconstruction_packet_037_040
production_chunk_step1_historical_lead_source_reconstruction_test_batch_037
production_chunk_step1_historical_lead_source_reconstruction_test_batch_038
production_chunk_step1_historical_lead_source_reconstruction_test_batch_039
production_chunk_step1_historical_lead_source_reconstruction_test_batch_040
```

Packet 037-040 is the current accepted Step 1 URL-stage historical-lead source reconstruction packet. It does not claim clean no-legacy benchmark success or full journal-release readiness.

The next packet should start from current `origin/main`. Continue `historical_lead_source_reconstruction` for imported LLM/programmatic leads unless project management explicitly changes the active selection objective.

## Current Reporting

- Current status and next action: `../CURRENT_STATUS_AND_NEXT_STEPS.md`
- Batch rollup table: `reports/prior_discovery_source_reconstruction_rollup/README.md`
- Historical pilot/drill/regression log: `../../PILOTS/url_discovery/historical_testing_log/README.md`

Current accepted totals are 40 batches, 1,048 institutions, 14,269 target institution-years, 5,513 accepted source-ledger rows, 8,756 explicit unresolved rows, 1 benchmark row source-ledger-resolved by other evidence, and 0 unresolved benchmark misses.

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
