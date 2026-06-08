import pandas as pd

from course_policy.phase3_review_packet import build_source_roots, build_start_here, build_year_panel_review


def test_build_start_here_records_audit_gate_counts():
    audit = pd.DataFrame(
        [
            {"audit_status": "pass_basic_checks"},
            {"audit_status": "needs_pipeline_fix"},
            {"audit_status": "accepted_dead_end_or_archive_bound"},
        ]
    )
    spotcheck = pd.DataFrame(
        [
            {"unitid": 1},
            {"unitid": 1},
            {"unitid": 2},
        ]
    )

    start_here = build_start_here(audit, spotcheck)
    lookup = dict(zip(start_here["item"], start_here["detail"]))

    assert lookup["Institutions"] == 2
    assert lookup["Institution-year rows"] == 3
    assert lookup["needs_pipeline_fix"] == 1


def test_build_year_panel_review_keeps_compact_review_columns():
    spotcheck = pd.DataFrame(
        [
            {
                "unitid": 1,
                "institution_name": "Example U",
                "start_year": 2000,
                "best_url": "https://example.edu/catalog",
                "legacy_url": "",
                "best_url_source": "reviewed_root_archive",
                "extra_debug_column": "debug",
            }
        ]
    )

    panel = build_year_panel_review(spotcheck)

    assert "extra_debug_column" not in panel.columns
    assert list(panel[["unitid", "institution_name", "start_year"]].iloc[0]) == [1, "Example U", 2000]


def test_build_source_roots_fills_missing_names_from_audit():
    manual = pd.DataFrame(
        [
            {
                "unitid": 1,
                "institution_name": "",
                "manual_status": "reviewed",
                "manual_best_root_url": "https://example.edu/archive",
            }
        ]
    )
    audit = pd.DataFrame([{"unitid": 1, "institution_name": "Example University"}])
    spotcheck = pd.DataFrame([{"unitid": 1, "institution_name": "Example University", "start_year": 2000}])

    roots = build_source_roots(manual, audit, spotcheck)

    assert roots.loc[0, "institution_name"] == "Example University"


def test_build_source_roots_appends_automated_batch_roots():
    manual = pd.DataFrame(
        columns=[
            "unitid",
            "institution_name",
            "manual_status",
            "manual_best_root_url",
        ]
    )
    audit = pd.DataFrame([{"unitid": 2, "institution_name": "Automated State"}])
    spotcheck = pd.DataFrame(
        [
            {
                "unitid": 2,
                "institution_name": "Automated State",
                "preferred_source_root_url": "https://catalog.automated.edu/",
                "legacy_url": "https://catalog.automated.edu/2000",
                "comments": "Root identified by batch discovery.",
                "next_batch_action": "source_root_discovery",
            }
        ]
    )

    roots = build_source_roots(manual, audit, spotcheck)

    assert roots.loc[0, "manual_status"] == "automated_batch_root_discovery"
    assert roots.loc[0, "manual_best_root_url"] == "https://catalog.automated.edu/"
