from pathlib import Path

import pandas as pd

from course_policy.step1_post_repair_closure_audit import (
    build_closure_institution_ledger,
    build_closure_year_ledger,
    build_summary,
    public_411_status,
)


def _attrition_year(rows: list[dict[str, object]]) -> pd.DataFrame:
    defaults = {
        "target_universe_sector": "public",
        "target_universe_institution_name": "",
        "target_universe_state": "",
        "old_collected_policy_institution": True,
        "old_public_411_diagnostic_member": False,
        "selected_in_accepted_batch": True,
        "has_valid_human_legacy": False,
        "has_prior_programmatic_accepted": False,
        "has_imported_llm_candidate_lead": False,
        "historical_lead_only": False,
        "step2_eligibility": "blocked_flag_for_step2",
    }
    return pd.DataFrame([{**defaults, **row} for row in rows])


def _attrition_institution(rows: list[dict[str, object]]) -> pd.DataFrame:
    defaults = {
        "institution_name": "",
        "sector": "public",
        "state": "",
        "target_universe_member": True,
        "complete_institution_years": 1,
        "old_collected_policy_institution": True,
        "never_collected_policy_institution": False,
        "old_public_411_diagnostic_member": False,
    }
    return pd.DataFrame([{**defaults, **row} for row in rows])


def _empty_repair_frames() -> dict[str, pd.DataFrame]:
    return {
        "target": pd.DataFrame(),
        "candidate": pd.DataFrame(),
        "source": pd.DataFrame(),
        "review": pd.DataFrame(),
        "benchmark": pd.DataFrame(),
        "unresolved": pd.DataFrame(),
        "decisions": pd.DataFrame(),
        "proof": pd.DataFrame(),
    }


def test_repair_source_ledger_combines_without_double_counting() -> None:
    attrition = _attrition_year(
        [
            {"unitid": 1, "academic_year": 2002, "attrition_class": "accepted_source_row"},
            {
                "unitid": 2,
                "academic_year": 2002,
                "attrition_class": "candidate_materialization_failure",
                "has_prior_programmatic_accepted": True,
            },
        ]
    )
    repair = _empty_repair_frames()
    repair["source"] = pd.DataFrame(
        [
            {
                "unitid": 2,
                "academic_year": 2002,
                "review_decision": "accept_exact_year_catalog",
                "provenance_type": "prior_programmatic",
                "accepted_source_url": "https://example.edu/catalog",
            }
        ]
    )
    repair["benchmark"] = pd.DataFrame(
        [
            {
                "unitid": 2,
                "academic_year": 2002,
                "benchmark_resolution_type": "source_ledger_resolved_by_other_evidence",
            }
        ]
    )

    closure = build_closure_year_ledger(attrition, repair)

    assert int(closure["accepted_after_repair"].sum()) == 2
    repaired = closure.loc[closure["unitid"].eq(2)].iloc[0]
    assert bool(repaired["newly_accepted_by_repair"])
    assert repaired["closure_class"] == "accepted_source_row"
    assert repaired["accepted_provenance_bucket"] == "prior_programmatic"
    assert repaired["repair_benchmark_resolved_by_other_evidence_rows"] == 1


def test_columbus_style_repair_invalidation_is_not_materialization_failure() -> None:
    attrition = _attrition_year(
        [
            {
                "unitid": 139366,
                "academic_year": 2002,
                "attrition_class": "candidate_materialization_failure",
                "old_public_411_diagnostic_member": True,
                "has_valid_human_legacy": True,
            }
        ]
    )
    repair = _empty_repair_frames()
    repair["target"] = pd.DataFrame([{"unitid": 139366, "academic_year": 2002}])
    repair["unresolved"] = pd.DataFrame(
        [
            {
                "unitid": 139366,
                "academic_year": 2002,
                "review_decision": "reject_institution_not_confirmed_from_current_evidence",
                "unresolved_reason": "current evidence did not confirm institution match",
            }
        ]
    )

    closure = build_closure_year_ledger(attrition, repair)
    row = closure.iloc[0]

    assert not bool(row["accepted_after_repair"])
    assert row["repair_target_rows"] == 1
    assert row["repair_unresolved_rows"] == 1
    assert row["closure_class"] == "source_review_rejected_wrong_institution"


def test_historical_lead_candidate_stays_unaccepted_lead_only() -> None:
    attrition = _attrition_year(
        [
            {
                "unitid": 3,
                "academic_year": 2002,
                "attrition_class": "candidate_materialization_failure",
                "has_imported_llm_candidate_lead": True,
                "historical_lead_only": True,
            }
        ]
    )
    repair = _empty_repair_frames()
    repair["proof"] = pd.DataFrame(
        [
            {
                "unitid": 3,
                "year": 2002,
                "materialization_decision": "materialized_historical_lead_candidate",
                "historical_evidence_class": "imported_llm_candidate_lead_overlay",
                "provenance_label": "imported_llm_candidate_lead",
            }
        ]
    )

    closure = build_closure_year_ledger(attrition, repair)
    row = closure.iloc[0]

    assert row["closure_class"] == "historical_lead_only"
    assert not bool(row["accepted_after_repair"])
    assert row["accepted_provenance_bucket"] == ""
    assert row["repair_proof_historical_lead_rows"] == 1


def test_public_411_status_counts_repair_progress_and_unresolved_not_selected() -> None:
    institution = _attrition_institution(
        [
            {"unitid": 1, "old_public_411_diagnostic_member": True},
            {"unitid": 2, "old_public_411_diagnostic_member": True},
            {"unitid": 3, "old_public_411_diagnostic_member": True},
        ]
    )
    closure_year = pd.DataFrame(
        [
            {
                "unitid": 1,
                "academic_year": 2002,
                "old_public_411_diagnostic_member": True,
                "accepted_before_repair": True,
                "newly_accepted_by_repair": False,
                "accepted_after_repair": True,
                "selected_after_repair": True,
            },
            {
                "unitid": 2,
                "academic_year": 2002,
                "old_public_411_diagnostic_member": True,
                "accepted_before_repair": False,
                "newly_accepted_by_repair": True,
                "accepted_after_repair": True,
                "selected_after_repair": True,
            },
            {
                "unitid": 3,
                "academic_year": 2002,
                "old_public_411_diagnostic_member": True,
                "accepted_before_repair": False,
                "newly_accepted_by_repair": False,
                "accepted_after_repair": False,
                "selected_after_repair": False,
            },
        ]
    )
    target_counts = {
        "old_public_411_diagnostic": {
            "institutions": 4,
            "outside_target_universe": 1,
        }
    }

    status = public_411_status(institution, closure_year, target_counts)

    assert status["baseline_old_public_411_institutions"] == 4
    assert status["inside_target_universe"] == 3
    assert status["accepted_before_repair"] == 1
    assert status["newly_accepted_through_repair"] == 1
    assert status["still_unresolved_after_repair"] == 1
    assert status["not_yet_selected_unresolved_after_repair"] == 1


def test_build_summary_reports_columbus_closure_class() -> None:
    attrition = _attrition_year(
        [
            {
                "unitid": 139366,
                "academic_year": 2002,
                "attrition_class": "candidate_materialization_failure",
                "old_public_411_diagnostic_member": True,
            }
        ]
    )
    repair = _empty_repair_frames()
    repair["target"] = pd.DataFrame([{"unitid": 139366, "academic_year": 2002}])
    repair["unresolved"] = pd.DataFrame(
        [
            {
                "unitid": 139366,
                "academic_year": 2002,
                "review_decision": "reject_institution_not_confirmed_from_current_evidence",
            }
        ]
    )
    closure_year = build_closure_year_ledger(attrition, repair)
    attrition_inst = _attrition_institution([{"unitid": 139366, "old_public_411_diagnostic_member": True}])
    closure_inst = build_closure_institution_ledger(attrition_inst, closure_year)
    summary = build_summary(
        closure_inst,
        closure_year,
        {
            "target_universe_counts": {
                "old_public_411_diagnostic": {"institutions": 1, "outside_target_universe": 0}
            }
        },
        repair_artifacts=type(
            "Artifacts",
            (),
            {"input_dir": None, "release_dir": None, "chunk_dir": None, "proof_dir": None},
        )(),
        repo_root=Path("."),
        output_dir=Path("."),
    )

    assert summary["columbus_state"]["current_final_closure_class"] == "source_review_rejected_wrong_institution"
    assert summary["columbus_state"]["no_longer_candidate_materialization_failure"] is True
