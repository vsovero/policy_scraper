# Data Schema

This document defines the planned tables for the policy pipeline. Field names may evolve during implementation, but the separation between source inventory, extracted evidence, AI classification, review, and final panel should remain.

## Table 1: Institution Universe

One row per institution included in the target sample.

```text
unitid
institution_name
sector
control
state
target_start_year
target_end_year
source_in_legacy_public
source_in_legacy_private
active_in_ipeds_panel
legacy_row_count
legacy_conflict_count
legacy_needs_review
notes
```

## Table 1A: Legacy Workbook Audit

One row per audited legacy workbook row. This table is generated in Phase 1 and should be used as prior evidence and review metadata in later phases.

```text
workbook
sheet_name
excel_row
unitid
institution_name
grade_averaging
grade_avg_threshold
grade_forgiveness
grade_forgive_threshold
start_year
parsed_start_year
bulletin_url
evidence_text
comments
student
page_number
parent_url
score
missing_start_year
start_year_outside_2000_2020
missing_bulletin_url
missing_evidence_text
likely_student_note
malformed_grade_averaging
malformed_grade_forgiveness
malformed_grade_avg_threshold
malformed_grade_forgive_threshold
duplicate_institution_year
conflicting_duplicate_institution_year
needs_review
review_reasons
```

For private workbook rows, `sheet_name` is important because the workbook contains overlapping main, automated, example, and training-set sheets.

## Table 1B: Legacy Evidence Links

Optional bridge table from the institution-year universe to one or more legacy audit rows.

```text
legacy_link_id
unitid
target_year
legacy_workbook
legacy_sheet_name
legacy_excel_row
legacy_source_priority
legacy_url
legacy_excerpt
legacy_policy_class
legacy_grade_averaging
legacy_grade_avg_threshold
legacy_grade_forgiveness
legacy_grade_forgive_threshold
legacy_needs_review
legacy_review_reasons
selected_as_prior_evidence
created_at
```

This table should preserve duplicate or conflicting legacy rows rather than collapsing them prematurely. Phase 2 may produce this bridge directly or include equivalent fields in `institution_year_targets.csv`.

## Table 2: Catalog Inventory

One or more rows per institution-year candidate source.

```text
source_id
unitid
institution_name
target_year
candidate_url
archived_url
source_kind
source_domain
catalog_year_start
catalog_year_end
retrieval_status
content_type
local_source_path
text_extract_status
source_confidence
discovery_method
selected_for_use
needs_human_review
review_reason
legacy_workbook
legacy_sheet_name
legacy_excel_row
notes
created_at
updated_at
```

Recommended `discovery_method` values:

```text
legacy_workbook
institution_archive_page
url_pattern
search_engine
internet_archive
ai_assisted_discovery
manual_review
```

Recommended `retrieval_status` values:

```text
not_attempted
retrieved
dead_link
blocked
not_catalog
wrong_year
requires_review
```

## Table 3: Extracted Text

One row per saved source text extraction.

```text
text_id
source_id
unitid
target_year
local_source_path
local_text_path
extractor
extractor_version
text_length
page_count
extraction_status
error_message
created_at
```

## Table 4: Candidate Excerpts

One row per policy-relevant excerpt found in extracted text.

```text
excerpt_id
text_id
source_id
unitid
institution_name
target_year
section_title
page_number
keyword_hits
excerpt_text
excerpt_start_char
excerpt_end_char
excerpt_score
selected_for_classification
created_at
```

The excerpt text should be long enough to support classification but short enough to keep AI calls bounded.

## Table 5: AI Classification Results

One row per AI classification attempt.

```text
classification_id
excerpt_id
source_id
unitid
institution_name
target_year
model
prompt_version
schema_version
input_hash
raw_response_path
grade_averaging
grade_avg_threshold
grade_forgiveness
grade_forgive_threshold
policy_class
threshold_type
attempt_limit
credit_limit
repeat_limit_notes
same_institution_required
both_grades_on_transcript
supporting_quote
confidence
needs_human_review
review_reason
validation_status
created_at
```

Allowed `policy_class` values:

```text
grade_forgiveness
grade_averaging
neither
both_or_ambiguous
unknown
```

Allowed `threshold_type` values:

```text
explicit_letter
any
unknown
not_applicable
```

## Table 6: Human Review

One row per classification or source requiring review.

```text
review_id
unitid
institution_name
target_year
source_id
excerpt_id
classification_id
review_reason
ai_policy_class
ai_grade_averaging
ai_grade_avg_threshold
ai_grade_forgiveness
ai_grade_forgive_threshold
ai_confidence
legacy_policy_class
legacy_threshold
human_policy_class
human_grade_averaging
human_grade_avg_threshold
human_grade_forgiveness
human_grade_forgive_threshold
human_notes
reviewer
review_status
reviewed_at
```

Recommended `review_status` values:

```text
pending
resolved
needs_second_review
unresolved_missing_source
unresolved_ambiguous_policy
```

## Table 7: Final Policy Panel

Exactly one row per `unitid x year` in the analysis universe.

```text
unitid
institution_name
sector
year
policy_class
grade_averaging
grade_avg_threshold
grade_forgiveness
grade_forgive_threshold
threshold_type
gradegpa
attempt_limit
credit_limit
source_status
source_id
excerpt_id
classification_id
review_id
evidence_basis
confidence
needs_human_review
final_notes
created_at
```

Recommended `evidence_basis` values:

```text
direct_catalog_observed
multi_year_catalog_applied
carried_forward
backfilled
human_reviewed
legacy_only
missing
ambiguous
```

## Stata Compatibility

The final panel should include Stata-friendly versions of core variables:

```text
avg
gradeavg
forgive
gradeforgive
year
unitid
instnm
public
gradegpa
has_valid_policy
source_status
needs_human_review
```

The Stata import should not need to expand sparse change rows. It should merge a complete institution-year policy panel to IPEDS by `unitid year`.
