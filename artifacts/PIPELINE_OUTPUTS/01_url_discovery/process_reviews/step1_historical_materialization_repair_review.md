# Step 1 Historical URL/Evidence Materialization Repair Review

Decision: PASS

Reviewed commit: `90f62f5ee8f613088a074d57867d0121b321161e`

Review worktree:
`/Users/verosovero/Dropbox/Course repetition IPEDS/policy_scraper_step1_historical_materialization_repair`

## Scope Reviewed

Source/test files inspected:

- `src/course_policy/step1_proof_to_scale_url_production.py`
- `src/course_policy/step1_historical_materialization_repair.py`
- `tests/test_step1_proof_to_scale_url_production.py`

Generated proof outputs inspected:

- `artifacts/PIPELINE_OUTPUTS/01_url_discovery/build_reports/step1_historical_materialization_repair/REPAIR_PROOF_REPORT.md`
- `artifacts/PIPELINE_OUTPUTS/01_url_discovery/build_reports/step1_historical_materialization_repair/historical_materialization_repair_ledger.csv`
- `artifacts/PIPELINE_OUTPUTS/01_url_discovery/build_reports/step1_historical_materialization_repair/materialized_candidate_url_ledger.csv`
- `artifacts/PIPELINE_OUTPUTS/01_url_discovery/build_reports/step1_historical_materialization_repair/BUILD_LOG.md`

## Findings

The materialization rule is general and provenance based. It maps `valid_human_legacy` to `validated_human_legacy`, `prior_programmatic_accepted_needs_current_reverification` to `prior_programmatic`, imported LLM leads to `imported_llm_candidate_lead`, unreviewed historical leads to `historical_programmatic_lead`, and failed historical attempts to `not_materialized`. I did not find institution-specific or URL-specific promotion logic in the production path.

The only Columbus-specific code in `step1_historical_materialization_repair.py` is a proof/report regression metric for `unitid=139366`, not the materialization selection rule. The production-path materialization functions in `step1_proof_to_scale_url_production.py` are rule based.

Imported LLM/programmatic lead rows remain distinguishable from human legacy:

- imported LLM lead rows use `legacy_input_provenance=imported_llm_candidate_lead`;
- unreviewed lead rows use `legacy_input_provenance=historical_programmatic_lead`;
- both use `candidate_source_type=historical_lead_input_url`;
- both have `counts_as_legacy_coverage=False`;
- lead rows are excluded from benchmark creation by `raw_input_counts_as_legacy_coverage`.

Failed historical attempts without URL values are not materialized. The no-materializable proof rows have either `no_historical_url_evidence_for_target_year` or `excluded_no_url_value`, and no candidate URL is emitted.

## Proof Targeting

The proof targets exactly the reviewed attrition-audit materialization-failure set:

- attrition-audit subset rows: 1,736
- attrition-audit unique `unitid`/year keys: 1,736
- repair ledger rows: 1,736
- repair ledger unique `unitid`/year keys: 1,736
- repair keys not in audit subset: 0
- audit subset keys missing from repair ledger: 0
- duplicate repair ledger `unitid`/year rows: 0

The materialized candidate ledger has 1,726 rows, matching the 1,726 materialized repair-ledger rows. The remaining 10 repair-ledger rows are non-materialized.

The materialized candidate ledger repeats some identical multi-year catalog candidates once per affected target year. This is not duplicate target-row inflation in the proof ledger. The downstream production input builder maps raw legacy/historical candidate rows back to target years and then de-duplicates by `unitid`/`academic_year`, so the repeated multi-year candidate rows are a reporting/planning caveat rather than a blocker.

## Verified Counts

The proof counts are mechanically supported:

- examined candidate-materialization-failure rows: 1,736
- true human legacy materialized: 362
- prior programmatic accepted materialized: 471
- imported LLM/programmatic lead only: 893
- no materializable URL after stricter rules: 10
- text-validation-rather-than-URL-acceptance rows: 0

Candidate-ledger provenance counts:

- `validated_human_legacy` / `legacy_input_url` / legacy coverage true: 362
- `prior_programmatic` / `legacy_input_url` / legacy coverage true: 471
- `imported_llm_candidate_lead` / `historical_lead_input_url` / legacy coverage false: 821
- `historical_programmatic_lead` / `historical_lead_input_url` / legacy coverage false: 72

## Columbus State

Columbus State University, `unitid=139366`, is correctly handled:

- 15 affected rows in the repair ledger
- before repair proof: 0 candidate rows and 0 benchmark rows
- after repair proof: 15 materialized candidate rows
- historical evidence class: `prior_programmatic_accepted_needs_current_reverification`
- provenance label: `prior_programmatic`
- candidate source type: `legacy_input_url`
- not labeled as human legacy
- source table: `historical_discovery`

This satisfies the required Columbus regression without relying on row-specific materialization logic.

## Planning Use

PM can use this proof for planning:

- 833 rows are ready for a controlled materialization repair lane as true human legacy or prior programmatic accepted evidence.
- 893 rows are historical lead candidates only and need a separate review-gated lane, not legacy/benchmark treatment.
- 10 rows have no materializable URL after stricter rules.

The proof does not claim final URL-stage acceptance, text-stage readiness, or journal readiness. Materialized rows are candidate inputs for current Step 1 retrieval/source review.

Residual risks:

- The generated proof outputs are ignored build artifacts in this worktree. If PM wants them as a durable repo record, they will need to be explicitly added according to repo process.
- Some materialized candidate rows represent the same multi-year catalog evidence repeated across affected target years. This is expected for planning, but PM should interpret the 1,726 candidate rows as target-year materializations, not unique URL strings.

## Checks Run

- `PYTHONPATH=src ../.venv/bin/python -c "import course_policy.step1_proof_to_scale_url_production; import course_policy.step1_historical_materialization_repair; print('import ok')"`: pass
- `PYTHONPATH=src ../.venv/bin/python -m pytest tests/test_step1_proof_to_scale_url_production.py -q`: pass, `36 passed`
- `git diff --check`: pass before review-file edits
- Columbus State trace in repair ledger: reviewed
- samples reviewed for true human legacy, prior programmatic accepted, imported LLM lead, historical programmatic lead, and no-materializable rows
