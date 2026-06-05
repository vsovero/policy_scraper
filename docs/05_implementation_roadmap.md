# Implementation Roadmap

## Phase 0: Scaffold and Documentation

Status: completed.

Tasks:

- create `policy_pipeline/` and `data_policy_pipeline/`;
- document workflow, protocol, schema, AI touchpoints, and roadmap;
- keep current Excel/Stata/R files unchanged.

Deliverables:

- project documentation;
- folder scaffold;
- initial implementation plan.

## Phase 1: Legacy Workbook Audit

Status: completed.

Purpose: understand the current public and private data before replacing or expanding it.

Tasks:

- inspect public workbook columns and malformed values;
- inspect private workbook process and training/example sheets;
- count missing URLs, excerpts, years, and policy codes;
- identify rows that look like student notes rather than catalog excerpts;
- identify duplicate/conflicting institution-year records;
- identify start years outside 2000-2020;
- identify `Unknown`/`Any`/missing patterns;
- produce a read-only audit report.

Deliverables:

- `data_policy_pipeline/interim/legacy_public_audit.csv`;
- `data_policy_pipeline/interim/legacy_private_audit.csv`;
- `data_policy_pipeline/review/legacy_audit_review.xlsx`;
- summary report in `data_policy_pipeline/logs/`.

Completed outputs:

- `data_policy_pipeline/interim/legacy_public_audit.csv`;
- `data_policy_pipeline/interim/legacy_private_audit.csv`;
- `data_policy_pipeline/review/legacy_audit_review.xlsx`;
- `data_policy_pipeline/logs/legacy_workbook_audit_summary.md`.

Key findings:

- public workbook: 967 rows audited, 272 rows flagged for review, 200 missing evidence text/excerpts, 191 missing bulletin URLs, 187 missing start years, 39 rows outside 2000-2020, and a small number of malformed threshold/code values;
- private workbook: 11,218 rows audited across four policy-like sheets, 8,319 rows flagged for review, many duplicate institution-year rows, missing URLs/excerpts, missing start years, and 654 conflicting duplicate institution-year rows;
- `Unknown` and `Any` thresholds are common enough that all later stages must preserve the distinction;
- private workbook rows require sheet/source precedence rules before they are used as selected prior evidence.

Implementation implications:

- legacy rows should be merged into later phases as prior evidence with audit flags, not as final policy classifications;
- malformed values should be flagged by validation rather than silently normalized;
- student-note-like text, missing source details, duplicate conflicts, and out-of-range years should feed human review routing.

## Phase 2: Institution-Year Universe

Status: completed.

Purpose: define exactly which institutions and years need policy records.

Tasks:

- derive institution universe from IPEDS/Stata panel;
- mark public/private sector;
- create all `unitid x year` combinations for 2000-2020;
- merge known legacy rows as prior evidence with Phase 1 audit flags attached;
- preserve all duplicate/conflicting legacy rows in a link table or equivalent long-form evidence table;
- define initial private workbook sheet/source precedence rules, but route unresolved conflicts to review;
- identify missing institution-years.

Deliverables:

- `data_policy_pipeline/interim/institution_universe.csv`;
- `data_policy_pipeline/interim/institution_year_targets.csv`;
- optional `data_policy_pipeline/interim/legacy_evidence_links.csv` if legacy rows are kept in a separate bridge table.

## Phase 3: Catalog Discovery Pilot

Status: in progress.

Purpose: test source discovery on a small but representative set.

Recommended pilot:

- begin with a strict 5-institution public pilot to validate evidence rules before expanding;
- expand toward 20 public institutions after the strict protocol is stable;
- include clean cases, messy cases, missing URLs, duplicate/conflicting legacy evidence, multiple policy changes, and ambiguous thresholds;
- cover all years 2000-2020.

Tasks:

- use legacy URLs first;
- use public workbook legacy rows for the public pilot; ignore private workbook example/training rows;
- search institution archive pages;
- record preferred source roots, fallback roots, stop rules, and escalation buckets before expanding beyond the strict pilot;
- query Internet Archive where needed;
- use AI-assisted discovery for hard cases;
- verify all candidate sources by code;
- reject or route school-specific handbook leads to review unless a documented exception says the institution-wide undergraduate catalog is unavailable;
- record academic years by start year. For example, a `2013-2014` catalog is AY 2013, and a `2004-2006` catalog covers AY 2004 and AY 2005;
- require explicit catalog-year evidence from source title/heading, source metadata, or extracted text. URL or filename year patterns are review leads, not accepted coverage by themselves.

Deliverables:

- `data_policy_pipeline/interim/catalog_inventory_pilot.csv`;
- `data_policy_pipeline/interim/catalog_pilot_institutions.csv`;
- `data_policy_pipeline/interim/catalog_retrieval_attempts_pilot.csv`;
- `data_policy_pipeline/interim/catalog_retrieval_coverage_pilot.csv`;
- `data_policy_pipeline/interim/catalog_year_coverage_pilot.csv`;
- `data_policy_pipeline/interim/catalog_pilot_institutions_strict.csv`;
- `data_policy_pipeline/interim/catalog_inventory_strict_pilot.csv`;
- `data_policy_pipeline/interim/catalog_retrieval_attempts_strict_pilot.csv`;
- `data_policy_pipeline/interim/catalog_retrieval_coverage_strict_pilot.csv`;
- `data_policy_pipeline/interim/catalog_year_coverage_strict_pilot.csv`;
- `data_policy_pipeline/interim/catalog_panel_candidates_strict_pilot.csv`;
- `data_policy_pipeline/interim/catalog_panel_year_status_strict_pilot.csv`;
- `data_policy_pipeline/interim/catalog_source_root_plan_strict_pilot.csv`;
- `data_policy_pipeline/interim/catalog_first_pass_escalation_queue_strict_pilot.csv`;
- `data_policy_pipeline/interim/catalog_panel_ready_inventory_strict_pilot.csv`;
- `data_policy_pipeline/interim/catalog_panel_retrieval_attempts_strict_pilot.csv`;
- `data_policy_pipeline/interim/catalog_panel_retrieval_coverage_strict_pilot.csv`;
- `data_policy_pipeline/interim/catalog_panel_year_coverage_retrieved_strict_pilot.csv`;
- `data_policy_pipeline/review/strict_catalog_pilot_review.xlsx`;
- saved sources in `data_policy_pipeline/catalog_sources/`;
- discovery validation report.

Initial implementation note:

- pilot selection and inventory scaffolding should be deterministic;
- optional API smoke testing may be run to confirm OpenAI access, but the smoke test should not create catalog evidence;
- PDF catalog years must be confirmed from extracted PDF text or metadata when possible. If extraction is unavailable or inconclusive, filename-only evidence is retained for review but not counted as strict coverage;
- AI-assisted discovery remains a later, explicitly logged candidate-generation step after deterministic discovery has been attempted.

Current strict-pilot panel expansion note:

- the 5-institution strict pilot is being expanded across AY 2000-2020 before adding more institutions;
- `docs/08_phase3_discovery_protocol.md` defines the general source-root strategy, stop rules, escalation buckets, and scale-up gate;
- the replication checklist in `docs/08_phase3_discovery_protocol.md` is the operating procedure for the next pilot batch;
- `catalog_source_root_plan_strict_pilot.csv` records preferred/fallback/rejected source roots for the strict pilot;
- `catalog_first_pass_escalation_queue_strict_pilot.csv` records unresolved first-pass buckets such as OCR, source-root review, and wrong-scope/fresh discovery;
- `catalog_panel_candidates_strict_pilot.csv` records candidate catalog/bulletin sources discovered from official archive/index pages;
- `catalog_panel_year_status_strict_pilot.csv` records each pilot institution-year as already strictly covered, ready for retrieval, needing OCR/visual review, requiring fresh discovery, or having no current candidate;
- `catalog_panel_retrieval_coverage_strict_pilot.csv` records retrieval and strict catalog-year evidence for ready candidates only;
- `catalog_panel_year_coverage_retrieved_strict_pilot.csv` records the combined strict year coverage after adding ready-candidate retrieval results to the original strict pilot evidence;
- Oregon Health & Science University is treated as fresh discovery because the legacy School of Nursing lead is wrong-scope for an institution-wide undergraduate catalog source.

## Phase 4: Text Extraction and Excerpt Search Pilot

Purpose: confirm that saved sources can produce policy-relevant evidence.

Tasks:

- extract PDF and HTML text;
- store extracted text;
- search for course repetition policy keywords;
- create candidate excerpts;
- score excerpts for relevance.

Deliverables:

- `data_policy_pipeline/extracted_text/` files;
- `data_policy_pipeline/interim/candidate_excerpts_pilot.csv`;
- extraction failure report.

## Phase 5: AI Classification Pilot

Purpose: test whether AI can classify policies reliably from bounded excerpts.

Tasks:

- create classification prompt and JSON schema;
- run AI classification on pilot excerpts;
- validate outputs;
- compare against legacy public/private codes;
- send disagreements and low-confidence cases to human review.

Deliverables:

- `data_policy_pipeline/interim/ai_classifications_pilot.csv`;
- raw API logs in `data_policy_pipeline/logs/`;
- `data_policy_pipeline/review/pilot_review.xlsx`;
- pilot accuracy and disagreement report.

## Phase 6: Human Review Workflow

Purpose: turn ambiguous machine output into reliable final decisions.

Tasks:

- design review workbook;
- include source URL, excerpt, AI result, confidence, and disagreement flags;
- collect human decisions;
- merge adjudicated decisions back into the final evidence table.

Deliverables:

- `data_policy_pipeline/review/policy_review_queue.xlsx`;
- `data_policy_pipeline/review/policy_review_resolved.csv`.

## Phase 7: Scale Public Institutions

Purpose: run the validated pipeline across public 4-year institutions.

Tasks:

- run catalog discovery in batches;
- run source retrieval and text extraction;
- classify excerpts with AI;
- validate outputs;
- create human review queue;
- resolve flagged cases.

Deliverables:

- public catalog inventory;
- public evidence master;
- public institution-year panel;
- coverage and validation report.

## Phase 8: Scale Private Institutions

Purpose: bring private data into the same evidence-first workflow.

Tasks:

- ingest `gfprivatelist.xlsx` as legacy evidence;
- apply explicit private sheet/source precedence rules before selecting prior evidence;
- reuse private examples and training set only as training/evaluation material or low-priority legacy context unless separately reviewed;
- run missing private institution-years through the same discovery/extraction/classification workflow;
- produce combined public/private panel.

Deliverables:

- private evidence master;
- private institution-year panel;
- combined public/private policy panel.

## Phase 9: Stata Integration

Purpose: connect the new panel to the existing analysis.

Tasks:

- export Stata-compatible fields;
- update Stata cleaning to import complete policy panel directly;
- avoid sparse-row expansion in Stata;
- rerun downstream sample construction;
- compare old vs new sample sizes, missingness, and treatment timing.

Deliverables:

- `data_policy_pipeline/processed/policy_panel_2000_2020.csv`;
- `data_policy_pipeline/processed/policy_panel_2000_2020.xlsx`;
- Stata-ready import file;
- comparison report.

## Phase 10: Reproducibility and Documentation

Purpose: make the project defensible for research use.

Tasks:

- write final data construction README;
- document AI models and prompt versions;
- record source coverage and missingness;
- document human review process;
- produce final audit tables.

Deliverables:

- final data construction document;
- audit logs;
- coverage tables;
- final code release checklist.

## First Coding Tasks

After Phase 1, the next implementation tasks should be:

1. create the institution-year universe table from the IPEDS/Stata analysis panel;
2. create all `unitid x year` targets for 2000-2020;
3. merge Phase 1 legacy audit rows as prior evidence and quality flags;
4. create private workbook precedence rules for legacy evidence links;
5. identify missing institution-years and source-discovery priority groups.
