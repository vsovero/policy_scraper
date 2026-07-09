"""Post-repair Step 1 closure audit.

This module is accounting only. It reads the reviewed attrition audit and the
accepted materialization repair release, then writes closure ledgers and a
compact report without running discovery, retrieval, source review, or
production packaging.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .step1_attrition_audit import (
    ATTRITION_CLASSES,
    AUDIT_OUTPUT_ROOT,
    URL_DISCOVERY_ROOT,
    bool_series,
    candidate_artifact_roots,
    clean_text,
    compact_count_dict,
    read_csv_or_empty,
    repo_relative,
    target_universe_expected_match,
    to_int_series,
)


CLOSURE_OUTPUT_ROOT = Path(
    "artifacts/PIPELINE_OUTPUTS/01_url_discovery/reports/step1_post_repair_closure_audit_001"
)
REPAIR_RELEASE_ID = "step1_materialization_repair_release_001"
REPAIR_RELEASE_DIR_NAME = f"production_release_{REPAIR_RELEASE_ID}"
REPAIR_CHUNK_DIR_NAME = f"production_chunk_{REPAIR_RELEASE_ID}"
REPAIR_PROOF_DIR_NAME = "step1_historical_materialization_repair"
KEY_COLUMNS = ["unitid", "academic_year"]
CLOSURE_CLASSES = [
    "accepted_source_row",
    "historical_lead_only",
    "true_no_upstream_url_evidence",
    "candidate_retrieval_failure",
    "source_review_rejected_wrong_institution",
    "source_review_rejected_wrong_scope_or_year",
    "source_review_rejected_insufficient_evidence",
    "provenance_taxonomy_conflict",
    "no_materializable_row",
    "candidate_materialization_failure",
    "needs_text_validation",
    "not_selected_yet",
    "unresolved_unclassified",
]
CLOSURE_PRIORITY = [
    "provenance_taxonomy_conflict",
    "source_review_rejected_wrong_institution",
    "source_review_rejected_wrong_scope_or_year",
    "source_review_rejected_insufficient_evidence",
    "candidate_retrieval_failure",
    "candidate_materialization_failure",
    "no_materializable_row",
    "historical_lead_only",
    "true_no_upstream_url_evidence",
    "needs_text_validation",
    "unresolved_unclassified",
    "accepted_source_row",
    "not_selected_yet",
]


@dataclass(frozen=True)
class RepairArtifacts:
    input_dir: Path | None
    release_dir: Path | None
    chunk_dir: Path | None
    proof_dir: Path | None


@dataclass(frozen=True)
class ClosureResult:
    output_dir: Path
    institution_ledger: Path
    institution_year_ledger: Path
    report: Path
    summary_json: Path
    institution_rows: int
    institution_year_rows: int
    combined_accepted_rows: int
    remaining_unresolved_rows: int
    target_universe_expected_count_match: bool
    columbus_closure_class: str


def normalize_unit_year(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=KEY_COLUMNS)
    out = frame.copy()
    if "academic_year" not in out.columns:
        for candidate in ["year", "target_year"]:
            if candidate in out.columns:
                out["academic_year"] = out[candidate]
                break
    for column in KEY_COLUMNS:
        if column not in out.columns:
            out[column] = pd.Series(dtype="Int64")
        out[column] = to_int_series(out[column])
    return out


def unit_year_keys(frame: pd.DataFrame) -> set[tuple[int, int]]:
    frame = normalize_unit_year(frame)
    if frame.empty:
        return set()
    keys = frame[KEY_COLUMNS].dropna().astype(int)
    return set(map(tuple, keys.to_records(index=False)))


def join_unique(values: object, limit: int = 8) -> str:
    cleaned = sorted({clean_text(value) for value in values if clean_text(value)})
    return "; ".join(cleaned[:limit])


def int_count(value: object) -> int:
    return int(pd.to_numeric(pd.Series([value]), errors="coerce").fillna(0).iloc[0])


def truthy_value(value: object) -> bool:
    return clean_text(value).lower() in {"1", "1.0", "true", "yes", "y"}


def choose_existing(existing: Path | None, candidate: Path) -> Path:
    if existing is None:
        return candidate
    existing_key = (existing.resolve().as_posix() != candidate.resolve().as_posix(), existing.as_posix())
    candidate_key = (candidate.resolve().as_posix() != candidate.as_posix(), candidate.as_posix())
    return candidate if candidate_key < existing_key else existing


def discover_repair_artifacts(repo_root: Path) -> RepairArtifacts:
    input_dir: Path | None = None
    release_dir: Path | None = None
    chunk_dir: Path | None = None
    proof_dir: Path | None = None
    for root in candidate_artifact_roots(repo_root):
        base = root / URL_DISCOVERY_ROOT
        candidates = {
            "input": base / "production_inputs" / REPAIR_RELEASE_ID,
            "release": base / "production_releases" / REPAIR_RELEASE_DIR_NAME,
            "chunk": base / "production_chunks" / REPAIR_CHUNK_DIR_NAME,
            "proof": base / "build_reports" / REPAIR_PROOF_DIR_NAME,
        }
        if candidates["input"].exists():
            input_dir = choose_existing(input_dir, candidates["input"])
        if candidates["release"].exists():
            release_dir = choose_existing(release_dir, candidates["release"])
        if candidates["chunk"].exists():
            chunk_dir = choose_existing(chunk_dir, candidates["chunk"])
        if candidates["proof"].exists():
            proof_dir = choose_existing(proof_dir, candidates["proof"])
    return RepairArtifacts(input_dir=input_dir, release_dir=release_dir, chunk_dir=chunk_dir, proof_dir=proof_dir)


def load_attrition_frames(repo_root: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    attrition_dir = repo_root / AUDIT_OUTPUT_ROOT
    year = read_csv_or_empty(attrition_dir / "institution_year_attrition_ledger.csv")
    institution = read_csv_or_empty(attrition_dir / "institution_attrition_ledger.csv")
    summary_path = attrition_dir / "attrition_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    if year.empty or institution.empty:
        raise FileNotFoundError(f"Missing reviewed attrition audit ledgers under {attrition_dir.as_posix()}")
    return normalize_unit_year(year), institution, summary


def load_repair_frames(artifacts: RepairArtifacts) -> dict[str, pd.DataFrame]:
    release = artifacts.release_dir
    input_dir = artifacts.input_dir
    proof_dir = artifacts.proof_dir
    return {
        "target": normalize_unit_year(read_csv_or_empty(release / "data/target_panel.csv" if release else None)),
        "candidate": normalize_unit_year(read_csv_or_empty(release / "data/candidate_url_ledger.csv" if release else None)),
        "source": normalize_unit_year(read_csv_or_empty(release / "data/source_ledger.csv" if release else None)),
        "review": normalize_unit_year(read_csv_or_empty(release / "data/source_review_log.csv" if release else None)),
        "benchmark": normalize_unit_year(read_csv_or_empty(release / "data/benchmark_recovery.csv" if release else None)),
        "unresolved": normalize_unit_year(read_csv_or_empty(release / "audit/unresolved_rows.csv" if release else None)),
        "decisions": normalize_unit_year(read_csv_or_empty(input_dir / "historical_materialization_decisions.csv" if input_dir else None)),
        "proof": normalize_unit_year(read_csv_or_empty(proof_dir / "historical_materialization_repair_ledger.csv" if proof_dir else None)),
    }


def summarize_keyed_rows(frame: pd.DataFrame, row_column: str, text_columns: list[str] | None = None) -> pd.DataFrame:
    frame = normalize_unit_year(frame)
    if frame.empty:
        return pd.DataFrame(columns=[*KEY_COLUMNS, row_column])
    text_columns = text_columns or []
    grouped = frame.dropna(subset=KEY_COLUMNS).groupby(KEY_COLUMNS, dropna=False)
    out = grouped.size().reset_index(name=row_column)
    for column in text_columns:
        if column in frame.columns:
            values = grouped[column].agg(join_unique).reset_index(name=column)
            out = out.merge(values, on=KEY_COLUMNS, how="left")
    return out


def summarize_repair_source(source: pd.DataFrame) -> pd.DataFrame:
    source = normalize_unit_year(source)
    if source.empty:
        return pd.DataFrame(columns=KEY_COLUMNS)
    working = source.dropna(subset=KEY_COLUMNS).copy()
    decision = working.get("review_decision", pd.Series("", index=working.index)).map(clean_text).str.lower()
    working["repair_source_accept_rows"] = decision.str.startswith("accept").astype(int)
    working["repair_source_needs_text_validation_rows"] = decision.eq("needs_text_validation").astype(int)
    grouped = working.groupby(KEY_COLUMNS, dropna=False)
    out = grouped.agg(
        repair_source_ledger_rows=("unitid", "size"),
        repair_source_accept_rows=("repair_source_accept_rows", "sum"),
        repair_source_needs_text_validation_rows=("repair_source_needs_text_validation_rows", "sum"),
    ).reset_index()
    for source_column, output_column in [
        ("review_decision", "repair_source_review_decisions"),
        ("provenance_type", "repair_source_provenance_types"),
        ("legacy_input_provenance", "repair_source_legacy_input_provenance"),
        ("accepted_source_url", "repair_accepted_source_urls"),
    ]:
        if source_column in working.columns:
            out = out.merge(grouped[source_column].agg(join_unique).reset_index(name=output_column), on=KEY_COLUMNS, how="left")
    return out


def summarize_repair_unresolved(unresolved: pd.DataFrame) -> pd.DataFrame:
    unresolved = normalize_unit_year(unresolved)
    if unresolved.empty:
        return pd.DataFrame(columns=KEY_COLUMNS)
    working = unresolved.dropna(subset=KEY_COLUMNS).copy()
    grouped = working.groupby(KEY_COLUMNS, dropna=False)
    out = grouped.size().reset_index(name="repair_unresolved_rows")
    for source_column, output_column in [
        ("review_decision", "repair_unresolved_review_decisions"),
        ("unresolved_reason", "repair_unresolved_reasons"),
        ("review_reason", "repair_unresolved_review_reasons"),
        ("url_status", "repair_unresolved_url_statuses"),
    ]:
        if source_column in working.columns:
            out = out.merge(grouped[source_column].agg(join_unique).reset_index(name=output_column), on=KEY_COLUMNS, how="left")
    return out


def summarize_repair_benchmark(benchmark: pd.DataFrame) -> pd.DataFrame:
    benchmark = normalize_unit_year(benchmark)
    if benchmark.empty:
        return pd.DataFrame(columns=KEY_COLUMNS)
    working = benchmark.dropna(subset=KEY_COLUMNS).copy()
    resolution = working.get("benchmark_resolution_type", pd.Series("", index=working.index)).map(clean_text)
    working["repair_benchmark_current_run_recovered_rows"] = resolution.eq("current_run_recovered").astype(int)
    working["repair_benchmark_resolved_by_other_evidence_rows"] = resolution.eq("source_ledger_resolved_by_other_evidence").astype(int)
    working["repair_benchmark_invalidated_rows"] = resolution.eq("row_invalidated_by_current_review").astype(int)
    grouped = working.groupby(KEY_COLUMNS, dropna=False)
    out = grouped.agg(
        repair_benchmark_rows=("unitid", "size"),
        repair_benchmark_current_run_recovered_rows=("repair_benchmark_current_run_recovered_rows", "sum"),
        repair_benchmark_resolved_by_other_evidence_rows=("repair_benchmark_resolved_by_other_evidence_rows", "sum"),
        repair_benchmark_invalidated_rows=("repair_benchmark_invalidated_rows", "sum"),
    ).reset_index()
    for source_column, output_column in [
        ("benchmark_recovery_status", "repair_benchmark_recovery_statuses"),
        ("benchmark_resolution_type", "repair_benchmark_resolution_types"),
        ("current_review_decision", "repair_benchmark_review_decisions"),
        ("current_url_status", "repair_benchmark_url_statuses"),
    ]:
        if source_column in working.columns:
            out = out.merge(grouped[source_column].agg(join_unique).reset_index(name=output_column), on=KEY_COLUMNS, how="left")
    return out


def summarize_repair_proof(proof: pd.DataFrame) -> pd.DataFrame:
    proof = normalize_unit_year(proof)
    if proof.empty:
        return pd.DataFrame(columns=KEY_COLUMNS)
    working = proof.dropna(subset=KEY_COLUMNS).copy()
    decision = working.get("materialization_decision", pd.Series("", index=working.index)).map(clean_text)
    evidence = working.get("historical_evidence_class", pd.Series("", index=working.index)).map(clean_text)
    working["repair_proof_historical_lead_rows"] = (
        decision.str.contains("historical_lead_candidate", regex=False)
        | evidence.str.contains("candidate_lead", regex=False)
        | evidence.str.contains("imported_llm", regex=False)
    ).astype(int)
    working["repair_proof_not_materialized_rows"] = decision.eq("not_materialized").astype(int)
    working["repair_proof_legacy_or_programmatic_rows"] = decision.eq("materialized_candidate").astype(int)
    grouped = working.groupby(KEY_COLUMNS, dropna=False)
    out = grouped.agg(
        repair_proof_rows=("unitid", "size"),
        repair_proof_historical_lead_rows=("repair_proof_historical_lead_rows", "sum"),
        repair_proof_not_materialized_rows=("repair_proof_not_materialized_rows", "sum"),
        repair_proof_legacy_or_programmatic_rows=("repair_proof_legacy_or_programmatic_rows", "sum"),
    ).reset_index()
    for source_column, output_column in [
        ("materialization_decision", "repair_proof_materialization_decisions"),
        ("historical_evidence_class", "repair_proof_historical_evidence_classes"),
        ("provenance_label", "repair_proof_provenance_labels"),
        ("candidate_source_type", "repair_proof_candidate_source_types"),
        ("exclusion_reason", "repair_proof_exclusion_reasons"),
    ]:
        if source_column in working.columns:
            out = out.merge(grouped[source_column].agg(join_unique).reset_index(name=output_column), on=KEY_COLUMNS, how="left")
    return out


def merge_feature_frames(base: pd.DataFrame, features: list[pd.DataFrame]) -> pd.DataFrame:
    out = base.copy()
    for feature in features:
        if feature.empty:
            continue
        out = out.merge(feature, on=KEY_COLUMNS, how="left")
    for column in out.columns:
        if column.endswith("_rows") or column.endswith("_count"):
            out[column] = pd.to_numeric(out[column], errors="coerce").fillna(0).astype(int)
    return out


def closure_provenance_bucket(row: pd.Series) -> str:
    repair_provenance = clean_text(row.get("repair_source_provenance_types")).lower()
    repair_legacy = clean_text(row.get("repair_source_legacy_input_provenance")).lower()
    if "prior_human" in repair_provenance or "validated_human_legacy" in repair_legacy:
        return "validated_human_legacy"
    if "prior_programmatic" in repair_provenance or "prior_programmatic" in repair_legacy:
        return "prior_programmatic"
    if "historical_lead" in repair_provenance or "imported_llm" in repair_legacy:
        return "historical_lead"
    if truthy_value(row.get("has_valid_human_legacy")):
        return "validated_human_legacy"
    if truthy_value(row.get("has_prior_programmatic_accepted")):
        return "prior_programmatic"
    if truthy_value(row.get("has_imported_llm_candidate_lead")) or truthy_value(row.get("historical_lead_only")):
        return "historical_lead"
    return "unknown_or_current_only"


def classify_closure_row(row: pd.Series) -> str:
    if truthy_value(row.get("accepted_after_repair")):
        return "accepted_source_row"
    unresolved_decisions = clean_text(row.get("repair_unresolved_review_decisions")).lower()
    if int_count(row.get("repair_unresolved_rows")):
        if "dead_or_unretrievable" in unresolved_decisions:
            return "candidate_retrieval_failure"
        if "institution_not_confirmed" in unresolved_decisions or "wrong_institution" in unresolved_decisions:
            return "source_review_rejected_wrong_institution"
        if "not_catalog" in unresolved_decisions or "policy_source" in unresolved_decisions:
            return "source_review_rejected_wrong_scope_or_year"
        return "source_review_rejected_insufficient_evidence"
    prior_class = clean_text(row.get("pre_repair_attrition_class"))
    if prior_class == "candidate_materialization_failure":
        if int_count(row.get("repair_proof_historical_lead_rows")):
            return "historical_lead_only"
        if int_count(row.get("repair_proof_not_materialized_rows")):
            return "no_materializable_row"
        return "candidate_materialization_failure"
    if prior_class in CLOSURE_CLASSES:
        return prior_class
    if truthy_value(row.get("historical_lead_only")):
        return "historical_lead_only"
    return "unresolved_unclassified"


def build_closure_year_ledger(attrition_year: pd.DataFrame, repair_frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    base = normalize_unit_year(attrition_year).copy()
    base["pre_repair_attrition_class"] = base.get("attrition_class", pd.Series("", index=base.index)).map(clean_text)
    base["accepted_before_repair"] = base["pre_repair_attrition_class"].eq("accepted_source_row")
    base["pre_repair_step2_eligibility"] = base.get("step2_eligibility", pd.Series("", index=base.index)).map(clean_text)
    source_summary = summarize_repair_source(repair_frames.get("source", pd.DataFrame()))
    unresolved_summary = summarize_repair_unresolved(repair_frames.get("unresolved", pd.DataFrame()))
    target_summary = summarize_keyed_rows(repair_frames.get("target", pd.DataFrame()), "repair_target_rows")
    candidate_summary = summarize_keyed_rows(
        repair_frames.get("candidate", pd.DataFrame()),
        "repair_candidate_rows",
        ["review_decision", "candidate_source_type", "legacy_input_provenance"],
    ).rename(
        columns={
            "review_decision": "repair_candidate_review_decisions",
            "candidate_source_type": "repair_candidate_source_types",
            "legacy_input_provenance": "repair_candidate_legacy_input_provenance",
        }
    )
    decision_summary = summarize_keyed_rows(
        repair_frames.get("decisions", pd.DataFrame()),
        "repair_materialization_decision_rows",
        ["historical_evidence_class", "materialization_decision", "provenance_label"],
    ).rename(
        columns={
            "historical_evidence_class": "repair_materialization_historical_evidence_classes",
            "materialization_decision": "repair_materialization_decisions",
            "provenance_label": "repair_materialization_provenance_labels",
        }
    )
    benchmark_summary = summarize_repair_benchmark(repair_frames.get("benchmark", pd.DataFrame()))
    proof_summary = summarize_repair_proof(repair_frames.get("proof", pd.DataFrame()))
    out = merge_feature_frames(
        base,
        [
            source_summary,
            unresolved_summary,
            target_summary,
            candidate_summary,
            decision_summary,
            benchmark_summary,
            proof_summary,
        ],
    )
    for column in [
        "repair_source_review_decisions",
        "repair_source_provenance_types",
        "repair_source_legacy_input_provenance",
        "repair_accepted_source_urls",
        "repair_unresolved_review_decisions",
        "repair_unresolved_reasons",
        "repair_unresolved_review_reasons",
        "repair_unresolved_url_statuses",
        "repair_candidate_review_decisions",
        "repair_candidate_source_types",
        "repair_candidate_legacy_input_provenance",
        "repair_materialization_historical_evidence_classes",
        "repair_materialization_decisions",
        "repair_materialization_provenance_labels",
        "repair_benchmark_recovery_statuses",
        "repair_benchmark_resolution_types",
        "repair_benchmark_review_decisions",
        "repair_benchmark_url_statuses",
        "repair_proof_materialization_decisions",
        "repair_proof_historical_evidence_classes",
        "repair_proof_provenance_labels",
        "repair_proof_candidate_source_types",
        "repair_proof_exclusion_reasons",
    ]:
        if column not in out.columns:
            out[column] = ""
        out[column] = out[column].map(clean_text)
    for column in [
        "repair_source_ledger_rows",
        "repair_source_accept_rows",
        "repair_source_needs_text_validation_rows",
        "repair_target_rows",
        "repair_candidate_rows",
        "repair_unresolved_rows",
        "repair_materialization_decision_rows",
        "repair_benchmark_rows",
        "repair_benchmark_current_run_recovered_rows",
        "repair_benchmark_resolved_by_other_evidence_rows",
        "repair_benchmark_invalidated_rows",
        "repair_proof_rows",
        "repair_proof_historical_lead_rows",
        "repair_proof_not_materialized_rows",
        "repair_proof_legacy_or_programmatic_rows",
    ]:
        if column not in out.columns:
            out[column] = 0
        out[column] = pd.to_numeric(out[column], errors="coerce").fillna(0).astype(int)
    out["accepted_after_repair"] = out["accepted_before_repair"] | out["repair_source_ledger_rows"].gt(0)
    out["newly_accepted_by_repair"] = ~out["accepted_before_repair"] & out["repair_source_ledger_rows"].gt(0)
    out["selected_after_repair"] = bool_series(out.get("selected_in_accepted_batch", pd.Series(False, index=out.index))) | out.get(
        "repair_target_rows", pd.Series(0, index=out.index)
    ).fillna(0).astype(int).gt(0)
    out["accepted_provenance_bucket"] = out.apply(closure_provenance_bucket, axis=1).where(out["accepted_after_repair"], "")
    out["closure_class"] = out.apply(classify_closure_row, axis=1)
    out["remaining_unresolved_after_repair"] = ~out["accepted_after_repair"]
    ordered_columns = [
        "unitid",
        "academic_year",
        "target_universe_sector",
        "target_universe_institution_name",
        "target_universe_state",
        "old_collected_policy_institution",
        "old_public_411_diagnostic_member",
        "accepted_before_repair",
        "repair_source_ledger_rows",
        "repair_source_accept_rows",
        "repair_source_needs_text_validation_rows",
        "newly_accepted_by_repair",
        "accepted_after_repair",
        "accepted_provenance_bucket",
        "remaining_unresolved_after_repair",
        "pre_repair_attrition_class",
        "closure_class",
        "repair_target_rows",
        "repair_candidate_rows",
        "repair_unresolved_rows",
        "repair_unresolved_review_decisions",
        "repair_unresolved_reasons",
        "repair_benchmark_current_run_recovered_rows",
        "repair_benchmark_resolved_by_other_evidence_rows",
        "repair_benchmark_invalidated_rows",
        "repair_benchmark_resolution_types",
        "repair_materialization_historical_evidence_classes",
        "repair_materialization_decisions",
        "repair_materialization_provenance_labels",
        "repair_proof_historical_evidence_classes",
        "repair_proof_materialization_decisions",
        "repair_proof_provenance_labels",
        "repair_proof_exclusion_reasons",
    ]
    remaining_columns = [column for column in out.columns if column not in ordered_columns]
    return out[ordered_columns + remaining_columns].sort_values(KEY_COLUMNS).reset_index(drop=True)


def choose_institution_class(group: pd.DataFrame) -> str:
    counts = group["closure_class"].value_counts().to_dict()
    priority = {label: index for index, label in enumerate(CLOSURE_PRIORITY)}
    return min(counts, key=lambda label: priority.get(label, 99))


def build_closure_institution_ledger(attrition_institution: pd.DataFrame, closure_year: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for _, institution in attrition_institution.iterrows():
        unitid = int_count(institution.get("unitid"))
        group = closure_year.loc[closure_year["unitid"].astype("Int64").eq(unitid)].copy()
        if group.empty:
            continue
        accepted_after = group["accepted_after_repair"]
        unresolved_after = group["remaining_unresolved_after_repair"]
        old_public = truthy_value(institution.get("old_public_411_diagnostic_member"))
        if old_public:
            if accepted_after.any():
                public_disposition = "accepted_after_repair"
            elif group["selected_after_repair"].any():
                public_disposition = "selected_unresolved_after_repair"
            else:
                public_disposition = "not_selected_yet_after_repair"
        else:
            public_disposition = "not_old_public_411_member"
        rows.append(
            {
                "unitid": unitid,
                "institution_name": clean_text(institution.get("institution_name")),
                "sector": clean_text(institution.get("sector")),
                "state": clean_text(institution.get("state")),
                "target_universe_member": truthy_value(institution.get("target_universe_member")),
                "complete_institution_years": int_count(institution.get("complete_institution_years")),
                "old_collected_policy_institution": truthy_value(institution.get("old_collected_policy_institution")),
                "never_collected_policy_institution": truthy_value(institution.get("never_collected_policy_institution")),
                "old_public_411_diagnostic_member": old_public,
                "accepted_before_repair_years": int(group["accepted_before_repair"].sum()),
                "repair_source_ledger_years": int(group["repair_source_ledger_rows"].gt(0).sum()),
                "newly_accepted_by_repair_years": int(group["newly_accepted_by_repair"].sum()),
                "accepted_after_repair_years": int(accepted_after.sum()),
                "remaining_unresolved_after_repair_years": int(unresolved_after.sum()),
                "historical_lead_only_years": int(group["closure_class"].eq("historical_lead_only").sum()),
                "true_no_upstream_evidence_years": int(group["closure_class"].eq("true_no_upstream_url_evidence").sum()),
                "retrieval_failure_years": int(group["closure_class"].eq("candidate_retrieval_failure").sum()),
                "source_review_failure_years": int(group["closure_class"].str.startswith("source_review_rejected").sum()),
                "provenance_taxonomy_conflict_years": int(group["closure_class"].eq("provenance_taxonomy_conflict").sum()),
                "no_materializable_years": int(group["closure_class"].eq("no_materializable_row").sum()),
                "candidate_materialization_failure_years": int(group["closure_class"].eq("candidate_materialization_failure").sum()),
                "closure_class_counts": json.dumps(group["closure_class"].value_counts().to_dict(), sort_keys=True),
                "institution_closure_class": choose_institution_class(group),
                "old_public_411_closure_disposition": public_disposition,
                "accepted_provenance_buckets": join_unique(group["accepted_provenance_bucket"]),
            }
        )
    out = pd.DataFrame(rows)
    return out.sort_values(["institution_closure_class", "unitid", "sector"]).reset_index(drop=True)


def count_rows_and_institutions(frame: pd.DataFrame, mask: pd.Series) -> dict[str, int]:
    selected = frame.loc[mask]
    return {"institution_years": int(len(selected)), "institutions": int(selected["unitid"].nunique())}


def closure_class_counts(frame: pd.DataFrame) -> dict[str, int]:
    observed = {str(key): int(value) for key, value in frame["closure_class"].value_counts().to_dict().items()}
    return {label: int(observed.get(label, 0)) for label in CLOSURE_CLASSES}


def closure_class_institution_counts(frame: pd.DataFrame) -> dict[str, int]:
    return {
        label: int(frame.loc[frame["closure_class"].eq(label), "unitid"].nunique())
        for label in CLOSURE_CLASSES
    }


def public_411_status(institution: pd.DataFrame, year: pd.DataFrame, target_counts: dict[str, dict[str, int]]) -> dict[str, int | str]:
    old_public = institution.loc[institution["old_public_411_diagnostic_member"]].copy()
    old_target_ids = set(old_public["unitid"].dropna().astype(int))
    old_year = year.loc[year["old_public_411_diagnostic_member"].map(truthy_value)].copy()
    if "accepted_before_repair_years" in old_public.columns:
        accepted_before_ids = set(old_public.loc[old_public["accepted_before_repair_years"].gt(0), "unitid"].dropna().astype(int))
    else:
        accepted_before_ids = set(old_year.loc[old_year["accepted_before_repair"], "unitid"].dropna().astype(int))
    if "newly_accepted_by_repair_years" in old_public.columns:
        repair_new_ids = set(old_public.loc[old_public["newly_accepted_by_repair_years"].gt(0), "unitid"].dropna().astype(int)) - accepted_before_ids
    else:
        repair_new_ids = set(old_year.loc[old_year["newly_accepted_by_repair"], "unitid"].dropna().astype(int)) - accepted_before_ids
    if "accepted_after_repair_years" in old_public.columns:
        accepted_after_ids = set(old_public.loc[old_public["accepted_after_repair_years"].gt(0), "unitid"].dropna().astype(int))
    else:
        accepted_after_ids = set(old_year.loc[old_year["accepted_after_repair"], "unitid"].dropna().astype(int))
    selected_after_ids = set(
        old_year.loc[old_year["selected_after_repair"], "unitid"]
        .dropna()
        .astype(int)
    )
    unresolved_ids = old_target_ids - accepted_after_ids
    baseline = int(target_counts.get("old_public_411_diagnostic", {}).get("institutions", len(old_target_ids)))
    outside = int(target_counts.get("old_public_411_diagnostic", {}).get("outside_target_universe", max(baseline - len(old_target_ids), 0)))
    return {
        "baseline_old_public_411_institutions": baseline,
        "inside_target_universe": int(len(old_target_ids)),
        "outside_target_universe": outside,
        "accepted_before_repair": int(len(accepted_before_ids)),
        "newly_accepted_through_repair": int(len(repair_new_ids)),
        "accepted_after_repair": int(len(accepted_after_ids)),
        "still_unresolved_after_repair": int(len(unresolved_ids)),
        "not_yet_selected_unresolved_after_repair": int(len(unresolved_ids - selected_after_ids)),
        "short_of_inside_target_floor": int(len(unresolved_ids)),
        "short_of_all_411_baseline": int((baseline - len(accepted_after_ids))),
    }


def build_summary(
    closure_institution: pd.DataFrame,
    closure_year: pd.DataFrame,
    attrition_summary: dict[str, object],
    repair_artifacts: RepairArtifacts,
    repo_root: Path,
    output_dir: Path,
) -> dict[str, object]:
    target_counts = attrition_summary.get("target_universe_counts", {})
    if not isinstance(target_counts, dict):
        target_counts = {}
    accepted_before = count_rows_and_institutions(closure_year, closure_year["accepted_before_repair"])
    repair_source = count_rows_and_institutions(closure_year, closure_year["repair_source_ledger_rows"].gt(0))
    combined = count_rows_and_institutions(closure_year, closure_year["accepted_after_repair"])
    remaining = closure_year.loc[closure_year["remaining_unresolved_after_repair"]].copy()
    columbus = closure_year.loc[closure_year["unitid"].astype(str).eq("139366")].copy()
    accepted_sector_rows = {
        str(key): int(value)
        for key, value in closure_year.loc[closure_year["accepted_after_repair"], "target_universe_sector"].value_counts().to_dict().items()
    }
    accepted_sector_institutions = {
        str(key): int(value)
        for key, value in closure_year.loc[closure_year["accepted_after_repair"]].groupby("target_universe_sector")["unitid"].nunique().to_dict().items()
    }
    accepted_provenance_rows = {
        str(key): int(value)
        for key, value in closure_year.loc[closure_year["accepted_after_repair"], "accepted_provenance_bucket"].value_counts().to_dict().items()
    }
    accepted_provenance_institutions = {
        str(key): int(value)
        for key, value in closure_year.loc[closure_year["accepted_after_repair"]].groupby("accepted_provenance_bucket")["unitid"].nunique().to_dict().items()
    }
    return {
        "output_dir": repo_relative(output_dir, repo_root),
        "input_attrition_audit_dir": AUDIT_OUTPUT_ROOT.as_posix(),
        "repair_artifacts": {
            "input_dir": repo_relative(repair_artifacts.input_dir, repo_root) if repair_artifacts.input_dir else "",
            "release_dir": repo_relative(repair_artifacts.release_dir, repo_root) if repair_artifacts.release_dir else "",
            "chunk_dir": repo_relative(repair_artifacts.chunk_dir, repo_root) if repair_artifacts.chunk_dir else "",
            "proof_dir": repo_relative(repair_artifacts.proof_dir, repo_root) if repair_artifacts.proof_dir else "",
        },
        "target_universe_counts": target_counts,
        "target_universe_expected_count_match": target_universe_expected_match(target_counts),
        "accepted_after_repair": {
            "accepted_before_repair": accepted_before,
            "repair_source_ledger": repair_source,
            "repair_source_accept_exact_year_catalog_rows": int(closure_year["repair_source_accept_rows"].sum()),
            "repair_source_needs_text_validation_rows": int(closure_year["repair_source_needs_text_validation_rows"].sum()),
            "repair_benchmark_current_run_recovered_rows": int(closure_year["repair_benchmark_current_run_recovered_rows"].sum()),
            "repair_benchmark_resolved_by_other_evidence_rows": int(
                closure_year["repair_benchmark_resolved_by_other_evidence_rows"].sum()
            ),
            "combined_accepted": combined,
            "combined_accepted_by_sector_rows": accepted_sector_rows,
            "combined_accepted_by_sector_institutions": accepted_sector_institutions,
            "combined_accepted_by_provenance_rows": accepted_provenance_rows,
            "combined_accepted_by_provenance_institutions": accepted_provenance_institutions,
        },
        "remaining_unresolved_after_repair": {
            "total": {"institution_years": int(len(remaining)), "institutions": int(remaining["unitid"].nunique())},
            "closure_class_counts": closure_class_counts(remaining),
            "closure_class_institution_counts": closure_class_institution_counts(remaining),
            "source_review_failure_rows": int(remaining["closure_class"].str.startswith("source_review_rejected").sum()),
            "source_review_failure_institutions": int(
                remaining.loc[remaining["closure_class"].str.startswith("source_review_rejected"), "unitid"].nunique()
            ),
            "any_remaining_candidate_materialization_failures": int(remaining["closure_class"].eq("candidate_materialization_failure").sum()),
        },
        "public_411_floor": public_411_status(closure_institution, closure_year, target_counts),
        "columbus_state": {
            "unitid": 139366,
            "year_rows": int(len(columbus)),
            "repair_target_rows": int(columbus["repair_target_rows"].gt(0).sum()) if not columbus.empty else 0,
            "repair_source_ledger_rows": int(columbus["repair_source_ledger_rows"].sum()) if not columbus.empty else 0,
            "repair_unresolved_rows": int(columbus["repair_unresolved_rows"].sum()) if not columbus.empty else 0,
            "current_final_closure_class": clean_text(columbus["closure_class"].mode().iloc[0]) if not columbus.empty else "",
            "closure_class_counts": {str(key): int(value) for key, value in columbus["closure_class"].value_counts().to_dict().items()},
            "no_longer_candidate_materialization_failure": bool(
                not columbus.empty and not columbus["closure_class"].eq("candidate_materialization_failure").any()
            ),
        },
    }


def write_report(output_dir: Path, summary: dict[str, object]) -> Path:
    target_counts = summary["target_universe_counts"]
    accepted = summary["accepted_after_repair"]
    remaining = summary["remaining_unresolved_after_repair"]
    public_411 = summary["public_411_floor"]
    columbus = summary["columbus_state"]
    accepted_prov_rows = accepted["combined_accepted_by_provenance_rows"]
    remaining_counts = {
        key: value
        for key, value in remaining["closure_class_counts"].items()
        if int(value) > 0
    }
    lines = [
        "# Step 1 Post-Repair Closure Audit 001",
        "",
        "Accounting-only audit. It reads accepted Step 1 batches 001-040, the accepted materialization repair release, and the reviewed target-universe denominator. It does not run live discovery, retrieval, source review, production batches, or Step 2 handoff construction.",
        "",
        "## Inputs",
        "",
        f"- Attrition audit input: `{summary['input_attrition_audit_dir']}`",
        f"- Repair release input: `{summary['repair_artifacts']['release_dir']}`",
        f"- Repair proof input: `{summary['repair_artifacts']['proof_dir']}`",
        "",
        "## Target Universe",
        "",
        "| Sector | Institutions | Complete institution-years | Old collected-policy institutions | Never-collected institutions |",
        "|---|---:|---:|---:|---:|",
        (
            f"| Public | {target_counts['public']['institutions']} | "
            f"{target_counts['public']['membership_complete_institution_years']} | "
            f"{target_counts['public']['old_collected_policy_institutions']} | "
            f"{target_counts['public']['never_collected_policy_institutions']} |"
        ),
        (
            f"| Private nonprofit | {target_counts['private']['institutions']} | "
            f"{target_counts['private']['membership_complete_institution_years']} | "
            f"{target_counts['private']['old_collected_policy_institutions']} | "
            f"{target_counts['private']['never_collected_policy_institutions']} |"
        ),
        (
            f"| Total | {target_counts['total']['sector_institution_memberships']} | "
            f"{target_counts['total']['unique_complete_institution_years']} | "
            f"{target_counts['total']['old_collected_policy_institutions']} | "
            f"{target_counts['total']['never_collected_policy_institutions']} |"
        ),
        "",
        f"- Target-universe count check: {'matched reviewed denominator' if summary['target_universe_expected_count_match'] else 'NOT MATCHED'}",
        "",
        "## Accepted Evidence After Repair",
        "",
        f"- Accepted/source-ledger institution-years before repair: {accepted['accepted_before_repair']['institution_years']}",
        f"- Accepted/source-ledger institutions before repair: {accepted['accepted_before_repair']['institutions']}",
        f"- Repair source-ledger institution-years: {accepted['repair_source_ledger']['institution_years']}",
        f"- Repair source-ledger institutions: {accepted['repair_source_ledger']['institutions']}",
        f"- Repair direct current-run benchmark recoveries: {accepted['repair_benchmark_current_run_recovered_rows']}",
        f"- Repair source-ledger-resolved-by-other-evidence rows, not direct benchmark recoveries: {accepted['repair_benchmark_resolved_by_other_evidence_rows']}",
        f"- Combined accepted/source-ledger institution-years: {accepted['combined_accepted']['institution_years']}",
        f"- Combined accepted/source-ledger institutions: {accepted['combined_accepted']['institutions']}",
        "",
        "### Accepted Sector Split",
        "",
        compact_count_dict(accepted["combined_accepted_by_sector_rows"]),
        "### Accepted Provenance Split",
        "",
        compact_count_dict(accepted_prov_rows),
        "## Remaining Unresolved After Repair",
        "",
        f"- Remaining unresolved institution-years: {remaining['total']['institution_years']}",
        f"- Remaining unresolved institutions: {remaining['total']['institutions']}",
        f"- Remaining candidate-materialization failures: {remaining['any_remaining_candidate_materialization_failures']}",
        "",
        compact_count_dict(remaining_counts),
        "## Public Old 411 Floor",
        "",
        f"- Baseline old public 411 institutions: {public_411['baseline_old_public_411_institutions']}",
        f"- Inside current target universe: {public_411['inside_target_universe']}",
        f"- Accepted before repair: {public_411['accepted_before_repair']}",
        f"- Newly accepted through repair: {public_411['newly_accepted_through_repair']}",
        f"- Accepted after repair: {public_411['accepted_after_repair']}",
        f"- Still unresolved after repair: {public_411['still_unresolved_after_repair']}",
        f"- Not-yet-selected unresolved institutions: {public_411['not_yet_selected_unresolved_after_repair']}",
        f"- Outside current target universe: {public_411['outside_target_universe']}",
        f"- Status: the repair materially closes the public floor by adding {public_411['newly_accepted_through_repair']} old-public institutions, but the floor is still short by {public_411['short_of_inside_target_floor']} inside-target institutions.",
        "",
        "## Columbus State Regression",
        "",
        f"- Unitid: {columbus['unitid']}",
        f"- Target rows: {columbus['year_rows']}",
        f"- Materialized/reviewed repair rows: {columbus['repair_target_rows']}",
        f"- Source-ledger rows accepted through repair: {columbus['repair_source_ledger_rows']}",
        f"- Current-review invalidated/unresolved rows: {columbus['repair_unresolved_rows']}",
        f"- Current final closure class: `{columbus['current_final_closure_class']}`",
        f"- No longer candidate-materialization failure: {columbus['no_longer_candidate_materialization_failure']}",
        "",
        "## Guardrails",
        "",
        "- Unresolved rows are not counted as accepted evidence.",
        "- Source-ledger-resolved-by-other-evidence rows are labeled separately from direct benchmark recoveries.",
        "- Imported LLM/programmatic historical leads remain historical-lead provenance, not human legacy.",
        "- No Step 2 handoff table is constructed.",
        "- This report does not claim journal readiness.",
        "",
    ]
    report = output_dir / "STEP1_POST_REPAIR_CLOSURE_AUDIT_REPORT.md"
    report.write_text("\n".join(lines), encoding="utf-8")
    return report


def build_post_repair_closure_audit(repo_root: Path, output_dir: Path | None = None) -> ClosureResult:
    repo_root = repo_root.resolve()
    output_dir = (output_dir or repo_root / CLOSURE_OUTPUT_ROOT).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    attrition_year, attrition_institution, attrition_summary = load_attrition_frames(repo_root)
    repair_artifacts = discover_repair_artifacts(repo_root)
    if repair_artifacts.release_dir is None:
        raise FileNotFoundError(f"Could not find accepted repair release {REPAIR_RELEASE_DIR_NAME}")
    repair_frames = load_repair_frames(repair_artifacts)
    year_ledger = build_closure_year_ledger(attrition_year, repair_frames)
    institution_ledger = build_closure_institution_ledger(attrition_institution, year_ledger)
    summary = build_summary(institution_ledger, year_ledger, attrition_summary, repair_artifacts, repo_root, output_dir)

    institution_path = output_dir / "institution_closure_ledger.csv"
    year_path = output_dir / "institution_year_closure_ledger.csv"
    summary_path = output_dir / "post_repair_summary.json"
    report_path = write_report(output_dir, summary)
    institution_ledger.to_csv(institution_path, index=False)
    year_ledger.to_csv(year_path, index=False)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    columbus_class = clean_text(summary["columbus_state"]["current_final_closure_class"])
    return ClosureResult(
        output_dir=output_dir,
        institution_ledger=institution_path,
        institution_year_ledger=year_path,
        report=report_path,
        summary_json=summary_path,
        institution_rows=len(institution_ledger),
        institution_year_rows=len(year_ledger),
        combined_accepted_rows=int(summary["accepted_after_repair"]["combined_accepted"]["institution_years"]),
        remaining_unresolved_rows=int(summary["remaining_unresolved_after_repair"]["total"]["institution_years"]),
        target_universe_expected_count_match=bool(summary["target_universe_expected_count_match"]),
        columbus_closure_class=columbus_class,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = build_post_repair_closure_audit(args.root, args.output_dir)
    print(f"institution_rows={result.institution_rows}")
    print(f"institution_year_rows={result.institution_year_rows}")
    print(f"target_universe_expected_count_match={result.target_universe_expected_count_match}")
    print(f"combined_accepted_institution_years={result.combined_accepted_rows}")
    print(f"remaining_unresolved_institution_years={result.remaining_unresolved_rows}")
    print(f"columbus_state_closure_class={result.columbus_closure_class}")
    print(f"output_dir={result.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
