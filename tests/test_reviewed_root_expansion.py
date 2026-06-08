import pandas as pd

from course_policy.reviewed_root_expansion import choose_best_candidates


def test_choose_best_candidates_keeps_general_and_graduate_catalog():
    candidates = pd.DataFrame(
        [
            {
                "unitid": 1,
                "target_year": 2020,
                "candidate_url": "https://catalog.example.edu/archives/2020-2021/general_and_graduate",
                "candidate_link_text": "PDF",
                "candidate_evidence_text": "2020-2021 General and Graduate Catalog PDF",
                "candidate_source_method": "reviewed_root_archive",
                "candidate_priority": 15,
            },
            {
                "unitid": 1,
                "target_year": 2020,
                "candidate_url": "https://catalog.example.edu/archives/2020-2021/graduate",
                "candidate_link_text": "2020-2021 Graduate Catalog",
                "candidate_evidence_text": "2020-2021 Graduate Catalog",
                "candidate_source_method": "reviewed_root_archive",
                "candidate_priority": 30,
            },
        ]
    )

    chosen = choose_best_candidates(candidates)

    assert len(chosen) == 1
    assert chosen["candidate_url"].iloc[0].endswith("/general_and_graduate")
