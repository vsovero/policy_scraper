import pandas as pd

from course_policy.catalog_retrieval import (
    build_coverage,
    candidate_links_from_parent,
    candidate_attempt_urls,
    infer_years,
    parent_urls,
    parse_cdx_snapshots,
    parse_wayback_snapshot,
    source_extension,
)


def test_candidate_attempt_urls_includes_scheme_variant_and_wayback():
    attempts = candidate_attempt_urls("https://example.edu/catalog.pdf", 2004)

    assert attempts[0] == ("direct", "https://example.edu/catalog.pdf")
    assert ("http_variant", "http://example.edu/catalog.pdf") in attempts
    assert attempts[-1][0] == "wayback_available"
    assert "timestamp=20040701" in attempts[-1][1]


def test_parse_wayback_snapshot_returns_closest_available_url():
    body = b'{"archived_snapshots":{"closest":{"available":true,"url":"https://web.archive.org/x"}}}'

    assert parse_wayback_snapshot(body) == "https://web.archive.org/x"


def test_parse_cdx_snapshots_orders_by_target_year_distance():
    body = (
        b'[["timestamp","original","mimetype","statuscode","digest"],'
        b'["20100101000000","https://example.edu/catalog.pdf","application/pdf","200","a"],'
        b'["20040101000000","https://example.edu/catalog.pdf","application/pdf","200","b"]]'
    )

    snapshots = parse_cdx_snapshots(body, 2004)

    assert snapshots[0].startswith("https://web.archive.org/web/20040101000000/")


def test_parent_urls_climbs_path_without_query():
    assert parent_urls("https://example.edu/a/b/file.pdf?x=1")[:2] == [
        "https://example.edu/a/b/",
        "https://example.edu/a/",
    ]


def test_candidate_links_from_parent_scores_catalog_year_links():
    parent_result = {
        "links": [
            "https://example.edu/archive/random.pdf",
            "https://example.edu/archive/catalog-2004-2006.pdf",
        ]
    }

    assert candidate_links_from_parent(parent_result, "https://example.edu/archive/missing.pdf", 2004)[0].endswith(
        "catalog-2004-2006.pdf"
    )


def test_source_extension_uses_content_type_when_url_has_no_suffix():
    assert source_extension("https://example.edu/catalog", "application/pdf") == ".pdf"
    assert source_extension("https://example.edu/catalog", "text/html; charset=utf-8") == ".html"


def test_infer_years_filters_to_catalog_range():
    assert infer_years("1985 2004 2006 2035") == [2004, 2006]


def test_build_coverage_does_not_count_wayback_availability_as_source_retrieved():
    inventory = pd.DataFrame(
        [
            {
                "source_id": "pilot-1",
                "pilot_rank": 1,
                "unitid": 1,
                "institution_name": "Example U",
                "target_year": 2004,
                "candidate_url": "https://example.edu/catalog.pdf",
                "needs_human_review": False,
                "review_reason": "",
                "legacy_workbook": "public",
                "legacy_sheet_name": "Sheet1",
                "legacy_excel_row": 2,
                "legacy_link_id": 1,
                "legacy_selected_as_prior_evidence": True,
                "legacy_needs_review": False,
                "legacy_review_reasons": "",
            }
        ]
    )
    attempts = pd.DataFrame(
        [
            {
                "source_id": "pilot-1",
                "retrieval_status": "retrieved",
                "attempt_method": "wayback_available",
                "attempt_sequence": 1,
                "final_url": "https://archive.org/wayback/available",
                "content_type": "application/json",
                "page_title": "",
                "year_hints": "2004",
                "local_source_path": "",
                "sha256": "hash",
            }
        ]
    )

    coverage = build_coverage(inventory, attempts)

    assert not coverage.loc[0, "source_retrieved"]
    assert coverage.loc[0, "best_retrieval_status"] == "not_retrieved"
