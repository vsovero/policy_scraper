# Step 1 URL Discovery Run Contract

Created: 2026-06-23
Renamed and simplified: 2026-06-30

Authority: BINDING RUN CONTRACT. This file governs Step 1 URL-discovery
production chunks and benchmark runs. It cannot be weakened by process reviews,
generated reports, or submission prose.

This is the stable contract for Step 1 URL-discovery runs. It defines how a run
must be named, what evidence it must produce, and what claims it may support.
It is not the active status register. Current decisions, current blockers, and
which batch/chunk to run next belong in:

```text
policy_scraper/artifacts/PIPELINE_OUTPUTS/CURRENT_STATUS_AND_NEXT_STEPS.md
```

Current direction: do not extend the historical `pilot_batch_*` sequence as if
it were production. Future production construction should move to the clean
Step 1 production-runner contract below: explicit production inputs, no
`pilot_batch_*` runtime dependency, and a packageable `production_release_*`
handoff. `production_chunk_001` is transitional evidence from earlier pilot
work, not the model input contract for future production runs. The
implementation task is to extract and reorganize reusable discovery, retrieval,
review, and packaging code into a clean pipeline, not to add another wrapper
around old runs.

## Stage Boundary

Step 1 finds and validates institution-year source URLs. A Step 1 run may:

```text
build a target institution-year panel
generate candidate catalog/policy URLs
retrieve and validate candidate URLs
review source evidence
assign URL-stage ready/not-ready statuses
write source-ledger rows or benchmark scores, depending on run type
```

A Step 1 run does not:

```text
extract full source text for policy classification
search text for policy language
classify grade-forgiveness or grade-threshold policies
assemble the final analysis panel
stand in for the journal replication package
```

## Naming Rule

Use the run name to state the purpose of the work.

| Name | Use For | Meaning |
|---|---|---|
| `pilot_batch_*` | Existing historical batches only | Prior process tests, development runs, and regression evidence |
| `benchmark_*` | Clean validation tests | Tests of how well the computer can recover hidden human answers without seeing them |
| `production_chunk_*` | Dataset construction chunks | Bounded source-ledger construction for the actual dataset |
| `production_release_*` | Frozen release outputs | Package-ready dataset versions and final reproducible handoffs |

Keep old `pilot_batch_*` folders under
`policy_scraper/artifacts/PILOTS/url_discovery/`. Historical pilot outputs may be
used to identify failure modes, write general code/rule fixes, create tests, and
design benchmarks. They should not be required runtime inputs for future
production chunks or journal release packages. If a migration-only run uses an
old pilot output, label it as transitional and do not treat it as the clean
production-runner contract.

Recommended clean production layout:

```text
policy_scraper/artifacts/PIPELINE_OUTPUTS/01_url_discovery/
  production_chunks/
    production_chunk_<clean_runner_id>/
      README.md
      CHUNK_REPORT.md
      OUTPUT_urls_for_text_extraction.csv
      OUTPUT_source_ledger_delta.csv
      UNRESOLVED_ROWS.csv
      MANIFEST.json

policy_scraper/artifacts/AUDIT_TRAILS/
  url_discovery_production_chunk_<clean_runner_id>/
```

## Run Types

### Historical Pilot / Regression Evidence

Existing `pilot_batch_*` folders remain evidence of process tests and regression
runs under `policy_scraper/artifacts/PILOTS/url_discovery/`. They can show that
the command path, reporting, source review, and tests ran on a bounded batch.
They do not by themselves establish final production coverage or
publication-ready clean benchmark performance.

### Clean Benchmark

A `benchmark_*` run answers:

```text
How well can computer URL discovery recover valid human source URLs when those
answers are hidden from discovery?
```

Rules:

```text
pre-specify the target rows and hidden-answer denominator
withhold human legacy URLs from discovery inputs for scored rows
report valid-human recovery separately from prior-programmatic diagnostics
do not use old reviewed URLs to assign ready status before scoring
do not count production ledger recovery as clean benchmark success
```

The 90 percent recovery floor belongs to this lane only. It is not the standard
for production source-ledger construction.

### Production Chunk

A `production_chunk_*` run answers:

```text
Can this bounded set of institution-years be closed into a reproducible source
ledger?
```

Rules:

```text
target 100 percent ledger closure, not 90 percent hidden-answer recovery
recover every valid source possible
recover, promote, or row-invalidate every valid human legacy benchmark row
recover every prior-programmatic benchmark row in the current run or row-invalidate it
record unresolved/unrecoverable statuses for the rest
allow prior valid human evidence as transparent ledger provenance
keep prior-programmatic evidence visible as benchmark diagnostics only unless
the current run recovers and reviews the source
review every accepted source under the same source-review standard
never hide row-specific answers in scraper conditionals
separate general code/rule fixes from row-specific ledger decisions
```

Codex may assist coding, debugging, and source-review triage during production
construction. That assistance belongs in the AI-use disclosure and audit trail.
The required replication package must not require a live Codex step to repair
code or rediscover sources.

Production construction is not a clean out-of-sample validation claim. During
construction, Codex may observe failures, make general source/test fixes, commit
those fixes, and rerun the chunk from clean committed code. Those repaired runs
must be labeled as AI-assisted production construction or development/build
evidence, not clean benchmark evidence. The final claim is reproducibility of
the committed code, explicit inputs, source evidence, manifests, and source
ledger, not autonomous scraper performance on untouched data.

### Source Taxonomy For Legacy And Historical Leads

Step 1 source selection must separate human legacy evidence from historical
programmatic or LLM leads. This rule is binding for all production chunks,
release packages, benchmarks, and stream prompts.

Allowed source roles:

| Role | Meaning | May satisfy legacy selection? | May guide search? | May enter source ledger? |
|---|---|---:|---:|---:|
| `validated_human_legacy` | Human/curated public or private legacy URL/source evidence | yes | yes | yes, after current review |
| `prior_programmatic` | Earlier programmatic discovery accepted by review | no | yes | yes, only after current-run recovery and review |
| `imported_llm_candidate_lead` | Imported LLM, Claude, automated workbook, or suggestion-pool lead | no | yes | yes, only after current-run recovery and review |
| `failed_programmatic_attempt` | Historical attempt with no valid accepted discovery | no | yes, as diagnostics | no, unless current run finds and reviews evidence |

Hard rule:

```text
Automated, LLM, Claude, training, suggestion-pool, or private missing-sheet tabs
are not human legacy evidence. They must not contribute to legacy_covered_years,
valid_human_legacy rows, human legacy provenance, legacy benchmark denominators,
or prior_valid_legacy_reverification eligibility.
```

These leads should remain usable. They belong in a separate
`historical_lead_source_reconstruction` lane that selects public and private
historical lead cases symmetrically, labels them as lead reconstruction, and
requires current-run recovery plus source review before any source-ledger
acceptance.

Existing accepted source evidence is not automatically invalidated by a
taxonomy correction if the current run recovered and reviewed the source.
However, any row or institution that entered through an automated/LLM-as-legacy
path must be relabeled or audited before it is reported as legacy
reconstruction evidence.

### Journal-Ready Step 1 Successful Test Batch Goal

The active Step 1 goal is not satisfied by a smoke test, mini batch, generated
report, release folder, or `under review` status. The goal is to create one
bounded URL-stage test batch that is journal-standard for Step 1 and passes the
same gates that will govern scale-up.

`Successful test batch` means all of the following are true:

```text
the batch is selected from the frozen 4-year target panel, with the selection rule recorded
the clean Step 1 production runner starts from explicit production inputs
the run does not depend on pilot folders, old run folders, or hidden row-specific answers
every target row is accounted for as accepted, unresolved, invalidated, or out of scope
accepted sources are source-reviewed under the binding URL-source standard
valid human legacy evidence is reported as provenance when used
prior-programmatic evidence is reported only as diagnostics or benchmark evidence unless the current run recovers and reviews the source
a production_release_* package is built from the chunk
the release uses package-local relative paths and records exact commands, hashes, environment, inputs, outputs, and caches
cached source evidence is included or the missing evidence is explicitly labeled optional live retrieval
the release can be verified without a required live Codex/web repair step
a human process review crosswalks the run to Gate 1 and Gate 2 requirements
the process review explicitly says PASS for Gate 1 and Gate 2, or the goal is not complete
front-door status files are updated only after that review decision
tests/test_front_door_status_claim_gate.py passes after any front-door status edit
```

If any item is missing, the run is not a successful test batch and Codex must
keep fixing, rerunning, packaging, and reviewing until the Gate 1 and Gate 2
process review passes. `Not done`, `under review`, `partial pass`, and `fail`
are status labels only; they are not acceptable stopping points. Codex may stop
only for a real external blocker such as missing credentials, denied
permissions, unavailable required input data, or an external service outage, and
the blocker must be named precisely. A generated requirements table, manifest,
or verifier result is evidence for the review, not completion by itself.

This is a Step 1 URL-stage standard only. It does not claim that text
extraction, policy classification, final panel construction, or the full journal
replication package are complete.

### Stream Write Scope

Step 1 production construction uses this workflow:

```text
project-management task definition
-> build source/test fixes plus production chunk/release output
-> process review
-> project-management current status
```

Project-management streams define the work slice and publish front-door status.
Build streams may edit Step 1 URL-discovery source/tests and run-local
production output while constructing a chunk. Review streams write only the
process-review file. Project-management streams update current status only
after review. Testing, drill, smoke, or mini-batch streams remain output-only
lanes for clean benchmarks and limited checks, not the default production
construction lane. Integration streams remain available for narrow source/test
hotfixes outside a production build loop.

Build streams may fix general production-path bugs and discovery rules. They
must add or update tests, commit fixes, rerun from clean committed code, and
write a run-local build log. They must not hard-code row-specific source answers
into scraper logic.

| Stream scope | May edit | Must not edit |
|---|---|---|
| `testing` | Run-local generated output such as `CHUNK_REPORT.md`, `RUN_REPORT.md`, `TEST_REPORT.md`, `REQUIREMENTS_STATUS.csv`, manifests, ledgers, and caches | Process reviews, standards, current status, front-door README/START_HERE docs |
| `review` | The relevant process-review file and its protected-doc manifest hash | Test output, current status, front-door docs, standards |
| `build` | Step 1 URL-discovery source/tests plus run-local production chunk/release output and build logs | Current status, process reviews, standards docs, front-door README/START_HERE docs, protected-doc manifest, downstream classification files |
| `integration` | Step 1 production-runner/release-packager source files and matching tests only | Current status, process reviews, standards docs, generated output, unrelated discovery/classification/public/private modules |
| `project_management` | `CURRENT_STATUS_AND_NEXT_STEPS.md`, front-door README/START_HERE docs, standards when approved, and their manifest hashes | Test output and process-review files |

Allowed testing outputs include run-local files such as:

```text
CHUNK_REPORT.md
RUN_REPORT.md
TEST_REPORT.md
RELEASE_REPORT.md
MANIFEST.json
REQUIREMENTS_STATUS.csv
```

Protected documents include planning, standards, status, stage README, and
process-review files, especially:

```text
docs/**
artifacts/PIPELINE_OUTPUTS/CURRENT_STATUS_AND_NEXT_STEPS.md
artifacts/PIPELINE_OUTPUTS/START_HERE.md
artifacts/PIPELINE_OUTPUTS/**/README.md
artifacts/PIPELINE_OUTPUTS/**/process_reviews/**
artifacts/AUDIT_TRAILS/START_HERE.md
artifacts/PILOTS/**/README.md
```

If a run reveals that a protected document is wrong or incomplete, the testing
or build stream should record that finding in its own run-local report. The review stream
may record the review decision in the process-review file. The
project-management stream updates `CURRENT_STATUS_AND_NEXT_STEPS.md` only after
the review file supports the status claim or the user directly instructs it.
If an integration stream discovers that its allowed source/test slice is too
narrow, it should stop and report the extra files needed; project management can
then expand the allowed integration slice explicitly.

Persistent protected docs inside ignored `artifacts/` are hash-locked by:

```text
docs/replication_standards/protected_artifact_docs_manifest.csv
```

Testing streams must not update those protected artifact docs or the manifest.
Build and integration streams also must not update those protected artifact docs
or the manifest. Review streams may update only process-review rows in the
manifest. Project-management streams may update only front-door/status rows in
the manifest.

Every stream should create a scope baseline before it starts editing and check
against that baseline before reporting done:

Use the copy/paste prompts in:

```text
docs/replication_standards/codex_goals/stream_prompt_templates.md
```

```text
../.venv/bin/python -m course_policy.codex_scope_guard init --scope testing --baseline /private/tmp/codex_scope_testing.json
../.venv/bin/python -m course_policy.codex_scope_guard check --scope testing --baseline /private/tmp/codex_scope_testing.json

../.venv/bin/python -m course_policy.codex_scope_guard init --scope review --baseline /private/tmp/codex_scope_review.json
../.venv/bin/python -m course_policy.codex_scope_guard check --scope review --baseline /private/tmp/codex_scope_review.json

../.venv/bin/python -m course_policy.codex_scope_guard init --scope build --baseline /private/tmp/codex_scope_build.json
../.venv/bin/python -m course_policy.codex_scope_guard check --scope build --baseline /private/tmp/codex_scope_build.json

../.venv/bin/python -m course_policy.codex_scope_guard init --scope integration --baseline /private/tmp/codex_scope_integration.json
../.venv/bin/python -m course_policy.codex_scope_guard check --scope integration --baseline /private/tmp/codex_scope_integration.json

../.venv/bin/python -m course_policy.codex_scope_guard init --scope project_management --baseline /private/tmp/codex_scope_project_management.json
../.venv/bin/python -m course_policy.codex_scope_guard check --scope project_management --baseline /private/tmp/codex_scope_project_management.json
```

### Historical URL Discovery Inventory Contract

Historical URL discovery inventory is a planning support lane. It belongs in:

```text
artifacts/PIPELINE_OUTPUTS/01_url_discovery/historical_inventory/
artifacts/AUDIT_TRAILS/url_discovery_historical_inventory/
```

The inventory may scan old URL-extraction folders, clean-benchmark outputs,
pilot/regression outputs, old archives, and legacy artifacts to classify:

```text
valid human legacy evidence
accepted prior programmatic discovery needing current-run re-verification
unreviewed programmatic candidate leads
programmatic attempts with no valid discovery
institutions with no historical programmatic attempt found
```

The inventory is not a production chunk, source-ledger promotion step, clean
benchmark, or journal release. It cannot feed hidden URLs into the production
runner and cannot be a required runtime input for a journal release.

Hard gate: the clean Step 1 production runner must reject runtime inputs that
reference `historical_inventory/`,
`url_discovery_historical_inventory/`, `normalized_historical_url_attempts`,
`normalized_historical_discoveries`, or `institution_priority_buckets`.

Allowed use:

```text
rank batches
preserve old benchmark/failure information
identify candidate leads for current-run recovery
document where historical signals came from
```

Forbidden use:

```text
promote prior programmatic rows into the source ledger by itself
count prior programmatic rows as recovery evidence without current-run recovery and review
hide row-specific old URLs inside code or production inputs
make old output folders part of the normal production runtime contract
```

### Historical Inventory Rebuild Command

The official historical-inventory rebuild command must be run from a clean
`policy_scraper` checkout and must scan the durable quarantined artifact archive,
not a temporary or tiny salvage-worktree artifact folder:

```bash
PYTHONPATH=src ../.venv/bin/python -m course_policy.historical_url_inventory \
  --scan-root "/Users/verosovero/Dropbox/Course repetition IPEDS/_quarantine/policy_scraper_artifacts_20260702/artifacts"
```

This command writes URL-free planning outputs under:

```text
artifacts/AUDIT_TRAILS/url_discovery_historical_inventory/
artifacts/PIPELINE_OUTPUTS/01_url_discovery/historical_inventory/
```

The production runner may consume only the URL-free precheck generated from
these outputs. It must not consume historical URL attempts, normalized
historical discoveries, or `institution_priority_buckets.csv` as source evidence
or current recovery.

### Historical Case Precheck Gate

Every Step 1 coding/test batch must consult the historical URL-discovery
catalog before claiming completion, but it must do so through a URL-free
case-precheck control file rather than by feeding old ledgers into the production
runner.

Required precheck artifact:

```text
historical_case_precheck.csv
```

The precheck is a planning-memory gate. It must have one completed precheck row
for every target institution in the batch and must include:

```text
unitid
institution_name
historical_priority_bucket
valid_human_legacy_rows
prior_programmatic_accepted_rows
unreviewed_candidate_lead_rows
failed_attempt_rows
known_source_family_summary
known_failure_pattern_summary
historical_precheck_completed
runtime_input_guardrail_confirmed
precheck_created_by
precheck_created_at
```

Allowed precheck content:

```text
priority bucket
counts of historical evidence classes
source-family or host summaries
failure-pattern summaries
notes that guide general code/rule development
```

Forbidden precheck content:

```text
direct URLs
candidate_url, final_url, source_url, accepted_source_url, or benchmark_url columns
paths to historical_inventory/ or url_discovery_historical_inventory/
row-specific old URLs copied from historical ledgers
any field that promotes prior programmatic evidence into source evidence
```

Hard gate: the clean Step 1 production runner must require
`historical_case_precheck.csv`, must fail its requirements if any target
institution lacks a completed guardrail-confirmed precheck row, and must reject
the precheck if it contains direct URLs.

The historical case precheck is not source evidence. It can explain what the
coding stream should learn from past work, but current-run source review still
controls source-ledger promotion.

### Clean Step 1 Production Runner Contract

Future production chunks should be generated by a clean Step 1 production
runner. The runner should start from explicit production inputs, not from a
`pilot_batch_*` output folder or old pilot audit folder.

Implementation standard: reuse good code from pilot/benchmark scripts only by
moving or refactoring the general logic into production modules. The production
runner should orchestrate those modules directly. It should not shell out to,
transform, or depend on old run folders as the normal way to build a production
chunk or release.

Required front-door inputs:

```text
target_panel.csv
candidate_url_ledger.csv
source_review_log.csv
historical_case_precheck.csv
source_evidence_cache/manifest, when cached source evidence exists
optional benchmark_key.csv, used only for benchmark scoring after discovery/review
run configuration naming the chunk id, release id, sector/year scope, and API/web mode
```

Runner rules:

```text
do not accept `pilot_batch_*` as the normal production input contract
do not require `artifacts/PILOTS/` or old pilot audit folders to rebuild a production release
do not use hidden human/legacy URLs as discovery inputs for clean benchmark rows
use old pilot outputs only during development, debugging, test creation, or benchmark design
turn failure modes found in old outputs into general code/rules or explicit source-ledger rows
record all row-specific accepted sources in the source ledger, not in scraper conditionals
write a production input manifest that identifies every required runtime input
```

Expected output:

```text
production_chunk_*
-> OUTPUT_urls_for_text_extraction.csv
-> OUTPUT_source_ledger_delta.csv
-> UNRESOLVED_ROWS.csv
-> BENCHMARK_RECOVERY.csv / BENCHMARK_MISSES.csv when benchmark keys exist
-> REQUIREMENTS_STATUS.csv
-> MANIFEST.json
-> production_release_* package
-> package-local rebuild verification
```

If a legacy migration mode is kept temporarily, it must be named and reported as
migration/transitional evidence. It cannot be described as the clean
start-to-finish production runner and cannot be the normal journal release input
contract.

### First Production Chunk

`production_chunk_001` is the first bounded production-shaped source-ledger
artifact, but it was built from earlier pilot evidence. It should not be
described as a clean start-to-finish production runner, and future production
chunks should not copy its pilot-batch runtime-input pattern.

Purpose:

```text
close a bounded set of institution-years into the source ledger
preserve all accepted sources with provenance
preserve all unresolved/unrecoverable rows with explicit reasons
create the Step 1 handoff for later text extraction
```

Allowed evidence:

```text
active human legacy URLs, if valid and reviewed
valid prior programmatic discoveries only as benchmark diagnostics unless
current-run recovery/review reaccepts the source
new programmatic candidates generated by the current URL process
manual/Codex-assisted source review, recorded as review evidence
API-assisted candidates, only when live or cached API evidence is documented
```

Done criteria:

```text
the target panel is frozen before review
every target row has ready or not-ready status
every accepted URL has row-level and institution-panel source-review evidence
every unresolved row has a stop reason
the source-ledger delta records provenance for each accepted source
benchmark recovery and miss files show that old valid discoveries were not lost
the text-extraction handoff, unresolved-row table, report, and manifest agree
clean hidden-answer recovery is reported separately if benchmark answers exist
```

## Required Inputs

Every Step 1 run must freeze and document:

```text
run_id
run_type: historical_pilot, benchmark, production_chunk, or production_release
target institution-year panel
institution metadata and homepages
year range and sector rules
sample flags when relevant, including GF and threshold samples
available source-evidence inputs
API/web-rescue mode: live, cached, off, or not eligible
code version or commit/hash when available
```

The target panel must include, at minimum:

```text
unitid
institution_name
sector
state
academic_year
target-inclusion reason
estimation-sample or panel-fill flags when relevant
```

## Required Process

A complete run must preserve evidence for:

```text
candidate URL generation
candidate retrieval and HTTP/archive status
source-family or stop-reason buckets
source-review decisions
API/web-rescue prompts, calls, cache paths, and parsed outputs when used
accepted source URLs
unresolved/unrecoverable rows
manifest/hash information for generated outputs
```

Candidate URLs are not evidence by themselves. A URL becomes ready only after it
passes retrieval, institution identity, source-type, year-coverage, and
source-review checks.

## Required URL Output Fields

`OUTPUT_urls_for_text_extraction.csv` or the equivalent Step 1 handoff must
include:

```text
run_id
run_type
unitid
institution_name
sector
state
academic_year
url_status
ready_for_text_extraction
url_for_text_extraction
url_source_bucket
candidate_url
retrieval_status
http_status
review_decision
review_reason
source_review_file
unresolved_reason, when not ready
```

For production chunks, also write a source-ledger delta with:

```text
unitid
academic_year
accepted_source_url
source_type
source_year_coverage
provenance_type: prior_human, prior_programmatic, new_programmatic, manual_review, api_assisted
review_file
review_decision
evidence_hash_or_cache_path when available
```

## Required Front-Door Outputs

For benchmark and historical pilot/regression runs:

```text
OUTPUT_urls_for_text_extraction.csv
HOW_CREATED.md
BENCHMARKS_AND_ATTRITION.md
REQUIREMENTS_STATUS.csv
MANIFEST.json or equivalent manifest/hash record
```

For production chunks:

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

## Required Reporting

Every run report must state:

```text
target denominator
number of institutions and institution-years
ready/recovered rows
not-ready rows by stop reason
unreviewed candidate count, which should be zero at handoff
API/web-rescue mode and failures
source-review coverage
whether the run supports benchmark, production-chunk, or only historical claims
```

For production monitoring, report recovery and expansion separately:

```text
recovery lane: rows in the current GF/threshold samples
panel-fill lane: rows outside current samples that could expand coverage
```

## Done Criteria

A Step 1 run is complete only when:

```text
all target rows have a ready or explicit not-ready status
all accepted URLs have source-review evidence
all unresolved rows have explicit stop reasons
all API/model use or failure is documented when applicable
outputs, reports, requirements files, and manifests agree
row-specific answers are not hidden in code
```

A clean benchmark is complete only after hidden-answer scoring is regenerated
from the frozen run outputs.

A production chunk is complete only after every target row is represented in
the source-ledger delta or unresolved-row table, and every known valid old
human discovery is recovered, promoted into the source ledger with provenance,
or row-invalidated with a documented reason. Prior-programmatic benchmark rows
must be recovered by the current run or row-invalidated; they must not be
promoted into the source ledger from old programmatic evidence alone. If
`BENCHMARK_MISSES.csv` is nonempty, it must label which misses are already
source-ledger-resolved by valid human legacy evidence and which are still
programmatic-only source holes.

## Related Standards

```text
policy_scraper/docs/replication_standards/requirements_checklist.md
policy_scraper/docs/replication_standards/url_source_review_standard.md
policy_scraper/docs/replication_standards/supporting_rules/benchmark_protocol.md
policy_scraper/docs/replication_standards/supporting_rules/api_setup.md
policy_scraper/artifacts/PIPELINE_OUTPUTS/CURRENT_STATUS_AND_NEXT_STEPS.md
```
