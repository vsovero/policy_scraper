# Replication Standards

Created: 2026-06-23

This folder is the single documentation standard for the course repetition
policy data build. The top level is intentionally small.

## Current Operating Mode

The active work is a Step 1 URL-discovery pilot.

The pilot is meant to test whether the URL-stage workflow is reproducible,
auditable, validation-backed, and honest about unresolved rows. It is not a
final production URL-stage claim and should not be treated as the journal
replication package.

Current strategy: clean no-legacy URL discovery is a benchmark diagnostic, not
the only route to a reproducible final dataset. Codex may assist coding,
debugging, and source-review triage during construction, but the required
replication package should rebuild from a frozen source ledger and archived
artifacts without a live Codex repair step. Accepted row-specific findings
belong in the ledger as transparent data/provenance, not as hidden scraper
conditionals.

## Open First

```text
codex_goals/step_1_pilot_goal_template.md
requirements_checklist.md
url_source_review_standard.md
```

The Step 1 pilot goal is the current runnable Codex goal. The checklist and
source-review standard define the gates the pilot is testing against. A pipeline
stage is not publication-ready unless the relevant checklist items have concrete
evidence, not just placeholder hooks.

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
