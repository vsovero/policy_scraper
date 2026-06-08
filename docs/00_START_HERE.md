# Start Here

This is the navigation page for the course repetition policy pipeline.

## Current Phase

Phase 3: catalog discovery pilot and controlled expansion.

The current review sample contains 45 public institutions and 945 institution-year rows for AY 2000-2020.

## What To Open First

Open this workbook first:

`data_policy_pipeline/review/phase3_catalog_discovery_review_packet.xlsx`

Use the tabs in this order:

1. `START_HERE`: workbook navigation and current audit counts.
2. `institution_summary`: one row per institution.
3. `nonpass_explanations`: plain-language explanations for partial panels, OCR queues, and accepted stop reasons.
4. `year_panel_review`: compact year-by-year URL panel.
5. `source_roots`: selected source root and source-finding note by institution.

The `raw_full_mockup` tab is preserved for auditability, but it is not the main review interface.

## Current Gate

The review packet should not be treated as ready if any institution has `needs_pipeline_fix`.

Current acceptable non-pass statuses are:

- `accepted_dead_end_or_archive_bound`: a documented archive bound, verified source gap, or scope stop.
- `needs_ocr_or_visual_review`: catalog candidates exist, but OCR or visual confirmation is still queued.

## Main Reference Docs

- `docs/05_implementation_roadmap.md`: phase plan.
- `docs/07_high_level_issues_log.md`: running high-level methodological issues.
- `docs/08_phase3_discovery_protocol.md`: current Phase 3 catalog-discovery rules.

## Output Folder Map

- `data_policy_pipeline/review/`: user-facing review workbooks and review CSVs.
- `data_policy_pipeline/logs/`: run summaries and audit summaries.
- `data_policy_pipeline/interim/`: detailed pipeline tables, mostly for code/debugging.
- `data_policy_pipeline/catalog_sources/`: downloaded or saved source bodies.
- `data_policy_pipeline/extracted_text/`: extracted catalog text.

## Historical Outputs

Older strict-pilot and batch workbooks/logs are retained for provenance, but the current Phase 3 review entry point is:

`data_policy_pipeline/review/phase3_catalog_discovery_review_packet.xlsx`
