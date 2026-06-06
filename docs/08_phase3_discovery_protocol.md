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

   Record the best coherent catalog source before collecting individual year URLs. Prefer official institution-wide catalog archives and institution-specific repositories. Treat legacy workbook links as prior evidence or fallback leads unless they clearly represent the same coherent root.

2. Record fallback roots separately.

   If another root is useful, assign it a role such as `legacy_prior`, `fallback_official`, `secondary_institutional_digital_archive`, `fallback_external_archive`, or `rejected_wrong_scope`. Do not silently mix roots.

3. Promote bounded secondary roots when justified.

   Do not make university-wide digital archives the default main-root search target. Promote one only when the preferred catalog root is missing, dead, or visibly bounded, or when legacy/official context points to a university-wide institutional digital archive or repository collection that covers years outside the preferred root's observed archive span. Inspect the parent/collection context first. If it is catalog-specific, institution-wide, and bounded, promote it to `secondary_institutional_digital_archive` for those gap years only.

4. Extract source candidates from the preferred root.

   For each catalog candidate, record title, URL, source-root URL, catalog-year start, catalog-year end, evidence type, and whether the source appears institution-wide and undergraduate. Policy-page leads can be logged as later extraction leads, but they should not drive the Phase 3 catalog panel.

5. Apply academic-year expansion.

   Expand ranges as `[start, end)`: `2013-2014` covers AY 2013, and `2004-2006` covers AY 2004 and AY 2005.

6. Retrieve easy candidates first.

   Attempt direct retrieval and simple recovery only. Save retrieved source bodies. Do not conduct open-ended web search during the first pass.

7. Verify source-year evidence.

   Count catalog coverage only when catalog-year evidence appears in source title/heading, metadata, extracted text, OCR, or visual review. URL or filename year patterns alone are review leads.

8. Assign every institution-year a first-pass status.

   Each year should be covered or assigned a stop/review status such as OCR needed, archive lower/upper bound reached, wrong-scope lead rejected, fresh discovery needed, or fallback deferred.

9. Move unresolved years to an escalation bucket.

   Escalate by type, not by institution story: OCR/visual review, source-root review, archive-bound revisit, wrong-scope exception review, API-assisted discovery, or manual review.

10. Stop the first pass.

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
- `secondary_institutional_digital_archive`: university-wide institutional archive or repository collection promoted from legacy/official context to fill years outside the preferred root's observed span;
- `deferred_policy_lead`: official policy page or policy manual document that may help later policy extraction, but is not used for Phase 3 catalog coverage.
- `fallback_external_archive`: non-institutional archive, such as a state digital archive or Internet Archive;
- `rejected_wrong_scope`: school-, program-, or handbook-specific source outside the target scope.

## First-Pass Source-Root Priority

Use this order unless an institution-specific note documents a reason to change it:

1. Coherent official institution-wide undergraduate catalog archive.
2. Coherent institution repository or library collection for institution-wide catalogs.
3. Legacy workbook URLs, treated as prior evidence and fallback leads.
4. Bounded secondary institutional digital archive collection promoted from legacy or official context for years outside the preferred root span, or after the normal catalog-root search fails.
5. Internet Archive recovery of official URLs.
6. Coherent state/library digital archive collection with institution catalog records, only when it appears organically from legacy links or official-site search.
7. AI-assisted discovery for remaining hard cases.

Legacy URLs should be inspected early as discovery leads, but they should not override a better coherent source root. When a legacy URL points to a broader official archive, repository collection, or stable catalog root, record the broader root as the preferred first-pass source and keep the legacy URL as prior or corroborating evidence.

Do not run broad searches across general state or library digital archives as a standard first-pass step. If such an archive appears organically, use it only after checking whether its years fall outside the observed coverage of the official archive/root. For years where the official archive and the external archive overlap, prefer the official archive.

The selected root should be stable enough that a reviewer can understand why years were covered or not covered.

## Secondary Institutional Digital Archive Rule

A university-wide institutional digital archive can be promoted from `legacy_prior` to `secondary_institutional_digital_archive` when all of these conditions hold:

- the normal catalog-root search is missing, dead, or visibly bounded, or the archive appears organically from legacy evidence or an official institution page;
- the source is institution-specific, not a broad external search result;
- the parent page, collection page, object metadata, or sibling records indicate an institution-wide catalog/bulletin collection;
- the archive's target years fall outside the preferred source root's observed coverage span;
- candidate records expose explicit catalog-year evidence in title, heading, metadata, extracted text, OCR, or visual review.

When promoted, expansion must remain bounded to the identified collection or sibling-object context. Do not use the archive as a reason to run a broad web search. The search target is not "find any digital archive"; it is "find a catalog archive/root first, then use a university digital archive only if the catalog root fails or leaves documented gaps." For overlapping years, prefer the preferred official root/archive unless the secondary archive is needed for corroboration or the preferred source fails retrieval.

Use these statuses and roles:

- source-root role: `secondary_institutional_digital_archive`;
- candidate method: `institutional_digital_archive_gap_fill`;
- unresolved status: `secondary_archive_gap_unfilled`;
- escalation bucket: `institutional_archive_expansion`.

UNC batch 2 example: SmartCatalog is the preferred root for AY 2011-2020. Legacy evidence points to UNC Digital Archive objects for AY 2000, AY 2002, and AY 2008. Because those leads are institution-specific and outside the SmartCatalog span, the UNC Digital Archive can be promoted to a bounded secondary root for AY 2000-2010. The tested route is Digital UNC's OAI endpoint, which exposes `Catalogs 2000-2009` and `Catalogs 2010-2019` sets with explicit catalog-year metadata. This fills AY 2000-2010 as source candidates, but direct catalog body retrieval remains WAF/challenge-blocked from the pipeline environment; extraction needs a browser/manual/approved access path.

## First-Pass Stop Rules

Stop first-pass discovery for an institution-year when one of these statuses applies:

- `strict_source_found`: retrieved source has explicit catalog-year evidence covering the year.
- `source_found_needs_ocr_or_visual_review`: candidate source appears to cover the year but cannot be verified with text extraction.
- `official_archive_lower_bound_reached`: preferred source root starts after the target year.
- `official_archive_upper_bound_reached`: preferred source root ends before the target year.
- `secondary_archive_gap_unfilled`: a promoted secondary institutional digital archive was checked but no explicit candidate was found for the target year.
- `wrong_scope_lead_rejected`: available lead is school-, program-, or handbook-specific and no exception has been approved.
- `catalog_dead_end_wrong_scope`: fresh discovery found only wrong-scope catalog leads, so catalog-first discovery stops for the institution in this pilot.
- `policy_lead_deferred`: current official policy source found, but deferred because using it for AY 2000-2020 would require revision-history or Wayback work outside the catalog-first pass.
- `fresh_discovery_needed`: no acceptable catalog root has been found in the easy first pass.
- `fallback_deferred`: a deeper fallback is plausible but intentionally deferred.

Do not use open-ended web searching to resolve every gap during the first pass.

## Escalation Buckets

After first pass, unresolved institution-years should be routed by bucket:

- `ocr_or_visual_review`: scanned or image-only sources need OCR or page-image confirmation.
- `source_root_review`: multiple plausible roots exist and a coherent hierarchy must be chosen.
- `institutional_archive_expansion`: legacy/official context reveals a bounded university digital archive that should be expanded within its collection context for years outside the preferred root span.
- `archive_bound_revisit`: source root has a lower or upper bound; deeper search may be revisited later.
- `wrong_scope_exception_review`: institution structure may require a documented exception to institution-wide source rules.
- `catalog_dead_end`: catalog-first discovery found no usable university-wide catalog root; preserve provenance and move on in the pilot.
- `api_assisted_discovery`: deterministic source-root discovery failed and AI/search assistance is warranted.
- `manual_review`: source or policy evidence is too ambiguous for automated handling.

## Catalog-Year Evidence Rule

Strict coverage requires explicit catalog-year evidence from one of:

- source title or heading;
- page metadata;
- extracted PDF/document text;
- OCR or visual review record.

URL or filename year patterns alone are not strict evidence.

## Policy-Page Deferral Rule

If an official institution-wide academic policy page contains the course repetition, repeat grade, remediation, or grade replacement rule, preserve it as a later policy-extraction lead. Do not use it as Phase 3 catalog coverage.

A current policy page is not enough to fill the full AY 2000-2020 panel. Historical policy-page coverage would require revision history, effective dates, archived snapshots, dated PDF versions, or another source with explicit year coverage. That is a later phase or escalation path, not the main catalog-discovery pass.

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

Rule: Use the official archive first. Legacy URLs can fill or corroborate years outside the official archive's observed range, but overlapping years should prefer official archive evidence. DigitalNC was found incidentally and should be preserved as a possible later cross-check, not searched as a standard first-pass source.

### University of Northern Colorado

Reusable lesson: A legacy URL can reveal a university-wide institutional digital archive that is more than a one-off prior evidence link.

Rule: If the preferred root starts later than the target panel and legacy URLs point to an institution-specific catalog archive, promote that archive to a bounded `secondary_institutional_digital_archive` root for the missing pre-root years. Expand only within the archive's catalog collection or sibling-object context, preserve the preferred-root/secondary-root distinction, and keep unresolved archive gaps in `institutional_archive_expansion` or `secondary_archive_gap_unfilled`.

### OHSU

Reusable lesson: School-specific catalog leads can look plausible but be wrong-scope, while official policy pages can create an immediate historical-dating detour.

Rule: If fresh discovery finds only school-specific catalogs and no usable university-wide catalog root, mark the institution as a catalog dead end for this pilot. Preserve institution-wide policy pages as deferred extraction leads, but do not keep spending Phase 3 effort on the institution.

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
