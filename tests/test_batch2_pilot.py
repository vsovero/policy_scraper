import pandas as pd

from course_policy.batch2_pilot import (
    build_legacy_leads,
    build_source_root_tasks,
    build_year_status,
    parent_url,
    select_batch2_institutions,
)


def test_parent_url_returns_directory_for_pdf():
    assert parent_url("https://example.edu/catalogs/2004-2006.pdf") == "https://example.edu/catalogs/"


def test_select_batch2_excludes_strict_pilot_unitids():
    pilot = pd.DataFrame(
        [
            {"pilot_rank": 1, "unitid": 209490, "institution_name": "OHSU"},
            {"pilot_rank": 6, "unitid": 127741, "institution_name": "Northern Colorado"},
            {"pilot_rank": 7, "unitid": 126775, "institution_name": "Colorado Mesa"},
        ]
    )
    for col in ["state", "webaddr", "pilot_case_types"]:
        pilot[col] = ""
    for col in [
        "legacy_link_rows",
        "legacy_year_count",
        "legacy_url_count",
        "selected_clean_url_count",
        "missing_url_count",
        "needs_review_count",
    ]:
        pilot[col] = 0

    selected = select_batch2_institutions(pilot, batch_size=2)

    assert selected["unitid"].tolist() == [127741, 126775]
    assert selected["batch2_rank"].tolist() == [1, 2]


def test_batch2_year_status_marks_legacy_lead_years():
    batch = pd.DataFrame(
        [
            {
                "batch2_rank": 1,
                "unitid": 10,
                "institution_name": "Example U",
                "state": "EX",
                "webaddr": "example.edu",
                "pilot_case_types": "clean",
            }
        ]
    )
    links = pd.DataFrame(
        [
            {
                "unitid": 10,
                "institution_name": "Example U",
                "target_year": 2000,
                "legacy_workbook": "public",
                "legacy_link_id": 1,
                "legacy_url": "https://example.edu/catalogs/2000-2001.pdf",
            }
        ]
    )
    targets = pd.DataFrame(
        [
            {"unitid": 10, "institution_name": "Example U", "state": "EX", "year": 2000},
            {"unitid": 10, "institution_name": "Example U", "state": "EX", "year": 2001},
        ]
    )

    leads = build_legacy_leads(batch, links)
    tasks = build_source_root_tasks(batch, leads)
    status = build_year_status(batch, targets, leads)

    assert leads["institution_name"].iloc[0] == "Example U"
    assert leads["legacy_url_parent"].iloc[0] == "https://example.edu/catalogs/"
    assert tasks["task_status"].iloc[0] == "source_root_discovery_needed"
    assert status.loc[status["target_year"].eq(2000), "candidate_status"].iloc[0] == "legacy_lead_available"
    assert status.loc[status["target_year"].eq(2001), "candidate_status"].iloc[0] == (
        "source_root_discovery_needed"
    )
