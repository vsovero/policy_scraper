import pandas as pd

from course_policy.batch4_discovery import select_batch4_institutions


def test_select_batch4_excludes_prior_batches_and_requires_public_legacy_urls():
    universe = pd.DataFrame(
        [
            {
                "unitid": 1,
                "institution_name": "Already Strict",
                "sector": "public_4_year",
                "active_in_ipeds_panel": True,
                "source_in_legacy_public": True,
                "state": "AA",
                "webaddr": "strict.edu",
            },
            {
                "unitid": 2,
                "institution_name": "No URL U",
                "sector": "public_4_year",
                "active_in_ipeds_panel": True,
                "source_in_legacy_public": True,
                "state": "AA",
                "webaddr": "nourl.edu",
            },
            {
                "unitid": 3,
                "institution_name": "Next U",
                "sector": "public_4_year",
                "active_in_ipeds_panel": True,
                "source_in_legacy_public": True,
                "state": "AA",
                "webaddr": "next.edu",
            },
            {
                "unitid": 4,
                "institution_name": "Private U",
                "sector": "private_nonprofit_4_year",
                "active_in_ipeds_panel": True,
                "source_in_legacy_public": True,
                "state": "AA",
                "webaddr": "private.edu",
            },
        ]
    )
    links = pd.DataFrame(
        [
            {
                "unitid": 1,
                "legacy_workbook": "public",
                "legacy_link_id": "l1",
                "target_year": 2000,
                "legacy_url": "https://strict.edu/catalog.pdf",
                "selected_as_prior_evidence": True,
                "missing_bulletin_url": False,
                "legacy_needs_review": False,
            },
            {
                "unitid": 2,
                "legacy_workbook": "public",
                "legacy_link_id": "l2",
                "target_year": 2000,
                "legacy_url": "",
                "selected_as_prior_evidence": True,
                "missing_bulletin_url": True,
                "legacy_needs_review": True,
            },
            {
                "unitid": 3,
                "legacy_workbook": "public",
                "legacy_link_id": "l3",
                "target_year": 2000,
                "legacy_url": "https://next.edu/catalog.pdf",
                "selected_as_prior_evidence": True,
                "missing_bulletin_url": False,
                "legacy_needs_review": False,
            },
            {
                "unitid": 4,
                "legacy_workbook": "public",
                "legacy_link_id": "l4",
                "target_year": 2000,
                "legacy_url": "https://private.edu/catalog.pdf",
                "selected_as_prior_evidence": True,
                "missing_bulletin_url": False,
                "legacy_needs_review": False,
            },
        ]
    )

    selected = select_batch4_institutions(
        universe,
        links,
        strict=pd.DataFrame([{"unitid": 1}]),
        batch2=pd.DataFrame(columns=["unitid"]),
        batch3=pd.DataFrame(columns=["unitid"]),
        batch_size=10,
    )

    assert selected["unitid"].tolist() == [3]
    assert selected["batch4_rank"].tolist() == [1]
    assert selected["legacy_url_count"].tolist() == [1]
