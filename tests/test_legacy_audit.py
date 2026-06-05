from course_policy.legacy_audit import (
    alias_map,
    flag_likely_student_note,
    normalize_policy_code,
    normalize_threshold,
    parse_year,
)


def test_alias_map_handles_public_and_private_headers():
    columns = ["unitid", "instnm", "start_yr", "Excerpt", "bulletin"]

    mapped = alias_map(columns)

    assert mapped["institution_name"] == "instnm"
    assert mapped["start_year"] == "start_yr"
    assert mapped["evidence_text"] == "Excerpt"
    assert mapped["bulletin_url"] == "bulletin"


def test_parse_year_extracts_catalog_year_from_text():
    assert parse_year("2004-2006") == 2004
    assert parse_year("Fall 2020 catalog") == 2020
    assert parse_year("") is None


def test_normalizers_distinguish_any_unknown_and_malformed_values():
    assert normalize_threshold("Any") == "ANY"
    assert normalize_threshold("Unknown") == "UNKNOWN"
    assert normalize_threshold("C-") == "C-"
    assert normalize_policy_code("yes") == "1"
    assert normalize_policy_code("No") == "0"
    assert normalize_policy_code("maybe") == "maybe"


def test_student_note_heuristic_flags_short_or_collector_language():
    assert flag_likely_student_note("Same policy in place since 2002.")
    assert flag_likely_student_note("The website did not mention a clear repeat policy in this catalog.")
    assert not flag_likely_student_note(
        "Students may repeat a course in which a grade of C- or lower was earned. "
        "Only the most recent grade will be included in the grade point average, "
        "although all attempts remain on the transcript."
    )
