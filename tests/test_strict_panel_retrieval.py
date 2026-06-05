import pandas as pd

from course_policy.strict_panel_retrieval import (
    build_ready_inventory,
    combine_strict_retrieval,
    enrich_missing_year_reasons,
)


def test_build_ready_inventory_uses_only_ready_candidates():
    institutions = pd.DataFrame(
        [{"unitid": 1, "strict_pilot_rank": 2, "strict_pilot_reason": "test"}]
    )
    candidates = pd.DataFrame(
        [
            candidate_row("ready-1", "ready_for_retrieval"),
            candidate_row("review-1", "review_before_retrieval"),
        ]
    )

    inventory = build_ready_inventory(institutions, candidates)

    assert inventory["source_id"].tolist() == ["ready-1"]
    assert inventory.loc[0, "target_year"] == 2004
    assert inventory.loc[0, "pilot_rank"] == 2
    assert not inventory.loc[0, "needs_human_review"]


def test_combine_strict_retrieval_preserves_existing_and_panel_rows():
    existing = pd.DataFrame(
        [
            {"unitid": 1, "target_year": 2000, "source_id": "strict-1"},
        ]
    )
    panel = pd.DataFrame(
        [
            {"unitid": 1, "target_year": 2001, "source_id": "panel-1"},
        ]
    )

    combined = combine_strict_retrieval(existing, panel)

    assert combined["source_id"].tolist() == ["strict-1", "panel-1"]


def test_enrich_missing_year_reasons_uses_panel_status():
    year_coverage = pd.DataFrame(
        [
            {
                "unitid": 1,
                "target_year": 2017,
                "has_strict_catalog_source": False,
                "review_reason": "generic",
            },
            {
                "unitid": 1,
                "target_year": 2018,
                "has_strict_catalog_source": True,
                "review_reason": "",
            },
        ]
    )
    panel_status = pd.DataFrame(
        [
            {
                "unitid": 1,
                "target_year": 2017,
                "candidate_status": "official_archive_limit_reached",
                "candidate_title": "",
                "candidate_review_reason": "Archive only yielded AY 2000-2016 candidates.",
            }
        ]
    )

    enriched = enrich_missing_year_reasons(year_coverage, panel_status)

    assert "official_archive_limit_reached" in enriched.loc[0, "review_reason"]
    assert enriched.loc[1, "review_reason"] == ""


def candidate_row(source_id, status):
    return {
        "source_id": source_id,
        "unitid": 1,
        "institution_name": "Example U",
        "candidate_url": f"https://example.edu/{source_id}",
        "source_title": "Example Catalog 2004-2005",
        "catalog_year_start": 2004,
        "catalog_year_end": 2005,
        "discovery_method": "archive",
        "source_kind": "undergraduate_catalog",
        "source_status": status,
        "archive_page_url": "https://example.edu/archive",
    }
