import pandas as pd
import pytest

from course_policy import clean_no_legacy_benchmark as bench
from course_policy.clean_no_legacy_benchmark import (
    add_year_gap_context_to_status,
    ai_triage_pending_status_materialization,
    ai_year_gap_direct_candidates,
    assert_discovery_input_clean,
    build_ai_case_prompt,
    build_ai_year_gap_cases,
    build_ai_year_gap_prompt,
    build_benchmark_policy_extraction_queue,
    build_discovery_input,
    compact_year_panel,
    first_truth_link,
    inferred_year_url_replacements,
    ai_triage_for_unitids,
    non_retryable_ai_attempted_unitids,
    retrieve_unique_truth_legacy_urls,
    score_loss_bucket,
    select_ai_rescue_cases,
    summarize_scores,
    year_range_from_ai_direct_item,
)
from course_policy.batch2_year_candidates import candidate_document_priority


def test_benchmark_wayback_original_url_normalizes_triple_slash_original():
    url = "https://web.archive.org/web/20240707121305/https:///catalogs.marymount.edu/2020-2021/catalog"

    assert bench.wayback_original_url(url) == "https://catalogs.marymount.edu/2020-2021/catalog"


def test_sitemap_catalog_page_seed_roots_uses_current_site_sitemap(monkeypatch):
    panel = pd.DataFrame(
        [
            {
                "unitid": 224004,
                "institution_name": "Concordia University Texas",
                "target_year": 2015,
                "best_url": "",
                "webaddr": "www.concordia.edu",
            }
        ]
    )

    def fake_retrieve_url(url, **_kwargs):
        if url == "https://www.concordia.edu/sitemap.xml":
            return {
                "retrieval_status": "retrieved",
                "http_status": 200,
                "body": (
                    b"<urlset>"
                    b"<url><loc>https://www.concordia.edu/resources/office-of-student-registration-and-records/"
                    b"schedules-calendars-and-catalog.html</loc></url>"
                    b"<url><loc>https://www.concordia.edu/resources/financial-aid.html</loc></url>"
                    b"</urlset>"
                ),
            }
        return {"retrieval_status": "http_error", "http_status": 404, "body": b""}

    monkeypatch.setattr(bench, "retrieve_url", fake_retrieve_url)

    seeds = bench.sitemap_catalog_page_seed_roots(panel)

    assert seeds["seed_url"].tolist() == [
        "https://www.concordia.edu/resources/office-of-student-registration-and-records/schedules-calendars-and-catalog.html"
    ]
    assert seeds["seed_source"].iloc[0] == "generated_sitemap_catalog_page"


def test_generated_current_site_catalog_page_seed_roots_adds_registrar_catalog_paths():
    panel = pd.DataFrame(
        [
            {
                "unitid": 181002,
                "institution_name": "Creighton University",
                "target_year": 2002,
                "best_url": "",
                "webaddr": "www.creighton.edu",
            }
        ]
    )

    seeds = bench.generated_current_site_catalog_page_seed_roots(panel)

    assert "https://www.creighton.edu/course-schedules-and-catalogs" in set(seeds["seed_url"])
    assert "https://www.creighton.edu/about/office-registrar/catalogs-and-course-schedules" in set(seeds["seed_url"])
    assert seeds["seed_source"].eq("generated_current_site_catalog_page").all()


def test_first_truth_link_uses_any_human_legacy_url_for_workbook_denominator():
    links = pd.DataFrame(
        [
            {
                "unitid": 1,
                "target_year": 2019,
                "legacy_workbook": "private",
                "legacy_url": "",
                "legacy_source_priority": 1,
                "legacy_link_id": 1,
            },
            {
                "unitid": 1,
                "target_year": 2019,
                "legacy_workbook": "private",
                "legacy_url": "https://example.edu/catalog-2019.pdf",
                "legacy_source_priority": 20,
                "legacy_link_id": 2,
            },
            {
                "unitid": 1,
                "target_year": 2019,
                "legacy_workbook": "private",
                "legacy_url": "https://example.edu/catalog-2019-alt.pdf",
                "legacy_source_priority": 30,
                "legacy_link_id": 3,
            },
        ]
    )

    truth = first_truth_link(links, workbook_label="private")

    assert len(truth) == 1
    assert truth["legacy_url"].iloc[0] == "https://example.edu/catalog-2019.pdf"


def test_build_discovery_input_withholds_legacy_truth_columns():
    truth = pd.DataFrame(
        [
            {
                "truth_sector": "public",
                "unitid": 1,
                "institution_name": "Example University",
                "state": "CA",
                "webaddr": "www.example.edu",
                "target_year": 2019,
                "legacy_url": "https://example.edu/catalog-2019.pdf",
                "legacy_policy_class": "grade_forgiveness",
            }
        ]
    )

    discovery_input = build_discovery_input(truth, sector="public")

    assert "legacy_url" not in discovery_input.columns
    assert "legacy_policy_class" not in discovery_input.columns
    assert discovery_input["source_stream"].iloc[0] == "public_clean_no_legacy_holdout"
    assert bool(discovery_input["counts_as_clean_no_legacy_benchmark"].iloc[0])


def test_archive_expansion_seed_roots_use_only_clean_outputs(tmp_path):
    outputs = bench.stream_outputs(tmp_path, "public")
    for path in outputs.__dict__.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "unitid": 1,
                "batch3_rank": 7,
                "fresh_rank": 7,
                "institution_name": "Example University",
                "fresh_discovery_status": "year_candidates_found",
            }
        ]
    ).to_csv(outputs.institution_status_csv, index=False)
    pd.DataFrame(
        [
            {
                "unitid": 1,
                "institution_name": "Example University",
                "decision_status": "preferred_source_root_identified",
                "preferred_source_root_url": "https://catalog.example.edu/",
                "preferred_source_root_type": "generated_catalog_subdomain",
            }
        ]
    ).to_csv(outputs.source_root_decisions_csv, index=False)
    pd.DataFrame(
        [
            {
                "unitid": 1,
                "institution_name": "Example University",
                "candidate_url": "https://catalog.example.edu/archive/",
                "candidate_source_type": "generated_catalog_resource_archive_path",
                "retrieval_status": "retrieved",
                "likely_catalog_root": True,
            },
            {
                "unitid": 1,
                "institution_name": "Example University",
                "candidate_url": "https://policy.example.edu/repeat.html",
                "candidate_source_type": "generated_policy_path",
                "retrieval_status": "retrieved",
                "likely_catalog_root": False,
            },
        ]
    ).to_csv(outputs.root_candidates_csv, index=False)
    pd.DataFrame(
        [
            {
                "unitid": 1,
                "institution_name": "Example University",
                "archive_url": "https://catalog.example.edu/archive/2018-2019/",
                "archive_source": "root_archive_link",
                "retrieval_status": "retrieved",
            }
        ]
    ).to_csv(outputs.archive_pages_csv, index=False)
    pd.DataFrame(
        [
            {
                "unitid": 1,
                "target_year": 2019,
                "best_url": "https://catalog.example.edu/archive/2019-2020/",
                "best_url_source": "clean_candidate",
                "archive_url": "https://catalog.example.edu/archive/",
                "institution_name": "Example University",
            }
        ]
    ).to_csv(outputs.year_panel_csv, index=False)
    pd.DataFrame(
        [
            {
                "unitid": 1,
                "legacy_url": "https://withheld.example.edu/catalog-2019.pdf",
            }
        ]
    ).to_csv(outputs.truth_csv, index=False)

    current_panel = bench.normalize_full_year_panel_for_rescue(pd.read_csv(outputs.year_panel_csv))
    seeds = bench.archive_expansion_seed_roots(tmp_path, "public", current_panel)

    seed_urls = set(seeds["preferred_source_root_url"])
    assert "https://catalog.example.edu/" in seed_urls
    assert "https://catalog.example.edu/archive/" in seed_urls
    assert "https://policy.example.edu/repeat.html" not in seed_urls
    assert "https://catalog.example.edu/archive/2018-2019/" not in seed_urls
    assert not seeds["preferred_source_root_url"].str.contains("withheld", regex=False).any()


def test_archive_expansion_seed_roots_prioritize_retrieved_wordpress_media_api_under_cap(tmp_path):
    outputs = bench.stream_outputs(tmp_path, "private")
    for path in outputs.__dict__.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "unitid": 213385,
                "batch3_rank": 2,
                "fresh_rank": 2,
                "institution_name": "Lafayette College",
                "fresh_discovery_status": "year_candidates_found",
            }
        ]
    ).to_csv(outputs.institution_status_csv, index=False)
    pd.DataFrame(
        [
            {
                "unitid": 213385,
                "institution_name": "Lafayette College",
                "decision_status": "preferred_source_root_identified",
                "preferred_source_root_url": "https://catalog.lafayette.edu/",
                "preferred_source_root_type": "generated_catalog_subdomain",
            }
        ]
    ).to_csv(outputs.source_root_decisions_csv, index=False)
    pd.DataFrame(
        [
            {
                "unitid": 213385,
                "institution_name": "Lafayette College",
                "candidate_url": "https://registrar.lafayette.edu/wp-json/wp/v2/media?search=catalog&per_page=100",
                "candidate_source_type": "generated_wordpress_media_catalog_api",
                "retrieval_status": "retrieved",
                "likely_catalog_root": True,
            }
        ]
    ).to_csv(outputs.root_candidates_csv, index=False)
    pd.DataFrame(columns=["unitid", "archive_url", "archive_source", "retrieval_status"]).to_csv(
        outputs.archive_pages_csv,
        index=False,
    )
    pd.DataFrame(
        [
            {
                "unitid": 213385,
                "target_year": 2016,
                "best_url": "https://catalog.lafayette.edu/2016-2017/catalog",
                "best_url_source": "clean_candidate",
                "archive_url": "https://catalog.lafayette.edu/",
                "institution_name": "Lafayette College",
                "webaddr": "lafayette.edu",
            }
        ]
    ).to_csv(outputs.year_panel_csv, index=False)

    current_panel = bench.normalize_full_year_panel_for_rescue(pd.read_csv(outputs.year_panel_csv))
    seeds = bench.archive_expansion_seed_roots(
        tmp_path,
        "private",
        current_panel,
        max_seed_roots_per_institution=8,
    )

    assert "https://registrar.lafayette.edu/wp-json/wp/v2/media?search=catalog&per_page=100" in set(
        seeds["preferred_source_root_url"]
    )


def test_wordpress_media_year_search_seed_roots_expand_selected_media_api_root():
    selected = pd.DataFrame(
        [
            {
                "batch3_rank": 2,
                "unitid": 213385,
                "institution_name": "Lafayette College",
                "preferred_source_root_url": "https://registrar.lafayette.edu/wp-json/wp/v2/media?search=catalog&per_page=100",
                "preferred_source_root_type": "retrieved_likely_root_candidate:generated_wordpress_media_catalog_api",
            }
        ]
    )
    panel = pd.DataFrame(
        [
            {
                "unitid": 213385,
                "institution_name": "Lafayette College",
                "target_year": 2011,
                "best_url": "",
            },
            {
                "unitid": 213385,
                "institution_name": "Lafayette College",
                "target_year": 2012,
                "best_url": "",
            },
        ]
    )

    seeds = bench.wordpress_media_year_search_seed_roots(selected, panel, max_search_roots_per_institution=4)

    assert seeds["preferred_source_root_url"].tolist() == [
        "https://registrar.lafayette.edu/wp-json/wp/v2/media?per_page=100&search=2011",
        "https://registrar.lafayette.edu/wp-json/wp/v2/media?per_page=100&search=2012",
        "https://registrar.lafayette.edu/wp-json/wp/v2/media?per_page=100&search=11_12",
        "https://registrar.lafayette.edu/wp-json/wp/v2/media?per_page=100&search=12_13",
    ]
    assert seeds["preferred_source_root_type"].tolist() == [
        "generated_wordpress_media_year_search_api:2011",
        "generated_wordpress_media_year_search_api:2012",
        "generated_wordpress_media_year_search_api:11_12",
        "generated_wordpress_media_year_search_api:12_13",
    ]


def test_wordpress_media_year_search_terms_include_two_year_span_filenames():
    terms = bench.wordpress_media_year_search_terms([2005, 2006])

    assert "05_07" in terms
    assert "2005-2007" in terms
    assert "05-07" in terms


def test_wordpress_media_year_search_terms_keep_late_basic_terms_under_cap():
    terms = bench.wordpress_media_year_search_terms(list(range(2000, 2015)))[:48]

    assert "14_15" in terms
    assert "05-07" in terms


def test_exlibris_primo_pnxs_search_url_uses_browse_search_scope():
    url = bench.exlibris_primo_pnxs_search_url(
        "https://galileo-mum.primo.exlibrisgroup.com/discovery/collectionDiscovery?vid=01GALI_MUM:MainLibrary&inst=01GALI_MUM&collectionId=81257987790005956",
        "Mercer University",
        offset=100,
    )

    assert url.startswith("https://galileo-mum.primo.exlibrisgroup.com/primaws/rest/pub/pnxs?")
    assert "scope=browse_search" in url
    assert "q=any%2Ccontains%2CMercer+University+Catalog" in url
    assert "offset=100" in url


def test_exlibris_primo_search_archive_pages_adds_bounded_api_rows(monkeypatch):
    archive_pages = pd.DataFrame(
        [
            {
                "batch3_rank": 9,
                "unitid": 140447,
                "institution_name": "Mercer University",
                "archive_url": "https://ursa.mercer.edu/handle/10898/2885",
                "retrieval_status": "retrieved",
            }
        ]
    )
    result_by_url = {
        "https://ursa.mercer.edu/handle/10898/2885": {
            "final_url": "https://galileo-mum.primo.exlibrisgroup.com/discovery/collectionDiscovery?vid=01GALI_MUM:MainLibrary&inst=01GALI_MUM&collectionId=81257987790005956",
        }
    }
    requested_urls = []

    def fake_retrieve_url(url, **_kwargs):
        requested_urls.append(url)
        return {
            "retrieval_status": "retrieved",
            "http_status": 200,
            "final_url": url,
            "content_type": "application/json;charset=UTF-8",
            "page_title": "",
            "year_hints": "",
            "link_records": [],
            "body": b'{"docs":[]}',
        }

    monkeypatch.setattr(bench, "retrieve_url", fake_retrieve_url)

    pages, results = bench.exlibris_primo_search_archive_pages(
        archive_pages,
        result_by_url,
        timeout_seconds=4,
        max_offsets_per_collection=2,
    )

    assert len(pages) == 2
    assert pages["archive_source"].eq("exlibris_primo_pnxs_catalog_search_api").all()
    assert "offset=0" in requested_urls[0]
    assert "offset=100" in requested_urls[1]
    assert set(pages["archive_url"]) <= set(results)


def test_archive_expansion_seed_roots_prioritize_first_pass_wordpress_api_under_cap(tmp_path):
    outputs = bench.stream_outputs(tmp_path, "private")
    for path in outputs.__dict__.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "unitid": 170675,
                "batch3_rank": 1,
                "fresh_rank": 1,
                "institution_name": "Lawrence Technological University",
                "fresh_discovery_status": "year_candidates_found",
            }
        ]
    ).to_csv(outputs.institution_status_csv, index=False)
    pd.DataFrame(
        [
            {
                "unitid": 170675,
                "institution_name": "Lawrence Technological University",
                "decision_status": "preferred_source_root_identified",
                "preferred_source_root_url": "https://www.ltu.edu/wp-json/wp/v2/media?search=catalog&per_page=100",
                "preferred_source_root_type": "generated_wordpress_media_catalog_api",
            }
        ]
    ).to_csv(outputs.source_root_decisions_csv, index=False)
    pd.DataFrame(columns=["unitid", "candidate_url", "candidate_source_type", "retrieval_status", "likely_catalog_root"]).to_csv(
        outputs.root_candidates_csv,
        index=False,
    )
    pd.DataFrame(columns=["unitid", "archive_url", "archive_source", "retrieval_status"]).to_csv(
        outputs.archive_pages_csv,
        index=False,
    )
    panel = pd.DataFrame(
        [
            {
                "unitid": 170675,
                "target_year": 2005,
                "best_url": "",
                "best_url_source": "",
                "institution_name": "Lawrence Technological University",
                "webaddr": "www.ltu.edu",
            }
        ]
    )

    seeds = bench.archive_expansion_seed_roots(
        tmp_path,
        "private",
        panel,
        max_seed_roots_per_institution=1,
    )

    assert seeds["preferred_source_root_url"].tolist() == [
        "https://www.ltu.edu/wp-json/wp/v2/media?search=catalog&per_page=100"
    ]


def test_archive_expansion_seed_roots_include_library_archives_under_cap(tmp_path):
    panel = pd.DataFrame(
        [
            {
                "unitid": 232557,
                "target_year": 2002,
                "best_url": "",
                "best_url_source": "",
                "institution_name": "Liberty University",
                "webaddr": "www.liberty.edu",
            }
        ]
    )

    seeds = bench.archive_expansion_seed_roots(
        tmp_path,
        "private",
        panel,
        max_seed_roots_per_institution=8,
    )

    assert any("/library/archives/" in url for url in seeds["preferred_source_root_url"])
    assert "generated_repository_root:generated_repository_library_archives_path" in seeds[
        "preferred_source_root_type"
    ].tolist()


def test_merge_final_panel_prefers_catalog_document_over_same_year_wordpress_form():
    base_panel = pd.DataFrame(
        [
            {
                "unitid": 213385,
                "institution_name": "Lafayette College",
                "fresh_rank": 98,
                "target_year": 2011,
                "best_url": "",
                "best_url_source": "",
            },
            {
                "unitid": 213385,
                "institution_name": "Lafayette College",
                "fresh_rank": 98,
                "target_year": 2013,
                "best_url": "",
                "best_url_source": "",
            }
        ]
    )
    candidates = pd.DataFrame(
        [
            {
                "unitid": 213385,
                "institution_name": "Lafayette College",
                "target_year": 2011,
                "catalog_year_start": 2011,
                "catalog_year_end": 2012,
                "candidate_url": "https://registrar.lafayette.edu/wp-content/uploads/sites/193/2011/06/Internship-Draft_distributed.pdf",
                "candidate_link_text": "Summer Internship Form",
                "candidate_evidence_text": "Summer Internship Form WordPress media catalog search",
                "candidate_evidence_source": "wordpress_media_api",
                "candidate_source_method": "clean_archive_expansion",
                "candidate_priority": 25,
                "archive_url": "https://registrar.lafayette.edu/wp-json/wp/v2/media?per_page=100&search=2011",
            },
            {
                "unitid": 213385,
                "institution_name": "Lafayette College",
                "target_year": 2011,
                "catalog_year_start": 2011,
                "catalog_year_end": 2012,
                "candidate_url": "https://registrar.lafayette.edu/wp-content/uploads/sites/193/2011/08/Lafayette-College_11_12.pdf",
                "candidate_link_text": "Lafayette College_11_12",
                "candidate_evidence_text": "Lafayette College_11_12 WordPress media catalog search",
                "candidate_evidence_source": "wordpress_media_api",
                "candidate_source_method": "clean_archive_expansion",
                "candidate_priority": 25,
                "archive_url": "https://registrar.lafayette.edu/wp-json/wp/v2/media?per_page=100&search=11_12",
            },
            {
                "unitid": 213385,
                "institution_name": "Lafayette College",
                "target_year": 2013,
                "catalog_year_start": 2013,
                "catalog_year_end": 2014,
                "candidate_url": "https://registrar.lafayette.edu/wp-content/uploads/sites/193/2014/03/Academic_Calendar13-14.pdf",
                "candidate_link_text": "Academic_Calendar13-14",
                "candidate_evidence_text": "Academic_Calendar13-14 WordPress media catalog search",
                "candidate_evidence_source": "wordpress_media_api",
                "candidate_source_method": "clean_archive_expansion",
                "candidate_priority": 25,
                "archive_url": "https://registrar.lafayette.edu/wp-json/wp/v2/media?per_page=100&search=2014",
            },
            {
                "unitid": 213385,
                "institution_name": "Lafayette College",
                "target_year": 2013,
                "catalog_year_start": 2013,
                "catalog_year_end": 2014,
                "candidate_url": "https://registrar.lafayette.edu/wp-content/uploads/sites/193/2014/07/Lafayette-College_13_14.pdf",
                "candidate_link_text": "Lafayette College_13_14",
                "candidate_evidence_text": "Lafayette College_13_14 WordPress media catalog search",
                "candidate_evidence_source": "wordpress_media_api",
                "candidate_source_method": "clean_archive_expansion",
                "candidate_priority": 25,
                "archive_url": "https://registrar.lafayette.edu/wp-json/wp/v2/media?per_page=100&search=13_14",
            },
        ]
    )

    panel = bench.merge_final_panel(base_panel, candidates)

    assert panel["final_best_url"].tolist() == [
        "https://registrar.lafayette.edu/wp-content/uploads/sites/193/2011/08/Lafayette-College_11_12.pdf",
        "https://registrar.lafayette.edu/wp-content/uploads/sites/193/2014/07/Lafayette-College_13_14.pdf",
    ]


def test_merge_final_panel_replaces_risky_catalogarchive_root_with_retrieved_pdf():
    base_panel = pd.DataFrame(
        [
            {
                "unitid": 214069,
                "institution_name": "Misericordia University",
                "fresh_rank": 121,
                "target_year": 2014,
                "best_url": "http://catalogarchive.misericordia.edu/catalog201415/",
                "best_url_source": "table_row_context",
            }
        ]
    )
    candidates = pd.DataFrame(
        [
            {
                "unitid": 214069,
                "institution_name": "Misericordia University",
                "target_year": 2014,
                "catalog_year_start": 2014,
                "catalog_year_end": 2015,
                "candidate_url": "https://www.misericordia.edu/uploaded/documents/academics/catalogs/2014_2015_undergraduate_and_graduate_catalog.pdf",
                "candidate_link_text": "2014 2015 undergraduate and graduate catalog",
                "candidate_evidence_text": "2014 2015 undergraduate and graduate catalog",
                "candidate_evidence_source": "inferred_year_url_pattern",
                "candidate_source_method": "inferred_year_url_pattern",
                "candidate_priority": 18,
                "archive_url": "",
            }
        ]
    )

    panel = bench.merge_final_panel(base_panel, candidates)

    assert panel.iloc[0]["final_best_url"] == (
        "https://www.misericordia.edu/uploaded/documents/academics/catalogs/"
        "2014_2015_undergraduate_and_graduate_catalog.pdf"
    )
    assert panel.iloc[0]["final_status"] == "candidate_replaced_risky_catalogarchive"


def test_candidate_document_priority_demotes_reports_and_prefers_undergraduate_catalogs():
    assessment = pd.Series(
        {
            "candidate_url": "https://ltu.edu/wp-content/uploads/2026/02/University-Assessment-Report-2005-2006.pdf",
            "candidate_link_text": "University Assessment Report 2005-2006",
        }
    )
    graduate_catalog = pd.Series(
        {
            "candidate_url": "https://ltu.edu/wp-content/uploads/2026/02/GR-LTU-Catalog-WC-13-14-Final.pdf",
            "candidate_link_text": "GR-LTU-Catalog-WC-13-14-Final",
        }
    )
    undergraduate_catalog = pd.Series(
        {
            "candidate_url": "https://ltu.edu/wp-content/uploads/2026/02/UG-LTU-catalog-2013-14-FINAL-10-4-13.pdf",
            "candidate_link_text": "UG-LTU-catalog-2013-14-FINAL-10-4-13",
        }
    )
    abbreviated_undergraduate_catalog = pd.Series(
        {
            "candidate_url": "https://ltu.edu/wp-content/uploads/2026/02/LTU_UGradCat05-07.pdf",
            "candidate_link_text": "LTU_UGradCat05-07",
        }
    )

    assert candidate_document_priority(assessment) == 90
    assert candidate_document_priority(undergraduate_catalog) < candidate_document_priority(graduate_catalog)
    assert candidate_document_priority(abbreviated_undergraduate_catalog) < candidate_document_priority(assessment)


def test_archive_expansion_seed_roots_generate_clean_repository_hosts_for_missing_years(tmp_path):
    outputs = bench.stream_outputs(tmp_path, "private")
    for path in outputs.__dict__.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "unitid": 10,
                "batch3_rank": 1,
                "fresh_rank": 1,
                "institution_name": "Example College",
                "fresh_discovery_status": "year_candidates_found",
            }
        ]
    ).to_csv(outputs.institution_status_csv, index=False)
    panel = pd.DataFrame(
        [
            {
                "unitid": 10,
                "target_year": 2001,
                "best_url": "",
                "best_url_source": "",
                "institution_name": "Example College",
                "webaddr": "www.example.edu",
            },
            {
                "unitid": 10,
                "target_year": 2020,
                "best_url": "https://catalog.example.edu/2020-2021/",
                "best_url_source": "visible_link_text",
                "institution_name": "Example College",
                "webaddr": "www.example.edu",
            },
        ]
    )

    seeds = bench.archive_expansion_seed_roots(tmp_path, "private", panel, max_seed_roots_per_institution=20)

    seed_urls = set(seeds["preferred_source_root_url"])
    assert "https://digitalcommons.example.edu/" in seed_urls
    assert "https://academicarchive.example.edu/" in seed_urls
    assert "https://repository.example.edu/" in seed_urls


def test_generated_repository_seed_roots_include_img2_catalog_directory():
    panel = pd.DataFrame(
        [
            {
                "unitid": 232265,
                "institution_name": "Hampton University",
                "target_year": 2014,
                "best_url": "",
                "webaddr": "www.hamptonu.edu",
            }
        ]
    )

    seeds = bench.generated_repository_seed_roots(panel)

    assert "https://img2.hamptonu.edu/hu/docs/catalogs/" in set(seeds["seed_url"])


def test_official_domain_seed_urls_include_year_prefixed_bulletin_pages():
    urls = bench.official_domain_pdf_template_seed_urls(
        "https://www.loyno.edu",
        "Loyola University New Orleans",
        target_year=2012,
        max_urls=12,
    )

    assert urls[:3] == [
        "https://2012bulletin.loyno.edu/undergraduate.html",
        "https://2012bulletin.loyno.edu/undergraduate/index.php.html",
        "https://2012bulletin.loyno.edu/undergraduate/",
    ]


def test_official_domain_seed_urls_include_historical_pdf_shapes():
    urls = bench.official_domain_pdf_template_seed_urls(
        "https://www.madonna.edu",
        "Madonna University",
        target_year=2004,
        max_urls=40,
    )

    assert "https://www.madonna.edu/pdf/REG_ugbulletin04-06.pdf" in urls
    assert "https://www.madonna.edu/pdf/REG_ugbulletin04_06.pdf" in urls
    assert "https://www.madonna.edu/pdf/REG_UGBulletin04-06-1.pdf" in urls


def test_official_domain_seed_urls_include_prior_year_span_shapes_for_middle_years():
    urls = bench.official_domain_pdf_template_seed_urls(
        "https://www.madonna.edu",
        "Madonna University",
        target_year=2007,
        max_urls=40,
    )

    assert "https://www.madonna.edu/pdf/REG_06_08_ugradb.pdf" in urls
    assert "https://www.madonna.edu/pdf/REG_ugbulletin06-08.pdf" in urls


def test_official_domain_seed_urls_prioritize_reg_catalog_shape_under_probe_cap():
    urls = bench.official_domain_pdf_template_seed_urls(
        "https://www.madonna.edu",
        "Madonna University",
        target_year=2016,
        max_urls=32,
    )

    assert "https://www.madonna.edu/pdf/REG_UG_Catalog_16-17_11.pdf" in urls


def test_official_domain_seed_urls_prioritize_batch14_archive_pdf_shapes_under_probe_cap():
    mckendree = bench.official_domain_pdf_template_seed_urls(
        "https://www.mckendree.edu",
        "McKendree University",
        target_year=2012,
        max_urls=36,
    )
    millikin = bench.official_domain_pdf_template_seed_urls(
        "https://millikin.edu",
        "Millikin University",
        target_year=2015,
        max_urls=36,
    )
    misericordia = bench.official_domain_pdf_template_seed_urls(
        "https://www.misericordia.edu",
        "Misericordia University",
        target_year=2013,
        max_urls=36,
    )
    msoe = bench.official_domain_pdf_template_seed_urls(
        "https://www.msoe.edu",
        "Milwaukee School of Engineering",
        target_year=2002,
        max_urls=36,
    )

    mckendree_url = "https://www.mckendree.edu/academics/info/course-catalogs/undergraduate-catalog-2012-2013.pdf"
    millikin_url = "https://millikin.edu/sites/default/files/2023-03/2015-2016_bulletin_4.pdf"
    misericordia_url = (
        "https://www.misericordia.edu/uploaded/documents/academics/catalogs/"
        "2013-2014_undergraduate_and_graduate_catalog.pdf"
    )
    msoe_url = "https://s3.amazonaws.com/msoe/files/resources/undergrad-catalog-2002-2003.pdf"

    assert mckendree.index(mckendree_url) < 32
    assert millikin.index(millikin_url) < 32
    assert misericordia.index(misericordia_url) < 32
    assert msoe.index(msoe_url) < 32


def test_official_domain_seed_urls_prioritize_batch14_gap_fill_shapes_under_probe_cap():
    cases = [
        (
            bench.official_domain_pdf_template_seed_urls(
                "https://www.mckendree.edu",
                "McKendree University",
                target_year=2007,
                max_urls=36,
            ),
            "https://www.mckendree.edu/academics/info/course-catalogs/mck-07-08-catalog.pdf",
        ),
        (
            bench.official_domain_pdf_template_seed_urls(
                "https://millikin.edu",
                "Millikin University",
                target_year=2010,
                max_urls=36,
            ),
            "https://millikin.edu/sites/default/files/2023-03/bulletin_10_11final_052110.pdf",
        ),
        (
            bench.official_domain_pdf_template_seed_urls(
                "https://millikin.edu",
                "Millikin University",
                target_year=2011,
                max_urls=36,
            ),
            "https://millikin.edu/sites/default/files/2023-03/millik_bulletin_2011-2012_finalpdf1.pdf",
        ),
        (
            bench.official_domain_pdf_template_seed_urls(
                "https://millikin.edu",
                "Millikin University",
                target_year=2014,
                max_urls=36,
            ),
            "https://millikin.edu/sites/default/files/2023-03/final_2014-2015_bulletin_27-jan-15.pdf",
        ),
        (
            bench.official_domain_pdf_template_seed_urls(
                "https://www.misericordia.edu",
                "Misericordia University",
                target_year=2004,
                max_urls=36,
            ),
            "https://archive.org/download/catalog0405mise/catalog0405mise.pdf",
        ),
        (
            bench.official_domain_pdf_template_seed_urls(
                "https://www.misericordia.edu",
                "Misericordia University",
                target_year=2008,
                max_urls=36,
            ),
            "https://www.misericordia.edu/uploaded/documents/academics/catalogs/2008_2009_catalog.pdf",
        ),
        (
            bench.official_domain_pdf_template_seed_urls(
                "https://www.jmu.edu",
                "James Madison University",
                target_year=2008,
                max_urls=36,
            ),
            "https://www.jmu.edu/academics/info/course-catalogs/2008-2009-jmu-undergraduate-catalog.pdf",
        ),
        (
            bench.official_domain_pdf_template_seed_urls(
                "https://www.iup.edu",
                "Indiana University of Pennsylvania-Main Campus",
                target_year=2002,
                max_urls=36,
            ),
            "https://www.iup.edu/academics/info/course-catalogs/2002-2003-undergraduate-catalog.pdf",
        ),
    ]

    for urls, expected_url in cases:
        assert expected_url in urls
        assert urls.index(expected_url) < 32


def test_inferred_year_candidate_rows_expand_compact_two_digit_ranges():
    seed = pd.Series(
        {
            "unitid": 170806,
            "institution_name": "Madonna University",
            "target_year": 2006,
            "candidate_url": "https://www.madonna.edu/pdf/REG_06_08_ugradb.pdf",
            "candidate_link_text": "Generated official-domain catalog PDF probe for 2006-2007",
            "candidate_evidence_text": "",
            "archive_url": "https://www.madonna.edu/",
        }
    )
    result = {
        "retrieval_status": "retrieved_truncated",
        "http_status": 200,
        "page_title": "REG 06 08 ugradb.pdf",
    }

    rows = bench.inferred_year_candidate_rows_from_seed_result(seed, result)

    assert [row["target_year"] for row in rows] == [2006, 2007]


def test_official_domain_seed_urls_include_catalog_docs_and_previouscatalogs_shapes():
    grambling = bench.official_domain_pdf_template_seed_urls(
        "https://www.gram.edu",
        "Grambling State University",
        target_year=2005,
        max_urls=40,
    )
    isu = bench.official_domain_pdf_template_seed_urls(
        "https://www.isu.edu",
        "Idaho State University",
        target_year=2008,
        max_urls=40,
    )

    assert "https://www.gram.edu/academics/catalog/docs/GSU2005-07catalog.pdf" in grambling
    assert "https://coursecat.isu.edu/previouscatalogs/2008-2009_ISU_UG_catalog-min.pdf" in isu


def test_archive_expansion_seed_roots_generate_clean_smartcatalogiq_host_for_missing_years(tmp_path):
    outputs = bench.stream_outputs(tmp_path, "private")
    for path in outputs.__dict__.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "unitid": 10,
                "batch3_rank": 1,
                "fresh_rank": 1,
                "institution_name": "Inter American University of Puerto Rico-Aguadilla",
                "fresh_discovery_status": "year_candidates_found",
            }
        ]
    ).to_csv(outputs.institution_status_csv, index=False)
    panel = pd.DataFrame(
        [
            {
                "unitid": 10,
                "target_year": 2011,
                "best_url": "",
                "best_url_source": "",
                "institution_name": "Inter American University of Puerto Rico-Aguadilla",
                "webaddr": "aguadilla.inter.edu/",
            },
            {
                "unitid": 10,
                "target_year": 2020,
                "best_url": "https://aguadilla.inter.edu/catalog-2020.pdf",
                "best_url_source": "visible_link_text",
                "institution_name": "Inter American University of Puerto Rico-Aguadilla",
                "webaddr": "aguadilla.inter.edu/",
            },
        ]
    )

    seeds = bench.archive_expansion_seed_roots(tmp_path, "private", panel, max_seed_roots_per_institution=20)

    seed_urls = set(seeds["preferred_source_root_url"])
    assert "https://inter.smartcatalogiq.com/" in seed_urls


def test_wayback_cdx_seed_roots_include_failed_clean_catalog_candidates_not_truth(tmp_path):
    outputs = bench.stream_outputs(tmp_path, "public")
    for path in outputs.__dict__.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "unitid": 1,
                "batch3_rank": 7,
                "fresh_rank": 7,
                "institution_name": "Example University",
                "fresh_discovery_status": "year_candidates_found",
            }
        ]
    ).to_csv(outputs.institution_status_csv, index=False)
    pd.DataFrame(
        [
            {
                "unitid": 1,
                "institution_name": "Example University",
                "candidate_url": "https://catalog.example.edu/",
                "candidate_source_type": "generated_catalog_subdomain",
                "retrieval_status": "url_error",
                "likely_catalog_root": False,
            },
            {
                "unitid": 1,
                "institution_name": "Example University",
                "candidate_url": "https://example.edu/admission/",
                "candidate_source_type": "generated_admission_path",
                "retrieval_status": "retrieved",
                "likely_catalog_root": False,
            },
        ]
    ).to_csv(outputs.root_candidates_csv, index=False)
    pd.DataFrame(
        [
            {
                "unitid": 1,
                "target_year": 2000,
                "best_url": "",
                "best_url_source": "",
                "institution_name": "Example University",
            },
            {
                "unitid": 1,
                "target_year": 2020,
                "best_url": "https://catalog.example.edu/2020-2021/",
                "best_url_source": "visible_link_text",
                "institution_name": "Example University",
            },
        ]
    ).to_csv(outputs.year_panel_csv, index=False)
    pd.DataFrame(
        [
            {
                "unitid": 1,
                "legacy_url": "https://withheld.example.edu/catalog-2000.pdf",
            }
        ]
    ).to_csv(outputs.truth_csv, index=False)

    current_panel = bench.normalize_full_year_panel_for_rescue(pd.read_csv(outputs.year_panel_csv))
    seeds = bench.wayback_cdx_seed_roots(tmp_path, "public", current_panel, max_seed_roots_per_institution=4)

    assert not seeds.empty
    assert seeds["seed_url"].str.contains("catalog.example.edu", regex=False).any()
    assert not seeds["seed_url"].str.contains("admission", regex=False).any()
    assert not seeds["seed_url"].str.contains("withheld", regex=False).any()
    assert "2000" in seeds["missing_target_years"].iloc[0]


def test_assert_discovery_input_clean_rejects_legacy_column():
    with pytest.raises(ValueError, match="prohibited legacy columns"):
        assert_discovery_input_clean(
            pd.DataFrame(
                [
                    {
                        "source_stream": "public_clean_no_legacy_holdout",
                        "legacy_url": "https://example.edu/catalog.pdf",
                    }
                ]
            )
        )


def test_compact_year_panel_prefers_archive_expansion_panel(tmp_path):
    first = bench.stream_outputs(tmp_path, "public")
    inferred = bench.inferred_year_url_outputs(tmp_path, "public")
    expanded = bench.archive_expansion_outputs(tmp_path, "public")
    for path in [first.year_panel_csv, inferred.inferred_year_panel_csv, expanded.archive_expansion_panel_csv]:
        path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "unitid": 1,
                "fresh_rank": 1,
                "target_year": 2019,
                "best_url": "https://first.example.edu/catalog-2019.pdf",
                "institution_name": "Example University",
            }
        ]
    ).to_csv(first.year_panel_csv, index=False)
    pd.DataFrame(
        [
            {
                "unitid": 1,
                "fresh_rank": 1,
                "target_year": 2019,
                "best_url": "https://inferred.example.edu/catalog-2019.pdf",
                "institution_name": "Example University",
            }
        ]
    ).to_csv(inferred.inferred_year_panel_csv, index=False)
    pd.DataFrame(
        [
            {
                "unitid": 1,
                "fresh_rank": 1,
                "target_year": 2019,
                "best_url": "https://inferred.example.edu/catalog-2019.pdf",
                "final_best_url": "https://expanded.example.edu/catalog-2019.pdf",
                "final_best_url_source": "clean_archive_expansion",
                "final_status": "ai_candidate_added",
                "candidate_link_text": "2019-2020 Undergraduate Catalog",
                "candidate_evidence_source": "clean_archive_expansion",
                "catalog_year_start": 2019,
                "catalog_year_end": 2020,
                "archive_url": "https://expanded.example.edu/archive/",
                "institution_name": "Example University",
            }
        ]
    ).to_csv(expanded.archive_expansion_panel_csv, index=False)

    panel = compact_year_panel(tmp_path, "public")

    assert panel["clean_best_url"].tolist() == ["https://expanded.example.edu/catalog-2019.pdf"]


def test_best_panel_prefers_specific_pdf_over_risky_catalogarchive_root(tmp_path):
    inferred = bench.inferred_year_url_outputs(tmp_path, "private")
    expanded = bench.archive_expansion_outputs(tmp_path, "private")
    for path in [inferred.inferred_year_panel_csv, expanded.archive_expansion_panel_csv]:
        path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "unitid": 214069,
                "target_year": 2010,
                "best_url": "https://www.misericordia.edu/uploaded/documents/academics/catalogs/2010_2011_catalog.pdf",
                "best_url_source": "inferred_year_url_pattern",
                "institution_name": "Misericordia University",
            }
        ]
    ).to_csv(inferred.inferred_year_panel_csv, index=False)
    pd.DataFrame(
        [
            {
                "unitid": 214069,
                "target_year": 2010,
                "best_url": "http://catalogarchive.misericordia.edu/catalog1011/",
                "best_url_source": "table_row_context",
                "institution_name": "Misericordia University",
            }
        ]
    ).to_csv(expanded.archive_expansion_panel_csv, index=False)

    panel = bench.read_best_full_year_panel(tmp_path, "private")

    assert panel["best_url"].tolist() == [
        "https://www.misericordia.edu/uploaded/documents/academics/catalogs/2010_2011_catalog.pdf"
    ]


def test_best_panel_prefers_archive_expansion_over_stale_wayback_panel(tmp_path):
    wayback = bench.wayback_cdx_outputs(tmp_path, "private")
    expanded = bench.archive_expansion_outputs(tmp_path, "private")
    for path in [wayback.wayback_cdx_panel_csv, expanded.archive_expansion_panel_csv]:
        path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "unitid": 140447,
                "target_year": 2016,
                "best_url": "https://www.mercer.edu/pdf/REG_Undergrad20152017.pdf",
                "best_url_source": "inferred_year_url_pattern",
                "institution_name": "Mercer University",
            }
        ]
    ).to_csv(wayback.wayback_cdx_panel_csv, index=False)
    pd.DataFrame(
        [
            {
                "unitid": 140447,
                "target_year": 2016,
                "best_url": "https://galileo-mum.primo.exlibrisgroup.com/discovery/delivery/01GALI_MUM:MainLibrary/991005673387205956",
                "best_url_source": "clean_archive_expansion",
                "institution_name": "Mercer University",
            }
        ]
    ).to_csv(expanded.archive_expansion_panel_csv, index=False)

    panel = bench.read_best_full_year_panel(tmp_path, "private")

    assert panel["_selected_panel_file"].tolist() == ["archive_expansion_year_panel.csv"]
    assert panel["best_url"].tolist() == [
        "https://galileo-mum.primo.exlibrisgroup.com/discovery/delivery/01GALI_MUM:MainLibrary/991005673387205956"
    ]


def test_official_template_rescue_includes_risky_catalogarchive_rows(tmp_path):
    outputs = bench.stream_outputs(tmp_path, "private")
    outputs.discovery_input_csv.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "unitid": 214069,
                "institution_name": "Misericordia University",
                "webaddr": "www.misericordia.edu/",
            }
        ]
    ).to_csv(outputs.discovery_input_csv, index=False)
    panel = pd.DataFrame(
        [
            {
                "unitid": 214069,
                "target_year": 2010,
                "best_url": "http://catalogarchive.misericordia.edu/catalog1011/",
                "institution_name": "Misericordia University",
            }
        ]
    )

    seeds = bench.official_domain_pdf_template_seed_rows(tmp_path, "private", panel)

    assert not seeds.empty
    assert seeds["candidate_url"].str.contains("2010_2011_catalog.pdf", regex=False).any()


def test_compact_year_panel_prefers_wayback_cdx_panel(tmp_path):
    first = bench.stream_outputs(tmp_path, "public")
    expanded = bench.archive_expansion_outputs(tmp_path, "public")
    wayback = bench.wayback_cdx_outputs(tmp_path, "public")
    for path in [first.year_panel_csv, expanded.archive_expansion_panel_csv, wayback.wayback_cdx_panel_csv]:
        path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "unitid": 1,
                "fresh_rank": 1,
                "target_year": 2004,
                "best_url": "",
                "institution_name": "Example University",
            }
        ]
    ).to_csv(first.year_panel_csv, index=False)
    pd.DataFrame(
        [
            {
                "unitid": 1,
                "fresh_rank": 1,
                "target_year": 2004,
                "best_url": "",
                "final_best_url": "https://expanded.example.edu/catalog-2004.pdf",
                "final_best_url_source": "clean_archive_expansion",
                "final_status": "ai_candidate_added",
                "candidate_link_text": "2004-2005 Catalog",
                "candidate_evidence_source": "clean_archive_expansion",
                "catalog_year_start": 2004,
                "catalog_year_end": 2005,
                "institution_name": "Example University",
            }
        ]
    ).to_csv(expanded.archive_expansion_panel_csv, index=False)
    pd.DataFrame(
        [
            {
                "unitid": 1,
                "fresh_rank": 1,
                "target_year": 2004,
                "best_url": "",
                "final_best_url": "https://web.archive.org/web/20041001000000id_/https://catalog.example.edu/",
                "final_best_url_source": "clean_wayback_cdx_content_dating",
                "final_status": "ai_candidate_added",
                "candidate_link_text": "Wayback catalog snapshot captured 20041001",
                "candidate_evidence_source": "wayback_timestamp_catalog_snapshot",
                "catalog_year_start": 2004,
                "catalog_year_end": 2005,
                "institution_name": "Example University",
            }
        ]
    ).to_csv(wayback.wayback_cdx_panel_csv, index=False)

    panel = compact_year_panel(tmp_path, "public")

    assert panel["clean_best_url"].tolist() == [
        "https://web.archive.org/web/20041001000000id_/https://catalog.example.edu/"
    ]


def test_validated_wayback_candidate_requires_year_or_in_year_catalog_snapshot():
    row = pd.Series(
        {
            "batch3_rank": 1,
            "unitid": 10,
            "institution_name": "Example University",
            "target_year": 2004,
            "seed_url": "https://catalog.example.edu/",
            "cdx_query_target": "https://catalog.example.edu/*",
            "wayback_original_url": "https://catalog.example.edu/",
            "wayback_timestamp": "20041001000000",
            "snapshot_url": "https://web.archive.org/web/20041001000000id_/https://catalog.example.edu/",
        }
    )
    result = {
        "retrieval_status": "retrieved",
        "http_status": 200,
        "page_title": "Example University Catalog",
        "year_hints": "",
        "catalog_year_start": "",
        "catalog_year_end": "",
    }

    candidate = bench.validated_wayback_candidate_row(row, result)

    assert candidate is not None
    assert candidate["validation_status"] == "wayback_timestamp_catalog_snapshot"
    result["page_title"] = "Example University Admissions"
    assert bench.validated_wayback_candidate_row(row, result) is None


def test_score_loss_bucket_reaches_success_only_after_exact_class_match():
    row = pd.Series(
        {
            "truth_policy_class_informative": True,
            "clean_output_row_present": True,
            "clean_has_url": True,
            "clean_policy_extraction_ready": True,
            "classification_row_present": True,
            "api_parsed": True,
            "classification_has_informative_class": True,
            "exact_policy_class_match": True,
        }
    )

    assert score_loss_bucket(row) == "08_exact_class_match_success"
    row["exact_policy_class_match"] = False
    assert score_loss_bucket(row) == "07_informative_class_mismatch"
    row["classification_has_informative_class"] = False
    assert score_loss_bucket(row) == "06_non_informative_classification"


def test_summarize_scores_keeps_source_and_final_class_denominators_separate():
    scores = pd.DataFrame(
        [
            {
                "truth_sector": "private",
                "truth_policy_class_informative": True,
                "clean_output_row_present": True,
                "clean_has_url": True,
                "clean_policy_extraction_ready": True,
                "classification_row_present": True,
                "classification_has_informative_class": True,
                "exact_policy_class_match": True,
                "clean_pipeline_success": True,
                "clean_url_exact_match_to_legacy": False,
                "loss_bucket": "08_exact_class_match_success",
            },
            {
                "truth_sector": "private",
                "truth_policy_class_informative": False,
                "clean_output_row_present": True,
                "clean_has_url": True,
                "clean_policy_extraction_ready": True,
                "classification_row_present": False,
                "classification_has_informative_class": False,
                "exact_policy_class_match": False,
                "clean_pipeline_success": False,
                "clean_url_exact_match_to_legacy": False,
                "loss_bucket": "00_truth_policy_class_not_informative",
            },
        ]
    )

    summary = summarize_scores(scores)
    keyed = {
        (row["sector"], row["denominator"], row["metric"]): row["count"]
        for _, row in summary.iterrows()
    }

    assert keyed[("private", "truth_rows_with_human_legacy_url", "denominator")] == 2
    assert keyed[("private", "informative_truth_policy_rows", "denominator")] == 1
    assert keyed[("private", "informative_truth_policy_rows", "exact_policy_class_match")] == 1


def test_retrieve_unique_truth_legacy_urls_fetches_each_url_once(monkeypatch):
    calls = []

    def fake_retrieve_url(url, *, timeout_seconds, max_bytes):
        calls.append((url, timeout_seconds, max_bytes))
        return {
            "retrieval_status": "retrieved",
            "http_status": 200,
            "final_url": url,
            "content_type": "text/html",
            "content_length_bytes": 123,
            "page_title": "Catalog",
            "sha256": "abc",
            "error_type": "",
            "error_message": "",
            "body": b"not saved",
        }

    monkeypatch.setattr(bench, "retrieve_url", fake_retrieve_url)

    retrieval = retrieve_unique_truth_legacy_urls(
        pd.Series(["https://b.example/catalog", "https://a.example/catalog", "https://a.example/catalog", ""]),
        timeout_seconds=7,
        max_workers=1,
        max_bytes=99,
    )

    assert calls == [
        ("https://a.example/catalog", 7, 99),
        ("https://b.example/catalog", 7, 99),
    ]
    assert retrieval["legacy_url"].tolist() == ["https://a.example/catalog", "https://b.example/catalog"]
    assert "body" not in retrieval.columns


def test_legacy_url_benchmark_validity_rejects_generic_homepage_redirect():
    valid, reason = bench.legacy_url_benchmark_validity(
        legacy_url="https://www.clarion.edu/academics/catalog-and-class-schedules/u-09-11.pdf",
        retrieval_status="retrieved_truncated",
        http_status="200",
        final_url="https://www.pennwest.edu/",
        content_type="text/html; charset=UTF-8",
        page_title="PennWest University",
    )

    assert not valid
    assert reason == "generic_landing_redirect"


def test_legacy_url_benchmark_validity_accepts_catalog_redirect():
    valid, reason = bench.legacy_url_benchmark_validity(
        legacy_url="http://academic-catalog.massart.edu/index.php",
        retrieval_status="retrieved",
        http_status="200",
        final_url="https://academic-catalog.massart.edu/index.php",
        content_type="text/html; charset=UTF-8",
        page_title="Massachusetts College of Art and Design",
    )

    assert valid
    assert reason == "valid"


def test_legacy_url_benchmark_validity_rejects_http_202_shell():
    valid, reason = bench.legacy_url_benchmark_validity(
        legacy_url="https://digarch.unco.edu/islandora/object/cogru%3A6822",
        retrieval_status="retrieved",
        http_status="202",
        final_url="https://digarch.unco.edu/islandora/object/cogru%3A6822",
        content_type="text/html; charset=UTF-8",
        page_title="",
    )

    assert not valid
    assert reason == "http_202_challenge_or_placeholder"


def test_summarize_scores_adds_currently_retrieved_truth_url_denominator():
    scores = pd.DataFrame(
        [
            {
                "truth_sector": "private",
                "truth_policy_class_informative": True,
                "clean_output_row_present": True,
                "clean_has_url": True,
                "clean_policy_extraction_ready": True,
                "classification_row_present": False,
                "classification_has_informative_class": False,
                "exact_policy_class_match": False,
                "clean_pipeline_success": False,
                "clean_url_exact_match_to_legacy": True,
                "truth_legacy_url_validity_checked": True,
                "truth_legacy_url_currently_retrieved": True,
                "truth_legacy_url_currently_valid": True,
                "loss_bucket": "04_no_classification_row",
            },
            {
                "truth_sector": "private",
                "truth_policy_class_informative": True,
                "clean_output_row_present": True,
                "clean_has_url": False,
                "clean_policy_extraction_ready": False,
                "classification_row_present": False,
                "classification_has_informative_class": False,
                "exact_policy_class_match": False,
                "clean_pipeline_success": False,
                "clean_url_exact_match_to_legacy": False,
                "truth_legacy_url_validity_checked": True,
                "truth_legacy_url_currently_retrieved": False,
                "truth_legacy_url_currently_valid": False,
                "loss_bucket": "02_clean_holdout_row_no_url",
            },
            {
                "truth_sector": "private",
                "truth_policy_class_informative": True,
                "clean_output_row_present": True,
                "clean_has_url": True,
                "clean_policy_extraction_ready": True,
                "classification_row_present": False,
                "classification_has_informative_class": False,
                "exact_policy_class_match": False,
                "clean_pipeline_success": False,
                "clean_url_exact_match_to_legacy": False,
                "truth_legacy_url_validity_checked": True,
                "truth_legacy_url_currently_retrieved": True,
                "truth_legacy_url_currently_valid": False,
                "loss_bucket": "04_no_classification_row",
            },
        ]
    )

    summary = summarize_scores(scores)
    keyed = {
        (row["sector"], row["denominator"], row["metric"]): row["count"]
        for _, row in summary.iterrows()
    }

    assert keyed[("private", "truth_rows_with_checked_human_legacy_url", "denominator")] == 3
    assert keyed[("private", "truth_rows_with_checked_human_legacy_url", "truth_legacy_url_currently_retrieved")] == 2
    assert keyed[("private", "truth_rows_with_checked_human_legacy_url", "truth_legacy_url_currently_valid")] == 1
    assert keyed[("private", "truth_rows_with_checked_human_legacy_url", "truth_legacy_url_retrieved_but_invalid")] == 1
    assert keyed[("private", "truth_rows_with_currently_retrieved_human_legacy_url", "denominator")] == 2
    assert keyed[("private", "truth_rows_with_currently_retrieved_human_legacy_url", "clean_has_url")] == 2
    assert keyed[("private", "truth_rows_with_currently_valid_human_legacy_url", "denominator")] == 1
    assert keyed[("private", "truth_rows_with_currently_valid_human_legacy_url", "clean_has_url")] == 1


def test_benchmark_policy_extraction_queue_filters_to_valid_clean_rows(tmp_path, monkeypatch):
    scores = pd.DataFrame(
        [
            {
                "truth_sector": "public",
                "unitid": 10,
                "institution_name": "Example State",
                "state": "CA",
                "target_year": 2019,
                "clean_policy_extraction_ready": True,
                "truth_legacy_url_currently_valid": True,
                "clean_best_url": "https://example.edu/catalog-2019.pdf",
                "candidate_evidence_source": "root_archive_link",
                "candidate_link_text": "2019 Catalog",
                "archive_url": "https://example.edu/catalogs",
                "clean_source_scope_type": "catalog_confirmed",
                "clean_scope_review_flag": "",
                "legacy_url": "https://legacy.example.edu/withheld.pdf",
                "legacy_policy_class": "grade_forgiveness",
            },
            {
                "truth_sector": "public",
                "unitid": 20,
                "institution_name": "Invalid Denominator",
                "state": "CA",
                "target_year": 2019,
                "clean_policy_extraction_ready": True,
                "truth_legacy_url_currently_valid": False,
                "clean_best_url": "https://example.edu/catalog-2019.pdf",
                "candidate_evidence_source": "root_archive_link",
                "candidate_link_text": "2019 Catalog",
                "archive_url": "https://example.edu/catalogs",
                "clean_source_scope_type": "catalog_confirmed",
                "clean_scope_review_flag": "",
            },
        ]
    )
    monkeypatch.setattr(bench, "score_rows", lambda repo_root, sectors: scores)

    queue = build_benchmark_policy_extraction_queue(tmp_path, ["public"])

    assert len(queue) == 1
    assert queue.iloc[0]["source_stream"] == "public_clean_no_legacy_holdout"
    assert queue.iloc[0]["source_url"] == "https://example.edu/catalog-2019.pdf"
    assert "legacy_url" not in queue.columns
    assert "legacy_policy_class" not in queue.columns


def test_reset_discovery_preflight_fails_before_overwriting_outputs(tmp_path, monkeypatch):
    outputs = bench.stream_outputs(tmp_path, "public")
    for path in outputs.__dict__.values():
        path.parent.mkdir(parents=True, exist_ok=True)

    discovery_input = pd.DataFrame(
        [
            {
                "source_stream": "public_clean_no_legacy_holdout",
                "benchmark_protocol": "clean_no_legacy_benchmark",
                "counts_as_clean_no_legacy_benchmark": True,
                "fresh_rank": 1,
                "batch3_rank": 1,
                "unitid": 100,
                "institution_name": "Example State University",
                "state": "CA",
                "webaddr": "www.example.edu",
                "clean_holdout_status": "clean_no_legacy_holdout_needs_discovery",
                "created_at": "2026-01-01T00:00:00+00:00",
            }
        ]
    )
    discovery_input.to_csv(outputs.discovery_input_csv, index=False)
    outputs.root_candidates_csv.write_text("old_root_candidates\n", encoding="utf-8")

    def fail_preflight(timeout_seconds: int) -> None:
        raise RuntimeError("network blocked")

    monkeypatch.setattr(bench, "assert_network_preflight", fail_preflight)

    with pytest.raises(RuntimeError, match="network blocked"):
        bench.run_discovery_for_sector(
            tmp_path,
            "public",
            limit=None,
            rank_start=1,
            timeout_seconds=1,
            max_root_candidates_per_institution=1,
            max_archive_pages_per_institution=1,
            max_workers=1,
            chunk_size=1,
            resume=False,
        )

    assert outputs.root_candidates_csv.read_text(encoding="utf-8") == "old_root_candidates\n"
    assert not list((outputs.root_candidates_csv.parent.parent / "archive").rglob("root_candidates.csv"))


def test_compact_year_panel_uses_final_candidate_metadata_from_ai_merge(tmp_path):
    path = bench.ai_rescue_outputs(tmp_path, "public").ai_rescue_year_panel_csv
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "unitid": 10,
                "target_year": 2005,
                "best_url": "https://www.example.edu/2005/",
                "best_url_source": "visible_link_text",
                "catalog_year_start": 2005,
                "catalog_year_end": 2006,
                "candidate_link_text_x": "2005-2006 Undergraduate Catalog",
                "archive_url_x": "https://www.example.edu/catalogs/",
                "ai_candidate_url": "",
                "candidate_source_method": "",
                "candidate_link_text_y": "",
                "archive_url_y": "",
                "final_best_url": "https://www.example.edu/2005/",
                "final_best_url_source": "visible_link_text",
                "final_status": "first_pass_candidate_found",
            },
            {
                "unitid": 20,
                "target_year": 2008,
                "best_url": "",
                "best_url_source": "",
                "catalog_year_start": "",
                "catalog_year_end": "",
                "candidate_link_text_x": "",
                "archive_url_x": "",
                "ai_candidate_url": "https://www.example.edu/2008/",
                "candidate_source_method": "ai_verified_root_archive",
                "candidate_link_text_y": "2008-2009 Undergraduate Catalog",
                "archive_url_y": "https://www.example.edu/archive/",
                "final_best_url": "https://www.example.edu/2008/",
                "final_best_url_source": "ai_verified_root_archive",
                "final_status": "ai_candidate_added",
            },
        ]
    ).to_csv(path, index=False)

    panel = compact_year_panel(tmp_path, "public").sort_values("unitid")

    assert panel["candidate_link_text"].tolist() == [
        "2005-2006 Undergraduate Catalog",
        "2008-2009 Undergraduate Catalog",
    ]
    assert panel["archive_url"].tolist() == [
        "https://www.example.edu/catalogs/",
        "https://www.example.edu/archive/",
    ]
    assert panel["clean_policy_extraction_ready"].tolist() == [True, True]


def test_select_ai_rescue_cases_uses_year_candidates_found_as_lowest_priority():
    status = pd.DataFrame(
        [
            {
                "unitid": 1,
                "institution_name": "Some Years U",
                "fresh_rank": 1,
                "fresh_discovery_status": "year_candidates_found",
            },
            {
                "unitid": 2,
                "institution_name": "No Years U",
                "fresh_rank": 2,
                "fresh_discovery_status": "source_root_found_no_explicit_years",
            },
            {
                "unitid": 3,
                "institution_name": "No Root U",
                "fresh_rank": 3,
                "fresh_discovery_status": "source_root_not_found",
            },
        ]
    )

    cases = select_ai_rescue_cases(status, max_cases=None)

    assert cases["unitid"].tolist() == [2, 3, 1]


def test_add_year_gap_context_to_status_uses_current_final_panel():
    status = pd.DataFrame(
        [
            {
                "unitid": 10,
                "institution_name": "Example University",
                "fresh_discovery_status": "year_candidates_found",
            }
        ]
    )
    panel = pd.DataFrame(
        [
            {"unitid": 10, "target_year": 2000, "final_best_url": "https://example.edu/2000/"},
            {"unitid": 10, "target_year": 2001, "final_best_url": ""},
            {"unitid": 10, "target_year": 2002, "final_best_url": "https://example.edu/2002/"},
        ]
    )

    enriched = add_year_gap_context_to_status(status, panel)

    assert enriched.loc[0, "observed_candidate_years"] == "2000; 2002"
    assert enriched.loc[0, "missing_target_years"] == "2001"
    assert int(enriched.loc[0, "missing_target_year_count"]) == 1


def test_ai_case_prompt_includes_missing_target_year_context():
    case = pd.Series(
        {
            "unitid": 10,
            "institution_name": "Example University",
            "fresh_rank": 1,
            "state": "AA",
            "webaddr": "www.example.edu",
            "fresh_discovery_status": "year_candidates_found",
            "preferred_source_root_url": "https://catalog.example.edu/",
            "observed_candidate_years": "2019; 2020",
            "missing_target_years": "2000; 2001",
            "missing_target_year_count": 2,
        }
    )

    prompt = build_ai_case_prompt(case, pd.DataFrame(), sector="public")

    assert '"missing_target_years": "2000; 2001"' in prompt
    assert "Prioritize official catalog URLs or archive roots that cover the listed missing_target_years" in prompt


def test_ai_year_gap_cases_use_current_clean_panel_missing_years():
    status = pd.DataFrame(
        [
            {
                "unitid": 10,
                "fresh_rank": 1,
                "institution_name": "Example University",
                "state": "AA",
                "webaddr": "www.example.edu",
                "fresh_discovery_status": "year_candidates_found",
                "final_discovery_status": "candidate_years_found",
                "preferred_source_root_url": "https://catalog.example.edu/",
            }
        ]
    )
    panel = pd.DataFrame(
        [
            {"unitid": 10, "target_year": 2000, "best_url": "https://catalog.example.edu/2000/"},
            {"unitid": 10, "target_year": 2001, "best_url": ""},
            {"unitid": 10, "target_year": 2002, "best_url": ""},
        ]
    )

    cases = build_ai_year_gap_cases(status, panel, max_cases=None)
    prompt = build_ai_year_gap_prompt(cases.iloc[0], pd.DataFrame(), sector="private")

    assert cases.loc[0, "observed_candidate_years"] == "2000"
    assert cases.loc[0, "missing_target_years"] == "2001; 2002"
    assert "legacy_url" not in prompt
    assert "The missing_target_years are clean panel years with no URL" in prompt


def test_ai_year_gap_direct_candidates_cover_only_missing_years(monkeypatch):
    def fake_retrieve_url(url, *, timeout_seconds, max_bytes):
        return {
            "retrieval_status": "retrieved",
            "http_status": 200,
            "final_url": url,
            "content_type": "text/html",
            "page_title": "2005-2007 Catalog",
        }

    monkeypatch.setattr(bench, "retrieve_url", fake_retrieve_url)
    triage = pd.DataFrame(
        [
            {
                "unitid": 10,
                "institution_name": "Example University",
                "missing_target_years": "2005; 2006",
                "api_direct_catalog_urls_json": (
                    '[{"url":"https://catalog.example.edu/2005-2007/",'
                    '"catalog_year_text":"2005-2007 Undergraduate Catalog",'
                    '"covered_start_year":2005,"covered_end_year":2007,'
                    '"evidence":"official catalog archive"}]'
                ),
            }
        ]
    )

    candidates = ai_year_gap_direct_candidates(triage, timeout_seconds=3)

    assert candidates["target_year"].tolist() == [2005, 2006]
    assert candidates["candidate_source_method"].unique().tolist() == ["ai_year_gap_direct_catalog_url"]


def test_acalog_media_bucket_variants_try_bounded_bucket_values():
    variants = bench.acalog_media_bucket_variants("https://catalog.example.edu/mime/media/2/1212/20022003.pdf")

    assert variants[0] == "https://catalog.example.edu/mime/media/2/1212/20022003.pdf"
    assert "https://catalog.example.edu/mime/media/44/1212/20022003.pdf" in variants


def test_ai_year_gap_direct_candidates_accept_bucket_variant(monkeypatch):
    def fake_retrieve_result(url):
        if "/mime/media/44/" in url:
            return {
                "retrieval_status": "retrieved",
                "http_status": 200,
                "final_url": url,
                "content_type": "application/pdf",
                "page_title": "2002-2003 Catalog",
            }
        return {
            "retrieval_status": "http_error",
            "http_status": 404,
            "final_url": "",
            "content_type": "",
            "page_title": "",
        }

    def fake_retrieve_ai_direct_url(url, *, timeout_seconds, max_bytes):
        return fake_retrieve_result(url)

    def fake_retrieve_url(url, *, timeout_seconds, max_bytes):
        return fake_retrieve_result(url)

    monkeypatch.setattr(bench, "retrieve_ai_direct_url", fake_retrieve_ai_direct_url)
    monkeypatch.setattr(bench, "retrieve_url", fake_retrieve_url)
    triage = pd.DataFrame(
        [
            {
                "unitid": 10,
                "institution_name": "Example University",
                "missing_target_years": "2002",
                "api_direct_catalog_urls_json": (
                    '[{"url":"https://catalog.example.edu/mime/media/2/1212/20022003.pdf",'
                    '"catalog_year_text":"2002-2003 Undergraduate Catalog",'
                    '"covered_start_year":2002,"covered_end_year":2003,'
                    '"evidence":"official catalog PDF"}]'
                ),
            }
        ]
    )

    candidates = ai_year_gap_direct_candidates(triage, timeout_seconds=3)

    assert candidates["candidate_url"].tolist() == [
        "https://catalog.example.edu/mime/media/44/1212/20022003.pdf"
    ]
    assert "retrieved Modern Campus media bucket variant" in candidates["candidate_evidence_text"].iloc[0]


def test_year_range_from_ai_direct_item_allows_old_range_overlap():
    assert year_range_from_ai_direct_item(
        {"covered_start_year": 1970, "covered_end_year": 2012, "catalog_year_text": "Older Catalogs (1970-2012)"}
    ) == (1970, 2012)


def test_ai_year_gap_direct_candidates_skip_retrieval_timeout(monkeypatch):
    def fake_retrieve_url(url, *, timeout_seconds, max_bytes):
        raise TimeoutError("slow direct URL")

    monkeypatch.setattr(bench, "retrieve_url", fake_retrieve_url)
    triage = pd.DataFrame(
        [
            {
                "unitid": 10,
                "institution_name": "Example University",
                "missing_target_years": "2005",
                "api_direct_catalog_urls_json": (
                    '[{"url":"https://catalog.example.edu/2005/",'
                    '"catalog_year_text":"2005 Undergraduate Catalog",'
                    '"covered_start_year":2005,"covered_end_year":2006,'
                    '"evidence":"official catalog archive"}]'
                ),
            }
        ]
    )

    candidates = ai_year_gap_direct_candidates(triage, timeout_seconds=3)

    assert candidates.empty


def test_api_error_attempts_remain_retryable():
    triage = pd.DataFrame(
        [
            {"unitid": 1, "api_validation_status": "parsed"},
            {"unitid": 2, "api_validation_status": "api_error"},
        ]
    )

    assert non_retryable_ai_attempted_unitids(triage) == {1}


def test_pending_status_materialization_uses_saved_parsed_triage():
    triage = pd.DataFrame(
        [
            {"unitid": 1, "api_validation_status": "parsed"},
            {"unitid": 2, "api_validation_status": "parsed"},
            {"unitid": 3, "api_validation_status": "api_error"},
        ]
    )
    status = pd.DataFrame(
        [
            {"unitid": 1, "api_validation_status": "parsed"},
            {"unitid": 2, "api_validation_status": ""},
        ]
    )

    pending = ai_triage_pending_status_materialization(triage, status)

    assert pending["unitid"].tolist() == [2]


def test_ai_triage_for_unitids_filters_saved_parsed_rows():
    triage = pd.DataFrame(
        [
            {"unitid": 1, "api_validation_status": "parsed"},
            {"unitid": 2, "api_validation_status": "parsed"},
            {"unitid": 3, "api_validation_status": "api_error"},
        ]
    )

    pending = ai_triage_for_unitids(triage, {2, 3})

    assert pending["unitid"].tolist() == [2]


def test_inferred_year_url_replacements_require_source_year_match():
    assert inferred_year_url_replacements(
        "https://example.edu/catalog/2013-2014.pdf",
        source_year=2013,
        target_year=2015,
    ) == ["https://example.edu/catalog/2015-2016.pdf"]
    assert inferred_year_url_replacements(
        "https://www.lehigh.edu/LU_course_catalog_09-10.pdf",
        source_year=2009,
        target_year=2006,
    ) == ["https://www.lehigh.edu/LU_course_catalog_06-07.pdf"]
    assert (
        inferred_year_url_replacements(
            "https://example.edu/catalog/2013-2014.pdf",
            source_year=2012,
            target_year=2015,
        )
        == []
    )


def test_inferred_year_url_replacements_handle_compact_full_year_ranges():
    assert inferred_year_url_replacements(
        "https://catalog.example.edu/mime/media/44/1210/20042005.pdf",
        source_year=2004,
        target_year=2005,
    )[0] == "https://catalog.example.edu/mime/media/44/1210/20052006.pdf"


def test_inferred_year_url_replacements_add_same_directory_simple_pdf_variants():
    urls = inferred_year_url_replacements(
        "https://www.etbu.edu/sites/default/files/downloads/2016-2017%20Undergraduate%20Catalog%209.24.25.pdf",
        source_year=2016,
        target_year=2014,
    )

    assert "https://www.etbu.edu/sites/default/files/downloads/2014-2015.pdf" in urls


def test_catalog_root_pdf_template_urls_include_drake_undergraduate_pattern():
    urls = bench.catalog_root_pdf_template_urls("https://catalog.drake.edu/", target_year=2014)

    assert "https://catalog.drake.edu/pdf/2014-15_Undergraduate_Catalog.pdf" in urls


def test_catalog_root_pdf_template_urls_include_full_year_undergraduate_pattern():
    urls = bench.catalog_root_pdf_template_urls("https://catalog.gonzaga.edu/", target_year=2003)

    assert "https://catalog.gonzaga.edu/pdf/2003-2004Undergraduate_Catalog.pdf" in urls


def test_catalog_root_pdf_template_urls_include_http_previous_catalog_variant():
    urls = bench.catalog_root_pdf_template_urls("https://catalog.daltonstate.edu/", target_year=2012)

    assert "http://catalog.daltonstate.edu/previous/catalog-12-13.pdf" in urls


def test_official_domain_pdf_template_urls_include_common_homepage_pdf_patterns():
    eastern = bench.official_domain_pdf_template_urls(
        "www.easternct.edu/",
        "Eastern Connecticut State University",
        target_year=2016,
    )
    fandm = bench.official_domain_pdf_template_urls(
        "www.fandm.edu/",
        "Franklin and Marshall College",
        target_year=2016,
    )
    east_central = bench.official_domain_pdf_template_urls(
        "www.ecok.edu/",
        "East Central University",
        target_year=2013,
    )

    assert "https://www.easternct.edu/academics/_documents/easterncatalog-2016-2017.pdf" in eastern
    assert "https://www.fandm.edu/_resources/pdfs/2016-2017-catalog.pdf" in fandm
    assert (
        "https://www.ecok.edu/sites/default/files/website_files/Academics/Academic_Affairs/ECU_Catalog_13-14.pdf"
        in east_central
    )


def test_official_domain_pdf_template_urls_keep_likely_patterns_inside_default_cap():
    eastern = bench.official_domain_pdf_template_urls(
        "www.easternct.edu/",
        "Eastern Connecticut State University",
        target_year=2002,
    )
    delta = bench.official_domain_pdf_template_urls(
        "www.deltastate.edu/",
        "Delta State University",
        target_year=2015,
    )

    assert "https://www.easternct.edu/academics/_documents/easterncatalog-2002-2004.pdf" in eastern
    assert "https://www.deltastate.edu/docs/acad_affairs/2015-2016-ug-catalog.pdf" in delta


def test_official_domain_pdf_template_urls_prioritize_library_bulletin_archive_pattern():
    urls = bench.official_domain_pdf_template_urls(
        "www.highpoint.edu/",
        "High Point University",
        target_year=2002,
    )

    assert "https://library.highpoint.edu/archives/catalogs/high-point-university-bulletin-2002-03.pdf" in urls


def test_official_domain_pdf_template_urls_prioritize_registrar_wordpress_day_catalog_pattern():
    urls = bench.official_domain_pdf_template_urls(
        "www.indianatech.edu/",
        "Indiana Institute of Technology",
        target_year=2007,
    )

    assert "https://registrar.indianatech.edu/wp-content/uploads/sites/13/2014/04/Day-Catalog-07-08.pdf" in urls


def test_official_domain_pdf_template_urls_prioritize_inside_wordpress_catalog_pattern():
    urls = bench.official_domain_pdf_template_urls(
        "www.ewu.edu/",
        "Eastern Washington University",
        target_year=2004,
    )

    assert "https://inside.ewu.edu/records-and-registration/wp-content/uploads/sites/364/2022/09/04-05_Catalog.pdf" in urls


def test_official_domain_pdf_template_urls_prioritize_wordpress_prior_year_catalog_pattern():
    urls = bench.official_domain_pdf_template_urls(
        "www.hiram.edu/",
        "Hiram College",
        target_year=2005,
    )

    assert "https://www.hiram.edu/wp-content/uploads/2022/07/hiram-college-catalog-2004-2005.pdf" in urls


def test_official_domain_pdf_template_urls_include_simple_catalog_year_pdf_name():
    urls = bench.official_domain_pdf_template_urls(
        "www.hiram.edu/",
        "Hiram College",
        target_year=2009,
    )

    assert "https://www.hiram.edu/wp-content/uploads/2022/07/catalog2008.pdf" in urls


def test_official_domain_pdf_template_urls_include_compact_acronym_catalog_names():
    urls_2014 = bench.official_domain_pdf_template_urls(
        "www.hiram.edu/",
        "Hiram College",
        target_year=2014,
    )
    urls_2016 = bench.official_domain_pdf_template_urls(
        "www.hiram.edu/",
        "Hiram College",
        target_year=2016,
    )

    assert "https://www.hiram.edu/wp-content/uploads/2022/07/hccatalog1314final.pdf" in urls_2014
    assert "https://www.hiram.edu/wp-content/uploads/2022/07/College_catalog_1516.pdf" in urls_2016


def test_official_domain_pdf_template_urls_include_bounded_modern_campus_media_probe():
    urls = bench.official_domain_pdf_template_urls(
        "www.hope.edu/",
        "Hope College",
        target_year=2003,
    )

    assert "https://catalog.hope.edu/mime/media/7/2035/03-04-hope-college-catalog.pdf" in urls


def test_official_domain_pdf_template_urls_include_kings_style_pdf_paths():
    urls_2004 = bench.official_domain_pdf_template_urls(
        "www.kings.edu/",
        "King's College",
        target_year=2004,
    )
    urls_2016 = bench.official_domain_pdf_template_urls(
        "www.kings.edu/",
        "King's College",
        target_year=2016,
    )

    assert "https://www.kings.edu/pdf/2004-05CourseCatalog.pdf" in urls_2004
    assert "https://www.kings.edu/academics/essentials/registrar/catalog2016-2017.pdf" in urls_2016


def test_official_domain_pdf_template_urls_include_general_historical_pdf_patterns():
    lee = bench.official_domain_pdf_template_urls(
        "www.leeuniversity.edu/",
        "Lee University",
        target_year=2004,
    )
    frostburg = bench.official_domain_pdf_template_urls(
        "www.frostburg.edu/",
        "Frostburg State University",
        target_year=2008,
    )
    gsw = bench.official_domain_pdf_template_urls(
        "www.gsw.edu/",
        "Georgia Southwestern State University",
        target_year=2003,
    )
    lafayette = bench.official_domain_pdf_template_urls(
        "www.lafayette.edu/",
        "Lafayette College",
        target_year=2008,
    )
    liberty = bench.official_domain_pdf_template_urls(
        "www.liberty.edu/",
        "Liberty University",
        target_year=2015,
    )

    assert "https://www.leeuniversity.edu/wp-content/uploads/2004-2005-Academic-Catalog.pdf" in lee
    assert (
        "https://www.frostburg.edu/_files/pdfs/academics/undergraduate-catalog-archive/2007-2009.pdf"
        in frostburg
    )
    assert "https://www.gsw.edu/registrar/bulletin/2003-All.pdf" in gsw
    assert "https://www.lafayette.edu/wp-content/uploads/Lafayette-College_08_09.pdf" in lafayette
    assert (
        "https://www.liberty.edu/wp-content/uploads/2015-2016-Liberty-University-Undergraduate-Catalog-Addendum.pdf"
        in liberty
    )


def test_official_domain_pdf_template_seed_urls_keep_regression_patterns_bounded():
    lee = bench.official_domain_pdf_template_seed_urls(
        "www.leeuniversity.edu/",
        "Lee University",
        target_year=2004,
    )
    frostburg = bench.official_domain_pdf_template_seed_urls(
        "www.frostburg.edu/",
        "Frostburg State University",
        target_year=2008,
    )
    gsw = bench.official_domain_pdf_template_seed_urls(
        "www.gsw.edu/",
        "Georgia Southwestern State University",
        target_year=2003,
    )

    assert len(lee) <= 36
    assert "https://www.leeuniversity.edu/wp-content/uploads/2004-2005-Academic-Catalog.pdf" in lee
    assert (
        "https://www.frostburg.edu/_files/pdfs/academics/undergraduate-catalog-archive/2007-2009.pdf"
        in frostburg
    )
    assert "https://www.gsw.edu/registrar/bulletin/2003-All.pdf" in gsw
    assert (
        "https://www.leeuniversity.edu/_media/department/registrar/documents/catalogues/ugc0405.pdf"
        in lee
    )


def test_inferred_year_url_replacements_try_wordpress_upload_date_variants():
    source = "https://registrar.lafayette.edu/wp-content/uploads/sites/193/2010/09/Lafayette-College_10_11.pdf"

    replacements = bench.inferred_year_url_replacements(source, source_year=2010, target_year=2012)

    assert "https://registrar.lafayette.edu/wp-content/uploads/sites/193/2014/02/Lafayette-College_12_13.pdf" in replacements


def test_cap_inferred_year_url_seeds_keeps_best_rows_per_institution_year():
    seeds = pd.DataFrame(
        [
            {
                "unitid": 1,
                "target_year": 2012,
                "source_target_year": 2020,
                "source_url": "https://example.edu/catalog-2020-2021.pdf",
                "candidate_url": "https://example.edu/catalog-2012-2013.pdf",
            },
            {
                "unitid": 1,
                "target_year": 2012,
                "source_target_year": 2013,
                "source_url": "https://example.edu/catalog-2013-2014.pdf",
                "candidate_url": "https://example.edu/catalog-2012-2013.pdf?variant=near",
            },
            {
                "unitid": 1,
                "target_year": 2012,
                "source_target_year": 2013,
                "source_url": "https://example.edu/catalog-2013-2014.pdf",
                "candidate_url": "https://example.edu/catalog-random.pdf",
            },
        ]
    )

    capped = bench.cap_inferred_year_url_seeds(seeds, max_per_institution_year=1)

    assert len(capped) == 1
    assert capped.iloc[0]["candidate_url"] == "https://example.edu/catalog-2012-2013.pdf?variant=near"


def test_official_domain_materializer_short_circuits_by_institution_year(monkeypatch):
    seeds = pd.DataFrame(
        [
            {
                "unitid": 220613,
                "institution_name": "Lee University",
                "target_year": 2004,
                "candidate_url": "https://www.leeuniversity.edu/wp-content/uploads/2004-2005-Academic-Catalog.pdf",
                "candidate_link_text": "Generated probe",
                "candidate_evidence_text": "Official-domain probe",
                "archive_url": "https://www.leeuniversity.edu/",
            },
            {
                "unitid": 220613,
                "institution_name": "Lee University",
                "target_year": 2004,
                "candidate_url": "https://www.leeuniversity.edu/wp-content/uploads/should-not-fetch-2004.pdf",
                "candidate_link_text": "Generated probe",
                "candidate_evidence_text": "Official-domain probe",
                "archive_url": "https://www.leeuniversity.edu/",
            },
            {
                "unitid": 162584,
                "institution_name": "Frostburg State University",
                "target_year": 2008,
                "candidate_url": "https://www.frostburg.edu/_files/pdfs/academics/undergraduate-catalog-archive/2008-2009.pdf",
                "candidate_link_text": "Generated probe",
                "candidate_evidence_text": "Official-domain probe",
                "archive_url": "https://www.frostburg.edu/",
            },
            {
                "unitid": 162584,
                "institution_name": "Frostburg State University",
                "target_year": 2008,
                "candidate_url": "https://www.frostburg.edu/_files/pdfs/academics/undergraduate-catalog-archive/2007-2009.pdf",
                "candidate_link_text": "Generated probe",
                "candidate_evidence_text": "Official-domain probe",
                "archive_url": "https://www.frostburg.edu/",
            },
        ]
    )
    called_urls = []

    def fake_retrieve_url(url, **_kwargs):
        called_urls.append(url)
        if "should-not-fetch" in url:
            raise AssertionError("successful target-year probe should short-circuit remaining probes")
        if url.endswith("2008-2009.pdf"):
            return {"retrieval_status": "http_error", "http_status": 404, "page_title": ""}
        return {
            "retrieval_status": "retrieved_truncated",
            "http_status": 200,
            "page_title": url.rsplit("/", 1)[-1],
        }

    monkeypatch.setattr(bench, "retrieve_url", fake_retrieve_url)

    candidates = bench.materialize_official_domain_year_url_candidates(
        seeds,
        timeout_seconds=4,
        max_workers=2,
    )

    assert "https://www.leeuniversity.edu/wp-content/uploads/should-not-fetch-2004.pdf" not in called_urls
    lee = candidates.loc[candidates["unitid"].eq(220613)]
    frostburg = candidates.loc[candidates["unitid"].eq(162584)]
    assert lee["target_year"].tolist() == [2004]
    assert set(frostburg["target_year"]) == {2007, 2008}


def test_official_domain_materializer_caps_probes_per_institution_year(monkeypatch):
    seeds = pd.DataFrame(
        [
            {
                "unitid": 1,
                "institution_name": "Example University",
                "target_year": 2010,
                "candidate_url": f"https://example.edu/catalog-2010-2011-{index}.pdf",
                "candidate_link_text": "Generated probe",
                "candidate_evidence_text": "Official-domain probe",
                "archive_url": "https://example.edu/",
            }
            for index in range(5)
        ]
    )
    called_urls = []

    def fake_retrieve_url(url, **_kwargs):
        called_urls.append(url)
        return {"retrieval_status": "http_error", "http_status": 404, "page_title": ""}

    monkeypatch.setattr(bench, "retrieve_url", fake_retrieve_url)

    candidates = bench.materialize_official_domain_year_url_candidates(
        seeds,
        timeout_seconds=4,
        max_workers=2,
        max_probes_per_institution_year=2,
    )

    assert candidates.empty
    assert called_urls == [
        "https://example.edu/catalog-2010-2011-0.pdf",
        "https://example.edu/catalog-2010-2011-1.pdf",
    ]


def test_generated_current_site_catalog_page_seed_roots_adds_registrar_archive_paths():
    panel = pd.DataFrame(
        [
            {
                "unitid": 134097,
                "institution_name": "Florida State University",
                "target_year": 2002,
                "best_url": "",
                "webaddr": "www.fsu.edu",
            }
        ]
    )

    seeds = bench.generated_current_site_catalog_page_seed_roots(panel)

    assert "https://registrar.fsu.edu/archive" in set(seeds["seed_url"])
    assert "https://registrar.fsu.edu/bulletin/archive" in set(seeds["seed_url"])


def test_generated_current_site_catalog_page_seed_roots_adds_course_catalog_and_catalog_archive_paths():
    panel = pd.DataFrame(
        [
            {
                "unitid": 170675,
                "institution_name": "Lawrence Technological University",
                "target_year": 2015,
                "best_url": "",
                "webaddr": "www.ltu.edu",
            },
            {
                "unitid": 220613,
                "institution_name": "Lee University",
                "target_year": 2015,
                "best_url": "",
                "webaddr": "www.leeuniversity.edu",
            },
        ]
    )

    seeds = bench.generated_current_site_catalog_page_seed_roots(panel)

    assert "https://www.ltu.edu/academics/course-catalog" in set(seeds["seed_url"])
    assert "https://www.leeuniversity.edu/publications/catalog-archives" in set(seeds["seed_url"])


def test_archive_expansion_seed_priority_promotes_generated_catalog_archives():
    assert (
        bench.archive_expansion_seed_priority(
            "generated_current_site_catalog_page",
            "publications/catalog-archives",
            "https://www.leeuniversity.edu/publications/catalog-archives",
        )
        == 1
    )


def test_archive_expansion_seed_priority_prioritizes_registrar_archive_seed():
    assert (
        bench.archive_expansion_seed_priority(
            "generated_current_site_catalog_page",
            "archive",
            "https://registrar.fsu.edu/archive",
        )
        == 0
    )


def test_archive_expansion_seed_priority_keeps_digitalcollections_before_catalog_lists():
    assert (
        bench.archive_expansion_seed_priority(
            "generated_repository_root",
            "generated_repository_digitalcollections_subdomain",
            "https://digitalcollections.example.edu/",
        )
        < bench.archive_expansion_seed_priority(
            "first_pass_archive_page",
            "acalog_catalog_list",
            "https://catalog.example.edu/misc/catalog_list.php?catoid=1",
        )
    )


def test_materialize_inferred_year_url_candidates_expands_verified_multi_year_urls(monkeypatch):
    def fake_retrieve_url(url, *, timeout_seconds, max_bytes):
        return {
            "retrieval_status": "retrieved",
            "http_status": 200,
            "page_title": "Undergraduate Catalog",
        }

    monkeypatch.setattr(bench, "retrieve_url", fake_retrieve_url)
    seeds = pd.DataFrame(
        [
            {
                "unitid": 1,
                "institution_name": "Example University",
                "target_year": 2002,
                "candidate_url": "http://coursecatalog.example.edu/previous/0204_catalog.pdf",
                "candidate_link_text": "Inferred 2002-2004 catalog URL",
                "candidate_evidence_text": "Template source",
                "archive_url": "http://coursecatalog.example.edu/previous/",
            }
        ]
    )

    candidates = bench.materialize_inferred_year_url_candidates(seeds, timeout_seconds=1, max_workers=1)

    assert candidates["target_year"].tolist() == [2002, 2003]
    assert candidates["catalog_year_start"].tolist() == [2002, 2002]
    assert candidates["catalog_year_end"].tolist() == [2004, 2004]


def test_materialize_inferred_year_url_candidates_uses_filename_before_upload_folder_year(monkeypatch):
    def fake_retrieve_url(url, *, timeout_seconds, max_bytes):
        return {
            "retrieval_status": "retrieved_truncated",
            "http_status": 200,
            "content_type": "application/pdf",
            "page_title": "hiram college catalog 2004 2005.pdf",
            "body": b"%PDF",
        }

    monkeypatch.setattr(bench, "retrieve_url", fake_retrieve_url)
    seeds = pd.DataFrame(
        [
            {
                "unitid": 203128,
                "institution_name": "Hiram College",
                "target_year": 2005,
                "candidate_url": "https://www.hiram.edu/wp-content/uploads/2022/07/hiram-college-catalog-2004-2005.pdf",
                "candidate_link_text": "Generated official-domain catalog PDF probe",
                "candidate_evidence_text": "Template source",
                "archive_url": "www.hiram.edu/",
            }
        ]
    )

    candidates = bench.materialize_inferred_year_url_candidates(seeds, timeout_seconds=1, max_workers=1)

    assert candidates["target_year"].tolist() == [2005]
    assert candidates["catalog_year_start"].tolist() == [2004]
    assert candidates["catalog_year_end"].tolist() == [2005]


def test_materialize_inferred_year_url_candidates_rejects_placeholder_html(monkeypatch):
    def fake_retrieve_url(url, *, timeout_seconds, max_bytes):
        return {
            "retrieval_status": "retrieved",
            "http_status": 200,
            "content_type": "text/html; charset=UTF-8",
            "page_title": "F&M Page Not Found",
            "body": b"<html><title>F&M Page Not Found</title></html>",
        }

    monkeypatch.setattr(bench, "retrieve_url", fake_retrieve_url)
    seeds = pd.DataFrame(
        [
            {
                "unitid": 1,
                "institution_name": "Franklin and Marshall College",
                "target_year": 2006,
                "candidate_url": "https://www.fandm.edu/PDFFiles/Academic%20Affairs/2006-07-catalog.pdf",
                "candidate_link_text": "Inferred 2006-2007 catalog URL",
                "candidate_evidence_text": "Template source",
                "archive_url": "https://www.fandm.edu/",
            }
        ]
    )

    candidates = bench.materialize_inferred_year_url_candidates(seeds, timeout_seconds=1, max_workers=1)

    assert candidates.empty
