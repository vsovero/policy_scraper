# Project Plan

## Objective

Build a complete, auditable database of course repetition policies for public and private 4-year institutions for every year from 2000 through 2020.

The final output should support the existing academic research project on grade forgiveness, grade averaging, retake thresholds, and graduation outcomes. It should produce a complete `unitid x year` policy panel that can be merged with IPEDS and used in Stata.

## Current Problem

The existing public workbook, `Ipeds raw Data files/Course repetition data.xlsx`, is a useful historical input but not a reliable final database. Known issues include:

- rows were recorded mainly when students believed the policy changed;
- many institution-years are missing because the sheet is not a full panel;
- some rows contain student-written notes instead of verbatim policy excerpts;
- some URLs are missing, incorrect, or not tied cleanly to a catalog year;
- some coding columns contain malformed values;
- `Unknown`, `Any`, and missing values may have been conflated;
- some start years fall outside the 2000-2020 target range;
- downstream cleaning currently maps some uncertain values into policy categories.

The private workbook process is closer to the desired approach because it contains institution-year expanded sheets and examples of excerpt-driven collection.

## Phase 1 Audit Findings

The read-only legacy workbook audit confirms the overall project direction. The legacy workbooks are valuable as historical inputs and discovery seeds, but neither workbook should be treated as a clean source of final policy data.

Public workbook findings:

- 967 rows audited across roughly 805 institutions;
- 272 rows flagged for review;
- 200 rows missing evidence text or excerpts;
- 191 rows missing bulletin URLs;
- 187 rows missing start years;
- 39 rows with start years outside the 2000-2020 target range;
- malformed values include typo variants such as `Unkonwn` and `Unknonw`, plus at least one visibly shifted row;
- `Unknown` and `Any` are both materially present and must remain distinct.

Private workbook findings:

- 11,218 rows audited across four policy-like sheets;
- 8,319 rows flagged for review;
- major review reasons include duplicate institution-year rows, missing evidence text, missing URLs, missing start years, and conflicting duplicate records;
- conflicts are concentrated in the `private` and `LLM Training Set` sheets;
- the workbook functions as a workflow archive rather than one final flat source table.

Implications for the build:

- Phase 2 should carry legacy audit flags into the institution-year target table wherever legacy evidence is merged;
- private workbook ingestion needs explicit sheet/source precedence rules before private rows are used as legacy evidence;
- malformed policy codes and threshold values should be detected by validation, not silently repaired;
- review routing should treat student-note-like excerpts, missing URLs, missing evidence, and duplicate conflicts as first-class reasons for review.

## Recommended Approach

Use a Python-centered pipeline for data collection, evidence extraction, AI-assisted classification, validation, and export. Keep Stata for downstream econometric analysis.

The workflow should be:

```text
Institution universe
-> catalog discovery
-> source verification
-> catalog download/snapshot
-> text extraction
-> policy excerpt search
-> AI-assisted classification
-> deterministic validation
-> human review
-> final institution-year policy panel
-> Stata analysis
```

## Why Python

Python is the best primary tool for this pipeline because it can handle:

- Excel and CSV ingestion;
- URL validation and downloading;
- PDF and HTML extraction;
- Internet Archive queries;
- text search and excerpt construction;
- structured AI API calls;
- JSON schema validation;
- audit logging;
- review workbook generation;
- Stata-ready data export.

Stata should not be responsible for scraping websites or interpreting catalog text. Its role should begin after a clean, complete policy panel exists.

## What AI Should Do

AI should assist in two bounded places:

1. **Catalog discovery for hard cases**
   - When deterministic search cannot locate catalog sources.
   - AI can suggest candidate URLs, archive pages, and likely year coverage.
   - Every AI-suggested source must be verified by code before entering the source table.

2. **Policy classification from bounded evidence**
   - After Python has already extracted relevant catalog excerpts.
   - AI receives institution/year metadata and a candidate excerpt.
   - AI returns structured JSON matching a fixed schema.
   - AI must include a supporting quote and confidence flag.

AI should not be allowed to browse freely and directly create final data. The final database must be evidence-backed and reproducible.

## What Code Should Do

Code should:

- define the institution-year universe;
- ingest legacy spreadsheet data as historical evidence;
- preserve legacy audit-quality flags when merging prior evidence;
- identify missing or suspicious legacy records;
- search and verify catalog URLs;
- download and preserve source files;
- extract text;
- generate candidate excerpts;
- call AI using controlled prompts and schemas;
- validate the AI response;
- flag low-confidence cases for human review;
- generate final cleaned panels.

## What Human Review Should Do

Human review should focus on cases that are hard, ambiguous, or high-impact:

- no catalog found;
- catalog found but no policy excerpt extracted;
- AI confidence below threshold;
- AI classification conflicts with legacy data;
- policy appears to change unexpectedly;
- `Any` vs `Unknown` cannot be resolved;
- both grade averaging and grade forgiveness appear to be present;
- source year coverage is unclear.

The review workflow should not ask humans to search from scratch whenever avoidable. It should present candidate sources, excerpts, AI classification, and clear review reasons.

## Final Deliverables

Expected final outputs:

- `policy_evidence_master.csv`: all source-backed evidence records.
- `catalog_inventory.csv`: source discovery and retrieval status by institution-year.
- `policy_panel_2000_2020.csv`: final institution-year panel.
- `policy_panel_2000_2020.xlsx`: reviewable final workbook.
- Stata-ready export, either `.dta` or CSV designed for Stata import.
- audit reports documenting coverage, missingness, classification confidence, and review status.

## Non-Goals

The first phase should not:

- modify existing public/private workbooks;
- rewrite Stata estimation code;
- scrape every institution immediately;
- trust AI classifications without validation;
- use Excel as the sole raw source archive.
