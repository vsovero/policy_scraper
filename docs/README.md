# Policy Scraper Docs

Use this folder for replication-standard documentation only. The pipeline
outputs themselves live in:

```text
policy_scraper/artifacts/PIPELINE_OUTPUTS/
```

## Open First

Current work is the transition from Step 1 URL-discovery pilots to Step 1
production source-ledger construction. Open these first:

```text
replication_standards/README.md
replication_standards/codex_goals/step_1_url_discovery_run_contract.md
```

Historical pilot/regression outputs live in:

```text
policy_scraper/artifacts/PILOTS/url_discovery/
```

Clean-runner smoke and mini-batch test evidence lives in:

```text
policy_scraper/artifacts/PILOTS/url_discovery/clean_runner_tests/
```

Current status, cross-stage next steps, and production-readiness notes live in:

```text
policy_scraper/artifacts/PIPELINE_OUTPUTS/CURRENT_STATUS_AND_NEXT_STEPS.md
```

The active plan for the self-contained computer-versus-human validation rebuild
lives in:

```text
policy_scraper/artifacts/PIPELINE_OUTPUTS/CLEAN_REBUILD_VALIDATION_PLAN.md
```

Current reproducibility rule:

```text
Codex may assist code development, debugging, and source-review triage, but the
required replication package should not ask Codex to fix code or rediscover
sources. General discoveries become general code/rules. Row-specific accepted
sources become rows in a frozen source ledger. The final dataset rebuilds from
that ledger and archived/cached artifacts.
```

Human-written process reviews and go/no-go notes live in:

```text
policy_scraper/artifacts/PIPELINE_OUTPUTS/01_url_discovery/process_reviews/
```

The detailed audit evidence lives in:

```text
policy_scraper/artifacts/AUDIT_TRAILS/START_HERE.md
```

## Documentation Organization Rules

Use one home for each kind of note:

```text
docs/replication_standards/
  Stable standards, checklists, run contracts, and journal-readiness rules.

artifacts/PIPELINE_OUTPUTS/CURRENT_STATUS_AND_NEXT_STEPS.md
  Current bottom line, current blockers, and next action.

artifacts/PIPELINE_OUTPUTS/<stage>/process_reviews/
  Human-written review of a run, chunk, or stage.

artifacts/PILOTS/
  Pilot, smoke-test, mini-batch, regression, and superseded run evidence.

artifacts/AUDIT_TRAILS/
  Detailed manifests, logs, cached evidence, and evidence snapshots.
```

Do not create a new Markdown file unless it has a clear owner folder and is
linked from the nearest `README.md`, `START_HERE.md`, or current-status file in
the same edit. If the same conclusion belongs in multiple places, write it once
in the owner file and add short pointers elsewhere.

Pass-claim gate: a front-door file such as `CURRENT_STATUS_AND_NEXT_STEPS.md` or
a stage `README.md` may not say a run passed, is production ready, is ready to
scale, or is journal standard unless the relevant process review explicitly says
the same thing after checking the binding standards. Generated files such as
`CHUNK_REPORT.md`, `REQUIREMENTS_STATUS.csv`, `MANIFEST.json`, and `run_config`
can provide evidence, but they cannot authorize pass language by themselves. If
the process review is missing or conflicts with a generated report, the front
door must say `under review`, `partial pass`, or `fail` rather than `pass`.

For the active Step 1 URL-stage test-batch goal, those are status labels, not
completion states; the next Codex run should keep fixing, rerunning, packaging,
and reviewing until Gate 1 and Gate 2 pass unless there is a precise external
blocker.

Before editing front-door status claims, run:

```text
../.venv/bin/python -m pytest tests/test_front_door_status_claim_gate.py
```

Stream write scope follows this chain:

```text
testing output -> process review -> project-management current status
```

Use the scopes this way:

| Stream scope | May edit | Must not edit |
|---|---|---|
| `testing` | Run-local generated output such as `CHUNK_REPORT.md`, `RUN_REPORT.md`, `TEST_REPORT.md`, `REQUIREMENTS_STATUS.csv`, manifests, ledgers, and caches | Process reviews, standards, current status, front-door README/START_HERE docs |
| `review` | The relevant process-review file and its protected-doc manifest hash | Test output, current status, front-door docs, standards |
| `project_management` | `CURRENT_STATUS_AND_NEXT_STEPS.md`, front-door README/START_HERE docs, standards when approved, and their manifest hashes | Test output and process-review files |

Each stream should create a baseline at the start of its work and check against
that same baseline before reporting done. This makes the guard usable in a dirty
shared worktree because it checks only what changed after the stream started.

Testing streams should run:

```text
../.venv/bin/python -m course_policy.codex_scope_guard init --scope testing --baseline /private/tmp/codex_scope_testing.json
../.venv/bin/python -m course_policy.codex_scope_guard check --scope testing --baseline /private/tmp/codex_scope_testing.json
```

Review streams should run:

```text
../.venv/bin/python -m course_policy.codex_scope_guard init --scope review --baseline /private/tmp/codex_scope_review.json
../.venv/bin/python -m course_policy.codex_scope_guard check --scope review --baseline /private/tmp/codex_scope_review.json
```

Project-management streams should run:

```text
../.venv/bin/python -m course_policy.codex_scope_guard init --scope project_management --baseline /private/tmp/codex_scope_project_management.json
../.venv/bin/python -m course_policy.codex_scope_guard check --scope project_management --baseline /private/tmp/codex_scope_project_management.json
```

Persistent status/review docs under ignored `artifacts/` are also hash-locked
in `replication_standards/protected_artifact_docs_manifest.csv`. Testing streams
may not update those files or the manifest. A review stream may update only
process-review rows in the manifest. A project-management stream may update only
front-door/status rows in the manifest.

Historical URL-discovery inventory is allowed for batch-priority planning and
benchmark preservation, not as production-runner input. The coding gate is:

```text
../.venv/bin/python -m pytest tests/test_step1_production_runner.py::test_clean_runner_rejects_historical_inventory_runtime_inputs
```

## Folder Meaning

Everything current is organized under:

```text
replication_standards/
```

Start with:

```text
replication_standards/requirements_checklist.md
replication_standards/url_source_review_standard.md
```

```text
replication_standards/
  Publication, replication-package, and LLM/AI-use requirements. The current
  Step 1 run contract, supporting rules, and old design notes live inside this
  folder so there is one standard.
```

## Current Rule

The active Step 1 process should be documented stage-by-stage in
`policy_scraper/artifacts/PIPELINE_OUTPUTS/`. This docs folder defines the
standards and goals; it should not become a second output folder.

New production work should be labeled `production_chunk_*`, not
`pilot_batch_*`. A production chunk is complete only when every target
institution-year is represented in the source ledger or in an unresolved-row
table with an explicit reason.
