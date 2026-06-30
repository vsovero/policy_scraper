# Step 1 URL Discovery Run Contract

Created: 2026-06-23
Renamed and simplified: 2026-06-30

This is the stable contract for Step 1 URL-discovery runs. It defines how a run
must be named, what evidence it must produce, and what claims it may support.
It is not the active status register. Current decisions, current blockers, and
which batch/chunk to run next belong in:

```text
policy_scraper/artifacts/PIPELINE_OUTPUTS/CURRENT_STATUS_AND_NEXT_STEPS.md
```

Current direction: do not extend the historical `pilot_batch_*` sequence as if
it were production. The next dataset-construction unit should be
`production_chunk_001`, unless the explicit purpose is a separate clean
`benchmark_*` run.

## Stage Boundary

Step 1 finds and validates institution-year source URLs. A Step 1 run may:

```text
build a target institution-year panel
generate candidate catalog/policy URLs
retrieve and validate candidate URLs
review source evidence
assign URL-stage ready/not-ready statuses
write source-ledger rows or benchmark scores, depending on run type
```

A Step 1 run does not:

```text
extract full source text for policy classification
search text for policy language
classify grade-forgiveness or grade-threshold policies
assemble the final analysis panel
stand in for the journal replication package
```

## Naming Rule

Use the run name to state the purpose of the work.

| Name | Use For | Meaning |
|---|---|---|
| `pilot_batch_*` | Existing historical batches only | Prior process tests, development runs, and regression evidence |
| `benchmark_*` | Clean validation tests | Tests of how well the computer can recover hidden human answers without seeing them |
| `production_chunk_*` | Dataset construction chunks | Bounded source-ledger construction for the actual dataset |
| `production_release_*` | Frozen release outputs | Package-ready dataset versions and final reproducible handoffs |

Do not rename old `pilot_batch_*` folders. If a failed historical pilot becomes
input to production construction, create a new `production_chunk_*` output with
its own report, source-ledger delta, unresolved-row table, and manifest.

Recommended production layout:

```text
policy_scraper/artifacts/PIPELINE_OUTPUTS/01_url_discovery/
  production_chunks/
    production_chunk_001/
      README.md
      CHUNK_REPORT.md
      OUTPUT_urls_for_text_extraction.csv
      OUTPUT_source_ledger_delta.csv
      UNRESOLVED_ROWS.csv
      MANIFEST.json

policy_scraper/artifacts/AUDIT_TRAILS/
  url_discovery_production_chunk_001/
```

## Run Types

### Historical Pilot / Regression Evidence

Existing `pilot_batch_*` folders remain evidence of process tests and regression
runs. They can show that the command path, reporting, source review, and tests
ran on a bounded batch. They do not by themselves establish final production
coverage or publication-ready clean benchmark performance.

### Clean Benchmark

A `benchmark_*` run answers:

```text
How well can computer URL discovery recover valid human source URLs when those
answers are hidden from discovery?
```

Rules:

```text
pre-specify the target rows and hidden-answer denominator
withhold human legacy URLs from discovery inputs for scored rows
report valid-human recovery separately from prior-programmatic diagnostics
do not use old reviewed URLs to assign ready status before scoring
do not count production ledger recovery as clean benchmark success
```

The 90 percent recovery floor belongs to this lane only. It is not the standard
for production source-ledger construction.

### Production Chunk

A `production_chunk_*` run answers:

```text
Can this bounded set of institution-years be closed into a reproducible source
ledger?
```

Rules:

```text
target 100 percent ledger closure, not 90 percent hidden-answer recovery
recover every valid source possible
record unresolved/unrecoverable statuses for the rest
allow prior valid human/programmatic evidence as transparent ledger provenance
review every accepted source under the same source-review standard
never hide row-specific answers in scraper conditionals
separate general code/rule fixes from row-specific ledger decisions
```

Codex may assist coding, debugging, and source-review triage during production
construction. That assistance belongs in the AI-use disclosure and audit trail.
The required replication package must not require a live Codex step to repair
code or rediscover sources.

### First Production Chunk

`production_chunk_001` should be the first bounded dataset-construction unit.
It should not be described as a pilot or as clean no-legacy validation.

Purpose:

```text
close a bounded set of institution-years into the source ledger
preserve all accepted sources with provenance
preserve all unresolved/unrecoverable rows with explicit reasons
create the Step 1 handoff for later text extraction
```

Allowed evidence:

```text
active human legacy URLs, if valid and reviewed
valid prior programmatic discoveries, if reviewed under the current standard
new programmatic candidates generated by the current URL process
manual/Codex-assisted source review, recorded as review evidence
API-assisted candidates, only when live or cached API evidence is documented
```

Done criteria:

```text
the target panel is frozen before review
every target row has ready or not-ready status
every accepted URL has row-level and institution-panel source-review evidence
every unresolved row has a stop reason
the source-ledger delta records provenance for each accepted source
the text-extraction handoff, unresolved-row table, report, and manifest agree
clean hidden-answer recovery is reported separately if benchmark answers exist
```

## Required Inputs

Every Step 1 run must freeze and document:

```text
run_id
run_type: historical_pilot, benchmark, production_chunk, or production_release
target institution-year panel
institution metadata and homepages
year range and sector rules
sample flags when relevant, including GF and threshold samples
available source-evidence inputs
API/web-rescue mode: live, cached, off, or not eligible
code version or commit/hash when available
```

The target panel must include, at minimum:

```text
unitid
institution_name
sector
state
academic_year
target-inclusion reason
estimation-sample or panel-fill flags when relevant
```

## Required Process

A complete run must preserve evidence for:

```text
candidate URL generation
candidate retrieval and HTTP/archive status
source-family or stop-reason buckets
source-review decisions
API/web-rescue prompts, calls, cache paths, and parsed outputs when used
accepted source URLs
unresolved/unrecoverable rows
manifest/hash information for generated outputs
```

Candidate URLs are not evidence by themselves. A URL becomes ready only after it
passes retrieval, institution identity, source-type, year-coverage, and
source-review checks.

## Required URL Output Fields

`OUTPUT_urls_for_text_extraction.csv` or the equivalent Step 1 handoff must
include:

```text
run_id
run_type
unitid
institution_name
sector
state
academic_year
url_status
ready_for_text_extraction
url_for_text_extraction
url_source_bucket
candidate_url
retrieval_status
http_status
review_decision
review_reason
source_review_file
unresolved_reason, when not ready
```

For production chunks, also write a source-ledger delta with:

```text
unitid
academic_year
accepted_source_url
source_type
source_year_coverage
provenance_type: prior_human, prior_programmatic, new_programmatic, manual_review, api_assisted
review_file
review_decision
evidence_hash_or_cache_path when available
```

## Required Front-Door Outputs

For benchmark and historical pilot/regression runs:

```text
OUTPUT_urls_for_text_extraction.csv
HOW_CREATED.md
BENCHMARKS_AND_ATTRITION.md
REQUIREMENTS_STATUS.csv
MANIFEST.json or equivalent manifest/hash record
```

For production chunks:

```text
README.md
CHUNK_REPORT.md
OUTPUT_urls_for_text_extraction.csv
OUTPUT_source_ledger_delta.csv
UNRESOLVED_ROWS.csv
REQUIREMENTS_STATUS.csv
MANIFEST.json
```

## Required Reporting

Every run report must state:

```text
target denominator
number of institutions and institution-years
ready/recovered rows
not-ready rows by stop reason
unreviewed candidate count, which should be zero at handoff
API/web-rescue mode and failures
source-review coverage
whether the run supports benchmark, production-chunk, or only historical claims
```

For production monitoring, report recovery and expansion separately:

```text
recovery lane: rows in the current GF/threshold samples
panel-fill lane: rows outside current samples that could expand coverage
```

## Done Criteria

A Step 1 run is complete only when:

```text
all target rows have a ready or explicit not-ready status
all accepted URLs have source-review evidence
all unresolved rows have explicit stop reasons
all API/model use or failure is documented when applicable
outputs, reports, requirements files, and manifests agree
row-specific answers are not hidden in code
```

A clean benchmark is complete only after hidden-answer scoring is regenerated
from the frozen run outputs.

A production chunk is complete only after every target row is represented in
the source-ledger delta or unresolved-row table.

## Related Standards

```text
policy_scraper/docs/replication_standards/requirements_checklist.md
policy_scraper/docs/replication_standards/url_source_review_standard.md
policy_scraper/docs/replication_standards/supporting_rules/benchmark_protocol.md
policy_scraper/docs/replication_standards/supporting_rules/api_setup.md
policy_scraper/artifacts/PIPELINE_OUTPUTS/CURRENT_STATUS_AND_NEXT_STEPS.md
```
