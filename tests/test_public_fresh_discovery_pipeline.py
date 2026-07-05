import pandas as pd

from course_policy.public_fresh_discovery_pipeline import (
    build_final_status,
    excel_safe_frame,
    filter_candidate_rows,
    is_expandable_ai_root,
    merge_final_panel,
    select_ai_cases,
)


def test_select_ai_cases_prioritizes_root_found_cases_before_no_root_cases():
    status = pd.DataFrame(
        [
            {
                "unitid": 1,
                "institution_name": "No Root U",
                "fresh_rank": 1,
                "fresh_discovery_status": "source_root_not_found",
            },
            {
                "unitid": 2,
                "institution_name": "Root Only U",
                "fresh_rank": 2,
                "fresh_discovery_status": "source_root_found_no_explicit_years",
            },
            {
                "unitid": 3,
                "institution_name": "Done U",
                "fresh_rank": 3,
                "fresh_discovery_status": "year_candidates_found",
            },
        ]
    )

    cases = select_ai_cases(status, max_cases=2)

    assert cases["unitid"].tolist() == [2, 1]


def test_contentdm_search_root_is_expandable_ai_root():
    assert is_expandable_ai_root(
        "https://dmr.example.edu/cdm/search/collection/BSUCoursCat/order/title/ad/desc",
        {
            "retrieval_status": "retrieved",
            "content_type": "text/html",
            "page_title": "CONTENTdm",
        },
    )


def test_acalog_index_root_is_expandable_ai_root():
    assert is_expandable_ai_root(
        "https://records.example.edu/index.php",
        {
            "retrieval_status": "retrieved",
            "content_type": "text/html",
            "page_title": "Example University",
            "body": b"acalog-clients catalog shell",
        },
    )


def test_merge_final_panel_adds_ai_url_only_when_first_pass_is_missing():
    base_panel = pd.DataFrame(
        [
            {"unitid": 10, "fresh_rank": 1, "target_year": 2000, "best_url": "", "best_url_source": ""},
            {
                "unitid": 10,
                "fresh_rank": 1,
                "target_year": 2001,
                "best_url": "https://catalog.edu/2001.pdf",
                "best_url_source": "first_pass",
            },
        ]
    )
    candidates = pd.DataFrame(
        [
            {
                "unitid": 10,
                "target_year": 2000,
                "candidate_url": "https://catalog.edu/2000.pdf",
                "candidate_source_method": "ai_verified_root_archive",
                "candidate_priority": 5,
            },
            {
                "unitid": 10,
                "target_year": 2001,
                "candidate_url": "https://catalog.edu/alternate-2001.pdf",
                "candidate_source_method": "ai_verified_root_archive",
                "candidate_priority": 5,
            },
        ]
    )

    final = merge_final_panel(base_panel, candidates).sort_values("target_year")

    assert final.loc[final["target_year"].eq(2000), "final_best_url"].iloc[0] == "https://catalog.edu/2000.pdf"
    assert final.loc[final["target_year"].eq(2000), "final_status"].iloc[0] == "ai_candidate_added"
    assert final.loc[final["target_year"].eq(2001), "final_best_url"].iloc[0] == "https://catalog.edu/2001.pdf"
    assert final.loc[final["target_year"].eq(2001), "final_status"].iloc[0] == "first_pass_candidate_found"


def test_merge_final_panel_expands_candidate_catalog_span_to_missing_years():
    base_panel = pd.DataFrame(
        [
            {"unitid": 10, "fresh_rank": 1, "target_year": 2002, "best_url": "", "best_url_source": ""},
            {"unitid": 10, "fresh_rank": 1, "target_year": 2003, "best_url": "", "best_url_source": ""},
        ]
    )
    candidates = pd.DataFrame(
        [
            {
                "unitid": 10,
                "target_year": 2002,
                "candidate_url": "http://coursecatalog.example.edu/previous/0204_catalog.pdf",
                "candidate_source_method": "inferred_year_url_pattern",
                "candidate_priority": 18,
                "catalog_year_start": 2002,
                "catalog_year_end": 2004,
            },
        ]
    )

    final = merge_final_panel(base_panel, candidates).sort_values("target_year")

    assert final["final_best_url"].tolist() == [
        "http://coursecatalog.example.edu/previous/0204_catalog.pdf",
        "http://coursecatalog.example.edu/previous/0204_catalog.pdf",
    ]
    assert final["final_status"].tolist() == ["ai_candidate_added", "ai_candidate_added"]


def test_merge_final_panel_handles_numeric_missing_source_column():
    base_panel = pd.DataFrame(
        [
            {
                "unitid": 10,
                "fresh_rank": 1,
                "target_year": 2002,
                "best_url": "",
                "best_url_source": float("nan"),
            },
        ]
    )
    candidates = pd.DataFrame(
        {
            "unitid": [10],
            "target_year": [2002],
            "candidate_url": ["http://coursecatalog.example.edu/previous/0204_catalog.pdf"],
            "candidate_source_method": pd.Series(["inferred_year_url_pattern"], dtype="string"),
            "candidate_priority": [18],
        }
    )

    final = merge_final_panel(base_panel, candidates)

    assert final["final_best_url_source"].iloc[0] == "inferred_year_url_pattern"
    assert final["final_status"].iloc[0] == "ai_candidate_added"


def test_merge_final_panel_replaces_inferred_probe_with_retrieved_archive_candidate():
    base_panel = pd.DataFrame(
        [
            {
                "unitid": 140447,
                "fresh_rank": 1,
                "target_year": 2016,
                "best_url": "https://www.mercer.edu/pdf/REG_Undergrad20152017.pdf",
                "best_url_source": "inferred_year_url_pattern",
            },
        ]
    )
    candidates = pd.DataFrame(
        [
            {
                "unitid": 140447,
                "target_year": 2016,
                "candidate_url": "https://galileo-mum.primo.exlibrisgroup.com/discovery/delivery/01GALI_MUM:MainLibrary/991005673387205956",
                "candidate_source_method": "clean_archive_expansion",
                "candidate_evidence_source": "exlibris_primo_pnxs_context",
                "candidate_link_text": "Mercer University Catalog - Macon Campus, 2016-2017",
                "candidate_priority": 25,
                "catalog_year_start": 2016,
                "catalog_year_end": 2017,
            },
        ]
    )

    final = merge_final_panel(base_panel, candidates)

    assert final["final_best_url"].iloc[0] == (
        "https://galileo-mum.primo.exlibrisgroup.com/discovery/delivery/"
        "01GALI_MUM:MainLibrary/991005673387205956"
    )
    assert final["final_best_url_source"].iloc[0] == "clean_archive_expansion"
    assert final["final_status"].iloc[0] == "candidate_replaced_generated_probe"
    assert final["ai_candidate_evidence_source"].iloc[0] == "exlibris_primo_pnxs_context"


def test_merge_final_panel_keeps_precise_span_for_duplicate_candidate_url():
    base_panel = pd.DataFrame(
        [
            {"unitid": 232265, "fresh_rank": 1, "target_year": 2010, "best_url": "", "best_url_source": ""},
        ]
    )
    url = "https://img2.hamptonu.edu/hu/docs/catalogs/hu_academic_catalog_rev2010-2012.pdf"
    wrong_url = "https://img2.hamptonu.edu/hu/docs/catalogs/Academic_Catalog_2014-2016_20140912181907.pdf"
    candidates = pd.DataFrame(
        [
            {
                "unitid": 232265,
                "target_year": 2001,
                "candidate_url": wrong_url,
                "candidate_source_method": "clean_archive_expansion",
                "candidate_priority": 25,
                "candidate_evidence_source": "table_row_context",
                "catalog_year_start": 2001,
                "catalog_year_end": 2031,
            },
            {
                "unitid": 232265,
                "target_year": 2001,
                "candidate_url": url,
                "candidate_source_method": "clean_archive_expansion",
                "candidate_priority": 25,
                "candidate_evidence_source": "table_row_context",
                "catalog_year_start": 2001,
                "catalog_year_end": 2031,
            },
            {
                "unitid": 232265,
                "target_year": 2010,
                "candidate_url": url,
                "candidate_source_method": "clean_archive_expansion",
                "candidate_priority": 25,
                "candidate_evidence_source": "visible_link_text",
                "catalog_year_start": 2010,
                "catalog_year_end": 2012,
            },
        ]
    )

    final = merge_final_panel(base_panel, candidates)

    assert final["final_best_url"].iloc[0] == url
    assert final["ai_candidate_url"].iloc[0] == url


def test_filter_candidate_rows_drops_generic_prior_to_search_links():
    candidates = pd.DataFrame(
        [
            {
                "unitid": 10,
                "target_year": 2007,
                "candidate_url": "https://digital.example.edu/search?q=undergraduate+catalog",
                "candidate_link_text": "Catalog Archive Prior to 2007",
                "candidate_evidence_text": "For catalogs published prior to 2007, search the library site.",
            },
            {
                "unitid": 10,
                "target_year": 2008,
                "candidate_url": "https://example.edu/catalog-2008-2009.pdf",
                "candidate_link_text": "2008-2009 Catalog",
                "candidate_evidence_text": "2008-2009 Catalog",
            },
        ]
    )

    filtered = filter_candidate_rows(candidates)

    assert filtered["target_year"].tolist() == [2008]


def test_filter_candidate_rows_requires_retrieved_direct_catalog_urls():
    candidates = pd.DataFrame(
        [
            {
                "unitid": 10,
                "target_year": 2009,
                "candidate_url": "https://example.edu/catalog-2009.pdf",
                "candidate_link_text": "2009-2010 Catalog",
                "candidate_evidence_text": "2009-2010 Catalog",
                "candidate_source_method": "ai_web_direct_catalog_url",
                "candidate_retrieval_status": "url_error",
            },
            {
                "unitid": 10,
                "target_year": 2010,
                "candidate_url": "https://example.edu/catalog-2010.pdf",
                "candidate_link_text": "2010-2011 Catalog",
                "candidate_evidence_text": "2010-2011 Catalog",
                "candidate_source_method": "ai_web_direct_catalog_url",
                "candidate_retrieval_status": "retrieved",
            },
        ]
    )

    filtered = filter_candidate_rows(candidates)

    assert filtered["target_year"].tolist() == [2010]


def test_filter_candidate_rows_drops_non_catalog_publications():
    candidates = pd.DataFrame(
        [
            {
                "unitid": 10,
                "institution_name": "Public U",
                "target_year": 2007,
                "candidate_url": "https://example.edu/Academic_Calendar_2007-08.pdf",
                "candidate_link_text": "2007-2008 Academic Calendar",
                "candidate_evidence_text": "2007-2008 Academic Calendar",
            },
            {
                "unitid": 10,
                "institution_name": "Public U",
                "target_year": 2008,
                "candidate_url": "https://example.edu/2008-2009_Course_Descriptions.pdf",
                "candidate_link_text": "2008-2009 Course Descriptions",
                "candidate_evidence_text": "2008-2009 Course Descriptions",
            },
            {
                "unitid": 10,
                "institution_name": "Public U",
                "target_year": 2009,
                "candidate_url": "https://example.edu/catalog-2009-2010.pdf",
                "candidate_link_text": "2009-2010 Undergraduate Catalog",
                "candidate_evidence_text": "2009-2010 Undergraduate Catalog",
            },
        ]
    )

    filtered = filter_candidate_rows(candidates)

    assert filtered["target_year"].tolist() == [2009]


def test_filter_candidate_rows_keeps_catalog_that_mentions_academic_calendar():
    candidates = pd.DataFrame(
        [
            {
                "unitid": 10,
                "institution_name": "Public U",
                "target_year": 2012,
                "candidate_url": "https://repo.example.edu/server/api/core/items/catalog-2012",
                "candidate_link_text": "2012-2013 undergraduate catalog",
                "candidate_evidence_text": (
                    "2012-2013 undergraduate catalog includes the academic calendar, "
                    "admission information, tuition, academic regulations, and program descriptions."
                ),
                "candidate_source_method": "dspace_discover_context",
            }
        ]
    )

    filtered = filter_candidate_rows(candidates)

    assert filtered["target_year"].tolist() == [2012]


def test_filter_candidate_rows_drops_unmatched_geographic_campus_subdomains():
    candidates = pd.DataFrame(
        [
            {
                "unitid": 10,
                "institution_name": "University of Maryland Global Campus",
                "target_year": 2000,
                "candidate_url": "https://asia.umgc.edu/catalog/2000.pdf",
                "candidate_link_text": "2000-2001 Undergraduate Catalog",
                "candidate_evidence_text": "2000-2001 Undergraduate Catalog",
            },
            {
                "unitid": 11,
                "institution_name": "University of Maryland Global Campus Asia",
                "target_year": 2000,
                "candidate_url": "https://asia.umgc.edu/catalog/2000.pdf",
                "candidate_link_text": "2000-2001 Undergraduate Catalog",
                "candidate_evidence_text": "2000-2001 Undergraduate Catalog",
            },
        ]
    )

    filtered = filter_candidate_rows(candidates)

    assert filtered["unitid"].tolist() == [11]


def test_filter_candidate_rows_drops_unofficial_blog_hosts():
    candidates = pd.DataFrame(
        [
            {
                "unitid": 10,
                "institution_name": "Eastern Michigan University",
                "target_year": 2017,
                "candidate_url": "https://blogemu.com/",
                "candidate_link_text": "2017-2018 Undergraduate Catalog",
                "candidate_evidence_text": "2017-2018 Undergraduate Catalog",
            },
            {
                "unitid": 10,
                "institution_name": "Eastern Michigan University",
                "target_year": 2018,
                "candidate_url": "https://catalog.emich.edu/index.php?catoid=25",
                "candidate_link_text": "2018-2019 Undergraduate Catalog",
                "candidate_evidence_text": "2018-2019 Undergraduate Catalog",
            },
        ]
    )

    filtered = filter_candidate_rows(candidates)

    assert filtered["target_year"].tolist() == [2018]


def test_build_final_status_separates_ai_added_from_ai_not_run():
    first_status = pd.DataFrame(
        [
            {
                "unitid": 10,
                "fresh_rank": 1,
                "institution_name": "AI Added U",
                "fresh_discovery_status": "source_root_not_found",
            },
            {
                "unitid": 20,
                "fresh_rank": 2,
                "institution_name": "Not Run U",
                "fresh_discovery_status": "source_root_not_found",
            },
        ]
    )
    final_panel = pd.DataFrame(
        [
            {"unitid": 10, "best_url": "", "final_best_url": "https://catalog.edu/2000.pdf", "final_status": "ai_candidate_added"},
            {"unitid": 20, "best_url": "", "final_best_url": "", "final_status": "still_missing"},
        ]
    )
    ai_triage = pd.DataFrame(
        [
            {
                "unitid": 10,
                "api_validation_status": "parsed",
                "api_root_candidate_count": 1,
                "api_direct_catalog_url_count": 0,
                "api_stop_reason_if_no_root": "",
                "api_error_message": "",
            }
        ]
    )
    ai_roots = pd.DataFrame(
        [
            {"unitid": 10, "verified_as_expandable_root": True, "root_url": "https://catalog.edu/archive/"},
        ]
    )

    status = build_final_status(first_status, final_panel, ai_triage, ai_roots).set_index("unitid")

    assert status.loc[10, "final_discovery_status"] == "ai_added_candidate_years"
    assert status.loc[20, "final_discovery_status"] == "ai_not_run"


def test_excel_safe_frame_strips_control_characters_for_workbook_output():
    frame = pd.DataFrame([{"text": "safe\x05text", "number": 1}])

    safe = excel_safe_frame(frame)

    assert safe.loc[0, "text"] == "safetext"
    assert safe.loc[0, "number"] == 1
