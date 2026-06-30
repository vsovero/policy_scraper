# URL Source Review Standard

Created: 2026-06-23

This defines "manual review" for URL search validation in the policy data
pipeline. The term is easy to weaken, so this file uses the highest-scrutiny
standard from the human-replication work.

## Short Definition

For URL discovery, manual review means:

```text
An evidence-backed source validation and institution-panel review that happens
before a programmatic URL can become production evidence.
```

It does not mean the user personally inspected every row.

It also does not mean:

```text
a script returned 200 OK
a URL string looked like a catalog
a cached pipeline label said valid
an LLM suggested the URL
one year worked, so nearby years are assumed
```

## Highest-Standard Rule

Programmatic discovery produces candidates only. A candidate URL becomes
production evidence only after the source and the institution panel have been
reviewed to the same standard used in the human-replication work.

The unit of review is both:

```text
row-level source evidence
institution-level panel consistency
```

Accepting isolated rows without checking the institution's source family, year
coverage, and missing-year pattern is not sufficient.

## Required Review Questions

For each institution with any promising programmatic URL candidate, the review
must answer:

1. Is this the correct institution?
2. Is this the correct campus/unitid, including name changes, branch campuses,
   mergers, or system schools?
3. Is this an acceptable source type for undergraduate course-repetition policy
   evidence?
4. Does the source cover the credited academic year or multi-year catalog span?
5. Is the source institution-wide or otherwise valid for undergraduate policy,
   rather than graduate-only, professional-school-only, department-only,
   financial-aid/SAP-only, or another narrow policy page?
6. If the URL is an archive/landing page, were the relevant child links checked?
7. If one valid year exists, were nearby and missing years actively searched
   using the official archive, official catalog domain, source-family URL
   patterns, parent directories, or other bounded source search?
8. Does the set of accepted URLs make sense as an institution panel?
9. Are remaining missing years explained rather than silently dropped?

## Operational Decision Protocol

Codex-assisted or human source review must follow this order. A row cannot be
accepted until all applicable checks pass and the institution-level panel check
is complete. Codex may help inspect evidence, bucket failures, or propose
general fixes, but final acceptance is the recorded source evidence and review
decision, not the fact that an AI system suggested the URL.

### Step A. Open And Identify The Source

Record the opened URL, final redirected URL, retrieval status, HTTP status,
content type where available, page title, archive URL where applicable, and the
candidate source file.

Reject or stop before acceptance if:

- the URL is dead or cannot be retrieved after bounded retry;
- the page is only a search-results page, login wall, metadata-only holding
  record, or generic homepage;
- the source cannot be inspected well enough to verify institution, source
  type, and year coverage.

Bounded HEAD-only or catalog-platform 202 evidence is allowed only for narrow
retrieval failures where a catalog-platform HTML page is live but full body
retrieval fails or returns a platform-specific interim status. The row still
must have current-run evidence for the correct institution, catalog/source type,
target year or catalog span, and institution-panel consistency. This fallback
cannot be used to accept a generic homepage, a search page, or a PDF URL that
redirects away from the target-year source.

### Step B. Confirm Institution And Campus

Accept only if the source belongs to the target institution and target unitid or
if a third-party host is clearly serving that institution's official catalog.

Official third-party hosts can include catalog-platform domains, document hosts,
state university system catalog hosts, or archive repositories when the page
itself or the parent archive clearly identifies the target institution.

Reject if:

- the page belongs to a similarly named but different institution;
- the page is for a branch campus, professional school, medical center, or
  system office that is not the target unitid;
- a merger/name-change relationship is plausible but not documented.

### Step C. Confirm Acceptable Source Type

Acceptable URL-stage sources include:

- official undergraduate catalog or bulletin PDF;
- official undergraduate catalog or bulletin HTML page;
- official catalog archive page with checked child links;
- official registrar or academic policy page that contains course-repetition
  policy evidence;
- archived copies of the above when the original source and target year are
  identifiable.

Reject if the source is graduate-only, professional-school-only,
department/program-only, financial-aid/SAP-only, admissions-only,
course-schedule-only, news/blog content, or a library holding record without a
retrievable source.

### Step D. Confirm Year Or Catalog Span

Accept only if the source supports the credited academic year.

Valid year support includes:

- explicit catalog year on the page or file;
- a multi-year catalog whose start/end span covers the target year;
- an archive page with checked child links that directly identify the target
  catalog year;
- a Wayback/CDX snapshot where the original URL, timestamp, page title, or page
  content identifies the target catalog year.

Do not accept a row from filename/year pattern alone unless the source is opened
and the institution/source/year checks are also satisfied.

### Step E. Archive And Landing-Page Rules

Catalog archive or landing pages are candidates, not production year evidence,
unless the relevant child link for the target year is opened or the archive page
itself directly exposes enough source/year evidence for the target row.

For archive pages, record whether child links were checked. If a landing page is
useful but does not establish a target-year source, stop the row with a
needs-more-search style reason rather than accepting it.

### Step F. Panel Consistency Review

After row-level checks, inspect the institution as a panel.

Accept the panel only if accepted URLs form a plausible source family or any
source-family changes are documented. Missing years must have visible stop
reasons. A single verified year cannot be used to infer all nearby years without
active search of official archives, catalog roots, source-family URL patterns,
parent directories, or bounded archive sources.

### Step G. Decision Coding

Accepted rows must use one of these decision meanings:

- `accept_exact_year_catalog`
- `accept_multi_year_catalog`
- `accept_official_policy_source`
- `accept_cached_external_evidence_replay`

Rejected or stopped rows must use one of these decision meanings:

- `reject_wrong_institution`
- `reject_wrong_campus_or_unitid`
- `reject_wrong_year`
- `reject_not_catalog_or_policy_source`
- `reject_graduate_only`
- `reject_professional_school_only`
- `reject_department_or_program_only`
- `reject_financial_aid_or_sap_only`
- `reject_dead_or_unretrievable`
- `reject_metadata_only_archive`
- `reject_low_confidence`
- `needs_more_source_search`
- `manual_panel_search_no_verified_source`
- `not_reviewed_no_target_year_candidate`

Current pilot files may use compact implementation labels such as
`accept_current_run_source_review`; those labels are valid only when the row also
records the underlying evidence fields required by this standard.

## Evidence Required For Accepted Rows

Every accepted programmatic URL row must have evidence for:

```text
source_opened
institution_match_confirmed
source_scope_confirmed
year_coverage_confirmed
gap_fill_search_completed
panel_consistency_confirmed
review_decision
review_reason
reviewed_by
reviewed_at
```

The evidence can be compact, but it must be explicit enough that a later
researcher can understand why the URL entered production.

## Valid Decision Meanings

Use plain-language decisions such as:

```text
accept_exact_year_catalog
accept_multi_year_catalog
accept_official_policy_source
reject_wrong_institution
reject_wrong_campus_or_unitid
reject_wrong_year
reject_not_catalog_or_policy_source
reject_graduate_only
reject_professional_school_only
reject_department_or_program_only
reject_financial_aid_or_sap_only
reject_dead_or_unretrievable
reject_metadata_only_archive
reject_low_confidence
needs_more_source_search
manual_panel_search_no_verified_source
```

The exact coded values can vary by script, but the decision meaning must be
this specific.

## What Does Not Count

These are not sufficient for production acceptance:

- HTTP success alone.
- Redirect success alone.
- A filename containing a year.
- A page title containing "catalog" without source/year/scope confirmation.
- A broad library record claiming holdings but not exposing a retrievable
  source.
- A catalog archive page without checked child links or documented usable year
  coverage.
- An inferred URL pattern that has not been opened and checked.
- A single accepted year used to infer all missing years without active panel
  search.
- Cached API/LLM output without source verification.

## Panel-Level Review

Panel-level review means checking the institution as a series, not only as
individual rows.

The reviewer must look for:

- consistent source family or justified source-family changes;
- unexplained gaps;
- suspicious domain changes;
- branch-campus or system-campus mismatches;
- graduate/professional/program-only substitutions;
- archive pages that list holdings but do not expose source text;
- multi-year catalogs assigned to the correct covered years;
- impossible historical rows, such as an institution/unitid that did not exist
  in the target year.

## Fail Conditions

The URL-stage output is invalid if:

- a programmatic URL enters production without an accepted review record;
- an institution has programmatic production URLs but no institution-level
  panel review;
- human legacy evidence is overwritten by programmatic evidence;
- missing years are silently dropped instead of assigned a status/reason;
- the output claims to pass while any required review evidence fields are blank
  for accepted programmatic rows.

## Goal Wording

Use this wording in future Codex goals:

```text
Manual URL/source review must follow
policy_scraper/docs/replication_standards/url_source_review_standard.md.

Programmatic URLs are candidates only. They may enter the production URL
handoff only after row-level source evidence and institution-level panel review
are complete. If that evidence is missing, stop and report the gap rather than
producing a final handoff.
```
