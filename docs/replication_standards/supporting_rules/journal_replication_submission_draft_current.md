# Current Draft: Journal Replication Submission Text

Created: 2026-06-23

This is the current reusable draft for the journal replication package, data
appendix, or data editor response. It intentionally excludes pilot-specific
language. Pilot outputs are tests of this reporting structure; they are not
described here as production results.

## Data And Code Availability Statement

The analysis uses institution-year policy data constructed from IPEDS-derived
institution panels, legacy hand-collected policy source information, and
publicly available college catalog or academic-policy sources. The replication
package documents source discovery and validation at the institution-year
level. Each retained source row identifies the institution, year, source URL,
source provenance, URL validation status, and whether the row is ready for
downstream text extraction.

The URL-discovery stage produces the source handoff for later text retrieval.
Rows without accepted URLs remain visible with stop reasons rather than being
silently dropped. Later stages retrieve source text, extract policy-relevant
language, classify course-repetition policies, adjudicate ambiguous cases, and
construct the final analysis panel.

Where full catalog source text cannot be redistributed because of copyright or
website terms, the release package will provide source URLs, retrieval metadata,
hashes or stable identifiers where available, extracted policy excerpts where
permitted, and code or instructions to regenerate source text from public URLs.

## Stage Boundary

The URL-discovery stage is limited to source discovery and URL validation. It
does not extract full source text for policy classification, search catalog text
for course-repetition language, classify grade forgiveness or grade averaging,
or call policy-classification APIs.

The URL-stage handoff file should contain one row per target institution-year.
Each row should either have an accepted source URL ready for text extraction or
an explicit stop reason explaining why the row did not advance.

## URL-Discovery Methods

The URL-discovery process starts from an IPEDS-derived target panel. The target
panel is restricted to the institution-years used for the policy build and
records the institution identifier, institution name, sector, year, graduation
outcome availability, and target-panel inclusion rule.

The source-discovery process follows these steps:

1. Build the target institution-year panel.
2. Preserve active human legacy source evidence where available.
3. Search official institution homepages, registrar pages, catalog roots,
   catalog archives, and bounded source-family URL patterns for candidate
   catalog or academic-policy sources.
4. Apply deterministic recovery layers for unresolved rows, including
   inferred-year URL search, archive expansion, and Wayback/CDX search where
   applicable.
5. Use API-assisted URL rescue only as candidate generation when configured and
   documented.
6. Replay previously validated external evidence, such as Wayback/CDX evidence,
   only when the cached source, validation basis, current-run replay decision,
   and replay log are documented.
7. Review candidate URLs before they enter the source handoff.
8. Report row-level attrition, loss buckets, and benchmark recovery rates.

Candidate URLs are not treated as evidence until they pass URL/source review.

## URL/Source Review Standard

Programmatic discovery produces candidates only. A programmatic URL becomes
production evidence only after row-level source evidence and institution-level
panel review. HTTP status, filename patterns, cached labels, or LLM suggestions
alone are not sufficient.

For each accepted URL, the release package should document:

```text
source_opened
retrieval_status
http_status or equivalent retrieval result
final_url_after_redirect where applicable
institution_match_confirmed
campus_or_unitid_match_confirmed where relevant
source_scope_confirmed
source_type_confirmed
year_coverage_confirmed
archive_child_links_checked where relevant
gap_fill_search_completed
panel_consistency_confirmed
review_decision
review_reason
reviewed_by
reviewed_at
```

Rows without accepted URLs should remain in the handoff file or stop-log file
with explicit reasons.

## AI/API Use In URL Discovery

AI tools have two different roles and should not be described as one thing.

First, Codex or similar tools may be used during research development as coding,
debugging, and source-review triage assistants. This use should be disclosed in
the AI-use statement. It is not a required runtime step in the replication
package.

Second, API/model calls may be used inside controlled pipeline stages as
candidate-generation, extraction, classification, or review aids. AI output is
not source evidence by itself. A URL suggested or surfaced by an AI-assisted
process can enter the production handoff only after ordinary retrieval,
institution, source-type, year-coverage, and panel-consistency review.

Accepted Codex- or API-assisted source findings should not be hidden in scraper
code. General patterns should become general code or documented source-family
rules. Row-specific accepted source decisions should be recorded as transparent
rows in the source ledger with evidence and provenance.

For every API/model-assisted URL-discovery task that creates candidate data, the
replication package should preserve:

```text
task type
provider and model ID
run date/time
prompt version
schema version
input hash
raw response path
parsed response path
output hash
validation status
error message if applicable
candidate URL rows derived from the response
```

If an accepted row depends on an AI-assisted candidate, the front-door handoff
or linked audit table should identify the relevant AI call ID and response
paths. This prevents the final source panel from becoming detached from the
model-assisted search record.

The required replication path should not require live Codex, live code fixing,
or live source rediscovery. It should rebuild the final dataset from the frozen
source ledger, archived/cached source artifacts, code, and cached model outputs
where applicable. Optional live API/Codex demos may be included as diagnostics
or construction-process examples, but they are not required to reproduce the
published dataset.

## Required URL-Stage Outputs

The final URL-stage release should include:

```text
target_panel.csv
frozen source ledger
candidate URL ledger
URL validation audit
source-review log
validated external-evidence replay log where applicable
reviewed URL handoff panel
URL stop log or visible not-ready rows
stage rates
loss buckets
benchmark truth file where applicable
benchmark validation scores where applicable
input manifest
output manifest
run summary or README
```

The file manifest should record row counts, column counts, file sizes,
modification times, and SHA-256 hashes for release files and key inputs.

## URL-Stage Results To Report

The production URL-stage report should report the following fields after the
full production run is frozen:

```text
target institution-years
target institutions
target years
public/private target counts
rows with active human legacy URL evidence
rows added by reviewed programmatic discovery
rows ready for text extraction
rows stopped before text extraction
ready rate by sector
ready rate by source type
institution counts with 2+, 5+, 8+, 10+, 12+, and complete URL panels
stage-specific attrition
rolling attrition from the target denominator
loss buckets
benchmark recovery rates against held-out legacy URLs
```

The production report should not present pilot-batch rates as production rates.
Pilot results may be cited only as process tests or internal diagnostics.

## Benchmarking

Where human legacy source evidence exists, it should be used in two distinct
ways:

1. Active human legacy URLs may be preserved as production evidence.
2. Withheld human legacy URLs may be used after discovery as a benchmark answer
   key.

The benchmark report should state the denominator, the recovery definition, the
sector-specific recovery rates, and the major failure categories. The internal
URL-stage target is at least 90 percent recovery on valid held-out human legacy
URL rows, reported by sector and combined sample, unless a later design note
pre-specifies a different threshold.

## Downstream Stages

Text retrieval starts only after the URL handoff is frozen. The text-readiness
stage should report source retrieval, readable-text extraction, and text-ready
rates. It should not run policy-classification APIs.

Policy classification starts only after source text or policy excerpts are
available. Any LLM/API-assisted policy classification should be fully
documented with prompt, schema, model, parameters, raw output, parsed output,
supporting quote, review reason, parse status, and human-review flag.

Final analysis data should be built only after policy classification and human
adjudication are complete. Treatment timing and threshold changes should remain
traceable to underlying institution-year source evidence.

## Current Completion Status

As of this draft, the current work is still in URL-discovery pilot and
validation mode. The reusable reporting structure above can carry forward into
production, but production counts should be filled in only after the full
URL-stage handoff is frozen and its manifest, benchmark, and source-review
checks pass.
