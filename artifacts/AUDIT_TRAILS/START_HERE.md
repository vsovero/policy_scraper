# Audit Trails: Start Here

This folder contains detailed evidence snapshots, not the main human-facing
output.

For current decisions and next actions, open:

```text
policy_scraper/artifacts/PIPELINE_OUTPUTS/CURRENT_STATUS_AND_NEXT_STEPS.md
```

For current stage handoff files, open:

```text
policy_scraper/artifacts/PIPELINE_OUTPUTS/
```

For historical Step 1 pilot evidence, open:

```text
policy_scraper/artifacts/PILOTS/url_discovery/
```

For clean-runner smoke and mini-batch test audit evidence, open:

```text
policy_scraper/artifacts/PILOTS/url_discovery/clean_runner_tests/audit_trails/
```

## Current Non-Pilot Audit Folders

```text
url_discovery_step1_full_audit/
url_stage_strict_source_review/
text_readiness_step2_full_audit/
clean_replication_test/
human_replication_gold_standard/
human_legacy_rebuild/
public_legacy_rebuild/
policy_data_internal_existing/
spreadsheet_builders/
```

## Rule Of Thumb

Use `AUDIT_TRAILS/` when you need detailed evidence behind a result.

Use `PILOTS/url_discovery/` when you need the historical pilot batches.

Use `PILOTS/url_discovery/clean_runner_tests/` when you need smoke or mini-batch
evidence for the clean Step 1 runner.

Use `PIPELINE_OUTPUTS/` when you want the current human-facing output.
