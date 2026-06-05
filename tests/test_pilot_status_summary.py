import pandas as pd

from course_policy.pilot_status_summary import build_status_summary, count_join, derived_bucket


def test_count_join_summarizes_status_counts():
    values = pd.Series(["ready", "missing", "ready", "", None])

    assert count_join(values) == "missing=1; ready=2"


def test_derived_bucket_marks_archive_bound_revisit():
    assert derived_bucket("official_archive_upper_bound_reached=4; review_before_retrieval=1") == (
        "archive_bound_revisit"
    )


def test_build_status_summary_marks_complete_and_escalated_cases():
    institutions = pd.DataFrame(
        [
            {"unitid": 1, "institution_name": "Clean U", "state": "CA", "strict_pilot_rank": 1},
            {"unitid": 2, "institution_name": "OCR U", "state": "GA", "strict_pilot_rank": 2},
        ]
    )
    year_coverage = pd.DataFrame(
        [
            {"unitid": 1, "target_year": 2000, "has_strict_catalog_source": True},
            {"unitid": 1, "target_year": 2001, "has_strict_catalog_source": True},
            {"unitid": 2, "target_year": 2000, "has_strict_catalog_source": False},
            {"unitid": 2, "target_year": 2001, "has_strict_catalog_source": True},
        ]
    )
    year_status = pd.DataFrame(
        [
            {"unitid": 2, "target_year": 2000, "candidate_status": "scanned_pdf_needs_ocr_or_visual_review"},
            {"unitid": 2, "target_year": 2001, "candidate_status": "already_strict_covered"},
        ]
    )
    source_root_plan = pd.DataFrame(
        [
            {
                "unitid": 1,
                "source_root_name": "Clean Archive",
                "source_root_role": "preferred_first_pass",
                "first_pass_decision": "use_for_first_pass",
                "fallback_order": 1,
                "notes": "done",
            },
            {
                "unitid": 2,
                "source_root_name": "Scanned Archive",
                "source_root_role": "preferred_first_pass",
                "first_pass_decision": "route_to_ocr_or_visual_review",
                "fallback_order": 1,
                "notes": "needs OCR",
            },
        ]
    )
    escalation_queue = pd.DataFrame(
        [
            {
                "unitid": 2,
                "strict_pilot_rank": 2,
                "escalation_bucket": "ocr_or_visual_review",
                "source_root_name": "Scanned Archive",
                "recommended_next_step": "Run OCR.",
            }
        ]
    )

    summary = build_status_summary(institutions, year_coverage, year_status, source_root_plan, escalation_queue)

    clean = summary.loc[summary["unitid"].eq(1)].iloc[0]
    ocr = summary.loc[summary["unitid"].eq(2)].iloc[0]
    assert clean["overall_status"] == "complete_strict_catalog_coverage"
    assert clean["strict_covered_years"] == 2
    assert ocr["overall_status"] == "ocr_or_visual_review"
    assert ocr["first_unresolved_year"] == 2000
    assert ocr["unresolved_statuses"] == "scanned_pdf_needs_ocr_or_visual_review=1"
