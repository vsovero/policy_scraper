# URL Discovery Clean Production Runner Review

Created: 2026-07-01
Updated: 2026-07-01

This review covers the clean Step 1 URL-discovery production runner, its focused
tests, and the current smoke output. It is separate from:

```text
url_discovery_pilot_batches_review.md
url_discovery_production_chunks_review.md
```

## Scope

Reviewed runner and tests:

```text
src/course_policy/step1_production_runner.py
src/course_policy/production_release_url_stage.py
tests/test_step1_production_runner.py
tests/test_production_release_url_stage.py
```

Reviewed smoke output, now archived as clean-runner test evidence:

```text
artifacts/PILOTS/url_discovery/clean_runner_tests/pipeline_outputs/production_chunks/production_chunk_clean_runner_smoke_001/
artifacts/PILOTS/url_discovery/clean_runner_tests/pipeline_outputs/production_releases/production_release_clean_runner_smoke_001/
```

This is a clean-runner smoke check. It is not a downstream text extraction,
policy classification, adjudication, final panel, or full journal-release
review. It is also not a current production chunk or current production release.

## Standards Applied

The relevant current-stage standards are:

```text
docs/replication_standards/codex_goals/step_1_url_discovery_run_contract.md
docs/replication_standards/requirements_checklist.md
docs/replication_standards/supporting_rules/benchmark_protocol.md
```

Current-stage requirements reviewed here:

```text
clean production runner must use explicit production inputs, not pilot runtime folders
each target row must be in source ledger or unresolved table
accepted URLs must have source-review evidence
unresolved rows must have explicit stop reasons
no candidate URL should be left unreviewed at handoff
benchmark misses must be zero when a benchmark key is supplied
release package must use package-local paths and preserve manifests/checksums
required rebuild/verification must not require live Codex repair or live web rediscovery
```

## Smoke Output Status

The current checked-in smoke output passes the current-stage artifact checks.

Chunk output:

```text
target rows:                  2
ready/source-ledger rows:     1
unresolved rows:              1
benchmark misses:             0
REQUIREMENTS_STATUS.csv:      7/7 pass
```

Release output:

```text
release_manifest.csv rows:              39
rebuild_check.csv rows:                 39
rebuild_check.csv non-pass rows:         0
rebuild_check_log.txt status:          pass
unmanifested_failures:                   0
local_absolute_path_failures:             0
```

The release verification command succeeds from the release root:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=code/source_snapshot/src python -m course_policy.production_release_url_stage --release-root . --verify-only
files_checked=39
unmanifested_failures=0
local_absolute_path_failures=0
status=pass
```

I did not find local absolute paths in the smoke release runtime artifacts. I
did find forbidden pilot strings in `data/requirements_status.csv`, but only
inside the rule text saying pilot paths are forbidden. That is not a runtime
dependency. Runtime/input columns checked clean:

```text
audit/production_input_manifest.csv:      0 pilot-runtime hits; 0 local absolute path hits
audit/input_manifest.csv:                 0 pilot-runtime hits; 0 local absolute path hits
data/reviewed_url_handoff_panel.csv:      0 pilot-runtime hits; 0 local absolute path hits
data/source_ledger.csv:                   0 pilot-runtime hits; 0 local absolute path hits
data/source_review_log.csv:               0 pilot-runtime hits; 0 local absolute path hits
data/candidate_url_ledger.csv:            0 pilot-runtime hits; 0 local absolute path hits
source_evidence_manifest.csv:             0 pilot-runtime hits; 0 local absolute path hits
audit/production_command.txt:             0 local absolute path hits
audit/construction_chunk_manifest.json:   0 local absolute path hits
```

## Test Status

The focused runner tests now pass.

```text
../.venv/bin/python -m pytest tests/test_step1_production_runner.py tests/test_production_release_url_stage.py
6 passed
```

## Findings

1. The smoke output and runner/test gate now pass at the current stage.

The current smoke artifact passes the current-stage artifact checks, and the
focused tests now pass. This supports treating the clean runner as
current-stage guideline-compliant for the smoke scope.

2. Pilot-runtime input rejection is now covered by the test gate.

`step1_production_runner.py` is supposed to reject `pilot_batch_*`,
`artifacts/PILOTS/`, and old pilot audit paths as clean-runner runtime inputs.
The test fixture intentionally inserts a forbidden path:

```text
artifacts/PILOTS/url_discovery/pipeline_outputs/pilot_batch_001/foo.csv
```

The focused test now passes, meaning the runner rejects that pilot-runtime input
path as required. The checked-in smoke output also has no pilot-runtime hits in
the production input manifest or release runtime data columns.

3. Release path sanitization is now covered by the test gate.

The release package test now passes for the temporary-root case that previously
left an absolute path in `source_evidence_manifest.csv`:

```text
abc123 /private/.../current_run_reattempt_source_review.csv
```

The smoke release also verifies with `local_absolute_path_failures=0`.

4. The current smoke output should remain a smoke pass, not a full production
coverage claim.

The smoke output has 2 target rows and is useful for testing the clean-runner
contract. It should not be described as a full production batch or final journal
replication package.

## Current Decision

```text
Smoke output artifact:                    PASS
Clean production runner implementation:   PASS for current Stage 1 smoke scope
Clean production runner test gate:         PASS
Downstream/final-journal stages:           NOT APPLICABLE AT STAGE 1
```

## Conditions To Preserve

No current-stage blocking fixes remain for the clean-runner smoke gate. Preserve
these checks in future runner changes:

1. Keep rejecting `pilot_batch_*`, `artifacts/PILOTS/`, and old pilot audit
   paths as clean-runner runtime inputs.
2. Keep release runtime artifacts free of local absolute paths.
3. Keep `PYTHONDONTWRITEBYTECODE=1` in the package-local verification command.
4. Keep all required files manifested or documented in `manifest_exclusions.csv`.
5. Re-run the focused tests after any runner or release-packager change:

```text
../.venv/bin/python -m pytest tests/test_step1_production_runner.py
../.venv/bin/python -m pytest tests/test_production_release_url_stage.py
```

6. Rebuild or rerun the clean smoke output after substantive runner changes,
then update this review with the new test and artifact status.

## Stage Boundary

The `journal_release_ready=fail` flag in `release_status.csv` is expected at
Stage 1 and is not a clean-runner defect. Downstream text retrieval, policy
excerpt search, policy classification, human adjudication, final panel
construction, and final analysis outputs belong to later stages.
