# Start Here

This is the navigation page for the course repetition policy pipeline.

## Current Phase

Phase 3 catalog URL production has been consolidated into a single harmonized
catalog URL database. Public/private stream outputs, fresh-discovery batches,
LLM traces, and legacy/student comparison files are retained internally for
audit and reproducibility, but they are not the day-to-day review entry point.

## What To Open First

Open the generated output navigation file first:

`policy_data/START_HERE.md`

Then open the current catalog URL database workbook:

`policy_data/catalog_url_database.xlsx`

Companion files:

1. `catalog_url_database_summary.md`: short summary of the run.
2. `catalog_url_database.csv`: CSV version of the harmonized database.
3. `catalog_url_database_institution_status.csv`: institution-level status.
4. `catalog_url_database_scope_qc.csv`: source-scope and QC flags.

## Current Production Boundary

The current front-facing production object is the catalog URL database. Policy
classification files are diagnostic/audit work unless and until they are
regenerated from the selected best URL database as a separate production step.

Catalog URL work is now organized by named production streams:

1. `public_legacy_url`;
2. `private_human_legacy_url`;
3. `public_fresh_discovery`;
4. `private_new_legacy_url` (review-gated workspace, not final evidence);
5. `private_fresh_discovery`;
6. `combined_catalog_url_database`.

Use `docs/11_production_streams.md` for the plain-language stream map.
Use `docs/12_benchmark_protocol.md` for the benchmark rules that separate
legacy-assisted rebuilds from clean no-legacy validation.

The current catalog URL production command is:

```bash
PYTHONPATH=src python -m course_policy.private_fresh_discovery
PYTHONPATH=src python -m course_policy.catalog_pipeline
```

The first command refreshes the private no-human-legacy fresh-discovery stream.
The second command stages the current stream files and regenerates
`policy_data/catalog_url_database.*`.

If no private fresh-discovery refresh is needed, rerun only:

```bash
PYTHONPATH=src python -m course_policy.catalog_pipeline
```

The current extraction-queue command is:

```bash
PYTHONPATH=src python -m course_policy.policy_extraction_queue
```

It writes internal queue files under `policy_scraper/artifacts/policy_data_internal/interim/` and excludes review-gated sources by default.

Legacy/student URL and excerpt comparisons are useful for learning, auditing,
and detecting missed sources. They should not directly overwrite production
classification; if a legacy comparison reveals a better source, that finding
should be routed back to catalog URL selection and then extraction/classification
should be rerun from the selected best source.

Human legacy URLs can be used to rebuild the existing dataset and to diagnose
retrieval/extraction/classification when a valid URL is supplied. They cannot
count as success for the clean no-legacy benchmark. A no-legacy benchmark row
must withhold human legacy URLs and legacy-derived source hints.

## Folder Map

The user-facing policy-data folder is intentionally flat:

- `policy_data/`: leading review files and short run summaries only.

Background outputs needed for reproducibility are stored in the code folder but ignored by Git:

- `policy_scraper/artifacts/policy_data_internal/audits/legacy_benchmark_current/`
- `policy_scraper/artifacts/policy_data_internal/archive/front_folder_cleanup_2026_06_10/`
- `policy_scraper/artifacts/policy_data_internal/interim/`
- `policy_scraper/artifacts/policy_data_internal/review/`
- `policy_scraper/artifacts/policy_data_internal/logs/`
- `policy_scraper/artifacts/policy_data_internal/catalog_sources/`
- `policy_scraper/artifacts/policy_data_internal/extracted_text/`

The archive manifest is stored under:

`policy_scraper/artifacts/policy_data_internal/logs/archive/`

## Versioning Rule

Stable `current/` filenames are intentionally not versioned. GitHub versions the code. The data/process audit trail is preserved by run manifests, checksums, source paths, run ids, and logs.

Use version-like names only for archived run folders or explicit historical comparisons, not for the user-facing current files.

## Main Reference Docs

- `docs/05_implementation_roadmap.md`: phase plan.
- `docs/07_high_level_issues_log.md`: running high-level methodological issues.
- `docs/08_phase3_discovery_protocol.md`: current Phase 3 catalog-discovery rules.
- `docs/09_public_private_stream_design.md`: public/private stream architecture.
- `docs/10_policy_classification_rules.md`: working rules for policy excerpt classification.
- `docs/11_production_streams.md`: named production streams and the reserved private new-legacy URL stream.
- `docs/12_benchmark_protocol.md`: rebuild versus clean benchmark rules.
