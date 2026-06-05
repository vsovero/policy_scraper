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

   Record the best coherent source before collecting individual year URLs. Prefer official institution-wide catalog archives, institutional repositories, or state/library digital archive collections. If the course repetition rule is published on an official institution-wide academic policy page, that policy page can be treated as a policy evidence root and catalogs are not required for that rule. Treat legacy workbook links as prior evidence or fallback leads unless they clearly represent the same coherent root.

2. Record fallback roots separately.

   If another root is useful, assign it a role such as `legacy_prior`, `fallback_official`, `fallback_external_archive`, or `rejected_wrong_scope`. Do not silently mix roots.

3. Extract source candidates from the preferred root.

   For each catalog candidate, record title, URL, source-root URL, catalog-year start, catalog-year end, evidence type, and whether the source appears institution-wide and undergraduate. For each policy-page candidate, record the policy title, URL, source-root URL, policy scope, retrieval status, visible/retrieved evidence text, and any available revision or archive-date evidence.

4. Apply academic-year expansion.

   Expand ranges as `[start, end)`: `2013-2014` covers AY 2013, and `2004-2006` covers AY 2004 and AY 2005.

5. Retrieve easy candidates first.

   Attempt direct retrieval and simple recovery only. Save retrieved source bodies. Do not conduct open-ended web search during the first pass.

6. Verify source-year evidence.

   Count catalog coverage only when catalog-year evidence appears in source title/heading, metadata, extracted text, OCR, or visual review. For policy-page evidence, do not infer panel-year coverage from a current page alone; historical coverage needs revision history, archived snapshots, or another dated source. URL or filename year patterns alone are review leads.

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
- an official institution-wide academic policy page or policy manual document that contains the course repetition policy;
- Internet Archive snapshots of an official source.

Avoid silently mixing source roots during the first pass. If multiple roots are used, record their role:

- `preferred_first_pass`: main source root for the institution;
- `legacy_prior`: legacy workbook lead used as prior evidence or corroboration;
- `fallback_official`: official alternate source used only when the preferred root has a gap;
- `preferred_policy_root`: official institution-wide policy page or policy manual document used as direct policy evidence;
- `fallback_external_archive`: non-institutional archive, such as a state digital archive or Internet Archive;
- `rejected_wrong_scope`: school-, program-, or handbook-specific source outside the target scope.

## First-Pass Source-Root Priority

Use this order unless an institution-specific note documents a reason to change it:

1. Coherent official institution-wide undergraduate catalog archive.
2. Coherent institution repository or library collection for institution-wide catalogs.
3. Official institution-wide academic policy page or policy manual document that contains the course repetition rule.
4. Coherent state/library digital archive collection with institution catalog records.
5. Legacy workbook URLs, treated as prior evidence and fallback leads.
6. Internet Archive recovery of official URLs.
7. AI-assisted discovery for remaining hard cases.

The selected root should be stable enough that a reviewer can understand why years were covered or not covered.

## First-Pass Stop Rules

Stop first-pass discovery for an institution-year when one of these statuses applies:

- `strict_source_found`: retrieved source has explicit catalog-year evidence covering the year.
- `source_found_needs_ocr_or_visual_review`: candidate source appears to cover the year but cannot be verified with text extraction.
- `official_archive_lower_bound_reached`: preferred source root starts after the target year.
- `official_archive_upper_bound_reached`: preferred source root ends before the target year.
- `wrong_scope_lead_rejected`: available lead is school-, program-, or handbook-specific and no exception has been approved.
- `policy_evidence_root_found_needs_historical_coverage`: current official policy source found, but AY 2000-2020 coverage still needs revision history or archived snapshots.
- `fresh_discovery_needed`: no acceptable catalog or policy evidence root has been found in the easy first pass.
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

## Policy-Page Evidence Rule

If an official institution-wide academic policy page contains the course repetition, repeat grade, remediation, or grade replacement rule, it can substitute for a catalog source for policy extraction. The evidence record must preserve the policy page URL, retrieved source body or PDF, excerpt text, source scope, and retrieval date.

A current policy page is not enough to fill the full AY 2000-2020 panel. Historical panel coverage must be established through policy revision history, effective dates, archived snapshots, dated PDF versions, or another source with explicit year coverage.

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

Reusable lesson: School-specific catalog leads can look plausible but be wrong-scope, while an official institution-wide academic policy page may still provide the relevant course repetition rule.

Rule: Reject school-specific sources by default unless an exception is documented. If an institution-wide academic policy page contains the course repetition policy, use it as a policy evidence root and separately document historical coverage through revisions or archived snapshots.

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
