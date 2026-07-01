# URL Discovery Production Chunks Review

Created: 2026-06-30

This is the process review for the transitional Step 1 URL-discovery
production-shaped chunk. It is separate from `url_discovery_pilot_batches_review.md`,
which is only for historical pilot, development, and regression batches.

Status update: the reviewed artifact has been moved out of the production-facing
output tree because it depended on old pilot runtime inputs. It is retained under
`artifacts/PILOTS/url_discovery/` as transitional pilot/history evidence, not as
the clean production-runner template.

## Scope

Reviewed production chunk:

```text
artifacts/PILOTS/url_discovery/pipeline_outputs/transitional_production_chunk_001/
artifacts/PILOTS/url_discovery/audit_trails/transitional_url_discovery_production_chunk_001/
```

Production Chunk 001 was built from fixed Batch 14 prior reviewed evidence:

```text
prior_batch_slug: pilot_batch_014_dev_009
```

This is not a clean no-legacy benchmark. It is a bounded source-ledger
construction package.

## Standards Applied

The production-chunk lane is governed by:

```text
docs/replication_standards/requirements_checklist.md
docs/replication_standards/codex_goals/step_1_url_discovery_run_contract.md
docs/replication_standards/supporting_rules/benchmark_protocol.md
docs/replication_standards/supporting_rules/journal_replication_submission_draft_current.md
```

The relevant production-chunk requirements are:

```text
100 percent target-row accounting in source-ledger or unresolved rows
accepted sources must have review evidence
unresolved rows must have explicit stop reasons
valid human legacy rows may be recovered, carried forward with human-legacy provenance, or row-invalidated
prior-programmatic rows must be recovered by current-run review or row-invalidated
old programmatic evidence alone cannot promote a row into the source ledger
current-run recovery must be reported separately from any human-legacy carry-forward
production chunks are working construction units, not journal-ready releases by themselves
final journal releases must be frozen production_release packages
release commands must be runnable from package-local relative paths, not local absolute paths
release code state must be frozen by commit or archived source bundle, not only a dirty working tree flag
required rebuilds must run from frozen ledgers, cached/archived source artifacts, code, and cached model outputs without live Codex repair or live rediscovery
```

## Chunk 001 Checks Completed

The checked files exist in the production chunk folder:

```text
README.md
CHUNK_REPORT.md
OUTPUT_urls_for_text_extraction.csv
OUTPUT_source_ledger_delta.csv
UNRESOLVED_ROWS.csv
BENCHMARK_RECOVERY.csv
BENCHMARK_MISSES.csv
REQUIREMENTS_STATUS.csv
MANIFEST.json
```

Row accounting checks:

```text
target institution-year rows: 277
institutions: 19
ready/source-ledger rows: 204
unresolved rows: 73
duplicate unitid-year rows: 0
ready rows missing from ledger: 0
not-ready rows missing from unresolved table: 0
ledger/unresolved overlap: 0
```

Requirement checks:

```text
REQUIREMENTS_STATUS.csv: 11/11 pass
BENCHMARK_MISSES.csv: 0 rows
```

Programmatic verification:

```text
pytest -q tests/test_production_chunk_url_discovery.py
4 passed
```

## Current-Run Reattempt Result

Production Chunk 001 was rerun after applying the stricter rule that
prior-programmatic evidence cannot enter the source ledger from old evidence
alone. The 39 prior-programmatic benchmark misses were sent through a current-run
reattempt review:

```text
current_run_reattempt_queue.csv:                 39 benchmark-miss rows
current_run_reattempt_source_review_auto.csv:    39-row raw automated review
current_run_reattempt_manual_adjudications.csv:  11 PDF text inspections
current_run_reattempt_source_review.csv:         39-row final reattempt review
```

The reattempt review accepted all 39 rows under the current source-review
standard:

```text
prior-programmatic benchmark rows: 181
recovered by current-run review:   181
promoted from prior evidence:        0
current-run misses:                  0
```

The first automated reattempt accepted 28 rows and rejected 11. The 11 rejected
rows were manually/Codex inspected by opening the retrieved PDFs and checking
institution, source type, and year evidence. Those 11 were then accepted with
explicit adjudication notes:

```text
Jacksonville State University: 2002, 2003
McKendree University: 2010
Jackson State University: 2009
Meredith College: 2008, 2009, 2010, 2013, 2014, 2015, 2016
```

The key evidence pattern was explicit PDF text such as institution name plus
undergraduate catalog/catalogue year. The raw automated review is preserved
separately from the final adjudicated review.

## Benchmark Status

```text
BENCHMARK_RECOVERY.csv:
  valid human legacy URLs recovered by current run:      83/83
  prior-programmatic URLs recovered by current run:     181/181
BENCHMARK_MISSES.csv:                                     0 rows
REQUIREMENTS_STATUS.csv:                                  11/11 pass
```

This means the previous prior-programmatic promotion concern has been resolved
for Chunk 001. The chunk no longer relies on old programmatic evidence alone for
those rows.

## Post-Rerun Review Notes

Reviewed after the Chunk 001 rerun on 2026-06-30.

Confirmed checks:

```text
target rows:                         277
ready/source-ledger rows:            204
unresolved rows:                      73
duplicate unitid-year rows:            0
ready rows missing from ledger:        0
not-ready rows missing unresolved:     0
ledger/unresolved overlap:             0
BENCHMARK_MISSES.csv rows:             0
REQUIREMENTS_STATUS.csv non-pass:       0
manifest hash mismatches:              0
```

The focused production-chunk test also passes:

```text
.venv/bin/python -m pytest policy_scraper/tests/test_production_chunk_url_discovery.py
4 passed
```

Current-run reattempt evidence checks:

```text
current_run_reattempt_queue.csv rows:                 39
current_run_reattempt_source_review_auto.csv rows:    39
current_run_reattempt_source_review.csv rows:         39
current_run_reattempt_manual_adjudications.csv rows:  11
current_run_reattempt_retrieved_evidence.csv rows:    35
final reattempt accepted rows:                        39
```

The final reattempt review now supports the stricter prior-programmatic rule:

```text
prior-programmatic rows recovered by current run: 181/181
valid-human rows recovered by current run:         83/83
old programmatic promotions into ledger:             0
```

## Reproducibility Process Fixes

The previous review flagged packaging and evidence-cache issues. The production
process has now been updated and Chunk 001 was regenerated with those fixes.

```text
MANIFEST.json listed in output_manifest.csv:                         yes
exact run command recorded in MANIFEST.json and production_command:   yes
git/code state recorded in MANIFEST.json:                            yes
code_snapshot_manifest.csv written:                                  yes
reattempt queue listed in MANIFEST/input_manifest:                   yes
raw automated reattempt review listed:                               yes
manual adjudications listed:                                         yes
final reattempt source review listed:                                yes
retrieved-evidence table listed:                                     yes
cached source-evidence table listed:                                 yes
cached source-evidence rows:                                         39
cached source text paths and hashes present:                         yes
```

The reattempt source-evidence cache is:

```text
artifacts/PILOTS/url_discovery/audit_trails/transitional_url_discovery_production_chunk_001/current_run_reattempt_cached_source_evidence.csv
artifacts/PILOTS/url_discovery/audit_trails/transitional_url_discovery_production_chunk_001/current_run_reattempt_cached_text/
```

The cache records source URL, retrieval status, final URL, content type, content
length, source body hash, cached text path, cached text hash, and a short
evidence excerpt. This addresses the manual/Codex PDF inspection concern: the 11
manual adjudications now point to package-local hashed text evidence rather than
only to live URL retrieval plus notes.

These are necessary chunk-level fixes, but the construction chunk alone is not
the journal-release artifact under the tightened standards.

## Rerun Review: URL-Stage Release Package

The rerun added a frozen URL-stage release package:

```text
artifacts/PILOTS/url_discovery/pipeline_outputs/transitional_production_release_url_stage_001/
```

Release-package checks now present:

```text
README.md with package-local verification command:         yes
REBUILD_COMMANDS.txt:                                      yes
release_manifest.csv:                                      yes
checksums.sha256:                                          yes
rebuild_check.csv and rebuild_check_log.txt:               yes
data/source_ledger.csv:                                    204 rows
data/reviewed_url_handoff_panel.csv:                       277 rows
data/url_stop_log.csv:                                      73 rows
data/benchmark_misses.csv:                                   0 rows
data/requirements_status.csv non-pass rows:                  0
source_evidence_manifest.csv:                              204 rows
ai_model_output_manifest.csv:                                1 row
environment_manifest.csv:                                    4 rows
code/source_snapshot/ and code_archive_manifest.csv:          yes
```

I reran the package-local verification command from the release root:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=code/source_snapshot/src python -m course_policy.production_release_url_stage --release-root . --verify-only
files_checked=85
unmanifested_failures=0
local_absolute_path_failures=0
status=pass
```

This resolves several of the prior fail reasons for the URL-stage release lane:
there is now a named `production_release_*` package, an archived source snapshot,
a package-local verification command, release manifests/checksums, and a clean
verification log for the files the release currently tracks.

Current-stage release-package checks after the latest rerun:

```text
release_status.csv url_stage_source_review:                 pass
release_manifest.csv rows:                                  85
release_manifest.csv paths:                                 package-local
rebuild_check.csv rows / non-pass rows:                     85 / 0
rebuild_check_log.txt status:                               pass
local absolute path failures reported by verifier:            0
release data/audit CSV fields with local absolute paths:      0
source_evidence_manifest rows with local absolute paths:      0/204
unmanifested files after documented exclusions:               0
manifest_exclusions.csv rows:                                 4
__pycache__ / .pyc files present in release package:          0
code_state.csv authoritative release code:                  archived_source_bundle
```

Scope note:

```text
release_status.csv journal_release_ready:                   fail
```

That `journal_release_ready` value is expected at Stage 1 and is not counted as
a current-stage URL-discovery failure. Step 1, by definition, does not include
downstream text retrieval, policy excerpt search, classification, adjudication,
final panel construction, or final analysis outputs.

The previous local-path problem has been resolved for release data and audit
CSV fields. I checked these release files and found no `/Users/...`, `/Dropbox/`,
or leading absolute-path values in their fields:

```text
data/source_ledger.csv
data/reviewed_url_handoff_panel.csv
data/url_stop_log.csv
data/candidate_url_ledger.csv
data/benchmark_recovery.csv
data/source_review_log.csv
source_evidence_manifest.csv
audit/input_manifest.csv
audit/output_manifest.csv
audit/construction_chunk_manifest.json
```

The remaining `/Users/` strings are only generic validation strings inside the
archived source code and tests. They are not local machine paths recorded as
release evidence.

The verification run leaves four files outside `release_manifest.csv`, but they
are now documented in `manifest_exclusions.csv` and the verifier reports
`unmanifested_failures=0`:

```text
checksums.sha256
release_manifest.csv
rebuild_check.csv
rebuild_check_log.txt
```

The package README now uses `PYTHONDONTWRITEBYTECODE=1` in the verification
command, and no Python bytecode cache files are present in the release package.

## Review Decision

Current-stage decision after the rerun:

```text
PASS for Step 1 source-review content and benchmark requirements.
PASS for Step 1 URL-stage release packaging.
NOT APPLICABLE for downstream/final-journal stages at Stage 1.
```

Component status:

```text
Step 1 production-chunk row accounting:                 PASS
Prior-programmatic current-run recovery check:          PASS
Chunk-level evidence-cache and manifest improvements:   PASS
URL-stage release package exists and self-verifies:     PASS
URL-stage release portability/manifest completeness:    PASS
Downstream/final-journal stages:                        NOT APPLICABLE AT STAGE 1
```

Why this is now a current-stage pass:

1. Source-ledger accounting remains closed for the chunk: 277 target rows, 204
   ready/source-ledger rows, 73 unresolved rows, no ledger/unresolved overlap,
   and no missing ready or not-ready rows.
2. The benchmark requirements remain satisfied: `BENCHMARK_MISSES.csv` has 0
   rows, prior-programmatic current-run recovery is 181/181, and valid-human
   current-run recovery is 83/83.
3. The URL-stage release package self-verifies from the release root with
   85 files checked, 0 non-pass rebuild checks, 0 unmanifested failures, and
   0 local absolute path failures.
4. Release data and audit CSVs now use package-local paths or hash references
   rather than local Dropbox paths.
5. `code_state.csv` identifies `code/source_snapshot` as the authoritative
   release code. The dirty git flag is still disclosed as construction-workspace
   metadata, but it no longer replaces the archived source bundle for this
   URL-stage package.
6. Downstream stages are not considered defects for this current-stage decision;
   they are later-stage scope items.

Current-stage conditions to preserve in future URL-stage chunks:

1. Keep the raw automated reattempt review separate from manual/Codex
   adjudications.
2. Do not count prior-programmatic evidence as recovered unless current-run
   retrieval/review accepts it or the row is explicitly invalidated.
3. Continue reporting source-ledger unresolved rows separately from benchmark
   current-run misses.
4. Keep every reattempt evidence file in the manifest/input manifest.
5. Keep package-local cached text evidence and hashes for accepted reattempt
   rows, especially manual adjudications.
6. Record the exact run command, git state, and code snapshot for every
   production chunk.
7. Create a frozen `production_release_*` package with package-local relative
   paths, a master README, exact command block, run order, environment record,
   release manifest, and source-evidence manifest.
8. Keep release data/audit fields free of local absolute paths; use
   package-local paths, hash-only evidence references, or clearly labeled
   construction-only audit fields.
9. Suppress generated `__pycache__`/`.pyc` files with
   `PYTHONDONTWRITEBYTECODE=1` during verification.
10. Manifest/hash every required release file and document any self-referential
    or verifier-generated exclusions in `manifest_exclusions.csv`.
11. For each URL-stage release, state whether the archived source bundle or a
   clean commit is the authoritative release code, and document any
   differences from the public repository snapshot.
12. Run and preserve a clean release-package rebuild check from the release root.

Later-stage requirement, not part of the current Stage 1 pass/fail decision:

```text
Add downstream stage artifacts and documentation before making a full journal
replication-package claim: text retrieval, excerpt search, classification,
adjudication, final panel construction, final data availability, and downstream
AI/model-use manifests.
```

## Scale Drill 003 Review

Reviewed on 2026-07-01 after the latest Drill 3 rerun.

Reviewed artifacts:

```text
artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_chunks/production_chunk_scale_drill_003/
artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_scale_drill_003/
artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_inputs/production_scale_drill_003_reviewfix/
```

Current-stage decision:

```text
FAIL for production-scale Step 1 URL-discovery readiness.
PASS only for clean production-runner row-accounting and release-package mechanics.
NOT A FULL JOURNAL RELEASE because downstream stages are outside this Stage 1 package.
```

This is a fail at the current URL-discovery stage, not merely a downstream
journal-release fail. The chunk report correctly says that the machinery ran, but
the output does not meet the tightened production-readiness standard for moving
to larger production construction.

Evidence checked:

```text
target_panel.csv rows:                         444
candidate_url_ledger input rows:               114
source_review_log input rows:                  444
ready/source-ledger rows:                       57
unresolved rows:                               387
ready rate:                                   12.8%
unresolved rate:                              87.2%
no-candidate target rows:                      330
source-review rejected rows:                    57
private accepted rows:                      54/240
public accepted rows:                         3/204
benchmark_key.csv rows:                          0
BENCHMARK_RECOVERY.csv rows:                     0
BENCHMARK_MISSES.csv rows:                       0
REQUIREMENTS_STATUS.csv:                       7/7 pass
release_manifest.csv rows:                      43
release rebuild check non-pass rows:             0
release rebuild_check_log.txt status:          pass
release manifest local/pilot path hits:          0
```

Main findings:

1. The generated `REQUIREMENTS_STATUS.csv` is a mechanical contract pass, not a
   production-readiness pass. It checks that every target row is either ready or
   unresolved, that accepted rows have review fields, that unresolved rows have a
   reason, and that the release files exist. Those checks are necessary, but they
   do not prove adequate URL discovery when 387 of 444 target rows remain
   unresolved.
2. The benchmark result is not interpretable. `benchmark_key.csv` has 0 rows, so
   `BENCHMARK_RECOVERY.csv` and `BENCHMARK_MISSES.csv` having 0 rows only means
   there was no benchmark denominator. This cannot be described as recovery
   success, and it cannot satisfy the prior-programmatic recovery rule.
3. Candidate generation coverage is not sufficient for a production-scale drill.
   The input candidate ledger has 114 rows for 444 targets, and the release
   candidate table shows 330 target rows with `no_candidate_found` and blank
   candidate-generation method. Under the tightened checklist, a production-path
   URL test must show the search/rescue path used or document why API/web rescue
   was not eligible or not needed.
4. Public-sector performance is especially not ready for scale: only 3 of 204
   public target rows reached the source ledger. A release package can verify
   cleanly and still fail as source-discovery evidence when one sector effectively
   collapses.
5. The release package is mechanically cleaner than the earlier transitional
   package: it has package-local paths, a package-local verify command, no pilot
   runtime dependency in the manifest, and a passing rebuild check. That packaging
   pass does not override the source-discovery fail.
6. The accepted-row source evidence is not yet portable enough to support a
   journal-facing source-evidence claim. `source_evidence_manifest.csv` has 57
   accepted rows, but they are marked `source_url_and_review_evidence_only`; the
   cached text path, cached text hash, and source body hash fields are blank.
   That may be acceptable as a URL-stage construction limitation if disclosed,
   but it should not be counted as portable cached source evidence.
7. `release_status.csv` currently says `url_stage_source_review: pass` because
   the package was built from a "passing production chunk." That label is too
   broad for Drill 3. The release can be called a packaging/rebuild pass, but the
   source-review/content status should be fail or explicitly limited to
   clean-runner mechanics.

Corrections required before treating Drill 3 as ready for the next larger
production batch:

1. Reclassify Drill 3 as a failed production-scale URL-discovery drill unless a
   rerun materially improves coverage and resolves the benchmark denominator
   problem. Do not use the 7/7 mechanical requirements status as the go/no-go
   decision.
2. Add a nonempty benchmark key when making any benchmark or prior-programmatic
   recovery claim. If no benchmark is intentionally supplied, the report must say
   "benchmark not tested" rather than treating 0 misses as a pass.
3. Add explicit coverage/readiness gates to the requirements output: ready rate by
   sector and combined, no-candidate count, candidate-generation coverage, and a
   rule that a zero-row benchmark denominator is not a benchmark pass.
4. For rows with `no_candidate_found`, record the actual search attempts and
   bounded rescue path. If API/web rescue is not run, document why it was
   ineligible or intentionally out of scope; otherwise the deterministic-only
   drill cannot pass as the full production URL path.
5. Strengthen the release status language so it separates:
   `clean runner/rebuild package pass`, `source-discovery content pass/fail`,
   `benchmark tested/not tested`, and `full journal release ready/not ready`.
6. Package or document source evidence for accepted rows. If cached source text
   cannot be redistributed, the Data Availability Statement should say so and
   preserve URL, retrieval metadata, hashes or stable identifiers where available.
   Blank cached-text/hash fields should not be silently counted as source-evidence
   portability.
7. Re-run Drill 3 only after the candidate-generation/rescue and benchmark
   corrections are in place, then rerun the package-local release verification
   from the release root.

Until those corrections are made, Drill 3 should be retained as a useful
clean-runner and attrition diagnostic, not as evidence that Step 1 is ready for a
larger production batch.

## Scale Drill 005 Review

Reviewed on 2026-07-01 as the latest production chunk report.

Reviewed artifacts:

```text
artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_chunks/production_chunk_scale_drill_005/
artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_scale_drill_005/
artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_inputs/production_scale_drill_005/
```

Current-stage decision:

```text
FAIL for journal-grade Step 1 benchmark/readiness claims.
FAIL because generated pass criteria were not tied back to the binding guidelines.
PASS for clean production-runner mechanics and release-package rebuild.
PARTIAL PASS for source-ledger construction because row closure and accepted-row evidence are much improved.
NOT A FULL JOURNAL RELEASE because downstream stages are outside this Stage 1 package.
```

This is a major improvement over Drill 003, but it should still be treated as a
failed readiness review if the question is whether Step 1 is ready to scale as a
journal-grade production process.

Binding-guideline enforcement note:

```text
The binding guidelines must be reviewed and met before a production chunk can be
called pass. A run-config threshold, generated `REQUIREMENTS_STATUS.csv` row, or
chunk-report pass label is not authoritative unless it is traceable to the
binding checklist and does not weaken that checklist. If the runner/report uses
unsupported or weaker thresholds, or omits a required guideline check, that is
itself a reproducibility failure.
```

Evidence checked:

```text
target_panel.csv rows:                         375
institutions:                                   25
target rows by sector:                  private 300; public 75
candidate_url_ledger.csv rows:                 349
human-legacy candidate rows:                   333
non-legacy/current-discovery candidate rows:    16
ready/source-ledger rows:                      307
unresolved rows:                                68
combined ready rate:                         81.9%
private ready rate:                         276/300 = 92.0%
public ready rate:                           31/75 = 41.3%
benchmark_key.csv rows:                        333
BENCHMARK_RECOVERY.csv rows:                   333
BENCHMARK_MISSES.csv rows:                       0
current-run benchmark recovered:           295/333 = 88.6%
current-run benchmark not recovered:            38
joined private benchmark recovery:         276/300 = 92.0%
joined public benchmark recovery:            19/33 = 57.6%
REQUIREMENTS_STATUS.csv:                     12/12 pass
release_manifest.csv rows:                    393
release rebuild check non-pass rows:            0
release rebuild_check_log.txt status:         pass
release manifest local/pilot path hits:         0
accepted source-evidence rows:                307
accepted rows with cached text available:     307
cached text files missing from release:          0
```

Main findings:

1. The runner/report generated pass criteria instead of only applying binding
   criteria. That is a reproducibility failure in itself. Generated artifacts may
   calculate diagnostics, but they must not define, invent, or weaken pass/fail
   standards. A production chunk can pass only against criteria that already exist
   in the binding documentation or an approved versioned standards file.
2. The generated requirements file is still too permissive for the benchmark
   claim. It marks `benchmark_misses_resolved_when_key_present`,
   `benchmark_denominator_status`, and `source_discovery_sector_ready_rate` as
   pass, but the release `stage_rates.csv` reports only 295/333 current-run
   benchmark recovery, or 88.6%. The written benchmark target is at least 90%
   recovery by sector and combined when the benchmark is being used as a clean
   no-legacy recovery test.
3. The by-sector benchmark target is not directly auditable from
   `BENCHMARK_RECOVERY.csv` because the file lacks `sector` and denominator
   fields. Joining it back to `target_panel.csv` shows private benchmark recovery
   at 276/300 (92.0%) but public benchmark recovery at only 19/33 (57.6%). That is
   a substantive fail, not a cosmetic reporting issue.
4. `BENCHMARK_MISSES.csv` is empty because 38 benchmark rows are coded
   `row_invalidated_by_current_review`, not because every benchmark row was
   recovered by the current run. That can be valid source-ledger accounting if the
   invalidations are evidence-backed, but it cannot be summarized as a benchmark
   recovery pass without separating current-run recovery, invalidated legacy rows,
   and true misses.
5. The benchmark is not a hidden no-legacy discovery benchmark. All 333 benchmark
   URLs also appear in `candidate_url_ledger.csv` as `human_legacy_url` candidate
   rows. That means the benchmark result is a legacy URL review/carry-forward
   test, not proof that the current discovery machinery can rediscover those URLs
   when legacy URLs are withheld.
6. Public-sector source discovery remains weak for scaling. The full target-panel
   public ready rate is 31/75 (41.3%), and 44/75 public rows remain unresolved.
   The generated report relied on a 30% sector floor from `run_config.json`; that
   floor is not a binding guideline and should not be allowed to convert weak
   public-sector performance into a pass.
7. API/web rescue was documented as not run. That is acceptable only for a
   bounded ledger drill. It should not be described as a full production-path URL
   test while 68 rows remain unresolved, including 26 `no_candidate_found` rows.
8. The release packaging and source-evidence portability are substantially better:
   the package verifies from package-local files, paths are package-local, accepted
   rows have cached text and hashes, and the 307 cached accepted-source files are
   present. Those are real passes, but they do not repair the benchmark/design
   problem.
9. `data_availability.csv` still says cached source text is stored under
   `audit/current_run_reattempt_cached_text`, while the actual Drill 005 release
   stores the accepted-source cache under `audit/source_evidence_cache`. That
   documentation mismatch should be corrected before any journal-facing release.

Corrections required before treating Drill 005 as ready for larger production
scale:

1. Add a required binding-guideline crosswalk before any future pass claim. The
   chunk report or requirements file must cite the controlling guideline,
   acceptance criterion, observed value, and pass/fail result for each URL-stage
   rule. A missing crosswalk is itself a fail.
2. Remove or relabel unsupported run-config pass thresholds. Any threshold used
   for pass/fail must come from the binding docs or be explicitly documented as a
   diagnostic-only drill threshold that cannot override the binding checklist.
3. Change the Drill 005 go/no-go language from `URL-stage production requirements:
   pass` and `Benchmark status: pass` to a limited status such as:
   `runner/release package pass; source-ledger construction partial pass;
   benchmark/readiness fail`.
4. Revise benchmark reporting so `BENCHMARK_RECOVERY.csv`, `stage_rates.csv`, and
   the chunk report separately report:
   current-run recovered rows, row-invalidated legacy rows, unresolved benchmark
   misses, active benchmark denominator, and sector-specific denominators.
5. Do not count `row_invalidated_by_current_review` rows as current-run benchmark
   recoveries. If they are removed from the active benchmark denominator, document
   the evidence-backed invalidation reason and report both the original and active
   denominators.
6. Add `sector` and benchmark-denominator fields directly to
   `BENCHMARK_RECOVERY.csv` and `BENCHMARK_MISSES.csv`; the benchmark standard
   should not require a separate join to discover public-sector failure.
7. Separate legacy-candidate review from clean no-legacy discovery. If human
   legacy URLs are used as candidate input, describe the result as a legacy
   validation/carry-forward drill, not a hidden benchmark recovery test. Run a
   separate held-out benchmark if the claim is discovery reproducibility.
8. Either run the bounded API/web rescue path or keep the claim limited to a
   bounded deterministic-plus-legacy drill. Do not call it a full production-path
   URL test until the configured rescue path is included or ruled out row by row.
9. Fix `data_availability.csv` so it names the actual cached evidence location
   for Drill 005: `audit/source_evidence_cache`.

Until these corrections are made, Drill 005 should be retained as a useful
mechanical/release-package success and a strong source-evidence-cache improvement,
but not as evidence that the Step 1 production process is ready for larger
journal-grade scaling.

## Scale Drill 006 Review

Reviewed on 2026-07-01 as the latest production chunk report after the Drill 005
failure notes.

Reviewed artifacts:

```text
artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_chunks/production_chunk_scale_drill_006/
artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/production_release_scale_drill_006/
artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_inputs/production_scale_drill_006/
```

Current-stage decision:

```text
FAIL for ready-to-scale / journal-grade Step 1 production readiness.
PASS for clean production-runner mechanics and release-package rebuild.
PARTIAL PASS for source-ledger accounting, legacy carry-forward accounting, and cached source evidence.
NOT TESTED for clean no-legacy discovery benchmark.
NOT A FULL JOURNAL RELEASE because downstream stages are outside this Stage 1 package.
```

Drill 006 improves the reporting language from Drill 005. It no longer claims a
clean no-legacy benchmark pass, and it labels ready-to-scale status as
`under_review`. This review resolves that `under_review` status as fail for
larger production scaling.

Evidence checked:

```text
target_panel.csv rows:                         375
institutions:                                   25
target rows by sector:                  private 300; public 75
candidate_url_ledger.csv rows:                 349
human-legacy candidate rows:                   333
non-legacy/current-discovery candidate rows:    16
ready/source-ledger rows:                      307
unresolved rows:                                68
combined ready rate:                         81.9%
private ready rate:                         276/300 = 92.0%
public ready rate:                           31/75 = 41.3%
public unresolved rows:                         44
no-candidate rows:                              26
source-review rejected rows:                    42
benchmark_key.csv rows:                        333
BENCHMARK_RECOVERY.csv rows:                   333
BENCHMARK_MISSES.csv rows:                       0
current-run benchmark recovered:           295/333 = 88.6%
benchmark rows invalidated by review:           38
private benchmark current-run recovery:     276/300 = 92.0%
public benchmark current-run recovery:        19/33 = 57.6%
accepted source-evidence rows:                307
accepted source-evidence provenance:      prior_human 295; new_programmatic 12
accepted rows with cached text available:     307
release_manifest.csv rows:                    395
release rebuild check non-pass rows:            0
release rebuild_check_log.txt status:         pass
release manifest local/pilot path hits:         0
```

Main findings:

1. Drill 006 is more honest than Drill 005, but it still fails the production
   readiness question. `clean_no_legacy_benchmark` is correctly marked
   `not_tested`, and `ready_to_scale_claim` is marked `under_review`; the human
   review decision is that the chunk is not ready to scale.
2. Clean no-legacy discovery was not tested. All 333 benchmark rows are raw human
   legacy URLs, and the candidate ledger includes those same human legacy URLs as
   inputs. That supports a legacy carry-forward/review lane, not a hidden
   rediscovery benchmark.
3. Current-run benchmark recovery is below the documented benchmark target if this
   were treated as a recovery benchmark: 295/333 overall (88.6%) and 19/33 public
   (57.6%). The 38 invalidated rows are now separated more clearly, which is an
   improvement, but invalidation is not current-run recovery.
4. Public-sector coverage is still too weak for scaling. Only 31/75 public target
   rows are ready for text extraction, 44/75 public rows remain unresolved, and
   public current-run benchmark recovery is 57.6%.
5. The run is still not the full production URL path. `api_web_rescue_mode` is
   `not_run` for every row and `api_web_rescue_status` is
   `documented_limited_scope_not_full_production_path`. Under the binding
   checklist, a deterministic-only run cannot pass as the full production path
   while unresolved rows remain unless rescue is ineligible or not needed.
6. The source-ledger is heavily legacy-backed. Among 307 accepted source-evidence
   rows, 295 are `prior_human` and only 12 are `new_programmatic`. That may be
   useful for ledger construction, but it is not enough evidence that the current
   discovery process can scale independently.
7. `REQUIREMENTS_STATUS.csv` is now narrower at 10 blocking clean-runner rows and
   does not directly claim ready-to-scale. That is better, but the generated
   requirements still do not themselves confer a pass. The binding review controls
   the readiness decision.
8. Release packaging and source-evidence portability remain real positives: the
   release verifies from package-local files, no local or pilot runtime paths were
   found in the release manifest, accepted rows have cached text/hash references,
   and the Data Availability Statement now names `audit/source_evidence_cache`.

Corrections required before treating Drill 006 as ready for larger production
scale:

1. Keep the Drill 006 status as fail for ready-to-scale production. Do not promote
   it based on clean-runner mechanics, release verification, or legacy-accounting
   closure.
2. Run a clean no-legacy benchmark with human legacy URLs hidden from candidate
   generation, or state explicitly that this chunk only tests legacy
   carry-forward/source-review accounting.
3. Improve public-sector discovery before scaling. The next candidate-generation
   and review pass needs to address the 44 unresolved public rows and the 26 rows
   with no candidate.
4. Run the bounded API/web rescue path, replay cached rescue evidence, or document
   row-level reasons why rescue is not eligible or not needed. A global
   `not_run` status is not enough for a full production-path claim.
5. Continue separating current-run recovery from row invalidation. Invalidated
   rows can close ledger accounting only when their invalidation evidence is
   preserved, but they must not be counted as discovery recovery.
6. Add an explicit human-review result to the release status for
   `ready_to_scale_claim`, rather than leaving it as `under_review` after this
   process review.
7. Keep the Drill 006 reporting improvements: sector fields in benchmark files,
   original and active benchmark denominator fields, separate invalidation counts,
   package-local cached source evidence, and corrected data-availability language.

Until these corrections are made, Drill 006 should be retained as a cleaner
diagnostic/release package and a better legacy-accounting artifact, not as
evidence that Step 1 is ready for larger journal-grade production.

## Scale Drill 012 Review

Reviewed on 2026-07-01 as the Codex review stream.

Reviewed artifacts:

- `production_chunks/production_chunk_scale_drill_012/CHUNK_REPORT.md`
- `production_chunks/production_chunk_scale_drill_012/REQUIREMENTS_STATUS.csv`
- `production_chunks/production_chunk_scale_drill_012/GUIDELINE_CROSSWALK.csv`
- `production_chunks/production_chunk_scale_drill_012/run_config.json`
- `production_releases/production_release_scale_drill_012/release_status.csv`
- `production_releases/production_release_scale_drill_012/stage_rates.csv`
- `production_releases/production_release_scale_drill_012/data/*`
- `production_releases/production_release_scale_drill_012/audit/*`

Current-stage decision after the latest fixes: **pass for bounded Step 1
URL-stage production readiness and ready to proceed to the next production batch
in the same legacy carry-forward/source-review lane**.

Drill 12 is materially improved over the prior failing drills. It passes the
quantitative source-ledger readiness floors and the clean-runner accounting
checks now use the binding 90 percent combined and 90 percent by-sector
standards. The latest post-fix release also resolves the two remaining
reproducibility blockers from the prior review: API/web-rescue provenance is now
packaged with complete manifest fields and matching hashes, and candidate/source
lineage is now package-local with an internally consistent source-lineage
manifest.

### What now passes

1. **Binding readiness floors are met.**
   The release reports 369 ready/source-ledger rows out of 375 target rows
   (98.4 percent). By sector, private is 300/300 (100.0 percent) and public is
   69/75 (92.0 percent). This satisfies the documented 90 percent combined and
   90 percent by-sector readiness gate for this stage.

2. **Legacy/prior benchmark accounting is now separated from the clean
   no-legacy benchmark.**
   The run reports 333 benchmark rows, 330 current-run recovered rows, 3 rows
   invalidated by review, and 0 unresolved benchmark misses. The three
   non-recovered benchmark rows are accounted for as review-invalidated rather
   than hidden failures. This is acceptable as legacy carry-forward accounting.

3. **Historical-case precheck is present and passes.**
   The historical precheck contains 25 institutions and does not expose URL-like
   fields. This supports the claim that historical cases were used as eligibility
   inputs rather than as direct URL seeds.

4. **Accepted source evidence is packaged with cache/hash evidence.**
   The release source-evidence table contains 369 accepted rows, all with cached
   text paths and hashes. The release manifest rebuild check reports 588 checked
   files with no unmanifested failures and no local-absolute-path failures.

5. **Unresolved rows are visible and bounded.**
   The remaining 6 unresolved rows are all public-sector rows with explicit stop
   reasons and `source_search_or_review_needed` as the next action. They are not
   silently dropped.

6. **API/web-rescue artifacts are now packaged.**
   The release now includes `ai_api_use_statement.csv`,
   `ai_model_output_manifest.csv`, and `audit/ai_api_provenance/`. The AI/model
   manifest contains 14 rows. The manifest now directly records model
   (`gpt-5.4-mini-2026-03-17`), run date/time, prompt/rule version, schema
   version, source-review linkage, and linked AI-candidate counts. The referenced
   prompt, raw-response, parsed-response, triage, and source-review linkage files
   all exist in the release package, and the hashes recorded in
   `ai_model_output_manifest.csv` match the packaged files.

7. **Candidate/source lineage is now package-local.**
   The released `data/candidate_url_ledger.csv` and
   `data/reviewed_url_handoff_panel.csv` now point to package-local
   `audit/source_lineage/...` files for `candidate_source_file` and
   `source_review_file`. The referenced raw workbooks, AI/year-gap panels,
   archive-expansion panel, and source-review log are present inside the release.
   `audit/source_lineage_manifest.csv` now records both original and packaged
   size/hash fields. Independent checks found 67 lineage rows, 0 missing
   packaged files, 0 packaged hash mismatches, and 0 packaged size mismatches.

8. **Release rebuild and package-local evidence checks pass.**
   `rebuild_check_log.txt` reports 588 checked files, 0 unmanifested failures,
   0 local-absolute-path failures, and `status=pass`. Additional checks of the
   source-evidence cache references found 744 handoff/source-ledger cache
   references and 842 source-evidence-manifest cache references with 0 missing
   packaged files.

### Remaining limits, not blockers for the next batch

1. **Clean no-legacy benchmark remains not tested.**
   The report correctly labels the clean no-legacy benchmark as `not_tested`
   because this drill used human legacy URL evidence. That is acceptable only if
   the run is described as a legacy carry-forward/review-lane production drill.
   It cannot be used as evidence that the pipeline can independently rediscover
   all valid historical URLs from clean non-URL inputs.

2. **Six rows remain unresolved before downstream text extraction.**
   The unresolved rows are NJIT 2002, 2005, and 2013, plus Kutztown University
   of Pennsylvania 2014, 2015, and 2016. This does not fail the current
   readiness floor, but the rows must remain visible in downstream handoff and
   should not be treated as completed source evidence.

3. **This is still not a full journal replication package.**
   The release correctly states that downstream text retrieval, extraction,
   policy classification, adjudication, final panel construction, and analysis
   outputs are outside this URL-stage package. That downstream absence should
   not be counted as a Step 1 failure, but it means the package is not a complete
   journal release by itself.

### Required conditions going forward

1. Keep the distinction between legacy carry-forward recovery and clean
   no-legacy rediscovery in the release report. Do not convert the legacy
   benchmark pass into a clean-discovery claim.

2. Preserve the 6 unresolved rows in the handoff with explicit stop reasons and
   next actions until they are resolved or formally excluded by documented
   review.

3. Keep the AI/API provenance package and source-lineage manifest requirements
   as binding gates for the next production batch. Generated reports should not
   self-authorize pass criteria; process review must continue to decide whether
   the binding guidelines are met.

4. If future generated `release_status.csv` files are intended to mirror the
   process-review decision, update `ready_to_scale_claim` from `under_review` to
   a reviewed pass status after this review is incorporated. The current
   `under_review` status is not a substantive blocker because the status file
   explicitly defers the final pass/fail decision to human process review.

With those limits stated, Drill 12 is acceptable as the Step 1 production-release
benchmark for the bounded legacy carry-forward/source-review lane and is ready
to support the next production batch.
