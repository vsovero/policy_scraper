# Production Streams

## Purpose

The project should now be organized by production streams, not by old pilot or
batch names. A stream is a source route with a defined input, trust level,
review gate, and output namespace.

This matters because public legacy URLs, private legacy URLs, public fresh
discovery, and private fresh discovery should not blur together. They can all
flow through the same shared code, but each stream needs a clear status and
audit trail.

It is equally important that production recovery and benchmarking do not blur
together. Human legacy URLs may be used to rebuild the existing dataset, but
using them cannot count as clean no-legacy benchmark success.

The benchmark protocol is:

| Lane | Purpose | Human legacy URLs allowed? | Counts as clean no-legacy benchmark? |
|---|---|---:|---:|
| `legacy_assisted_rebuild` | Recover the existing usable dataset with all legitimate evidence. | yes | no |
| `known_url_execution_diagnostic` | Test retrieval, extraction, policy search, and classification after a valid human URL is supplied. | yes | no |
| `clean_no_legacy_benchmark` | Prove the no-legacy pipeline can independently find and classify sources. | no | yes |

The clean no-legacy benchmark target is 90 percent on a manually validated
sample where the source exists and is reasonably discoverable. The
known-URL diagnostic target is 90-100 percent among valid/retrievable human
legacy URLs, but that diagnostic is not a discovery benchmark.

## Current Stream Map

| Order | Stream | Status | Meaning |
|---:|---|---|---|
| 10 | `public_legacy_url` | current catalog URL component | Human-entered public legacy URLs from the old public workbook. |
| 20 | `private_human_legacy_url` | current catalog URL component | Human-entered private legacy URLs from the old private workbook. |
| 30 | `public_fresh_discovery` | current catalog URL component | Public institutions or years not resolved by public legacy URLs. |
| 40 | `private_new_legacy_url` | review-gated workspace, not final | Automated or LLM-suggested private workbook URL leads. |
| 50 | `private_fresh_discovery` | current catalog URL component | Private institutions with no human-entered private legacy URL, using bounded official-site catalog discovery. |
| 90 | `combined_catalog_url_database` | current front-facing output | Validated stream outputs merged into the flat `policy_data` catalog URL database. |

The code version of this registry is:

`src/course_policy/production_streams.py`

## Current Production Command

Use this command to run the deterministic private no-human-legacy fresh
discovery stream:

```bash
PYTHONPATH=src python -m course_policy.private_fresh_discovery
```

This command calls external websites, but does not call the OpenAI API. Its
outputs live in the `private_fresh_discovery/current` stream folders and are
picked up by the catalog database rebuild.

Use this command to rebuild the current catalog URL database from the staged
production streams:

```bash
PYTHONPATH=src python -m course_policy.catalog_pipeline
```

By default this command:

- stages current stream outputs under `artifacts/policy_data_internal/*/streams/<stream_id>/current/`;
- uses recovered public/private human legacy panels when those upstream fixes exist;
- includes the private fresh-discovery stream when its current run files exist;
- includes the private new-legacy URL stream as review-gated, not final evidence;
- regenerates `policy_data/catalog_url_database.csv`;
- regenerates `policy_data/catalog_url_database.xlsx`;
- regenerates the public and private legacy benchmarks against the old
  downstream `gfdatafull` valid-policy panels when `gfdatafull.dta` is
  available;
- writes stream manifests under `artifacts/policy_data_internal/logs/streams/<stream_id>/current/`.

It does not call external websites or the OpenAI API.

The catalog database is a production rebuild object. It may contain both
legacy-assisted and independently discovered rows. Its `benchmark_protocol`
fields describe how a row may be used in evaluation, but a clean no-legacy
benchmark must still exclude any row with legacy URL/source hints.

The legacy coverage benchmark is always the old downstream `gfdatafull`
valid-policy panel for the sector being measured, not the raw student
change-log rows and not the newly generated URL universe. The row-level
benchmarks live at:

```text
artifacts/policy_data_internal/review/url_fix_validation/current/gfdatafull_public_valid_policy_panel_attrition.csv
artifacts/policy_data_internal/review/url_fix_validation/current/gfdatafull_private_valid_policy_panel_attrition.csv
```

The summary table also reports the outcome-valid subset separately, because not
all institutions or years have graduation outcomes. It also reports
policy-spell coverage, which respects the original downstream panel expansion:
if a contiguous same-policy spell has a recovered source/classification in one
year, the diagnostic shows how many old panel rows that spell would cover.

```text
artifacts/policy_data_internal/review/url_fix_validation/current/gfdatafull_public_valid_policy_panel_attrition_summary.csv
artifacts/policy_data_internal/review/url_fix_validation/current/gfdatafull_private_valid_policy_panel_attrition_summary.csv
```

The benchmark also writes ranked policy-spell queues for the next extraction or
classification pass. These queues sort by old-panel rows covered, so the first
rows are the fastest route to the 70% and 80% coverage gates:

```text
artifacts/policy_data_internal/review/url_fix_validation/current/gfdatafull_public_policy_spell_classification_priority.csv
artifacts/policy_data_internal/review/url_fix_validation/current/gfdatafull_private_policy_spell_classification_priority.csv
```

Each priority row carries a `policy_spell_work_bucket`. Interpret it before
starting automation:

- `needs_source_retrieval`: run source retrieval/excerpt extraction.
- `cached_retrieved_short_or_empty_no_terms`: source retrieval happened, but
  extraction was too short or empty; rescue the source/text extraction.
- `cached_retrieved_long_text_no_terms`: text exists but no course-repetition
  terms were found; review term search/scope before API classification.
- `cached_retrieval_failed`: repair retrieval or replace the URL.
- `cached_policy_terms_ready_for_classification`: classification/API is the
  next step.

To build the 80%-target priority queues currently used for the next run:

```bash
PYTHONPATH=src python -m course_policy.policy_extraction_queue \
  --output-stem policy_extraction_queue_public_spell80 \
  --priority-spell-queue artifacts/policy_data_internal/review/url_fix_validation/current/gfdatafull_public_policy_spell_classification_priority.csv \
  --priority-limit 46

PYTHONPATH=src python -m course_policy.policy_extraction_queue \
  --output-stem policy_extraction_queue_private_spell80 \
  --priority-spell-queue artifacts/policy_data_internal/review/url_fix_validation/current/gfdatafull_private_policy_spell_classification_priority.csv \
  --priority-limit 121
```

Run these queues through the production block runner with `--queue-path` so the
outputs are queue-specific and cannot collide with ordinary row-ordered runs.

After the catalog database is rebuilt, use this command to build the internal
policy-extraction queue:

```bash
PYTHONPATH=src python -m course_policy.policy_extraction_queue
```

The queue command reads `policy_data/catalog_url_database.csv` and keeps only
rows with `policy_extraction_ready = true`. Review-gated rows, including
`private_new_legacy_url`, are excluded unless the command is run with
`--include-review-gated`.

For human legacy streams, a valid URL is allowed into policy extraction even
when the URL string looks like a policy page, handbook, or unknown-scope source.
That is a known-URL execution diagnostic and rebuild route. For no-legacy/fresh
streams, source-scope gates still apply before extraction because no human URL
prior exists.

## Policy Excerpt and Classification Production

After `policy_extraction_queue` is rebuilt, use the production block runner for
large-scale policy extraction, local classification, API backfill, and rollup.
The runner keeps retrieval internally chunked, defaults to resuming existing
outputs, and writes one combined block deliverable:

```bash
PYTHONPATH=src python -m course_policy.policy_production_block \
  --source-stream public_legacy_url \
  --start-row 101 \
  --total-rows 500 \
  --chunk-size 25 \
  --api-mode live \
  --api-request-cap 250 \
  --config config/openai.local.toml
```

`--start-row` is one-indexed after filtering to the requested source stream.
For example, the validated first block used rows `1-100`; the next block should
start at `101`. The runner writes a temporary live config copy when
`--api-mode live` is used, so `config/openai.local.toml` can stay locked in
`dry_run` with `max_requests_per_run = 0`. The live process still requires
`OPENAI_API_KEY` in the environment.

The production block runner runs a quality gate after each combined block.
With the default `--quality-gate auto`, live production enforces the gate and
dry-run/skip modes write a report only. A failed gate means broad unattended
automation must stop before the next block starts. The report is written next
to the normal block summaries as:

```text
artifacts/policy_data_internal/logs/policy_classification_production_excerpt_<stream>_<rows>_api_<mode>_quality_gate.md
```

Resume broad automation only after a targeted rescue pass is run on the failed
loss bucket and a bounded validation slice passes the quality gate. If a
diagnostic run intentionally needs to inspect low-yield behavior, pass
`--quality-gate report` instead of disabling the gate. Use `--quality-gate off`
only for local debugging where no production decision will be made from the
outputs.

For classification, larger API caps are acceptable. The first 100
`public_legacy_url` queue rows used 73 live API calls and cost about $0.10.
Retrieval/PDF extraction is the bottleneck, not classification API cost.

The lower-level commands remain useful for debugging individual chunks. This
command retrieves catalog sources, extracts text, and searches for candidate
course-repetition policy passages. It does not call the OpenAI API:

```bash
PYTHONPATH=src python -m course_policy.policy_excerpt_search \
  --production-queue \
  --source-stream public_legacy_url \
  --limit 25 \
  --output-suffix production_queue_public_legacy_001_025 \
  --timeout-seconds 20 \
  --max-pdf-pages 80 \
  --pdf-timeout-seconds 30 \
  --reuse-existing-source-audit \
  --checkpoint-source-audit
```

Use `--offset` with the same `--limit` to advance through later chunks. Keep
`--reuse-existing-source-audit` and `--checkpoint-source-audit` on production
runs so interrupted or repeated chunks do not restart source retrieval from
zero.

Then classify the extracted production excerpts with the existing classification
pipeline. This command is deterministic when `--api-hard-case-limit 0` is used:

```bash
PYTHONPATH=src python -m course_policy.policy_classification_batch \
  --input-kind production_excerpts \
  --production-excerpt-path artifacts/policy_data_internal/review/catalog_policy_excerpt_year_review_production_queue_public_legacy_001_025.csv \
  --source-stream public_legacy_url \
  --suffix production_excerpt_public_legacy_001_025_rules \
  --limit 25 \
  --api-hard-case-limit 0 \
  --skip-source-context
```

For guarded API review, use the existing backfill command. First run it while
`config/openai.local.toml` is still in `dry_run` mode to write prompts and verify
the exact rows selected:

```bash
PYTHONPATH=src python -m course_policy.policy_classification_api_backfill \
  --input-csv artifacts/policy_data_internal/review/policy_classification_batch_results_production_excerpt_public_legacy_001_025_rules.csv \
  --output-stem policy_classification_production_excerpt_public_legacy_001_025_api_dryrun_005 \
  --limit 5 \
  --config config/openai.local.toml
```

Only switch `config/openai.local.toml` to `mode = "live"` for a deliberately
small batch, with `max_requests_per_run` set to the same intended request cap.
After the live pass, return the local config to `dry_run` and
`max_requests_per_run = 0`.

## What Counts As Legacy

Use narrower labels instead of the single word `legacy`:

- `public_legacy_url`: public workbook rows entered by students/humans.
- `private_human_legacy_url`: private workbook rows entered by students/humans.
- `private_new_legacy_url`: automated or LLM-suggested private workbook URL leads. These are legacy-like because they came from the workbook ecosystem, but they are not trusted human legacy evidence.

This distinction is important. Human legacy URLs are strong prior evidence.
Automated or LLM-suggested private URLs are leads only.

Human legacy URLs are also not clean benchmark evidence. They can support
`legacy_assisted_rebuild` and `known_url_execution_diagnostic`, but they must be
withheld from `clean_no_legacy_benchmark`.

## Private New Legacy URL Space

`private_new_legacy_url` is the reserved/review-gated stream for private
automated or LLM-suggested leads. Existing prototype files may be staged here,
but they are not final catalog evidence.

It should be used for:

- URLs from the private workbook's automated missing-private sheet;
- LLM-suggested private URLs that came through the legacy workbook workflow;
- URL leads that preserve workbook provenance but were not human-coded source evidence.

Every row in this stream must preserve:

- workbook sheet;
- workbook row;
- parent URL if available;
- page number if available;
- score or confidence field if available;
- original excerpt or surrounding text if available;
- source seed type;
- source trust level;
- review gate.

Required default values:

```text
source_seed_type = private_workbook_automated_missing_private_url
source_trust_level = unverified_suggestion
requires_source_review = true
review_gate = verify_official_scope_catalog_year_and_source_type
```

Rows from this stream may be retrieved and searched for policy language, but
they cannot become final catalog evidence until the review gate is resolved.

## Private Fresh AI Rescue Gate

The private fresh-discovery stream has many unresolved institutions, so API
web-search rescue is intentionally limited to high-priority cases.

High-priority cases are deterministic first-pass gaps where the pipeline either:

1. found a plausible source root but extracted no explicit academic-year catalog links; or
2. retrieved candidate roots but did not recognize them as catalog roots.

Cases where no source root was retrieved are not included in this API rescue
pass. Those cases are much more numerous and lower-yield, especially among
small or obscure private institutions, so running web-search API calls over all
of them would spend money on a broad fresh-discovery task rather than on likely
gap-filling. They should remain deferred unless a later project decision raises
the value/cost threshold.

Private fresh AI rescue outputs are diagnostic until reviewed. They live under:

`artifacts/policy_data_internal/review/streams/private_fresh_discovery/current/`

The diagnostic runner is:

```bash
PYTHONPATH=src python -m course_policy.private_fresh_ai_rescue --config config/openai.local.toml --max-api-cases 10
```

The local config should keep `max_requests_per_run` small. The runner skips
institutions already present in `ai_rescue_triage.csv`, so repeated 10-case
runs progress through the high-priority queue without paying twice for the same
institution.

## Source Priority

Within an institution-year, use this order unless a documented exception says
otherwise:

1. verified coherent institution-wide undergraduate catalog root;
2. human legacy URL that retrieves and has catalog-year evidence;
3. bounded official or institutional archive gap-fill;
4. private new legacy URL lead after review gate is resolved;
5. fresh discovery lead after source scope and catalog-year evidence are verified;
6. unresolved queue with a defined stop reason.

Student or legacy comparisons should be used for audit and learning. If they
show that the computer selected the wrong source, the correction belongs in URL
selection, not as a patch inside classification.

## Internal Workspace

Stream-specific generated files should live under internal ignored folders:

```text
artifacts/policy_data_internal/interim/streams/<stream_id>/current/
artifacts/policy_data_internal/review/streams/<stream_id>/current/
artifacts/policy_data_internal/logs/streams/<stream_id>/current/
artifacts/policy_data_internal/catalog_sources/streams/<stream_id>/current/
artifacts/policy_data_internal/extracted_text/streams/<stream_id>/current/
```

Each stream may also have a matching `archive/` folder. The user-facing
`policy_data/` folder should stay flat and should contain only leading current
outputs and short summaries.

## Production Rule

Old pilot, batch, stream-1/stream-2, and manual-audit scripts can remain as
development history until the consolidated pipeline reproduces the current
outputs. They should not be the normal production commands.

The target production shape is:

```text
course_policy.catalog_pipeline          # shared catalog URL engine
course_policy.production_streams        # stream registry and workspace map
course_policy.catalog_qc                # shared catalog quality-control gate
course_policy.policy_classification_pipeline
```

Public/private differences should be configuration and source seeds, not
separate forked pipelines.
