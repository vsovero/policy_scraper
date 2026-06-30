# Course Repetition Policy Scraper

This folder contains the code, documentation, prompts, tests, and local
artifacts for rebuilding the course repetition policy database.

The current work is shifting from Step 1 URL-discovery pilots to Step 1
production source-ledger construction. Existing `pilot_batch_*` folders are
historical process/regression evidence; new dataset-construction work should
use `production_chunk_*` outputs rather than new pilot labels.

Current reproducibility strategy: Codex may assist code development, debugging,
and source-review triage, but the required replication package should not
depend on live Codex code fixing or live source rediscovery. General discoveries
become general code or documented source-family rules. Row-specific accepted
sources become transparent rows in a frozen source ledger. The final dataset
should rebuild from that ledger, archived/cached source artifacts, code, and
cached model outputs where applicable.

## Open First

For current Step 1 outputs and status:

```text
artifacts/PIPELINE_OUTPUTS/START_HERE.md
artifacts/PIPELINE_OUTPUTS/CURRENT_STATUS_AND_NEXT_STEPS.md
artifacts/PIPELINE_OUTPUTS/CLEAN_REBUILD_VALIDATION_PLAN.md
artifacts/PIPELINE_OUTPUTS/01_url_discovery/
artifacts/PIPELINE_OUTPUTS/01_url_discovery/process_reviews/url_discovery_pilot_batches_review.md
```

For detailed evidence and audit trails:

```text
artifacts/AUDIT_TRAILS/START_HERE.md
artifacts/FOLDER_MAP.csv
```

For replication standards and Codex goals:

```text
docs/README.md
docs/replication_standards/README.md
docs/replication_standards/codex_goals/step_1_url_discovery_run_contract.md
docs/replication_standards/requirements_checklist.md
docs/replication_standards/url_source_review_standard.md
```

## Current Status

The active human-facing output area is:

```text
artifacts/PIPELINE_OUTPUTS/
```

Current decisions, cleanup proposals, and production-readiness notes live in:

```text
artifacts/PIPELINE_OUTPUTS/CURRENT_STATUS_AND_NEXT_STEPS.md
```

The active plan for a self-contained computer-versus-human validation rebuild is:

```text
artifacts/PIPELINE_OUTPUTS/CLEAN_REBUILD_VALIDATION_PLAN.md
```

The Step 1 URL-discovery output folder is:

```text
artifacts/PIPELINE_OUTPUTS/01_url_discovery/
```

The human-written URL-discovery process review is:

```text
artifacts/PIPELINE_OUTPUTS/01_url_discovery/process_reviews/url_discovery_pilot_batches_review.md
```

Historical pilot/regression outputs are not final production URL-stage
releases. They are process evidence: bounded batches, visible output CSVs,
status/reason fields for every row, generated provenance documentation,
generated benchmark/attrition documentation, and detailed audit evidence kept
outside the normal view.

The next dataset-construction unit should be `production_chunk_001`. Its goal
is not to prove blind URL discovery again. Its goal is to close a bounded set of
institution-years into the source ledger: each row gets an accepted reviewed
source URL or an explicit unresolved/unrecoverable reason, with provenance for
human legacy, prior programmatic, new programmatic, manual review, or
API-assisted evidence.

Detailed logs, candidate ledgers, source-review logs, validation audits, cached
artifacts, and manifests live under:

```text
artifacts/AUDIT_TRAILS/
```

Superseded layouts and old delivery packets live under:

```text
artifacts/OLD_OUTPUT_ARCHIVES/
```

The old top-level `policy_data/` workflow is no longer the active front door.
Some older code and documentation may still mention it; use `artifacts/FOLDER_MAP.csv`
to locate the corresponding current or archived files.

## Pipeline Boundary

Step 1 is URL discovery and URL validation only. It may produce a URL handoff
for later text extraction, but it does not:

```text
download full source text for classification
search source text for course-repetition language
classify policy
call OpenAI/API classification
assemble the final journal replication package
```

The stable Step 1 URL-discovery run contract is defined in:

```text
docs/replication_standards/codex_goals/step_1_url_discovery_run_contract.md
```

The URL/source review standard is:

```text
docs/replication_standards/url_source_review_standard.md
```

## Folder Roles

```text
policy_scraper/
  README.md
  pyproject.toml
  artifacts/
    PIPELINE_OUTPUTS/      # small human-facing stage outputs
    AUDIT_TRAILS/          # detailed evidence and reproducibility files
    OLD_OUTPUT_ARCHIVES/   # superseded output layouts and historical packets
    FOLDER_MAP.csv         # map from old locations to current locations
  config/                  # pipeline settings and API config templates
  docs/                    # replication standards and current Codex goals
  prompts/                 # prompt templates and schemas for AI-assisted tasks
  src/course_policy/       # Python package code
  tests/                   # unit tests and fixture-based checks
```

## Design Principle

The final policy data should be generated from code and traceable to source
evidence. The production source ledger should make ambiguity visible instead of
hiding it: candidate URLs are not production evidence until the source-review
gate is documented and passed.

Do not hard-code Codex-assisted source findings into scraper logic. If a finding
is general, turn it into a general rule or code path. If it is row-specific,
record it in the source ledger as data/provenance.
