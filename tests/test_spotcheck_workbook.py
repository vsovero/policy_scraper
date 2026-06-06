import pandas as pd

from course_policy.spotcheck_workbook import best_url_for_row


def test_best_url_prefers_archive_candidate_over_legacy_url():
    best_url, source, status, title = best_url_for_row(
        pd.Series(
            {
                "candidate_url": "https://archive.example.edu/2001-2002.pdf",
                "candidate_link_text": "2001-2002 Undergraduate Catalog",
                "legacy_url": "https://legacy.example.edu/policy",
                "retrieval_status": "retrieved",
            }
        )
    )

    assert best_url == "https://archive.example.edu/2001-2002.pdf"
    assert source == "preferred_or_secondary_archive_candidate"
    assert status == "retrieved"
    assert title == "2001-2002 Undergraduate Catalog"


def test_best_url_falls_back_to_legacy_when_no_current_candidate():
    best_url, source, status, title = best_url_for_row(
        pd.Series(
            {
                "candidate_url": "",
                "retrieved_candidate_url": "",
                "legacy_policy_page_url": "",
                "legacy_url": "https://legacy.example.edu/catalog.pdf",
            }
        )
    )

    assert best_url == "https://legacy.example.edu/catalog.pdf"
    assert source == "legacy_url_only"
    assert status == "not_checked_in_current_stage"
    assert title == ""
