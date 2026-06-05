import pandas as pd

from course_policy.fresh_discovery import overall_fresh_discovery_status, repeated_course_excerpt


def test_overall_status_prefers_policy_evidence_root_after_catalog_root():
    discovery = pd.DataFrame(
        [
            {
                "acceptable_first_pass_catalog_root": False,
                "acceptable_policy_evidence_root": True,
                "needs_exception_review": True,
                "first_pass_decision": "use_as_policy_evidence_root",
            }
        ]
    )

    assert overall_fresh_discovery_status(discovery) == "acceptable_policy_evidence_root_found"


def test_repeated_course_excerpt_extracts_near_repeat_terms():
    text = "A" * 100 + "Repeated Courses with Low or Failing Grades. The original course is excluded."

    excerpt = repeated_course_excerpt(text)

    assert "Repeated Courses" in excerpt
    assert "original course is excluded" in excerpt
