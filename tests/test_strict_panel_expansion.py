import pandas as pd

from course_policy.strict_panel_expansion import build_year_status, normalize_wayback_url, parse_catalog_year_range


def test_parse_catalog_year_range_handles_multi_year_and_typo():
    assert parse_catalog_year_range("SF State 2004 - 2006 Bulletin") == (2004, 2006)
    assert parse_catalog_year_range("2208-2009 Southern Illinois Undergraduate Catalog") == (2008, 2009)


def test_normalize_wayback_url_repairs_single_slash_rewrite():
    url = "https://web.archive.org/web/20230401072525id_/https:/tools.abac.edu/Registrar/Catalogs/Archive/2020-2021.pdf"

    assert normalize_wayback_url(url) == (
        "https://web.archive.org/web/20230401072525id_/https://tools.abac.edu/Registrar/Catalogs/Archive/2020-2021.pdf"
    )


def test_build_year_status_marks_strict_covered_and_candidate_years():
    institutions = pd.DataFrame(
        [{"unitid": 122597, "strict_pilot_rank": 1, "strict_pilot_reason": "test"}]
    )
    targets = pd.DataFrame(
        [
            {"unitid": 122597, "institution_name": "Example U", "year": 2000},
            {"unitid": 122597, "institution_name": "Example U", "year": 2001},
            {"unitid": 122597, "institution_name": "Example U", "year": 2002},
        ]
    )
    strict_year_coverage = pd.DataFrame(
        [
            {"unitid": 122597, "target_year": 2000, "has_strict_catalog_source": True, "source_id": "strict-1"},
            {"unitid": 122597, "target_year": 2001, "has_strict_catalog_source": False, "source_id": ""},
            {"unitid": 122597, "target_year": 2002, "has_strict_catalog_source": False, "source_id": ""},
        ]
    )
    candidates = pd.DataFrame(
        [
            {
                "unitid": 122597,
                "source_id": "candidate-1",
                "candidate_url": "https://example.edu/catalog",
                "source_title": "Catalog 2001-2003",
                "catalog_year_start": 2001,
                "catalog_year_end": 2003,
                "source_status": "ready_for_retrieval",
                "review_reason": "",
            }
        ]
    )

    status = build_year_status(institutions, targets, strict_year_coverage, candidates)

    assert status["candidate_status"].tolist() == [
        "already_strict_covered",
        "ready_for_retrieval",
        "ready_for_retrieval",
    ]
