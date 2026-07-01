# Replication Standards

Created: 2026-06-23

Authority: BINDING ROUTER. Read this file first when reviewing replication
standards. It defines which files are binding, supporting, draft, or historical.

This folder is the single documentation standard for the course repetition
policy data build. The top level is intentionally small.

## Codex Review Hierarchy

When scanning this folder, first look for the `Authority:` label near the top of
each Markdown file. If a file has no authority label and is not listed below,
treat it as non-binding context until this README says otherwise.

Authority order:

| Authority | Meaning | Files |
|---|---|---|
| Binding router | Tells Codex what to read and how to resolve conflicts | `README.md` |
| Binding checklist | Journal-stage pass/fail requirements | `requirements_checklist.md` |
| Binding run contract | Stable requirements for a named production or benchmark process | `codex_goals/step_1_url_discovery_run_contract.md` |
| Binding prompt template | Required stream prompt structure and guard commands | `codex_goals/stream_prompt_templates.md` |
| Binding stage rule | Detailed rules for one stage or claim type | `url_source_review_standard.md`, `supporting_rules/data_protocol.md`, `supporting_rules/benchmark_protocol.md`, `supporting_rules/policy_classification_rules.md`, `supporting_rules/api_setup.md` |
| Citation/example support | External standards and examples; useful for rationale but not a project checklist | `supporting_rules/sources_reviewed.md` |
| Submission prose | Draft wording for a paper, appendix, or data-editor response; not a standard | `supporting_rules/journal_replication_submission_draft_current.md` |
| Run evidence/status | Current outputs, process reviews, audits, and reports; evidence only | `artifacts/PIPELINE_OUTPUTS/**`, `artifacts/AUDIT_TRAILS/**` |
| Historical notes | Superseded plans and old design notes; not current | `old_design_notes/**` |

Conflict rule: higher-authority files override lower-authority files. A lower
file can add detail only when it does not weaken the checklist, stage rule, or
run contract. If two binding files conflict, report the conflict and use the
stricter requirement until the standard is edited.

## What Codex Should Review

For any standards review, start with:

```text
README.md
requirements_checklist.md
```

Then add only the relevant binding stage files:

| Review task | Add these files |
|---|---|
| URL discovery or production chunks | `codex_goals/step_1_url_discovery_run_contract.md`, `url_source_review_standard.md`, `supporting_rules/benchmark_protocol.md` |
| Clean benchmark claims | `supporting_rules/benchmark_protocol.md` |
| Source data and panel definitions | `supporting_rules/data_protocol.md` |
| LLM/API setup or AI-use runtime claims | `supporting_rules/api_setup.md`, `supporting_rules/policy_classification_rules.md` when classification is involved |
| Policy text classification | `supporting_rules/policy_classification_rules.md` |
| Journal release readiness | Final-stage section of `requirements_checklist.md`, plus every binding stage file touched by the release |
| Citations or example packages | `supporting_rules/sources_reviewed.md` only after the binding files above |

Do not use process reviews, generated reports, old design notes, citation files,
or submission drafts to override binding standards. They may show what happened
or why the standard was chosen, but they are not the standard.

## Standards Folder Organization Rules

Use this folder only for durable requirements. Do not put run status, current
blockers, generated reports, or mini-batch notes here.

Before adding a new Markdown file in this folder:

1. Check whether the note belongs in an existing binding file.
2. If it is a stable requirement, add it to the relevant checklist, run
   contract, or stage rule.
3. If it is current status or a run result, put it under
   `artifacts/PIPELINE_OUTPUTS/` or `artifacts/PILOTS/` instead.
4. If a new standards file is truly needed, give it an `Authority:` label and
   list it in the hierarchy table above in the same edit.

Do not duplicate the same standard across several files. Put the rule in the
highest-authority owner file and point to it from lower-authority files.

## Pass-Claim Authority Rule

Generated reports and manifests are evidence, not authority. A generated
`CHUNK_REPORT.md`, `REQUIREMENTS_STATUS.csv`, `run_config`, release manifest, or
benchmark table cannot by itself establish that a run passed, is production
ready, is ready to scale, or is journal standard.

For any front-door pass claim:

1. The relevant binding checklist, run contract, or stage rule must define the
   criterion.
2. A human process review must cite the controlling criterion, observed value,
   and pass/fail result.
3. The current-status or stage README may summarize `pass` only if the process
   review also says `pass` for the same claim.

If generated artifacts and the process review disagree, the process review
controls the front-door summary until the binding standard or review is updated.
If no process review exists, the run is `under review`, not `pass`.

For the active Step 1 URL-stage successful-test-batch goal, `under review`,
`partial pass`, `fail`, and `not tested` are status labels only. They are not
completion states. Codex should continue fixing, rerunning, packaging, and
reviewing until the process review explicitly passes Gate 1 and Gate 2, unless
there is a precise external blocker.

This rule is enforced by:

```text
../.venv/bin/python -m pytest tests/test_front_door_status_claim_gate.py
```

## Codex Stream Write-Scope Rule

Use a four-scope workflow:

```text
project-management task definition
-> integration source/test edits
-> testing output
-> process review
-> project-management current status
```

Project-management streams define the work slice and publish front-door status.
Integration streams edit only the approved source/test slice. Testing or drill
streams may edit only run-local generated output. Review streams may edit only
the relevant process-review file.

| Stream scope | May edit | Must not edit |
|---|---|---|
| `testing` | Run-local generated output such as `CHUNK_REPORT.md`, `RUN_REPORT.md`, `TEST_REPORT.md`, `REQUIREMENTS_STATUS.csv`, manifests, ledgers, and caches | Process reviews, standards, current status, front-door README/START_HERE docs |
| `review` | The relevant process-review file and its protected-doc manifest hash | Test output, current status, front-door docs, standards |
| `integration` | Step 1 production-runner/release-packager source files and matching tests only | Current status, process reviews, standards docs, generated output, unrelated discovery/classification/public/private modules |
| `project_management` | `CURRENT_STATUS_AND_NEXT_STEPS.md`, front-door README/START_HERE docs, standards when approved, and their manifest hashes | Test output and process-review files |

Allowed testing-stream output locations include:

```text
artifacts/PILOTS/**/CHUNK_REPORT.md
artifacts/PILOTS/**/RUN_REPORT.md
artifacts/PILOTS/**/TEST_REPORT.md
artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_chunks/*/CHUNK_REPORT.md
artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/*/RELEASE_REPORT.md
```

Protected documents include:

```text
docs/**
README.md
artifacts/PIPELINE_OUTPUTS/CURRENT_STATUS_AND_NEXT_STEPS.md
artifacts/PIPELINE_OUTPUTS/START_HERE.md
artifacts/PIPELINE_OUTPUTS/**/README.md
artifacts/PIPELINE_OUTPUTS/**/process_reviews/**
artifacts/AUDIT_TRAILS/START_HERE.md
artifacts/PILOTS/**/README.md
```

If a test run discovers that a protected planning or review document needs to
change, the testing stream should write that need into its run-local report and
stop changing documents there. A review stream may decide and record the review
outcome in the process-review file. The project-management stream updates
`CURRENT_STATUS_AND_NEXT_STEPS.md` or other front-door status docs only after the
review file supports that status claim or the user directly instructs it.
If an integration stream discovers that its allowed source/test slice is too
narrow, it should stop and report the extra files needed; project management can
then expand the allowed integration slice explicitly.

Each stream should create a baseline at the start of its work and check against
that same baseline before reporting done. This makes the guard usable in a dirty
shared worktree because it checks only what changed after the stream started.
Use the copy/paste prompts in
`codex_goals/stream_prompt_templates.md`; do not hand-write stream prompts from
memory.

```text
../.venv/bin/python -m course_policy.codex_scope_guard init --scope testing --baseline /private/tmp/codex_scope_testing.json
../.venv/bin/python -m course_policy.codex_scope_guard check --scope testing --baseline /private/tmp/codex_scope_testing.json

../.venv/bin/python -m course_policy.codex_scope_guard init --scope review --baseline /private/tmp/codex_scope_review.json
../.venv/bin/python -m course_policy.codex_scope_guard check --scope review --baseline /private/tmp/codex_scope_review.json

../.venv/bin/python -m course_policy.codex_scope_guard init --scope integration --baseline /private/tmp/codex_scope_integration.json
../.venv/bin/python -m course_policy.codex_scope_guard check --scope integration --baseline /private/tmp/codex_scope_integration.json

../.venv/bin/python -m course_policy.codex_scope_guard init --scope project_management --baseline /private/tmp/codex_scope_project_management.json
../.venv/bin/python -m course_policy.codex_scope_guard check --scope project_management --baseline /private/tmp/codex_scope_project_management.json
```

The pytest file `tests/test_codex_testing_write_scope.py` remains a static
contract test and an optional global scope check. The baseline guard above is
the operational gate for active streams.

Because `artifacts/` is ignored by Git, persistent artifact docs that function
as front-door status or process-review records are additionally locked in:

```text
docs/replication_standards/protected_artifact_docs_manifest.csv
```

Testing and integration streams must not update those files or the manifest. A
review stream may update only process-review rows in the manifest. A
project-management stream may update only front-door/status rows in the manifest.
This keeps the review file as the judgment record and the current-status file as
the published summary.

## Historical Inventory Runtime Gate

Historical URL discovery inventory is planning and benchmark-preservation
evidence only. It cannot be a runtime input to the clean Step 1 production
runner or a source-ledger promotion mechanism.

The hard coding gate is:

```text
../.venv/bin/python -m pytest tests/test_step1_production_runner.py::test_clean_runner_rejects_historical_inventory_runtime_inputs
```

If production-runner code or production inputs allow
`historical_inventory/`, `url_discovery_historical_inventory/`,
`normalized_historical_url_attempts`, `normalized_historical_discoveries`, or
`institution_priority_buckets` as runtime inputs, the gate must fail.

## Historical Case Precheck Gate

The historical inventory must be used as operational memory before Step 1 coding
or test-batch completion claims. That memory must enter the clean production
runner only as `historical_case_precheck.csv`, a URL-free control file with one
completed row per target institution.

The precheck may contain priority buckets, evidence-class counts, source-family
or host summaries, and failure-pattern summaries. It must not contain direct
URLs, row-specific old URLs, historical-inventory paths, or source-ledger
promotion claims.

The hard coding gate is:

```text
../.venv/bin/python -m pytest tests/test_step1_production_runner.py::test_clean_runner_requires_historical_case_precheck tests/test_step1_production_runner.py::test_clean_runner_fails_incomplete_historical_case_precheck tests/test_step1_production_runner.py::test_clean_runner_rejects_direct_urls_in_historical_case_precheck
```

The full Step 1 runner test file also verifies that a valid precheck appears in
`REQUIREMENTS_STATUS.csv` as `historical_case_precheck_complete`.

## Current Operating Mode

The active work is now the transition from Step 1 URL-discovery process
hardening to bounded production source-ledger construction. Existing
`pilot_batch_*` folders remain historical evidence under
`policy_scraper/artifacts/PILOTS/url_discovery/`; new dataset-construction work
should not be called a pilot.

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
closure, not the 90 percent clean benchmark. Prior valid human discoveries may
be reviewed and recorded as ledger provenance. Prior programmatic discoveries
may be visible as diagnostics or rule-development aids, but they cannot promote a
row into the source ledger unless the current run recovers and reviews the
source, or the row is explicitly invalidated.

Historical pilot outputs may inform code development, source-family rules,
regression tests, and benchmark design. They are not valid normal runtime inputs
for future `production_chunk_*` or `production_release_*` builds. A clean Step 1
production runner should start from explicit production inputs such as a target
panel, candidate URL ledger, source-review log, source-evidence cache/manifest,
and optional benchmark key. If a run requires `pilot_batch_*` outputs as input,
label it transitional or migration evidence, not the clean production runner.
In plain terms: extract and reorganize the good reusable code into a clean
production pipeline. Do not keep layering wrappers over old runs, and do not
make old run folders part of the production runtime contract.

The next dataset-construction goal is to replace the pilot-derived production
chunk builder with that clean Step 1 production runner. Additional clean
no-legacy batches should be run only when the purpose is benchmarking, not
ordinary production construction.

## Open First

```text
README.md
requirements_checklist.md
codex_goals/step_1_url_discovery_run_contract.md
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
