from course_policy.manual_catalog_search_audit import MANUAL_FINDINGS


def test_manual_catalog_search_audit_covers_current_test_set():
    unitids = {row["unitid"] for row in MANUAL_FINDINGS}

    assert len(MANUAL_FINDINGS) == 45
    assert len(unitids) == 45


def test_manual_catalog_search_audit_records_digital_archive_recoveries():
    digital_roots = {
        row["unitid"]: row
        for row in MANUAL_FINDINGS
        if "digital_archive" in row["manual_root_type"] or row["manual_root_type"] == "university_digital_archive"
    }

    assert 139940 in digital_roots
    assert 127741 in digital_roots
