import json
from pathlib import Path

import pandas as pd
import pytest

from course_policy.step1_production_runner import benchmark_url_match, build_step1_production_chunk


def _write_clean_inputs(
    root: Path,
    *,
    forbidden_input: bool = False,
    forbidden_source_file: str | None = None,
    unreviewed_candidate: bool = False,
) -> Path:
    input_dir = root / "artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_inputs/smoke_clean_runner"
    cache_dir = input_dir / "source_evidence_cache"
    cache_dir.mkdir(parents=True)
    (input_dir / "run_config.json").write_text(
        json.dumps(
            {
                "chunk_id": "production_chunk_clean_runner_test",
                "release_id": "production_release_clean_runner_test",
                "sector_scope": "both",
                "year_scope": "2002-2003",
                "api_web_mode": "cached",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {
                "unitid": 1,
                "institution_name": "Example University",
                "sector": "private",
                "state": "CA",
                "academic_year": 2002,
                "target_inclusion_reason": "smoke_test_ready_row",
                "estimation_sample_flag": True,
                "panel_fill_flag": False,
            },
            {
                "unitid": 1,
                "institution_name": "Example University",
                "sector": "private",
                "state": "CA",
                "academic_year": 2003,
                "target_inclusion_reason": "smoke_test_unresolved_row",
                "estimation_sample_flag": True,
                "panel_fill_flag": False,
            },
        ]
    ).to_csv(input_dir / "target_panel.csv", index=False)
    if forbidden_source_file is not None:
        source_file = forbidden_source_file
    elif forbidden_input:
        source_file = "artifacts/PILOTS/url_discovery/pipeline_outputs/pilot_batch_001/foo.csv"
    else:
        source_file = "explicit_smoke_seed"
    pd.DataFrame(
        [
            {
                "unitid": 1,
                "academic_year": 2002,
                "candidate_url": "https://example.edu/2002-2003-catalog.pdf",
                "candidate_rank": 1,
                "candidate_generation_method": "explicit_production_input_smoke",
                "candidate_source_file": source_file,
            },
            {
                "unitid": 1,
                "academic_year": 2003,
                "candidate_url": "https://example.edu/2003-2004-catalog.pdf",
                "candidate_rank": 1,
                "candidate_generation_method": "explicit_production_input_smoke",
                "candidate_source_file": "explicit_smoke_seed",
            },
        ]
    ).to_csv(input_dir / "candidate_url_ledger.csv", index=False)
    review_rows = [
        {
            "unitid": 1,
            "academic_year": 2002,
            "candidate_url": "https://example.edu/2002-2003-catalog.pdf",
            "final_url_after_redirect": "https://example.edu/2002-2003-catalog.pdf",
            "retrieval_status": "cached_retrieved",
            "http_status": 200,
            "content_type": "application/pdf",
            "source_page_title": "Example University Undergraduate Catalog 2002-2003",
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
            "review_decision": "accept_exact_year_catalog",
            "review_reason": "Cached source evidence identifies the institution and catalog year.",
            "reviewed_by": "codex_source_review_with_cached_evidence",
            "reviewed_at": "2026-06-30T00:00:00+00:00",
        },
    ]
    if not unreviewed_candidate:
        review_rows.append(
            {
                "unitid": 1,
                "academic_year": 2003,
                "candidate_url": "https://example.edu/2003-2004-catalog.pdf",
                "retrieval_status": "not_retrieved",
                "http_status": "",
                "source_opened": False,
                "institution_match_confirmed": False,
                "source_scope_confirmed": False,
                "source_type_confirmed": False,
                "year_coverage_confirmed": False,
                "gap_fill_search_completed": True,
                "panel_consistency_confirmed": True,
                "review_decision": "reject_dead_or_unretrievable",
                "review_reason": "Cached smoke input marks this target-year source unresolved.",
                "reviewed_by": "codex_source_review_with_cached_evidence",
                "reviewed_at": "2026-06-30T00:00:00+00:00",
            }
        )
    pd.DataFrame(review_rows).to_csv(input_dir / "source_review_log.csv", index=False)
    pd.DataFrame(
        [
            {
                "unitid": 1,
                "institution_name": "Example University",
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
                "precheck_created_at": "2026-06-30T00:00:00+00:00",
            }
        ]
    ).to_csv(input_dir / "historical_case_precheck.csv", index=False)
    cached_text = cache_dir / "example_2002.txt"
    cached_text.write_text("Example University Undergraduate Catalog 2002-2003", encoding="utf-8")
    pd.DataFrame(
        [
            {
                "unitid": 1,
                "academic_year": 2002,
                "candidate_url": "https://example.edu/2002-2003-catalog.pdf",
                "cached_text_path": "source_evidence_cache/example_2002.txt",
                "cached_text_sha256": "cachehash",
                "source_body_sha256": "bodyhash",
            }
        ]
    ).to_csv(input_dir / "source_evidence_manifest.csv", index=False)
    pd.DataFrame(
        [
            {
                "benchmark_group": "smoke_benchmark",
                "unitid": 1,
                "institution_name": "Example University",
                "academic_year": 2002,
                "benchmark_url": "https://example.edu/2002-2003-catalog.pdf",
            }
        ]
    ).to_csv(input_dir / "benchmark_key.csv", index=False)
    return input_dir


def test_clean_runner_builds_chunk_and_release_without_pilot_runtime_inputs(tmp_path: Path) -> None:
    input_dir = _write_clean_inputs(tmp_path)

    result = build_step1_production_chunk(
        tmp_path,
        input_dir=input_dir,
        chunk_id="production_chunk_clean_runner_test",
        release_id="production_release_clean_runner_test",
        build_release=True,
    )

    assert result.requirements_pass
    assert result.release_pass
    assert result.target_rows == 2
    assert result.ready_rows == 1
    assert result.unresolved_rows == 1

    requirements = pd.read_csv(result.output_dir / "REQUIREMENTS_STATUS.csv")
    assert requirements["status"].eq("pass").all()
    ledger = pd.read_csv(result.output_dir / "OUTPUT_source_ledger_delta.csv")
    assert ledger["accepted_source_url"].tolist() == ["https://example.edu/2002-2003-catalog.pdf"]
    input_manifest = pd.read_csv(result.audit_dir / "production_input_manifest.csv")
    assert not input_manifest["path"].str.contains("pilot_batch_|artifacts/PILOTS", regex=True).any()
    precheck_req = requirements.loc[requirements["requirement_id"].eq("historical_case_precheck_complete")].iloc[0]
    assert precheck_req["status"] == "pass"
    assert "Historical case precheck" in (result.output_dir / "CHUNK_REPORT.md").read_text(encoding="utf-8")

    assert result.release_dir is not None
    release_manifest = pd.read_csv(result.release_dir / "release_manifest.csv")
    assert not release_manifest["path"].str.contains("pilot_batch_|artifacts/PILOTS", regex=True).any()
    rebuild_check = pd.read_csv(result.release_dir / "rebuild_check.csv")
    assert rebuild_check["status"].eq("pass").all()


def test_clean_runner_rejects_pilot_runtime_inputs(tmp_path: Path) -> None:
    input_dir = _write_clean_inputs(tmp_path, forbidden_input=True)

    with pytest.raises(ValueError, match="forbidden non-production runtime references"):
        build_step1_production_chunk(
            tmp_path,
            input_dir=input_dir,
            chunk_id="production_chunk_clean_runner_test",
        )


def test_clean_runner_rejects_historical_inventory_runtime_inputs(tmp_path: Path) -> None:
    input_dir = _write_clean_inputs(
        tmp_path,
        forbidden_source_file=(
            "artifacts/PIPELINE_OUTPUTS/01_url_discovery/"
            "historical_inventory/institution_priority_buckets.csv"
        ),
    )

    with pytest.raises(ValueError, match="forbidden non-production runtime references"):
        build_step1_production_chunk(
            tmp_path,
            input_dir=input_dir,
            chunk_id="production_chunk_clean_runner_test",
        )


def test_clean_runner_requires_historical_case_precheck(tmp_path: Path) -> None:
    input_dir = _write_clean_inputs(tmp_path)
    (input_dir / "historical_case_precheck.csv").unlink()

    with pytest.raises(FileNotFoundError, match="historical_case_precheck.csv"):
        build_step1_production_chunk(
            tmp_path,
            input_dir=input_dir,
            chunk_id="production_chunk_clean_runner_test",
        )


def test_clean_runner_fails_incomplete_historical_case_precheck(tmp_path: Path) -> None:
    input_dir = _write_clean_inputs(tmp_path)
    precheck = pd.read_csv(input_dir / "historical_case_precheck.csv")
    precheck["historical_precheck_completed"] = False
    precheck.to_csv(input_dir / "historical_case_precheck.csv", index=False)

    result = build_step1_production_chunk(
        tmp_path,
        input_dir=input_dir,
        chunk_id="production_chunk_clean_runner_test",
    )

    assert not result.requirements_pass
    requirements = pd.read_csv(result.output_dir / "REQUIREMENTS_STATUS.csv")
    precheck_req = requirements.loc[requirements["requirement_id"].eq("historical_case_precheck_complete")].iloc[0]
    assert precheck_req["status"] == "fail"


def test_clean_runner_rejects_direct_urls_in_historical_case_precheck(tmp_path: Path) -> None:
    input_dir = _write_clean_inputs(tmp_path)
    precheck = pd.read_csv(input_dir / "historical_case_precheck.csv")
    precheck["known_source_family_summary"] = "www.example.edu/2002-2003-catalog.pdf"
    precheck.to_csv(input_dir / "historical_case_precheck.csv", index=False)

    with pytest.raises(ValueError, match="must not contain direct URLs"):
        build_step1_production_chunk(
            tmp_path,
            input_dir=input_dir,
            chunk_id="production_chunk_clean_runner_test",
        )


def test_clean_runner_fails_unreviewed_candidates(tmp_path: Path) -> None:
    input_dir = _write_clean_inputs(tmp_path, unreviewed_candidate=True)

    result = build_step1_production_chunk(
        tmp_path,
        input_dir=input_dir,
        chunk_id="production_chunk_clean_runner_test",
    )

    assert not result.requirements_pass
    requirements = pd.read_csv(result.output_dir / "REQUIREMENTS_STATUS.csv")
    review_req = requirements.loc[requirements["requirement_id"].eq("source_review_handoff_complete")].iloc[0]
    assert review_req["status"] == "fail"


def test_clean_runner_fails_misleading_human_legacy_label_without_validated_provenance(tmp_path: Path) -> None:
    input_dir = _write_clean_inputs(tmp_path)
    review = pd.read_csv(input_dir / "source_review_log.csv")
    accepted = review["academic_year"].eq(2002)
    review.loc[accepted, "candidate_generation_method"] = "raw_human_legacy_url"
    review.loc[accepted, "candidate_source_type"] = "human_legacy_url"
    review.loc[accepted, "url_source_bucket"] = "active_human_legacy_url"
    review.loc[accepted, "legacy_input_provenance"] = "unknown_legacy_input"
    review.to_csv(input_dir / "source_review_log.csv", index=False)
    candidates = pd.read_csv(input_dir / "candidate_url_ledger.csv")
    candidates.loc[candidates["academic_year"].eq(2002), "candidate_generation_method"] = "raw_human_legacy_url"
    candidates.loc[candidates["academic_year"].eq(2002), "candidate_source_type"] = "human_legacy_url"
    candidates.loc[candidates["academic_year"].eq(2002), "legacy_input_provenance"] = "unknown_legacy_input"
    candidates.to_csv(input_dir / "candidate_url_ledger.csv", index=False)

    result = build_step1_production_chunk(
        tmp_path,
        input_dir=input_dir,
        chunk_id="production_chunk_clean_runner_test",
    )

    assert not result.requirements_pass
    requirements = pd.read_csv(result.output_dir / "REQUIREMENTS_STATUS.csv")
    gate = requirements.loc[requirements["requirement_id"].eq("legacy_label_and_prior_human_funnel")].iloc[0]
    assert gate["status"] == "fail"
    assert "misleading_human_label_rows=1" in gate["evidence_column_or_check"]


def test_clean_runner_fails_prior_human_thin_evidence_wrong_institution_invalidation(tmp_path: Path) -> None:
    input_dir = _write_clean_inputs(tmp_path)
    review = pd.read_csv(input_dir / "source_review_log.csv")
    accepted = review["academic_year"].eq(2002)
    review.loc[accepted, "retrieval_status"] = "retrieved_truncated"
    review.loc[accepted, "institution_match_confirmed"] = False
    review.loc[accepted, "campus_or_unitid_match_confirmed"] = False
    review.loc[accepted, "panel_consistency_confirmed"] = False
    review.loc[accepted, "review_decision"] = "confirmed_wrong_institution"
    review.loc[accepted, "review_reason"] = "Thin current evidence did not confirm institution."
    review.loc[accepted, "candidate_source_type"] = "legacy_input_url"
    review.loc[accepted, "legacy_input_provenance"] = "validated_human_legacy"
    review.to_csv(input_dir / "source_review_log.csv", index=False)
    candidates = pd.read_csv(input_dir / "candidate_url_ledger.csv")
    candidates.loc[candidates["academic_year"].eq(2002), "candidate_source_type"] = "legacy_input_url"
    candidates.loc[candidates["academic_year"].eq(2002), "legacy_input_provenance"] = "validated_human_legacy"
    candidates.to_csv(input_dir / "candidate_url_ledger.csv", index=False)

    result = build_step1_production_chunk(
        tmp_path,
        input_dir=input_dir,
        chunk_id="production_chunk_clean_runner_test",
    )

    assert not result.requirements_pass
    requirements = pd.read_csv(result.output_dir / "REQUIREMENTS_STATUS.csv")
    gate = requirements.loc[requirements["requirement_id"].eq("legacy_label_and_prior_human_funnel")].iloc[0]
    assert gate["status"] == "fail"
    assert "prior_human_thin_wrong_institution_rows=1" in gate["evidence_column_or_check"]


def test_clean_runner_resolves_benchmark_miss_with_alternate_ready_source(tmp_path: Path) -> None:
    input_dir = _write_clean_inputs(tmp_path)
    benchmark = pd.read_csv(input_dir / "benchmark_key.csv")
    benchmark["benchmark_url"] = "https://example.edu/different-catalog.pdf"
    benchmark.to_csv(input_dir / "benchmark_key.csv", index=False)

    result = build_step1_production_chunk(
        tmp_path,
        input_dir=input_dir,
        chunk_id="production_chunk_clean_runner_test",
    )

    assert result.requirements_pass
    recovery = pd.read_csv(result.output_dir / "BENCHMARK_RECOVERY.csv")
    misses = pd.read_csv(result.output_dir / "BENCHMARK_MISSES.csv")
    assert misses.empty
    assert recovery["benchmark_recovery_status"].tolist() == ["source_ledger_resolved_by_other_evidence"]
    assert recovery["current_run_recovered"].tolist() == [False]
    assert recovery["source_ledger_resolved_or_invalidated"].tolist() == [True]


def test_clean_runner_fails_unresolved_benchmark_miss(tmp_path: Path) -> None:
    input_dir = _write_clean_inputs(tmp_path)
    benchmark = pd.read_csv(input_dir / "benchmark_key.csv")
    benchmark["academic_year"] = 2003
    benchmark["benchmark_url"] = "https://example.edu/different-2003-catalog.pdf"
    benchmark.to_csv(input_dir / "benchmark_key.csv", index=False)

    result = build_step1_production_chunk(
        tmp_path,
        input_dir=input_dir,
        chunk_id="production_chunk_clean_runner_test",
    )

    assert not result.requirements_pass
    misses = pd.read_csv(result.output_dir / "BENCHMARK_MISSES.csv")
    assert len(misses) == 1
    requirements = pd.read_csv(result.output_dir / "REQUIREMENTS_STATUS.csv")
    benchmark_req = requirements.loc[
        requirements["requirement_id"].eq("benchmark_misses_resolved_when_key_present")
    ].iloc[0]
    assert benchmark_req["status"] == "fail"


def test_clean_runner_recovers_benchmark_when_only_fragment_differs(tmp_path: Path) -> None:
    input_dir = _write_clean_inputs(tmp_path)
    review = pd.read_csv(input_dir / "source_review_log.csv")
    review.loc[review["academic_year"].eq(2002), "candidate_url"] = "https://example.edu/catalog/content.php?catoid=1"
    review.loc[review["academic_year"].eq(2002), "final_url_after_redirect"] = "https://example.edu/catalog/content.php?catoid=1"
    review.to_csv(input_dir / "source_review_log.csv", index=False)
    candidates = pd.read_csv(input_dir / "candidate_url_ledger.csv")
    candidates.loc[candidates["academic_year"].eq(2002), "candidate_url"] = "https://example.edu/catalog/content.php?catoid=1"
    candidates.to_csv(input_dir / "candidate_url_ledger.csv", index=False)
    evidence = pd.read_csv(input_dir / "source_evidence_manifest.csv")
    evidence.loc[evidence["academic_year"].eq(2002), "candidate_url"] = "https://example.edu/catalog/content.php?catoid=1"
    evidence.to_csv(input_dir / "source_evidence_manifest.csv", index=False)
    benchmark = pd.read_csv(input_dir / "benchmark_key.csv")
    benchmark["benchmark_url"] = "https://example.edu/catalog/content.php?catoid=1#Policy_Section"
    benchmark.to_csv(input_dir / "benchmark_key.csv", index=False)

    result = build_step1_production_chunk(
        tmp_path,
        input_dir=input_dir,
        chunk_id="production_chunk_clean_runner_test",
    )

    assert result.requirements_pass
    misses = pd.read_csv(result.output_dir / "BENCHMARK_MISSES.csv")
    assert misses.empty


def test_benchmark_match_treats_wayback_case_variant_as_same_pdf() -> None:
    assert benchmark_url_match(
        "http://web.archive.org/web/20121108104011id_/http://evansville.edu/registrar/downloads/CourseCatalog2007-2009.pdf",
        "https://www.evansville.edu/registrar/downloads/coursecatalog2007-2009.pdf",
    )


def test_clean_runner_counts_accepted_human_legacy_wayback_host_drift_as_recovered(tmp_path: Path) -> None:
    input_dir = _write_clean_inputs(tmp_path)
    wayback_url = (
        "http://web.archive.org/web/20140516150704id_/"
        "http://www4.example.edu/university-catalog/2002-2003-catalog/university-regulations"
    )
    benchmark_url = "https://www.example.edu/university-catalog/2002-2003-catalog/university-regulations"
    review = pd.read_csv(input_dir / "source_review_log.csv")
    accepted = review["academic_year"].eq(2002)
    review.loc[accepted, "candidate_url"] = wayback_url
    review.loc[accepted, "final_url_after_redirect"] = wayback_url
    review.loc[accepted, "retrieval_status"] = "retrieved"
    review.loc[accepted, "candidate_generation_method"] = "raw_public_legacy_workbook_url_wayback_recovery"
    review.loc[accepted, "candidate_source_type"] = "human_legacy_url_wayback_recovery"
    review.loc[accepted, "legacy_input_provenance"] = "validated_human_legacy"
    review.loc[accepted, "url_source_bucket"] = "active_human_legacy_url_wayback_recovery"
    review.loc[accepted, "source_type"] = "catalog_html_or_policy_page"
    review.loc[accepted, "source_year_start"] = 2002
    review.loc[accepted, "source_year_end"] = 2003
    review.loc[accepted, "review_reason"] = (
        "Current-run retrieval confirmed institution, source type, and target year/span evidence. "
        "Dead source URL was recovered through bounded Wayback lookup."
    )
    review.to_csv(input_dir / "source_review_log.csv", index=False)
    candidates = pd.read_csv(input_dir / "candidate_url_ledger.csv")
    candidates.loc[candidates["academic_year"].eq(2002), "candidate_url"] = wayback_url
    candidates.loc[
        candidates["academic_year"].eq(2002),
        "candidate_generation_method",
    ] = "raw_public_legacy_workbook_url_wayback_recovery"
    candidates.loc[candidates["academic_year"].eq(2002), "legacy_input_provenance"] = "validated_human_legacy"
    candidates.to_csv(input_dir / "candidate_url_ledger.csv", index=False)
    evidence = pd.read_csv(input_dir / "source_evidence_manifest.csv")
    evidence.loc[evidence["academic_year"].eq(2002), "candidate_url"] = wayback_url
    evidence.to_csv(input_dir / "source_evidence_manifest.csv", index=False)
    benchmark = pd.read_csv(input_dir / "benchmark_key.csv")
    benchmark["benchmark_url"] = benchmark_url
    benchmark.to_csv(input_dir / "benchmark_key.csv", index=False)

    result = build_step1_production_chunk(
        tmp_path,
        input_dir=input_dir,
        chunk_id="production_chunk_clean_runner_test",
    )

    assert result.requirements_pass
    misses = pd.read_csv(result.output_dir / "BENCHMARK_MISSES.csv")
    recovery = pd.read_csv(result.output_dir / "BENCHMARK_RECOVERY.csv")
    assert misses.empty
    assert recovery["benchmark_recovery_status"].tolist() == ["recovered_by_current_chunk"]


def test_clean_runner_accepts_multiyear_catalog_without_benchmark_key(tmp_path: Path) -> None:
    input_dir = _write_clean_inputs(tmp_path)
    (input_dir / "benchmark_key.csv").unlink()
    review = pd.read_csv(input_dir / "source_review_log.csv")
    review.loc[review["academic_year"].eq(2002), "review_decision"] = "accept_multi_year_catalog"
    review.loc[review["academic_year"].eq(2002), "source_year_start"] = 2002
    review.loc[review["academic_year"].eq(2002), "source_year_end"] = 2003
    review.to_csv(input_dir / "source_review_log.csv", index=False)

    result = build_step1_production_chunk(
        tmp_path,
        input_dir=input_dir,
        chunk_id="production_chunk_clean_runner_test",
    )

    assert result.requirements_pass
    recovery = pd.read_csv(result.output_dir / "BENCHMARK_RECOVERY.csv")
    assert recovery.empty
