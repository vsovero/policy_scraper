from pathlib import Path

import pandas as pd
import pytest

from course_policy.step1_production_input_builder import build_production_inputs_from_seed
from course_policy.step1_production_runner import build_step1_production_chunk


def _seed_frame(*, forbidden_value: bool = False) -> pd.DataFrame:
    source_file = "artifacts/PILOTS/url_discovery/pipeline_outputs/pilot_batch_001/foo.csv" if forbidden_value else "explicit_seed"
    return pd.DataFrame(
        [
            {
                "unitid": 1,
                "institution_name": "Example University",
                "sector": "private",
                "state": "CA",
                "academic_year": 2002,
                "target_inclusion_reason": "synthetic_builder_ready",
                "estimation_sample_flag": True,
                "panel_fill_flag": False,
                "candidate_url": "https://example.edu/catalog-2002-2003.pdf",
                "candidate_rank": 1,
                "candidate_generation_method": "explicit_seed_candidate",
                "candidate_source_file": source_file,
                "candidate_source_type": "manual_seed",
                "source_query_or_root": "https://example.edu/catalogs",
                "candidate_generated_at": "2026-07-01T00:00:00+00:00",
                "final_url_after_redirect": "https://example.edu/catalog-2002-2003.pdf",
                "retrieval_status": "cached_retrieved",
                "http_status": 200,
                "content_type": "application/pdf",
                "source_page_title": "Example University Catalog 2002-2003",
                "source_opened": True,
                "institution_match_confirmed": True,
                "campus_or_unitid_match_confirmed": True,
                "source_scope_confirmed": True,
                "source_type_confirmed": True,
                "year_coverage_confirmed": True,
                "archive_child_links_checked": False,
                "gap_fill_search_completed": True,
                "panel_consistency_confirmed": True,
                "source_type": "catalog_pdf",
                "source_year_start": 2002,
                "source_year_end": 2003,
                "source_year_coverage_note": "2002-2003 catalog",
                "url_source_bucket": "explicit_seed_reviewed",
                "review_decision": "accept_exact_year_catalog",
                "review_reason": "Cached seed evidence identifies institution and catalog year.",
                "reviewed_by": "codex_source_review_with_cached_evidence",
                "reviewed_at": "2026-07-01T00:00:00+00:00",
                "deterministic_search_completed": True,
                "archive_expansion_completed": True,
                "api_web_rescue_mode": "cached",
                "api_web_rescue_status": "not_needed_source_accepted",
                "api_web_rescue_reason": "Accepted cached source evidence.",
                "source_evidence_note": "Synthetic cached evidence.",
                "evidence_excerpt": "Example University Catalog 2002-2003",
                "benchmark_group": "synthetic_seed",
                "benchmark_url": "https://example.edu/catalog-2002-2003.pdf",
                "historical_priority_bucket": "valid_human_legacy",
                "valid_human_legacy_rows": 1,
                "prior_programmatic_accepted_rows": 0,
                "unreviewed_candidate_lead_rows": 0,
                "failed_attempt_rows": 0,
                "known_source_family_summary": "example.edu catalog_pdf family",
                "known_failure_pattern_summary": "no prior failed attempt found",
                "historical_precheck_completed": True,
                "runtime_input_guardrail_confirmed": True,
                "precheck_created_by": "codex_test_fixture",
                "precheck_created_at": "2026-07-01T00:00:00+00:00",
            },
            {
                "unitid": 1,
                "institution_name": "Example University",
                "sector": "private",
                "state": "CA",
                "academic_year": 2003,
                "target_inclusion_reason": "synthetic_builder_unresolved",
                "estimation_sample_flag": True,
                "panel_fill_flag": False,
                "candidate_url": "",
                "candidate_rank": "",
                "candidate_generation_method": "explicit_seed_no_candidate",
                "candidate_source_file": "",
                "candidate_source_type": "",
                "source_query_or_root": "",
                "candidate_generated_at": "2026-07-01T00:00:00+00:00",
                "final_url_after_redirect": "",
                "retrieval_status": "not_retrieved_no_candidate",
                "http_status": "",
                "content_type": "",
                "source_page_title": "",
                "source_opened": False,
                "institution_match_confirmed": False,
                "campus_or_unitid_match_confirmed": False,
                "source_scope_confirmed": False,
                "source_type_confirmed": False,
                "year_coverage_confirmed": False,
                "archive_child_links_checked": True,
                "gap_fill_search_completed": True,
                "panel_consistency_confirmed": True,
                "source_type": "",
                "source_year_start": "",
                "source_year_end": "",
                "source_year_coverage_note": "",
                "url_source_bucket": "",
                "review_decision": "not_reviewed_no_target_year_candidate",
                "review_reason": "No candidate URL found after bounded seed search.",
                "reviewed_by": "codex_source_review_with_cached_evidence",
                "reviewed_at": "2026-07-01T00:00:00+00:00",
                "deterministic_search_completed": True,
                "archive_expansion_completed": True,
                "api_web_rescue_mode": "cached",
                "api_web_rescue_status": "attempted_no_candidate_found",
                "api_web_rescue_reason": "Synthetic seed records bounded cached rescue with no candidate.",
                "source_evidence_note": "",
                "evidence_excerpt": "",
                "benchmark_group": "",
                "benchmark_url": "",
                "historical_priority_bucket": "valid_human_legacy",
                "valid_human_legacy_rows": 1,
                "prior_programmatic_accepted_rows": 0,
                "unreviewed_candidate_lead_rows": 0,
                "failed_attempt_rows": 0,
                "known_source_family_summary": "example.edu catalog_pdf family",
                "known_failure_pattern_summary": "no prior failed attempt found",
                "historical_precheck_completed": True,
                "runtime_input_guardrail_confirmed": True,
                "precheck_created_by": "codex_test_fixture",
                "precheck_created_at": "2026-07-01T00:00:00+00:00",
            },
        ]
    )


def test_input_builder_creates_clean_inputs_that_runner_accepts(tmp_path: Path) -> None:
    seed_csv = tmp_path / "seed.csv"
    _seed_frame().to_csv(seed_csv, index=False)
    input_dir = tmp_path / "artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_inputs/mini_seed"

    build_result = build_production_inputs_from_seed(
        tmp_path,
        seed_csv=seed_csv,
        input_dir=input_dir,
        chunk_id="production_chunk_builder_test",
        release_id="production_release_builder_test",
    )

    assert build_result.target_rows == 2
    assert build_result.candidate_rows == 1
    assert build_result.precheck_rows == 1
    assert build_result.evidence_rows == 1
    manifest = pd.read_csv(build_result.manifest_path)
    assert not manifest["path"].str.contains("pilot_batch_|artifacts/PILOTS", regex=True).any()

    run_result = build_step1_production_chunk(
        tmp_path,
        input_dir=input_dir,
        chunk_id="production_chunk_builder_test",
        release_id="production_release_builder_test",
        build_release=True,
    )

    assert run_result.requirements_pass
    assert run_result.release_pass


def test_input_builder_rejects_forbidden_pilot_seed_values(tmp_path: Path) -> None:
    seed_csv = tmp_path / "seed.csv"
    _seed_frame(forbidden_value=True).to_csv(seed_csv, index=False)

    with pytest.raises(ValueError, match="forbidden pilot runtime references"):
        build_production_inputs_from_seed(
            tmp_path,
            seed_csv=seed_csv,
            input_dir=tmp_path / "inputs",
            chunk_id="production_chunk_builder_test",
        )


def test_input_builder_rejects_direct_urls_in_historical_precheck_seed(tmp_path: Path) -> None:
    seed = _seed_frame()
    seed["known_source_family_summary"] = "www.example.edu/catalog-2002-2003.pdf"
    seed_csv = tmp_path / "seed.csv"
    seed.to_csv(seed_csv, index=False)

    with pytest.raises(ValueError, match="must not contain direct URLs"):
        build_production_inputs_from_seed(
            tmp_path,
            seed_csv=seed_csv,
            input_dir=tmp_path / "inputs",
            chunk_id="production_chunk_builder_test",
        )
