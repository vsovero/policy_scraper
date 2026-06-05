# Phase 3 Discovery Protocol

This protocol translates the strict 5-institution pilot into a scalable first-pass workflow. The goal is not to exhaust every possible source for each institution. The goal is to produce a consistent, auditable first-pass catalog coverage table and a clear escalation queue.

## Operating Principle

Phase 3 should answer three questions for each institution-year:

1. Is there a source-root candidate that can cover this year?
2. Can that source be retrieved and verified with explicit catalog-year evidence?
3. If not, what is the next controlled escalation bucket?

Institution-specific cases are useful only when they become reusable rules.

## Replication Checklist

Use this checklist for each institution in the next pilot batch.

1. Identify one preferred source root.

   Record the best coherent catalog collection/archive before collecting individual year URLs. Prefer official institution-wide catalog archives, institutional repositories, or state/library digital archive collections. Treat legacy workbook links as prior evidence or fallback leads unless they clearly represent the same coherent root.

2. Record fallback roots separately.

   If another root is useful, assign it a role such as `legacy_prior`, `fallback_official`, `fallback_external_archive`, or `rejected_wrong_scope`. Do not silently mix roots.

3. Extract catalog candidates from the preferred root.

   For each candidate, record title, URL, source-root URL, catalog-year start, catalog-year end, evidence type, and whether the source appears institution-wide and undergraduate.

4. Apply academic-year expansion.

   Expand ranges as `[start, end)`: `2013-2014` covers AY 2013, and `2004-2006` covers AY 2004 and AY 2005.

5. Retrieve easy candidates first.

   Attempt direct retrieval and simple recovery only. Save retrieved source bodies. Do not conduct open-ended web search during the first pass.

6. Verify strict catalog-year evidence.

   Count coverage only when catalog-year evidence appears in source title/heading, metadata, extracted text, OCR, or visual review. URL or filename year patterns alone are review leads.

7. Assign every institution-year a first-pass status.

   Each year should be covered or assigned a stop/review status such as OCR needed, archive lower/upper bound reached, wrong-scope lead rejected, fresh discovery needed, or fallback deferred.

8. Move unresolved years to an escalation bucket.

   Escalate by type, not by institution story: OCR/visual review, source-root review, archive-bound revisit, wrong-scope exception review, API-assisted discovery, or manual review.

9. Stop the first pass.

   The first pass is complete when every institution-year is either strict-covered or assigned a defensible status. Do not chase every gap before moving to the next institution.

## Reverse-Engineered Current Process

The current strict-pilot outputs were created while the protocol was still being developed. They should be understood as a reverse-engineered workflow rather than a clean single-root first pass.

The current process is:

1. Start with legacy links as prior evidence.
2. Retrieve and count legacy links only when strict catalog-year evidence is confirmed.
3. Identify archive or repository roots to fill uncovered years.
4. Retrieve easy archive/repository candidates.
5. Preserve mixed-root roles rather than hiding them:
   - `legacy_prior_confirmed`;
   - `preferred_root_archive_fill`;
   - `preferred_root_repository_fill`;
   - `fallback_official_gap_fill`;
   - `ocr_or_visual_review`;
   - `wrong_scope_or_fresh_discovery`;
   - `archive_bound_stop`.
6. Route unresolved cases by escalation bucket.

This reverse-engineered process is recorded in:

- `data_policy_pipeline/interim/catalog_current_process_source_trace_strict_pilot.csv`;
- `data_policy_pipeline/interim/catalog_current_process_year_trace_strict_pilot.csv`;
- `data_policy_pipeline/logs/phase3_current_process_trace_summary.md`.

These outputs explain how the current strict-pilot files were produced. They should be used to audit the current results and to decide which parts of the workflow should be generalized for the next pilot batch.

## Source-Root Strategy

For each institution, first identify one preferred source root whenever possible. A source root is the collection or archive from which catalog candidates are discovered, such as:

- an official catalog archive page;
- an institutional repository collection;
- a state or library digital archive collection;
- an institution-hosted legacy catalog URL pattern;
- Internet Archive snapshots of an official source.

Avoid silently mixing source roots during the first pass. If multiple roots are used, record their role:

- `preferred_first_pass`: main source root for the institution;
- `legacy_prior`: legacy workbook lead used as prior evidence or corroboration;
- `fallback_official`: official alternate source used only when the preferred root has a gap;
- `fallback_external_archive`: non-institutional archive, such as a state digital archive or Internet Archive;
- `rejected_wrong_scope`: school-, program-, or handbook-specific source outside the target scope.

## First-Pass Source-Root Priority

Use this order unless an institution-specific note documents a reason to change it:

1. Coherent official institution-wide undergraduate catalog archive.
2. Coherent institution repository or library collection for institution-wide catalogs.
3. Coherent state/library digital archive collection with institution catalog records.
4. Legacy workbook URLs, treated as prior evidence and fallback leads.
5. Internet Archive recovery of official URLs.
6. AI-assisted discovery for remaining hard cases.

The selected root should be stable enough that a reviewer can understand why years were covered or not covered.

## First-Pass Stop Rules

Stop first-pass discovery for an institution-year when one of these statuses applies:

- `strict_source_found`: retrieved source has explicit catalog-year evidence covering the year.
- `source_found_needs_ocr_or_visual_review`: candidate source appears to cover the year but cannot be verified with text extraction.
- `official_archive_lower_bound_reached`: preferred source root starts after the target year.
- `official_archive_upper_bound_reached`: preferred source root ends before the target year.
- `wrong_scope_lead_rejected`: available lead is school-, program-, or handbook-specific and no exception has been approved.
- `fresh_discovery_needed`: no acceptable root has been found in the easy first pass.
- `fallback_deferred`: a deeper fallback is plausible but intentionally deferred.

Do not use open-ended web searching to resolve every gap during the first pass.

## Escalation Buckets

After first pass, unresolved institution-years should be routed by bucket:

- `ocr_or_visual_review`: scanned or image-only sources need OCR or page-image confirmation.
- `source_root_review`: multiple plausible roots exist and a coherent hierarchy must be chosen.
- `archive_bound_revisit`: source root has a lower or upper bound; deeper search may be revisited later.
- `wrong_scope_exception_review`: institution structure may require a documented exception to institution-wide source rules.
- `api_assisted_discovery`: deterministic source-root discovery failed and AI/search assistance is warranted.
- `manual_review`: source or policy evidence is too ambiguous for automated handling.

## Catalog-Year Evidence Rule

Strict coverage requires explicit catalog-year evidence from one of:

- source title or heading;
- page metadata;
- extracted PDF/document text;
- OCR or visual review record.

URL or filename year patterns alone are not strict evidence.

## Academic-Year Rule

Catalog ranges are expanded as `[start, end)`.

Examples:

- `2013-2014` covers AY 2013.
- `2004-2006` covers AY 2004 and AY 2005.

## Pilot Lessons Converted To Rules

### SFSU

Reusable lesson: A clean official archive page can support direct first-pass retrieval across the panel.

Rule: Use visible archive link text and retrieved page title/heading as strict catalog-year evidence.

### SIU Carbondale

Reusable lesson: Institutional repository records can work well, but repository archive bounds should become first-pass stop rules.

Rule: If the repository collection yields explicit catalog candidates only through a visible range, mark later missing years as upper-bound archive stops rather than chasing them immediately.

### ABAC

Reusable lesson: A coherent archive can exist but still fail strict automated validation because PDFs are scanned.

Rule: Route scanned/image-only catalogs to OCR or visual review, not deeper discovery.

### UNC Charlotte

Reusable lesson: Mixing legacy links, Provost pages, and DigitalNC makes coverage hard to explain.

Rule: Choose a preferred first-pass root before expanding further. DigitalNC appears to be a coherent candidate root; legacy and Provost links should be treated as fallback or corroborating sources unless the root plan says otherwise.

### OHSU

Reusable lesson: School-specific leads can look plausible but be wrong-scope.

Rule: Reject school-specific sources by default and route the institution to fresh discovery or exception review.

## Required First-Pass Outputs

Each first-pass run should produce:

- source-root plan by institution;
- candidate source inventory;
- retrieval attempts;
- source-level retrieval and evidence status;
- institution-year coverage status;
- escalation queue;
- review workbook tabs for source roots, candidates, retrieval evidence, and institution-year statuses.

## Scaling Gate

Do not expand from the strict 5-institution pilot to a larger pilot until:

- source-root roles are recorded;
- stop statuses are stable and documented;
- scanned/OCR cases are routed without being counted as strict coverage;
- wrong-scope sources are rejected consistently;
- review workbook outputs make it easy to inspect why each year is covered, deferred, or unresolved.
