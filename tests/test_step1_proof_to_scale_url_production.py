from pathlib import Path
import time

import pandas as pd
import pytest

from course_policy.step1_proof_to_scale_url_production import (
    INSTITUTION_YEAR_TARGETS_RUNTIME_INPUT,
    benchmark_rows_for_legacy_candidates,
    build_historical_case_precheck,
    build_parser,
    build_step1_inputs,
    candidate_options_for_row,
    enrich_raw_legacy_with_historical_provenance,
    load_excluded_unitids,
    load_raw_legacy_url_rows,
    raw_legacy_candidates_for_target,
    raw_legacy_coverage_summary,
    retrieve_candidate_with_wayback_recovery,
    retrieve_url_with_retries,
    run_proof_to_scale,
    select_historical_lead_source_reconstruction_institutions,
    select_high_legacy_coverage_institutions,
    select_prior_valid_legacy_reverification_institutions,
    write_discovery_inputs,
)


def test_step1_proof_to_scale_imports_clean_dependency_closure() -> None:
    assert callable(build_historical_case_precheck)


def test_cli_defaults_to_prior_valid_legacy_reverification_target() -> None:
    args = build_parser().parse_args(["--namespace", "n", "--chunk-id", "c"])

    assert args.selection_mode == "prior_valid_legacy_reverification"


def test_cli_accepts_prior_valid_exclusion_file() -> None:
    args = build_parser().parse_args(["--namespace", "n", "--chunk-id", "c", "--exclude-unitids-file", "done.csv"])

    assert args.exclude_unitids_file == Path("done.csv")


def test_cli_accepts_historical_lead_source_reconstruction_mode() -> None:
    args = build_parser().parse_args(
        ["--namespace", "n", "--chunk-id", "c", "--selection-mode", "historical_lead_source_reconstruction"]
    )

    assert args.selection_mode == "historical_lead_source_reconstruction"


def test_legacy_candidate_uses_neutral_label_and_provenance() -> None:
    row = pd.Series(
        {
            "unitid": 123,
            "institution_name": "Example University",
            "sector": "public",
            "state": "EX",
            "academic_year": 2002,
            "homepage_url": "https://example.edu",
        }
    )
    legacy_row = pd.Series(
        {
            "candidate_url": "https://legacy.example.edu/catalog-2002.pdf",
            "candidate_generation_method": "raw_human_legacy_url",
            "candidate_source_type": "human_legacy_url",
            "legacy_input_provenance": "prior_programmatic",
            "catalog_year_start": 2002,
            "catalog_year_end": 2002,
        }
    )

    [option] = candidate_options_for_row(row=row, legacy_row=legacy_row, namespace="n", repo_root=Path.cwd())

    assert option["candidate_generation_method"] == "raw_legacy_input_url"
    assert option["candidate_source_type"] == "legacy_input_url"
    assert option["url_source_bucket"] == "legacy_input_url"
    assert option["legacy_input_provenance"] == "prior_programmatic"
    label_text = " ".join(str(option[key]) for key in ["candidate_generation_method", "candidate_source_type", "url_source_bucket"])
    assert "human" not in label_text


def test_imported_llm_legacy_candidate_is_not_labeled_human() -> None:
    row = pd.Series(
        {
            "unitid": 124,
            "institution_name": "LLM Candidate University",
            "sector": "private",
            "state": "EX",
            "academic_year": 2004,
            "homepage_url": "https://llm.example.edu",
        }
    )
    legacy_row = pd.Series(
        {
            "candidate_url": "https://llm-lead.example.edu/catalog-2004.pdf",
            "candidate_generation_method": "imported_llm_candidate_lead",
            "candidate_source_type": "human_legacy_url",
            "catalog_year_start": 2004,
            "catalog_year_end": 2004,
        }
    )

    [option] = candidate_options_for_row(row=row, legacy_row=legacy_row, namespace="n", repo_root=Path.cwd())

    assert option["candidate_generation_method"] == "imported_llm_candidate_lead"
    assert option["candidate_source_type"] == "imported_llm_candidate_lead"
    assert option["url_source_bucket"] == "historical_lead_input_url"
    assert option["legacy_input_provenance"] == "imported_llm_candidate_lead"
    assert "human" not in option["candidate_source_type"]


def test_loader_labels_automated_and_llm_private_tabs_as_historical_leads(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    public_path = tmp_path / "Ipeds raw Data files" / "Course repetition data.xlsx"
    private_path = tmp_path / "Stata Files" / "Data" / "gfprivatelist.xlsx"
    public_path.parent.mkdir(parents=True)
    private_path.parent.mkdir(parents=True)
    public_path.write_bytes(b"")
    private_path.write_bytes(b"")

    def fake_read_excel(path: Path, sheet_name: str):
        if sheet_name == "(Automated, 0121) Missing priva":
            return pd.DataFrame(
                [
                    {
                        "unitid": 31,
                        "instnm": "Automated Tab College",
                        "bulletin": "https://automated.invalid/catalog-2002.pdf",
                    }
                ]
            )
        if sheet_name == "LLM Training Set":
            return pd.DataFrame(
                [
                    {
                        "unitid": 32,
                        "instnm": "LLM Tab College",
                        "bulletin": "https://llm.invalid/catalog-2003.pdf",
                    }
                ]
            )
        if sheet_name == "private":
            return pd.DataFrame(columns=["unitid", "instnm", "bulletin"])
        return pd.DataFrame(columns=["unitid", "institution name", "bulletin", "Earliest Bulletin", "Current Bulletin"])

    monkeypatch.setattr("course_policy.step1_proof_to_scale_url_production.pd.read_excel", fake_read_excel)

    loaded = load_raw_legacy_url_rows(repo_root)

    by_unitid = {int(row["unitid"]): row for _, row in loaded.iterrows()}
    automated = by_unitid[31]
    llm = by_unitid[32]
    assert automated["candidate_generation_method"] == "historical_programmatic_lead"
    assert automated["candidate_source_type"] == "historical_programmatic_lead"
    assert automated["legacy_input_provenance"] == "historical_programmatic_lead"
    assert bool(automated["counts_as_legacy_coverage"]) is False
    assert llm["candidate_generation_method"] == "imported_llm_candidate_lead"
    assert llm["candidate_source_type"] == "imported_llm_candidate_lead"
    assert llm["legacy_input_provenance"] == "imported_llm_candidate_lead"
    assert bool(llm["counts_as_legacy_coverage"]) is False


def test_retrieve_url_with_retries_has_wall_clock_guard(monkeypatch) -> None:
    def slow_retrieve(url: str, *, timeout_seconds: int, max_bytes: int):
        time.sleep(5)
        return {"retrieval_status": "retrieved", "body": b"late"}

    monkeypatch.setattr("course_policy.step1_proof_to_scale_url_production.retrieve_url", slow_retrieve)

    started = time.monotonic()
    result = retrieve_url_with_retries(
        "https://example.edu/slow",
        timeout_seconds=1,
        max_bytes=100,
        attempts=1,
        wall_timeout_seconds=0.2,
    )
    elapsed = time.monotonic() - started

    assert elapsed < 2
    assert result["retrieval_status"] == "error"
    assert result["error_type"] == "RetrievalWallClockTimeout"


def test_retrieve_url_with_retries_can_terminate_subprocess_hang(monkeypatch) -> None:
    def slow_retrieve(url: str, *, timeout_seconds: int, max_bytes: int):
        time.sleep(5)
        return {"retrieval_status": "retrieved", "body": b"late"}

    monkeypatch.setattr("course_policy.step1_proof_to_scale_url_production.retrieve_url", slow_retrieve)

    started = time.monotonic()
    result = retrieve_url_with_retries(
        "https://web.archive.org/slow",
        timeout_seconds=1,
        max_bytes=100,
        attempts=1,
        wall_timeout_seconds=0.2,
        use_subprocess=True,
        subprocess_start_method="fork",
    )
    elapsed = time.monotonic() - started

    assert elapsed < 2
    assert result["retrieval_status"] == "error"
    assert result["error_type"] == "RetrievalWallClockTimeout"


def test_retrieve_url_with_retries_reads_subprocess_result_before_join(monkeypatch) -> None:
    large_body = b"x" * (2 * 1024 * 1024)

    def large_retrieve(url: str, *, timeout_seconds: int, max_bytes: int):
        return {"retrieval_status": "retrieved", "body": large_body}

    monkeypatch.setattr("course_policy.step1_proof_to_scale_url_production.retrieve_url", large_retrieve)

    started = time.monotonic()
    result = retrieve_url_with_retries(
        "https://web.archive.org/large-result",
        timeout_seconds=1,
        max_bytes=len(large_body),
        attempts=1,
        wall_timeout_seconds=2,
        use_subprocess=True,
        subprocess_start_method="fork",
    )
    elapsed = time.monotonic() - started

    assert elapsed < 2
    assert result["retrieval_status"] == "retrieved"
    assert result["body"] == large_body


def test_wayback_recovery_uses_single_bounded_lookup_attempts(monkeypatch) -> None:
    def failed_direct_retrieve(url: str, *, timeout_seconds: int, max_bytes: int, **kwargs):
        return {"retrieval_status": "error", "error_type": "direct_failure"}

    retry_calls: list[dict[str, object]] = []

    def failed_retry(url: str, **kwargs):
        retry_calls.append({"url": url, **kwargs})
        return {"retrieval_status": "error", "error_type": "wayback_failure"}

    monkeypatch.setattr("course_policy.step1_proof_to_scale_url_production.retrieve_url_bounded", failed_direct_retrieve)
    monkeypatch.setattr("course_policy.step1_proof_to_scale_url_production.retrieve_url_with_retries", failed_retry)

    retrieve_candidate_with_wayback_recovery(
        "https://example.edu/catalog-2004.pdf",
        target_year=2004,
        timeout_seconds=30,
        max_source_bytes=1000,
        allow_wayback_recovery=True,
    )

    assert len(retry_calls) == 3
    assert {call["attempts"] for call in retry_calls} == {1}
    assert {call["timeout_seconds"] for call in retry_calls} == {12}
    assert {call["wall_timeout_seconds"] for call in retry_calls} == {14}
    assert all(call["use_subprocess"] is True for call in retry_calls)
    assert {call["subprocess_start_method"] for call in retry_calls} == {"spawn"}


def test_prior_valid_legacy_selection_prioritizes_current_reverification_bucket() -> None:
    target_universe = pd.DataFrame(
        [
            {
                "unitid": 1,
                "institution_name": "Programmatic Accepted U",
                "sector_stream": "public",
                "state": "AA",
                "academic_year": 2002,
                "webaddr": "https://program.edu",
                "has_human_legacy_source": False,
            },
            {
                "unitid": 1,
                "institution_name": "Programmatic Accepted U",
                "sector_stream": "public",
                "state": "AA",
                "academic_year": 2003,
                "webaddr": "https://program.edu",
                "has_human_legacy_source": False,
            },
            {
                "unitid": 2,
                "institution_name": "Human Legacy U",
                "sector_stream": "public",
                "state": "BB",
                "academic_year": 2002,
                "webaddr": "https://human.edu",
                "has_human_legacy_source": True,
            },
            {
                "unitid": 2,
                "institution_name": "Human Legacy U",
                "sector_stream": "public",
                "state": "BB",
                "academic_year": 2003,
                "webaddr": "https://human.edu",
                "has_human_legacy_source": True,
            },
            {
                "unitid": 3,
                "institution_name": "No Human Holdout U",
                "sector_stream": "public",
                "state": "CC",
                "academic_year": 2002,
                "webaddr": "https://holdout.edu",
                "has_human_legacy_source": False,
            },
            {
                "unitid": 3,
                "institution_name": "No Human Holdout U",
                "sector_stream": "public",
                "state": "CC",
                "academic_year": 2003,
                "webaddr": "https://holdout.edu",
                "has_human_legacy_source": False,
            },
        ]
    )
    historical_priority = pd.DataFrame(
        [
            {
                "unitid": 1,
                "priority_bucket": "prior_programmatic_accepted_needs_current_reverification",
                "prior_programmatic_accepted_rows": 3,
                "valid_human_legacy_rows": 0,
            },
            {
                "unitid": 3,
                "priority_bucket": "no_historical_programmatic_attempt_found",
                "prior_programmatic_accepted_rows": 0,
                "valid_human_legacy_rows": 0,
            },
        ]
    )

    selected = select_prior_valid_legacy_reverification_institutions(
        target_universe,
        historical_priority,
        pd.DataFrame(),
        public_count=2,
        private_count=0,
        min_target_rows=1,
        max_target_rows=10,
    )

    assert selected["unitid"].tolist() == [1, 2]
    assert "No Human Holdout U" not in set(selected["institution_name"])
    assert selected.iloc[0]["historical_priority_bucket"] == "prior_programmatic_accepted_needs_current_reverification"


def test_prior_valid_legacy_selection_excludes_completed_unitids() -> None:
    target_universe = pd.DataFrame(
        [
            {
                "unitid": 1,
                "institution_name": "Already Completed U",
                "sector_stream": "public",
                "state": "AA",
                "academic_year": 2002,
                "webaddr": "https://done.edu",
                "has_human_legacy_source": False,
            },
            {
                "unitid": 2,
                "institution_name": "Next Candidate U",
                "sector_stream": "public",
                "state": "BB",
                "academic_year": 2002,
                "webaddr": "https://next.edu",
                "has_human_legacy_source": True,
            },
        ]
    )
    historical_priority = pd.DataFrame(
        [
            {
                "unitid": 1,
                "priority_bucket": "prior_programmatic_accepted_needs_current_reverification",
                "prior_programmatic_accepted_rows": 5,
                "valid_human_legacy_rows": 0,
            }
        ]
    )

    selected = select_prior_valid_legacy_reverification_institutions(
        target_universe,
        historical_priority,
        pd.DataFrame(),
        public_count=2,
        private_count=0,
        min_target_rows=1,
        max_target_rows=10,
        exclude_unitids={1},
    )

    assert selected["unitid"].tolist() == [2]


def test_private_automated_and_llm_tabs_do_not_create_prior_valid_legacy_eligibility() -> None:
    target_universe = pd.DataFrame(
        [
            {
                "unitid": 10,
                "institution_name": "Automated Lead College",
                "sector_stream": "private",
                "state": "AL",
                "academic_year": 2002,
                "webaddr": "https://automated.example.edu",
                "has_human_legacy_source": False,
            },
            {
                "unitid": 10,
                "institution_name": "Automated Lead College",
                "sector_stream": "private",
                "state": "AL",
                "academic_year": 2003,
                "webaddr": "https://automated.example.edu",
                "has_human_legacy_source": False,
            },
        ]
    )
    raw_inputs = pd.DataFrame(
        [
            {
                "unitid": 10,
                "institution_name": "Automated Lead College",
                "sector": "private",
                "candidate_url": "https://lead.invalid/catalog-2002-2003.pdf",
                "catalog_year_start": 2002,
                "catalog_year_end": 2003,
                "candidate_generation_method": "historical_programmatic_lead",
                "candidate_source_type": "historical_programmatic_lead",
                "legacy_input_provenance": "historical_programmatic_lead",
                "source_query_or_root": "(Automated, 0121) Missing priva",
            },
            {
                "unitid": 10,
                "institution_name": "Automated Lead College",
                "sector": "private",
                "candidate_url": "https://llm-lead.invalid/catalog-2003.pdf",
                "catalog_year_start": 2003,
                "catalog_year_end": 2003,
                "candidate_generation_method": "imported_llm_candidate_lead",
                "candidate_source_type": "imported_llm_candidate_lead",
                "legacy_input_provenance": "imported_llm_candidate_lead",
                "source_query_or_root": "LLM Training Set",
            },
        ]
    )

    coverage = raw_legacy_coverage_summary(target_universe, raw_inputs)

    assert coverage.loc[coverage["unitid"].eq(10), "legacy_covered_years"].iloc[0] == 0
    with pytest.raises(RuntimeError, match="Prior-valid-legacy reverification selection found no eligible"):
        select_prior_valid_legacy_reverification_institutions(
            target_universe,
            pd.DataFrame(),
            raw_inputs,
            public_count=0,
            private_count=1,
            min_target_rows=1,
            max_target_rows=10,
        )


def test_private_automated_and_llm_tabs_can_enter_historical_lead_reconstruction_lane() -> None:
    target_universe = pd.DataFrame(
        [
            {
                "unitid": 11,
                "institution_name": "Lead Reconstruction College",
                "sector_stream": "private",
                "state": "LR",
                "academic_year": 2002,
                "webaddr": "https://leadrecon.example.edu",
                "has_human_legacy_source": False,
            },
            {
                "unitid": 11,
                "institution_name": "Lead Reconstruction College",
                "sector_stream": "private",
                "state": "LR",
                "academic_year": 2003,
                "webaddr": "https://leadrecon.example.edu",
                "has_human_legacy_source": False,
            },
        ]
    )
    raw_inputs = pd.DataFrame(
        [
            {
                "unitid": 11,
                "institution_name": "Lead Reconstruction College",
                "sector": "private",
                "candidate_url": "https://lead.invalid/catalog-2002-2003.pdf",
                "catalog_year_start": 2002,
                "catalog_year_end": 2003,
                "candidate_generation_method": "historical_programmatic_lead",
                "candidate_source_type": "historical_programmatic_lead",
                "legacy_input_provenance": "historical_programmatic_lead",
                "source_query_or_root": "(Automated, 0121) Missing priva",
            }
        ]
    )

    selected = select_historical_lead_source_reconstruction_institutions(
        target_universe,
        pd.DataFrame(),
        raw_inputs,
        public_count=0,
        private_count=1,
        min_target_rows=1,
        max_target_rows=10,
    )

    assert selected["unitid"].tolist() == [11]
    assert selected.iloc[0]["selection_mode"] == "historical_lead_source_reconstruction"
    assert selected.iloc[0]["historical_lead_bucket"] == "raw_historical_lead_input"
    assert selected.iloc[0]["historical_lead_covered_years"] == 2


def test_public_imported_llm_priority_bucket_can_enter_historical_lead_reconstruction_lane() -> None:
    target_universe = pd.DataFrame(
        [
            {
                "unitid": 12,
                "institution_name": "Public LLM Lead University",
                "sector_stream": "public",
                "state": "PL",
                "academic_year": 2002,
                "webaddr": "https://publicllm.example.edu",
                "has_human_legacy_source": False,
            }
        ]
    )
    historical_priority = pd.DataFrame(
        [
            {
                "unitid": 12,
                "priority_bucket": "imported_llm_candidate_lead_overlay",
                "imported_llm_candidate_lead_rows": 1,
                "valid_human_legacy_rows": 0,
                "prior_programmatic_accepted_rows": 0,
            }
        ]
    )

    selected = select_historical_lead_source_reconstruction_institutions(
        target_universe,
        historical_priority,
        pd.DataFrame(),
        public_count=1,
        private_count=0,
        min_target_rows=1,
        max_target_rows=10,
    )

    assert selected["unitid"].tolist() == [12]
    assert selected.iloc[0]["selection_mode"] == "historical_lead_source_reconstruction"
    assert selected.iloc[0]["historical_lead_bucket"] == "imported_llm_candidate_lead_overlay"


def test_automated_llm_lead_inputs_never_become_legacy_benchmark_or_human_provenance() -> None:
    target_panel = pd.DataFrame(
        [
            {
                "unitid": 13,
                "institution_name": "LLM Lead Guard College",
                "sector": "private",
                "state": "LG",
                "academic_year": 2002,
                "homepage_url": "https://llmguard.example.edu",
                "has_human_legacy_source": False,
            }
        ]
    )
    target_universe = pd.DataFrame(
        [
            {
                "unitid": 13,
                "institution_name": "LLM Lead Guard College",
                "sector_stream": "private",
                "state": "LG",
                "academic_year": 2002,
                "webaddr": "https://llmguard.example.edu",
                "has_human_legacy_source": False,
            }
        ]
    )
    raw_inputs = pd.DataFrame(
        [
            {
                "unitid": 13,
                "institution_name": "LLM Lead Guard College",
                "sector": "private",
                "candidate_url": "https://llm-lead.invalid/catalog-2002.pdf",
                "catalog_year_start": 2002,
                "catalog_year_end": 2002,
                "candidate_generation_method": "imported_llm_candidate_lead",
                "candidate_source_type": "imported_llm_candidate_lead",
                "source_query_or_root": "LLM Training Set",
            }
        ]
    )
    historical_memory = pd.DataFrame(
        [
            {
                "unitid": 13,
                "historical_priority_bucket": "valid_human_legacy",
                "valid_human_legacy_rows": 1,
            }
        ]
    )

    enriched = enrich_raw_legacy_with_historical_provenance(raw_inputs, historical_memory)
    candidates = raw_legacy_candidates_for_target(target_panel, enriched)
    [option] = candidate_options_for_row(
        row=target_panel.iloc[0],
        legacy_row=candidates.iloc[0],
        namespace="n",
        repo_root=Path.cwd(),
    )
    coverage = raw_legacy_coverage_summary(target_universe, enriched)

    assert enriched.iloc[0]["legacy_input_provenance"] == "imported_llm_candidate_lead"
    assert bool(enriched.iloc[0]["counts_as_legacy_coverage"]) is False
    assert coverage.loc[coverage["unitid"].eq(13), "legacy_covered_years"].iloc[0] == 0
    assert benchmark_rows_for_legacy_candidates(candidates) == []
    assert option["legacy_input_provenance"] == "imported_llm_candidate_lead"
    assert option["candidate_source_type"] == "imported_llm_candidate_lead"
    assert option["url_source_bucket"] == "historical_lead_input_url"
    assert bool(option["counts_as_legacy_coverage"]) is False


def test_workbook_default_coverage_true_does_not_override_imported_llm_priority() -> None:
    target_panel = pd.DataFrame(
        [
            {
                "unitid": 199184,
                "institution_name": "North Carolina School of the Arts",
                "sector": "public",
                "state": "NC",
                "academic_year": 2003,
                "homepage_url": "https://uncsa.edu",
                "has_human_legacy_source": False,
            }
        ]
    )
    target_universe = pd.DataFrame(
        [
            {
                "unitid": 199184,
                "institution_name": "North Carolina School of the Arts",
                "sector_stream": "public",
                "state": "NC",
                "academic_year": 2003,
                "webaddr": "https://uncsa.edu",
                "has_human_legacy_source": False,
            }
        ]
    )
    raw_inputs = pd.DataFrame(
        [
            {
                "unitid": 199184,
                "institution_name": "North Carolina School of the Arts",
                "sector": "public",
                "candidate_url": "https://www.uncsa.edu/bulletin/archived-bulletins/2003-combined-bulletin.pdf",
                "catalog_year_start": 2003,
                "catalog_year_end": 2004,
                "candidate_generation_method": "raw_public_legacy_workbook_url",
                "candidate_source_type": "legacy_input_url",
                "legacy_input_provenance": "unknown_legacy_input",
                "counts_as_legacy_coverage": True,
                "source_query_or_root": "Sheet1",
            }
        ]
    )
    historical_memory = pd.DataFrame(
        [
            {
                "unitid": 199184,
                "historical_priority_bucket": "imported_llm_candidate_lead_overlay",
                "imported_llm_candidate_lead_rows": 18,
            }
        ]
    )

    enriched = enrich_raw_legacy_with_historical_provenance(raw_inputs, historical_memory)
    candidates = raw_legacy_candidates_for_target(target_panel, enriched)
    coverage = raw_legacy_coverage_summary(target_universe, enriched)

    assert enriched.iloc[0]["legacy_input_provenance"] == "imported_llm_candidate_lead"
    assert bool(enriched.iloc[0]["counts_as_legacy_coverage"]) is False
    assert coverage.loc[coverage["unitid"].eq(199184), "legacy_covered_years"].iloc[0] == 0
    assert benchmark_rows_for_legacy_candidates(candidates) == []


def test_curated_private_legacy_inputs_still_select_prior_valid_reverification() -> None:
    target_universe = pd.DataFrame(
        [
            {
                "unitid": 14,
                "institution_name": "Curated Legacy College",
                "sector_stream": "private",
                "state": "CL",
                "academic_year": 2002,
                "webaddr": "https://curated.example.edu",
                "has_human_legacy_source": False,
            }
        ]
    )
    raw_inputs = pd.DataFrame(
        [
            {
                "unitid": 14,
                "institution_name": "Curated Legacy College",
                "sector": "private",
                "candidate_url": "https://curated.example.edu/catalog-2002.pdf",
                "catalog_year_start": 2002,
                "catalog_year_end": 2002,
                "candidate_generation_method": "raw_private_legacy_workbook_url",
                "candidate_source_type": "legacy_input_url",
            }
        ]
    )

    coverage = raw_legacy_coverage_summary(target_universe, raw_inputs)
    selected = select_prior_valid_legacy_reverification_institutions(
        target_universe,
        pd.DataFrame(),
        raw_inputs,
        public_count=0,
        private_count=1,
        min_target_rows=1,
        max_target_rows=10,
    )

    assert coverage.loc[coverage["unitid"].eq(14), "legacy_covered_years"].iloc[0] == 1
    assert selected["unitid"].tolist() == [14]
    assert selected.iloc[0]["historical_priority_bucket"] == "valid_human_legacy"


def test_load_excluded_unitids_reads_unitid_column(tmp_path: Path) -> None:
    exclusion = tmp_path / "completed.csv"
    pd.DataFrame([{"unitid": 10}, {"unitid": "11"}, {"unitid": ""}]).to_csv(exclusion, index=False)

    assert load_excluded_unitids(exclusion, tmp_path) == {10, 11}


def test_high_legacy_coverage_selection_counts_unique_unitids() -> None:
    target_universe = pd.DataFrame(
        [
            {
                "unitid": 1,
                "institution_name": "ALPHA UNIVERSITY",
                "sector_stream": "public",
                "state": "AA",
                "academic_year": 2002,
                "webaddr": "https://alpha.edu",
                "has_human_legacy_source": False,
            },
            {
                "unitid": 1,
                "institution_name": "Alpha University",
                "sector_stream": "public",
                "state": "AA",
                "academic_year": 2003,
                "webaddr": "https://alpha.edu",
                "has_human_legacy_source": False,
            },
            {
                "unitid": 2,
                "institution_name": "Beta University",
                "sector_stream": "public",
                "state": "BB",
                "academic_year": 2002,
                "webaddr": "https://beta.edu",
                "has_human_legacy_source": False,
            },
            {
                "unitid": 2,
                "institution_name": "Beta University",
                "sector_stream": "public",
                "state": "BB",
                "academic_year": 2003,
                "webaddr": "https://beta.edu",
                "has_human_legacy_source": False,
            },
        ]
    )
    raw_legacy = pd.DataFrame(
        [
            {
                "unitid": 1,
                "institution_name": "Alpha University",
                "sector": "public",
                "candidate_url": "https://alpha.edu/catalog-2002-2003.pdf",
                "catalog_year_start": 2002,
                "catalog_year_end": 2003,
            },
            {
                "unitid": 2,
                "institution_name": "Beta University",
                "sector": "public",
                "candidate_url": "https://beta.edu/catalog-2002-2003.pdf",
                "catalog_year_start": 2002,
                "catalog_year_end": 2003,
            },
        ]
    )

    selected = select_high_legacy_coverage_institutions(
        target_universe,
        raw_legacy,
        public_count=2,
        private_count=0,
        min_target_rows=1,
        max_target_rows=10,
    )

    assert selected["unitid"].tolist() == [1, 2]
    assert selected["unitid"].is_unique


def test_build_step1_inputs_closes_rows_when_source_review_budget_exceeded(monkeypatch, tmp_path: Path) -> None:
    target_panel = pd.DataFrame(
        [
            {
                "unitid": 123,
                "institution_name": "Example State University",
                "sector": "public",
                "state": "EX",
                "academic_year": 2002,
                "homepage_url": "https://example.edu",
                "has_human_legacy_source": False,
            }
        ]
    )
    current_panel = pd.DataFrame(
        [
            {
                "unitid": 123,
                "target_year": 2002,
                "sector": "public",
                "best_url": "https://example.edu/catalog-2002.pdf",
                "best_url_source": "current_production_discovery",
                "catalog_year_start": 2002,
                "catalog_year_end": 2002,
                "candidate_link_text": "Catalog 2002",
                "candidate_evidence_source": "current production discovery",
                "archive_url": "https://example.edu/catalogs/",
                "_current_run_file": "artifacts/PIPELINE_OUTPUTS/01_url_discovery/current_run/current.csv",
                "_selected_panel_file": "artifacts/PIPELINE_OUTPUTS/01_url_discovery/current_run/current.csv",
            }
        ]
    )

    def slow_failed_retrieve(*args, **kwargs):
        time.sleep(0.12)
        return (
            args[0],
            {"retrieval_status": "error", "error_type": "simulated_dead_source", "body": b"", "links": [], "link_records": []},
            "direct_retrieval_failed_no_wayback_recovery",
            "",
        )

    monkeypatch.setattr(
        "course_policy.step1_proof_to_scale_url_production.current_panel_for_targets",
        lambda *args, **kwargs: current_panel,
    )
    monkeypatch.setattr(
        "course_policy.step1_proof_to_scale_url_production.source_family_gap_fill_lookup",
        lambda *args, **kwargs: {
            (123, 2002): [
                {
                    "unitid": 123,
                    "institution_name": "Example State University",
                    "sector": "public",
                    "state": "EX",
                    "academic_year": 2002,
                    "candidate_url": "https://example.edu/catalog-2002-alt.pdf",
                    "candidate_rank": 2,
                    "candidate_generation_method": "same_institution_source_family_gap_fill",
                    "candidate_source_file": "current_run_discovery_output",
                    "candidate_source_type": "same_institution_source_family_gap_fill",
                    "source_query_or_root": "https://example.edu/catalog-2002.pdf",
                    "candidate_generated_at": "budget_test",
                    "url_source_bucket": "same_institution_source_family_gap_fill",
                    "catalog_year_start": 2002,
                    "catalog_year_end": 2002,
                    "candidate_link_text": "alternate catalog",
                    "candidate_evidence_source": "generated from same-institution seed",
                }
            ]
        },
    )
    monkeypatch.setattr(
        "course_policy.step1_proof_to_scale_url_production.retrieve_candidate_with_wayback_recovery",
        slow_failed_retrieve,
    )

    input_dir = build_step1_inputs(
        tmp_path,
        target_panel=target_panel,
        sectors=["public"],
        namespace="budget_test",
        chunk_id="budget_test_chunk",
        release_id="budget_test_release",
        input_dir=tmp_path / "inputs",
        timeout_seconds=1,
        max_source_bytes=1000,
        source_review_row_timeout_seconds=0.01,
    )

    review = pd.read_csv(input_dir / "source_review_log.csv")
    assert "reject_dead_or_unretrievable" in set(review["review_decision"])
    budget_rows = review.loc[review["review_decision"].eq("reject_source_review_budget_exceeded")]
    assert len(budget_rows) == 1
    assert budget_rows.iloc[0]["retrieval_status"] == "not_retrieved_source_review_budget_exceeded"
    assert "after reviewing 1 candidate(s)" in budget_rows.iloc[0]["review_reason"]


def test_validated_prior_human_thin_evidence_routes_to_text_validation(monkeypatch, tmp_path: Path) -> None:
    target_panel = pd.DataFrame(
        [
            {
                "unitid": 901,
                "institution_name": "Prior Human University",
                "sector": "public",
                "state": "PH",
                "academic_year": 2002,
                "homepage_url": "https://priorhuman.edu",
                "has_human_legacy_source": True,
            }
        ]
    )
    raw_legacy = pd.DataFrame(
        [
            {
                "unitid": 901,
                "institution_name": "Prior Human University",
                "sector": "public",
                "candidate_url": "https://legacy-cdn.example.org/catalog-2002.pdf",
                "catalog_year_start": 2002,
                "catalog_year_end": 2002,
                "legacy_input_provenance": "validated_human_legacy",
            }
        ]
    )
    monkeypatch.setattr(
        "course_policy.step1_proof_to_scale_url_production.current_panel_for_targets",
        lambda *args, **kwargs: pd.DataFrame(columns=["unitid", "target_year", "best_url", "sector"]),
    )
    monkeypatch.setattr(
        "course_policy.step1_proof_to_scale_url_production.retrieve_candidate_with_wayback_recovery",
        lambda *args, **kwargs: (
            args[0],
            {
                "retrieval_status": "retrieved_truncated",
                "body": b"",
                "content_type": "application/pdf",
                "page_title": "Catalog 2002",
                "final_url": args[0],
                "sha256": "thin",
                "link_records": [],
            },
            "direct_retrieval",
            "",
        ),
    )

    input_dir = build_step1_inputs(
        tmp_path,
        target_panel=target_panel,
        sectors=["public"],
        namespace="prior_human_thin",
        chunk_id="prior_human_thin_chunk",
        release_id=None,
        input_dir=tmp_path / "inputs",
        timeout_seconds=1,
        max_source_bytes=1000,
        raw_legacy=raw_legacy,
        include_raw_legacy_candidates=True,
    )

    review = pd.read_csv(input_dir / "source_review_log.csv")
    row = review.iloc[0]
    assert row["review_decision"] == "needs_text_validation"
    assert row["legacy_input_provenance"] == "validated_human_legacy"
    assert row["source_type_confirmed"] == True
    assert row["year_coverage_confirmed"] == True
    assert "Step 2 text extraction/final validation" in row["review_reason"]


def test_historical_valid_human_priority_enriches_raw_legacy_for_text_validation(monkeypatch, tmp_path: Path) -> None:
    inventory_dir = tmp_path / "artifacts/AUDIT_TRAILS/url_discovery_historical_inventory"
    inventory_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "unitid": 903,
                "institution_name": "Production Prior Human University",
                "priority_bucket": "valid_human_legacy",
                "valid_human_legacy_rows": 1,
                "prior_programmatic_accepted_rows": 0,
                "imported_llm_candidate_lead_rows": 0,
            }
        ]
    ).to_csv(inventory_dir / "institution_priority_buckets.csv", index=False)
    target_panel = pd.DataFrame(
        [
            {
                "unitid": 903,
                "institution_name": "Production Prior Human University",
                "sector": "private",
                "state": "PH",
                "academic_year": 2002,
                "homepage_url": "https://priorhuman.example.edu",
                "has_human_legacy_source": False,
            }
        ]
    )
    raw_legacy = pd.DataFrame(
        [
            {
                "unitid": 903,
                "institution_name": "Production Prior Human University",
                "sector": "private",
                "candidate_url": "https://legacy-source.invalid/catalog-2002.pdf",
                "catalog_year_start": 2002,
                "catalog_year_end": 2002,
                "candidate_generation_method": "raw_private_legacy_workbook_url",
                "candidate_source_type": "legacy_input_url",
            }
        ]
    )
    monkeypatch.setattr(
        "course_policy.step1_proof_to_scale_url_production.current_panel_for_targets",
        lambda *args, **kwargs: pd.DataFrame(columns=["unitid", "target_year", "best_url", "sector"]),
    )
    monkeypatch.setattr(
        "course_policy.step1_proof_to_scale_url_production.retrieve_candidate_with_wayback_recovery",
        lambda *args, **kwargs: (
            args[0],
            {
                "retrieval_status": "retrieved_truncated",
                "body": b"",
                "content_type": "application/pdf",
                "page_title": "Catalog 2002",
                "final_url": args[0],
                "sha256": "thin-valid-human",
                "link_records": [],
            },
            "direct_retrieval",
            "",
        ),
    )

    input_dir = build_step1_inputs(
        tmp_path,
        target_panel=target_panel,
        sectors=["private"],
        namespace="historical_valid_human_thin",
        chunk_id="historical_valid_human_chunk",
        release_id=None,
        input_dir=tmp_path / "inputs",
        timeout_seconds=1,
        max_source_bytes=1000,
        raw_legacy=raw_legacy,
        include_raw_legacy_candidates=True,
    )

    review = pd.read_csv(input_dir / "source_review_log.csv")
    candidate = pd.read_csv(input_dir / "candidate_url_ledger.csv").iloc[0]
    row = review.iloc[0]
    assert candidate["legacy_input_provenance"] == "validated_human_legacy"
    assert candidate["candidate_source_type"] == "legacy_input_url"
    assert "human" not in candidate["candidate_generation_method"]
    assert row["review_decision"] == "needs_text_validation"
    assert row["legacy_input_provenance"] == "validated_human_legacy"


def test_imported_llm_priority_does_not_presume_prior_human_text_validation(monkeypatch, tmp_path: Path) -> None:
    inventory_dir = tmp_path / "artifacts/AUDIT_TRAILS/url_discovery_historical_inventory"
    inventory_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "unitid": 904,
                "institution_name": "Production LLM Lead University",
                "priority_bucket": "imported_llm_candidate_lead_overlay",
                "valid_human_legacy_rows": 0,
                "prior_programmatic_accepted_rows": 0,
                "imported_llm_candidate_lead_rows": 1,
            }
        ]
    ).to_csv(inventory_dir / "institution_priority_buckets.csv", index=False)
    target_panel = pd.DataFrame(
        [
            {
                "unitid": 904,
                "institution_name": "Production LLM Lead University",
                "sector": "private",
                "state": "LL",
                "academic_year": 2003,
                "homepage_url": "https://llmlead.example.edu",
                "has_human_legacy_source": False,
            }
        ]
    )
    raw_legacy = pd.DataFrame(
        [
            {
                "unitid": 904,
                "institution_name": "Production LLM Lead University",
                "sector": "private",
                "candidate_url": "https://legacy-source.invalid/catalog-2003.pdf",
                "catalog_year_start": 2003,
                "catalog_year_end": 2003,
                "candidate_generation_method": "raw_private_legacy_workbook_url",
                "candidate_source_type": "legacy_input_url",
            }
        ]
    )
    monkeypatch.setattr(
        "course_policy.step1_proof_to_scale_url_production.current_panel_for_targets",
        lambda *args, **kwargs: pd.DataFrame(columns=["unitid", "target_year", "best_url", "sector"]),
    )
    monkeypatch.setattr(
        "course_policy.step1_proof_to_scale_url_production.retrieve_candidate_with_wayback_recovery",
        lambda *args, **kwargs: (
            args[0],
            {
                "retrieval_status": "retrieved_truncated",
                "body": b"",
                "content_type": "application/pdf",
                "page_title": "Catalog 2003",
                "final_url": args[0],
                "sha256": "thin-llm",
                "link_records": [],
            },
            "direct_retrieval",
            "",
        ),
    )

    input_dir = build_step1_inputs(
        tmp_path,
        target_panel=target_panel,
        sectors=["private"],
        namespace="historical_llm_thin",
        chunk_id="historical_llm_chunk",
        release_id=None,
        input_dir=tmp_path / "inputs",
        timeout_seconds=1,
        max_source_bytes=1000,
        raw_legacy=raw_legacy,
        include_raw_legacy_candidates=True,
    )

    review = pd.read_csv(input_dir / "source_review_log.csv")
    candidate = pd.read_csv(input_dir / "candidate_url_ledger.csv").iloc[0]
    row = review.iloc[0]
    assert candidate["legacy_input_provenance"] == "imported_llm_candidate_lead"
    assert row["legacy_input_provenance"] == "imported_llm_candidate_lead"
    assert row["review_decision"] != "needs_text_validation"
    assert row["review_decision"] == "institution_not_confirmed_from_current_evidence"


def test_wrong_institution_evidence_is_confirmed_wrong_institution(monkeypatch, tmp_path: Path) -> None:
    target_panel = pd.DataFrame(
        [
            {
                "unitid": 902,
                "institution_name": "Target College",
                "sector": "private",
                "state": "TC",
                "academic_year": 2002,
                "homepage_url": "https://target.edu",
                "has_human_legacy_source": False,
            }
        ]
    )
    raw_legacy = pd.DataFrame(
        [
            {
                "unitid": 902,
                "institution_name": "Target College",
                "sector": "private",
                "candidate_url": "https://other.edu/catalog-2002.html",
                "catalog_year_start": 2002,
                "catalog_year_end": 2002,
                "legacy_input_provenance": "unknown_legacy_input",
            }
        ]
    )
    wrong_text = (
        "Other State University Undergraduate Catalog 2002. "
        "Other State University policies, academic rules, course catalog, and degree requirements. "
        "This source repeatedly identifies Other State University and no other campus. "
    ) * 3
    monkeypatch.setattr(
        "course_policy.step1_proof_to_scale_url_production.current_panel_for_targets",
        lambda *args, **kwargs: pd.DataFrame(columns=["unitid", "target_year", "best_url", "sector"]),
    )
    monkeypatch.setattr(
        "course_policy.step1_proof_to_scale_url_production.retrieve_candidate_with_wayback_recovery",
        lambda *args, **kwargs: (
            args[0],
            {
                "retrieval_status": "retrieved",
                "body": wrong_text.encode("utf-8"),
                "content_type": "text/html",
                "page_title": "Other State University Catalog",
                "final_url": args[0],
                "sha256": "wrong",
                "link_records": [],
            },
            "direct_retrieval",
            "",
        ),
    )

    input_dir = build_step1_inputs(
        tmp_path,
        target_panel=target_panel,
        sectors=["private"],
        namespace="wrong_institution",
        chunk_id="wrong_institution_chunk",
        release_id=None,
        input_dir=tmp_path / "inputs",
        timeout_seconds=1,
        max_source_bytes=1000,
        raw_legacy=raw_legacy,
        include_raw_legacy_candidates=True,
    )

    review = pd.read_csv(input_dir / "source_review_log.csv")
    assert review.iloc[0]["review_decision"] == "confirmed_wrong_institution"


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


def test_historical_precheck_drops_direct_url_inventory_fields(tmp_path: Path) -> None:
    inventory_dir = tmp_path / "artifacts/AUDIT_TRAILS/url_discovery_historical_inventory"
    inventory_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "unitid": 321,
                "institution_name": "Leak Test University",
                "priority_bucket": "prior_programmatic_accepted_needs_current_reverification",
                "prior_programmatic_accepted_rows": 1,
                "url": "https://leak.example.edu/catalog-2002.pdf",
                "candidate_url": "https://leak.example.edu/catalog-2003.pdf",
                "accepted_source_url": "https://leak.example.edu/catalog-2004.pdf",
            }
        ]
    ).to_csv(inventory_dir / "institution_priority_buckets.csv", index=False)
    target_panel = pd.DataFrame(
        [
            {
                "unitid": 321,
                "institution_name": "Leak Test University",
                "academic_year": 2002,
                "has_human_legacy_source": False,
            }
        ]
    )

    precheck = build_historical_case_precheck(tmp_path, target_panel, "precheck_test_namespace")

    assert {"url", "candidate_url", "accepted_source_url"}.isdisjoint(precheck.columns)
    combined_text = " ".join(str(value) for value in precheck.iloc[0].tolist())
    assert "https://leak.example.edu" not in combined_text


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


def test_run_stop_report_written_on_controlled_discovery_failure(monkeypatch, tmp_path: Path) -> None:
    target_universe = pd.DataFrame(
        [
            {
                "unitid": 700,
                "institution_name": "Stop Report U",
                "sector_stream": "public",
                "state": "SR",
                "academic_year": 2002,
                "webaddr": "https://stop.example.edu",
                "has_human_legacy_source": False,
            },
            {
                "unitid": 700,
                "institution_name": "Stop Report U",
                "sector_stream": "public",
                "state": "SR",
                "academic_year": 2003,
                "webaddr": "https://stop.example.edu",
                "has_human_legacy_source": False,
            },
        ]
    )
    historical_priority = pd.DataFrame(
        [
            {
                "unitid": 700,
                "priority_bucket": "prior_programmatic_accepted_needs_current_reverification",
                "prior_programmatic_accepted_rows": 2,
            }
        ]
    )

    monkeypatch.setattr(
        "course_policy.step1_proof_to_scale_url_production.load_target_panel_universe",
        lambda *args, **kwargs: target_universe,
    )
    monkeypatch.setattr(
        "course_policy.step1_proof_to_scale_url_production.load_raw_legacy_url_rows",
        lambda *args, **kwargs: pd.DataFrame(),
    )
    monkeypatch.setattr(
        "course_policy.step1_proof_to_scale_url_production.load_historical_priority_buckets",
        lambda *args, **kwargs: historical_priority,
    )

    def fail_discovery(*args, **kwargs):
        raise RuntimeError("controlled discovery failure")

    monkeypatch.setattr("course_policy.step1_proof_to_scale_url_production.run_discovery_for_sector", fail_discovery)

    with pytest.raises(RuntimeError, match="controlled discovery failure"):
        run_proof_to_scale(
            tmp_path,
            namespace="stop_report_test",
            chunk_id="stop_report_chunk",
            release_id=None,
            selection_mode="prior_valid_legacy_reverification",
            institution_count=1,
            public_institution_count=1,
            private_institution_count=0,
            min_target_rows=1,
            max_target_rows=10,
            timeout_seconds=1,
            max_root_candidates_per_institution=1,
            max_archive_pages_per_institution=1,
            max_workers=1,
            run_inferred_year_rescue=False,
            run_archive_expansion=False,
            run_wayback_cdx_rescue=False,
            run_ai_year_gap_rescue=False,
            max_api_cases=None,
            include_raw_legacy_candidates=False,
            min_ready_rate=0.0,
            min_sector_ready_rate=0.0,
            api_web_rescue_mode="not_run",
            api_web_rescue_status="not_run",
            api_web_rescue_reason="",
            build_release=False,
            source_review_row_timeout_seconds=1.0,
        )

    input_dir = tmp_path / "artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_inputs/stop_report_test"
    report = input_dir / "RUN_STOP_REPORT.md"
    assert report.exists()
    text = report.read_text(encoding="utf-8")
    assert "running public discovery" in text
    assert "controlled discovery failure" in text
    assert "No valid `production_chunk_*` or `production_release_*` was produced" in text
    assert (input_dir / "target_panel.csv").exists()
    assert (input_dir / "source_review_log.csv").exists()
    assert list(pd.read_csv(input_dir / "source_review_log.csv").columns)[:3] == [
        "unitid",
        "institution_name",
        "sector",
    ]


def test_run_proof_to_scale_applies_prior_valid_exclusion_file(monkeypatch, tmp_path: Path) -> None:
    target_universe = pd.DataFrame(
        [
            {
                "unitid": 1,
                "institution_name": "Already Completed U",
                "sector_stream": "public",
                "state": "AA",
                "academic_year": 2002,
                "webaddr": "https://done.example.edu",
                "has_human_legacy_source": False,
            },
            {
                "unitid": 2,
                "institution_name": "Next Candidate U",
                "sector_stream": "public",
                "state": "BB",
                "academic_year": 2002,
                "webaddr": "https://next.example.edu",
                "has_human_legacy_source": True,
            },
        ]
    )
    historical_priority = pd.DataFrame(
        [
            {
                "unitid": 1,
                "priority_bucket": "prior_programmatic_accepted_needs_current_reverification",
                "prior_programmatic_accepted_rows": 5,
            }
        ]
    )
    exclusion = tmp_path / "completed_batch.csv"
    pd.DataFrame([{"unitid": 1}]).to_csv(exclusion, index=False)
    monkeypatch.setattr(
        "course_policy.step1_proof_to_scale_url_production.load_target_panel_universe",
        lambda *args, **kwargs: target_universe,
    )
    monkeypatch.setattr(
        "course_policy.step1_proof_to_scale_url_production.load_raw_legacy_url_rows",
        lambda *args, **kwargs: pd.DataFrame(),
    )
    monkeypatch.setattr(
        "course_policy.step1_proof_to_scale_url_production.load_historical_priority_buckets",
        lambda *args, **kwargs: historical_priority,
    )

    def fail_discovery(*args, **kwargs):
        raise RuntimeError("stop after selection")

    monkeypatch.setattr("course_policy.step1_proof_to_scale_url_production.run_discovery_for_sector", fail_discovery)

    with pytest.raises(RuntimeError, match="stop after selection"):
        run_proof_to_scale(
            tmp_path,
            namespace="exclude_file_test",
            chunk_id="exclude_file_chunk",
            release_id=None,
            selection_mode="prior_valid_legacy_reverification",
            institution_count=1,
            public_institution_count=2,
            private_institution_count=0,
            min_target_rows=1,
            max_target_rows=10,
            timeout_seconds=1,
            max_root_candidates_per_institution=1,
            max_archive_pages_per_institution=1,
            max_workers=1,
            run_inferred_year_rescue=False,
            run_archive_expansion=False,
            run_wayback_cdx_rescue=False,
            run_ai_year_gap_rescue=False,
            max_api_cases=None,
            include_raw_legacy_candidates=False,
            min_ready_rate=0.0,
            min_sector_ready_rate=0.0,
            api_web_rescue_mode="not_run",
            api_web_rescue_status="not_run",
            api_web_rescue_reason="",
            build_release=False,
            source_review_row_timeout_seconds=1.0,
            exclude_unitids_file=exclusion,
        )

    selected = pd.read_csv(
        tmp_path / "artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_selection/exclude_file_test/selected_institutions.csv"
    )
    target_panel = pd.read_csv(
        tmp_path / "artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_inputs/exclude_file_test/target_panel.csv"
    )
    config = (tmp_path / "artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_inputs/exclude_file_test/run_config.json").read_text(
        encoding="utf-8"
    )
    assert selected["unitid"].tolist() == [2]
    assert target_panel["unitid"].tolist() == [2]
    assert '"excluded_unitid_count": 1' in config


def test_partial_ledgers_are_preserved_when_source_review_fails(monkeypatch, tmp_path: Path) -> None:
    target_panel = pd.DataFrame(
        [
            {
                "unitid": 800,
                "institution_name": "Partial Ledger U",
                "sector": "public",
                "state": "PL",
                "academic_year": 2002,
                "homepage_url": "https://partial.example.edu",
                "has_human_legacy_source": False,
            }
        ]
    )
    current_panel = pd.DataFrame(
        [
            {
                "unitid": 800,
                "target_year": 2002,
                "sector": "public",
                "best_url": "https://partial.example.edu/catalog-2002.pdf",
                "best_url_source": "current_production_discovery",
                "catalog_year_start": 2002,
                "catalog_year_end": 2002,
                "candidate_link_text": "Catalog 2002",
                "candidate_evidence_source": "current production discovery",
                "archive_url": "https://partial.example.edu/catalogs/",
                "_current_run_file": "artifacts/PIPELINE_OUTPUTS/01_url_discovery/current_run/current.csv",
                "_selected_panel_file": "artifacts/PIPELINE_OUTPUTS/01_url_discovery/current_run/current.csv",
            }
        ]
    )

    monkeypatch.setattr(
        "course_policy.step1_proof_to_scale_url_production.current_panel_for_targets",
        lambda *args, **kwargs: current_panel,
    )

    def fail_retrieval(*args, **kwargs):
        raise RuntimeError("controlled source-review failure")

    monkeypatch.setattr(
        "course_policy.step1_proof_to_scale_url_production.retrieve_candidate_with_wayback_recovery",
        fail_retrieval,
    )

    input_dir = tmp_path / "inputs"
    with pytest.raises(RuntimeError, match="controlled source-review failure"):
        build_step1_inputs(
            tmp_path,
            target_panel=target_panel,
            sectors=["public"],
            namespace="partial_ledger_test",
            chunk_id="partial_ledger_chunk",
            release_id=None,
            input_dir=input_dir,
            timeout_seconds=1,
            max_source_bytes=1000,
        )

    candidate_ledger = pd.read_csv(input_dir / "candidate_url_ledger.csv")
    assert candidate_ledger["candidate_url"].tolist() == ["https://partial.example.edu/catalog-2002.pdf"]
    assert (input_dir / "source_review_log.csv").exists()
    assert {"unitid", "academic_year", "review_decision"}.issubset(pd.read_csv(input_dir / "source_review_log.csv").columns)
    assert (input_dir / "source_evidence_manifest.csv").exists()
    assert (input_dir / "historical_case_precheck.csv").exists()
    assert (input_dir / "run_config.json").exists()
