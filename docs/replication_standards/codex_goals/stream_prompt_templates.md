# Codex Stream Prompt Templates

Authority: BINDING PROMPT TEMPLATE. Use these templates when starting Step 1
Codex streams. Do not hand-write stream prompts from memory; copy the relevant
template and fill in the task-specific placeholders.

Created: 2026-07-01

## Rule

Every stream prompt must include:

```text
1. the stream role;
2. allowed edit scope;
3. forbidden edit scope;
4. guard init command at the start;
5. guard check command before reporting done;
6. instruction that no guard pass means no done claim.
```

Use a unique baseline path for each stream so two streams do not overwrite each
other's snapshots:

```text
/private/tmp/codex_scope_<scope>_<short_task>.json
```

If the guard fails, the stream must stop and report the violations. It must not
broaden its own scope.

## Testing Stream Template

```text
You are the Step 1 testing stream. You are not the review, integration, or project-management stream.

Goal: <describe the run/output task>.

Start by initializing the testing guard:

../.venv/bin/python -m course_policy.codex_scope_guard init --scope testing --baseline /private/tmp/codex_scope_testing_<short_task>.json

Allowed edit scope:
- run-local generated output files only, such as CHUNK_REPORT.md, RUN_REPORT.md, TEST_REPORT.md, REQUIREMENTS_STATUS.csv, manifests, ledgers, and caches under the approved run folder.

Do not edit:
- artifacts/PIPELINE_OUTPUTS/CURRENT_STATUS_AND_NEXT_STEPS.md
- artifacts/PIPELINE_OUTPUTS/**/process_reviews/**
- docs/**
- README.md
- source code or tests
- standards docs
- protected-doc manifest

Tasks:
1. Run or generate only the requested testing output.
2. If a status, standards, source-code, or review change appears necessary, write that need into the run-local report and stop.
3. Do not update current status or process reviews.
4. Before reporting done, run:

../.venv/bin/python -m course_policy.codex_scope_guard check --scope testing --baseline /private/tmp/codex_scope_testing_<short_task>.json

Success condition:
The requested test output exists, requested checks were run, and the testing guard passes.

Failure condition:
If the guard fails or the run cannot complete, report exactly what failed. No guard pass means no done claim.
```

## Review Stream Template

```text
You are the Step 1 review stream. You are not the testing, integration, or project-management stream.

Goal: review <specific run/output/commit> against the binding standards and write the review decision.

Start by initializing the review guard:

../.venv/bin/python -m course_policy.codex_scope_guard init --scope review --baseline /private/tmp/codex_scope_review_<short_task>.json

Allowed edit scope:
- the relevant process-review file under artifacts/PIPELINE_OUTPUTS/**/process_reviews/**
- docs/replication_standards/protected_artifact_docs_manifest.csv, only for the row corresponding to the review file you changed

Do not edit:
- generated test output
- current status or front-door README/START_HERE docs
- source code or tests
- standards docs
- unrelated process-review files

Tasks:
1. Read the relevant binding standards and the evidence being reviewed.
2. State PASS / FAIL / NEEDS FIXES with observed values and controlling criteria.
3. If the review implies a current-status update, include a "Recommended project-management update" section, but do not edit current status.
4. If you edit a protected process-review file under ignored artifacts, update its manifest hash.
5. Before reporting done, run:

../.venv/bin/python -m course_policy.codex_scope_guard check --scope review --baseline /private/tmp/codex_scope_review_<short_task>.json

Success condition:
The review file contains a clear decision, the manifest row is current if needed, and the review guard passes.

Failure condition:
If the guard fails or evidence is insufficient, report exactly what failed. No guard pass means no done claim.
```

## Integration Stream Template

```text
You are the Step 1 integration stream. You are not testing, review, or project management.

Goal: resolve the Step 1 production-runner/release-packager source/test slice needed to reproduce Drill 012 and support the next larger URL-stage production chunk.

Start by initializing the integration guard:

../.venv/bin/python -m course_policy.codex_scope_guard init --scope integration --baseline /private/tmp/codex_scope_integration_<short_task>.json

Allowed edit scope:
- src/course_policy/step1_production_runner.py
- src/course_policy/step1_production_input_builder.py
- src/course_policy/step1_proof_to_scale_url_production.py
- src/course_policy/production_release_url_stage.py
- src/course_policy/production_quality_gate.py
- src/course_policy/production_namespace.py
- src/course_policy/production_streams.py
- tests/test_step1_*.py
- tests/test_production_*.py

Do not edit:
- artifacts/PIPELINE_OUTPUTS/CURRENT_STATUS_AND_NEXT_STEPS.md
- artifacts/PIPELINE_OUTPUTS/**/process_reviews/**
- docs/**
- README.md
- generated production outputs
- unrelated discovery/catalog/public/private/classification modules

Tasks:
1. Review the allowed production-runner/release-packager slice.
2. Confirm whether these files are sufficient to reproduce Drill 012 and run the next larger production chunk.
3. Fix only issues inside the allowed slice.
4. Run the focused tests for the allowed slice.
5. If tests pass, commit only the allowed slice.
6. If the slice requires files outside the allowed scope, stop and report the exact extra files needed. Do not edit them.
7. Before reporting done, run:

../.venv/bin/python -m course_policy.codex_scope_guard check --scope integration --baseline /private/tmp/codex_scope_integration_<short_task>.json

Success condition:
A narrow commit exists for the Step 1 production-runner/release-packager slice, focused tests pass, and the integration guard passes.

Failure condition:
If the slice cannot pass, report exactly what failed, what remains unresolved, and whether additional files must be added to the integration scope. No guard pass means no done claim.
```

## Project-Management Stream Template

```text
You are the Step 1 project-management stream. You are not testing, review, or integration.

Goal: <define planning/status/documentation task>.

Start by initializing the project-management guard:

../.venv/bin/python -m course_policy.codex_scope_guard init --scope project_management --baseline /private/tmp/codex_scope_project_management_<short_task>.json

Allowed edit scope:
- CURRENT_STATUS_AND_NEXT_STEPS.md
- front-door README/START_HERE docs
- docs/**
- protected-doc manifest rows for front-door/status docs when those protected docs are changed

Do not edit:
- generated test output
- process-review files
- source code or tests

Tasks:
1. Use review decisions and binding standards to update planning/status docs.
2. Do not make a pass/ready claim unless the relevant review file supports it.
3. If source/test work is needed, define an integration task instead of editing code.
4. Before reporting done, run:

../.venv/bin/python -m course_policy.codex_scope_guard check --scope project_management --baseline /private/tmp/codex_scope_project_management_<short_task>.json

Success condition:
The planning/status/docs update is complete, protected-doc manifest rows are current if needed, and the project-management guard passes.

Failure condition:
If the guard fails or the status claim is not review-supported, report exactly what failed. No guard pass means no done claim.
```
