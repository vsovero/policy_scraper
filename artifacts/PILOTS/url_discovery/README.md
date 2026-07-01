# URL Discovery Pilots

This is the single folder for historical Step 1 URL-discovery pilot material.

## Folder Meaning

```text
pipeline_outputs/
  Human-facing pilot output folders. Each batch usually contains HOW_CREATED.md,
  BENCHMARKS_AND_ATTRITION.md, OUTPUT_urls_for_text_extraction.csv, and
  REQUIREMENTS_STATUS.csv.

clean_runner_tests/
  Smoke and mini-batch evidence for the clean Step 1 production runner. These
  are test/regression artifacts, not current production chunks or releases.

audit_trails/
  Detailed pilot evidence: manifests, source-review logs, retrieved candidate
  evidence, attrition tables, loss buckets, and production commands.

old_or_superseded/
  Early superseded pilot attempts kept for traceability.
```

## Status

These pilot folders are historical process, development, and regression
evidence. They are useful for understanding what was tested and what failed or
passed, but they are not final production URL-stage releases.

Clean-runner smoke and mini-batch tests live in:

```text
policy_scraper/artifacts/PILOTS/url_discovery/clean_runner_tests/
```

Those tests may demonstrate runner mechanics or preserve failure cases. They
should not be treated as current production chunks, production releases, or
journal-ready packages.

New dataset-construction work should use:

```text
policy_scraper/artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_chunks/
```

and not create more `pilot_batch_*` folders.

## Current Review

The human-written review of the pilot sequence remains in:

```text
policy_scraper/artifacts/PIPELINE_OUTPUTS/01_url_discovery/process_reviews/url_discovery_pilot_batches_review.md
```
