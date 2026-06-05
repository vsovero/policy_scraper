# Course Repetition Policy Pipeline

This folder contains the planned Python-based pipeline for rebuilding the course repetition policy database for U.S. 4-year institutions from 2000 through 2020.

The goal is to move from a sparse, change-row spreadsheet workflow to a reproducible evidence-first workflow:

1. identify undergraduate catalogs and bulletins by institution-year;
2. save source files or snapshots;
3. extract catalog text;
4. locate course repetition policy excerpts;
5. classify policies with structured AI assistance;
6. validate and route uncertain cases to human review;
7. export a complete institution-year panel for downstream Stata analysis.

Existing raw workbooks and Stata/R analysis files should remain untouched unless a later task explicitly says otherwise. This pipeline should create new outputs under `../data_policy_pipeline/`.

## Documentation

- [Project Plan](docs/01_project_plan.md): overall workflow, scope, and operating principles.
- [Data Protocol](docs/02_data_protocol.md): coding definitions, source rules, and review rules.
- [Data Schema](docs/03_data_schema.md): planned tables and fields.
- [AI Workflow](docs/04_ai_workflow.md): where AI calls enter the workflow and how they should be logged.
- [Implementation Roadmap](docs/05_implementation_roadmap.md): staged build plan from audit to full-scale run.
- [API Setup](docs/06_api_setup.md): local API configuration, dry-run/live modes, and secret handling.

## Current Status

Phase 1, the legacy workbook audit, has been implemented and run. Generated audit outputs are stored under `../data_policy_pipeline/`:

- `interim/legacy_public_audit.csv`;
- `interim/legacy_private_audit.csv`;
- `review/legacy_audit_review.xlsx`;
- `logs/legacy_workbook_audit_summary.md`.

The audit confirms that the legacy workbooks are useful historical evidence but should not be treated as final panel data. Phase 2 should build the institution-year universe from the IPEDS/Stata analysis panel and merge legacy rows only as prior evidence with audit-quality flags attached.

## Proposed Folder Roles

```text
policy_pipeline/
  README.md
  pyproject.toml
  config/              # pipeline settings, institution lists, API config templates
  docs/                # project planning and data protocol docs
  prompts/             # prompt templates and JSON schemas for AI calls
  src/course_policy/   # Python package code
  tests/               # unit tests and fixture-based checks

data_policy_pipeline/
  raw_legacy/          # optional copies of legacy workbooks, never edited in place
  catalog_sources/     # downloaded PDFs, HTML snapshots, Wayback captures
  extracted_text/      # extracted text from catalog sources
  interim/             # inventories, candidate URLs, candidate excerpts
  review/              # human review workbooks and adjudication outputs
  processed/           # final cleaned panels and Stata-ready exports
  logs/                # run logs, API call metadata, validation reports
```

## Design Principle

The final policy data should be generated from code and traceable to evidence. Excel should be used for review and delivery, not as the only archive of raw source material.
