# Phase 3 Discovery Protocol

This protocol translates the strict 5-institution pilot into a scalable first-pass workflow. The goal is not to exhaust every possible source for each institution. The goal is to produce a consistent, auditable first-pass catalog coverage table and a clear escalation queue.

## Operating Principle

Phase 3 should move each institution-year as far as possible along the same source-to-policy stage ladder:

| Stage | `pipeline_stage` | Meaning |
|---:|---|---|
| 0 | `no_source_path` | No acceptable source root or source path has been identified. |
| 1 | `root_identified` | A preferred or secondary source root exists, but no year-level source candidate has been identified for this institution-year. |
| 2 | `candidate_identified` | A year-level source candidate exists with explicit catalog-year metadata/title/heading evidence. |
| 3 | `source_retrieved` | The source body has been saved and is ready for text/OCR work. |
| 4 | `text_available` | Searchable text or OCR text exists. |
| 5 | `policy_excerpt_found` | Candidate course-repeat policy text has been found. |
| 6 | `policy_classified` | The policy excerpt has been classified and coded. |

Each row should also record:

- `stop_reason`: why the row has not advanced to the next stage;
- `next_batch_action`: which pipeline module or work queue should handle it next;
- `human_decision_needed`: true only for project-level judgment calls, not ordinary retrieval, OCR, archive expansion, or extraction work.

Most rows should not require row-by-row human troubleshooting. They should either advance to the next stage or be assigned to a defined next batch action.

Institution-specific cases are useful only when they become reusable rules that fit this stage ladder.

## Stage Stops And Next Actions

Use these stop reasons and actions to explain why a row paused.

| `stop_reason` | Typical current stage | `next_batch_action` | Meaning |
|---|---|---|---|
| `archive_bound` | `root_identified` | `defer_archive_bound` | The preferred archive visibly starts after or ends before the target year. |
| `interior_archive_gap` | `root_identified` | `targeted_archive_gap_search` | The target year falls inside the observed archive span, but no explicit candidate was extracted. Treat this as a likely missed item until targeted archive/search checks are exhausted. |
| `no_root_found` | `no_source_path` | `source_root_discovery` | No acceptable catalog root has been found in the deterministic pass. |
| `secondary_archive_needed` | `root_identified` | `expand_secondary_archive` | Legacy/official context points to a bounded institutional archive that should be expanded. |
| `body_access_blocked` | `candidate_identified` | `retrieval_recovery` | Candidate metadata exists, but the source body is blocked or challenge-protected. |
| `source_not_retrieved` | `candidate_identified` | `retrieval_recovery` | Candidate URL exists, but direct retrieval failed. |
| `ocr_needed` | `source_retrieved` | `ocr_batch` | Source is likely scanned/image-only. |
| `text_extraction_failed` | `source_retrieved` | `text_extraction_repair` | Source body exists, but text extraction failed for a non-OCR reason. |
| `policy_terms_not_searched` | `text_available` | `policy_term_search` | Text exists but policy search has not run. |
| `policy_excerpt_ambiguous` | `policy_excerpt_found` | `classification_review` | Candidate policy text exists, but classification is not settled. |
| `wrong_scope` | `no_source_path` or `root_identified` | `defer_wrong_scope` | Available leads are school-, program-, or handbook-specific and not approved for institution-wide coding. |
| `policy_dating_needed` | `no_source_path` or `candidate_identified` | `policy_dating_workflow` | A current policy page exists but needs historical dating before it can support AY 2000-2020. |

Examples:

- UNC AY 2000-2010 after the OAI test: `pipeline_stage = candidate_identified`, `stop_reason = body_access_blocked`, `next_batch_action = retrieval_recovery`.
- ABAC scanned catalogs: `pipeline_stage = source_retrieved`, `stop_reason = ocr_needed`, `next_batch_action = ocr_batch`.
- ETSU AY 2000-2009 after the official archive check: `pipeline_stage = root_identified`, `stop_reason = archive_bound`, `next_batch_action = defer_archive_bound`.
- GMU AY 2000 after retrieval: `pipeline_stage = source_retrieved`, `stop_reason = policy_terms_not_searched`, `next_batch_action = policy_term_search`.

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

8. Assign every institution-year a stage status.

   Record `pipeline_stage`, `stop_reason`, and `next_batch_action`. The row should either advance to the next stage or land in a defined queue.

   A missing year inside an otherwise observed archive span is not a routine `no_candidate_found` row. Because archives rarely omit a single year within a continuous run, classify it as `interior_archive_gap` and send it to `targeted_archive_gap_search`. First check for missed pagination, hidden slideshow/gallery entries, alternate title patterns, search facets within the same archive, and adjacent sibling records. Only downgrade after those bounded checks fail.

9. Move unresolved years to the next batch action.

   Escalate by type, not by institution story: retrieval recovery, OCR, secondary archive expansion, archive-bound deferral, wrong-scope deferral, policy dating, or text/policy extraction.

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

When the preferred root does not produce a year-level candidate, legacy URLs may be used as bounded gap-fill candidates. Record these as `legacy_prior_gap_fill`, not as preferred-root coverage. This preserves the student-discovered source while keeping the root-first audit trail clear.

If a legacy URL is a current or archived policy page rather than a catalog, bulletin, or catalog PDF, preserve it as `legacy_policy_page_deferred` and route the institution-year to `policy_dating_workflow`. Do not retrieve it as catalog-source coverage.

If an official catalog root is JavaScript-rendered and points users to a library or institutional repository archive, record that archive as a reviewed secondary archive seed. Batch 4 example: UAH's Kuali catalog page points to the LOUIS Course Catalogs collection, which is a BePress gallery with visible catalog-year titles and downloadable `viewcontent.cgi` PDF sources.

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

Stop first-pass discovery for an institution-year when one of these conditions applies, then map it to `pipeline_stage`, `stop_reason`, and `next_batch_action`:

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

## Next Batch Actions

After first pass, unresolved institution-years should be routed by next action:

- `source_root_discovery`: no acceptable root has been found.
- `expand_secondary_archive`: bounded institutional archive expansion is the next automated source-candidate step.
- `retrieval_recovery`: source candidate exists but body retrieval needs mechanical recovery.
- `ocr_batch`: source body exists but needs OCR or visual confirmation.
- `text_extraction_repair`: source body exists but extraction failed.
- `policy_term_search`: text exists and needs policy keyword/excerpt search.
- `classification_review`: candidate policy excerpt exists but classification needs review or AI-assisted coding.
- `defer_archive_bound`: preferred archive bound is recorded; do not chase this year in the current batch.
- `defer_wrong_scope`: only wrong-scope sources have been found in the current batch.
- `policy_dating_workflow`: policy page exists but historical dating is needed before it can support panel years.
- `api_assisted_discovery`: deterministic discovery failed and AI/search assistance is warranted.

`human_decision_needed` should be reserved for project-level choices, such as changing scope rules, accepting a non-catalog source class, or deciding to spend resources on archive-bound years. Ordinary retrieval recovery, OCR, secondary archive expansion, and text extraction are pipeline queues, not manual row review.

For larger batches, keep preferred-root discovery and legacy gap-fill retrieval as separate, restartable stages. The batch 4 run showed that legacy recovery is productive but slow enough that it should be capped or resumed independently rather than bundled into one long full-scale run.

## Catalog-Year Evidence Rule

Strict coverage requires explicit catalog-year evidence from one of:

- source title or heading;
- page metadata;
- visible archive-page context, such as table-row text, dropdown option text, or an undergraduate catalog archive page title paired with a visible year-range link;
- extracted PDF/document text;
- OCR or visual review record.

URL or filename year patterns alone are not strict evidence.

Batch 3 converts two reusable page-context patterns into code:

- table rows where the year appears in a neighboring cell and the link text is generic, such as `PDF` or `HTML`;
- catalog dropdowns where archived catalog years appear in visible `<option>` text.
- BePress gallery cards where the visible title contains the catalog year and the item asset id maps to a downloadable `viewcontent.cgi` source.

The year still must appear in visible page context. URL or filename years may help identify the linked source or undergraduate scope, but they should not be the sole year evidence.

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
