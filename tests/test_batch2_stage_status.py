import pandas as pd

from course_policy.batch2_stage_status import build_stage_status, stage_for_row


def test_stage_for_retrieved_source_goes_to_policy_search():
    row = pd.Series({"has_preferred_root_retrieved": True, "has_legacy_gap_retrieved": False})

    assert stage_for_row(row)[:3] == ("source_retrieved", "policy_terms_not_searched", "policy_term_search")


def test_stage_for_secondary_candidate_goes_to_retrieval_recovery():
    row = pd.Series(
        {
            "has_preferred_root_retrieved": False,
            "has_legacy_gap_retrieved": False,
            "has_secondary_archive_candidate": True,
        }
    )

    assert stage_for_row(row)[:3] == ("candidate_identified", "body_access_blocked", "retrieval_recovery")


def test_stage_for_secondary_candidate_takes_precedence_over_legacy_challenge_page():
    row = pd.Series(
        {
            "has_preferred_root_retrieved": False,
            "has_legacy_gap_retrieved": True,
            "has_secondary_archive_candidate": True,
        }
    )

    assert stage_for_row(row)[:3] == ("candidate_identified", "body_access_blocked", "retrieval_recovery")


def test_stage_for_archive_bound():
    row = pd.Series(
        {
            "unitid": 220075,
            "target_year": 2005,
            "has_preferred_root_retrieved": False,
            "has_legacy_gap_retrieved": False,
            "has_secondary_archive_candidate": False,
        }
    )

    assert stage_for_row(row)[:3] == ("root_identified", "archive_bound", "defer_archive_bound")


def test_build_stage_status_prefers_secondary_candidate_for_unretrieved_year():
    run_summary = pd.DataFrame(
        [
            {
                "batch2_rank": 1,
                "unitid": 127741,
                "institution_name": "University of Northern Colorado",
                "target_year": 2000,
                "has_root_archive_candidate": False,
                "has_legacy_gap_fill_candidate": False,
            }
        ]
    )
    retrieval = pd.DataFrame()
    secondary = pd.DataFrame(
        [
            {
                "unitid": 127741,
                "target_year": 2000,
                "candidate_url": "https://digarch.unco.edu/node/49720",
                "candidate_title": "2000-2001 undergraduate catalog",
                "secondary_source_root_name": "Catalogs 2000-2009",
                "secondary_source_set_spec": "node:11204",
                "catalog_body_access_status": "blocked_or_challenge_page",
                "catalog_body_retrieval_status": "retrieved",
                "catalog_body_content_type": "text/html",
            }
        ]
    )
    secondary_summary = pd.DataFrame(
        [{"unitid": 127741, "target_year": 2000, "has_secondary_archive_candidate": True}]
    )
    year_coverage = pd.DataFrame(
        [
            {
                "unitid": 127741,
                "target_year": 2000,
                "candidate_url": "",
                "candidate_link_text": "",
                "archive_url": "",
                "catalog_year_start": "",
                "catalog_year_end": "",
            }
        ]
    )

    status = build_stage_status(run_summary, retrieval, secondary, secondary_summary, year_coverage)

    assert status["pipeline_stage"].iloc[0] == "candidate_identified"
    assert status["next_batch_action"].iloc[0] == "retrieval_recovery"
