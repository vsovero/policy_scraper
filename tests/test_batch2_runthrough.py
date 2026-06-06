import pandas as pd

from course_policy.batch2_runthrough import build_combined_inventory, build_year_summary


def test_combined_inventory_adds_legacy_gap_fill_only_for_missing_years():
    candidates = pd.DataFrame(
        [
            {
                "batch2_rank": 1,
                "unitid": 1,
                "institution_name": "Example U",
                "target_year": 2001,
                "candidate_url": "https://example.edu/2001.pdf",
                "candidate_link_text": "2001-2002 Undergraduate Catalog",
                "catalog_year_start": 2001,
                "catalog_year_end": 2002,
                "archive_url": "https://example.edu/archive",
                "candidate_priority": 10,
            }
        ]
    )
    coverage = pd.DataFrame(
        [
            {"unitid": 1, "target_year": 2000, "candidate_status": "no_explicit_year_candidate_from_root"},
            {"unitid": 1, "target_year": 2001, "candidate_status": "explicit_year_candidate_found"},
        ]
    )
    legacy = pd.DataFrame(
        [
            {
                "batch2_rank": 1,
                "unitid": 1,
                "institution_name": "Example U",
                "target_year": 2000,
                "legacy_url": "https://legacy.example.edu/2000",
                "legacy_url_parent": "https://legacy.example.edu/",
                "legacy_link_id": 7,
                "selected_as_prior_evidence": True,
                "legacy_needs_review": False,
                "legacy_review_reasons": "",
            },
            {
                "batch2_rank": 1,
                "unitid": 1,
                "institution_name": "Example U",
                "target_year": 2001,
                "legacy_url": "https://legacy.example.edu/2001",
                "legacy_url_parent": "https://legacy.example.edu/",
                "legacy_link_id": 8,
                "selected_as_prior_evidence": True,
                "legacy_needs_review": False,
                "legacy_review_reasons": "",
            },
        ]
    )

    inventory = build_combined_inventory(candidates, coverage, legacy)

    assert len(inventory) == 2
    assert inventory["candidate_source_method"].tolist().count("legacy_gap_fill_outside_root_span") == 1


def test_combined_inventory_keeps_one_root_candidate_per_year():
    candidates = pd.DataFrame(
        [
            {
                "batch2_rank": 1,
                "unitid": 1,
                "institution_name": "Example U",
                "target_year": 2001,
                "candidate_url": "https://example.edu/2001-page",
                "candidate_link_text": "2001-2002",
                "catalog_year_start": 2001,
                "catalog_year_end": 2002,
                "archive_url": "https://example.edu/archive",
                "candidate_priority": 30,
            },
            {
                "batch2_rank": 1,
                "unitid": 1,
                "institution_name": "Example U",
                "target_year": 2001,
                "candidate_url": "https://example.edu/2001.pdf",
                "candidate_link_text": "2001-2002 Undergraduate Catalog",
                "catalog_year_start": 2001,
                "catalog_year_end": 2002,
                "archive_url": "https://example.edu/archive",
                "candidate_priority": 10,
            },
        ]
    )
    coverage = pd.DataFrame(
        [{"unitid": 1, "target_year": 2001, "candidate_status": "explicit_year_candidate_found"}]
    )
    legacy = pd.DataFrame(
        columns=[
            "batch2_rank",
            "unitid",
            "institution_name",
            "target_year",
            "legacy_url",
            "legacy_url_parent",
            "legacy_link_id",
            "selected_as_prior_evidence",
            "legacy_needs_review",
            "legacy_review_reasons",
        ]
    )

    inventory = build_combined_inventory(candidates, coverage, legacy)

    assert len(inventory) == 1
    assert inventory["candidate_url"].iloc[0] == "https://example.edu/2001.pdf"


def test_year_summary_classifies_root_legacy_and_missing():
    coverage = pd.DataFrame(
        [
            {"batch2_rank": 1, "unitid": 1, "institution_name": "Example U", "target_year": 2000, "candidate_url": ""},
            {
                "batch2_rank": 1,
                "unitid": 1,
                "institution_name": "Example U",
                "target_year": 2001,
                "candidate_url": "https://example.edu/2001.pdf",
            },
            {"batch2_rank": 1, "unitid": 1, "institution_name": "Example U", "target_year": 2002, "candidate_url": ""},
        ]
    )
    retrieval = pd.DataFrame(
        [
            {
                "unitid": 1,
                "target_year": 2000,
                "candidate_source_method": "legacy_gap_fill_outside_root_span",
                "source_retrieved": True,
            },
            {
                "unitid": 1,
                "target_year": 2001,
                "candidate_source_method": "preferred_root_archive",
                "source_retrieved": True,
            },
        ]
    )

    summary = build_year_summary(coverage, retrieval)

    statuses = dict(zip(summary["target_year"], summary["batch2_year_status"]))
    assert statuses[2000] == "legacy_gap_fill_candidate"
    assert statuses[2001] == "root_candidate"
    assert statuses[2002] == "missing_after_root_and_legacy"
    assert summary.loc[summary["target_year"].eq(2000), "has_any_catalog_candidate"].iloc[0]
