import pandas as pd

from course_policy.current_process_trace import actual_source_role, build_year_trace


def test_actual_source_role_labels_mixed_roots():
    assert actual_source_role("strict-00009", 199139) == "legacy_prior_confirmed"
    assert actual_source_role("panel-uncc-2005-2007", 199139) == "fallback_official_gap_fill"
    assert actual_source_role("panel-abac-2000-2002", 138558) == "ocr_or_visual_review"
    assert actual_source_role("panel-ohsu-missing-2000", 209490) == "wrong_scope_or_fresh_discovery"


def test_build_year_trace_reverse_engineers_gap_and_coverage_steps():
    panel_year_status = pd.DataFrame(
        [
            {
                "unitid": 199139,
                "target_year": 2005,
                "candidate_status": "ready_for_retrieval",
                "candidate_source_id": "panel-uncc-2005-2007",
                "candidate_url": "https://provost.charlotte.edu/node/173/",
                "candidate_title": "2005-2007 Undergraduate Catalog",
                "candidate_review_reason": "",
            },
            {
                "unitid": 138558,
                "target_year": 2000,
                "candidate_status": "scanned_pdf_needs_ocr_or_visual_review",
                "candidate_source_id": "panel-abac-2000-2002",
                "candidate_url": "https://example.edu/2000-2002.pdf",
                "candidate_title": "2000-2002.pdf",
                "candidate_review_reason": "needs OCR",
            },
        ]
    )
    panel_retrieved_years = pd.DataFrame(
        [
            {
                "strict_pilot_rank": 4,
                "unitid": 199139,
                "institution_name": "UNC Charlotte",
                "target_year": 2005,
                "has_strict_catalog_source": True,
                "source_id": "panel-uncc-2005-2007",
                "candidate_url": "https://provost.charlotte.edu/node/173/",
                "review_reason": "",
            },
            {
                "strict_pilot_rank": 2,
                "unitid": 138558,
                "institution_name": "ABAC",
                "target_year": 2000,
                "has_strict_catalog_source": False,
                "source_id": "",
                "candidate_url": "",
                "review_reason": "missing",
            },
        ]
    )

    trace = build_year_trace(panel_year_status, panel_retrieved_years)

    roles = dict(zip(trace["unitid"], trace["actual_process_role"]))
    assert roles[199139] == "fallback_official_gap_fill"
    assert roles[138558] == "ocr_or_visual_review"
