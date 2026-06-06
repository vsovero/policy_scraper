import pandas as pd

from course_policy.batch2_year_candidates import (
    academic_years_from_range,
    build_year_coverage,
    is_relevant_catalog_link,
    normalized_year_range,
)


def test_normalized_year_range_accepts_two_digit_end_year():
    assert normalized_year_range("Mason 2003_04.pdf") == (2003, 2004)
    assert normalized_year_range("2015-2016 Undergraduate Catalog") == (2015, 2016)


def test_academic_years_from_range_expands_multi_year_catalogs():
    assert academic_years_from_range(2004, 2006) == [2004, 2005]


def test_relevant_catalog_link_excludes_graduate_and_associate_sources():
    assert is_relevant_catalog_link(
        {"text": "2014-2015 Undergraduate Catalog", "url": "https://example.edu/2014-2015"},
        "Example University",
    )
    assert not is_relevant_catalog_link(
        {"text": "2014-2015 Graduate Catalog", "url": "https://example.edu/2014-2015"},
        "Example University",
    )
    assert not is_relevant_catalog_link(
        {"text": "2014-2015 Associate-Level Undergraduate Catalog", "url": "https://example.edu/2014-2015"},
        "Georgia State University",
    )


def test_build_year_coverage_marks_found_and_missing_years():
    year_status = pd.DataFrame(
        [
            {"batch2_rank": 1, "unitid": 1, "institution_name": "Example U", "target_year": 2000},
            {"batch2_rank": 1, "unitid": 1, "institution_name": "Example U", "target_year": 2001},
        ]
    )
    candidates = pd.DataFrame(
        [
            {
                "unitid": 1,
                "target_year": 2000,
                "candidate_url": "https://example.edu/catalog.pdf",
                "candidate_link_text": "2000-2001 Undergraduate Catalog",
                "archive_url": "https://example.edu/archive",
                "catalog_year_start": 2000,
                "catalog_year_end": 2001,
                "candidate_priority": 10,
            }
        ]
    )

    coverage = build_year_coverage(year_status, candidates)

    assert coverage.loc[coverage["target_year"].eq(2000), "candidate_status"].iloc[0] == "explicit_year_candidate_found"
    assert (
        coverage.loc[coverage["target_year"].eq(2001), "candidate_status"].iloc[0]
        == "no_explicit_year_candidate_from_root"
    )
