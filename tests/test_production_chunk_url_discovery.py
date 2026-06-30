from pathlib import Path

import pandas as pd

from course_policy.production_chunk_url_discovery import build_production_chunk_from_prior_batch


def _write_prior_batch(root: Path) -> None:
    output_dir = root / "artifacts/PIPELINE_OUTPUTS/01_url_discovery/pilot_batch_test"
    audit_dir = root / "artifacts/AUDIT_TRAILS/url_discovery_pilot_batch_test"
    output_dir.mkdir(parents=True)
    audit_dir.mkdir(parents=True)
    source_review = audit_dir / "source_review_log.csv"
    pd.DataFrame(
        [
            {
                "unitid": 1,
                "institution_name": "Example University",
                "target_year": 2002,
                "candidate_url": "https://example.edu/catalog.pdf",
                "review_decision": "accept_current_run_source_review",
            }
        ]
    ).to_csv(source_review, index=False)
    pd.DataFrame(
        [
            {
                "unitid": 1,
                "institution_name": "Example University",
                "sector": "private",
                "state": "CA",
                "academic_year": 2002,
                "url_status": "programmatic_ready",
                "url_status_reason": "Accepted after source review.",
                "ready_for_text_extraction": True,
                "url_for_text_extraction": "https://example.edu/catalog.pdf",
                "url_source_bucket": "programmatic_new_discovery",
                "production_url_source": "programmatic_new_discovery",
                "source_type": "catalog_pdf",
                "source_year_start": 2002,
                "source_year_end": 2003,
                "source_year_coverage_note": "2002-2003 catalog",
                "candidate_url": "https://example.edu/catalog.pdf",
                "retrieval_status": "retrieved",
                "http_status": 200,
                "final_url_after_redirect": "https://example.edu/catalog.pdf",
                "source_page_title": "Example Catalog",
                "source_opened": True,
                "institution_match_confirmed": True,
                "source_scope_confirmed": True,
                "source_type_confirmed": True,
                "year_coverage_confirmed": True,
                "panel_consistency_confirmed": True,
                "review_decision": "accept_current_run_source_review",
                "review_reason": "Reviewed exact catalog.",
                "reviewed_by": "codex_source_review_with_retrieval_evidence",
                "reviewed_at": "2026-06-30T00:00:00+00:00",
                "source_review_file": str(source_review),
            },
            {
                "unitid": 1,
                "institution_name": "Example University",
                "sector": "private",
                "state": "CA",
                "academic_year": 2003,
                "url_status": "no_candidate_found",
                "url_status_reason": "No target-year candidate found.",
                "ready_for_text_extraction": False,
                "url_for_text_extraction": "",
                "candidate_url": "",
                "review_decision": "not_reviewed_no_target_year_candidate",
                "review_reason": "No source to review.",
                "stop_reason": "After recovery layers, no source was found.",
            },
        ]
    ).to_csv(output_dir / "OUTPUT_urls_for_text_extraction.csv", index=False)
    pd.DataFrame([{"rows": 0, "parsed_rows": 0, "api_error_rows": 0}]).to_csv(
        audit_dir / "api_rescue_summary.csv",
        index=False,
    )


def _write_legacy_audit(root: Path) -> None:
    audit_dir = root / "artifacts/AUDIT_TRAILS/url_discovery_step1_full_audit/outputs"
    audit_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "unitid": 1,
                "institution_name": "Example University",
                "target_year": 2002,
                "ready_for_text_extraction_step2": True,
                "has_valid_human_legacy_url": False,
                "production_best_url": "https://example.edu/catalog.pdf",
                "programmatic_url": "https://example.edu/catalog.pdf",
            },
            {
                "unitid": 1,
                "institution_name": "Example University",
                "target_year": 2003,
                "ready_for_text_extraction_step2": True,
                "has_valid_human_legacy_url": False,
                "production_best_url": "https://example.edu/old-catalog.pdf",
                "programmatic_url": "https://example.edu/old-catalog.pdf",
            },
        ]
    ).to_csv(audit_dir / "reviewed_url_panel.csv", index=False)


def _write_legacy_audit_with_human_overlap(root: Path) -> None:
    audit_dir = root / "artifacts/AUDIT_TRAILS/url_discovery_step1_full_audit/outputs"
    audit_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "unitid": 1,
                "institution_name": "Example University",
                "target_year": 2002,
                "ready_for_text_extraction_step2": True,
                "has_valid_human_legacy_url": False,
                "production_best_url": "https://example.edu/catalog.pdf",
                "programmatic_url": "https://example.edu/catalog.pdf",
            },
            {
                "unitid": 1,
                "institution_name": "Example University",
                "target_year": 2003,
                "ready_for_text_extraction_step2": True,
                "has_valid_human_legacy_url": True,
                "human_legacy_url": "https://example.edu/human-catalog.pdf",
                "human_legacy_final_url": "https://example.edu/human-catalog.pdf",
                "production_best_url": "https://example.edu/old-programmatic-catalog.pdf",
                "programmatic_url": "https://example.edu/old-programmatic-catalog.pdf",
            },
        ]
    ).to_csv(audit_dir / "reviewed_url_panel.csv", index=False)


def test_build_production_chunk_from_prior_batch_closes_ledger(tmp_path: Path) -> None:
    _write_prior_batch(tmp_path)

    result = build_production_chunk_from_prior_batch(
        tmp_path,
        chunk_id="production_chunk_test",
        prior_batch_slug="pilot_batch_test",
        prior_audit_slug="url_discovery_pilot_batch_test",
    )

    assert result.requirements_pass
    assert result.target_rows == 2
    assert result.ready_rows == 1
    assert result.unresolved_rows == 1

    output_dir = result.output_dir
    for filename in [
        "README.md",
        "CHUNK_REPORT.md",
        "OUTPUT_urls_for_text_extraction.csv",
        "OUTPUT_source_ledger_delta.csv",
        "UNRESOLVED_ROWS.csv",
        "BENCHMARK_RECOVERY.csv",
        "BENCHMARK_MISSES.csv",
        "REQUIREMENTS_STATUS.csv",
        "MANIFEST.json",
    ]:
        assert (output_dir / filename).exists()

    ledger = pd.read_csv(output_dir / "OUTPUT_source_ledger_delta.csv")
    unresolved = pd.read_csv(output_dir / "UNRESOLVED_ROWS.csv")
    requirements = pd.read_csv(output_dir / "REQUIREMENTS_STATUS.csv")

    assert ledger["accepted_source_url"].tolist() == ["https://example.edu/catalog.pdf"]
    assert ledger["provenance_type"].tolist() == ["prior_programmatic"]
    assert unresolved["unresolved_reason"].fillna("").str.contains("recovery layers").any()
    assert requirements["status"].eq("pass").all()


def test_build_production_chunk_does_not_promote_prior_programmatic_misses(tmp_path: Path) -> None:
    _write_prior_batch(tmp_path)
    _write_legacy_audit(tmp_path)

    result = build_production_chunk_from_prior_batch(
        tmp_path,
        chunk_id="production_chunk_test",
        prior_batch_slug="pilot_batch_test",
        prior_audit_slug="url_discovery_pilot_batch_test",
    )

    assert not result.requirements_pass
    assert result.target_rows == 2
    assert result.ready_rows == 1
    assert result.unresolved_rows == 1

    output_dir = result.output_dir
    ledger = pd.read_csv(output_dir / "OUTPUT_source_ledger_delta.csv")
    recovery = pd.read_csv(output_dir / "BENCHMARK_RECOVERY.csv")
    misses = pd.read_csv(output_dir / "BENCHMARK_MISSES.csv")
    requirements = pd.read_csv(output_dir / "REQUIREMENTS_STATUS.csv")

    assert ledger["accepted_source_url"].tolist() == ["https://example.edu/catalog.pdf"]
    assert recovery["benchmark_recovery_status"].tolist() == [
        "recovered_by_current_chunk",
        "miss",
    ]
    assert len(misses) == 1
    assert misses["benchmark_group"].tolist() == ["prior_programmatic_audit"]
    assert misses["benchmark_miss_type"].tolist() == ["benchmark_miss_source_ledger_unresolved"]
    assert misses["unresolved_for_production"].tolist() == [True]
    assert requirements["requirement_id"].str.contains("benchmark_resolved").any()
    assert not requirements["status"].eq("pass").all()


def test_prior_programmatic_miss_can_be_source_resolved_by_valid_human(tmp_path: Path) -> None:
    _write_prior_batch(tmp_path)
    _write_legacy_audit_with_human_overlap(tmp_path)

    result = build_production_chunk_from_prior_batch(
        tmp_path,
        chunk_id="production_chunk_test",
        prior_batch_slug="pilot_batch_test",
        prior_audit_slug="url_discovery_pilot_batch_test",
    )

    assert not result.requirements_pass
    assert result.ready_rows == 2
    assert result.unresolved_rows == 0

    output_dir = result.output_dir
    recovery = pd.read_csv(output_dir / "BENCHMARK_RECOVERY.csv")
    misses = pd.read_csv(output_dir / "BENCHMARK_MISSES.csv")
    requirements = pd.read_csv(output_dir / "REQUIREMENTS_STATUS.csv")

    assert recovery["benchmark_recovery_status"].tolist() == [
        "recovered_by_current_chunk",
        "promoted_from_prior_valid_benchmark_evidence",
        "miss",
    ]
    assert len(misses) == 1
    assert misses["benchmark_group"].tolist() == ["prior_programmatic_audit"]
    assert misses["benchmark_miss_type"].tolist() == [
        "prior_programmatic_current_run_miss_source_resolved_by_valid_human"
    ]
    assert misses["source_ledger_resolved"].tolist() == [True]
    assert misses["unresolved_for_production"].tolist() == [False]
    prior_req = requirements.loc[
        requirements["requirement_id"].eq("chunk_prior_programmatic_benchmark_resolved")
    ].iloc[0]
    assert prior_req["status"] == "fail"
    assert "source_ledger_resolved_by_other_evidence=1" in prior_req["evidence_column_or_check"]
