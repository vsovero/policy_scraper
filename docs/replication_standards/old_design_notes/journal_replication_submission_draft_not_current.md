# Draft Journal Replication Submission Text

Created: 2026-06-23

This is draft language for the replication package, data appendix, or journal
data editor response. It reflects the current stage of progress: URL discovery
and validation are packaged; text extraction, policy classification, final panel
construction, and final repository deposit are not yet represented here as
complete release stages.

## Data And Code Availability Statement

The analysis uses institution-year policy data constructed from IPEDS-derived
institution panels, legacy hand-collected policy source information, and
publicly available college catalog or academic-policy URLs. The replication
package documents the source-discovery and validation process at the
institution-year level. Each retained source row identifies the institution,
year, source URL, source provenance, URL validation status, and whether the row
is ready for downstream text extraction.

The current packaged stage is URL discovery and validation. The primary
URL-stage output is:

```text
policy_url_discovery_step1/outputs/reviewed_url_panel.csv
```

This file contains one row per target institution-year and records the selected
production URL where available, or the reason the row stops before text
extraction. The package also includes source decision audits, URL validation
audits, gap-fill audits, benchmark truth files, benchmark validation scores,
coverage summaries, loss buckets, and file manifests with checksums.

Full catalog source text and policy classification outputs are handled in later
pipeline stages. Where full source text cannot be redistributed because of
copyright or website terms, the release package will provide source URLs,
retrieval metadata, hashes or stable identifiers where available, extracted
policy excerpts where permitted, and code or instructions to regenerate source
text from the public URLs.

## Current Replication Package Status

As of 2026-06-23, the URL discovery and validation stage is packaged under:

```text
policy_url_discovery_step1/
```

The package is designed to stop before source-text extraction and policy
classification. It does not classify grade-forgiveness or grade-averaging
policies and does not make policy-classification API calls.

The current URL-stage package was generated at:

```text
2026-06-23T17:15:20+00:00
```

The target panel contains:

```text
Target years: 2002-2016
Target institution-years: 25,191
Target institutions: 1,969
Universe rule: IPEDS-derived public four-year and private nonprofit four-year
institutions, iclevel == 1, with nonmissing grad4per, grad5per, or grad6per.
```

## Current Stage Methods: URL Discovery And Validation

The URL-discovery stage starts from an IPEDS-derived target panel and searches
for catalog or academic-policy sources that can support later extraction of
course-repetition policy language. The unit of observation is an
institution-year.

The stage has five main steps:

1. Build the target institution-year panel and hidden legacy benchmark files.
2. Run or reuse validated no-legacy programmatic URL discovery.
3. Apply reviewed rescue and gap-fill layers where first-pass discovery does
   not identify a usable source.
4. Score programmatic URL recovery against withheld human legacy URLs.
5. Build a unified reviewed URL panel using active human legacy URLs plus
   reviewed programmatic fills.

The process manifest is stored at:

```text
policy_url_discovery_step1/outputs/validated_process_manifest.csv
```

The main run command is:

```bash
/Users/verosovero/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  policy_url_discovery_step1/code/run_step1_url_discovery.py
```

The run uses cached validated artifacts by default. It does not rerun policy
classification and does not make policy-classification API calls.

## URL-Stage Inputs

The URL-stage package uses the following main inputs:

```text
Stata Files/Data/mainpanelgf_clean.dta
policy_scraper/artifacts/policy_data_internal/90_INTERNAL_PIPELINE_ARTIFACTS/interim/legacy_evidence_links.csv
policy_scraper/artifacts/policy_data_internal/90_INTERNAL_PIPELINE_ARTIFACTS/audits/clean_no_legacy_benchmark/current/clean_no_legacy_holdout_row_scores.csv
policy_scraper/artifacts/policy_data_internal/90_INTERNAL_PIPELINE_ARTIFACTS/audits/clean_no_legacy_benchmark/current/truth_legacy_url_retrieval.csv
```

The relevant source-code files are listed in the URL-stage manifest and include:

```text
policy_url_discovery_step1/code/run_step1_url_discovery.py
policy_scraper/src/course_policy/clean_no_legacy_benchmark.py
policy_scraper/src/course_policy/public_fresh_discovery.py
policy_scraper/src/course_policy/batch3_discovery.py
policy_scraper/src/course_policy/catalog_retrieval.py
policy_scraper/src/course_policy/catalog_url_harmonization.py
```

## URL-Stage Outputs

The principal URL-stage outputs are:

```text
policy_url_discovery_step1/outputs/target_panel.csv
policy_url_discovery_step1/outputs/institution_universe.csv
policy_url_discovery_step1/outputs/url_candidate_audit.csv
policy_url_discovery_step1/outputs/url_validation_audit.csv
policy_url_discovery_step1/outputs/source_decision_audit.csv
policy_url_discovery_step1/outputs/gap_fill_audit.csv
policy_url_discovery_step1/outputs/package_pattern_gap_fill_audit.csv
policy_url_discovery_step1/outputs/final_best_url_panel.csv
policy_url_discovery_step1/outputs/reviewed_url_panel.csv
policy_url_discovery_step1/outputs/panel_coverage_summary.csv
policy_url_discovery_step1/outputs/url_review_stop_log.csv
policy_url_discovery_step1/outputs/legacy_holdout_truth.csv
policy_url_discovery_step1/outputs/legacy_validation_scores.csv
policy_url_discovery_step1/outputs/stage_rates.csv
policy_url_discovery_step1/outputs/loss_buckets.csv
policy_url_discovery_step1/outputs/run_summary.csv
policy_url_discovery_step1/outputs/file_manifest.csv
```

The manifest file records row counts, file sizes, modification times, and
SHA-256 hashes for packaged outputs and key inputs.

## URL-Stage Progress And Benchmarks

The reviewed URL panel contains 25,191 target institution-year rows. Of these,
6,337 rows have a production URL, equal to 25.2 percent of the target panel.

Production URL coverage by source:

```text
Rows with active human legacy URL: 1,979
Rows added by reviewed programmatic discovery: 4,358
Rows added for institutions with no human legacy URL in the target panel: 1,386
Rows filling missing or inactive years for institutions with some legacy evidence: 2,972
```

Production URL coverage by sector:

```text
Public: 4,085 of 8,745 target institution-years, 46.7 percent
Private nonprofit: 2,252 of 16,446 target institution-years, 13.7 percent
Combined: 6,337 of 25,191 target institution-years, 25.2 percent
```

Institution-level URL-panel coverage after combining active human legacy URLs
and reviewed programmatic URLs:

```text
Institutions with 2+ production URL years: 572
Institutions with 5+ production URL years: 515
Institutions with 8+ production URL years: 411
Institutions with 10+ production URL years: 359
Institutions with 12+ production URL years: 324
Institutions with complete 2002-2016 production URL panels: 263
```

The primary URL-recovery benchmark uses valid held-out human legacy URL rows in
the 2002-2016 estimation sample with graduation outcomes. Against this
benchmark, the URL package recovers:

```text
Combined: 1,783 of 1,979 rows, 90.1 percent
Public: 239 of 261 rows, 91.6 percent
Private nonprofit: 1,544 of 1,718 rows, 89.9 percent
```

The package also reports a broader valid-human-legacy benchmark over all
available years:

```text
Combined: 2,859 of 3,141 rows, 91.0 percent
Public: 404 of 443 rows, 91.2 percent
Private nonprofit: 2,455 of 2,698 rows, 91.0 percent
```

Rows not recovered in the URL benchmark remain visible in
`loss_buckets.csv` and `legacy_validation_scores.csv`; they are not dropped from
the audit trail.

## Treatment Of Human Legacy URLs

Human legacy URLs are used in two separate ways.

First, active human legacy URLs are preserved as production evidence in the
reviewed URL panel. Second, when evaluating clean computer discovery, the human
legacy URL is withheld from the discovery process and used only after discovery
as a benchmark answer key.

This separation is documented in:

```text
policy_url_discovery_step1/README.md
policy_url_discovery_step1/outputs/legacy_holdout_truth.csv
policy_url_discovery_step1/outputs/legacy_validation_scores.csv
```

## Treatment Of LLM Or AI-Assisted URL Search

The clean URL-stage replication package does not use the old external
Claude/LLM suggestion-pool files as production inputs. The URL-stage README
states that these suggestion-pool files are not production inputs for the clean
Step 1 package.

The validated no-legacy discovery process includes cached AI rescue layers for
URL roots and year gaps. These appear in the process manifest as rescue layers
from the prior validated benchmark. In the current packaged run, cached
validated artifacts are reused by default; the package does not make new live
API calls and does not run policy classification.

Any LLM- or AI-assisted URL output is treated as a candidate-generation or
rescue aid, not as source evidence. A URL can enter the production URL panel
only after ordinary validation of retrieval, institution match, source type, and
year support. The catalog or policy page itself is the evidence used for later
policy extraction.

## What Is Not Yet Complete In This Draft

The following replication components are not yet claimed as complete in this
current-stage draft:

```text
Source-text retrieval for every reviewed URL
Policy excerpt extraction from retrieved text
Final policy classification for grade forgiveness and grade averaging
Human adjudication of all ambiguous or treatment-changing classification rows
Final merge into analysis-ready policy panel
Final manuscript-ready AI Use Statement
Final Data Availability Statement covering all downstream outputs
Trusted repository deposit
```

These components should be added to this draft as later stages are frozen.

## Planned Downstream Replication Requirements

For the next stage, the reviewed URL panel will be used to build a text
retrieval queue. That stage should report whether each source URL is retrieved,
whether readable source text is extracted, and whether the row is ready for
policy excerpt extraction. API or LLM classification should remain out of the
text-readiness stage.

For the policy-classification stage, any LLM/API use should be fully
documented. The release package should preserve the prompt, schema, model ID,
run date, parameters, raw response, parsed response, parse status, supporting
quote, review reason, and human review flag for each model-assisted row. Final
policy classifications should be reproducible from cached model outputs and
source-backed evidence without requiring a live API rerun.

## Draft AI Use Statement For The Current URL Stage

AI-assisted tools were used only as candidate-generation or rescue aids in the
URL discovery workflow, not as final source evidence and not as authors. The
current URL-stage replication package reuses cached validated artifacts by
default and does not make new live API calls. The package does not use AI tools
to classify grade-forgiveness or grade-averaging policy at this stage. All
accepted production URLs are subject to validation for retrieval, institution
match, source type, and year support. The authors remain responsible for all
source-selection and validation decisions.

## Draft Replication Instructions For The URL Stage

To reproduce the current URL-stage package from the project root, run:

```bash
/Users/verosovero/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  policy_url_discovery_step1/code/run_step1_url_discovery.py
```

The expected outputs are written to:

```text
policy_url_discovery_step1/outputs/
```

The main file to use in the next stage is:

```text
policy_url_discovery_step1/outputs/reviewed_url_panel.csv
```

Rows with `ready_for_text_extraction_step2 == True` are eligible to enter the
text-retrieval stage. Rows without accepted URLs remain in the reviewed panel or
the URL review stop log with documented stop reasons.
