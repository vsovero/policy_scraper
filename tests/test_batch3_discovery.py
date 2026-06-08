import pandas as pd

from course_policy.batch2_root_check import candidate_urls_for_task, legacy_derived_collection_roots
from course_policy.batch2_year_candidates import candidate_archive_urls
from course_policy.batch2_year_candidates import normalized_year_range
from course_policy.batch3_discovery import (
    add_legacy_gap_status,
    bepress_gallery_context_records,
    build_inventory,
    build_legacy_gap_candidates,
    build_observed_candidate_bounds,
    build_year_candidates,
    contextual_link_records,
    build_stage_status,
    contentdm_api_context_records,
    build_year_coverage,
    heading_section_context_records,
    is_relevant_catalog_link,
    is_policy_page_lead,
    nearby_year_context_records,
    normalize_candidate_url,
    select_batch3_institutions,
    select_option_context_records,
    stage_for_row,
    table_row_context_records,
)


def test_legacy_derived_collection_roots_uses_bepress_context_query():
    roots = legacy_derived_collection_roots(
        "https://scholarworks.example.edu/cgi/viewcontent.cgi?article=1065&context=catalogs"
    )

    assert {
        "candidate_url": "https://scholarworks.example.edu/catalogs/",
        "candidate_source_type": "legacy_derived_repository_collection",
    } in roots


def test_legacy_derived_collection_roots_uses_digital_collection_path():
    roots = legacy_derived_collection_roots("https://dmr.example.edu/digital/collection/BSUCoursCat/id/33307/rec/17")

    assert {
        "candidate_url": "https://dmr.example.edu/digital/collection/BSUCoursCat/",
        "candidate_source_type": "legacy_derived_repository_collection",
    } in roots


def test_contentdm_collection_root_adds_api_archive_url():
    archives = candidate_archive_urls({}, "https://dmr.example.edu/digital/collection/BSUCoursCat/")

    assert {
        "archive_url": "https://dmr.example.edu/digital/api/search/collection/BSUCoursCat/searchterm/catalog/field/title/maxRecords/250",
        "archive_source": "contentdm_collection_api",
        "archive_link_text": "CONTENTdm collection API catalog title search",
    } in archives


def test_catalog_subdomain_root_adds_common_resource_archive_paths():
    archives = candidate_archive_urls({}, "https://catalog.example.edu/")

    assert {
        "archive_url": "https://catalog.example.edu/resources/catalog-archives/",
        "archive_source": "generated_catalog_resource_archive_path",
        "archive_link_text": "resources/catalog-archives/",
    } in archives


def test_candidate_archive_urls_follows_repository_pagination_links():
    archives = candidate_archive_urls(
        {
            "link_records": [
                {
                    "url": "https://scholarworks.example.edu/catalogs/index.2.html",
                    "text": "Next",
                }
            ]
        },
        "https://scholarworks.example.edu/catalogs/",
    )

    assert {
        "archive_url": "https://scholarworks.example.edu/catalogs/index.2.html",
        "archive_source": "archive_pagination_link",
        "archive_link_text": "Next",
    } in archives


def test_candidate_urls_include_catalogarchive_and_legacy_archive_parent():
    task = pd.Series({"unitid": 1, "webaddr": "www.jsu.edu/"})
    leads = pd.DataFrame(
        [
            {
                "unitid": 1,
                "legacy_url": "http://www.jsu.edu/catalogarchive/pdf/jsucatalogue04-05.pdf",
                "legacy_url_parent": "http://www.jsu.edu/catalogarchive/pdf/",
            }
        ]
    )

    urls = candidate_urls_for_task(task, leads)

    assert {
        "candidate_url": "https://www.jsu.edu/catalogarchive/",
        "candidate_source_type": "generated_catalog_archive_path",
    } in urls
    assert {
        "candidate_url": "http://www.jsu.edu/catalogarchive/",
        "candidate_source_type": "legacy_derived_archive_root",
    } in urls


def test_contentdm_api_context_records_builds_item_links_from_titles():
    records = contentdm_api_context_records(
        b"""
        {
          "items": [
            {
              "title": "2011-2012 Ball State University course catalog",
              "itemLink": "/compoundobject/collection/BSUCoursCat/id/23132"
            },
            {
              "title": "2011-2012 Ball State University graduate course catalog",
              "itemLink": "/compoundobject/collection/BSUCoursCat/id/23516"
            }
          ]
        }
        """,
        "https://dmr.example.edu/digital/api/search/collection/BSUCoursCat/searchterm/catalog/field/title/maxRecords/250",
    )

    assert records[0] == {
        "url": "https://dmr.example.edu/compoundobject/collection/BSUCoursCat/id/23132",
        "text": "2011-2012 Ball State University course catalog",
        "evidence_text": "2011-2012 Ball State University course catalog",
        "evidence_source": "contentdm_api_context",
    }
    assert is_relevant_catalog_link(records[0])
    assert not is_relevant_catalog_link(records[1])


def test_select_batch3_excludes_strict_and_batch2_unitids():
    pilot = pd.DataFrame(
        [
            {"pilot_rank": 1, "unitid": 122597, "institution_name": "SFSU"},
            {"pilot_rank": 2, "unitid": 139940, "institution_name": "GSU"},
            {"pilot_rank": 3, "unitid": 213349, "institution_name": "Kutztown"},
            {"pilot_rank": 4, "unitid": 185828, "institution_name": "NJIT"},
        ]
    )
    batch2 = pd.DataFrame([{"unitid": 139940}])

    selected = select_batch3_institutions(pilot, batch2, batch_size=2)

    assert selected["unitid"].tolist() == [213349, 185828]
    assert selected["batch3_rank"].tolist() == [1, 2]


def test_batch3_relevant_catalog_link_is_generic_and_undergraduate_first():
    assert is_relevant_catalog_link(
        {"text": "2015-2016 Undergraduate Catalog", "url": "https://example.edu/catalog/2015-2016"}
    )
    assert is_relevant_catalog_link(
        {
            "text": "2015-2016 Undergraduate and Graduate Catalog",
            "url": "https://example.edu/catalog/2015-2016",
        }
    )
    assert is_relevant_catalog_link(
        {"text": "2015-2016 University Catalog", "url": "https://example.edu/catalog/2015-2016"}
    )
    assert not is_relevant_catalog_link(
        {"text": "2015-2016 Graduate Catalog", "url": "https://example.edu/catalog/2015-2016"}
    )
    assert not is_relevant_catalog_link(
        {"text": "2015-2016 Course Schedule", "url": "https://example.edu/schedule/2015-2016"}
    )
    assert not is_relevant_catalog_link(
        {"text": "PDF", "url": "https://example.edu/2015-2016Undergraduate.pdf"}
    )
    assert not is_relevant_catalog_link(
        {"text": "2015-2017", "url": "https://example.edu/archive/GR15-17/15-17GradCatalog.pdf"}
    )


def test_wcsu_ugrad_archive_menu_links_are_undergraduate_context():
    assert is_relevant_catalog_link(
        {
            "text": "2018-2019",
            "url": "https://catalogs.wcsu.edu/ugrad21221920/",
            "evidence_text": "2018-2019 WCSU Undergraduate Catalog 2021-2022",
        }
    )
    assert normalize_candidate_url(
        "https://catalogs.wcsu.edu/ugrad21221920/",
        "2018-2019 WCSU Undergraduate Catalog 2021-2022",
    ) == "https://catalogs.wcsu.edu/ugrad1819/"


def test_obvious_22xx_catalog_year_typo_is_normalized():
    assert normalized_year_range("2208-2009 Southern Illinois University Undergraduate Catalog") == (2008, 2009)


def test_table_row_context_uses_visible_row_year_without_url_year_inference():
    records = table_row_context_records(
        """
        <table><tr>
          <td>2003-2004</td>
          <td><a href="2003-2004Graduate.pdf">PDF</a></td>
          <td><a href="2003-2004Undergraduate.pdf">PDF</a></td>
        </tr></table>
        """,
        "https://archive.example.edu/",
    )

    undergraduate = [record for record in records if "Undergraduate" in record["evidence_text"]]

    assert undergraduate
    assert is_relevant_catalog_link(undergraduate[0])


def test_select_option_context_builds_acalog_catalog_urls():
    records = select_option_context_records(
        """
        <select name="catalog">
          <option value="50">2020-2021 Catalog [ARCHIVED CATALOG]</option>
          <option value="59">2002-2026 Senate Policy Catalog</option>
        </select>
        """,
        "https://catalog.example.edu/",
    )

    assert records[0]["url"] == "https://catalog.example.edu/index.php?catoid=50"
    assert is_relevant_catalog_link(records[0])
    assert not is_relevant_catalog_link(records[1])


def test_bepress_gallery_context_builds_download_url_from_visible_title_and_asset_id():
    records = bepress_gallery_context_records(
        """
        <ul id="gallery_items">
          <li><div class="content_block">
            <a href="https://louis.example.edu/catalogs/44" class="cover">
              <img src="https://louis.example.edu/catalogs/1043/thumbnail.jpg"
                   alt="2013-2014 Undergraduate Catalog">
            </a>
            <h2><a href="https://louis.example.edu/catalogs/44">2013-2014 Undergraduate Catalog</a></h2>
          </div></li>
        </ul>
        """,
        "https://louis.example.edu/catalogs/",
    )

    assert records == [
        {
            "url": "https://louis.example.edu/cgi/viewcontent.cgi?article=1043&context=catalogs",
            "text": "2013-2014 Undergraduate Catalog",
            "evidence_text": "2013-2014 Undergraduate Catalog",
            "evidence_source": "bepress_gallery_context",
        }
    ]
    assert is_relevant_catalog_link(records[0])


def test_bepress_slideshow_context_builds_download_url_from_preview_title():
    records = bepress_gallery_context_records(
        """
        <div class="gallery-tools">
          <a href="https://louis.example.edu/catalogs/1008/preview.jpg"
             class="floatbox"
             title="1999-2001 Undergraduate Catalog"></a>
        </div>
        """,
        "https://louis.example.edu/catalogs/",
    )

    assert records == [
        {
            "url": "https://louis.example.edu/cgi/viewcontent.cgi?article=1008&context=catalogs",
            "text": "1999-2001 Undergraduate Catalog",
            "evidence_text": "1999-2001 Undergraduate Catalog",
            "evidence_source": "bepress_slideshow_context",
        }
    ]
    assert is_relevant_catalog_link(records[0])


def test_bepress_slideshow_context_uses_collection_context_from_url():
    records = bepress_gallery_context_records(
        """
        <div class="gallery-tools">
          <a href="https://scholarworks.example.edu/csusb-catalog/1004/preview.jpg"
             class="floatbox"
             title="Course Catalog 2000-2001"></a>
        </div>
        """,
        "https://scholarworks.example.edu/csusb-catalog/",
    )

    assert records == [
        {
            "url": "https://scholarworks.example.edu/cgi/viewcontent.cgi?article=1004&context=csusb-catalog",
            "text": "Course Catalog 2000-2001",
            "evidence_text": "Course Catalog 2000-2001",
            "evidence_source": "bepress_slideshow_context",
        }
    ]
    assert is_relevant_catalog_link(records[0])


def test_nearby_year_context_uses_visible_year_before_generic_archive_links():
    records = nearby_year_context_records(
        """
        <p>2019-2020:
          <a href="/archive/2019/index.html">Website</a> |
          <a href="/wp-content/uploads/2019-2020_Catalog.epub">ePub</a>
        </p>
        <p>2008-2010:
          <a href="https://cso.collegesource.com/example">CollegeSource</a>
        </p>
        """,
        "https://catalog.example.edu/resources/catalog-archives/",
    )

    assert {
        "url": "https://catalog.example.edu/archive/2019/index.html",
        "text": "Website",
        "evidence_text": "2019-2020: Website",
        "source_context": "https://catalog.example.edu/resources/catalog-archives/",
        "evidence_source": "nearby_year_context",
    } in records
    assert {
        "url": "https://cso.collegesource.com/example",
        "text": "CollegeSource",
        "evidence_text": "2008-2010: CollegeSource",
        "source_context": "https://catalog.example.edu/resources/catalog-archives/",
        "evidence_source": "nearby_year_context",
    } in records


def test_heading_section_context_keeps_undergraduate_and_graduate_year_links_separate():
    records = heading_section_context_records(
        """
        <h4>Graduate Edition</h4>
        <a href="/grad-2007-2009.pdf">2007-2009</a>
        <h4>Undergraduate Edition</h4>
        <a href="/ug-2007-2008.pdf">2007-2008</a>
        """,
        "https://registrar.example.edu/archive",
        "Archive",
    )

    graduate = [record for record in records if "Graduate Edition" in record["evidence_text"]][0]
    undergraduate = [record for record in records if "Undergraduate Edition" in record["evidence_text"]][0]
    assert not is_relevant_catalog_link(graduate)
    assert is_relevant_catalog_link(undergraduate)


def test_table_row_context_uses_link_year_when_row_has_multiple_year_links():
    records = table_row_context_records(
        """
        <tr>
          <td><a href="/2009.pdf">2009-2010</a></td>
          <td><a href="/2008.pdf">2008-2009</a></td>
          <td><a href="/2007.pdf">2007-2008</a></td>
        </tr>
        """,
        "https://registrar.example.edu/archive",
    )

    hit = [record for record in records if record["url"].endswith("/2007.pdf")][0]
    assert hit["evidence_text"] == "2007-2008"


def test_normalize_candidate_url_repairs_wcsu_archived_catalog_relative_paths():
    assert (
        normalize_candidate_url("http://catalogs.wcsu.edu/ugrad21221012/files/catalog.pdf")
        == "http://catalogs.wcsu.edu/ugrad1012/files/catalog.pdf"
    )


def test_normalize_candidate_url_repairs_asu_general_catalog_graduate_suffix():
    assert (
        normalize_candidate_url(
            "https://catalog.asu.edu/archive/academic-catalog-archive-2005-2006-graduate",
            "2005-2006 General Catalog PDF",
        )
        == "https://catalog.asu.edu/archive/academic-catalog-archive-2005-2006"
    )


def test_catalog_archive_page_title_supplies_context_for_year_only_links():
    result = {
        "content_type": "text/html",
        "body": b'<a href="pdf/jsucatalog18-19.pdf">2018-2019</a>',
        "link_records": [{"url": "https://www.example.edu/catalogarchive/pdf/jsucatalog18-19.pdf", "text": "2018-2019"}],
    }
    page = pd.Series({"archive_url": "https://www.example.edu/catalogarchive/", "page_title": "Catalog Archive"})

    records = contextual_link_records(result, page)
    archive_context = [record for record in records if record["evidence_source"] == "catalog_archive_page_title_context"]

    assert archive_context
    assert is_relevant_catalog_link(archive_context[0])


def test_graduate_link_is_rejected_even_on_undergraduate_archive_page():
    assert not is_relevant_catalog_link(
        {
            "text": "1999-2001",
            "url": "http://www.utsa.edu/ucat/archive/GR99-01/1999-2001GradCatalog.pdf",
            "evidence_text": "1999-2001 Graduate Catalog Previous Catalogs Undergraduate Catalog",
        }
    )


def test_general_and_graduate_catalog_is_treated_as_university_wide_catalog():
    assert is_relevant_catalog_link(
        {
            "url": "https://catalog.example.edu/archives/2020-2021/general_and_graduate",
            "text": "PDF",
            "evidence_text": "2020-2021 General and Graduate Catalog PDF",
            "evidence_source": "table_row_context",
        }
    )


def test_graduate_only_catalog_is_still_rejected():
    assert not is_relevant_catalog_link(
        {
            "url": "https://catalog.example.edu/archives/2020-2021/graduate",
            "text": "2020-2021 Graduate Catalog",
            "evidence_text": "2020-2021 Graduate Catalog",
            "evidence_source": "visible_link_text",
        }
    )


def test_observed_candidate_bounds_can_come_from_years_outside_target_panel():
    archive_pages = pd.DataFrame(
        [
            {
                "unitid": 1,
                "archive_url": "https://example.edu/archive",
                "retrieval_status": "retrieved",
                "page_title": "Undergraduate Course Catalog Archive",
            }
        ]
    )
    result_by_url = {
        "https://example.edu/archive": {
            "content_type": "text/html",
            "body": b'<a href="catalog-2023-2024.pdf">2023-2024</a>',
            "link_records": [{"url": "https://example.edu/catalog-2023-2024.pdf", "text": "2023-2024"}],
        }
    }

    bounds = build_observed_candidate_bounds(archive_pages, result_by_url)

    assert bounds.loc[0, "observed_candidate_start_year"] == 2023


def test_build_year_coverage_infers_archive_bound_only_after_observed_span():
    batch = pd.DataFrame(
        [
            {
                "batch3_rank": 1,
                "pilot_rank": 10,
                "unitid": 1,
                "institution_name": "Example U",
                "pilot_case_types": "clean",
            }
        ]
    )
    targets = pd.DataFrame(
        [
            {"unitid": 1, "institution_name": "Example U", "year": 2000},
            {"unitid": 1, "institution_name": "Example U", "year": 2001},
            {"unitid": 1, "institution_name": "Example U", "year": 2002},
            {"unitid": 1, "institution_name": "Example U", "year": 2003},
        ]
    )
    decisions = pd.DataFrame(
        [
            {
                "unitid": 1,
                "decision_status": "preferred_source_root_identified",
                "preferred_source_root_url": "https://example.edu/catalog/",
                "preferred_source_root_type": "generated_catalog_path",
            }
        ]
    )
    candidates = pd.DataFrame(
        [
            {
                "batch3_rank": 1,
                "unitid": 1,
                "institution_name": "Example U",
                "target_year": 2003,
                "candidate_url": "https://example.edu/catalog/2003-2004",
                "candidate_link_text": "2003-2004 Undergraduate Catalog",
                "archive_url": "https://example.edu/catalog/",
                "catalog_year_start": 2003,
                "catalog_year_end": 2004,
                "candidate_priority": 10,
            }
        ]
    )

    coverage = build_year_coverage(batch, targets, decisions, candidates, pd.DataFrame())

    assert coverage.loc[coverage["target_year"].eq(2000), "archive_bound_inferred"].iloc[0]
    assert not coverage.loc[coverage["target_year"].eq(2003), "archive_bound_inferred"].iloc[0]


def test_build_year_coverage_flags_single_missing_year_inside_archive_span():
    batch = pd.DataFrame(
        [
            {
                "batch3_rank": 1,
                "pilot_rank": 10,
                "unitid": 1,
                "institution_name": "Example U",
                "pilot_case_types": "clean",
            }
        ]
    )
    targets = pd.DataFrame(
        [
            {"unitid": 1, "institution_name": "Example U", "year": 2007},
            {"unitid": 1, "institution_name": "Example U", "year": 2008},
            {"unitid": 1, "institution_name": "Example U", "year": 2009},
            {"unitid": 1, "institution_name": "Example U", "year": 2010},
        ]
    )
    decisions = pd.DataFrame(
        [
            {
                "unitid": 1,
                "decision_status": "preferred_source_root_identified",
                "preferred_source_root_url": "https://example.edu/catalog/",
                "preferred_source_root_type": "official_archive",
            }
        ]
    )
    candidates = pd.DataFrame(
        [
            {
                "batch3_rank": 1,
                "unitid": 1,
                "institution_name": "Example U",
                "target_year": 2007,
                "candidate_url": "https://example.edu/catalog/2007-2009",
                "candidate_link_text": "2007-2009 Undergraduate Catalog",
                "archive_url": "https://example.edu/catalog/",
                "catalog_year_start": 2007,
                "catalog_year_end": 2009,
                "candidate_priority": 10,
            },
            {
                "batch3_rank": 1,
                "unitid": 1,
                "institution_name": "Example U",
                "target_year": 2008,
                "candidate_url": "https://example.edu/catalog/2007-2009",
                "candidate_link_text": "2007-2009 Undergraduate Catalog",
                "archive_url": "https://example.edu/catalog/",
                "catalog_year_start": 2007,
                "catalog_year_end": 2009,
                "candidate_priority": 10,
            },
            {
                "batch3_rank": 1,
                "unitid": 1,
                "institution_name": "Example U",
                "target_year": 2010,
                "candidate_url": "https://example.edu/catalog/2010-2011",
                "candidate_link_text": "2010-2011 Catalog",
                "archive_url": "https://example.edu/catalog/",
                "catalog_year_start": 2010,
                "catalog_year_end": 2011,
                "candidate_priority": 10,
            },
        ]
    )

    coverage = build_year_coverage(batch, targets, decisions, candidates, pd.DataFrame())
    gap = coverage.loc[coverage["target_year"].eq(2009)].iloc[0]

    assert gap["interior_archive_gap_inferred"]
    assert not gap["archive_bound_inferred"]


def test_nearby_context_uses_url_year_when_context_contains_many_years():
    archive_pages = pd.DataFrame(
        [
            {
                "batch3_rank": 1,
                "unitid": 1,
                "institution_name": "Example University",
                "archive_url": "https://catalog.example.edu/archive",
                "retrieval_status": "retrieved",
                "page_title": "Catalog Archive",
            }
        ]
    )
    result_by_url = {
        "https://catalog.example.edu/archive": {
            "content_type": "text/html",
            "body": b"""
                <p>2017-2018 General Catalog PDF
                2016-2017 General Catalog PDF
                2008-2009 General Catalog
                <a href="/archives/2008-2009/general_and_graduate">PDF</a></p>
            """,
            "link_records": [
                {
                    "url": "https://catalog.example.edu/archives/2008-2009/general_and_graduate",
                    "text": "PDF",
                },
                {
                    "url": "https://catalog.example.edu/archives/2008-2009/special-school",
                    "text": "PDF",
                }
            ],
        }
    }

    candidates = build_year_candidates(archive_pages, result_by_url)

    assert set(candidates["target_year"]) == {2008}
    assert candidates.sort_values("candidate_priority")["candidate_url"].iloc[0].endswith("/general_and_graduate")


def test_legacy_gap_candidates_only_fill_uncovered_years():
    coverage = pd.DataFrame(
        [
            {
                "batch3_rank": 1,
                "unitid": 1,
                "institution_name": "Example U",
                "target_year": 2000,
                "candidate_url": "",
            },
            {
                "batch3_rank": 1,
                "unitid": 1,
                "institution_name": "Example U",
                "target_year": 2001,
                "candidate_url": "https://example.edu/catalog/2001",
            },
        ]
    )
    legacy = pd.DataFrame(
        [
            {
                "batch3_rank": 1,
                "unitid": 1,
                "institution_name": "Example U",
                "target_year": 2000,
                "legacy_url": "https://legacy.example.edu/2000.pdf",
                "legacy_url_parent": "https://legacy.example.edu/",
                "legacy_link_id": "legacy-1",
                "selected_as_prior_evidence": True,
                "legacy_needs_review": False,
                "legacy_review_reasons": "",
            },
            {
                "batch3_rank": 1,
                "unitid": 1,
                "institution_name": "Example U",
                "target_year": 2001,
                "legacy_url": "https://legacy.example.edu/2001.pdf",
                "legacy_url_parent": "https://legacy.example.edu/",
                "legacy_link_id": "legacy-2",
                "selected_as_prior_evidence": True,
                "legacy_needs_review": False,
                "legacy_review_reasons": "",
            },
        ]
    )

    gap = build_legacy_gap_candidates(coverage, legacy)
    inventory = build_inventory(coverage, gap)

    assert gap["target_year"].tolist() == [2000]
    assert gap["candidate_source_method"].iloc[0] == "legacy_prior_gap_fill"
    assert inventory.loc[inventory["target_year"].eq(2000), "candidate_source_method"].iloc[0] == "legacy_prior_gap_fill"
    assert inventory.loc[inventory["target_year"].eq(2001), "candidate_source_method"].iloc[0] == "preferred_root_archive"


def test_policy_page_legacy_gap_leads_are_deferred_not_retrieved():
    coverage = pd.DataFrame(
        [
            {
                "batch3_rank": 1,
                "unitid": 1,
                "institution_name": "Example U",
                "target_year": 2017,
                "candidate_url": "",
            }
        ]
    )
    legacy = pd.DataFrame(
        [
            {
                "batch3_rank": 1,
                "unitid": 1,
                "institution_name": "Example U",
                "target_year": 2017,
                "legacy_url": "https://catalog.example.edu/archive/2017-2018/undergrad/policies/course-repeat-policy/",
                "legacy_url_parent": "https://catalog.example.edu/archive/2017-2018/undergrad/policies/",
                "legacy_link_id": "legacy-policy",
                "selected_as_prior_evidence": True,
                "legacy_needs_review": False,
                "legacy_review_reasons": "",
            }
        ]
    )

    gap = build_legacy_gap_candidates(coverage, legacy)
    updated = add_legacy_gap_status(coverage, gap)
    inventory = build_inventory(updated, gap)

    assert is_policy_page_lead(gap["candidate_url"].iloc[0])
    assert gap["candidate_source_method"].iloc[0] == "legacy_policy_page_deferred"
    assert updated["legacy_policy_page_url"].iloc[0] == gap["candidate_url"].iloc[0]
    assert inventory.empty


def test_stage_for_row_maps_pipeline_queue_cases():
    assert stage_for_row(pd.Series({"decision_status": "source_root_not_found"}))[:3] == (
        "no_source_path",
        "no_root_found",
        "source_root_discovery",
    )
    assert stage_for_row(
        pd.Series(
            {
                "decision_status": "source_root_not_found",
                "source_retrieved": True,
                "retrieved_candidate_url": "https://legacy.example.edu/catalog.pdf",
            }
        )
    )[:3] == ("source_retrieved", "policy_terms_not_searched", "policy_term_search")
    assert stage_for_row(
        pd.Series(
            {
                "decision_status": "source_root_not_found",
                "source_retrieved": False,
                "retrieved_candidate_url": "https://legacy.example.edu/catalog.pdf",
            }
        )
    )[:3] == ("candidate_identified", "source_not_retrieved", "retrieval_recovery")
    assert stage_for_row(
        pd.Series(
            {
                "decision_status": "preferred_source_root_identified",
                "legacy_policy_page_url": "https://catalog.example.edu/archive/policies/course-repeat-policy/",
            }
        )
    )[:3] == ("root_identified", "policy_dating_needed", "policy_dating_workflow")
    assert stage_for_row(
        pd.Series(
            {
                "decision_status": "preferred_source_root_identified",
                "candidate_url": "https://example.edu/catalog/2001-2002",
                "source_retrieved": False,
            }
        )
    )[:3] == ("candidate_identified", "source_not_retrieved", "retrieval_recovery")
    assert stage_for_row(
        pd.Series(
            {
                "decision_status": "preferred_source_root_identified",
                "candidate_url": "",
                "source_retrieved": float("nan"),
                "archive_bound_inferred": False,
                "interior_archive_gap_inferred": True,
                "interior_archive_gap_note": "Target AY falls inside observed archive candidate span.",
            }
        )
    )[:3] == ("root_identified", "interior_archive_gap", "targeted_archive_gap_search")
    assert stage_for_row(
        pd.Series(
            {
                "decision_status": "preferred_source_root_identified",
                "candidate_url": "",
                "source_retrieved": float("nan"),
                "archive_bound_inferred": False,
                "interior_archive_gap_inferred": False,
            }
        )
    )[:3] == ("root_identified", "no_candidate_found", "source_root_discovery")


def test_build_inventory_and_stage_status_keep_one_source_per_year():
    coverage = pd.DataFrame(
        [
            {
                "batch3_rank": 1,
                "unitid": 1,
                "institution_name": "Example U",
                "target_year": 2000,
                "decision_status": "preferred_source_root_identified",
                "candidate_url": "https://example.edu/catalog/2000-2001",
                "candidate_link_text": "2000-2001 Undergraduate Catalog",
                "archive_url": "https://example.edu/catalog/",
                "catalog_year_start": 2000,
                "catalog_year_end": 2001,
                "archive_bound_inferred": False,
                "archive_bound_note": "",
            }
        ]
    )
    inventory = build_inventory(coverage)
    retrieval = pd.DataFrame(
        [
            {
                "unitid": 1,
                "target_year": 2000,
                "source_id": "batch3-00001",
                "source_retrieved": True,
                "best_retrieval_status": "retrieved",
                "best_attempt_method": "direct",
                "best_content_type": "application/pdf",
                "local_source_path": "/tmp/catalog.pdf",
                "covers_target_year": True,
                "candidate_source_method": "legacy_prior_gap_fill",
                "candidate_url": "https://legacy.example.edu/catalog.pdf",
                "candidate_link_text": "legacy workbook URL",
                "archive_url": "https://legacy.example.edu/",
            }
        ]
    )

    status = build_stage_status(coverage, retrieval)

    assert inventory["source_id"].tolist() == ["batch3-00001"]
    assert status["pipeline_stage"].iloc[0] == "source_retrieved"
    assert status["next_batch_action"].iloc[0] == "policy_term_search"
    assert status["retrieved_candidate_method"].iloc[0] == "legacy_prior_gap_fill"


def test_build_inventory_accepts_source_prefix():
    coverage = pd.DataFrame(
        [
            {
                "batch3_rank": 1,
                "unitid": 1,
                "institution_name": "Example U",
                "target_year": 2000,
                "candidate_url": "https://example.edu/catalog/2000",
            }
        ]
    )

    inventory = build_inventory(coverage, source_prefix="batch4")

    assert inventory["source_id"].tolist() == ["batch4-00001"]
