import pandas as pd

from course_policy.strict_review_workbook import build_needs_review, build_summary


def test_build_summary_counts_covered_and_review_sources():
    year_coverage = pd.DataFrame(
        [
            year_row(1, 2000, True, 1),
            year_row(1, 2001, False, 0),
            year_row(2, 2000, False, 1),
        ]
    )
    retrieval_coverage = pd.DataFrame(
        [
            {"unitid": 1, "source_id": "s1", "strict_covers_target_year": True},
            {"unitid": 1, "source_id": "s2", "strict_covers_target_year": False},
            {"unitid": 2, "source_id": "s3", "strict_covers_target_year": False},
        ]
    )

    summary = build_summary(year_coverage, retrieval_coverage).sort_values("unitid")

    first = summary.loc[summary["unitid"].eq(1)].iloc[0]
    assert first["institution_years"] == 2
    assert first["covered_years"] == 1
    assert first["missing_years"] == 1
    assert first["legacy_evidence_years"] == 1
    assert first["source_rows"] == 2
    assert first["strict_source_rows"] == 1
    assert first["review_source_rows"] == 1


def test_build_needs_review_combines_missing_years_and_source_review():
    year_coverage = pd.DataFrame(
        [
            year_row(1, 2000, True, 1),
            year_row(1, 2001, False, 0),
        ]
    )
    retrieval_coverage = pd.DataFrame(
        [
            {
                "pilot_rank": 1,
                "unitid": 1,
                "institution_name": "Example U",
                "target_year": 2001,
                "source_id": "s2",
                "strict_covers_target_year": False,
                "strict_coverage_reason": "filename only",
                "review_reason": "",
                "candidate_url": "https://example.edu/catalog-2001.pdf",
                "best_final_url": "",
                "catalog_year_evidence_type": "filename_pattern_requires_review",
                "catalog_year_start": 2001,
                "catalog_year_end": 2002,
                "catalog_year_evidence_text": "",
                "local_source_path": "",
                "legacy_excel_row": 12,
                "legacy_review_reasons": "",
            }
        ]
    )

    needs_review = build_needs_review(year_coverage, retrieval_coverage)

    assert set(needs_review["review_type"]) == {"missing_institution_year", "source_not_strict_coverage"}
    source_row = needs_review.loc[needs_review["review_type"].eq("source_not_strict_coverage")].iloc[0]
    assert source_row["review_reason"] == "filename only"


def year_row(unitid, year, covered, legacy_count):
    return {
        "strict_pilot_rank": unitid,
        "unitid": unitid,
        "institution_name": f"Example U {unitid}",
        "state": "AA",
        "strict_pilot_reason": "test",
        "target_year": year,
        "has_strict_catalog_source": covered,
        "legacy_evidence_row_count": legacy_count,
        "source_id": "s1" if covered else "",
        "review_reason": "" if covered else "missing",
    }
