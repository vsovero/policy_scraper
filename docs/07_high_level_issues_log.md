# High-Level Issues Log

This is a running log of methodological and workflow issues uncovered while building the policy pipeline. It is meant to preserve decisions, concerns, and unresolved questions at a higher level than the code or interim CSV outputs.

## Source Root Consistency

Issue: For a given institution, candidate catalog coverage can come from multiple source roots: legacy workbook links, official institutional archive pages, repository collections, state/library digital archives, Internet Archive, or page-level search results.

Why it matters: Mixing roots can improve coverage but makes first-pass logic harder to audit. UNC Charlotte is the current example: legacy links covered some early years, Provost pages filled some later years, and a DigitalNC lead was found incidentally.

Current handling: Source provenance is preserved in candidate and retrieval tables, but the first-pass selection hierarchy needs to be made more explicit.

Follow-up: For each institution, identify a preferred first-pass source root where possible. Use the official archive/root first; use legacy URLs as leads, gap-fill, or corroboration only after checking whether they fall outside official archive coverage.

## Institution-Specific Cases Versus Scalable Rules

Issue: It is easy to get stuck solving one institution's catalog history in detail.

Why it matters: The purpose of the strict pilot is to build a scalable discovery protocol, not to maximize coverage for a single institution at any cost.

Current handling: Phase 3 now separates source-root planning, first-pass stop rules, and escalation buckets. The strict pilot institutions are treated as examples of reusable cases: clean archive, repository with bounds, scanned PDFs, mixed source roots, and wrong-scope leads.

Follow-up: Before expanding the pilot, use `docs/08_phase3_discovery_protocol.md`, `catalog_source_root_plan_strict_pilot.csv`, and `catalog_first_pass_escalation_queue_strict_pilot.csv` to decide which buckets should be handled next.

## Stage Ladder Versus Row-Level Troubleshooting

Issue: A long list of row-level edge cases can make the process look like manual troubleshooting, even when most unresolved rows simply need the next automated pipeline module.

Why it matters: Scale-up requires a small common workflow across all institution-years. The row table should say how far the row has progressed, why it stopped, and which batch action handles it next.

Current handling: The Phase 3 protocol now uses a stage ladder: `no_source_path`, `root_identified`, `candidate_identified`, `source_retrieved`, `text_available`, `policy_excerpt_found`, and `policy_classified`. Separate fields should record `stop_reason`, `next_batch_action`, and `human_decision_needed`.

Follow-up: Update review/status outputs to use these three fields. Reserve `human_decision_needed` for project-level decisions, not ordinary retrieval recovery, OCR, secondary archive expansion, or text extraction.

## Reverse-Engineering Current Results

Issue: The current strict-pilot data files were produced through iterative troubleshooting, not a fully pre-specified protocol.

Why it matters: We should not discard useful results, but we also should not hide how they were produced.

Current handling: The current process is now traced explicitly in `catalog_current_process_source_trace_strict_pilot.csv` and `catalog_current_process_year_trace_strict_pilot.csv`. These files label the actual process roles, such as `legacy_prior_confirmed`, `preferred_root_archive_fill`, `fallback_official_gap_fill`, `ocr_or_visual_review`, and `archive_bound_stop`.

Follow-up: Use the trace outputs to decide which ad hoc steps should become standard procedure and which should remain fallback or review-only behavior.

## UNC Charlotte Source Hierarchy

Issue: UNC Charlotte was initially handled with a mix of legacy PDF links and Provost archive pages. This created confusing archive-bound labels because AY 2001-2002 came from legacy evidence, while AY 2003-2011 came from Provost nodes.

Why it matters: The apparent gap structure depends on which source root is being evaluated. AY 2000 is earlier than the Provost-node candidates found, while AY 2012-2020 are later than them. Those are not the same failure mode.

Current handling: Guardrail statuses now distinguish lower-bound and upper-bound archive limits:

- `official_archive_lower_bound_reached`;
- `official_archive_upper_bound_reached`.

Follow-up: Keep UNC Charlotte official-archive first. Treat legacy URLs as prior/corroborating evidence and use them as gap-fill only for years outside the official archive's observed coverage. Do not turn incidental DigitalNC discovery into a standard search step.

## Archive Bound Guardrails

Issue: Searches can waste time when a visible archive/index has an obvious coverage boundary.

Why it matters: The pilot should prioritize easy, reproducible first-pass discovery before spending resources on deep search, ad hoc web search, or API-assisted candidate generation.

Current handling: For first-pass panel expansion, rows outside known official archive/index bounds are marked with archive-bound statuses rather than left as vague missing candidates.

Follow-up: Generalize the guardrail so each institution-source root can record `first_ay`, `last_ay`, and whether those bounds are inferred from observed catalog candidates or explicitly stated by the source.

## URL/Filename Inference Risk

Issue: URLs and filenames often contain year patterns, but those patterns are not enough to prove catalog coverage.

Why it matters: Accepting filename-only year evidence can silently create false coverage, especially for redirected downloads, stale pages, non-catalog documents, or PDFs with inaccessible text.

Current handling: Strict coverage requires catalog-year evidence from source title/heading, source metadata, or extracted document text. Filename-only evidence is retained for review but not counted as strict coverage.

Follow-up: Preserve this rule for scale-up. If OCR/visual review confirms a scanned PDF, record that confirmation type separately rather than converting filename-only evidence into strict automated evidence.

## Academic Year Interpretation

Issue: Catalog date ranges must be translated into academic-year panel rows consistently.

Why it matters: The target panel is AY 2000-2020. A `2013-2014` catalog covers AY 2013, while a `2004-2006` catalog covers AY 2004 and AY 2005.

Current handling: Code expands catalog ranges as `[start, end)`, so the ending year is exclusive.

Follow-up: Keep this explicit in every coverage output and review workbook.

## School-Specific Versus Institution-Wide Sources

Issue: Some leads point to school-specific or program-specific pages rather than institution-wide undergraduate catalogs or undergraduate academic policy sources.

Why it matters: These sources can be wrong-scope for institutional policy coding. OHSU's School of Nursing lead is the current example.

Current handling: Wrong-scope school-specific leads are routed to fresh discovery. If fresh discovery still finds only school-specific catalog leads and no usable university-wide catalog root, the institution is marked as a catalog dead end for the pilot.

Follow-up: Preserve any non-catalog policy leads separately, but do not keep spending Phase 3 catalog-discovery effort on dead-end cases.

## Catalog Sources Versus Academic Policy Sources

Issue: Course repetition policy is sometimes published in official institution-wide academic policy pages or policy manuals rather than in catalogs.

Why it matters: If the policy rule is available directly from an official institution-wide policy source, it may help later extraction, but using a current policy page for AY 2000-2020 would require historical dating work. OHSU is the current example: the catalog path dead-ended in school-specific sources, while the OHSU-wide University Grading policy contains repeated/remediated course language that is not dated for the full panel.

Current handling: Phase 3 now records `deferred_policy_lead` separately from catalog roots. A current policy root can be useful later, but it is not used for Phase 3 catalog coverage.

Follow-up: Keep the main pilot catalog-first. Revisit policy pages later only if catalog discovery fails or if a later extraction/classification phase can handle revision history, effective dates, archived snapshots, or another dated source.

## Scanned PDFs And OCR

Issue: Some catalog PDFs retrieve successfully but do not expose useful text to `pypdf`.

Why it matters: Without text extraction, catalog-year and policy-excerpt verification cannot be automated cleanly. ABAC is the current example.

Current handling: ABAC candidates are marked `scanned_pdf_needs_ocr_or_visual_review` and are not counted as strict coverage yet.

Current OCR pilot finding: The ABAC OCR/visual workflow can retrieve newer Wayback snapshots and render first-page images for some PDFs. The 2000-2002 catalog was strictly confirmed from visible first-page text. The 2002-2004 catalog rendered but did not show the full visible year range on page 1, so it remains unconfirmed. The 2004-2006 candidate hit a malformed snapshot/render failure.

Follow-up: Expand the OCR workflow cautiously by trying additional pages and additional Wayback snapshots before counting scanned PDFs as strict coverage. Preserve the confirmation method in provenance.

## Legacy Evidence As Prior Evidence

Issue: Legacy workbook rows are useful but inconsistent: missing URLs, duplicate/conflicting rows, review flags, and possible collector notes.

Why it matters: Legacy data should guide discovery but should not automatically become final policy evidence.

Current handling: Legacy rows are preserved as prior evidence with audit flags. Duplicate/conflicting rows remain in evidence-link outputs rather than being collapsed silently.

Follow-up: Keep selected legacy evidence separate from final source-confirmed evidence.

## Institutional Digital Archives As Secondary Roots

Issue: Some legacy URLs point to a university-wide digital archive collection rather than isolated pages. University of Northern Colorado is the current example: the preferred SmartCatalog root covers AY 2011-2020, while legacy rows point to `digarch.unco.edu` objects for AY 2000, AY 2002, and AY 2008.

Why it matters: Treating these URLs only as isolated legacy gap-fill leaves adjacent years missing even when the same institutional archive may contain sibling catalog records. Treating them as broad web-search leads would undermine the source-root guardrails.

Current handling: The Phase 3 protocol now allows a bounded `secondary_institutional_digital_archive` root when the archive appears organically from legacy/official context, is institution-specific, appears catalog/bulletin-related, and covers years outside the preferred root's observed span. The UNC test confirms the candidate-discovery part of this rule: Digital UNC's OAI endpoint exposes bounded `Catalogs 2000-2009` and `Catalogs 2010-2019` sets, and metadata titles fill AY 2000-2010.

Follow-up: Direct Digital UNC catalog body retrieval is WAF/challenge-blocked from the pipeline environment, so the next extraction step needs a browser/manual/approved access path or another downloadable file endpoint. Until then, UNC secondary archive rows are source candidates with metadata year evidence, not extracted policy text.

## Private Workbook Example Sheet

Issue: The private workbook contains an example/training sheet that should not be treated as real institutional evidence.

Why it matters: Including instructional examples would contaminate the institution-year evidence table.

Current handling: Private example material is ignored for pilot discovery and should only be used as training/evaluation context if separately documented.

Follow-up: Make private-workbook sheet precedence explicit before private-institution scale-up.

## API-Assisted Discovery Boundaries

Issue: AI/API calls can help with hard discovery and classification, but should not replace source retrieval, source saving, or evidence validation.

Why it matters: API results need to be reproducible, bounded, and auditable.

Current handling: API access is configured, smoke-tested, and used only in controlled comparison workflows so far. Deterministic discovery is attempted first.

Follow-up: Add AI-assisted candidate generation only after source-root, archive-bound, and retrieval guardrails are in place.
