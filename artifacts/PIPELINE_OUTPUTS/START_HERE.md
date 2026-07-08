# Policy Pipeline Outputs

Open this folder first for policy-database pipeline products.

## Open First

```text
CURRENT_STATUS_AND_NEXT_STEPS.md
CLEAN_REBUILD_VALIDATION_PLAN.md
PRODUCTION_SAMPLE_COVERAGE_STATUS.md
01_url_discovery/README.md
01_url_discovery/production_chunks/
01_url_discovery/process_reviews/
```

## Folder Meaning

```text
PIPELINE_OUTPUTS/
  Human-facing current stage outputs and status reports. This should stay small.

PILOTS/
  Historical pilot, development, and regression runs. Use this when you need old
  pilot evidence, not current production handoffs.

AUDIT_TRAILS/
  Detailed evidence, candidate ledgers, validation audits, source-review logs,
  cached retrieval outputs, and manifests needed for replication.

OLD_OUTPUT_ARCHIVES/
  Superseded layouts and historical output attempts kept so nothing is lost.
```

## Reporting Organization Rules

Keep this folder as the small human-facing map. Do not add one-off run notes at
the top level.

Use these homes:

```text
CURRENT_STATUS_AND_NEXT_STEPS.md
  Current bottom line, current blockers, next action, and concise run inventory.

CLEAN_REBUILD_VALIDATION_PLAN.md
  Validation design for computer-versus-human pipeline performance.

PRODUCTION_SAMPLE_COVERAGE_STATUS.md
  Current coverage against target samples/universe.

01_url_discovery/README.md
  Stage front door for URL-discovery outputs.

01_url_discovery/process_reviews/
  Review notes for specific URL-discovery runs or runner gates.

artifacts/PILOTS/url_discovery/
  Pilot, smoke-test, mini-batch, regression, and superseded URL-discovery runs.
```

Every new report or run folder should be linked from the nearest stage README or
from `CURRENT_STATUS_AND_NEXT_STEPS.md`. If it is not linked, it is probably
buried in the wrong place.

Pass-claim gate:

```text
Generated chunk/release outputs propose evidence.
Review-stream process reviews decide whether the evidence satisfies binding standards.
Front-door status files summarize the process-review decision.
```

Do not update `CURRENT_STATUS_AND_NEXT_STEPS.md` or a stage `README.md` with
`pass`, `ready to scale`, `production ready`, or `journal standard` language
unless the relevant process review explicitly reaches that same decision. If
the generated report says pass but the process review says fail or partial pass,
the process review controls the front-door summary.

For the active Step 1 URL-stage test-batch goal, `under review`, `partial pass`,
`fail`, or `not tested` means the goal is still open. Codex should keep fixing,
rerunning, packaging, and reviewing until Gate 1 and Gate 2 pass, unless a
precise external blocker is documented.

Required check before editing front-door status claims:

```text
../.venv/bin/python -m pytest tests/test_front_door_status_claim_gate.py
```

Testing-stream write scope:

```text
Testing, drill, smoke, and mini-batch streams may edit only run-local generated
artifacts unless the user explicitly authorizes a protected document edit.
Do not edit CURRENT_STATUS_AND_NEXT_STEPS.md, START_HERE.md, stage README files,
docs/**, or process_reviews/** from a testing stream.
Record needed planning/review changes in the run-local report instead.
```

Required check for testing streams:

```text
CODEX_STREAM_SCOPE=testing ../.venv/bin/python -m pytest tests/test_codex_testing_write_scope.py
```

Historical-inventory runtime gate:

```text
Historical URL discovery inventory is planning evidence only. It must not become
a production-runner runtime input or source-ledger promotion shortcut.
```

Required coding gate:

```text
../.venv/bin/python -m pytest tests/test_step1_production_runner.py::test_clean_runner_rejects_historical_inventory_runtime_inputs
```

## Current Status

Current decisions, next steps, and production-readiness notes live in:

```text
CURRENT_STATUS_AND_NEXT_STEPS.md
```

The active plan for the self-contained computer-versus-human validation rebuild
lives in:

```text
CLEAN_REBUILD_VALIDATION_PLAN.md
```

The prototype sample-coverage front-door report is:

```text
PRODUCTION_SAMPLE_COVERAGE_STATUS.md
```

## Step 1 URL Discovery

Current production-facing Step 1 outputs live in:

```text
01_url_discovery/
```

Historical pilot batches were moved out of the normal Step 1 output view and
consolidated under:

```text
policy_scraper/artifacts/PILOTS/url_discovery/
```

Clean-runner smoke and mini-batch testing evidence lives under:

```text
policy_scraper/artifacts/PILOTS/url_discovery/clean_runner_tests/
```

Those runs are regression/test evidence, not current production chunks or
production releases.

New dataset-construction work should use:

```text
01_url_discovery/production_chunks/production_chunk_*/
```

New frozen release handoffs should use:

```text
01_url_discovery/production_releases/production_release_*/
```

## Naming Convention Going Forward

```text
pilot_batch_*        = historical process tests/regression evidence
benchmark_*          = clean validation tests
production_chunk_*   = bounded dataset-construction/source-ledger work
production_release_* = frozen package-ready outputs
```

Do not create new top-level pilot folders in `PIPELINE_OUTPUTS/01_url_discovery/`.
Pilot history belongs under `policy_scraper/artifacts/PILOTS/`.
