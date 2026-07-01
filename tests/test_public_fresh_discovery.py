import pandas as pd

from course_policy.public_fresh_discovery import (
    build_archive_pages_concurrent,
    build_year_candidates,
    classify_institution_status,
    select_public_fresh_institutions,
)


def test_select_public_fresh_institutions_uses_no_legacy_queue_and_can_exclude_branches():
    queue = pd.DataFrame(
        [
            {
                "unitid": 1,
                "institution_name": "Main Public University",
                "state": "AA",
                "webaddr": "www.main.edu",
                "public_phase3_coverage_status": "no_public_legacy_url_needs_fresh_discovery",
                "public_legacy_url_count": 0,
                "public_legacy_year_count": 0,
                "public_legacy_rows": 0,
            },
            {
                "unitid": 2,
                "institution_name": "Main Public University-Branch Campus",
                "state": "AA",
                "webaddr": "branch.main.edu",
                "public_phase3_coverage_status": "no_public_legacy_url_needs_fresh_discovery",
                "public_legacy_url_count": 0,
                "public_legacy_year_count": 0,
                "public_legacy_rows": 0,
            },
            {
                "unitid": 3,
                "institution_name": "Legacy Public University",
                "state": "BB",
                "webaddr": "www.legacy.edu",
                "public_phase3_coverage_status": "processed_in_public_legacy_production_run",
                "public_legacy_url_count": 2,
                "public_legacy_year_count": 2,
                "public_legacy_rows": 2,
            },
        ]
    )

    selected = select_public_fresh_institutions(
        queue,
        limit=None,
        rank_start=1,
        include_branch_campuses=False,
    )

    assert selected["unitid"].tolist() == [1]
    assert selected["fresh_rank"].tolist() == [1]
    assert selected["batch3_rank"].tolist() == [1]


def test_institution_status_distinguishes_root_found_from_year_candidates_found():
    institutions = pd.DataFrame(
        [
            {
                "fresh_rank": 1,
                "batch3_rank": 1,
                "unitid": 10,
                "institution_name": "Catalog U",
                "state": "AA",
                "webaddr": "catalog.edu",
                "public_phase3_coverage_status": "no_public_legacy_url_needs_fresh_discovery",
            },
            {
                "fresh_rank": 2,
                "batch3_rank": 2,
                "unitid": 20,
                "institution_name": "No Year U",
                "state": "BB",
                "webaddr": "noyear.edu",
                "public_phase3_coverage_status": "no_public_legacy_url_needs_fresh_discovery",
            },
        ]
    )
    root_candidates = pd.DataFrame(
        [
            {
                "unitid": 10,
                "retrieval_status": "retrieved",
                "likely_catalog_root": True,
                "catalog_link_count": 5,
                "archive_link_count": 2,
            },
            {
                "unitid": 20,
                "retrieval_status": "retrieved",
                "likely_catalog_root": True,
                "catalog_link_count": 2,
                "archive_link_count": 0,
            },
        ]
    )
    decisions = pd.DataFrame(
        [
            {
                "unitid": 10,
                "decision_status": "preferred_source_root_identified",
                "preferred_source_root_url": "https://catalog.edu/catalogs/",
                "preferred_source_root_type": "generated_catalogs_path",
                "preferred_source_root_title": "Catalogs",
            },
            {
                "unitid": 20,
                "decision_status": "preferred_source_root_identified",
                "preferred_source_root_url": "https://noyear.edu/catalogs/",
                "preferred_source_root_type": "generated_catalogs_path",
                "preferred_source_root_title": "Catalogs",
            },
        ]
    )
    archive_pages = pd.DataFrame(
        [
            {
                "unitid": 10,
                "archive_url": "https://catalog.edu/catalogs/",
                "retrieval_status": "retrieved",
                "year_hints": "2000; 2001",
            }
        ]
    )
    year_candidates = pd.DataFrame(
        [
            {
                "unitid": 10,
                "target_year": 2000,
                "candidate_url": "https://catalog.edu/catalog-2000.pdf",
            }
        ]
    )
    year_panel = pd.DataFrame(
        [
            {"unitid": 10, "target_year": 2000, "best_url": "https://catalog.edu/catalog-2000.pdf"},
            {"unitid": 20, "target_year": 2000, "best_url": ""},
        ]
    )

    status = classify_institution_status(
        institutions,
        root_candidates,
        decisions,
        archive_pages,
        year_candidates,
        year_panel,
    )

    by_unitid = status.set_index("unitid")
    assert by_unitid.loc[10, "fresh_discovery_status"] == "year_candidates_found"
    assert by_unitid.loc[10, "next_pipeline_action"] == "retrieve_and_validate_candidate_catalogs"
    assert by_unitid.loc[20, "fresh_discovery_status"] == "source_root_found_no_explicit_years"
    assert by_unitid.loc[20, "next_pipeline_action"] == "ai_or_search_expand_root"


def test_archive_discovery_follows_bounded_nested_archive_links(tmp_path, monkeypatch):
    root_url = "https://www.example.edu/catalog/"
    first_archive_url = "https://example.edu/catalogs/"
    nested_archive_url = "https://example.edu/catalogs/archive.html"
    filler_nested_archive_url = "https://example.edu/catalogs/filler-archive.html"
    paginated_archive_url = "https://example.edu/catalogs/archive.html?pg=2"
    old_catalog_url = "https://example.edu/catalogs/2008-2009-undergraduate-catalog.pdf"

    def fake_retrieve(url, *, timeout_seconds, max_bytes):
        common = {
            "retrieval_status": "retrieved",
            "http_status": 200,
            "final_url": url,
            "content_type": "text/html",
            "year_hints": "",
            "body": b"<html></html>",
        }
        if url == root_url:
            return {
                **common,
                "page_title": "Catalog",
                "link_records": [{"url": first_archive_url, "text": "Archived Catalogs and Handbooks"}],
            }
        if url == first_archive_url:
            return {
                **common,
                "page_title": "Catalogs and Handbooks",
                "link_records": [
                    {"url": nested_archive_url, "text": "Archived Catalogs"},
                    {"url": filler_nested_archive_url, "text": "Archived Catalogs Filler"},
                ],
            }
        if url == filler_nested_archive_url:
            return {**common, "page_title": "Archived Catalogs Filler", "link_records": []}
        if url == nested_archive_url:
            return {
                **common,
                "page_title": "Archived Catalogs",
                "link_records": [{"url": paginated_archive_url, "text": "2"}],
            }
        if url == paginated_archive_url:
            return {
                **common,
                "page_title": "Archived Catalogs",
                "link_records": [{"url": old_catalog_url, "text": "2008-2009 Undergraduate Catalog"}],
            }
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr("course_policy.public_fresh_discovery.retrieve_url", fake_retrieve)
    monkeypatch.setattr(
        "course_policy.public_fresh_discovery.save_source_body",
        lambda repo_root, slug, kind, url, content_type, body: tmp_path / f"{slug}.html",
    )
    decisions = pd.DataFrame(
        [
            {
                "batch3_rank": 1,
                "unitid": 10,
                "institution_name": "Example University",
                "decision_status": "preferred_source_root_identified",
                "preferred_source_root_url": root_url,
            }
        ]
    )

    archive_pages, result_by_url = build_archive_pages_concurrent(
        tmp_path,
        decisions,
        timeout_seconds=1,
        max_archive_pages_per_institution=2,
        max_workers=1,
        source_slug="test",
    )
    year_candidates = build_year_candidates(archive_pages, result_by_url)

    assert nested_archive_url in archive_pages["archive_url"].tolist()
    nested_row = archive_pages.loc[archive_pages["archive_url"].eq(nested_archive_url)].iloc[0]
    assert nested_row["archive_source"] == "nested1_root_archive_link"
    assert paginated_archive_url in archive_pages["archive_url"].tolist()
    paginated_row = archive_pages.loc[archive_pages["archive_url"].eq(paginated_archive_url)].iloc[0]
    assert paginated_row["archive_source"] == "nested2_archive_pagination_link"
    assert int(year_candidates.loc[year_candidates["candidate_url"].eq(old_catalog_url), "target_year"].iloc[0]) == 2008
