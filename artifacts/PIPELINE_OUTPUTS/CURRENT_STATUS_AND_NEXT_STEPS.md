# Current Status And Next Steps

Reviewed: 2026-07-01
Consistency checked: 2026-07-01
Drill 012 process-review decision incorporated: 2026-07-01
Step 1 production-runner integration review incorporated: 2026-07-01
Step 1 clean-runtime import fix review incorporated: 2026-07-02
Step 1 target-panel materialization fix review incorporated: 2026-07-02
Step 1 production-build workflow adopted: 2026-07-02
Step 1 prior-discovery source reconstruction batch 001 review incorporated: 2026-07-02
Step 1 prior-discovery source reconstruction batch 002 review incorporated: 2026-07-02
Step 1 prior-discovery source reconstruction batch 003 review incorporated: 2026-07-03
Step 1 prior-discovery source reconstruction batch 004 review incorporated: 2026-07-03

This is the active human-facing status register for the policy pipeline. Open
this file for current decisions, next steps, and production-readiness notes.

Terminology note: use `prior-discovery source reconstruction` for this Step 1
lane. The existing reviewed artifact IDs still contain
`prior_valid_reverification` for traceability, but that phrase should be treated
as a frozen run identifier, not the preferred process name.

## 2026-07-03 Step 1 Current URL-Stage Status

Current reviewed Step 1 URL-stage production-test artifacts:

```text
01_url_discovery/production_chunks/production_chunk_step1_prior_valid_reverification_test_batch_004/
01_url_discovery/production_chunks/production_chunk_step1_prior_valid_reverification_test_batch_004/CHUNK_REPORT.md
01_url_discovery/production_releases/production_release_step1_prior_valid_reverification_test_batch_004/
```

Bottom line:

```text
Step 1 prior-discovery source reconstruction batch 004: accepted by process review
Clean-runner requirements:                         14/14 satisfied
Release-local package verification:                verified
Historical case precheck:                          complete; URL-free planning memory only
Legacy/prior benchmark accounting:                 complete
Clean no-legacy benchmark claim:                   not tested
Ready-to-scale URL-stage claim:                    under process-review scope, not journal readiness
Full journal-release claim:                        not claimed
Target institutions:                               28
Target rows:                                      420
Accepted source-ledger rows:                      224
Explicit unresolved rows:                         196
Ready/source-ledger rate:                         53.3%
Ready rate, private:                              64.7%
Ready rate, public:                               25.0%
Benchmark denominator:                            178
Current-run benchmark recovered:                  165
Benchmark rows invalidated by review:              13
Unresolved benchmark misses:                        0
Release-local verifier:                            verified; 818 files checked
```

Interpretation:

```text
Accepted as a Step 1 URL-stage prior-discovery source reconstruction batch.
The batch demonstrates that the clean production runner can build a reviewed
source ledger, unresolved-row table, benchmark accounting, and package-local
release for a prior-discovery lane from clean origin/main.

NOT TESTED for clean no-legacy benchmark recovery because this lane uses
transparent prior-discovery candidates for source reconstruction.

NOT A FULL JOURNAL RELEASE because downstream text extraction, policy
classification, adjudication, final panel construction, and full release
packaging remain later-stage work.
```

Next action:

```text
Start step1_prior_valid_reverification_test_batch_005 from clean origin/main at
or after the batch 004 status update commit. Use the same managed
goal/phase table, rebuild or confirm the durable-quarantine historical
inventory, select the next prior-discovery source reconstruction chunk, and
require a process review before updating this status file again.
```

Review-publication note: the batch 001, batch 002, batch 003, and batch 004
process reviews were completed in their batch worktrees. Publishing those
ignored artifacts into canonical `process_reviews/` should be handled by the
review stream, not by project management.

Batches 001, 002, and 003 remain prior accepted evidence. Together with batch
004, the reviewed prior-discovery source reconstruction lane now covers 112
institutions and 1,671 institution-years.

## 2026-07-01 Prior Step 1 Proof-To-Scale Status

Prior clean URL-stage proof artifacts:

```text
01_url_discovery/production_chunks/production_chunk_scale_drill_012/
01_url_discovery/production_chunks/production_chunk_scale_drill_012/CHUNK_REPORT.md
01_url_discovery/production_releases/production_release_scale_drill_012/
```

Prior Drill 012 bottom line:

```text
Gate 1 clean-runner/source-review mechanics:     pass
Gate 1 source-ledger row accounting:             pass
Gate 1 substantive readiness floors:             pass
Gate 2 release-local packaging mechanics:        pass
Legacy/prior benchmark accounting:               pass
Clean no-legacy benchmark claim:                 not tested
Ready-to-scale URL-stage proof claim:            pass for next larger production chunk
Full journal-release claim:                      not claimed
Target institutions:                              25
Target rows:                                     375
Accepted source-ledger rows:                     369
Explicit unresolved rows:                          6
Ready rate:                                      98.4%
Ready rate, private:                            100.0%
Ready rate, public:                              92.0%
Benchmark denominator:                            333
Current-run benchmark recovered:                  330
Benchmark rows invalidated by review:               3
Unresolved benchmark misses:                        0
Generated blocking checks:                      14/14 pass
Release-local verifier:                          pass
```

Completion rule:

```text
Drill 012 remains the prior successful URL-stage proof-to-scale batch. It has
now been superseded as the current Step 1 status artifact by
step1_prior_valid_reverification_test_batch_001, but remains useful prior
evidence for the clean-runner and release-package path. Drill 012 is not a
clean no-legacy benchmark and it is not a full journal replication package
because downstream text extraction, policy classification, adjudication, final
panel construction, and full release packaging remain later-stage work.
```

Process-review-controlled interpretation:

```text
PASS for clean production-runner mechanics, source-ledger accounting,
legacy/prior benchmark accounting, substantive readiness floors, and
release-package rebuild under the Drill 012 process review.
NOT TESTED for clean no-legacy benchmark recovery because human legacy URLs were
used as transparent candidate provenance.
PASS for moving to the next larger URL-stage production chunk under the same
run contract.
NOT A FULL JOURNAL RELEASE because downstream stages are outside this URL-stage package.
```

Production-runner integration status:

```text
Integration commit: 13f8f792696a43253ecf6ed66a0ae82e42b103da
Review decision: PASS
Review file:
01_url_discovery/process_reviews/step1_production_runner_integration_review.md
Meaning: the clean Step 1 runner/release-packager dependency-closure code is
reviewed for reproducing the Drill 012 style URL-stage release and running the
next larger URL-stage production chunk.
Limit: each generated production chunk still needs its own output/process
review before any ready-to-scale or journal-release claim.
```

Clean-runtime import status:

```text
Import-fix commit: c1779aaa0526ee5d6ca1c1c03e2f040f046fc0bc
Review decision: PASS
Review file:
01_url_discovery/process_reviews/step1_clean_runtime_import_fix_review.md
Clean-runtime import check: PASS with PYTHONPATH=src
Focused tests: 124 passed with PYTHONPATH=src
Meaning: the committed Step 1 production path no longer depends on helper
definitions present only in the dirty original worktree.
Limit: this fixes the clean-runtime blocker only. It is not a production chunk
or production release result. The next larger Step 1 production chunk still
must be rerun from clean main and reviewed before any scale-readiness claim.
```

Target-panel materialization status:

```text
Target-panel fix commit: 7eeff6508e08149c7049fb9bc288ff5c6b6f8d56
Review decision: PASS
Review file:
01_url_discovery/process_reviews/step1_target_panel_materialization_fix_review.md
Clean-runtime import check: PASS with PYTHONPATH=src
Focused tests: 49 passed with PYTHONPATH=src
Touched-helper tests: 7 passed with PYTHONPATH=src
Meaning: the Step 1 production path now materializes
artifacts/policy_data_internal/interim/institution_year_targets.csv from the
explicit Step 1 target_panel before discovery runs, and build_year_panel() can
also consume an explicit target_panel directly.
Limit: this clears the missing target-panel runtime-input blocker only. It is
not a production chunk or production release result. The next larger Step 1
production chunk still must be rerun from clean main and reviewed before any
scale-readiness claim.
```

Step 1 production-build operating mode:

```text
The next Step 1 attempt should use a single production build stream, not the
old testing -> integration -> review handoff for every small source-code bug.

Reason: the project claim is AI-assisted production construction and
reproducibility, not untouched out-of-sample scraper performance. During
construction, Codex may diagnose failures, make general source/test fixes,
commit those fixes, and rerun from clean committed code.

Required boundary: the build stream cannot edit current status, process
reviews, standards, front-door docs, or protected-doc manifest rows. It must not
hard-code row-specific source answers. It must log fixes, tests, reruns, and
remaining risks in a run-local BUILD_LOG.md or SUPERVISOR_RUN_REPORT.md.

Review boundary: generated outputs and build logs are evidence only. A separate
review stream must review the final code/output bundle before any PASS,
ready-to-scale, or journal-readiness claim. Project management updates this file
only after review.
```

Drill 012 replaces Drill 006 as the current URL-stage proof artifact. It keeps
the Drill 006 reporting corrections and adds the missing production-path pieces:
URL-free historical case precheck, bounded API/web rescue evidence, stronger
public-sector recovery, package-local release verification, and a process-review
decision. This remains URL-stage only: downstream text extraction, policy
classification, final panel construction, and final journal replication
packaging are not included.

Folder cleanup updated on 2026-06-30: historical Step 1 URL-discovery pilot,
development, regression, and superseded pilot folders now live together under:

```text
policy_scraper/artifacts/PILOTS/url_discovery/
```

The active review reports remain in:

```text
policy_scraper/artifacts/PIPELINE_OUTPUTS/01_url_discovery/process_reviews/
```

Current production-facing Step 1 outputs remain in:

```text
policy_scraper/artifacts/PIPELINE_OUTPUTS/01_url_discovery/
```

Audit-trail folders are evidence snapshots. They may explain how a specific
artifact was produced, but they should not be the only place where current
process decisions or next actions are recorded.

## Naming Convention Going Forward

Do not create new `pilot_batch_*` folders in the production-output area. The
existing pilot folders are preserved as historical testing, development, and
regression evidence under `policy_scraper/artifacts/PILOTS/url_discovery/`.
New work should use names that state the purpose of the run:

| Name | Use For | Meaning |
|---|---|---|
| `pilot_batch_*` | Existing historical batches only | Prior process tests, development runs, and regression evidence |
| `benchmark_*` | Clean validation tests | Tests of how well the computer can recover hidden human answers without seeing them |
| `production_chunk_*` | Dataset construction chunks | Bounded source-ledger construction for the actual dataset |
| `production_release_*` | Frozen release outputs | Package-ready dataset versions and final reproducible handoffs |

The project is still testing and hardening the URL-discovery process, but the
next dataset-construction outputs should not be called pilots. Historical pilot
batches such as `pilot_batch_014_dev_009` may be used to identify failure modes,
write tests, and improve general code/rules. They should not be normal runtime
inputs to future production chunks. A clean production chunk should have its own
production input manifest, source-ledger delta, unresolved-row table, report, and
manifest rather than converting an old pilot folder into production evidence.

Recommended production folder layout:

```text
PIPELINE_OUTPUTS/
  01_url_discovery/
    production_chunks/
      production_chunk_<clean_runner_id>/
        README.md
        CHUNK_REPORT.md
        OUTPUT_urls_for_text_extraction.csv
        OUTPUT_source_ledger_delta.csv
        UNRESOLVED_ROWS.csv
        BENCHMARK_RECOVERY.csv
        BENCHMARK_MISSES.csv
        MANIFEST.json

AUDIT_TRAILS/
  url_discovery_production_chunk_<clean_runner_id>/
```

## Current Reproducibility Strategy

The project should not claim that URL discovery is a fully autonomous,
production-ready scraper. The recent pilot history, especially Batch 14, shows
that clean out-of-sample URL discovery is still unstable and may continue to
fail on source-family shifts.

The production strategy is now chunked source construction plus deterministic
replication:

```text
start from an explicit production target panel and production candidate/source inputs
-> generate or load a production candidate URL ledger
-> bucket failures and source-family gaps
-> use Codex as a coding/debugging and source-review aid where useful
-> make generalizable code/rule fixes, not hidden row-specific conditionals
-> rerun the chunk and review candidate sources
-> freeze accepted sources in a source ledger with evidence
-> rebuild final data from the frozen ledger and archived artifacts
```

Codex assistance is part of the research-process disclosure and, where it
affects source construction, part of the audit trail. It is not a required live
step in the replication package. The replication package should not ask a
reviewer to run Codex to repair code or rediscover missing sources. It should
rebuild the final dataset from the frozen source ledger, cached source
artifacts, code, and cached model outputs where applicable.

Row-specific source decisions are allowed as transparent data in the source
ledger. They should not be hard-coded into scraper logic. General patterns
found during repair should become general code or documented source-family
rules.

Critical process correction: old `pilot_batch_*` outputs may be used to learn
failure modes, write tests, and improve general programmatic rules. They should
not be the runtime spine of future production construction. A clean Step 1
production runner should consume explicit production inputs, not convert an old
pilot folder into a production chunk. The next implementation goal is therefore
code extraction and reorganization: keep the good general logic, put it behind a
clean production command, and stop layering wrappers over old runs.

## Clean Runner Mini-Test Status

Clean-runner smoke and mini-batch testing outputs have been moved out of the
production-facing folders and into:

```text
artifacts/PILOTS/url_discovery/clean_runner_tests/
```

These are test/regression artifacts. They should not be treated as current
production chunks, current production releases, or journal-ready packages.

Current mini-test inventory:

| Run | Purpose | Result | Use |
|---|---|---|---|
| `clean_runner_smoke_001` | 2-row structural smoke test of runner and release packager | 1 ready, 1 unresolved, 0 benchmark misses, 7/7 checks | Keep as smoke regression |
| `step1_mini_batch_001` | Curated cached 10-row mini input package | 10 ready, 0 unresolved, 0 benchmark misses, 7/7 checks | Keep as curated runner/reporting regression |
| `step1_full_mini_002` | Full-mini input/seed setup only | No completed chunk found | Keep only as superseded setup residue |
| `step1_full_mini_003` | Live-web full-mini Abilene Christian rows | 0 ready, 7 unresolved, 7 misses, 6/7 checks | Keep as failure evidence |
| `step1_full_mini_004` | Live-web full-mini Adelphi rows | 15 ready, 0 unresolved, 0 misses, 7/7 checks | Keep as one-institution pass evidence |
| `step1_full_mini_005` | Repeat live-web full-mini Abilene Christian rows | 0 ready, 7 unresolved, 7 misses, 6/7 checks | Keep as failure evidence |

Bottom line: the clean runner and release packager have useful smoke/mini
evidence, but the live-web full-mini tests are mixed. The mini runs support
continued development and reporting design; they do not establish production
readiness or replace the need for a real production chunk built from the target
panel.

## Explicit Path To Production Ready / Journal Standard

There are three separate gates. Do not collapse them.

### Gate 1: Step 1 Production-Ready URL Discovery

Goal: prove that the clean Step 1 runner can construct real URL/source-ledger
data from the target panel, not just pass smoke or mini tests.

Required steps:

1. Freeze the target panel for the actual production scope.
   - Input: target 4-year IPEDS institution-years in 2002-2016 with graduation
     outcomes and complete controls, using the agreed target-universe rules.
   - Output: `target_panel.csv` with row counts, institution counts, sector/year
     coverage, and exclusion reasons.

2. Build a real production input package.
   - Inputs: `target_panel.csv`, generated `candidate_url_ledger.csv`,
     `source_review_log.csv`, source-evidence cache/manifest where available,
     and optional benchmark key used only after discovery/review.
   - Fail condition: the run depends on `pilot_batch_*`, `artifacts/PILOTS/`,
     old audit folders, hidden answers, or row-specific scraper conditionals as
     normal runtime inputs.

3. Run the clean production runner with a non-test chunk id.
   - Output: `production_chunk_*` with URL handoff, source-ledger delta,
     unresolved-row table, benchmark files when applicable, requirements status,
     manifest, production command, and code snapshot.
   - Mini/smoke ids such as `*_mini_*` or `*_smoke_*` cannot satisfy this gate.

4. Close every target row.
   - Pass condition: every row has either an accepted reviewed source URL or an
     explicit unresolved/unrecoverable reason.
   - Accepted rows require source-review evidence; unresolved rows require stop
     reasons that are useful for the next repair pass.

5. Run production-quality checks.
   - Checks: no pilot-runtime paths, no local absolute paths in release-facing
     files, no unreviewed accepted candidates, benchmark recovery reported
     separately from production closure, manifests/hashes complete, and tests for
     runner/release packaging pass.
   - Output: updated `REQUIREMENTS_STATUS.csv`, manifest, and concise status
     update in this file.

Step 1 is production-ready only after a real target-panel `production_chunk_*`
passes this gate. The current smoke and mini runs do not.

### Gate 2: Journal-Standard Step 1 URL-Stage Release

Goal: freeze the passed production URL/source-ledger output into a portable
URL-stage release package.

Required steps:

1. Build a `production_release_*` package from the passed production chunk or
   approved set of chunks.
2. Use package-local relative paths only; no Dropbox/local absolute paths in the
   required rebuild path.
3. Include exact runnable commands, code snapshot or commit/archive id,
   environment/dependency record, file hashes, row/column counts, manifests, and
   cached source-evidence manifest.
4. Verify the package from the release root with the documented command.
5. Label the release correctly: URL-stage release only, not the full journal
   replication package.

Step 1 is journal-standard only after the frozen `production_release_*` rebuild
passes without live Codex repair, live web rescue, or hidden local files.

### Gate 3: Full Journal Replication Package

Goal: make the whole policy-data pipeline journal-ready, not just Step 1.

Required downstream stages:

1. Text retrieval/extraction from the frozen URL/source ledger.
2. Policy excerpt search with logged candidate excerpts and misses.
3. LLM/API or deterministic policy classification with prompts, schemas,
   model-output manifests, cached outputs, and validation.
4. Human/Codex-assisted adjudication records where used, stored as data rather
   than hidden code behavior.
5. Final panel construction with source lineage from URL to text to policy
   classification to final variables.
6. Computer-versus-human validation metrics for all pipeline stages.
7. Final release rebuild check, AI-use disclosure, data availability statement,
   and journal repository deposit package.

The Step 1 clean runner can become one component of the journal replication
package. It is not the journal replication package by itself.

## Current Production Chunk Status

The active direction is no longer to keep extending the `pilot_batch_*`
development sequence as if it were production. The pilots remain historical
process, development, and regression evidence. New dataset-construction work
should use `production_chunk_*` folders.

Production Chunk 001 has been moved out of the production-facing output tree.
It is now archived as transitional pilot/history evidence because it was not the
clean start-to-finish production runner. It used fixed Batch 14
(`pilot_batch_014_dev_009`) as prior reviewed evidence, then rewrote the result
into production-shaped outputs with the corrected prior-programmatic guardrail.
It is useful evidence, but it is not the clean production-runner input contract.

Moved transitional artifacts are under the pilot/history folder in the
`pipeline_outputs/` and `audit_trails/` subfolders. They are not current
production chunks or production releases.

Chunk 001 counts:

```text
target institution-year rows: 277
institutions: 19
ready/source-ledger rows: 204
source-ledger unresolved rows: 73
unique old-discovery benchmark institution-year rows: 181
old-discovery benchmark group checks: 264
unique benchmark rows recovered by current chunk: 181
unique benchmark rows promoted from valid human legacy evidence: 0
prior-programmatic current-run misses: 0
prior-programmatic misses already source-ledger resolved by valid human legacy: 0
programmatic-only source-ledger unresolved misses: 0
requirements passing: 11/11
```

Production Chunk 001 answers:

```text
Can a bounded set of institution-years be closed into a reproducible source
ledger for later text extraction?
```

This is different from the clean no-legacy benchmark. The clean benchmark asks
whether the computer can recover hidden human URLs without seeing them, and its
floor is at least 90 percent recovery of valid human legacy URL rows.
Production construction instead targets 100 percent ledger accounting:

```text
accepted reviewed source URL
or explicit unresolved/unrecoverable reason
for every target institution-year row
```

For transitional chunks that use prior pilot/audit evidence, this is stricter
than basic ledger accounting. Valid human legacy benchmark rows may be
recovered, promoted into the source ledger with human-legacy provenance, or
row-invalidated. Prior-programmatic benchmark rows must be recovered by the
current run or row-invalidated; old programmatic evidence cannot promote a row
into the source ledger by itself. Future clean production-runner chunks should
avoid the pilot/audit runtime-input pattern altogether.

Chunk 001 now passes this stricter prior-programmatic benchmark check after a
current-run reattempt review of the 39 prior-programmatic miss URLs. The
reattempt review accepted 28 rows through automated current-run retrieval and
source review, then accepted 11 rows after Codex/manual PDF text inspection
under the source-review standard. The raw automated review, manual
adjudications, and final reattempt review log are preserved in the production
chunk audit folder.

Allowed production evidence:

```text
valid human legacy URLs, if reviewed and recorded as prior_human
valid prior programmatic discoveries as benchmark diagnostics or current-run
recovery targets, but not as automatic source-ledger promotions
new programmatic candidates from the current URL process
manual/Codex-assisted source review, recorded as review evidence
API-assisted candidates, only when live or cached API evidence is documented
```

Production chunk done criteria:

```text
target panel frozen before review
every target row has ready or not-ready status
every accepted URL has source-review evidence
every unresolved row has an explicit stop reason
source-ledger delta records provenance for every accepted source
valid human legacy benchmark rows have zero unresolved misses
prior-programmatic benchmark rows have zero current-run misses or row-level invalidations
text-extraction handoff, unresolved-row table, report, and manifest agree
hidden-answer benchmark recovery reported separately when benchmark answers exist
no row-specific source answer hidden in scraper logic
```

Chunk 001 can now be used as a reference for the benchmark guardrail, source
review expectations, manifest contents, cached evidence, code snapshot, and
release packaging. It should not be copied as the future runtime-input pattern,
because its builder still depends on old pilot evidence. The clean production
runner/release-packager code slice has now passed integration review in commit
`13f8f792696a43253ecf6ed66a0ae82e42b103da`. The next Step 1 production goal is
to use that reviewed runner on a real next larger target-panel production chunk
and send the generated outputs through review before making any scale-readiness
claim.

Required shape for the next goal:

```text
target_panel.csv
candidate_url_ledger.csv
source_review_log.csv
source_evidence_cache/manifest, where cached evidence exists
optional benchmark_key.csv, used only for post-run scoring
-> production_chunk_*
-> production_release_*
-> package-local verification
```

The clean runner should reject `pilot_batch_*`, `artifacts/PILOTS/`, and old
pilot audit folders as normal runtime inputs. Old pilot outputs remain allowed
as development evidence, regression fixtures, and benchmark-design context. Do
not start another `pilot_batch_*` unless the explicit purpose is a clean
benchmark or regression test. Do not count API-assisted rescue as available until
the quota/configuration problem is resolved or a cached API replay is documented.

## Current Bottom Line

Step 1 Pilot 1 and Pilot Batches 2, 3, and 4 are passed production-path
URL-discovery pilots. Pilot Batch 5 is now a frozen failed regression case: the
frozen corrected pilot failed badly at 80 of 128 old-audit rows recovered
(62.5%), and the latest regression run has improved to 116 of 128 rows
recovered (90.6%) after general discovery/gap-fill fixes. Pilot Batch 6
development run 001 passes the 90% floor at 174 of 185 old-audit-ready rows
recovered (94.1%). Pilot Batch 7 development run 002 passes the 90% floor at
124 of 132 old-audit-ready rows recovered (93.9%). Pilot Batch 8 development
run 003 passes the older all-prior-audit floor at 220 current ready rows on 218
old-audit-ready rows (100.9%). Pilot Batch 9 development run 004 failed badly
under that older summary at 82/168 rows (48.8%). The current fixed Batch 9
regression run 002 passes the corrected hidden-answer floor at 39/43 valid
human legacy rows (90.7%). Its broader prior-programmatic diagnostic remains
lower at 109/168 rows (64.9%) because it includes earlier programmatic rows that
are not clean valid-human answers. Batch 10 regression 004 passes the corrected
hidden-answer floor at 80/82 valid human legacy rows (97.6%). Its broader
prior-programmatic diagnostic is 128/172 rows (74.4%). Batch 10 required
additional general fixes and is therefore regression/development evidence, not
clean untouched validation. Batch 11 development run 006 failed at 29/62 valid
human legacy rows (46.8%). Batch 11 regression 001 passes the corrected
hidden-answer floor at 57/62 valid human legacy rows (91.9%). Its broader
prior-programmatic diagnostic is 123/142 rows (86.6%). Batch 11 also required
general fixes before passing, so it is regression/development evidence, not a
clean untouched validation pass. These are still not final production URL
handoffs and do not establish production benchmark coverage.

The pilots are useful evidence that the production command path, recovery
layers, source-review gate, manifests, and front-door reporting can run on
fixed batches. They are not evidence that URL discovery, text retrieval, policy
search, or LLM/API classification are ready for broad production.

Mini Full Production Test 001 is invalid/superseded. It was run from seed inputs
only, but it omitted the validated API/web rescue layers and replaced
evidence-backed source review with a deterministic quality gate. The all-pass
status from that attempted run was wrong; its requirements file now records fail
checks for the missing API/review gates and the then-used old-audit recovery
floor.

The corrected mini test must use the validated production path: deterministic
discovery, deterministic recovery, configured API/web rescue or cached API
replay where needed, and evidence-backed source review under
`url_source_review_standard.md` before any row is ready for text extraction.

The most recent completed development/regression evidence is
`pilot_batch_014_dev_009`, which now passes the corrected hidden-answer floor.
Batch 12 development run 007 failed the
corrected valid-human hidden-answer floor at 47/92 rows (51.1%). Earlier Batch
12 regression reports also failed. The latest front-door report,
`pilot_batch_012_regression_008`, now passes at 86/92 valid human legacy rows
(93.5%) after general fixes for official-domain seed retention, WordPress media
API year searches, candidate-document ranking, stricter non-source rejection,
compact year-span source review, official library/archive repository discovery,
CONTENTdm collection/API expansion, and JSON metadata source-review evidence.
Batch 12 is therefore a fixed regression pass, not a clean untouched validation
pass. The remaining valid human misses are Georgia Southwestern 2003, Lawrence
Technological University 2002/2012, Lafayette College 2015/2016, and Francis
Marion 2003. Batch 13 development run 008 then passed the corrected
hidden-answer floor at 85/94 valid human legacy rows (90.4%) after general
fixes for prior-year span official-domain probes, Wayback transient retries,
archived catalog-policy source review, and archived undergraduate index child
sources. Batch 13 is fixed development evidence, not a clean untouched
validation pass. Its remaining valid human misses are Humboldt State 2005/2009
and Maryville College 2009-2015; the Maryville College misses appear to involve
legacy URLs on `catalog.maryville.edu`, which source evidence identifies as
Maryville University rather than Maryville College, so they should be reviewed
before treating them as true current-run discovery failures.

Batch 14 development run 009 then initially failed the corrected hidden-answer
floor. The first corrected run recovered 22 of 83 valid human legacy rows
(26.5%). After general deterministic/source-review fixes for compact year
spans, short domain labels, selected archive PDF templates, S3 catalog storage,
soft-redirect PDF rejection, compact official-domain year templates, risky
catalogarchive demotion, undergraduate-and-graduate catalog source review,
Ex Libris/Primo PNX collection search, and archive-expansion precedence over
stale generated URL probes, the current Batch 14 report recovers 77 of 83 valid
human legacy rows (92.8%). The broader prior-programmatic diagnostic is 142 of
181 rows (78.5%). Overall target-year attrition is 277 target rows, 194 rows
with a current-run candidate, 165 rows ready for text extraction, 83 rows with
no candidate, and 29 rows rejected after source review. Batch 14 is fixed
development evidence, not a clean untouched validation pass.

Batch 14 also exposed an operational blocker: every API rescue attempt in the
root/archive and year-gap triage files failed with OpenAI `RateLimitError` 429
`insufficient_quota`. That means the documented production path was invoked,
but the API rescue layer did not return usable candidates. The API failure is
recorded in `../PILOTS/url_discovery/pipeline_outputs/pilot_batch_014_dev_009/HOW_CREATED.md` and
`../PILOTS/url_discovery/audit_trails/url_discovery_pilot_batch_014_dev_009/api_rescue_summary.csv`.
Before treating API-assisted rescue as available in later evidence, restore or
confirm API quota/configuration and rerun a batch with successful API/cached API
evidence. Batch 14's Mercer-type source-family failure was fixed through
general Ex Libris/Primo PNX collection search and archive-expansion precedence.

Current benchmark stopping rule: clean no-legacy development batches remain a
diagnostic lane. Continue them only when the goal is to test unaided discovery:
all accumulated regression batches should pass and three consecutive new
development batches should pass the valid-human hidden-answer recovery floor
without batch-specific cheating. Batch 14 is now a fixed development pass after
general code/rule repairs.

Current development-loop rule: pause before moving to a new clean benchmark
batch. Batch 14's reports, tests, and documentation are synchronized, but the
next bounded development or production-chunk plan should be discussed before
another run counts toward the three-consecutive-pass stopping rule.

The active plan for validating computer-versus-human performance across the
full pipeline is:

```text
CLEAN_REBUILD_VALIDATION_PLAN.md
```

That plan calls for one self-contained clean rebuild package rather than a
curated summary of scattered audit folders.

## Open For Mini Full Production Test 001

Use these files only as the invalid/superseded diagnostic record:

```text
../PILOTS/url_discovery/pipeline_outputs/mini_full_production_test_001/OUTPUT_urls_for_text_extraction.csv
../PILOTS/url_discovery/pipeline_outputs/mini_full_production_test_001/HOW_CREATED.md
../PILOTS/url_discovery/pipeline_outputs/mini_full_production_test_001/BENCHMARKS_AND_ATTRITION.md
../PILOTS/url_discovery/pipeline_outputs/mini_full_production_test_001/REQUIREMENTS_STATUS.csv
../PILOTS/url_discovery/audit_trails/mini_full_production_test_001/
```

Diagnostic URL-stage counts:

```text
target rows, 2002-2016 active IPEDS panel: 298
rows with any URL candidate:                 110
source opened live:                           90
ready for text extraction:                    88
institutions with 2+ ready years:              9
```

Post-run old-audit benchmark:

```text
old-audit ready rows on same targets: 113
old ready rows recovered:              77
old ready rows missing:                36
current ready rows beyond old audit:    2
```

Main interpretation: deterministic-only discovery is not the production path
and cannot be treated as journal-standard evidence. Later clean-runner smoke and
mini-batch tests now live in:

```text
../PILOTS/url_discovery/clean_runner_tests/
```

Those newer tests include evidence-backed source-review inputs and clean-runner
release packaging, but the live-web full-mini results are mixed. Future mini
tests should stay in the clean-runner test-evidence folder, report
stage-specific and rolling attrition plus benchmark recovery, and should not be
placed in the production chunk/release folders unless rerun as real dataset
construction from explicit production inputs.

## Open For Pilot 1 Evidence

Use these files for the actual Pilot 1 audit record:

```text
../PILOTS/url_discovery/pipeline_outputs/pilot_batch_001/HOW_CREATED.md
../PILOTS/url_discovery/pipeline_outputs/pilot_batch_001/BENCHMARKS_AND_ATTRITION.md
../PILOTS/url_discovery/pipeline_outputs/pilot_batch_001/REQUIREMENTS_STATUS.csv
01_url_discovery/process_reviews/url_discovery_pilot_batches_review.md
../PILOTS/url_discovery/audit_trails/url_discovery_pilot_batch_001/
```

The process review is here:

```text
01_url_discovery/process_reviews/url_discovery_pilot_batches_review.md
```

The cached external evidence replay report is here:

```text
../PILOTS/url_discovery/audit_trails/url_discovery_pilot_batch_001/external_evidence_replay_log.csv
```

## Open For Pilot Batch 2 Evidence

Use these files for the Pilot Batch 2 URL-stage audit record:

```text
../PILOTS/url_discovery/pipeline_outputs/pilot_batch_002/OUTPUT_urls_for_text_extraction.csv
../PILOTS/url_discovery/pipeline_outputs/pilot_batch_002/HOW_CREATED.md
../PILOTS/url_discovery/pipeline_outputs/pilot_batch_002/BENCHMARKS_AND_ATTRITION.md
../PILOTS/url_discovery/pipeline_outputs/pilot_batch_002/REQUIREMENTS_STATUS.csv
../PILOTS/url_discovery/audit_trails/url_discovery_pilot_batch_002/
```

Pilot Batch 2 covers the next ten public and next ten private clean no-legacy
holdout institutions after Pilot 1. It uses production discovery, deterministic
recovery, API URL rescue, API year-gap rescue, and Codex source review.

Headline URL-stage counts:

```text
target rows, 2002-2016 with graduation outcomes: 263
programmatic candidate rows before source review: 202
rows accepted by source review:                   176
rows rejected by source review:                    26
rows with no candidate after recovery:             61
ready for text extraction:                        176
```

Main attrition point: programmatic URL discovery/gap-fill, not source-review
accuracy among candidates. Candidate availability is 202/263 rows (76.8%).
Source-review acceptance among candidate rows is 176/202 (87.1%). The old-audit
benchmark check reports 176/188 rows recovered (93.6%), with 6 true misses
listed in the report.

To decide which audit folder to inspect for other questions, use:

```text
../AUDIT_TRAILS/START_HERE.md
```

Do not copy the same review text into the audit-trail folder. If an audit folder
needs a note, keep it factual and artifact-specific; put current decisions here.

## Open For Pilot Batch 3 Evidence

Use these files for the Pilot Batch 3 URL-stage audit record:

```text
../PILOTS/url_discovery/pipeline_outputs/pilot_batch_003/OUTPUT_urls_for_text_extraction.csv
../PILOTS/url_discovery/pipeline_outputs/pilot_batch_003/HOW_CREATED.md
../PILOTS/url_discovery/pipeline_outputs/pilot_batch_003/BENCHMARKS_AND_ATTRITION.md
../PILOTS/url_discovery/pipeline_outputs/pilot_batch_003/REQUIREMENTS_STATUS.csv
../PILOTS/url_discovery/audit_trails/url_discovery_pilot_batch_003/
```

Headline URL-stage counts:

```text
target rows, 2002-2016 with graduation outcomes: 289
programmatic candidate rows before source review: 235
ready for text extraction: 218
old-audit ready rows on same target rows: 193
true discovery misses after current review: 6
```

## Open For Pilot Batch 4 Evidence

Use these files for the Pilot Batch 4 harder-case URL-stage audit record:

```text
../PILOTS/url_discovery/pipeline_outputs/pilot_batch_004/OUTPUT_urls_for_text_extraction.csv
../PILOTS/url_discovery/pipeline_outputs/pilot_batch_004/HOW_CREATED.md
../PILOTS/url_discovery/pipeline_outputs/pilot_batch_004/BENCHMARKS_AND_ATTRITION.md
../PILOTS/url_discovery/pipeline_outputs/pilot_batch_004/REQUIREMENTS_STATUS.csv
../PILOTS/url_discovery/audit_trails/url_discovery_pilot_batch_004/
```

Pilot Batch 4 covers the next ten public and next ten private clean no-legacy
holdout institutions after Batch 3, using the selection rule:

```text
--sector both --limit 10 --rank-start 22
```

Headline URL-stage counts:

```text
target rows, 2002-2016 with graduation outcomes: 283
current-run candidate rows before source review: 244
rows accepted by source review: 210
rows rejected by source review: 34
rows with no candidate after recovery: 39
ready for text extraction: 210
```

Reproducibility and benchmark checks:

```text
all current candidates source-reviewed: yes
rows stuck at candidate_needs_source_review: 0
requirements status: all pass
input and output manifests with hashes: present
old-audit ready rows on same target rows: 186
current ready rows on same target rows: 210
old-audit rows not ready in current run: 23
true discovery misses after current review: 15
```

Main attrition point: URL discovery still does not find a usable target-year
candidate for every row. Candidate availability is 244/283 rows (86.2%).
Source-review acceptance among candidate rows is 210/244 rows (86.1%). Overall
text-ready yield is 210/283 rows (74.2%).

## Open For Pilot Batch 5 Evidence

Use these files for the frozen corrected Pilot Batch 5 URL-stage failure:

```text
../PILOTS/url_discovery/pipeline_outputs/pilot_batch_005/OUTPUT_urls_for_text_extraction.csv
../PILOTS/url_discovery/pipeline_outputs/pilot_batch_005/HOW_CREATED.md
../PILOTS/url_discovery/pipeline_outputs/pilot_batch_005/BENCHMARKS_AND_ATTRITION.md
../PILOTS/url_discovery/pipeline_outputs/pilot_batch_005/REQUIREMENTS_STATUS.csv
../PILOTS/url_discovery/audit_trails/url_discovery_pilot_batch_005/
```

Pilot Batch 5 covers the next five public and next five private clean
no-legacy holdout institutions after Batch 4, using the selection rule:

```text
--sector both --limit 5 --rank-start 32
```

Headline URL-stage counts:

```text
target rows, 2002-2016 with graduation outcomes: 150
current-run candidate rows before source review: 87
rows accepted by source review: 80
rows rejected by source review: 7
rows with no candidate after recovery: 63
ready for text extraction: 80
```

Reproducibility and benchmark checks:

```text
all current candidates source-reviewed: yes
rows stuck at candidate_needs_source_review: 0
input and output manifests with hashes: present
old-audit ready rows on same target rows: 128
current ready rows on same target rows: 80
old-audit rows not ready in current run: 48
old-audit recovery rate: 62.5%
requirements status: fail, because old-audit recovery is below the 90% floor
```

Main attrition point: URL discovery/gap-fill did not recover enough target-year
candidates. Source review rejected 7 Cal State LA rows where the opened source
was a General Education chart rather than a catalog; source-family review
corrected Cal State LA rows for 2010-2016, but 2002-2008 remained misses.
Other large old-audit misses include CSU East Bay 2002-2014, Carnegie Mellon
2002-2016, Cardinal Stritch 2013-2016, and Carthage 2002-2010.

## Open For Pilot Batch 5 Regression 003 Evidence

Use these files for the active Batch 5 regression record:

```text
../PILOTS/url_discovery/pipeline_outputs/pilot_batch_005_regression_003/OUTPUT_urls_for_text_extraction.csv
../PILOTS/url_discovery/pipeline_outputs/pilot_batch_005_regression_003/HOW_CREATED.md
../PILOTS/url_discovery/pipeline_outputs/pilot_batch_005_regression_003/BENCHMARKS_AND_ATTRITION.md
../PILOTS/url_discovery/pipeline_outputs/pilot_batch_005_regression_003/REQUIREMENTS_STATUS.csv
../PILOTS/url_discovery/audit_trails/url_discovery_pilot_batch_005_regression_003/
```

Latest regenerated URL-stage counts:

```text
target rows, 2002-2016 with graduation outcomes: 150
current-run candidate rows before source review: 118
rows accepted by source review: 116
rows rejected by source review: 2
rows with no candidate after recovery: 32
ready for text extraction: 116
old-audit ready rows on same target rows: 128
current ready rows on old-audit rows: 116
old-audit recovery rate: 90.6%
requirements status: pass for this regression batch
```

What changed from the frozen failure: CSU East Bay, CSU Los Angeles, Carnegie
Mellon, Carthage, Cardinal Stritch 2016, and Carroll 2013-2015/2017-2018 were
recovered by general fixes to catalog archive expansion, catalog-year span
handling, Modern Campus/Acalog media variants, direct API-URL materialization,
and post-rescue inferred-year gap fill. The remaining true discovery misses are
older Carroll target years. Two Cardinal Stritch rows are currently rejected
because the opened evidence did not support the credited academic year; they
are flagged separately as old-audit wrong-year exceptions.

Current stopping point for this regression path: Batch 5 now passes the 90%
floor, and the earlier passing batches have been rerun under the same fixed
code. Batches 6 and 7 have also passed after general fixes, so they are kept as
additional regression/development evidence before the next clean-pass attempt.

## Open For Pilot Batch 6 Development 001 Evidence

Use these files for the first new post-regression development batch:

```text
../PILOTS/url_discovery/pipeline_outputs/pilot_batch_006_dev_001/OUTPUT_urls_for_text_extraction.csv
../PILOTS/url_discovery/pipeline_outputs/pilot_batch_006_dev_001/HOW_CREATED.md
../PILOTS/url_discovery/pipeline_outputs/pilot_batch_006_dev_001/BENCHMARKS_AND_ATTRITION.md
../PILOTS/url_discovery/pipeline_outputs/pilot_batch_006_dev_001/REQUIREMENTS_STATUS.csv
../PILOTS/url_discovery/audit_trails/url_discovery_pilot_batch_006_dev_001/
```

Pilot Batch 6 covers the next ten public and next ten private clean no-legacy
holdout institutions after Batch 5, using the selection rule:

```text
--sector both --limit 10 --rank-start 37
```

Latest regenerated URL-stage counts:

```text
target rows, 2002-2016 with graduation outcomes: 285
current-run candidate rows before source review: 196
rows accepted by source review: 174
rows rejected by source review: 22
rows with no candidate after recovery: 89
ready for text extraction: 174
old-audit ready rows on same target rows: 185
current ready rows on old-audit rows: 174
old-audit recovery rate: 94.1%
requirements status: pass
```

Main remaining attrition point: current-run URL discovery/gap-fill, not
source-review review of opened candidates. Candidate availability is 196/285
rows (68.8%). Source-review acceptance among candidate rows is 174/196 rows
(88.8%). The remaining true old-audit misses are listed row by row in the
Batch 6 benchmark report.

## Open For Pilot Batch 7 Development 002 Evidence

Use these files for the second post-regression development batch:

```text
../PILOTS/url_discovery/pipeline_outputs/pilot_batch_007_dev_002/OUTPUT_urls_for_text_extraction.csv
../PILOTS/url_discovery/pipeline_outputs/pilot_batch_007_dev_002/HOW_CREATED.md
../PILOTS/url_discovery/pipeline_outputs/pilot_batch_007_dev_002/BENCHMARKS_AND_ATTRITION.md
../PILOTS/url_discovery/pipeline_outputs/pilot_batch_007_dev_002/REQUIREMENTS_STATUS.csv
../PILOTS/url_discovery/audit_trails/url_discovery_pilot_batch_007_dev_002/
```

Pilot Batch 7 covers the next ten public and next ten private clean no-legacy
holdout institutions after Batch 6, using the selection rule:

```text
--sector both --limit 10 --rank-start 47
```

Latest regenerated URL-stage counts:

```text
target rows, 2002-2016 with graduation outcomes: 284
current-run candidate rows before source review: 142
rows accepted by source review: 124
rows rejected by source review: 18
rows with no candidate after recovery: 142
ready for text extraction: 124
old-audit ready rows on same target rows: 132
current ready rows on old-audit rows: 124
old-audit recovery rate: 93.9%
requirements status: pass
```

Main remaining attrition point: current-run URL discovery/gap-fill. Candidate
availability is 142/284 rows (50.0%). Source-review acceptance among candidate
rows is 124/142 rows (87.3%). The key fix discovered in this batch was not a
manual old-URL shortcut: the current process now tries common current-site
catalog archive pages, which recovered Creighton's full 2002-2016 panel from
its live catalog archive page. The remaining true old-audit misses are listed
row by row in the Batch 7 benchmark report.

## Open For Pilot Batch 8 Development 003 Evidence

Use these files for the third post-regression development batch:

```text
../PILOTS/url_discovery/pipeline_outputs/pilot_batch_008_dev_003/OUTPUT_urls_for_text_extraction.csv
../PILOTS/url_discovery/pipeline_outputs/pilot_batch_008_dev_003/HOW_CREATED.md
../PILOTS/url_discovery/pipeline_outputs/pilot_batch_008_dev_003/BENCHMARKS_AND_ATTRITION.md
../PILOTS/url_discovery/pipeline_outputs/pilot_batch_008_dev_003/REQUIREMENTS_STATUS.csv
../PILOTS/url_discovery/audit_trails/url_discovery_pilot_batch_008_dev_003/
```

Pilot Batch 8 covers the next ten public and next ten private clean no-legacy
holdout institutions after Batch 7, using the selection rule:

```text
--sector both --limit 10 --rank-start 57
```

Latest regenerated URL-stage counts:

```text
target rows, 2002-2016 with graduation outcomes: 284
current-run candidate rows before source review: 220
rows accepted by source review: 220
rows rejected by source review: 0
rows with no candidate after recovery: 64
ready for text extraction: 220
old-audit ready rows on same target rows: 218
current ready rows on old-audit rows: 220
old-audit recovery rate: 100.9%
requirements status: pass
```

Main remaining attrition point: current-run URL discovery/gap-fill. Candidate
availability is 220/284 rows (77.5%). Source-review acceptance among target
candidate rows is 220/220 rows (100.0%). The general fixes discovered in this
batch were: bounded same-directory catalog-PDF year inference for simple
year-range filenames, higher priority for institutional repository roots,
two-depth nested archive crawling, query-pagination recognition for archive
pages, and a more stable source-review rerun setting for large evidence pages.
The remaining true old-audit misses are Embry-Riddle 2002-2004, Drake
2002-2003, Endicott 2002-2004, and Dickinson 2002-2016; they are listed row by
row in the Batch 8 benchmark report.

## Open For Pilot Batch 9 Regression 002 Evidence

Use these files for the current Batch 9 regression record:

```text
../PILOTS/url_discovery/pipeline_outputs/pilot_batch_009_regression_002/OUTPUT_urls_for_text_extraction.csv
../PILOTS/url_discovery/pipeline_outputs/pilot_batch_009_regression_002/HOW_CREATED.md
../PILOTS/url_discovery/pipeline_outputs/pilot_batch_009_regression_002/BENCHMARKS_AND_ATTRITION.md
../PILOTS/url_discovery/pipeline_outputs/pilot_batch_009_regression_002/REQUIREMENTS_STATUS.csv
../PILOTS/url_discovery/audit_trails/url_discovery_pilot_batch_009_regression_002/
```

Pilot Batch 9 covers the next ten public and next ten private clean no-legacy
holdout institutions after Batch 8, using the selection rule:

```text
--sector both --limit 10 --rank-start 67
```

Latest regenerated URL-stage counts:

```text
target rows, 2002-2016 with graduation outcomes: 269
current-run candidate rows before source review: 142
rows accepted by source review: 125
rows rejected by source review: 17
rows with no candidate after recovery: 127
ready for text extraction: 125
valid human legacy benchmark rows: 43
current ready rows on valid human legacy rows: 39
valid human legacy recovery rate: 90.7%
prior programmatic diagnostic rows: 168
current ready rows on prior programmatic diagnostic rows: 109
prior programmatic diagnostic recovery rate: 64.9%
requirements status: pass
```

Main interpretation: Batch 9 is not a clean untouched validation pass. The
development run failed, and the regression run passes after general fixes:
archive-root deduplication now keeps higher-priority archive links, source
review rejects branded placeholder pages that return HTTP 200, official-domain
PDF templates include high-yield catalog filename/folder patterns, generated
repository roots include `img2.<domain>/hu/docs/catalogs/`, and duplicate
candidate URLs now prefer precise year spans over broader contaminated spans.

The reporting standard also changed here. The valid human legacy rows are the
hidden-answer pass/fail benchmark. Prior programmatic audit rows remain visible
as a diagnostic, but they are not the 90% floor because they can include earlier
programmatic false positives.

## Open For Pilot Batch 10 Regression 004 Evidence

Use these files for the current Batch 10 regression record:

```text
../PILOTS/url_discovery/pipeline_outputs/pilot_batch_010_regression_004/OUTPUT_urls_for_text_extraction.csv
../PILOTS/url_discovery/pipeline_outputs/pilot_batch_010_regression_004/HOW_CREATED.md
../PILOTS/url_discovery/pipeline_outputs/pilot_batch_010_regression_004/BENCHMARKS_AND_ATTRITION.md
../PILOTS/url_discovery/pipeline_outputs/pilot_batch_010_regression_004/REQUIREMENTS_STATUS.csv
../PILOTS/url_discovery/audit_trails/url_discovery_pilot_batch_010_regression_004/
```

Pilot Batch 10 covers the next ten public and next ten private clean no-legacy
benchmark institutions after Batch 9, using the selection rule:

```text
--sector both --limit 10 --rank-start 77
```

Latest regenerated URL-stage counts:

```text
target rows, 2002-2016 with graduation outcomes: 284
current-run candidate rows before source review: 254
rows accepted by source review: 241
rows rejected by source review: 13
rows with no candidate after recovery: 105
ready for text extraction: 169
valid human legacy benchmark rows: 82
current ready rows on valid human legacy rows: 80
valid human legacy recovery rate: 97.6%
prior programmatic diagnostic rows: 172
current ready rows on prior programmatic diagnostic rows: 128
prior programmatic diagnostic recovery rate: 74.4%
requirements status: pass
```

Main interpretation: Batch 10 is not a clean untouched validation pass. It
failed during development/intermediate regression and then passed after general
fixes: SmartCatalog roots were prioritized inside the root-candidate cap,
filename years now take precedence over upload-folder dates, compact catalog
filenames are generated and parsed, and verified `catalog.<domain>` hosts get a
bounded Modern Campus media probe. The API rescue attempts are logged but failed
with quota 429 errors. The inferred/template rescue was slow on this small
batch, so broad production needs batching or optimization before scaling.

## Open For Pilot Batch 11 Regression 001 Evidence

Use these files for the current Batch 11 regression record:

```text
../PILOTS/url_discovery/pipeline_outputs/pilot_batch_011_regression_001/OUTPUT_urls_for_text_extraction.csv
../PILOTS/url_discovery/pipeline_outputs/pilot_batch_011_regression_001/HOW_CREATED.md
../PILOTS/url_discovery/pipeline_outputs/pilot_batch_011_regression_001/BENCHMARKS_AND_ATTRITION.md
../PILOTS/url_discovery/pipeline_outputs/pilot_batch_011_regression_001/REQUIREMENTS_STATUS.csv
../PILOTS/url_discovery/audit_trails/url_discovery_pilot_batch_011_regression_001/
```

The failed development run is preserved here:

```text
../PILOTS/url_discovery/pipeline_outputs/pilot_batch_011_dev_006/
../PILOTS/url_discovery/audit_trails/url_discovery_pilot_batch_011_dev_006/
```

Pilot Batch 11 covers the next ten public and next ten private clean no-legacy
benchmark institutions after Batch 10, using the selection rule:

```text
--sector both --limit 10 --rank-start 87
```

Latest regenerated URL-stage counts:

```text
target rows, 2002-2016 with graduation outcomes: 247
current-run candidate rows before source review: 140
rows accepted by source review: 138
rows rejected by source review: 2
rows with no candidate after recovery: 107
ready for text extraction: 138
valid human legacy benchmark rows: 62
current ready rows on valid human legacy rows: 57
valid human legacy recovery rate: 91.9%
prior programmatic diagnostic rows: 142
current ready rows on prior programmatic diagnostic rows: 123
prior programmatic diagnostic recovery rate: 86.6%
requirements status: pass
```

Main interpretation: Batch 11 is not a clean untouched validation pass. The
development run failed at 29/62 valid human legacy rows (46.8%). The regression
run passes after general fixes: CourseLeaf previous-editions pages are treated
as archive sources, registrar archive seeds are generated for official domains,
high-yield official-domain PDF templates are protected inside the candidate
cap, and source review uses a longer timeout for large PDFs. The remaining
valid-human misses are listed row by row in the Batch 11 benchmark report.

## What Pilot 1 Shows

Pilot 1 covers one public and one private clean no-legacy institution:

```text
Abraham Baldwin Agricultural College, unitid 138558, public
Abilene Christian University, unitid 222178, private
```

It produces 24 institution-year rows:

```text
ready_for_text_extraction = true:   8
ready_for_text_extraction = false: 16
```

Ready rows are all Abilene Christian University. ABAC has zero ready rows in
this corrected clean no-legacy pilot.

## Production Fixes Before Scaling

### 1. Reconcile Status Language

All front-door docs should use the same distinction:

```text
passed one-batch production-path pilot
not a final production handoff
not production benchmark evidence
```

### 2. Keep Pilot Status Separate From Production Status

Requirement files can report that the fixed Pilot 1 batch passed its checks, but
they should not imply production-stage pass/fail evidence.

If the status schema remains narrow, interpret every `pass` in Pilot 1 files as:

```text
pass for this fixed pilot batch
```

### 3. Keep Institution Identity Normalized

The Pilot 1 front-door output now uses one canonical display name per unitid.
Keep that contract in production outputs, while preserving source-specific names
in provenance fields.

### 4. Make Source-Review Logs Generic

The pilot-specific file:

```text
../PILOTS/url_discovery/audit_trails/url_discovery_pilot_batch_001/current_run_source_review_acu_ai_gap.csv
```

should not become the production pattern. Production needs a generic row-level
source-review log, for example:

```text
source_review_log.csv
source_review_panel_log.csv
```

### 5. Treat ABAC As A Process Test Case

ABAC produced zero ready target-year rows in this corrected clean no-legacy
pilot. Before scaling, decide whether that is a true clean-discovery failure or
whether scanned/OCR/source-root rules are available but not wired into the clean
production path.

If the second interpretation is true, fix the clean discovery path before
counting ABAC-like rows as unavoidable benchmark losses.

### 6. Promote The Active Production Runbook

The useful production stream plan currently lives under:

```text
policy_scraper/docs/replication_standards/old_design_notes/11_production_streams.md
```

If it is still the active plan, promote or rewrite it outside `old_design_notes`.
The active runbook should cover:

```text
catalog_pipeline
review-gated source cleanup
policy_extraction_queue
policy_production_block
production_quality_gate
clean_no_legacy_benchmark_runner
```

### 7. Separate Benchmarks By Failure Point

The existing clean benchmark shows URL discovery can look strong while full
policy replication fails. Production reporting should keep these benchmarks
separate:

```text
URL/source discovery benchmark
known-URL retrieval/text benchmark
policy-excerpt search benchmark
LLM/API classification benchmark
human adjudication benchmark
full end-to-end clean benchmark
```

Do not report one blended coverage number without the stage-specific losses.

### 8. Fix Extraction/Search Coverage Before Broad Classification

Existing audit evidence suggests classification coverage is limited by missing
or failed text retrieval, text extraction, year review, and policy-term search.
Large new API classification batches should wait until those upstream loss
buckets are handled.

### 9. Keep LLM/API Roles Narrow

The current separation is correct:

- URL-stage LLM/API use can generate or rescue candidates only.
- Text readiness should not call API classification.
- Classification may use LLM/API only after source text or source-backed
  excerpts exist.
- Cached raw and parsed outputs must be enough to replay the result without a
  live API call.

## Historical Clean-Benchmark Readiness Plan

This section records the older clean-benchmark readiness logic. It is still
useful for evaluating unaided URL discovery. The current active plan is the
capped Step 1 production-readiness development loop described above.

For the clean benchmark lane, the next step is not to run more batches hoping
one clears the floor. Pilot Batch 5 is now a failed regression test. The
URL-stage benchmark process becomes ready only after the same failed case
passes because the process was fixed, and then new unseen batches pass without
emergency fixes.

### Stopping Rule

Use a fixed validation design, not an open-ended sequence.

Development/regression stops when:

```text
Pilot Batch 5 rerun passes the URL/source recovery floor.
Pilot Batches 2-4 still pass after the same fixes.
All current candidates in those batches have source-review decisions.
No accepted row lacks retrieval/source-review/API provenance.
```

Only then start validation.

Before formal validation, allow a capped development phase because the current
process is expected to fail on additional hard cases.

Development batch cap:

```text
up to 10 additional development batches
20 institutions per development batch
10 public and 10 private where available
expected target size about 250-300 institution-year rows per batch
target valid-human hidden-answer denominator: at least 40 rows when available
prior-programmatic denominator: report as a diagnostic when available
```

Development batches may be used to diagnose failures and fix the general
URL-discovery/gap-fill process. A failed development batch becomes part of the
regression suite. It does not count as clean out-of-sample validation.

Development stops when either:

```text
all accumulated regression batches pass and 3 consecutive new development
batches pass the valid-human hidden-answer URL/source recovery floor

or

10 additional development batches have been processed

or

a blocker appears that cannot be fixed without a project decision
```

After development stabilizes, formal validation uses exactly two pre-specified
unseen batches:

```text
Validation Batch A: random mixed public/private batch.
Validation Batch B: harder-case mixed public/private batch.
```

Batch size:

```text
20 institutions per validation batch
10 public and 10 private where available
expected target size about 250-300 institution-year rows
target valid-human hidden-answer denominator: at least 40 rows when available
prior-programmatic denominator: report as a diagnostic when available
```

If a proposed validation batch has too few valid-human benchmark rows, top it
up before running using the pre-specified selection rule. Do not replace a batch
after seeing its results.

Validation passes only if both unseen batches pass:

```text
valid human legacy hidden-answer recovery >= 90% in each batch
accepted source precision >= 98% where reviewable
zero rows stuck at candidate_needs_source_review
all valid-human misses and prior-programmatic diagnostic misses listed row by row
stage-specific and rolling attrition reported
```

If either validation batch fails:

```text
stop running new validation batches
mark the failed batch as a failed regression test
fix the general process
rerun the full regression suite
then start a new validation round with two new pre-specified unseen batches
```

Do not keep running new batches until one clears 90%. Passing one later batch
does not erase a failed validation batch.

### 1. Freeze Regression Set

Treat these as fixed regression tests:

```text
Pilot Batch 2: must continue to pass.
Pilot Batch 3: must continue to pass.
Pilot Batch 4: must continue to pass.
Pilot Batch 5 regression 003: must continue to pass.
Pilot Batch 9 regression 002: must continue to pass.
Pilot Batch 10 regression 004: must continue to pass.
Pilot Batch 11 regression 001: must continue to pass.
```

Do not use old reviewed URLs as discovery inputs. They are benchmark truth only.

### 2. Fix Batch 5 Failure Modes With General Code

Batch 5 failures point to missing URL-discovery/gap-fill patterns, not mainly
source-review failure. Fix the general discovery process for:

```text
Modern Campus/Acalog catalog-list child links and media PDFs
older catalog-platform media files for pre-2010 years
previous/catalog PDF folders such as coursecatalog.../previous/
WordPress upload archives containing old undergraduate catalog PDFs
predictable official live/files catalog PDF source families
archive landing pages that need direct child PDF substitution
SmartCatalog roots crowded out by candidate caps
upload-folder dates parsed before filename catalog years
compact catalog filenames such as hccatalog1314final.pdf
bounded Modern Campus media probes for verified official catalog hosts
```

Each fix must create candidate rows with a named generation method, retrieval
evidence, and source-review provenance. Do not hardcode old benchmark URLs into
the production path.

### 3. Rerun Regression Batches

After process fixes:

```text
rerun Pilot Batch 5 from clean inputs
require valid human legacy hidden-answer recovery >= 90% where available
require zero rows stuck at candidate_needs_source_review
require all accepted rows to have source-review evidence
rerun Batches 2-4 to check that fixes did not break earlier passing cases
```

If Batch 5 still fails, repeat the diagnose/fix/rerun loop. The failed reruns
stay documented.

### 4. Validate On Unseen Batches

Only after the regression set passes, run new pre-specified unseen batches. Use
the same output contract and benchmarks:

```text
valid human legacy hidden-answer recovery >= 90%
accepted source precision >= 98% where reviewable
zero unreviewed current candidates
stage-specific and rolling attrition reported
valid-human misses and prior-programmatic diagnostic misses listed row by row
```

Recommended validation before broad production:

```text
one random mixed public/private batch
one hard-case mixed public/private batch
both selected before running discovery
```

Do not count a batch used for process fixes as clean out-of-sample validation.

### 5. Promote To Step 1 Production

Move to full Step 1 URL production only after:

```text
all frozen regression batches pass
two unseen validation batches pass
the production runbook names the exact commands and outputs
front-door outputs and audit trails are generated for every chunk
the combined Step 1 output has one row per target institution-year
```

At that point, Step 2 text retrieval/extraction can start using only rows
marked `ready_for_text_extraction`.

Do not move to broad policy classification until Step 2 has the same kind of
stage-specific attrition report, source-text provenance, replayable manifests,
and benchmark checks.

For the broader clean rebuild, keep using the self-contained validation plan:

```text
CLEAN_REBUILD_VALIDATION_PLAN.md
```

Then run a larger pre-specified clean benchmark slice and report stage-specific
losses before scaling broad production.

Minimum outputs:

```text
holdout_truth.csv
holdout_discovery_input.csv
clean_no_legacy_holdout_row_scores.csv
clean_no_legacy_holdout_summary.csv
loss_buckets.csv
source_review_log.csv
file_manifest.csv
```

## Note Placement Rule

Use this placement rule going forward:

```text
PIPELINE_OUTPUTS/CURRENT_STATUS_AND_NEXT_STEPS.md
  Current decisions, cross-stage next steps, and production-readiness notes.

PIPELINE_OUTPUTS/<stage>/
  Small stage handoff files intended for human inspection.

PIPELINE_OUTPUTS/<stage>/process_reviews/
  Human-facing process reviews, critiques, and go/no-go assessments for that stage.

AUDIT_TRAILS/START_HERE.md
  Navigation guide for choosing the right audit folder.

AUDIT_TRAILS/<run-or-stage>/
  Detailed evidence, manifests, logs, candidate ledgers, and historical
  artifact-specific explanations.

docs/replication_standards/
  Durable standards and process requirements, not pilot-specific diagnoses.
```
