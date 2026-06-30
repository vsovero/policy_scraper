# Replication Standards

Created: 2026-06-23

This folder is the single documentation standard for the course repetition
policy data build. The top level is intentionally small.

## Current Operating Mode

The active work is now the transition from Step 1 URL-discovery process
hardening to bounded production source-ledger construction. Existing
`pilot_batch_*` folders remain historical evidence; new dataset-construction
work should not be called a pilot.

Use this naming rule:

| Name | Use For | Meaning |
|---|---|---|
| `pilot_batch_*` | Existing historical batches only | Prior process tests, development runs, and regression evidence |
| `benchmark_*` | Clean validation tests | Tests of how well the computer can recover hidden human answers without seeing them |
| `production_chunk_*` | Dataset construction chunks | Bounded source-ledger construction for the actual dataset |
| `production_release_*` | Frozen release outputs | Package-ready dataset versions and final reproducible handoffs |

The completed pilot/development work tests whether the URL-stage workflow is
reproducible, auditable, validation-backed, and honest about unresolved rows. It
is not a final production URL-stage claim and should not be treated as the
journal replication package.

Current strategy: clean no-legacy URL discovery is a benchmark diagnostic, not
the only route to a reproducible final dataset. Codex may assist coding,
debugging, and source-review triage during construction, but the required
replication package should rebuild from a frozen source ledger and archived
artifacts without a live Codex repair step. Accepted row-specific findings
belong in the ledger as transparent data/provenance, not as hidden scraper
conditionals.

For production construction, the URL-stage target is complete source-ledger
closure, not the 90 percent clean benchmark. Prior valid human and programmatic
discoveries may be visible while Codex helps write general code/rule repairs;
they must be reviewed and recorded as ledger provenance, not counted as clean
out-of-sample benchmark successes.

The next dataset-construction unit should be `production_chunk_001`. It should
start from a frozen bounded institution-year target panel and end only when all
target rows have either an accepted reviewed source URL or an explicit
unresolved/unrecoverable status. Additional clean no-legacy batches should be
run only when the purpose is benchmarking, not ordinary production construction.

## Open First

```text
codex_goals/step_1_url_discovery_run_contract.md
requirements_checklist.md
url_source_review_standard.md
```

The Step 1 URL-discovery run contract defines stable naming, input, output,
review, benchmark, and production-chunk requirements. Current status and next
actions live in `artifacts/PIPELINE_OUTPUTS/CURRENT_STATUS_AND_NEXT_STEPS.md`.
A pipeline stage is not publication-ready unless the relevant checklist items
have concrete evidence, not just placeholder hooks.

## Top-Level Files

Only these files should sit directly in this folder:

```text
README.md
requirements_checklist.md
url_source_review_standard.md
```

Everything else should be inside one of the existing subfolders.

## Supporting Rules

```text
supporting_rules/data_protocol.md
supporting_rules/benchmark_protocol.md
supporting_rules/policy_classification_rules.md
supporting_rules/api_setup.md
supporting_rules/sources_reviewed.md
supporting_rules/journal_replication_submission_draft_current.md
```

These files explain or document the concepts used by the checklist. They do not
override the checklist.

## Other Files

```text
old_design_notes/
```

This folder includes superseded cleanup proposals, old planning notes, and
not-current release drafts. The current folder names are `PIPELINE_OUTPUTS`,
`AUDIT_TRAILS`, and `OLD_OUTPUT_ARCHIVES`.

The old design notes are historical context only. They are not the active
process map.

## Scope

The checklist applies to policy-source retrieval, catalog text extraction,
LLM/API-assisted policy classification, human adjudication, and final release of
the policy dataset and replication package.

The central standard is that an independent researcher should be able to
reconstruct the policy variables from documented source evidence, code,
cached model outputs where applicable, and human review logs.

For AI-assisted work, disclose the development assistance separately from the
reproducible runtime. Archive prompts, model outputs, and validation records
when they produce pipeline artifacts, but do not make a live AI assistant a
required dependency for rebuilding the published dataset.
