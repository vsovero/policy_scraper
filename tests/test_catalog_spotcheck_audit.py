import pandas as pd

from course_policy.catalog_spotcheck_audit import build_audit


def test_audit_flags_missing_years_inside_manual_span():
    rows = []
    for year in range(2000, 2021):
        rows.append(
            {
                "unitid": 1,
                "institution_name": "Example University",
                "start_year": year,
                "best_url": "https://catalog.example.edu/2000-2001" if year == 2000 else "",
                "legacy_url": "",
                "stop_reason": "reviewed_root_gap_unfilled" if year != 2000 else "reviewed_candidate_found",
                "manual_status": "found_official_archive",
                "manual_best_root_url": "https://catalog.example.edu/archive",
                "manual_coverage_start_year": 2000,
                "manual_coverage_end_year": 2020,
            }
        )

    audit = build_audit(pd.DataFrame(rows))
    row = audit.iloc[0]

    assert row["audit_status"] == "needs_pipeline_fix"
    assert "missing_years_inside_reviewed_manual_span" in row["pipeline_fix_issues"]
    assert "2001" in row["manual_span_missing_years"]


def test_audit_routes_ocr_status_without_manual_troubleshooting():
    rows = []
    for year in range(2000, 2021):
        rows.append(
            {
                "unitid": 2,
                "institution_name": "Scanned Catalog College",
                "start_year": year,
                "best_url": f"https://archive.example.edu/{year}-{year + 1}.pdf",
                "legacy_url": "",
                "stop_reason": "reviewed_candidate_found",
                "manual_status": "ocr_or_visual_review",
                "manual_best_root_url": "https://archive.example.edu/",
                "manual_coverage_start_year": 2000,
                "manual_coverage_end_year": 2020,
            }
        )

    audit = build_audit(pd.DataFrame(rows))
    row = audit.iloc[0]

    assert row["audit_status"] == "needs_ocr_or_visual_review"
    assert row["pipeline_fix_issues"] == ""
    assert "candidate_urls_need_ocr" in row["ocr_or_visual_review_issues"]


def test_audit_accepts_reviewed_row_level_source_gap():
    rows = []
    for year in range(2000, 2021):
        rows.append(
            {
                "unitid": 3,
                "institution_name": "Visible Gap University",
                "start_year": year,
                "best_url": "https://archive.example.edu/2000-2001" if year == 2000 else "",
                "legacy_url": "",
                "stop_reason": "verified_source_gap" if year != 2000 else "reviewed_candidate_found",
                "manual_status": "found_official_archive",
                "manual_best_root_url": "https://archive.example.edu/",
                "manual_coverage_start_year": 2000,
                "manual_coverage_end_year": 2020,
            }
        )

    audit = build_audit(pd.DataFrame(rows))
    row = audit.iloc[0]

    assert row["audit_status"] == "accepted_dead_end_or_archive_bound"
    assert row["pipeline_fix_issues"] == ""
    assert "row_level_verified_source_gaps" in row["accepted_stop_reasons"]


def test_audit_labels_mixed_found_rows_and_archive_bounds_as_accepted_stop():
    rows = []
    for year in range(2000, 2021):
        rows.append(
            {
                "unitid": 4,
                "institution_name": "Bounded Archive University",
                "start_year": year,
                "best_url": f"https://archive.example.edu/{year}-{year + 1}" if year >= 2005 else "",
                "legacy_url": "",
                "stop_reason": (
                    "reviewed_candidate_found"
                    if year >= 2005
                    else "official_archive_lower_bound_reached"
                ),
                "manual_status": "partial_official_archive",
                "manual_best_root_url": "https://archive.example.edu/",
                "manual_coverage_start_year": 2005,
                "manual_coverage_end_year": 2020,
            }
        )

    audit = build_audit(pd.DataFrame(rows))
    row = audit.iloc[0]

    assert row["audit_status"] == "accepted_dead_end_or_archive_bound"
    assert row["pipeline_fix_issues"] == ""
    assert "archive_bounds_explain_missing_years" in row["accepted_stop_reasons"]
