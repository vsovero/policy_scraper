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

## Production Construction Rule

Step 1 production construction is an AI-assisted build process, not a clean
out-of-sample validation benchmark. A Step 1 build stream may diagnose failures,
make general source/test fixes, commit those fixes, and rerun from clean
committed code until it produces a coherent production chunk/release or reaches
a real blocker.

This does not weaken review. Build streams must not update current status,
front-door docs, process reviews, standards, or protected-doc manifest rows.
Generated reports remain evidence, not authority. A final PASS still requires a
separate review stream and then a project-management status update.

## Clean Runtime Rule

For any Step 1 production-runner, build, integration, review, or testing task
that imports `course_policy` or runs Step 1 code, the stream must force the
package source to the clean checkout:

```text
PYTHONPATH=src ../.venv/bin/python ...
```

Do not rely on ambient virtualenv imports. If `../.venv/bin/python` works only
without `PYTHONPATH=src`, the run is contaminated by another worktree and must
be treated as failed. A clean-runtime import check is required before any
integration or review stream may report PASS on Step 1 production-runner code:

```text
PYTHONPATH=src ../.venv/bin/python -c "import course_policy.step1_proof_to_scale_url_production"
```

When reviewing a commit, run this check from a clean checkout/worktree of the
commit being reviewed, not from a dirty project-management or testing worktree.

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
2. For any command that imports `course_policy` or runs Step 1 code, use `PYTHONPATH=src ../.venv/bin/python ...`.
3. If the command works only without `PYTHONPATH=src`, stop and report runtime contamination.
4. If a status, standards, source-code, or review change appears necessary, write that need into the run-local report and stop.
5. Do not update current status or process reviews.
6. Before reporting done, run:

../.venv/bin/python -m course_policy.codex_scope_guard check --scope testing --baseline /private/tmp/codex_scope_testing_<short_task>.json

Success condition:
The requested test output exists, requested checks were run with a clean `PYTHONPATH=src` runtime when Step 1 code was imported, and the testing guard passes.

Failure condition:
If the guard fails or the run cannot complete, report exactly what failed. No guard pass means no done claim.
```

## Build Stream Template

```text
You are the Step 1 production build stream. You are not the review or project-management stream.

Goal: construct <describe production chunk/release target> from explicit Step 1 production inputs. This is production construction, not a clean out-of-sample benchmark claim.

Start from a clean checkout/worktree of current origin/main. Do not use the parked dirty original worktree.

Start by initializing the build guard:

../.venv/bin/python -m course_policy.codex_scope_guard init --scope build --baseline /private/tmp/codex_scope_build_<short_task>.json

Clean-runtime rule:
Use `PYTHONPATH=src ../.venv/bin/python ...` for every command that imports `course_policy` or runs Step 1 code.

Allowed edit scope:
- Step 1 URL-discovery production/build source files and matching tests named by the build guard.
- run-local generated output under the approved `production_chunk_*` and `production_release_*` folders.
- run-local build logs such as `BUILD_LOG.md` or `SUPERVISOR_RUN_REPORT.md` inside the approved production chunk folder.

Do not edit:
- artifacts/PIPELINE_OUTPUTS/CURRENT_STATUS_AND_NEXT_STEPS.md
- artifacts/PIPELINE_OUTPUTS/**/process_reviews/**
- docs/**
- README.md
- standards docs
- protected-doc manifest
- downstream policy-classification source/tests unless a separate approved scope is created

Tasks:
1. Run the clean-runtime import check:

PYTHONPATH=src ../.venv/bin/python -c "import course_policy.step1_proof_to_scale_url_production; print('import ok')"

2. Run a focused clean-runtime preflight before the production attempt.
3. Build the requested `production_chunk_*` and matching `production_release_*` from explicit production inputs.
4. If the production path fails because source/test code needs a fix, make a general fix, add or update regression tests, commit the fix narrowly, and rerun from clean committed code.
5. Do not hard-code institutions, years, URLs, rows, or benchmark answers into source logic.
6. Keep a run-local `BUILD_LOG.md` or `SUPERVISOR_RUN_REPORT.md` listing each code fix commit, failed command, fix summary, tests, rerun command, and remaining risk.
7. Stop only when either:
   - a coherent chunk/release package exists and is ready for review; or
   - a real blocker remains that cannot be fixed inside the build scope.
8. Before reporting done, run:

../.venv/bin/python -m course_policy.codex_scope_guard check --scope build --baseline /private/tmp/codex_scope_build_<short_task>.json

Success condition:
Report `DONE, READY FOR REVIEW` only when the final chunk/release was produced from clean committed code, required tests/checks were run with `PYTHONPATH=src`, the build log exists, and the build guard passes.

Failure condition:
Report `NOT DONE` only for a concrete blocker. Include the failed command, blocker, files changed or not changed, tests run, latest commit hash if any, and guard result.

Important:
The build stream cannot declare PASS, ready-to-scale, or journal-ready. Generated outputs and build logs are evidence for review. The review stream decides pass/fail; project management updates current status only after review.
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
2. If reviewing source/test integration or a production-runner commit, independently run the clean-runtime import check from a clean checkout/worktree of the reviewed commit:

PYTHONPATH=src ../.venv/bin/python -c "import course_policy.step1_proof_to_scale_url_production"

3. If reviewing Step 1 production-runner code, rerun the focused tests with `PYTHONPATH=src`. A PASS decision is forbidden if clean-runtime import or focused clean-runtime tests fail.
4. State PASS / FAIL / NEEDS FIXES with observed values and controlling criteria.
5. If the review implies a current-status update, include a "Recommended project-management update" section, but do not edit current status.
6. If you edit a protected process-review file under ignored artifacts, update its manifest hash.
7. Before reporting done, run:

../.venv/bin/python -m course_policy.codex_scope_guard check --scope review --baseline /private/tmp/codex_scope_review_<short_task>.json

Success condition:
The review file contains a clear decision, clean-runtime import/tests are reported when reviewing Step 1 production-runner code, the manifest row is current if needed, and the review guard passes.

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
3. Reproduce source/test behavior with a clean runtime by using `PYTHONPATH=src` on all Python commands that import `course_policy`.
4. Run this clean-runtime import check before reporting success:

PYTHONPATH=src ../.venv/bin/python -c "import course_policy.step1_proof_to_scale_url_production"

5. If the import check fails because a committed module depends on a missing helper, stale API, or dirty-worktree-only file, fix the dependency generally inside the approved integration scope or stop and report the exact extra files needed.
6. Fix only issues inside the allowed slice.
7. Run the focused tests for the allowed slice with `PYTHONPATH=src`.
8. If tests pass and the clean-runtime import check passes, commit only the allowed slice.
9. If the slice requires files outside the allowed scope, stop and report the exact extra files needed. Do not edit them.
10. Before reporting done, run:

../.venv/bin/python -m course_policy.codex_scope_guard check --scope integration --baseline /private/tmp/codex_scope_integration_<short_task>.json

Success condition:
A narrow commit exists for the Step 1 production-runner/release-packager slice, clean-runtime import passes, focused tests pass with `PYTHONPATH=src`, and the integration guard passes.

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
