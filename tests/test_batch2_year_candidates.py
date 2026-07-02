import pandas as pd

from course_policy.batch2_year_candidates import (
    add_candidate_selection_rank_columns,
    academic_years_from_range,
    build_year_coverage,
    catalog_year_range,
    candidate_selection_sort_columns,
    is_archive_link,
    is_relevant_catalog_link,
    normalized_year_range,
)


def test_normalized_year_range_accepts_two_digit_end_year():
    assert normalized_year_range("Mason 2003_04.pdf") == (2003, 2004)
    assert normalized_year_range("2015-2016 Undergraduate Catalog") == (2015, 2016)


def test_catalog_year_range_is_public_helper_for_historical_catalog_spans():
    assert catalog_year_range("Older Catalogs (1970-2012)") == (1970, 2012)
    assert catalog_year_range("Mason 2003_04.pdf") == (2003, 2004)
    assert catalog_year_range("0204_catalog.pdf") == (2002, 2004)
    assert catalog_year_range("2022-2012 malformed range") is None


def test_academic_years_from_range_expands_multi_year_catalogs():
    assert academic_years_from_range(2004, 2006) == [2004, 2005]


def test_candidate_selection_helpers_rank_stable_catalog_candidates():
    candidates = pd.DataFrame(
        [
            {"unitid": 1, "target_year": 2002, "candidate_url": "https://example.edu/catalog.pdf", "candidate_link_text": "Catalog"},
            {
                "unitid": 1,
                "target_year": 2002,
                "candidate_url": "https://example.edu/undergraduate.pdf",
                "candidate_link_text": "Undergraduate Catalog",
            },
        ]
    )

    ranked = add_candidate_selection_rank_columns(candidates)
    chosen = ranked.sort_values(candidate_selection_sort_columns(["unitid", "target_year"])).iloc[0]

    assert chosen["candidate_url"] == "https://example.edu/undergraduate.pdf"
    assert chosen["candidate_document_priority"] == 10
    assert chosen["candidate_priority"] == 10
    assert chosen["candidate_selection_rank"] == 1


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


def test_metadata_json_links_are_archive_links_for_digital_collections():
    assert is_archive_link(
        {
            "text": "Metadata JSON",
            "url": "https://www.lib.example.edu/digital/coursecatalogs/assets/data/metadata.json",
        }
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
