import pandas as pd

from course_policy.catalog_url_harmonization import (
    HarmonizedInput,
    build_scope_qc,
    classify_scope,
    current_inputs,
    normalize_panel,
)


def test_classify_scope_accepts_catalog_and_catalog_handbook():
    assert classify_scope(best_url="https://example.edu/catalog-2019.pdf") == ("catalog_confirmed", "")
    assert classify_scope(best_url="https://example.edu/Undergrad_Catalog_2012-2014.pdf") == (
        "catalog_confirmed",
        "",
    )
    assert classify_scope(best_url="https://example.edu/LU_course_catalog_09-10.pdf") == (
        "catalog_confirmed",
        "",
    )
    assert classify_scope(best_url="https://example.edu/catalog-and-student-handbook-2019.pdf") == (
        "catalog_and_handbook",
        "",
    )
    assert classify_scope(best_url="https://example.edu/PAU%20Catalog%20%26%20Student%20Handbook.pdf") == (
        "catalog_and_handbook",
        "",
    )


def test_classify_scope_flags_student_handbook_but_rejects_employee_or_privacy_policy():
    assert classify_scope(best_url="https://example.edu/student-handbook-2019.pdf") == (
        "student_handbook_possible_policy_source",
        "handbook_possible_policy_source_not_catalog_confirmed",
    )
    assert classify_scope(best_url="https://example.edu/employee-handbook.pdf") == (
        "nonacademic_policy_or_wrong_scope",
        "exclude_from_catalog_coverage_review",
    )
    assert classify_scope(best_url="https://example.edu/privacy-policy.pdf") == (
        "nonacademic_policy_or_wrong_scope",
        "exclude_from_catalog_coverage_review",
    )


def test_classify_scope_marks_policy_page_possible_source():
    assert classify_scope(best_url="https://example.edu/academic-policy/course-repeat") == (
        "policy_page_possible_policy_source",
        "policy_page_possible_policy_source_not_catalog_confirmed",
    )


def test_build_scope_qc_counts_types_and_flags():
    database = pd.DataFrame(
        [
            {
                "unitid": 1,
                "best_url": "https://example.edu/catalog.pdf",
                "source_scope_type": "catalog_confirmed",
                "scope_review_flag": "",
                "source_stream": "public_legacy",
            },
            {
                "unitid": 2,
                "best_url": "https://example.edu/student-handbook.pdf",
                "source_scope_type": "student_handbook_possible_policy_source",
                "scope_review_flag": "handbook_possible_policy_source_not_catalog_confirmed",
                "source_stream": "private_legacy",
            },
        ]
    )

    qc = build_scope_qc(database).set_index("metric")["value"]

    assert qc["rows"] == 2
    assert qc["rows_with_url"] == 2
    assert qc["source_scope_type:catalog_confirmed"] == 1
    assert qc["source_scope_type:student_handbook_possible_policy_source"] == 1
    assert qc["scope_review_flag:handbook_possible_policy_source_not_catalog_confirmed"] == 1


def test_private_new_legacy_rows_are_review_gated(tmp_path):
    source = tmp_path / "private_new.csv"
    pd.DataFrame(
        [
            {
                "unitid": 1,
                "institution_name": "Example College",
                "state": "CA",
                "target_year": 2019,
                "best_url": "https://example.edu/catalog-2019.pdf",
                "best_url_source": "private_step0_llm_suggested_url",
                "best_url_status": "candidate_found",
            }
        ]
    ).to_csv(source, index=False)

    panel = normalize_panel(
        HarmonizedInput(
            source_stream="private_new_legacy_url",
            sector_stream="private",
            candidate_paths=(source,),
        )
    )
    row = panel.iloc[0]

    assert row["source_trust_level"] == "unverified_suggestion"
    assert bool(row["requires_source_review"]) is True
    assert row["review_gate"] == "verify_official_scope_catalog_year_and_source_type"
    assert bool(row["catalog_evidence_ready"]) is False
    assert bool(row["policy_extraction_ready"]) is False


def test_human_legacy_catalog_rows_are_ready(tmp_path):
    source = tmp_path / "public.csv"
    pd.DataFrame(
        [
            {
                "unitid": 1,
                "institution_name": "Example State",
                "state": "CA",
                "start_year": 2019,
                "best_url": "https://example.edu/catalog-2019.pdf",
                "best_url_source": "human_legacy_url",
                "best_url_status": "direct_active_url",
            }
        ]
    ).to_csv(source, index=False)

    panel = normalize_panel(
        HarmonizedInput(
            source_stream="public_legacy_url",
            sector_stream="public",
            candidate_paths=(source,),
            year_column="start_year",
        )
    )
    row = panel.iloc[0]

    assert row["source_trust_level"] == "human_legacy_prior"
    assert bool(row["requires_source_review"]) is False
    assert bool(row["catalog_evidence_ready"]) is True
    assert bool(row["policy_extraction_ready"]) is True
    assert row["benchmark_protocol"] == "known_url_execution_diagnostic"
    assert bool(row["counts_as_clean_no_legacy_benchmark"]) is False


def test_human_legacy_policy_page_is_forced_into_extraction_diagnostic(tmp_path):
    source = tmp_path / "private.csv"
    pd.DataFrame(
        [
            {
                "unitid": 1,
                "institution_name": "Example College",
                "state": "CA",
                "start_year": 2019,
                "best_url": "https://example.edu/academic-policy/course-repeat",
                "best_url_source": "private_human_legacy_url",
                "best_url_status": "direct_active_url",
            }
        ]
    ).to_csv(source, index=False)

    panel = normalize_panel(
        HarmonizedInput(
            source_stream="private_human_legacy_url",
            sector_stream="private",
            candidate_paths=(source,),
            year_column="start_year",
        )
    )
    row = panel.iloc[0]

    assert row["source_scope_type"] == "policy_page_possible_policy_source"
    assert row["review_gate"] == "policy_page_possible_policy_source_not_catalog_confirmed"
    assert bool(row["catalog_evidence_ready"]) is False
    assert bool(row["policy_extraction_ready"]) is True
    assert row["benchmark_protocol"] == "known_url_execution_diagnostic"
    assert bool(row["counts_as_clean_no_legacy_benchmark"]) is False


def test_fresh_discovery_policy_page_stays_review_gated(tmp_path):
    source = tmp_path / "fresh.csv"
    pd.DataFrame(
        [
            {
                "unitid": 1,
                "institution_name": "Example State",
                "state": "CA",
                "target_year": 2019,
                "best_url": "https://example.edu/academic-policy/course-repeat",
                "best_url_source": "fresh_search_result",
                "best_url_status": "candidate_found",
            }
        ]
    ).to_csv(source, index=False)

    panel = normalize_panel(
        HarmonizedInput(
            source_stream="public_fresh_discovery",
            sector_stream="public",
            candidate_paths=(source,),
        )
    )
    row = panel.iloc[0]

    assert row["source_scope_type"] == "policy_page_possible_policy_source"
    assert bool(row["policy_extraction_ready"]) is False
    assert row["benchmark_protocol"] == "clean_no_legacy_benchmark"
    assert bool(row["counts_as_clean_no_legacy_benchmark"]) is True


def test_clean_holdout_stream_can_be_harmonized_as_benchmark_only(tmp_path):
    source = tmp_path / "clean_holdout.csv"
    pd.DataFrame(
        [
            {
                "unitid": 1,
                "institution_name": "Example State",
                "state": "CA",
                "target_year": 2019,
                "best_url": "https://example.edu/catalog-2019.pdf",
                "best_url_source": "clean_discovery",
                "best_url_status": "candidate_found",
            }
        ]
    ).to_csv(source, index=False)

    panel = normalize_panel(
        HarmonizedInput(
            source_stream="public_clean_no_legacy_holdout",
            sector_stream="public",
            candidate_paths=(source,),
        )
    )
    row = panel.iloc[0]

    assert row["source_trust_level"] == "benchmark_holdout_discovered"
    assert row["benchmark_protocol"] == "clean_no_legacy_benchmark"
    assert bool(row["counts_as_clean_no_legacy_benchmark"]) is True
    assert bool(row["policy_extraction_ready"]) is True


def test_clean_holdout_inputs_are_opt_in(tmp_path):
    default_streams = {item.source_stream for item in current_inputs(tmp_path)}
    clean_streams = {item.source_stream for item in current_inputs(tmp_path, only_clean_holdout=True)}

    assert "public_clean_no_legacy_holdout" not in default_streams
    assert clean_streams == {"public_clean_no_legacy_holdout", "private_clean_no_legacy_holdout"}
