# Step 1 Production Runner Integration Review

Reviewed on 2026-07-01 by the Step 1 review stream.

## Decision

**PASS.**

Commit `13f8f792696a43253ecf6ed66a0ae82e42b103da` is acceptable as the
expanded Step 1 production-runner/release-packager dependency-closure commit.
It supports reproducing Drill 012 and running the next larger URL-stage
production chunk, provided the next run keeps the existing process-review gate
around generated pass/fail claims.

## Commit Reviewed

- `13f8f792696a43253ecf6ed66a0ae82e42b103da`
- Commit title: `Add Step 1 production URL release runner`

## Files Reviewed

Committed source files:

- `src/course_policy/benchmark_protocol.py`
- `src/course_policy/catalog_url_harmonization.py`
- `src/course_policy/clean_no_legacy_benchmark.py`
- `src/course_policy/gfdatafull_panel_benchmark.py`
- `src/course_policy/legacy_reproduction_benchmark.py`
- `src/course_policy/production_namespace.py`
- `src/course_policy/production_quality_gate.py`
- `src/course_policy/production_release_url_stage.py`
- `src/course_policy/production_streams.py`
- `src/course_policy/public_fresh_discovery.py`
- `src/course_policy/public_fresh_discovery_pipeline.py`
- `src/course_policy/step1_production_input_builder.py`
- `src/course_policy/step1_production_runner.py`
- `src/course_policy/step1_proof_to_scale_url_production.py`

Committed tests:

- `tests/test_benchmark_protocol.py`
- `tests/test_catalog_url_harmonization.py`
- `tests/test_clean_no_legacy_benchmark.py`
- `tests/test_gfdatafull_panel_benchmark.py`
- `tests/test_legacy_reproduction_benchmark.py`
- `tests/test_production_namespace.py`
- `tests/test_production_quality_gate.py`
- `tests/test_production_release_url_stage.py`
- `tests/test_production_streams.py`
- `tests/test_public_fresh_discovery.py`
- `tests/test_public_fresh_discovery_pipeline.py`
- `tests/test_step1_production_input_builder.py`
- `tests/test_step1_production_runner.py`
- `tests/test_step1_proof_to_scale_url_production.py`

No committed changes were found in source standards, status documents, process
reviews, generated pipeline outputs, or `CURRENT_STATUS_AND_NEXT_STEPS.md`.

## Tests Reviewed

Focused test command run by this review:

```text
PYTHONDONTWRITEBYTECODE=1 ../.venv/bin/python -m pytest -p no:cacheprovider tests/test_benchmark_protocol.py tests/test_catalog_url_harmonization.py tests/test_clean_no_legacy_benchmark.py tests/test_gfdatafull_panel_benchmark.py tests/test_legacy_reproduction_benchmark.py tests/test_production_namespace.py tests/test_production_quality_gate.py tests/test_production_release_url_stage.py tests/test_production_streams.py tests/test_public_fresh_discovery.py tests/test_public_fresh_discovery_pipeline.py tests/test_step1_production_input_builder.py tests/test_step1_production_runner.py tests/test_step1_proof_to_scale_url_production.py
```

Result: **165 passed, 1 warning**.

The warning is a pandas deprecation warning in
`public_fresh_discovery_pipeline.py`; it does not affect the reviewed Step 1
scope decision.

## Scope Decision

1. **Approved slice only:** Pass.
   The commit adds 14 source files and 14 matching test files. The committed
   paths are source/test files for the Step 1 production-runner,
   production-input builder, proof-to-scale harness, production namespace,
   quality gate, release packager, benchmark protocol, clean no-legacy support,
   and URL-discovery dependency closure.

2. **Dependency files justified:** Pass.
   The extra files outside the narrow initial template are justified by the
   expanded dependency closure:
   `step1_proof_to_scale_url_production.py` depends on clean no-legacy discovery
   and current-run proof helpers; `clean_no_legacy_benchmark.py` depends on
   benchmark protocol, URL harmonization, legacy/current benchmark helpers,
   production stream definitions, and public fresh-discovery helpers; the
   production runner depends on the release packager. These files are not
   accidental status, standards, process-review, generated-output, or downstream
   policy-classification edits.

3. **Focused tests cover the committed slice:** Pass.
   Every committed source file has a corresponding committed focused test file.
   The focused test suite exercises benchmark guardrails, URL harmonization,
   clean no-legacy benchmark behavior, legacy and GFData benchmark helpers,
   namespace and quality-gate behavior, release packaging, production streams,
   public fresh discovery dependencies, production input building, the Step 1
   production runner, and the proof-to-scale harness.

4. **Supports Drill 012 reproduction and next larger chunk:** Pass.
   The committed runner/release-packager slice supplies the package-local
   production chunk builder, release package verifier, AI/API provenance and
   source-lineage packaging hooks, explicit production input builder, and
   proof-to-scale harness needed to reproduce the Drill 012 style of URL-stage
   release and run the next larger production chunk.

5. **Avoided forbidden edits:** Pass.
   Commit `13f8f79` does not edit source standards, status files, process-review
   files, generated outputs, `CURRENT_STATUS_AND_NEXT_STEPS.md`, or unrelated
   documentation. The large uncommitted worktree state is pre-existing and is not
   part of the reviewed commit.

6. **Integration guard:** Pass.
   The review reran the integration guard against the expanded Step 1 integration
   baseline:

```text
../.venv/bin/python -m course_policy.codex_scope_guard check --scope integration --baseline /private/tmp/codex_scope_integration_expanded_step1.json
```

Result: **integration scope check passed**.

## Remaining Risks

- The commit is large, especially `clean_no_legacy_benchmark.py`. The size is
  justified by dependency closure, but future work should keep follow-up commits
  narrower.
- The focused tests are strong for the committed slice, but they are not a full
  end-to-end rerun of a large production chunk.
- The generated `release_status.csv` files still defer ready-to-scale authority
  to process review. That is correct, but the next production run must preserve
  this rule and must not let generated reports self-authorize pass criteria.
- Clean no-legacy benchmark support is included as infrastructure, but Drill 012
  remains a legacy carry-forward/source-review lane unless a clean no-legacy
  benchmark is run with human legacy URLs hidden.

## Required Next Action

Proceed to the next larger URL-stage production batch using the committed Step 1
production runner/release packager, and require the same post-run process review
gate before claiming ready-to-scale or journal-grade status.
