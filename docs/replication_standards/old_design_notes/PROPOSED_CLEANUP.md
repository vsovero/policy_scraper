# Proposed Cleanup Plan

Created: 2026-06-23
Revised: 2026-06-23

This is only a proposal. It does not move, delete, rename, or archive anything.

## Main Problem

There are too many policy folders and too many output files. The cleanup should
make it easy to observe what the pipeline is creating and quickly inspect
whether it makes sense.

The goal is not to create a manual-review workspace.

The goal is:

```text
one place to look
one small folder per pipeline phase
one clear creation/provenance note per phase
one benchmark/attrition note per phase
one main next-stage output file per phase
clear column names so the output can be inspected directly
```

## Core Decision

Use `policy_scraper/` as the home for the policy pipeline.

Retire `policy_data/` as an active folder. It is too vague and currently mixes
data, reports, and review outputs.

Do not create a replication-package folder yet. A replication package is the
future journal/paper artifact that reproduces the project from start to finish.

## Target Shape

Inside `policy_scraper/artifacts/`, use:

```text
policy_scraper/artifacts/
  PIPELINE_OUTPUTS/
  INTERNAL_DO_NOT_OPEN/
  OLD_OUTPUTS_DO_NOT_USE/
```

Meaning:

```text
PIPELINE_OUTPUTS/
  The place to observe and inspect current pipeline products.

INTERNAL_DO_NOT_OPEN/
  Logs, caches, source downloads, full extracted text, temporary work tables,
  and giant audit traces.

OLD_OUTPUTS_DO_NOT_USE/
  Previous runs and historical snapshots kept for safety, not for current use.
```

## `PIPELINE_OUTPUTS/`

This is the only place you should normally look.

```text
policy_scraper/artifacts/PIPELINE_OUTPUTS/
  START_HERE.md

  01_url_discovery/
    HOW_CREATED.md
    BENCHMARKS_AND_ATTRITION.md
    OUTPUT_urls_for_text_extraction.csv

  02_text_extraction/
    HOW_CREATED.md
    BENCHMARKS_AND_ATTRITION.md
    OUTPUT_text_for_classification.csv

  03_policy_classification/
    HOW_CREATED.md
    BENCHMARKS_AND_ATTRITION.md
    OUTPUT_policy_classification.csv
```

No `support/` folder. No pile of miscellaneous CSVs.

The output file is both the next-stage handoff and the file to inspect. It
should have enough columns, clear labels, and status fields that it can be
understood without opening several other files.

## Link To Replication Requirements

Each phase folder should map directly to the project replication checklist:

```text
llm_replication_standards_review/requirements_checklist.md
```

The two markdown files have different jobs:

```text
HOW_CREATED.md
  Documents provenance and reproducibility:
  inputs, code, run order, unit of observation, output schema, and audit trail.

BENCHMARKS_AND_ATTRITION.md
  Documents validation:
  benchmark standard, denominators, pass/fail results, attrition, loss
  explanations, and publication caveats.
```

Neither file should be a loose narrative. Each should explicitly name the
replication requirement it satisfies and the evidence file that supports it.

## Example: URL Discovery Phase

The URL discovery phase would look like:

```text
policy_scraper/artifacts/PIPELINE_OUTPUTS/01_url_discovery/
  HOW_CREATED.md
  BENCHMARKS_AND_ATTRITION.md
  OUTPUT_urls_for_text_extraction.csv
```

### `HOW_CREATED.md`

This is the first thing to open.

It should answer:

```text
What file did this phase create?
What is the unit of observation?
What inputs were used?
What code or script created it?
What steps were applied?
What columns matter for understanding the file?
Which replication requirements does this satisfy?
Where are the detailed internal files if someone needs the audit trail?
```

Example:

```text
# How Created: URL Discovery Output

Output file:
OUTPUT_urls_for_text_extraction.csv

Unit of observation:
One institution-year.

Purpose:
Select the best available source URL for each institution-year so the text
extraction phase can retrieve and parse source material.

Inputs:
- human legacy URL panels
- programmatic URL discovery outputs
- IPEDS institution-year panel
- manual/source review logs where available

Creation steps:
1. Build the target institution-year panel.
2. Preserve human legacy URLs where available.
3. Add reviewed programmatic URLs only where no human URL is available.
4. Assign a plain-English URL status and reason.
5. Export one URL handoff file for text extraction.

Key columns:
- unitid: IPEDS institution ID
- institution_name: institution name
- year: catalog/policy year
- url_for_text_extraction: URL selected for the text-extraction phase
- url_source_type: human legacy, programmatic fill, or no URL
- url_status: ready, missing, blocked, or needs caution
- url_status_reason: short explanation of the status
- source_evidence_note: compact reason this URL was selected

Replication requirements satisfied:
- Maintain separate, documented stages for URL discovery, text extraction, and
  classification.
- Preserve row-level source provenance.
- Keep missingness visible through URL status and status-reason columns.
- Make live web/API reruns optional by documenting cached/default inputs.

Summary counts:
- target institution-years: 35,989
- rows with URL: 5,653
- rows without URL: 30,336
- human URL rows preserved: 5,203
- programmatic URL rows added: 450

Internal audit trail:
Detailed logs, candidate tables, reconciliation files, and manifests are stored
outside the normal view under INTERNAL_DO_NOT_OPEN.
```

### `BENCHMARKS_AND_ATTRITION.md`

This is separate from `HOW_CREATED.md`.

It is the publication-standards evidence file for the phase. It should answer:

```text
What standard is this phase being held to?
Which replication requirement requires this validation?
What benchmark sample was used?
What numerator and denominator were used?
Did the phase clear the standard, such as 90% human replication?
Where did rows get lost?
Are losses explained in plain English?
What caveats should be disclosed in the paper or replication materials?
Where are the detailed internal benchmark files?
```

Example:

```text
# Benchmarks And Attrition: URL Discovery

Benchmark standard:
At least 90% recovery against valid held-out human legacy URL rows in the
estimation sample.

Replication requirement:
Maintain a hidden legacy benchmark for discovery quality and report retrieval
stage rates by sector and combined sample.

Benchmark result:
- accepted URL among valid held-out rows: 1,783 / 1,979 = 90.1%
- status: passes combined 90% standard

Sector detail:
- public: 239 / 261 = 91.6%
- private: 1,544 / 1,718 = 89.9%

Attrition summary:
- target institution-years: 25,191
- rows with production URL: 6,337
- rows without production URL: 18,854

Main loss explanations:
- no active human legacy URL available for many institution-years
- programmatic discovery found candidate URLs for some rows but not all
- some programmatic candidate institutions require additional panel-level
  source review before production use

Publication caveat:
The combined held-out URL recovery benchmark clears 90%, but private-sector
recovery is just below 90% in the estimation sample. This should be reported
explicitly if this benchmark is used as evidence.

Detailed internal files:
- stage_rates.csv
- bucket_reconciliation.csv
- legacy_validation_scores.csv
- loss_buckets.csv
- file_manifest.csv
```

### `OUTPUT_urls_for_text_extraction.csv`

This is the machine-readable product of the phase. It feeds the next stage.

It should also be readable enough to inspect directly. That means:

```text
clear column names
one row per institution-year
one selected next-stage URL column
plain-English status and reason columns
compact evidence/source columns
no mystery abbreviations unless explained in HOW_CREATED.md
```

If the output needs extra audit fields, keep them at the far right. The first
columns should be the human-readable ones.

## What Happens To Extra Files

Extra files are still allowed to exist. They just should not be in the normal
view.

Examples:

```text
bucket_reconciliation.csv
manual_url_review_log.csv
source_decision_audit.csv
url_candidate_audit.csv
url_validation_audit.csv
file_manifest.csv
```

These should be handled in one of three ways:

```text
creation/provenance details
  -> summarize in HOW_CREATED.md

benchmark, attrition, and pass/fail evidence
  -> summarize in BENCHMARKS_AND_ATTRITION.md

row-level fields needed by the next stage or useful for direct inspection
  -> include as clear columns in OUTPUT_*.csv
```

The raw extra files can live under:

```text
policy_scraper/artifacts/INTERNAL_DO_NOT_OPEN/01_url_discovery/
```

That way the evidence is preserved, but the normal user experience is not a
maze.

## Current Top-Level Policy Folders

Do not move these while work may be running:

```text
policy_data/
policy_data_rebuild/
policy_url_stage_human_standard/
policy_url_discovery_step1/
policy_text_readiness_step2/
policy_database_clean_replication_test/
policy_database_human_legacy_rebuild/
policy_human_legacy_public_rebuild/
policy_human_replication_gold_standard/
policy_data_rebuild_archive_20260622_054122/
llm_replication_standards_review/
```

Later, sort their contents like this:

```text
small current phase outputs for direct inspection
  -> policy_scraper/artifacts/PIPELINE_OUTPUTS/

large logs, source downloads, extracted text, caches, audit traces, work tables
  -> policy_scraper/artifacts/INTERNAL_DO_NOT_OPEN/

old snapshots and previous phase folders
  -> policy_scraper/artifacts/OLD_OUTPUTS_DO_NOT_USE/
```

## What Happens To `policy_data/`

Current contents observed:

```text
policy_data/
  README.md
  file_manifest.csv
  policy_database_new_discovery_review.csv
  policy_database_new_discovery_review.xlsx
```

Plan:

1. Freeze `policy_data/` as temporary.
2. Stop writing new reports there.
3. Move anything still useful into the appropriate phase under
   `PIPELINE_OUTPUTS/`.
4. Move extra supporting machinery into `INTERNAL_DO_NOT_OPEN/`.
5. Update docs/scripts that point to `policy_data/`.
6. Retire or archive `policy_data/` once nothing depends on it.

## Cleanup Sequence

### Phase 0: While Jobs May Be Running

Only document. Do not move folders or files.

### Phase 1: Create The Observation Area

Later, create:

```text
policy_scraper/artifacts/PIPELINE_OUTPUTS/
policy_scraper/artifacts/INTERNAL_DO_NOT_OPEN/
policy_scraper/artifacts/OLD_OUTPUTS_DO_NOT_USE/
```

### Phase 2: Build One Phase Folder First

Start with URL discovery:

```text
policy_scraper/artifacts/PIPELINE_OUTPUTS/01_url_discovery/
  HOW_CREATED.md
  BENCHMARKS_AND_ATTRITION.md
  OUTPUT_urls_for_text_extraction.csv
```

If that feels navigable, repeat for text extraction and classification.

### Phase 3: Hide The Machinery

Move large and confusing generated material into `INTERNAL_DO_NOT_OPEN/` or
`OLD_OUTPUTS_DO_NOT_USE/`.

### Phase 4: Retire `policy_data/`

Only after docs and scripts no longer depend on it.
