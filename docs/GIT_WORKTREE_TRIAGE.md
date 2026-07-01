# Git Worktree Triage

Snapshot date: 2026-07-01

Purpose: keep the remaining dirty tree understandable after anchoring the Step 1
process guardrails.

## Completed Cleanup

Committed:

```text
9bbf38d Add Step 1 process guardrails
```

That commit anchored:

- protected front-door/status and process-review Markdown files under ignored
  `artifacts/`;
- `docs/replication_standards/protected_artifact_docs_manifest.csv`;
- the baseline stream-scope guard
  `src/course_policy/codex_scope_guard.py`;
- write-scope and front-door pass-claim tests;
- Step 1 stream-role documentation.

## Current Dirty State

Post-guardrail-commit snapshot:

- Branch: `main`
- Modified tracked files: 55
- Untracked files: 120
- Tracked diff size: 4,020 insertions and 244 deletions
- Staged files: none

Important: `artifacts/` remains ignored by default. Only the small protected
Markdown files named in the manifest have been force-added to Git. Do not add
data outputs or release payloads without a separate review.

## Cleanup Rule

Commit only one coherent group at a time. Do not use `git add .`, `git clean`,
or broad restore commands in this worktree. Several remaining files look like
active or recently active stream work.

For active streams, use the baseline guard:

```text
../.venv/bin/python -m course_policy.codex_scope_guard init --scope testing --baseline /private/tmp/codex_scope_testing.json
../.venv/bin/python -m course_policy.codex_scope_guard check --scope testing --baseline /private/tmp/codex_scope_testing.json

../.venv/bin/python -m course_policy.codex_scope_guard init --scope review --baseline /private/tmp/codex_scope_review.json
../.venv/bin/python -m course_policy.codex_scope_guard check --scope review --baseline /private/tmp/codex_scope_review.json

../.venv/bin/python -m course_policy.codex_scope_guard init --scope project_management --baseline /private/tmp/codex_scope_project_management.json
../.venv/bin/python -m course_policy.codex_scope_guard check --scope project_management --baseline /private/tmp/codex_scope_project_management.json
```

## Proposed Remaining Commit Groups

### 1. Standards and AI/API Documentation

Candidate files:

- `.gitignore`
- `README.md`
- `config/openai.example.toml`
- `docs/replication_standards/requirements_checklist.md`
- `docs/replication_standards/url_source_review_standard.md`
- `docs/replication_standards/supporting_rules/api_setup.md`
- `docs/replication_standards/supporting_rules/benchmark_protocol.md`
- `docs/replication_standards/supporting_rules/data_protocol.md`
- `docs/replication_standards/supporting_rules/journal_replication_submission_draft_current.md`
- `docs/replication_standards/supporting_rules/policy_classification_rules.md`
- `docs/replication_standards/supporting_rules/sources_reviewed.md`
- `pyproject.toml`
- `src/course_policy/ai_config.py`
- `tests/test_ai_config.py`

Commit only after checking that no private keys, local paths, or live API
credentials are present.

### 2. Tracked URL Discovery and Catalog Pipeline Changes

Candidate tracked files:

- `src/course_policy/batch2_*`
- `src/course_policy/batch3_discovery.py`
- `src/course_policy/batch4_discovery.py`
- `src/course_policy/catalog_*`
- `src/course_policy/fresh_discovery.py`
- `src/course_policy/institution_universe.py`
- `src/course_policy/legacy_audit.py`
- `src/course_policy/manual_catalog_search_audit.py`
- `src/course_policy/ocr_visual_review.py`
- `src/course_policy/phase3_review_packet.py`
- `src/course_policy/pilot_status_summary.py`
- `src/course_policy/production_chunk_url_discovery.py`
- `src/course_policy/review_ready_adjustments.py`
- `src/course_policy/reviewed_root_expansion.py`
- `src/course_policy/source_root_plan.py`
- `src/course_policy/spotcheck_workbook.py`
- `src/course_policy/strict_*`
- matching modified tracked tests under `tests/test_batch*`,
  `tests/test_catalog_*`, `tests/test_ocr_visual_review.py`, and
  `tests/test_production_chunk_url_discovery.py`

Commit only after running the relevant test subset. This group is too broad to
commit blindly.

### 3. New Production-Runner and Step 1 Modules

Candidate untracked files include:

- `src/course_policy/step1_production_runner.py`
- `src/course_policy/step1_production_input_builder.py`
- `src/course_policy/step1_proof_to_scale_url_production.py`
- `src/course_policy/production_release_url_stage.py`
- `src/course_policy/production_quality_gate.py`
- `src/course_policy/production_namespace.py`
- `src/course_policy/production_streams.py`
- matching `tests/test_step1_*`, `tests/test_production_*`, and
  `tests/test_production_release_url_stage.py`

These look important, but they should be reviewed as a coherent production-runner
slice before staging.

### 4. Historical Inventory, Benchmark, and Validation Modules

Candidate untracked files include:

- `src/course_policy/historical_url_inventory.py`
- `src/course_policy/legacy_gap_fill_benchmark.py`
- `src/course_policy/legacy_reproduction_benchmark.py`
- `src/course_policy/gfdatafull_panel_benchmark.py`
- `src/course_policy/validation_ground_truth.py`
- matching tests

Commit only after confirming these are durable planning/benchmark tools rather
than one-off exploratory scripts.

### 5. Policy Classification and API-Use Modules

Candidate untracked files include:

- `src/course_policy/policy_classification_*`
- `src/course_policy/policy_extraction_queue.py`
- `src/course_policy/policy_excerpt_search.py`
- `src/course_policy/policy_data_review_package.py`
- `src/course_policy/private_step0_llm_production.py`
- matching tests

Commit separately from URL discovery. This group has API/cost/reproducibility
implications and should be reviewed under the AI/API documentation standards.

### 6. Public/Private Discovery Add-on Streams

Candidate untracked files include:

- `src/course_policy/public_*`
- `src/course_policy/private_*`
- `src/course_policy/high_confidence_addon_*`
- `src/course_policy/review_gated_*`
- matching tests

These look like active construction or rescue streams. Do not commit until the
owning stream reports whether they are production code, migration helpers, or
superseded experiments.

## Recommended Next Move

Do not make another broad commit yet. The next safest cleanup action is to review
the standards/config group, because it is smaller and lower-risk than the
production-runner and discovery-code groups. After that, handle production-runner
code as its own reviewed slice.
