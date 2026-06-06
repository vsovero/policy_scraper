import pandas as pd

from course_policy.batch3_discovery import (
    add_legacy_gap_status,
    bepress_gallery_context_records,
    build_inventory,
    build_legacy_gap_candidates,
    build_observed_candidate_bounds,
    build_stage_status,
    build_year_coverage,
    is_relevant_catalog_link,
    is_policy_page_lead,
    select_batch3_institutions,
    select_option_context_records,
    stage_for_row,
    table_row_context_records,
)


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
