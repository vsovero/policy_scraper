import pandas as pd

from course_policy.catalog_retrieval import (
    build_coverage,
    build_deduped_coverage,
    candidate_links_from_parent,
    candidate_attempt_urls,
    infer_years,
    parent_urls,
    parse_cdx_snapshots,
    parse_wayback_snapshot,
    result_has_target_year,
    infer_catalog_coverage_years,
    source_extension,
    wayback_available_latest_url,
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


def test_wayback_available_latest_url_omits_timestamp():
    url = wayback_available_latest_url("https://example.edu/catalog.pdf")

    assert "timestamp=" not in url
    assert "archive.org/wayback/available" in url


def test_result_has_target_year_checks_url_title_and_hints():
    assert result_has_target_year({"catalog_year_start": 2004, "catalog_year_end": 2006}, 2004)
    assert result_has_target_year({"catalog_year_start": 2004, "catalog_year_end": 2006}, 2005)
    assert not result_has_target_year({"catalog_year_start": 2004, "catalog_year_end": 2006}, 2006)
    assert not result_has_target_year({"catalog_year_start": 2005, "catalog_year_end": 2006}, 2004)


def test_infer_catalog_coverage_years_uses_academic_year_start():
    assert infer_catalog_coverage_years("SFSU Bulletin 2013-2014") == (2013, 2014)
    assert infer_catalog_coverage_years("2004-06 Undergraduate Catalog") == (2004, 2006)
    assert infer_catalog_coverage_years("Mason 2000 01.pdf") == (2000, 2001)
    assert infer_catalog_coverage_years("Fall 2020 catalog") == (2020, 2021)


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
                "catalog_year_start": "",
                "catalog_year_end": "",
                "local_source_path": "",
                "sha256": "hash",
            }
        ]
    )

    coverage = build_coverage(inventory, attempts)

    assert not coverage.loc[0, "source_retrieved"]
    assert coverage.loc[0, "best_retrieval_status"] == "not_retrieved"


def test_build_coverage_maps_one_retrieval_result_to_duplicate_provenance_rows():
    inventory = pd.DataFrame(
        [
            inventory_row("pilot-1", "public"),
            inventory_row("pilot-2", "private"),
        ]
    )
    attempts = pd.DataFrame(
        [
            {
                "source_id": "pilot-1",
                "original_candidate_url": "https://example.edu/catalog.pdf",
                "retrieval_status": "retrieved",
                "attempt_method": "direct",
                "attempt_sequence": 1,
                "final_url": "https://example.edu/catalog.pdf",
                "content_type": "application/pdf",
                "page_title": "Catalog 2004",
                "year_hints": "2004",
                "catalog_year_start": 2004,
                "catalog_year_end": 2006,
                "local_source_path": "/tmp/catalog.pdf",
                "sha256": "hash",
            }
        ]
    )

    coverage = build_coverage(inventory, attempts)
    deduped = build_deduped_coverage(coverage)

    assert len(coverage) == 2
    assert coverage["source_retrieved"].tolist() == [True, True]
    assert coverage["covers_target_year"].tolist() == [True, True]
    assert len(deduped) == 1
    assert deduped.loc[0, "source_id_count"] == 2
    assert deduped.loc[0, "legacy_workbooks"] == "private; public"


def test_build_coverage_uses_half_open_academic_year_ranges():
    inventory = pd.DataFrame(
        [
            {**inventory_row("pilot-2005", "public"), "target_year": 2005},
            {**inventory_row("pilot-2006", "public"), "target_year": 2006},
        ]
    )
    attempts = pd.DataFrame(
        [
            {
                "source_id": "pilot-2005",
                "original_candidate_url": "https://example.edu/catalog.pdf",
                "retrieval_status": "retrieved",
                "attempt_method": "direct",
                "attempt_sequence": 1,
                "final_url": "https://example.edu/catalog.pdf",
                "content_type": "application/pdf",
                "page_title": "Catalog 2004-2006",
                "year_hints": "2004; 2006",
                "catalog_year_start": 2004,
                "catalog_year_end": 2006,
                "local_source_path": "/tmp/catalog.pdf",
                "sha256": "hash",
            }
        ]
    )

    coverage = build_coverage(inventory, attempts).sort_values("target_year")

    assert coverage["covers_target_year"].tolist() == [True, False]


def inventory_row(source_id, workbook):
    return {
        "source_id": source_id,
        "pilot_rank": 1,
        "unitid": 1,
        "institution_name": "Example U",
        "target_year": 2004,
        "candidate_url": "https://example.edu/catalog.pdf",
        "needs_human_review": False,
        "review_reason": "",
        "legacy_workbook": workbook,
        "legacy_sheet_name": "Sheet1",
        "legacy_excel_row": 2,
        "legacy_link_id": 1,
        "legacy_selected_as_prior_evidence": workbook == "public",
        "legacy_needs_review": False,
        "legacy_review_reasons": "",
    }
