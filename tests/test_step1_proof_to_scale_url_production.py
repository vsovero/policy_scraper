from pathlib import Path

import pandas as pd

from course_policy.step1_proof_to_scale_url_production import (
    INSTITUTION_YEAR_TARGETS_RUNTIME_INPUT,
    build_historical_case_precheck,
    write_discovery_inputs,
)


def test_step1_proof_to_scale_imports_clean_dependency_closure() -> None:
    assert callable(build_historical_case_precheck)


def test_write_discovery_inputs_materializes_year_targets_from_target_panel(tmp_path: Path) -> None:
    year_targets_path = tmp_path / INSTITUTION_YEAR_TARGETS_RUNTIME_INPUT
    assert not year_targets_path.exists()
    target_panel = pd.DataFrame(
        [
            {
                "unitid": 123,
                "institution_name": "Example State University",
                "sector": "public",
                "state": "EX",
                "academic_year": 2002,
                "homepage_url": "https://example.edu",
            },
            {
                "unitid": 123,
                "institution_name": "Example State University",
                "sector": "public",
                "state": "EX",
                "academic_year": 2003,
                "homepage_url": "https://example.edu",
            },
        ]
    )

    write_discovery_inputs(tmp_path, target_panel, ["public"])

    year_targets = pd.read_csv(year_targets_path)
    assert year_targets[["unitid", "institution_name", "year", "webaddr"]].to_dict("records") == [
        {
            "unitid": 123,
            "institution_name": "Example State University",
            "year": 2002,
            "webaddr": "https://example.edu",
        },
        {
            "unitid": 123,
            "institution_name": "Example State University",
            "year": 2003,
            "webaddr": "https://example.edu",
        },
    ]


def test_build_historical_case_precheck_uses_url_free_inventory_counts(tmp_path: Path) -> None:
    inventory_dir = tmp_path / "artifacts/AUDIT_TRAILS/url_discovery_historical_inventory"
    inventory_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "unitid": 123,
                "institution_name": "Example State University",
                "valid_human_legacy_rows": 2,
                "prior_programmatic_accepted_rows": 5,
                "unreviewed_candidate_lead_rows": 7,
                "failed_attempt_rows": 3,
                "priority_bucket": "prior_programmatic_accepted_needs_current_reverification",
                "source_files": "artifacts/PILOTS/url_discovery/pipeline_outputs/pilot_batch_001/source_review_log.csv",
            }
        ]
    ).to_csv(inventory_dir / "institution_priority_buckets.csv", index=False)
    target_panel = pd.DataFrame(
        [
            {
                "unitid": 123,
                "institution_name": "Example State University",
                "academic_year": 2002,
                "has_human_legacy_source": False,
            },
            {
                "unitid": 123,
                "institution_name": "Example State University",
                "academic_year": 2003,
                "has_human_legacy_source": False,
            },
        ]
    )

    precheck = build_historical_case_precheck(tmp_path, target_panel, "precheck_test_namespace")

    assert len(precheck) == 1
    row = precheck.iloc[0]
    assert row["historical_priority_bucket"] == "prior_programmatic_accepted_needs_current_reverification"
    assert row["valid_human_legacy_rows"] == 2
    assert row["prior_programmatic_accepted_rows"] == 5
    assert row["unreviewed_candidate_lead_rows"] == 7
    assert row["failed_attempt_rows"] == 3
    combined_text = " ".join(str(value) for value in row.tolist())
    assert "pilot_batch" not in combined_text
    assert "artifacts/PILOTS" not in combined_text
    assert "http://" not in combined_text
    assert "https://" not in combined_text


def test_build_historical_case_precheck_falls_back_without_inventory(tmp_path: Path) -> None:
    target_panel = pd.DataFrame(
        [
            {
                "unitid": 456,
                "institution_name": "Example Private College",
                "academic_year": 2002,
                "has_human_legacy_source": True,
            }
        ]
    )

    precheck = build_historical_case_precheck(tmp_path, target_panel, "precheck_test_namespace")

    assert len(precheck) == 1
    row = precheck.iloc[0]
    assert row["historical_priority_bucket"] == "valid_human_legacy"
    assert row["valid_human_legacy_rows"] == 1
    assert bool(row["historical_precheck_completed"]) is True
    assert bool(row["runtime_input_guardrail_confirmed"]) is True
