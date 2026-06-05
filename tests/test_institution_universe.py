import pandas as pd

from course_policy.institution_universe import (
    build_legacy_evidence_links,
    classify_legacy_policy,
    source_priority,
    to_bool,
)


def test_to_bool_handles_csv_string_values():
    values = pd.Series([True, False, "True", "False", "1", "0", "", None])

    assert to_bool(values).tolist() == [True, False, True, False, True, False, False, False]


def test_source_priority_uses_private_sheet_precedence_after_rename():
    assert source_priority(pd.Series({"legacy_workbook": "public", "legacy_sheet_name": "Sheet1"})) == 10
    assert source_priority(pd.Series({"legacy_workbook": "private", "legacy_sheet_name": "private"})) == 10
    assert (
        source_priority(
            pd.Series({"legacy_workbook": "private", "legacy_sheet_name": "(Automated, 0121) Missing priva"})
        )
        == 40
    )


def test_classify_legacy_policy_accepts_floatlike_normalized_codes():
    row = pd.Series({"grade_averaging_normalized": "0.0", "grade_forgiveness_normalized": "1.0"})

    assert classify_legacy_policy(row) == "grade_forgiveness"


def test_legacy_links_preserve_duplicates_and_select_clean_lowest_priority():
    audits = pd.DataFrame(
        [
            {
                "workbook": "private",
                "sheet_name": "private",
                "excel_row": 2,
                "unitid": 100663,
                "parsed_start_year": 2004,
                "grade_averaging_normalized": "0",
                "grade_avg_threshold_normalized": "",
                "grade_forgiveness_normalized": "1",
                "grade_forgive_threshold_normalized": "UNKNOWN",
                "needs_review": False,
                "conflicting_duplicate_institution_year": False,
            },
            {
                "workbook": "private",
                "sheet_name": "example",
                "excel_row": 3,
                "unitid": 100663,
                "parsed_start_year": 2004,
                "grade_averaging_normalized": "0",
                "grade_avg_threshold_normalized": "",
                "grade_forgiveness_normalized": "1",
                "grade_forgive_threshold_normalized": "UNKNOWN",
                "needs_review": False,
                "conflicting_duplicate_institution_year": False,
            },
        ]
    )
    for col in [
        "missing_bulletin_url",
        "missing_evidence_text",
        "likely_student_note",
        "malformed_grade_averaging",
        "malformed_grade_forgiveness",
        "malformed_grade_avg_threshold",
        "malformed_grade_forgive_threshold",
        "duplicate_institution_year",
    ]:
        audits[col] = False
    universe = pd.DataFrame({"unitid": [100663]})

    links = build_legacy_evidence_links(audits, universe)

    assert len(links) == 2
    assert links["selected_as_prior_evidence"].tolist() == [True, False]
