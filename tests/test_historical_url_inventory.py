from pathlib import Path

import pandas as pd

from course_policy.historical_url_inventory import build_historical_inventory, main


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def test_historical_inventory_classifies_priority_buckets(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_inputs/test/target_panel.csv",
        [
            {"unitid": 1, "institution_name": "Human Legacy U", "sector": "public", "state": "CA", "academic_year": 2002},
            {"unitid": 2, "institution_name": "Reviewed Program U", "sector": "private", "state": "NY", "academic_year": 2005},
            {"unitid": 3, "institution_name": "No History U", "sector": "public", "state": "TX", "academic_year": 2008},
            {"unitid": 4, "institution_name": "Candidate Lead U", "sector": "private", "state": "OH", "academic_year": 2010},
            {"unitid": 5, "institution_name": "Failed Attempt U", "sector": "public", "state": "MI", "academic_year": 2011},
            {"unitid": 6, "institution_name": "Claude Lead U", "sector": "public", "state": "WA", "academic_year": 2012},
            {"unitid": 7, "institution_name": "Reviewed Suggestion U", "sector": "private", "state": "OR", "academic_year": 2013},
            {"unitid": 8, "institution_name": "Unselected Human U", "sector": "public", "state": "IL", "academic_year": 2014},
        ],
    )
    _write_csv(
        tmp_path / "artifacts/policy_data_internal/interim/legacy_evidence_links.csv",
        [
            {
                "unitid": 1,
                "target_year": 2002,
                "institution_name": "Human Legacy U",
                "legacy_url": "https://human.example.edu/catalog-2002.pdf",
                "source_can_be_prior_evidence": True,
                "selected_as_prior_evidence": True,
            },
            {
                "unitid": 8,
                "target_year": 2014,
                "institution_name": "Unselected Human U",
                "legacy_url": "https://unselected-human.example.edu/catalog-2014.pdf",
                "source_can_be_prior_evidence": False,
                "selected_as_prior_evidence": False,
            },
        ],
    )
    _write_csv(
        tmp_path / "artifacts/PILOTS/url_discovery/audit_trails/url_discovery_pilot_batch_001/source_review_log.csv",
        [
            {
                "unitid": 2,
                "institution_name": "Reviewed Program U",
                "sector_stream": "private_clean_no_legacy_holdout",
                "target_year": 2005,
                "candidate_url": "https://program.example.edu/catalog-2005.pdf",
                "final_url": "https://program.example.edu/catalog-2005.pdf",
                "retrieval_status": "retrieved",
                "review_decision": "accept_current_run_source_review",
                "review_reason": "accepted in historical pilot",
                "reviewed_by": "test",
                "reviewed_at": "2026-07-01T00:00:00+00:00",
            }
        ],
    )
    _write_csv(
        tmp_path / "artifacts/PILOTS/url_discovery/audit_trails/url_discovery_pilot_batch_001/retrieved_candidate_url_evidence.csv",
        [
            {
                "unitid": 4,
                "institution_name": "Candidate Lead U",
                "target_year": 2010,
                "candidate_url": "https://lead.example.edu/catalog-2010.pdf",
                "final_url": "https://lead.example.edu/catalog-2010.pdf",
                "retrieval_status": "retrieved",
                "http_status": 200,
            }
        ],
    )
    _write_csv(
        tmp_path / "artifacts/PILOTS/url_discovery/pipeline_outputs/pilot_batch_002/UNRESOLVED_ROWS.csv",
        [
            {
                "unitid": 5,
                "institution_name": "Failed Attempt U",
                "academic_year": 2011,
                "url_status": "no_candidate_found",
                "stop_reason": "no source found",
            }
        ],
    )
    _write_csv(
        tmp_path / "artifacts/OLD_OUTPUT_ARCHIVES/rebuild/inputs_suggestion/public_claude_coverage_grid.csv",
        [
            {
                "unitid": 6,
                "name": "Claude Lead U",
                "year": 2012,
                "url": "https://claude.example.edu/catalog-2012.pdf",
                "scope": "institution_wide",
                "status": "verified",
                "stage": "year_confirmed",
            }
        ],
    )
    _write_csv(
        tmp_path / "artifacts/OLD_OUTPUT_ARCHIVES/rebuild/outputs/step4_source_review/step4_suggestion_source_review.csv",
        [
            {
                "unitid": 7,
                "institution_name": "Reviewed Suggestion U",
                "target_years": "2013",
                "candidate_url": "https://reviewed-suggestion.example.edu/catalog-2013.pdf",
                "source_review_status": "already_final_ready_from_manual_accept_and_cached_classification",
                "live_retrieval_status": "retrieved",
                "live_http_status": 200,
            }
        ],
    )

    result = build_historical_inventory(tmp_path)

    priority = pd.read_csv(result.institution_priority_buckets)
    buckets = dict(zip(priority["unitid"], priority["priority_bucket"]))
    assert buckets[1] == "valid_human_legacy"
    assert buckets[2] == "prior_programmatic_accepted_needs_current_reverification"
    assert buckets[3] == "no_historical_programmatic_attempt_found"
    assert buckets[4] == "unreviewed_prior_programmatic_candidate_lead"
    assert buckets[5] == "programmatic_attempt_no_valid_discovery"
    assert buckets[6] == "imported_llm_candidate_lead_overlay"
    assert buckets[7] == "prior_programmatic_accepted_needs_current_reverification"
    assert buckets[8] == "unreviewed_human_legacy_candidate_lead"

    counts = priority.set_index("unitid")
    assert counts.loc[4, "unreviewed_prior_programmatic_lead_rows"] == 1
    assert counts.loc[6, "imported_llm_candidate_lead_rows"] == 1
    assert counts.loc[8, "unreviewed_human_legacy_candidate_lead_rows"] == 1
    assert counts.loc[6, "unreviewed_candidate_lead_rows"] == 1
    assert {"url", "candidate_url", "final_url", "accepted_source_url", "benchmark_url"}.isdisjoint(priority.columns)
    priority_text = " ".join(priority.fillna("").astype(str).to_numpy().ravel())
    assert "https://human.example.edu" not in priority_text
    assert "https://program.example.edu" not in priority_text
    assert "https://lead.example.edu" not in priority_text

    discoveries = pd.read_csv(result.discoveries)
    assert set(discoveries["evidence_class"]) == {
        "valid_human_legacy",
        "prior_programmatic_accepted_needs_current_reverification",
    }
    attempts = pd.read_csv(result.attempts)
    assert "unreviewed_prior_programmatic_candidate_lead" in set(attempts["evidence_class"])
    assert "imported_llm_candidate_lead_overlay" in set(attempts["evidence_class"])
    assert "unreviewed_human_legacy_candidate_lead" in set(attempts["evidence_class"])
    assert "unreviewed_programmatic_candidate_lead" not in set(attempts["evidence_class"])
    assert "programmatic_attempt_no_valid_discovery" in set(attempts["evidence_class"])
    claude = attempts.loc[attempts["unitid"].eq(6)].iloc[0]
    assert claude["file_role"] == "llm_suggestion_candidate"
    assert claude["evidence_class"] == "imported_llm_candidate_lead_overlay"
    assert "Claude/LLM suggestion-pool" in claude["classification_reason"]


def test_historical_inventory_writes_expected_audit_and_summary_files(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_inputs/test/target_panel.csv",
        [
            {"unitid": 10, "institution_name": "Example U", "sector": "public", "state": "CA", "academic_year": 2002},
        ],
    )

    result = build_historical_inventory(tmp_path)

    assert result.source_file_manifest.exists()
    assert result.file_level_classification.exists()
    assert result.attempts.exists()
    assert result.discoveries.exists()
    assert result.institution_priority_buckets.exists()
    assert result.source_family_summary.exists()
    assert result.parse_exceptions.exists()
    assert result.run_manifest.exists()
    assert result.summary.exists()
    assert (result.summary_dir / "institution_priority_buckets.csv").exists()
    assert (result.summary_dir / "source_family_summary.csv").exists()
    assert "planning evidence only" in result.summary.read_text(encoding="utf-8")


def test_historical_inventory_cli_can_scan_external_quarantine_root(tmp_path: Path) -> None:
    repo_root = tmp_path / "clean_repo"
    parked_root = tmp_path / "quarantine" / "policy_scraper_artifacts_20260702"
    _write_csv(
        parked_root / "artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_inputs/old/target_panel.csv",
        [
            {"unitid": 20, "institution_name": "Parked U", "sector": "public", "state": "CA", "academic_year": 2002},
        ],
    )
    _write_csv(
        parked_root / "artifacts/PILOTS/url_discovery/audit_trails/old/source_review_log.csv",
        [
            {
                "unitid": 20,
                "institution_name": "Parked U",
                "target_year": 2002,
                "candidate_url": "https://parked.example.edu/catalog-2002.pdf",
                "final_url": "https://parked.example.edu/catalog-2002.pdf",
                "retrieval_status": "retrieved",
                "review_decision": "accept_current_run_source_review",
            }
        ],
    )

    status = main(
        [
            "--repo-root",
            str(repo_root),
            "--scan-root",
            str(parked_root / "artifacts"),
        ]
    )

    assert status == 0
    priority_path = repo_root / "artifacts/AUDIT_TRAILS/url_discovery_historical_inventory/institution_priority_buckets.csv"
    summary_path = repo_root / "artifacts/PIPELINE_OUTPUTS/01_url_discovery/historical_inventory/HISTORICAL_INVENTORY_SUMMARY.md"
    assert priority_path.exists()
    assert summary_path.exists()
    priority = pd.read_csv(priority_path)
    row = priority.loc[priority["unitid"].eq(20)].iloc[0]
    assert row["priority_bucket"] == "prior_programmatic_accepted_needs_current_reverification"
