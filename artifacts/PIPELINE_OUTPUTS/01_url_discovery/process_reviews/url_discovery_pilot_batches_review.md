# URL-Discovery Pilot Batch Review Against URL-Stage Standards

Reviewed: 2026-06-30
Latest Batch 14 snapshot checked: 2026-06-30 11:47 Pacific

This is the current process review for Step 1 URL-discovery pilot batches,
Batch 5 regression work, and post-regression development Batches 6 through 14. It
supersedes the earlier Pilot 1-only review text.

Batch 14 artifacts were rerun during the June 30 review and now pass the
corrected hidden-answer floor. Treat Batch 14 as fixed development evidence,
not clean untouched validation evidence.

## Files Reviewed

Front-door pilot outputs:

```text
policy_scraper/artifacts/PIPELINE_OUTPUTS/01_url_discovery/pilot_batch_001/
policy_scraper/artifacts/PIPELINE_OUTPUTS/01_url_discovery/pilot_batch_002/
policy_scraper/artifacts/PIPELINE_OUTPUTS/01_url_discovery/pilot_batch_003/
policy_scraper/artifacts/PIPELINE_OUTPUTS/01_url_discovery/pilot_batch_004/
policy_scraper/artifacts/PIPELINE_OUTPUTS/01_url_discovery/pilot_batch_005/
policy_scraper/artifacts/PIPELINE_OUTPUTS/01_url_discovery/pilot_batch_005_regression_003/
policy_scraper/artifacts/PIPELINE_OUTPUTS/01_url_discovery/pilot_batch_006_dev_001/
policy_scraper/artifacts/PIPELINE_OUTPUTS/01_url_discovery/pilot_batch_007_dev_002/
policy_scraper/artifacts/PIPELINE_OUTPUTS/01_url_discovery/pilot_batch_008_dev_003/
policy_scraper/artifacts/PIPELINE_OUTPUTS/01_url_discovery/pilot_batch_009_dev_004/
policy_scraper/artifacts/PIPELINE_OUTPUTS/01_url_discovery/pilot_batch_009_regression_002/
policy_scraper/artifacts/PIPELINE_OUTPUTS/01_url_discovery/pilot_batch_010_regression_004/
policy_scraper/artifacts/PIPELINE_OUTPUTS/01_url_discovery/pilot_batch_011_dev_006/
policy_scraper/artifacts/PIPELINE_OUTPUTS/01_url_discovery/pilot_batch_011_regression_001/
policy_scraper/artifacts/PIPELINE_OUTPUTS/01_url_discovery/pilot_batch_012_dev_007/
policy_scraper/artifacts/PIPELINE_OUTPUTS/01_url_discovery/pilot_batch_012_regression_003/
policy_scraper/artifacts/PIPELINE_OUTPUTS/01_url_discovery/pilot_batch_012_regression_008/
policy_scraper/artifacts/PIPELINE_OUTPUTS/01_url_discovery/pilot_batch_013_dev_008/
policy_scraper/artifacts/PIPELINE_OUTPUTS/01_url_discovery/pilot_batch_014_dev_009/
```

Audit evidence:

```text
policy_scraper/artifacts/AUDIT_TRAILS/url_discovery_pilot_batch_001/
policy_scraper/artifacts/AUDIT_TRAILS/url_discovery_pilot_batch_002/
policy_scraper/artifacts/AUDIT_TRAILS/url_discovery_pilot_batch_003/
policy_scraper/artifacts/AUDIT_TRAILS/url_discovery_pilot_batch_004/
policy_scraper/artifacts/AUDIT_TRAILS/url_discovery_pilot_batch_005/
policy_scraper/artifacts/AUDIT_TRAILS/url_discovery_pilot_batch_005_regression_003/
policy_scraper/artifacts/AUDIT_TRAILS/url_discovery_pilot_batch_006_dev_001/
policy_scraper/artifacts/AUDIT_TRAILS/url_discovery_pilot_batch_007_dev_002/
policy_scraper/artifacts/AUDIT_TRAILS/url_discovery_pilot_batch_008_dev_003/
policy_scraper/artifacts/AUDIT_TRAILS/url_discovery_pilot_batch_009_dev_004/
policy_scraper/artifacts/AUDIT_TRAILS/url_discovery_pilot_batch_009_regression_002/
policy_scraper/artifacts/AUDIT_TRAILS/url_discovery_pilot_batch_010_regression_004/
policy_scraper/artifacts/AUDIT_TRAILS/url_discovery_pilot_batch_011_dev_006/
policy_scraper/artifacts/AUDIT_TRAILS/url_discovery_pilot_batch_011_regression_001/
policy_scraper/artifacts/AUDIT_TRAILS/url_discovery_pilot_batch_012_dev_007/
policy_scraper/artifacts/AUDIT_TRAILS/url_discovery_pilot_batch_012_regression_003/
policy_scraper/artifacts/AUDIT_TRAILS/url_discovery_pilot_batch_012_regression_008/
policy_scraper/artifacts/AUDIT_TRAILS/url_discovery_pilot_batch_013_dev_008/
policy_scraper/artifacts/AUDIT_TRAILS/url_discovery_pilot_batch_014_dev_009/
```

Standards used:

```text
policy_scraper/docs/replication_standards/requirements_checklist.md
policy_scraper/docs/replication_standards/url_source_review_standard.md
policy_scraper/docs/replication_standards/supporting_rules/journal_replication_submission_draft_current.md
policy_scraper/artifacts/PIPELINE_OUTPUTS/CLEAN_REBUILD_VALIDATION_PLAN.md
```

## Verdict

Pilot batches 001-004 pass as controlled Step 1 URL-discovery process pilots.
Pilot Batch 5 is the frozen failed regression case. The frozen corrected run
recovered 80 of 128 old-audit rows (62.5%); the latest regression run recovered
116 of 128 rows (90.6%) after general fixes, passing the 90% floor. Pilot Batch
6 development run 001 recovers 174 of 185 old-audit-ready rows (94.1%). Pilot
Batch 7 development run 002 recovers 124 of 132 old-audit-ready rows (93.9%)
after a general current-site catalog-page discovery fix. Pilot Batch 8
development run 003 recovers 220 current ready rows on 218 old-audit-ready rows
(100.9%) after general archive-discovery and PDF-year gap-fill fixes. Pilot
Batch 9 development run 004 failed under the older all-prior-audit summary,
recovering only 82 of 168 rows (48.8%). Batch 9 regression 002 passes the
corrected hidden-answer benchmark, recovering 39 of 43 valid human legacy rows
(90.7%). The broader prior-programmatic diagnostic remains visible at 109 of
168 rows (64.9%). Together, these runs show that the production-path URL
discovery, recovery layers, source-review gate, attrition reporting, manifests,
and benchmark checks can run on fixed batches and on additional development
batches. Batch 10 regression 004 passes the corrected hidden-answer benchmark,
recovering 80 of 82 valid human legacy rows (97.6%). Its prior-programmatic
diagnostic is 128 of 172 rows (74.4%). Batch 10 is regression evidence, not
clean validation, because development and intermediate regression runs failed
before the general fixes were added. Batch 11 development run 006 failed,
recovering 29 of 62 valid human legacy rows (46.8%). Batch 11 regression 001
passes the corrected hidden-answer benchmark, recovering 57 of 62 valid human
legacy rows (91.9%). Its prior-programmatic diagnostic is 123 of 142 rows
(86.6%). Batch 11 is also regression evidence, not clean validation, because it
passed only after additional general fixes. Batch 12 development run 007 failed
at 47 of 92 valid human legacy rows (51.1%). Earlier Batch 12 regression
reports also failed. The latest Batch 12 front-door regression report,
`pilot_batch_012_regression_008`, now passes at 86 of 92 valid human legacy
rows (93.5%). It passes after general fixes for official-domain seed retention,
WordPress media API year searches, candidate-document ranking, stricter
non-source rejection, compact year-span source review, official library/archive
repository discovery, CONTENTdm collection/API expansion, and JSON metadata
source-review evidence. Batch 12 is fixed regression evidence, not clean
untouched validation. Batch 13 development run 008 passes the corrected
hidden-answer benchmark, recovering 85 of 94 valid human legacy rows (90.4%).
It passes after general fixes for prior-year span official-domain probes,
Wayback transient retries, archived catalog-policy source review, and archived
undergraduate index child-source fallback. Batch 13 is fixed development
evidence, not clean untouched validation. Batch 14 development run 009 now
passes the corrected hidden-answer benchmark, recovering 77 of 83 valid human
legacy rows (92.8%) after general deterministic/source-review fixes and a
general Ex Libris/Primo collection-search repair. Its broader
prior-programmatic diagnostic is 142 of 181 rows (78.5%). The latest
front-door counts are 277 target rows, 194 rows with a current-run candidate,
165 rows ready for text extraction, 83 rows with no candidate, and 29 rows
rejected after source review. The run also exposed an operational blocker: all
API rescue triage rows failed with OpenAI `RateLimitError` 429
`insufficient_quota`, so the documented API rescue layer did not return usable
candidates. Batch 14 is fixed development evidence, not a clean untouched
validation pass.

They are not a final production URL-stage handoff and should not be submitted as
the journal replication package. The journal package still needs a frozen full
production run or a self-contained clean validation package where all reported
metrics regenerate from package-local inputs, outputs, scores, manifests, and
cached API artifacts.

## Batch Summary

| batch | target rows | current candidates before review | ready for text extraction | no candidate | rejected after review | benchmark denominator | benchmark recovered | benchmark notes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 001 | 24 | 8 | 8 | 16 | 0 | n/a | n/a | process pilot only |
| 002 | 263 | 202 | 176 | 61 | 26 | 188 | 176 | older all-prior-audit summary |
| 003 | 289 | 235 | 218 | 54 | 17 | 193 | 218 | older all-prior-audit summary |
| 004 | 283 | 244 | 210 | 39 | 34 | 186 | 210 | older all-prior-audit summary |
| 005 frozen | 150 | 87 | 80 | 63 | 7 | 128 | 80 | older all-prior-audit summary; failed |
| 005 regression 003 | 150 | 118 | 116 | 32 | 2 | 128 | 116 | older all-prior-audit summary; fixed regression |
| 006 dev 001 | 285 | 196 | 174 | 89 | 22 | 185 | 174 | older all-prior-audit summary after general fixes |
| 007 dev 002 | 284 | 142 | 124 | 142 | 18 | 132 | 124 | older all-prior-audit summary after general fixes |
| 008 dev 003 | 284 | 220 | 220 | 64 | 0 | 218 | 220 | older all-prior-audit summary after general fixes |
| 009 dev 004 | 269 | 82 | 82 | 187 | 0 | 168 | 82 | older all-prior-audit summary; failed |
| 009 regression 002 | 269 | 142 | 125 | 127 | 17 | 43 | 39 | corrected valid-human hidden-answer floor; prior-programmatic diagnostic 109/168 |
| 010 regression 004 | 284 | 254 | 169 | 105 | 10 | 82 | 80 | corrected valid-human hidden-answer floor; prior-programmatic diagnostic 128/172 |
| 011 dev 006 | 247 | 97 | 95 | 150 | 2 | 62 | 29 | corrected valid-human hidden-answer floor; failed |
| 011 regression 001 | 247 | 140 | 138 | 107 | 2 | 62 | 57 | corrected valid-human hidden-answer floor; prior-programmatic diagnostic 123/142 |
| 012 dev 007 | 279 | 129 | 118 | 150 | 11 | 92 | 47 | corrected valid-human hidden-answer floor; failed |
| 012 regression 003 | 279 | 108 | 102 | 171 | 6 | 92 | 34 | corrected valid-human hidden-answer floor; failed current front-door report |
| 012 regression 008 | 279 | 182 | 147 | 97 | 35 | 92 | 86 | corrected valid-human hidden-answer floor; fixed regression at 93.5% |
| 013 dev 008 | 266 | 181 | 154 | 85 | 27 | 94 | 85 | corrected valid-human hidden-answer floor; fixed development pass at 90.4% |
| 014 dev 009 | 277 | 194 | 165 | 83 | 29 | 83 | 77 | corrected valid-human hidden-answer floor; fixed development pass at 92.8%; prior-programmatic diagnostic 142/181; API rescue quota failure still documented |

Batch 001 is a two-institution process pilot and does not have the same
benchmark denominator as later batches. Batches before Batch 9 were reported
with the broader all-prior-audit summary. Batch 9 exposed why that is not clean
enough for pass/fail validation: prior programmatic rows can include non-human
or false-positive programmatic discoveries. The current reporting standard is:

- valid human legacy URL rows are the hidden-answer pass/fail benchmark when
  available;
- prior programmatic audit rows are reported separately as a diagnostic;
- neither source is used as a current-run discovery input.

Batch 5 is not clean validation anymore. Because it failed and was used to
diagnose and fix general discovery logic, it is now a regression test. The
latest regression run passes the 90% floor, and earlier passing batches have
been rerun under the same fixed source-review/report contract. Batch 6 exposed
general source-review defects around vendor-hosted catalogs, upload-folder
dates, and Modern Campus/Acalog media buckets. Batch 7 exposed a general
discovery defect for current-site catalog-page paths, visible most clearly in
Creighton's catalog archive page. Those fixes were applied generally and both
batches now pass. Batch 8 exposed additional general discovery defects: useful
repository roots were sometimes crowded out by lower-value seeds, nested archive
pagination was not reached reliably, and simple same-directory catalog PDF
year-range variants were not inferred. Those fixes were applied generally and
Batch 8 now passes. Batch 9 exposed both discovery defects and a benchmark
definition defect. The process now rejects branded HTML placeholder pages that
return HTTP 200, preserves higher-priority archive roots before deduplication,
prefers precise target-year spans over broader contaminated spans for duplicate
URLs, tries bounded high-yield official-domain PDF templates, and includes
generated repository roots such as `img2.<domain>/hu/docs/catalogs/`. The report
now separates valid human legacy recovery from prior-programmatic diagnostic
recovery. Batch 10 exposed additional general defects: SmartCatalog roots could
be crowded out by candidate caps, upload-folder dates could be parsed before
filename catalog years, compact catalog filenames such as
`hccatalog1314final.pdf` were missing, and unlinked Modern Campus media PDFs
needed a bounded official-host media probe. Regression 004 passes after those
general fixes. It also shows a production concern: the inferred/template rescue
step took roughly a quarter hour on this small batch, so broad production needs
batching or optimization before scaling. Batch 11 exposed additional general
defects: CourseLeaf previous-editions pages needed to be treated as archive
sources, registrar archive-page seeds were missing for some official domains,
high-yield official-domain PDF templates could still be crowded out inside the
candidate cap, and source review needed a longer timeout for large PDFs.
Regression 001 passes after those general fixes. Batch 12 exposed several
additional URL-stage defects: inferred/template rescue could generate useful
official-domain PDF URLs but still missed target years, WordPress media API
search needed better candidate ranking, compact catalog filenames such as
`Lafayette-College_11_12.pdf` needed source-review support, official
library/archive roots needed to be generated, CONTENTdm collections needed API
expansion, and JSON metadata needed to count as source-review evidence.
Regression 008 passes after those general fixes. The next production blocker
check showed Batch 13 still needed a fix cycle: missing middle years needed
prior-year span probes, source review needed bounded post-parallel retry for
Wayback/catalog transient failures, archived original URLs needed to count as
catalog-policy context, and archived undergraduate index pages needed a narrow
child-source fallback. Batch 13 passes after those general fixes, but is not a
clean untouched validation pass. Batch 14 exposed further general defects:
compact full-year spans such as `20012003`, short institution/domain labels in
external storage paths, high-yield archive PDF filename shapes, S3 catalog
storage, soft-redirect fake PDFs, risky `catalogarchive` roots outranking
retrieved direct PDFs, and `undergraduate and graduate catalog` source-review
false negatives. A final general repair added Ex Libris/Primo PNX collection
search and made archive-expansion evidence outrank stale generated URL probes.
Those deterministic/source-review fixes improved the batch from 22/83 valid
human legacy rows recovered (26.5%) to 77/83 (92.8%) in the latest front-door
files. Batch 14 also exposed an operational
production blocker: the API rescue layer was called, but every root/archive and
year-gap API triage row failed with OpenAI quota error 429
`insufficient_quota`.

## Reproducibility Checks Completed

For all passing active batches and fixed development/regression evidence:

- `REQUIREMENTS_STATUS.csv` exists; passing batches have all requirement rows
  pass, including the fixed Batch 14 report.
- `OUTPUT_urls_for_text_extraction.csv` has one row per `unitid` and
  `academic_year`.
- No row is stuck at `candidate_needs_source_review`.
- Ready rows have a nonblank URL for text extraction.
- No-candidate and rejected rows remain visible with status/stop information.
- Batch 14 records API rescue failure in `api_rescue_summary.csv` rather than
  silently treating API rescue as successful.
- `input_manifest.csv` and `output_manifest.csv` exist in the audit folder.
- Manifest paths exist and SHA-256 hashes match the current files.
- The URL-stage report states that policy text extraction and policy
  classification are deliberately not performed in Step 1.
- Current reports separate valid human legacy recovery from prior-programmatic
  diagnostic recovery. The former is the pass/fail floor; the latter is a
  regression screen only.

The focused contract test now matches the latest Batch 14 snapshot and passes.
If Batch 14 changes again before it is frozen, rerun the same test and update
the expected values only after choosing the frozen count.

## What Meets The URL-Stage Standard

The pilot process now has the key ingredients required by the URL-stage
standards:

- A fixed target batch and stated denominator.
- A current-run production command path.
- Candidate URLs treated as candidates, not evidence.
- API-assisted URL rescue documented as candidate generation only.
- Source review or cached validated evidence replay required before a row can
  enter the text-extraction handoff.
- Stage-specific and rolling attrition.
- Loss buckets for stopped rows.
- Front-door handoff CSVs that keep unsuccessful rows visible.
- Input/output manifests with file sizes, row counts where applicable, and
  SHA-256 hashes.
- Hidden-answer benchmark checks against valid human legacy URL rows when
  available, with prior-programmatic rows shown separately as diagnostics.

## Main Remaining Limitations

These are limitations of the current state, not necessarily defects in the
pilot artifacts:

- The pilots are still validation slices, not a full production run.
- Pilot rates should not be described as production coverage rates.
- Batch 001 is too small and has no old-audit benchmark comparison.
- The URL stage alone does not establish text retrieval, policy excerpt search,
  policy classification, adjudication, or final panel quality.
- Current tests verify the front-door contract and manifests, but they do not
  rerun live network/API discovery. Live reruns require approved network access
  and should be logged as separate production or validation runs.
- Batch 14 shows the current API quota/configuration is not production-ready:
  all URL-rescue API triage rows failed with quota error 429.
- Batch 14 artifacts changed during review and now pass after fixes; freeze the
  run before copying its counts into a replication package.
- The invalid Mini Full Production Test 001 remains useful only as a diagnostic.
  Its output files were edited after its output manifest was generated, so do
  not treat that folder as replication evidence unless its invalid/superseded
  record is regenerated with matching hashes.
- The final journal package still needs package-local run order, scores, loss
  buckets, cached API/model outputs where used, and a validation report that can
  be regenerated without relying on scattered historical folders.

## Required Review Controls Before Replication Fold-In

Before copying these batch results into replication-package files:

1. Treat the current Batch 14 counts as fixed development evidence, not as
   clean untouched validation or a production-ready result.
2. If Batch 14 is rerun, regenerate its front-door output, requirements file,
   benchmark report, manifests, and this process review together.
3. Keep the Batch 14 expected values in
   `tests/test_step1_pilot_report_contract.py` aligned with the frozen count.
4. Keep `CURRENT_STATUS_AND_NEXT_STEPS.md`, `START_HERE.md`,
   `01_url_discovery/README.md`, `CLEAN_REBUILD_VALIDATION_PLAN.md`, and
   `AUDIT_TRAILS/START_HERE.md` aligned with the same Batch 14 count.
5. Keep Mini Full Production Test 001 out of the replication evidence set, or
   regenerate its invalid/superseded manifest if it must remain in a checked
   audit inventory.
6. Do not count API-assisted rescue as available while the API rescue layer has
   zero parsed rows and 39 quota-error rows.

## Required Before Production Handoff

Before Step 1 can be called production complete:

1. Freeze the full URL-discovery target panel and denominator.
2. Restore or confirm API quota/configuration before counting API-assisted
   rescue as available evidence.
3. Run the approved Step 1 process on the full target panel or a pre-specified
   production tranche after the development stopping rule is met: all
   accumulated regressions pass and three consecutive new development batches
   pass the valid-human hidden-answer recovery floor without batch-specific
   fixes.
4. Preserve all no-candidate and rejected rows in the handoff/status file.
5. Run the same manifest, source-review, attrition, and benchmark checks used
   for the pilots.
6. Report sector-specific and combined URL/source recovery against the relevant
   held-out human legacy benchmark.
7. Decide explicitly whether remaining URL losses are acceptable before Step 2.

## Required Before Journal Submission

Before this work is journal-replication ready:

1. Build the self-contained clean rebuild validation package described in
   `CLEAN_REBUILD_VALIDATION_PLAN.md`, or freeze an equivalent production
   package.
2. Make every reported metric regenerate from package-local files.
3. Include stage-specific score files and loss buckets for URL discovery, text
   retrieval, policy excerpt search, policy classification, and final panel
   variables.
4. Archive prompt/schema/model/config/raw response/parsed response artifacts for
   any LLM/API-assisted classification or URL rescue relied on in reported
   results.
5. Include human adjudication files for the validation sample and document
   override rates.
6. Keep pilot outputs clearly labeled as process validation, not final
   production evidence.

## Bottom Line

The cleaned Step 1 pilot, regression, and development folders through Batch 14
are understandable and auditable enough to show exactly where the process
stands. They are not, by themselves, the production database or the journal
replication package. Batch 14 now passes after general fixes; pause before
starting another batch so the next development or production-chunk plan is
explicit.
