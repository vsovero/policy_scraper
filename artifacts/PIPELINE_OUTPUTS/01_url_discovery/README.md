# Step 1 URL Discovery Outputs

Open this folder for current URL-discovery production-facing outputs.

Terminology note: use `prior-discovery source reconstruction` for the current
Step 1 lane. Existing reviewed artifact IDs still contain
`prior_valid_reverification` for traceability; treat that phrase as a frozen run
identifier, not the preferred process name.

As of 2026-07-03, the current reviewed Step 1 URL-stage production-test
artifacts are:

```text
production_chunks/production_chunk_step1_prior_valid_reverification_test_batch_004/
production_chunks/production_chunk_step1_prior_valid_reverification_test_batch_004/CHUNK_REPORT.md
production_releases/production_release_step1_prior_valid_reverification_test_batch_004/
```

Bottom line: `step1_prior_valid_reverification_test_batch_004` is the current
accepted Step 1 URL-stage prior-discovery source reconstruction batch. Process
review accepted it for clean production-runner requirements, URL-free historical
case precheck, source-ledger accounting, legacy/prior benchmark accounting,
accepted-source evidence packaging, and package-local release verification. It
does not claim clean no-legacy benchmark success or full journal-release
readiness. The run has `224/420` accepted source rows, `196/420` explicit
unresolved rows, `178` benchmark rows, `165` current-run benchmark recoveries,
`13` benchmark rows invalidated by review, and `0` unresolved benchmark misses.
The ready/source-ledger rate is `53.3%` overall, `64.7%` private, and `25.0%`
public. The release verifies from its own root with `818` files checked and `0`
local path failures. This remains URL-stage evidence only: downstream text
extraction, policy classification, final panel construction, and full journal
replication packaging are not included.

Next production-test action: start
`step1_prior_valid_reverification_test_batch_005` from clean `origin/main` at
or after the batch 004 status update commit, using the same
managed goal/phase table and process-review gate.

The batch 001, batch 002, batch 003, and batch 004 review records were produced
in their batch worktrees. If they should be published into this canonical
`process_reviews/` folder, that should be done by the review stream.

The old transitional production-shaped artifacts were moved to
`policy_scraper/artifacts/PILOTS/url_discovery/` as pilot/history evidence
because they depended on old pilot runtime inputs.

As of 2026-07-01, clean-runner smoke and mini-batch test artifacts were also
moved out of the production-facing folders. They now live under:

```text
policy_scraper/artifacts/PILOTS/url_discovery/clean_runner_tests/
```

Those test artifacts are useful for regression and reporting design, but they
are not current production chunks or production releases.

## Open First

```text
production_chunks/
production_releases/
process_reviews/
historical_inventory/
```

## Current Production Work

Dataset-construction/source-ledger work should use:

```text
production_chunks/production_chunk_*/
```

This folder should contain only clean production-runner chunks. Transitional or
pilot-derived outputs belong under:

```text
policy_scraper/artifacts/PILOTS/url_discovery/
```

Clean production work means extracting and reorganizing reusable code into a
fresh pipeline with explicit inputs and outputs. Do not add wrappers that depend
on old pilot runs as the normal construction path.

Frozen handoffs should use:

```text
production_releases/production_release_*/
```

## Historical Inventory

Historical URL-discovery attempt and discovery inventory planning lives in:

```text
historical_inventory/
```

Detailed normalized evidence should be written under:

```text
policy_scraper/artifacts/AUDIT_TRAILS/url_discovery_historical_inventory/
```

The historical inventory is for batch-priority planning and benchmark
preservation. It is not a production chunk, source-ledger promotion step, clean
benchmark, or journal release. Prior programmatic evidence found there remains
diagnostic or benchmark evidence unless the current production run recovers and
reviews the source.

## Pilot History

Historical pilot, development, and regression folders were consolidated under:

```text
policy_scraper/artifacts/PILOTS/url_discovery/
```

That folder contains both the human-facing pilot outputs and the detailed pilot
audit trails. The old `pilot_batch_*` folders should not be extended in the
Step 1 production-output area.

Clean-runner smoke and mini-batch tests are organized separately under:

```text
policy_scraper/artifacts/PILOTS/url_discovery/clean_runner_tests/
```

Moved transitional artifacts are under the pilot/history folder in the
`pipeline_outputs/` and `audit_trails/` subfolders. They are not current
production chunks or production releases.

## Review Reports

Pilot/development/regression process review:

```text
process_reviews/url_discovery_pilot_batches_review.md
```

Production-chunk process review:

```text
process_reviews/url_discovery_production_chunks_review.md
```
