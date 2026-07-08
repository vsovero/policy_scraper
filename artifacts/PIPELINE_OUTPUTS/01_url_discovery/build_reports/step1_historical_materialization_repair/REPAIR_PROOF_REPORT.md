# Step 1 Historical URL/Evidence Materialization Repair Proof

Bounded build-stream proof over reviewed candidate-materialization failures.

## Inputs

- Attrition audit: `artifacts/PIPELINE_OUTPUTS/01_url_discovery/reports/step1_attrition_audit_001_040`
- Historical inventory: `policy_scraper_worktrees/completed/policy_scraper_step1_historical_lead_source_reconstruction_packet_029_032/artifacts/AUDIT_TRAILS/url_discovery_historical_inventory`

## Proof Counts

| Measure | Rows |
|---|---:|
| candidate_materialization_failure_rows_examined | 1736 |
| materializable_true_human_legacy_rows | 362 |
| materializable_prior_programmatic_accepted_rows | 471 |
| imported_llm_or_programmatic_lead_only_rows | 893 |
| no_materializable_url_after_stricter_rules_rows | 10 |
| rows_requiring_text_validation_rather_than_url_stage_acceptance | 0 |

## Columbus State Regression

- unitid: `139366`
- before candidate_url_ledger rows in reviewed batch evidence: `0`
- before benchmark_key rows in reviewed batch evidence: `0`
- after materialized candidate rows in repair proof: `15`
- selected provenance labels: `prior_programmatic`

## Interpretation

- Materialized rows are candidates for current Step 1 retrieval/source review, not final URL-stage acceptances.
- Imported LLM/programmatic leads remain historical lead candidates and do not become human legacy evidence.
- Failed historical attempts without URL values remain excluded.
