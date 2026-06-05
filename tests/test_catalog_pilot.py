import pandas as pd

from course_policy.catalog_pilot import (
    build_catalog_inventory,
    build_public_pilot_features,
    infer_catalog_coverage_years,
    select_pilot_institutions,
)


def test_build_public_pilot_features_labels_representative_cases():
    universe = pd.DataFrame(
        [
            {"unitid": 1, "institution_name": "Clean U", "sector": "public_4_year", "state": "AA", "webaddr": ""},
            {"unitid": 2, "institution_name": "Messy U", "sector": "public_4_year", "state": "AA", "webaddr": ""},
            {"unitid": 3, "institution_name": "No Legacy U", "sector": "public_4_year", "state": "AA", "webaddr": ""},
            {"unitid": 4, "institution_name": "Private U", "sector": "private_nonprofit_4_year", "state": "AA", "webaddr": ""},
        ]
    )
    links = pd.DataFrame(
        [
            legacy_link(1, 2004, legacy_url="https://clean.edu/catalog-2004.pdf", selected_as_prior_evidence=True),
            legacy_link(
                2,
                2005,
                legacy_url="",
                legacy_needs_review=True,
                missing_bulletin_url=True,
                grade_forgive_threshold_normalized="UNKNOWN",
            ),
            legacy_link(
                2,
                2007,
                legacy_url="https://messy.edu/catalog-2006.pdf",
                grade_forgiveness_normalized="0",
                grade_avg_threshold_normalized="D",
            ),
            legacy_link(4, 2007, legacy_url="https://private.edu/catalog-2007.pdf"),
        ]
    )

    features = build_public_pilot_features(universe, links)

    clean = features.set_index("unitid").loc[1]
    messy = features.set_index("unitid").loc[2]
    no_legacy = features.set_index("unitid").loc[3]
    assert clean["clean_case"]
    assert messy["messy_case"]
    assert messy["missing_url_case"]
    assert not messy["cross_workbook_legacy_case"]
    assert messy["multiple_policy_change_case"]
    assert messy["ambiguous_threshold_case"]
    assert no_legacy["no_legacy_evidence_case"]
    assert set(features["unitid"]) == {1, 2, 3}


def test_select_pilot_institutions_is_bounded_and_ranked():
    features = pd.DataFrame(
        [
            feature_row(1, "A", clean_case=True),
            feature_row(2, "B", messy_case=True, missing_url_case=True),
            feature_row(3, "C", no_legacy_evidence_case=True),
        ]
    )
    features["pilot_feature_count"] = features[
        [
            "clean_case",
            "messy_case",
            "missing_url_case",
            "cross_workbook_legacy_case",
            "duplicate_or_conflicting_legacy_case",
            "multiple_policy_change_case",
            "ambiguous_threshold_case",
            "no_legacy_evidence_case",
        ]
    ].sum(axis=1)
    features["pilot_case_types"] = ""

    pilot = select_pilot_institutions(features, pilot_size=2)

    assert len(pilot) == 2
    assert pilot["pilot_rank"].tolist() == [1, 2]


def test_build_catalog_inventory_preserves_legacy_link_and_placeholder_rows():
    pilot = pd.DataFrame(
        [
            {
                "pilot_rank": 1,
                "unitid": 1,
                "institution_name": "Clean U",
                "pilot_case_types": "clean",
            }
        ]
    )
    targets = pd.DataFrame(
        [
            {"unitid": 1, "institution_name": "Clean U", "year": 2004},
            {"unitid": 1, "institution_name": "Clean U", "year": 2005},
        ]
    )
    links = pd.DataFrame(
        [
            legacy_link(1, 2004, legacy_url="https://clean.edu/catalogs/2004-2006-undergraduate.pdf"),
            legacy_link(
                1,
                2004,
                legacy_workbook="private",
                legacy_url="https://clean.edu/private-example-should-be-ignored.pdf",
            ),
        ]
    )

    inventory = build_catalog_inventory(pilot, targets, links)

    assert len(inventory) == 2
    linked = inventory[inventory["target_year"].eq(2004)].iloc[0]
    missing = inventory[inventory["target_year"].eq(2005)].iloc[0]
    assert linked["candidate_url"] == "https://clean.edu/catalogs/2004-2006-undergraduate.pdf"
    assert linked["discovery_method"] == "legacy_workbook"
    assert missing["candidate_url"] == ""
    assert missing["needs_human_review"]


def test_infer_catalog_coverage_years_reads_academic_year_range():
    assert infer_catalog_coverage_years("https://example.edu/catalog-2013-2014.pdf", "") == (2013, 2014)
    assert infer_catalog_coverage_years("https://example.edu/catalog-2004-06.pdf", "") == (2004, 2006)
    assert infer_catalog_coverage_years("https://example.edu/catalog-2020.pdf", "") == (2020, 2021)


def legacy_link(unitid, year, **overrides):
    row = {
        "legacy_link_id": f"{unitid}-{year}",
        "unitid": unitid,
        "target_year": year,
        "legacy_workbook": "public",
        "legacy_sheet_name": "Sheet1",
        "legacy_excel_row": 2,
        "legacy_source_priority": 10,
        "legacy_url": "https://example.edu/catalog.pdf",
        "legacy_excerpt": "Students may repeat a course.",
        "legacy_policy_class": "grade_forgiveness",
        "grade_avg_threshold_normalized": "",
        "grade_forgive_threshold_normalized": "C",
        "grade_averaging_normalized": "0",
        "grade_forgiveness_normalized": "1",
        "legacy_needs_review": False,
        "legacy_review_reasons": "",
        "missing_bulletin_url": False,
        "missing_evidence_text": False,
        "likely_student_note": False,
        "malformed_grade_avg_threshold": False,
        "malformed_grade_forgive_threshold": False,
        "duplicate_institution_year": False,
        "conflicting_duplicate_institution_year": False,
        "selected_as_prior_evidence": False,
    }
    row.update(overrides)
    return row


def feature_row(unitid, name, **overrides):
    row = {
        "unitid": unitid,
        "institution_name": name,
        "state": "AA",
        "webaddr": "",
        "clean_case": False,
        "messy_case": False,
        "missing_url_case": False,
        "cross_workbook_legacy_case": False,
        "duplicate_or_conflicting_legacy_case": False,
        "multiple_policy_change_case": False,
        "ambiguous_threshold_case": False,
        "no_legacy_evidence_case": False,
        "legacy_link_rows": 1,
        "legacy_year_count": 1,
        "legacy_url_count": 1,
        "legacy_workbooks": "public",
        "legacy_policy_classes": "grade_forgiveness",
        "selected_clean_url_count": 1,
        "missing_url_count": 0,
        "missing_excerpt_count": 0,
        "student_note_count": 0,
        "malformed_threshold_count": 0,
        "needs_review_count": 0,
        "duplicate_count": 0,
        "conflicting_duplicate_count": 0,
        "ambiguous_threshold_count": 0,
    }
    row.update(overrides)
    return row
