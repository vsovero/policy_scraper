import pandas as pd

from course_policy.batch2_root_check import (
    build_source_root_decisions,
    candidate_urls_for_task,
    likely_catalog_root,
    normalized_url,
    update_source_root_tasks,
)


def test_normalized_url_adds_scheme_and_trailing_path():
    assert normalized_url("www.example.edu") == "https://www.example.edu/"
    assert normalized_url("nan") == ""


def test_candidate_urls_include_generated_catalog_subdomain_and_legacy_parent():
    task = pd.Series({"unitid": 1, "webaddr": "www.example.edu"})
    leads = pd.DataFrame(
        [{"unitid": 1, "legacy_url": "https://www.example.edu/catalogs/2000.pdf", "legacy_url_parent": ""}]
    )

    urls = candidate_urls_for_task(task, leads)

    assert {"candidate_url": "https://catalog.example.edu/", "candidate_source_type": "generated_catalog_subdomain"} in urls
    assert {"candidate_url": "https://www.example.edu/catalogs/", "candidate_source_type": "legacy_parent_url"} in urls


def test_likely_catalog_root_accepts_catalog_subdomain_title():
    result = {
        "retrieval_status": "retrieved",
        "page_title": "Example University Catalog",
        "link_records": [],
    }

    assert likely_catalog_root(result, "https://catalog.example.edu/", "generated_catalog_subdomain")


def test_build_source_root_decisions_prefers_lowest_priority_root():
    candidates = pd.DataFrame(
        [
            {
                "batch2_rank": 1,
                "unitid": 1,
                "institution_name": "Example U",
                "candidate_url": "https://example.edu/catalogs/",
                "candidate_source_type": "legacy_parent_url",
                "page_title": "Archive",
                "likely_catalog_root": True,
                "root_priority": 20,
            },
            {
                "batch2_rank": 1,
                "unitid": 1,
                "institution_name": "Example U",
                "candidate_url": "https://catalog.example.edu/",
                "candidate_source_type": "generated_catalog_subdomain",
                "page_title": "Catalog",
                "likely_catalog_root": True,
                "root_priority": 10,
            },
        ]
    )

    decisions = build_source_root_decisions(candidates)

    assert decisions["decision_status"].iloc[0] == "preferred_source_root_identified"
    assert decisions["preferred_source_root_url"].iloc[0] == "https://catalog.example.edu/"


def test_update_source_root_tasks_is_idempotent_after_prior_decision_columns():
    tasks = pd.DataFrame(
        [
            {
                "batch2_rank": 1,
                "unitid": 1,
                "institution_name": "Example U",
                "task_status": "preferred_source_root_identified",
                "decision_status": "preferred_source_root_identified",
                "preferred_source_root_url": "https://old.example.edu/",
                "preferred_source_root_type": "old",
                "preferred_source_root_title": "Old",
                "preferred_source_root_name": "Old",
                "recommended_next_step": "old",
            }
        ]
    )
    decisions = pd.DataFrame(
        [
            {
                "unitid": 1,
                "decision_status": "preferred_source_root_identified",
                "preferred_source_root_url": "https://catalog.example.edu/",
                "preferred_source_root_type": "generated_catalog_subdomain",
                "preferred_source_root_title": "Catalog",
                "recommended_next_step": "expand",
            }
        ]
    )

    updated = update_source_root_tasks(tasks, decisions)

    assert updated["task_status"].iloc[0] == "preferred_source_root_identified"
    assert updated["preferred_source_root_url"].iloc[0] == "https://catalog.example.edu/"
