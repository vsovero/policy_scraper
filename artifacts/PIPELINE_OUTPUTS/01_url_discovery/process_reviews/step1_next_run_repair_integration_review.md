# Step 1 Next-Run Repair Integration Review

Reviewed on 2026-07-02 by the Step 1 review stream.

## Decision

**PASS.**

Commits `04a972ab05994b5c98be994f6ee4d3490a7b69a2` and
`1942124a5560fc178705569680295aed69a44bdc` repair the next-run Step 1
production path. Commit `598d38772f2135dcedbbbf5c295dd9531cc45b39` satisfies
the prior conditional-pass requirement by documenting the official
historical-inventory rebuild command with the durable quarantine archive path:

```text
/Users/verosovero/Dropbox/Course repetition IPEDS/_quarantine/policy_scraper_artifacts_20260702/artifacts
```

The code supports that explicit external scan root, the focused tests passed,
and the documentation now states that future testing must not use a tiny
salvage-worktree artifact folder as the historical source.

No production readiness is claimed by this review.

## Commits Reviewed

- `04a972ab05994b5c98be994f6ee4d3490a7b69a2`
  - Title: `Repair Step 1 next-run production path`
- `1942124a5560fc178705569680295aed69a44bdc`
  - Title: `Add historical URL inventory builder`
- `598d38772f2135dcedbbbf5c295dd9531cc45b39`
  - Title: `Document Step 1 historical inventory rebuild path`
- Review worktree:
  `/Users/verosovero/Dropbox/Course repetition IPEDS/policy_scraper_step1_next_run_repair`

## Files Reviewed

Changed by the reviewed commits:

- `src/course_policy/historical_url_inventory.py`
- `src/course_policy/step1_proof_to_scale_url_production.py`
- `tests/test_historical_url_inventory.py`
- `tests/test_step1_proof_to_scale_url_production.py`

Supporting guard context reviewed:

- `src/course_policy/step1_production_runner.py`
- `tests/test_step1_production_runner.py`
- `docs/GIT_WORKTREE_TRIAGE.md`
- `docs/replication_standards/requirements_checklist.md`
- `docs/replication_standards/codex_goals/step_1_url_discovery_run_contract.md`
- `docs/replication_standards/codex_goals/stream_prompt_templates.md`

## Review Findings

1. **Default proof-to-scale selection: pass.**
   The CLI default selection mode is now
   `prior_valid_legacy_reverification`, with default chunk/release identifiers
   aligned to that lane. The prior-valid selector admits
   `prior_programmatic_accepted_needs_current_reverification` and
   `valid_human_legacy`, then explicitly excludes no-human/no-history holdout
   buckets such as `programmatic_attempt_no_valid_discovery` and
   `no_historical_programmatic_attempt_found`.

2. **Controlled stop reporting and partial ledgers: pass.**
   `run_proof_to_scale()` writes `RUN_STOP_REPORT.md` on `KeyboardInterrupt`
   and on controlled exceptions. The report records the stopped stage, reason,
   row counts, and key partial artifacts, and states that no valid
   `production_chunk_*` or `production_release_*` was produced. The input
   builder writes the target panel, candidate ledger, source-review log,
   source-evidence manifest, historical precheck, and run config early enough
   for partial ledgers to survive controlled source-review failure.

3. **Clean-main historical inventory generation: pass.**
   `course_policy.historical_url_inventory` is committed as a general builder.
   It writes `institution_priority_buckets.csv` to both:

```text
artifacts/AUDIT_TRAILS/url_discovery_historical_inventory/institution_priority_buckets.csv
artifacts/PIPELINE_OUTPUTS/01_url_discovery/historical_inventory/institution_priority_buckets.csv
```

   The CLI accepts repeated `--scan-root` values, including absolute paths
   outside the clean repo, so clean main after merge can rebuild priority memory
   from the durable quarantine archive without copying salvage artifacts into
   the repo.

4. **Priority buckets are planning/precheck memory only: pass.**
   `institution_priority_buckets.csv` stores historical bucket counts and
   ordering signals. In the production proof path, it is converted into
   `historical_case_precheck.csv` with URL-free summary fields only. Direct URL
   columns such as `url`, `candidate_url`, or `accepted_source_url` are not
   carried into the production precheck.

5. **Historical memory cannot promote URLs or count as current recovery: pass.**
   Historical accepted programmatic rows are classified as
   `prior_programmatic_accepted_needs_current_reverification`, not as current
   evidence. The historical inventory summary states that prior programmatic
   evidence cannot promote a row into the source ledger by itself. The clean
   production runner also forbids runtime references to
   `historical_inventory/`, `url_discovery_historical_inventory/`,
   `institution_priority_buckets`, `normalized_historical_url_attempts`, and
   `normalized_historical_discoveries`, which prevents historical inventory
   files from becoming source evidence or release inputs.

6. **Official rebuild path: pass after documentation fix.**
   The implementation can use the required durable quarantine archive path via
   `--scan-root`, and `tests/test_historical_url_inventory.py` covers scanning
   an external quarantine-style artifact root. Commit
   `598d38772f2135dcedbbbf5c295dd9531cc45b39` documents the official rebuild
   command in the Step 1 run contract:

```text
PYTHONPATH=src ../.venv/bin/python -m course_policy.historical_url_inventory --scan-root "/Users/verosovero/Dropbox/Course repetition IPEDS/_quarantine/policy_scraper_artifacts_20260702/artifacts"
```

   The same commit updates the stream prompt template to require the
   durable-quarantine command and to reject salvage-worktree artifact folders as
   the historical source.

7. **No live production chunk or readiness claim: pass.**
   This review did not run a live production chunk. The reviewed commits change
   source and focused tests only; they do not add generated production chunk
   outputs or claim production readiness.

## Required Checks

Scope guard init:

```text
../.venv/bin/python -m course_policy.codex_scope_guard init --scope review --baseline /private/tmp/codex_scope_review_step1_next_run_repair.json
```

Result: **passed**. Baseline written to
`/private/tmp/codex_scope_review_step1_next_run_repair.json`.

Clean import:

```text
PYTHONPATH=src ../.venv/bin/python -c "import course_policy.historical_url_inventory; import course_policy.step1_proof_to_scale_url_production; print('import ok')"
```

Result: **passed** with `import ok`.

Focused tests:

```text
PYTHONPATH=src ../.venv/bin/python -m pytest tests/test_historical_url_inventory.py tests/test_step1_proof_to_scale_url_production.py -q
```

Result: **passed**, `18 passed in 1.23s`.

Whitespace check:

```text
git diff --check
```

Result: **passed**.

Final review scope guard:

```text
../.venv/bin/python -m course_policy.codex_scope_guard check --scope review --baseline /private/tmp/codex_scope_review_step1_next_run_repair.json
```

Result: **passed** for baseline
`/private/tmp/codex_scope_review_step1_next_run_repair.json`.

Narrow final re-check after `598d38772f2135dcedbbbf5c295dd9531cc45b39`:

```text
git diff --check
```

Result: **passed**.

```text
../.venv/bin/python -m course_policy.codex_scope_guard init --scope review --baseline /private/tmp/codex_scope_review_step1_next_run_repair_final.json
../.venv/bin/python -m course_policy.codex_scope_guard check --scope review --baseline /private/tmp/codex_scope_review_step1_next_run_repair_final.json
```

Result: **passed** for baseline
`/private/tmp/codex_scope_review_step1_next_run_repair_final.json`.

## Scope Decision

**Pass.** The repair is general and test-covered, and the prior documentation
condition is now satisfied by commit
`598d38772f2135dcedbbbf5c295dd9531cc45b39`. No source code, tests,
current-status documents, standards documents outside the reviewed
documentation fix, or generated production outputs were edited by the review
stream.

## Remaining Risks

- This review did not execute the historical inventory rebuild against the full
  durable quarantine archive.
- This review did not run a long live production chunk.
- The next generated production chunk still needs its own process review before
  any ready-to-scale or journal-grade claim.

## Required Next Action

Use the documented clean-main historical inventory rebuild command with:

```text
--scan-root "/Users/verosovero/Dropbox/Course repetition IPEDS/_quarantine/policy_scraper_artifacts_20260702/artifacts"
```

Testing may proceed from clean main after merge. The historical inventory
remains planning/precheck memory only and must not be used as URL evidence,
current recovery, or release source evidence.
