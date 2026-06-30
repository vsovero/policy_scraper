# Step 1 Pilot Goal Template: URL Discovery And Validation

Created: 2026-06-23
Revised: 2026-06-30

Use this template for the Step 1 pilot of the policy pipeline:

```text
01_url_discovery
```

Step 1 means URL discovery and URL validation only. It produces the
institution-year URL panel that will later feed text extraction. It does not
retrieve full source text for classification, search policy language, classify
grade forgiveness or grade averaging, or call policy-classification APIs.

## Current Operating Mode

Use the capped small-batch development/regression process while production is
being built and tested.

Option B means:

```text
one full batch panel
one row per target institution-year in the batch
ready rows and not-ready rows kept together
clear status/reason fields for every row
only ready rows may feed Step 2
```

This is process validation and production hardening, not a final production
coverage claim. The batches may validate that the workflow is reproducible,
auditable, and honest about unresolved rows. They may not claim autonomous
URL-discovery readiness unless the benchmark requirements pass for the intended
production scope.

For final reproducibility, the durable output is a frozen source ledger plus
archived/cached source artifacts. Codex may assist code development, debugging,
and source-review triage, but the required replication package should not rely
on a live Codex step to fix code or rediscover sources.

The current operating loop is:

```text
run a pre-specified development batch of about 20 institutions
if it fails, freeze it as a regression case
make only general process fixes, not batch-specific cheating
rerun accumulated regression cases after fixes
move to the next development batch only after documenting the prior result
stop when all accumulated regressions pass and three consecutive new
  development batches pass the hidden valid-human benchmark
stop earlier if the 10-batch development cap is reached or a hard blocker
  prevents the production path from running
```

The current blocker rule is explicit: if the configured API/web rescue layer is
eligible but all calls fail because of quota/configuration, stop, document the
API failure, and do not treat later batches as clean production-path evidence
until the API problem is resolved and the failed batch is rerun.

This must be a production-path pilot, not a replay of old final outputs. The
pilot must rerun the Step 1 status-assignment path for the selected batch from
fixed inputs, candidate evidence, cached retrieval/validation evidence, and
documented source-review evidence. Prior final or reviewed URL panels may be
used only for benchmarking, comparison, or to locate underlying audit evidence.
They may not directly determine `url_status`, `ready_for_text_extraction`, or
`url_for_text_extraction`.

## Ready-To-Use Pilot Goal

```text
Build and run a journal-standard small-batch Step 1 URL discovery and validation
development/regression loop for the unified policy database.

Use the replication standards in:

- policy_scraper/docs/replication_standards/requirements_checklist.md
- policy_scraper/docs/replication_standards/url_source_review_standard.md

Each batch must start from a pre-specified institution-year target panel drawn
from the 2002-2016 IPEDS target panel with graduation outcomes. Human legacy
URL evidence may be preserved for final unified-dataset construction and for
hidden-answer scoring, but it must not be used as the discovery input for rows
being used to evaluate fresh computer discovery. For rows without usable human
URL evidence, and for hidden-answer test rows where the computer must recover
the URL from scratch, the pilot must run the production URL-discovery code for
the selected batch and generate fresh root-candidate, archive-page,
year-candidate, and year-panel artifacts during the run. Treat every
programmatic, inferred, archive-expanded, LLM-assisted, or manually suggested
URL as a candidate until it passes source review.

Do not stop after first-pass discovery. If target years are not recovered, run
the existing reproducible recovery layers on the same fixed batch before
reporting the pilot:

```text
deterministic inferred-year URL recovery
archive expansion from clean-discovered roots
Wayback/CDX recovery where applicable
configured API/web rescue if deterministic layers do not recover the target years
current-run source review for recovered candidates
```

API/web rescue is part of the validated URL-discovery process when
deterministic discovery leaves unresolved target years. To control cost, first
reuse cached API outputs with saved prompt/raw/parsed provenance when they match
the current batch and prompt version; make new live API calls only for remaining
eligible gaps under the configured request cap. A deterministic-only run is not
a full production-path pilot unless it documents that no API/web rescue was
eligible or needed.

Evidence-backed source review is also part of the validated process. A scripted
deterministic quality gate is not a substitute for source review under
`url_source_review_standard.md`. Codex may assist this review, but Codex output
is not source evidence. Programmatic, inferred, archive-expanded, Wayback/CDX,
or API-assisted URLs can be ready only after the source-review log records
row-level evidence and institution-level panel review.

Do not hard-code Codex-assisted row findings into scraper logic. General
patterns discovered during repair should become general code or documented
source-family rules. Row-specific accepted source decisions should become
source-ledger records with evidence and provenance.

The pilot is not complete merely because the first-pass command ran. It is
complete only when each target institution-year is either ready after
current-run source review or explicitly stopped with the recovery layer where it
failed.

This corrected pilot must not build its main output by copying or filtering an
old final reviewed URL panel, old candidate audit, old URL-validation audit, or
old manual review log. It must run the production URL-discovery path for the
selected batch, then build row status from artifacts generated in that same run
plus human legacy evidence and any source review completed during the pilot. If
old outputs are cited, they must be clearly labeled as comparison or benchmark
files only.

Use Option B output status:

- human_legacy_ready
- human_panel_fill_ready
- programmatic_ready
- candidate_needs_source_review
- candidate_rejected
- no_candidate_found
- not_in_batch_or_excluded

Only rows with a ready status may be marked ready for text extraction. Rows with
unreviewed candidates, rejected candidates, or no candidates must remain in the
same output file with explicit reasons.

Create or update these files together from the same run metadata:

policy_scraper/artifacts/PIPELINE_OUTPUTS/01_url_discovery/<pilot_batch_id>/
  OUTPUT_urls_for_text_extraction.csv
  REQUIREMENTS_STATUS.csv
  HOW_CREATED.md
  BENCHMARKS_AND_ATTRITION.md

Store or cite detailed audit evidence under:

policy_scraper/artifacts/AUDIT_TRAILS/

The markdown files must be generated evidence summaries, not placeholders. If
the batch is incomplete, they must say incomplete and identify the exact failed
checks or remaining review gaps.

Do not run text extraction.
Do not search source text for policy language.
Do not classify policy.
Do not call OpenAI/API classification.
Do not promote the batch to final production unless all production checks pass.
Stop only when the capped development/regression stopping rule is met, the
10-batch cap is reached, or a hard production-path blocker is documented. Do
not promote the batch to production unless all production checks pass.
```

## Journal-Standard Purpose

The Step 1 pilot must prove four things:

```text
replicable
  A researcher can identify the fixed inputs, script, command, run timestamp,
  cached/live-web rules, and output files. Previously validated cached
  external-retrieval evidence must not disappear merely because a fresh live
  refresh fails.

auditable
  Every URL decision has visible provenance, review evidence, and a reason.

validated
  Success rates, benchmark denominators, loss buckets, and strict-review checks
  are reported from the same run.

attrition-transparent
  Every row that does not reach text-extraction readiness has an exact stage
  where it stopped and a plain-English reason. Stage-specific and rolling
  attrition are reported so losses cannot hide inside aggregate coverage.

honest about status
  Unresolved rows stay visible and are not described as ready production data.
```

## Stage Boundary

This goal includes:

```text
batch target definition
candidate URL inventory
candidate generation provenance
human legacy URL preservation
candidate retrieval/validation status
source-review gate enforcement
institution-level panel review where a programmatic URL is marked ready
explicit status/reason for every batch row
stage-specific attrition accounting
hidden legacy benchmark scoring where the batch contains benchmark rows
loss buckets
requirements-status audit
generated reproducibility markdown
URL handoff status for text extraction
```

This goal excludes:

```text
full source text extraction for policy classification
OCR for classification
course-repetition policy text search
policy excerpt extraction
policy classification
OpenAI/API classification calls
final analysis data construction
final journal repository deposit
```

If any excluded task appears necessary, stop and report that it belongs to a
later stage.

## Required Standards

This goal must satisfy the relevant URL-stage requirements in:

```text
policy_scraper/docs/replication_standards/requirements_checklist.md
```

It must also satisfy the URL/source review standard in:

```text
policy_scraper/docs/replication_standards/url_source_review_standard.md
```

The core rule is:

```text
candidate URL != ready URL
```

A programmatic URL is ready evidence only if it has documented row-level source
evidence and institution-level panel review when applicable.

## Hard Fail Conditions

The corrected pilot fails the journal-standard reproducibility check if any of
these are true:

```text
deterministic discovery leaves unresolved target years and API/web rescue is
  neither run nor replayed from matching cached API provenance

ready API-assisted rows lack url_discovery_ai_call_id, prompt path, raw response
  path, parsed response path, or triage file

programmatic ready rows are accepted by a deterministic quality gate instead of
  evidence-backed source review under url_source_review_standard.md

source_review_log.csv lacks row-level source evidence or institution-level
  panel review fields for accepted programmatic rows

old final/reviewed URL panels determine current ready/not-ready status instead
  of being used only after the run for benchmark comparison

stage-specific attrition, rolling attrition, loss buckets, and old-audit
  recovery against the same target rows are not reported

old-audit recovery for active ready rows is below the pre-specified floor
  without a row-level exception review

configured API/web rescue is eligible but fails because of quota/configuration;
  in that case, document the failed API layer and pause clean-batch claims until
  the failed batch can be rerun
```

## Batch Definition Requirement

Before running the pilot, define the batch in `HOW_CREATED.md` and in the
output itself.

The batch definition must include:

```text
batch_id
batch_selection_rule
unitids included
years included
sector scope
whether rows are human legacy, programmatic candidates, or mixed
why this batch is useful for testing the process
whether the batch can support a hidden-legacy benchmark
```

Examples of acceptable pilot batches:

```text
high-value multi-year candidate institutions
institutions with both human legacy rows and programmatic gaps
held-out human legacy benchmark rows
mixed public/private institutions selected before review
```

The batch may not be retroactively redefined to make results look better.

## Input Rules

Allowed inputs for assigning Step 1 status:

```text
raw or derived target-panel files
human legacy source evidence files
candidate ledgers generated by the current pilot production run
URL-retrieval or URL-validation evidence generated by the current pilot production run
documented source-review logs created or updated during the current pilot
manual/Codex review evidence for candidate URLs created or updated during the current pilot
hidden-legacy benchmark truth or scoring files
```

Not allowed as direct inputs for assigning Step 1 status:

```text
prior final reviewed URL panels
prior final best-URL panels
prior Step 2 handoff files that already selected production_best_url
old user-facing final output files
any output whose main job was to decide final ready/not-ready status
old candidate audit files as substitutes for running discovery
old URL-validation audit files as substitutes for running retrieval/validation
old source-review logs as substitutes for current pilot review
```

Those old final outputs may still be used for:

```text
benchmark comparison
debugging differences from earlier attempts
finding the underlying candidate, validation, or review evidence
checking whether the corrected production path reproduces earlier decisions
```

When any old final output is used this way, `HOW_CREATED.md` must say exactly
which file was used, for what purpose, and why it did not determine the current
row-level status.

The production pilot must report the exact discovery command that was run. For
the current clean no-legacy discovery standard, the command must invoke the
production discovery entry point, for example:

```bash
PYTHONPATH=src python -m course_policy.clean_no_legacy_benchmark --sector <sector> --run-discovery --limit <N> --reset-discovery
```

Using only `url_candidate_audit.csv`, `url_validation_audit.csv`, or
`manual_url_review_log.csv` from a previous run is a replay, not a production
pilot.

## Main Output

The required main output is:

```text
policy_scraper/artifacts/PIPELINE_OUTPUTS/01_url_discovery/<pilot_batch_id>/OUTPUT_urls_for_text_extraction.csv
```

This file is both:

```text
the user-facing Step 1 inspection file
the candidate handoff file for Step 2 text extraction
```

Only rows marked ready may feed Step 2.

### Unit Of Observation

The main output must have:

```text
one row per target institution-year in the batch
```

No batch row may disappear silently.

### Required Status Fields

Use clear names. The exact column names may vary only if the meaning is equally
plain.

```text
step1_batch_id
unitid
institution_name
sector
state
academic_year
in_step1_batch
target_panel_status
target_panel_reason
url_status
url_status_reason
ready_for_text_extraction
stop_before_text_extraction
stop_reason
attrition_stage
attrition_reason
attrition_stage_order
stage_specific_denominator
stage_specific_pass
rolling_pass
url_for_text_extraction
url_source_bucket
production_url_source
source_type
source_year_start
source_year_end
source_year_coverage_note
```

Recommended `url_status` values:

```text
human_legacy_ready
human_panel_fill_ready
programmatic_ready
candidate_needs_source_review
candidate_rejected
no_candidate_found
not_in_batch_or_excluded
```

### Required Provenance Fields

```text
human_legacy_url_available
human_legacy_url_used
human_legacy_url
human_legacy_source_file
programmatic_candidate_available
candidate_url
candidate_generation_method
candidate_source_type
candidate_source_file
candidate_rank
candidate_created_at
candidate_is_clean_no_legacy
candidate_is_llm_or_claude
candidate_prompt_or_run_id
```

If LLM/AI-assisted URL discovery or rescue is used, the row or audit trail must
identify the model/tool, prompt/task, input file, output file, run date, cached
artifact, and review status. The LLM output is never source evidence.

### Required Review Fields

For every ready programmatic URL:

```text
source_opened
retrieval_status
http_status
final_url_after_redirect
content_type
retrieval_checked_at
institution_match_confirmed
campus_or_unitid_match_confirmed
source_scope_confirmed
source_type_confirmed
year_coverage_confirmed
archive_child_links_checked
gap_fill_search_completed
panel_consistency_confirmed
review_decision
review_reason
reviewed_by
reviewed_at
source_evidence_note
missing_year_reason
```

For rejected or not-ready rows, the output must include:

```text
review_decision
review_reason
stop_reason
next_required_action
```

## Source-Review Gate

Programmatic candidates are only candidates. They may become ready only after
review answers the questions in `url_source_review_standard.md`:

```text
correct institution
correct campus/unitid
acceptable source type
target year or multi-year span support
undergraduate/institution-wide scope or documented exception
archive child links checked when relevant
nearby/missing years actively searched
accepted URLs make sense as an institution panel
remaining missing years explained
```

Acceptance cannot be based only on:

```text
HTTP 200
redirect success
filename or page title
catalog-looking URL string
archive metadata without source retrieval
LLM/Claude suggestion
cached label from an earlier script
one valid year used to infer nearby years without active panel search
```

If live source access is unavailable, do not newly accept unreviewed
programmatic URLs. Mark them `candidate_needs_source_review` or an equivalent
not-ready status.

## Required User-Facing Files

The Step 1 pilot must create these four files together:

```text
policy_scraper/artifacts/PIPELINE_OUTPUTS/01_url_discovery/<pilot_batch_id>/OUTPUT_urls_for_text_extraction.csv
policy_scraper/artifacts/PIPELINE_OUTPUTS/01_url_discovery/<pilot_batch_id>/REQUIREMENTS_STATUS.csv
policy_scraper/artifacts/PIPELINE_OUTPUTS/01_url_discovery/<pilot_batch_id>/HOW_CREATED.md
policy_scraper/artifacts/PIPELINE_OUTPUTS/01_url_discovery/<pilot_batch_id>/BENCHMARKS_AND_ATTRITION.md
```

Do not create a pile of public-facing support files in this folder.

Detailed candidate ledgers, review logs, validation audits, cached retrievals,
and manifests belong under:

```text
policy_scraper/artifacts/AUDIT_TRAILS/
```

The user-facing markdown files must cite the exact audit-trail paths they use.

## REQUIREMENTS_STATUS.csv

This file converts the replication checklist from placeholders into evidence.

Required columns:

```text
requirement_id
pipeline_stage
requirement
acceptance_criterion
status
evidence_file
evidence_column_or_check
gap_if_incomplete
last_checked_at
```

Allowed `status` values:

```text
pass
fail
incomplete
not_applicable_for_batch
```

For a small batch, it is acceptable for some full-production requirements to be
`not_applicable_for_batch`, but the reason must be explicit.

At minimum, Step 1 must report status for:

```text
target panel defined
denominator stated
excluded rows visible
candidate URLs logged before review
candidate-generation methods separated
LLM/AI candidate provenance logged or explicitly absent
LLM/Claude suggestions treated only as candidates
accepted URLs resolve or have documented retrieval evidence
accepted URLs match institution/campus/unitid
accepted URLs have source type
accepted URLs support target year
weak URLs rejected with visible reasons
one row per batch institution-year
source hierarchy preserved
no policy classification in URL stage
no-URL/not-ready rows kept visible
hidden legacy benchmark reported where applicable
URL recovery rates reported where applicable
benchmark failures/loss buckets reported
handoff readiness stated
file manifest or input hashes recorded
```

## HOW_CREATED.md

This file must be generated from the run metadata, not written as a loose
narrative after the fact.

It must document:

```text
status of this batch: pass, fail, or incomplete
the exact output files created
batch_id and batch selection rule
unit of observation
target panel definition
input paths used
input row counts and hashes where feasible
script path and command used
the production discovery command that generated current-run candidates
run timestamp
whether live web was used
whether cached artifacts were used
whether live external retrieval failures occurred and how cached validated
evidence was replayed or blocked
whether old final/reviewed outputs were excluded from status assignment
whether LLM/API was used and for what purpose
whether policy-classification API calls were absent
candidate-generation methods
merge/status assignment logic
source hierarchy
how human legacy URLs were preserved
how programmatic candidates were reviewed
how institution-panel review was applied
how no-candidate/rejected/not-ready rows were assigned reasons
output schema in plain English
audit-trail locations
known limitations
```

It must explicitly state what was not done:

```text
no text extraction for policy classification
no policy text search
no policy classification
no OpenAI/API classification calls
no final production promotion unless checks pass
```

## BENCHMARKS_AND_ATTRITION.md

This file must be generated from the same run and validation outputs.

It must document:

```text
status of this batch: pass, fail, or incomplete
benchmark standard
benchmark denominator and numerator
whether the benchmark applies to this batch
public/private/combined rates where meaningful
stage-specific success rates
rolling success rates where meaningful
target batch row count
rows with human legacy ready URL
rows with programmatic ready URL
rows with candidate needing review
rows rejected
rows with no candidate
rows ready for text extraction
rows stopped before text extraction
loss buckets
attrition table from target batch to ready-for-text-extraction rows
stage-specific numerator, denominator, and rate at each URL-stage gate
rolling numerator, denominator, and rate after each gate
exact count of rows lost at each gate
plain-English reason distribution for rows lost at each gate
strict-review pass/fail checks
unresolved source-review gaps
comparison to old LLM/Claude/fresh named-pool benchmark if included
publication caveats
```

At minimum, the attrition table must include these gates, using
`not_applicable_for_batch` only when the batch truly cannot test the gate:

```text
target_batch_rows
human_legacy_url_available
programmatic_candidate_available
candidate_retrieved_or_resolvable
candidate_correct_institution_or_campus
candidate_correct_source_type
candidate_correct_year_or_span
source_review_completed
panel_review_completed
ready_for_text_extraction
```

The report must separate:

```text
stage-specific rate
  Of rows eligible for this exact gate, how many passed?

rolling rate
  Of original target batch rows, how many remain ready/eligible after this gate?
```

Losses must never be reported only as a final missing count.

For a small batch, do not overclaim the 90% benchmark. Use this wording unless a
large enough pre-specified benchmark sample is included:

```text
This batch validates the Step 1 workflow and evidence structure. It does not by
itself establish final production discovery coverage or the final 90% recovery
claim.
```

## Required Validation Checks

Before reporting progress, run or document these checks:

```text
one row per batch institution-year
no duplicate batch institution-year rows
batch definition present
all batch rows retained or explicitly excluded with reason
url_status is nonmissing for every row
ready_for_text_extraction is nonmissing for every row
ready rows have url_for_text_extraction
not-ready rows have stop_reason
not-ready rows have attrition_stage and attrition_reason
candidate/rejected/no-candidate rows remain visible
human legacy URLs are preserved where used
no programmatic URL silently overwrites human legacy evidence
all ready programmatic URLs have required source-review evidence
all ready programmatic institutions have panel-level review evidence
LLM/Claude suggestions are excluded as source evidence
LLM/AI provenance is logged if used
no policy text extraction/search/classification/API classification ran
requirements status file exists and has no blank requirement statuses
HOW_CREATED.md reflects the same run as the CSV output
BENCHMARKS_AND_ATTRITION.md reflects the same run as the CSV output
row counts reconcile across ready, not-ready, rejected, and no-candidate rows
attrition counts reconcile from target batch to ready-for-text-extraction rows
```

## Stop Condition

The goal ends after exactly one pre-specified pilot batch has been run,
documented, and statused against the publication and replication standards.

Within that one batch, Codex should keep working until one of these is true:

```text
pass
  The pilot batch meets the applicable publication and replication standards,
  after first-pass discovery and all needed recovery layers have run.

fail
  A hard standard is violated and the failure is documented.

incomplete
  The batch structure is built and documented, but remaining review, recovery,
  API, retrieval, or evidence gaps prevent a pass. The unresolved standards are
  named explicitly.
```

Stopping after one batch is mandatory even if the batch passes. Do not continue
to a second batch, full production, text extraction, policy search,
classification, or API classification unless the user separately approves that
next stage.

The goal does not end merely because files exist. It ends only when the files
prove the batch status against the standards:

```text
OUTPUT_urls_for_text_extraction.csv
REQUIREMENTS_STATUS.csv
HOW_CREATED.md
BENCHMARKS_AND_ATTRITION.md
```

## Pass, Fail, And Incomplete Rules

The batch may be labeled `pass` only if:

```text
the four user-facing files exist
the batch target is fixed and documented
production discovery was actually run for the fixed batch
needed recovery layers were run or explicitly documented as not applicable
the main output has one row per batch institution-year
every row has status and reason fields
all ready programmatic URLs pass the source-review gate
all ready programmatic institutions pass panel-level review
human legacy evidence is preserved where used
not-ready rows are visible and blocked from Step 2
not-ready rows identify the recovery layer where they stopped
requirements status is complete for the batch
benchmark/attrition documentation is generated from the run
no excluded Step 1 task was run
```

The batch must be labeled `fail` if:

```text
row counts do not reconcile
ready programmatic URLs lack required evidence
programmatic URLs overwrite human legacy evidence without a conflict flag
unreviewed candidates are marked ready
LLM/Claude output is treated as source evidence
policy classification or classification API calls are run
previously validated cached URL or Wayback/CDX evidence disappears because a
fresh live refresh failed
```

The batch should be labeled `incomplete` if:

```text
the structure is valid but some candidates still need source review
the benchmark denominator is too small to support a production claim
some audit evidence exists but is not yet mapped into REQUIREMENTS_STATUS.csv
live-source checks could not be completed
```

Incomplete is acceptable during process building. It is not a final production
handoff.

## Final Response Required From Codex

When the goal is finished or paused, Codex must report:

```text
what Step 1 files were created or updated
where they are
whether the batch status is pass, fail, or incomplete
whether any row is ready for text extraction
whether the source-review gate passed for ready programmatic rows
whether human legacy evidence was preserved
whether LLM/AI was used and how it was documented
whether hidden legacy validation was possible for this batch
main row counts by status
loss buckets
failed or incomplete requirements
what was deliberately not done
```

Do not summarize Step 1 as successful unless the pass rules above are met.
