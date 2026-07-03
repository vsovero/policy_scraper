import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from course_policy.production_release_url_stage import build_url_stage_release_package


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_chunk(
    root: Path,
    *,
    benchmark_miss: bool = False,
    failing_requirement: bool = False,
    include_ai_provenance: bool = False,
) -> None:
    chunk_dir = root / "artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_chunks/production_chunk_test"
    audit_dir = root / "artifacts/AUDIT_TRAILS/url_discovery_production_chunk_test"
    stream_dir = root / "artifacts/policy_data_internal/review/streams/public_clean_no_legacy_holdout/test_namespace"
    ai_logs = root / "artifacts/policy_data_internal/logs/ai"
    external_review_path = root.parent / "external_review_source.csv"
    chunk_dir.mkdir(parents=True)
    (audit_dir / "code_snapshot/src/course_policy").mkdir(parents=True)
    (audit_dir / "current_run_reattempt_cached_text").mkdir(parents=True)
    source_review_file = root / "artifacts/AUDIT_TRAILS/url_discovery_production_chunk_test/current_run_reattempt_source_review.csv"
    candidate_source_file = "explicit_smoke_seed"
    candidate_method = "current_run_prior_programmatic_reattempt"
    api_mode = ""
    api_status = ""
    if include_ai_provenance:
        stream_dir.mkdir(parents=True)
        (ai_logs / "raw_responses").mkdir(parents=True)
        (ai_logs / "parsed_responses").mkdir(parents=True)
        call_id = "public_clean_no_legacy_holdout_clean_no_legacy_year_gap_web_discovery_test"
        prompt = ai_logs / "parsed_responses" / f"{call_id}_prompt.json"
        raw = ai_logs / "raw_responses" / f"{call_id}.json"
        parsed = ai_logs / "parsed_responses" / f"{call_id}.json"
        prompt.write_text(
            json.dumps(
                {
                    "prompt": "find catalog",
                    "required_json_schema": {
                        "direct_catalog_urls": [],
                        "root_candidates": [],
                        "missing_years_not_found": [],
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        raw.write_text(
            json.dumps(
                {
                    "id": "resp_test",
                    "model": "gpt-test-2026-07-01",
                    "created_at": 1782939856.0,
                    "completed_at": 1782939871.0,
                    "status": "completed",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        parsed.write_text('{"direct_catalog_urls":[]}\n', encoding="utf-8")
        pd.DataFrame(
            [
                {
                    "unitid": 1,
                    "institution_name": "Example University",
                    "api_validation_status": "parsed",
                    "api_prompt_version": "clean_no_legacy_year_gap_web_discovery_v1",
                    "api_log_call_id": call_id,
                    "api_prompt_path": str(prompt),
                    "api_raw_response_path": str(raw),
                    "api_parsed_response_path": str(parsed),
                }
            ]
        ).to_csv(stream_dir / "ai_year_gap_triage.csv", index=False)
        pd.DataFrame([{"unitid": 1, "target_year": 2002, "best_url": "https://example.edu/catalog.pdf"}]).to_csv(
            stream_dir / "ai_year_gap_year_panel.csv",
            index=False,
        )
        for name in ["ai_year_gap_cases.csv", "ai_year_gap_status.csv", "ai_year_gap_verified_roots.csv"]:
            pd.DataFrame([{"unitid": 1, "institution_name": "Example University"}]).to_csv(stream_dir / name, index=False)
        candidate_source_file = str(stream_dir / "ai_year_gap_year_panel.csv")
        candidate_method = "ai_year_gap_direct_catalog_url"
        api_mode = "live_or_cached_ai_year_gap_rescue"
        api_status = "attempted_by_current_production_command"

    pd.DataFrame(
        [
            {
                "unitid": 1,
                "institution_name": "Example University",
                "sector": "private",
                "state": "CA",
                "academic_year": 2002,
                "ready_for_text_extraction": True,
                "url_status": "current_run_reattempt_ready",
                "url_status_reason": "Accepted.",
                "url_for_text_extraction": "https://example.edu/catalog.pdf",
                "production_url_source": "current_run_reverified_prior_programmatic",
                "candidate_url": "https://example.edu/catalog.pdf",
                "candidate_generation_method": candidate_method,
                "candidate_source_file": candidate_source_file,
                "source_review_file": str(
                    source_review_file
                ),
                "api_web_rescue_mode": api_mode,
                "api_web_rescue_status": api_status,
                "source_opened": True,
                "retrieval_status": "retrieved",
                "http_status": 200,
                "final_url_after_redirect": "https://example.edu/catalog.pdf",
                "institution_match_confirmed": True,
                "campus_or_unitid_match_confirmed": True,
                "source_scope_confirmed": True,
                "source_type_confirmed": True,
                "year_coverage_confirmed": True,
                "archive_child_links_checked": False,
                "gap_fill_search_completed": True,
                "panel_consistency_confirmed": True,
                "review_decision": "accept_current_run_source_review",
                "review_reason": "Opened exact catalog.",
                "reviewed_by": "codex_source_review_with_retrieval_evidence",
                "reviewed_at": "2026-06-30T00:00:00+00:00",
            },
            {
                "unitid": 1,
                "institution_name": "Example University",
                "sector": "private",
                "state": "CA",
                "academic_year": 2003,
                "ready_for_text_extraction": False,
                "url_status": "no_candidate_found",
                "url_status_reason": "No source found.",
                "unresolved_reason": "No target-year source found after bounded search.",
            },
        ]
    ).to_csv(chunk_dir / "OUTPUT_urls_for_text_extraction.csv", index=False)
    pd.DataFrame(
        [
            {
                "run_id": "production_chunk_test",
                "run_type": "production_chunk",
                "unitid": 1,
                "institution_name": "Example University",
                "sector": "private",
                "state": "CA",
                "academic_year": 2002,
                "accepted_source_url": "https://example.edu/catalog.pdf",
                "source_type": "catalog_pdf",
                "provenance_type": "manual_review",
                "review_file": str(
                    source_review_file
                ),
                "review_decision": "accept_current_run_source_review",
                "review_reason": "Opened exact catalog.",
                "reviewed_by": "codex_source_review_with_retrieval_evidence",
                "reviewed_at": "2026-06-30T00:00:00+00:00",
                "evidence_hash_or_cache_path": (
                    f"abc123 {external_review_path}"
                ),
                "candidate_url": "https://example.edu/catalog.pdf",
                "retrieval_status": "retrieved",
                "http_status": 200,
                "final_url_after_redirect": "https://example.edu/catalog.pdf",
                "source_opened": True,
                "institution_match_confirmed": True,
                "source_scope_confirmed": True,
                "source_type_confirmed": True,
                "year_coverage_confirmed": True,
                "panel_consistency_confirmed": True,
            }
        ]
    ).to_csv(chunk_dir / "OUTPUT_source_ledger_delta.csv", index=False)
    pd.DataFrame(
        [
            {
                "run_id": "production_chunk_test",
                "unitid": 1,
                "institution_name": "Example University",
                "academic_year": 2003,
                "url_status": "no_candidate_found",
                "unresolved_reason": "No target-year source found after bounded search.",
            }
        ]
    ).to_csv(chunk_dir / "UNRESOLVED_ROWS.csv", index=False)
    pd.DataFrame(
        [
            {
                "benchmark_group": "prior_programmatic_audit",
                "unitid": 1,
                "academic_year": 2002,
                "benchmark_recovery_status": "recovered_by_current_chunk",
            }
        ]
    ).to_csv(chunk_dir / "BENCHMARK_RECOVERY.csv", index=False)
    pd.DataFrame(
        [{"benchmark_group": "prior_programmatic_audit", "unitid": 1, "academic_year": 2004}]
        if benchmark_miss
        else [],
    ).to_csv(chunk_dir / "BENCHMARK_MISSES.csv", index=False)
    pd.DataFrame(
        [
            {
                "requirement_id": "chunk_row_accounting",
                "status": "fail" if failing_requirement else "pass",
            }
        ]
    ).to_csv(chunk_dir / "REQUIREMENTS_STATUS.csv", index=False)
    pd.DataFrame(
        [
            {
                "claim_id": "source_ledger_row_accounting",
                "authority_file": "docs/replication_standards/codex_goals/step_1_url_discovery_run_contract.md",
                "binding_rule": "All target rows must have ready or explicit not-ready status.",
                "observed_value": "target_rows=2; ready_rows=1; unresolved_rows=1",
                "status": "pass",
                "supported_claim": "Source-ledger row accounting is closed.",
                "limitation": "Unresolved rows remain not ready for text extraction.",
            },
            {
                "claim_id": "legacy_carry_forward_accounting",
                "authority_file": "docs/replication_standards/supporting_rules/benchmark_protocol.md",
                "binding_rule": "Prior benchmark evidence is recovered, invalidated, or left visible as a miss.",
                "observed_value": "benchmark_rows=1; current_recovered=1; row_invalidated=0; unresolved_misses=0",
                "status": "pass",
                "supported_claim": "Legacy/prior benchmark rows are accounted for.",
                "limitation": "",
            },
            {
                "claim_id": "clean_no_legacy_benchmark",
                "authority_file": "docs/replication_standards/supporting_rules/benchmark_protocol.md",
                "binding_rule": "Clean no-legacy benchmarks cannot use human legacy URLs as candidate input.",
                "observed_value": "benchmark_mode=not_tested",
                "status": "not_tested",
                "supported_claim": "No clean no-legacy benchmark pass is claimed.",
                "limitation": "",
            },
            {
                "claim_id": "source_discovery_readiness_to_scale",
                "authority_file": "docs/replication_standards/README.md",
                "binding_rule": "Generated reports cannot authorize ready-to-scale status.",
                "observed_value": "under review",
                "status": "under_review",
                "supported_claim": "Ready-to-scale status is not claimed by generated artifacts.",
                "limitation": "A process review controls final readiness claims.",
            },
        ]
    ).to_csv(chunk_dir / "GUIDELINE_CROSSWALK.csv", index=False)
    (chunk_dir / "README.md").write_text("chunk readme\n", encoding="utf-8")
    (chunk_dir / "CHUNK_REPORT.md").write_text("chunk report\n", encoding="utf-8")
    (chunk_dir / "MANIFEST.json").write_text('{"run_type":"production_chunk"}\n', encoding="utf-8")

    pd.DataFrame(
        [
            {
                "unitid": 1,
                "academic_year": 2002,
                "candidate_url": "https://example.edu/catalog.pdf",
                "review_decision": "accept_current_run_source_review",
            }
        ]
    ).to_csv(audit_dir / "current_run_reattempt_source_review.csv", index=False)
    pd.DataFrame(
        [
            {
                "unitid": 1,
                "academic_year": 2002,
                "candidate_url": "https://example.edu/catalog.pdf",
                "source_body_sha256": "bodyhash",
                "cached_text_path": "current_run_reattempt_cached_text/1_2002.txt",
                "cached_text_sha256": "texthash",
            }
        ]
    ).to_csv(audit_dir / "current_run_reattempt_cached_source_evidence.csv", index=False)
    (audit_dir / "current_run_reattempt_cached_text/1_2002.txt").write_text("Example catalog text", encoding="utf-8")
    (audit_dir / "production_command.txt").write_text("python -m course_policy.production_chunk_url_discovery\n", encoding="utf-8")
    (audit_dir / "code_snapshot/src/course_policy/production_release_url_stage.py").write_text("# snapshot\n", encoding="utf-8")


def test_release_package_uses_relative_manifests_and_cached_evidence(tmp_path: Path) -> None:
    _write_chunk(tmp_path)

    result = build_url_stage_release_package(
        tmp_path,
        chunk_id="production_chunk_test",
        release_id="production_release_test",
    )

    assert result.package_pass
    release_dir = result.release_dir
    manifest = pd.read_csv(release_dir / "release_manifest.csv")
    assert not manifest["path"].map(lambda value: Path(str(value)).is_absolute()).any()
    assert (release_dir / "checksums.sha256").exists()
    assert (release_dir / "source_evidence_manifest.csv").exists()
    assert (release_dir / "ai_model_output_manifest.csv").exists()
    assert (release_dir / "ai_api_use_statement.csv").exists()
    assert (release_dir / "audit/source_lineage_manifest.csv").exists()
    assert (release_dir / "code_archive_manifest.csv").exists()
    assert (release_dir / "REBUILD_COMMANDS.txt").read_text(encoding="utf-8").startswith("PYTHONDONTWRITEBYTECODE=1")

    source_evidence = pd.read_csv(release_dir / "source_evidence_manifest.csv")
    assert source_evidence["source_artifact_status"].tolist() == ["cached_text_available"]
    assert source_evidence["cached_text_path"].str.contains("audit/current_run_reattempt_cached_text").all()
    assert source_evidence["evidence_hash_or_cache_path"].tolist() == [
        "abc123 external_absolute_path_removed:external_review_source.csv"
    ]
    assert (release_dir / "manifest_exclusions.csv").exists()
    assert not list(release_dir.rglob("__pycache__"))
    assert not any("/Users/" in path.read_text(encoding="utf-8", errors="ignore") for path in release_dir.rglob("*.csv"))

    rebuild_check = pd.read_csv(release_dir / "rebuild_check.csv")
    assert rebuild_check["status"].eq("pass").all()


def test_release_package_includes_ai_provenance_and_package_local_lineage(tmp_path: Path) -> None:
    _write_chunk(tmp_path, include_ai_provenance=True)

    result = build_url_stage_release_package(
        tmp_path,
        chunk_id="production_chunk_test",
        release_id="production_release_test",
    )

    assert result.package_pass
    release_dir = result.release_dir
    ai_manifest = pd.read_csv(release_dir / "ai_model_output_manifest.csv")
    ai_rows = ai_manifest.loc[ai_manifest["task_type"].eq("clean_no_legacy_year_gap_web_discovery")].copy()
    assert len(ai_rows) == 1
    ai_row = ai_rows.iloc[0]
    assert ai_row["model_or_version"] == "gpt-test-2026-07-01"
    assert str(ai_row["run_date_time"]).startswith("2026-07-01T")
    assert ai_row["schema_version"] == "clean_no_legacy_year_gap_web_discovery_response_v1"
    assert ai_row["source_review_linkage_path"] == "data/source_review_log.csv"
    assert (release_dir / ai_row["source_review_linkage_path"]).exists()
    assert ai_row["source_review_linkage_sha256"] == _sha256(release_dir / ai_row["source_review_linkage_path"])
    assert "unitid=1" in ai_row["source_review_linkage_filter"]
    assert int(ai_row["linked_ai_candidate_rows"]) >= 1
    for column in ["prompt_path", "raw_response_path", "parsed_response_path", "triage_path"]:
        assert ai_rows[column].str.startswith("audit/ai_api_provenance/").all()
        assert all((release_dir / value).exists() for value in ai_rows[column])

    candidate_ledger = pd.read_csv(release_dir / "data/candidate_url_ledger.csv")
    accepted = candidate_ledger.loc[candidate_ledger["academic_year"].eq(2002)].iloc[0]
    assert accepted["candidate_source_file"].startswith("audit/ai_api_provenance/stream_outputs/")
    assert (release_dir / accepted["candidate_source_file"]).exists()
    assert accepted["source_review_file"].startswith("audit/source_lineage/")

    triage_paths = list((release_dir / "audit/ai_api_provenance").rglob("ai_year_gap_triage.csv"))
    assert len(triage_paths) == 1
    triage = pd.read_csv(triage_paths[0])
    assert triage["api_prompt_path"].str.startswith("audit/ai_api_provenance/prompts/").all()
    assert triage["api_raw_response_path"].str.startswith("audit/ai_api_provenance/raw_responses/").all()
    assert triage["api_parsed_response_path"].str.startswith("audit/ai_api_provenance/parsed_responses/").all()

    status = pd.read_csv(release_dir / "release_status.csv").set_index("check")
    assert status.loc["ai_api_provenance_packaged", "status"] == "pass"
    assert status.loc["candidate_source_lineage_package_local", "status"] == "pass"

    lineage = pd.read_csv(release_dir / "audit/source_lineage_manifest.csv")
    for _, row in lineage.iterrows():
        packaged = release_dir / row["packaged_path"]
        assert packaged.exists()
        assert int(row["size_bytes"]) == packaged.stat().st_size
        assert row["sha256"] == _sha256(packaged)
        assert int(row["packaged_size_bytes"]) == packaged.stat().st_size
        assert row["packaged_sha256"] == _sha256(packaged)


def test_release_package_handles_blank_ai_provenance_artifact_path(tmp_path: Path) -> None:
    _write_chunk(tmp_path, include_ai_provenance=True)
    triage_path = (
        tmp_path
        / "artifacts/policy_data_internal/review/streams/public_clean_no_legacy_holdout/"
        / "test_namespace/ai_year_gap_triage.csv"
    )
    triage = pd.read_csv(triage_path)
    triage["api_parsed_response_path"] = ""
    triage.to_csv(triage_path, index=False)

    result = build_url_stage_release_package(
        tmp_path,
        chunk_id="production_chunk_test",
        release_id="production_release_test",
    )

    assert result.package_pass
    ai_manifest = pd.read_csv(result.release_dir / "ai_model_output_manifest.csv")
    ai_row = ai_manifest.loc[ai_manifest["task_type"].eq("clean_no_legacy_year_gap_web_discovery")].iloc[0]
    assert pd.isna(ai_row["parsed_response_path"]) or ai_row["parsed_response_path"] == ""
    assert pd.isna(ai_row["parsed_response_sha256"]) or ai_row["parsed_response_sha256"] == ""
    assert pd.isna(ai_row["output_hash"]) or ai_row["output_hash"] == ""


def test_release_package_rejects_failing_chunk(tmp_path: Path) -> None:
    _write_chunk(tmp_path, failing_requirement=True)

    with pytest.raises(ValueError, match="failing requirements"):
        build_url_stage_release_package(
            tmp_path,
            chunk_id="production_chunk_test",
            release_id="production_release_test",
        )


def test_release_package_rejects_benchmark_misses(tmp_path: Path) -> None:
    _write_chunk(tmp_path, benchmark_miss=True)

    with pytest.raises(ValueError, match="benchmark misses"):
        build_url_stage_release_package(
            tmp_path,
            chunk_id="production_chunk_test",
            release_id="production_release_test",
        )
