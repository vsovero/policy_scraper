import pandas as pd

from course_policy.catalog_year_coverage import build_year_coverage, expand_sources_to_years


def test_expand_sources_to_years_uses_half_open_catalog_range():
    retrieval = pd.DataFrame(
        [
            retrieval_row(
                unitid=1,
                source_id="s1",
                start=2004,
                end=2006,
                source_retrieved=True,
            )
        ]
    )

    expanded = expand_sources_to_years(retrieval)

    assert expanded["target_year"].tolist() == [2004, 2005]


def test_build_year_coverage_marks_missing_and_covered_years():
    pilot = pd.DataFrame([{"unitid": 1}])
    targets = pd.DataFrame(
        [
            target_row(1, 2004),
            target_row(1, 2005),
            target_row(1, 2006),
        ]
    )
    retrieval = pd.DataFrame(
        [
            retrieval_row(
                unitid=1,
                source_id="s1",
                start=2004,
                end=2006,
                source_retrieved=True,
            )
        ]
    )

    coverage = build_year_coverage(pilot, targets, retrieval)

    assert coverage["has_catalog_source"].tolist() == [True, True, False]
    assert coverage["source_status"].tolist() == [
        "source_covers_year",
        "source_covers_year",
        "missing_source_for_year",
    ]


def target_row(unitid, year):
    return {
        "unitid": unitid,
        "institution_name": "Example U",
        "sector": "public_4_year",
        "control": "public",
        "state": "AA",
        "year": year,
        "prior_evidence_status": "missing",
        "source_discovery_priority": "high",
    }


def retrieval_row(unitid, source_id, start, end, source_retrieved):
    return {
        "unitid": unitid,
        "institution_name": "Example U",
        "target_year": start,
        "source_id": source_id,
        "candidate_url": "https://example.edu/catalog.pdf",
        "source_retrieved": source_retrieved,
        "best_catalog_year_start": start,
        "best_catalog_year_end": end,
        "best_retrieval_status": "retrieved",
        "best_attempt_method": "direct",
        "best_final_url": "https://example.edu/catalog.pdf",
        "best_content_type": "application/pdf",
        "best_page_title": "Catalog",
        "local_source_path": "/tmp/catalog.pdf",
        "sha256": "hash",
        "needs_human_review": False,
        "review_reason": "",
        "legacy_workbook": "public",
        "legacy_sheet_name": "Sheet1",
        "legacy_excel_row": 2,
        "legacy_link_id": 1,
    }
