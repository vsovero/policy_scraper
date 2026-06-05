import pandas as pd

from course_policy.source_root_plan import build_escalation_queue, build_source_root_plan


def test_build_source_root_plan_records_unc_digitalnc_review():
    plan = build_source_root_plan(institutions())

    unc_rows = plan[plan["unitid"].eq(199139)]

    assert "preferred_first_pass_candidate" in set(unc_rows["source_root_role"])
    digitalnc = unc_rows[unc_rows["source_root_name"].str.contains("DigitalNC")].iloc[0]
    assert digitalnc["first_pass_decision"] == "review_as_preferred_root_before_next_retrieval"


def test_build_escalation_queue_maps_general_buckets():
    plan = build_source_root_plan(institutions())
    queue = build_escalation_queue(plan)

    assert set(queue["escalation_bucket"]) == {
        "catalog_dead_end",
        "ocr_or_visual_review",
        "source_root_review",
    }
    assert queue.loc[queue["unitid"].eq(138558), "escalation_bucket"].iloc[0] == "ocr_or_visual_review"
    assert queue.loc[queue["unitid"].eq(209490), "escalation_bucket"].iloc[0] == "catalog_dead_end"


def institutions():
    return pd.DataFrame(
        [
            {"unitid": 122597, "institution_name": "San Francisco State University", "strict_pilot_rank": 1},
            {"unitid": 138558, "institution_name": "Abraham Baldwin Agricultural College", "strict_pilot_rank": 2},
            {"unitid": 149222, "institution_name": "Southern Illinois University-Carbondale", "strict_pilot_rank": 3},
            {"unitid": 199139, "institution_name": "University of North Carolina at Charlotte", "strict_pilot_rank": 4},
            {"unitid": 209490, "institution_name": "Oregon Health & Science University", "strict_pilot_rank": 5},
        ]
    )
