from pathlib import Path

import pandas as pd
import pytest

from course_policy.step1_attrition_audit import (
    BatchArtifacts,
    TargetUniverse,
    build_institution_ledger,
    build_institution_year_ledger,
    load_target_universe,
    parse_batch_range,
    read_csv_or_empty,
    target_universe_count_summary,
    target_universe_expected_match,
    write_report,
)


def _historical(
    attempts: list[dict[str, object]] | None = None,
    discoveries: list[dict[str, object]] | None = None,
    priority: list[dict[str, object]] | None = None,
) -> dict[str, pd.DataFrame]:
    return {
        "attempts": pd.DataFrame(attempts or []),
        "discoveries": pd.DataFrame(discoveries or []),
        "priority": pd.DataFrame(priority or []),
        "inventory_dir": pd.DataFrame([{"inventory_dir": "test_inventory"}]),
    }


def test_target_universe_loader_matches_correct_denominator() -> None:
    if not (Path("../Stata Files/Data/step2_ipeds_universe_with_policy_flags.dta").exists()):
        pytest.skip("Step 2 policy-flag panel is not available")

    target_universe = load_target_universe(Path.cwd())
    memberships = target_universe.memberships

    public = memberships.loc[memberships["target_universe_sector"].eq("public")]
    private = memberships.loc[memberships["target_universe_sector"].eq("private")]
    assert len(public) == 577
    assert int(public["membership_complete_institution_years"].sum()) == 7941
    assert int(public["old_collected_policy_institution"].sum()) == 427
    assert int(public["never_collected_policy_institution"].sum()) == 150
    assert len(private) == 1233
    assert int(private["membership_complete_institution_years"].sum()) == 15918
    assert int(private["old_collected_policy_institution"].sum()) == 243
    assert int(private["never_collected_policy_institution"].sum()) == 990
    assert len(memberships) == 1810
    assert len(target_universe.year_rows) == 23853
    assert len(target_universe.old_public_411) == 411
    target_public_ids = set(public["unitid"].dropna().astype(int))
    old_public_ids = set(target_universe.old_public_411["unitid"].dropna().astype(int))
    assert len(old_public_ids & target_public_ids) == 391
    assert len(old_public_ids - target_public_ids) == 20


def test_columbus_style_upstream_evidence_without_candidates_is_materialization_failure() -> None:
    target = pd.DataFrame(
        [
            {
                "unitid": 139366,
                "institution_name": "Columbus State University",
                "sector": "public",
                "state": "GA",
                "academic_year": 2002,
                "batch_id": "005",
                "has_human_legacy_source": True,
            },
            {
                "unitid": 139366,
                "institution_name": "Columbus State University",
                "sector": "public",
                "state": "GA",
                "academic_year": 2003,
                "batch_id": "005",
                "has_human_legacy_source": True,
            },
        ]
    )
    review = pd.DataFrame(
        [
            {"unitid": 139366, "academic_year": 2002, "review_decision": "not_reviewed_no_target_year_candidate"},
            {"unitid": 139366, "academic_year": 2003, "review_decision": "not_reviewed_no_target_year_candidate"},
        ]
    )
    historical = _historical(
        attempts=[
            {
                "unitid": 139366,
                "academic_year": 2002,
                "evidence_class": "valid_human_legacy",
                "url": "https://archived.columbusstate.edu/catalogs/2002-2003/",
            },
            {
                "unitid": 139366,
                "academic_year": 2003,
                "evidence_class": "valid_human_legacy",
                "url": "https://archived.columbusstate.edu/catalogs/2003-2004/",
            },
        ],
        discoveries=[
            {
                "unitid": 139366,
                "academic_year": 2002,
                "evidence_class": "valid_human_legacy",
                "url": "https://archived.columbusstate.edu/catalogs/2002-2003/",
            },
            {
                "unitid": 139366,
                "academic_year": 2003,
                "evidence_class": "valid_human_legacy",
                "url": "https://archived.columbusstate.edu/catalogs/2003-2004/",
            },
        ],
        priority=[{"unitid": 139366, "priority_bucket": "valid_human_legacy"}],
    )

    ledger = build_institution_year_ledger(
        target=target,
        candidate=pd.DataFrame(),
        benchmark=pd.DataFrame(),
        review=review,
        ledger=pd.DataFrame(),
        historical=historical,
        raw_year=pd.DataFrame(),
    )

    columbus = ledger.loc[ledger["unitid"].eq(139366)]
    assert set(columbus["attrition_class"]) == {"candidate_materialization_failure"}
    assert set(columbus["secondary_attrition_class"]) == {"dropped_historical_url_evidence"}
    assert set(columbus["step2_eligibility"]) == {"blocked_flag_for_step2"}
    assert columbus["has_historical_url_evidence"].all()
    assert columbus["has_valid_human_legacy"].all()
    institution = build_institution_ledger(ledger, historical["priority"])
    assert institution.iloc[0]["institution_attrition_class"] == "candidate_materialization_failure"


def test_failed_historical_attempt_without_url_is_not_dropped_url_evidence() -> None:
    target = pd.DataFrame(
        [
            {
                "unitid": 100010,
                "institution_name": "Failed Attempt College",
                "sector": "private",
                "state": "CA",
                "academic_year": 2010,
                "batch_id": "020",
            }
        ]
    )
    review = pd.DataFrame(
        [
            {"unitid": 100010, "academic_year": 2010, "review_decision": "not_reviewed_no_target_year_candidate"},
        ]
    )
    historical = _historical(
        attempts=[
            {
                "unitid": 100010,
                "academic_year": 2010,
                "evidence_class": "programmatic_attempt_no_valid_discovery",
                "url": "",
                "candidate_url": "",
                "final_url": "",
            }
        ],
        priority=[{"unitid": 100010, "priority_bucket": "programmatic_attempt_no_valid_discovery"}],
    )

    ledger = build_institution_year_ledger(
        target=target,
        candidate=pd.DataFrame(),
        benchmark=pd.DataFrame(),
        review=review,
        ledger=pd.DataFrame(),
        historical=historical,
        raw_year=pd.DataFrame(),
    )

    row = ledger.iloc[0]
    assert row["historical_attempt_failed_attempt_rows"] == 1
    assert row["historical_attempt_url_value_rows"] == 0
    assert bool(row["has_failed_historical_attempt"])
    assert not bool(row["has_historical_url_evidence"])
    assert not bool(row["has_upstream_url_evidence"])
    assert row["attrition_class"] == "true_no_upstream_url_evidence"
    assert row["secondary_attrition_class"] == ""


def test_selected_row_without_upstream_evidence_is_true_no_upstream_evidence() -> None:
    target = pd.DataFrame(
        [
            {
                "unitid": 100001,
                "institution_name": "No Evidence College",
                "sector": "private",
                "state": "CA",
                "academic_year": 2005,
                "batch_id": "010",
            }
        ]
    )

    ledger = build_institution_year_ledger(
        target=target,
        candidate=pd.DataFrame(),
        benchmark=pd.DataFrame(),
        review=pd.DataFrame(),
        ledger=pd.DataFrame(),
        historical=_historical(),
        raw_year=pd.DataFrame(),
    )

    row = ledger.iloc[0]
    assert row["attrition_class"] == "true_no_upstream_url_evidence"
    assert row["secondary_attrition_class"] == ""
    assert not bool(row["has_upstream_url_evidence"])


def test_source_ledger_acceptance_overrides_unresolved_review_state() -> None:
    target = pd.DataFrame(
        [
            {
                "unitid": 100002,
                "institution_name": "Accepted College",
                "sector": "public",
                "state": "OR",
                "academic_year": 2006,
                "batch_id": "011",
            }
        ]
    )
    source_ledger = pd.DataFrame(
        [
            {
                "unitid": 100002,
                "academic_year": 2006,
                "source_url": "https://accepted.example.edu/catalog-2006.pdf",
            }
        ]
    )

    ledger = build_institution_year_ledger(
        target=target,
        candidate=pd.DataFrame(),
        benchmark=pd.DataFrame(),
        review=pd.DataFrame(),
        ledger=source_ledger,
        historical=_historical(),
        raw_year=pd.DataFrame(),
    )

    assert ledger.iloc[0]["attrition_class"] == "accepted_source_row"
    assert ledger.iloc[0]["step2_eligibility"] == "eligible_source_accepted"


def test_attrition_report_includes_columbus_regression_and_hard_gates(tmp_path: Path) -> None:
    target = pd.DataFrame(
        [
            {
                "unitid": 139366,
                "institution_name": "Columbus State University",
                "sector": "public",
                "state": "GA",
                "academic_year": 2002,
                "batch_id": "005",
            }
        ]
    )
    historical = _historical(
        attempts=[
            {
                "unitid": 139366,
                "academic_year": 2002,
                "evidence_class": "valid_human_legacy",
                "url": "https://archived.columbusstate.edu/catalogs/2002-2003/",
            }
        ],
        discoveries=[
            {
                "unitid": 139366,
                "academic_year": 2002,
                "evidence_class": "valid_human_legacy",
                "url": "https://archived.columbusstate.edu/catalogs/2002-2003/",
            }
        ],
        priority=[{"unitid": 139366, "priority_bucket": "valid_human_legacy"}],
    )
    year_ledger = build_institution_year_ledger(
        target=target,
        candidate=pd.DataFrame(),
        benchmark=pd.DataFrame(),
        review=pd.DataFrame(),
        ledger=pd.DataFrame(),
        historical=historical,
        raw_year=pd.DataFrame(),
    )
    institution_ledger = build_institution_ledger(year_ledger, historical["priority"])
    target_universe = TargetUniverse(
        year_rows=year_ledger[["unitid", "academic_year"]].copy(),
        memberships=institution_ledger[["unitid", "sector"]].rename(columns={"sector": "target_universe_sector"}),
        old_public_411=pd.DataFrame([{"unitid": 139366, "old_public_411_diagnostic_member": True}]),
        source_panel=tmp_path / "step2_ipeds_universe_with_policy_flags.dta",
        old_public_source_panel=tmp_path / "step2_baseline_2002_representativeness_sample.dta",
    )
    target_counts = target_universe_count_summary(institution_ledger, year_ledger, target_universe.old_public_411)

    report = write_report(
        tmp_path,
        institution_ledger,
        year_ledger,
        artifacts={5: BatchArtifacts(batch_id=5, input_dir=tmp_path, release_dir=tmp_path)},
        historical=historical,
        target_universe=target_universe,
        target_counts=target_counts,
    )

    text = report.read_text(encoding="utf-8")
    assert "Columbus State is a candidate-materialization/dropped-historical-URL process failure" in text
    assert "selected institution with eligible historical URL evidence cannot have an empty candidate ledger" in text
    assert "candidate_materialization_failure" in text
    assert "dropped_historical_url_evidence" in text


def test_target_universe_expected_match_accepts_correct_counts() -> None:
    summary = {
        "public": {
            "institutions": 577,
            "membership_complete_institution_years": 7941,
            "old_collected_policy_institutions": 427,
            "never_collected_policy_institutions": 150,
        },
        "private": {
            "institutions": 1233,
            "membership_complete_institution_years": 15918,
            "old_collected_policy_institutions": 243,
            "never_collected_policy_institutions": 990,
        },
        "total": {
            "sector_institution_memberships": 1810,
            "unique_complete_institution_years": 23853,
            "old_collected_policy_institutions": 670,
            "never_collected_policy_institutions": 1140,
        },
    }

    assert target_universe_expected_match(summary)


def test_parse_batch_range_accepts_ranges_and_lists() -> None:
    assert parse_batch_range("1-3") == [1, 2, 3]
    assert parse_batch_range("1,3,5") == [1, 3, 5]


def test_read_csv_or_empty_handles_zero_column_csv(tmp_path: Path) -> None:
    empty_csv = tmp_path / "empty.csv"
    empty_csv.write_text("", encoding="utf-8")

    assert read_csv_or_empty(empty_csv).empty
