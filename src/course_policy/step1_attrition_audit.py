"""Forensic Step 1 URL/source attrition audit for accepted batches.

This module is diagnostic. It reads accepted production-input/release artifacts
without rewriting them, then writes new audit ledgers and a compact report.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from .step1_proof_to_scale_url_production import load_raw_legacy_url_rows


ATTRITION_CLASSES = [
    "accepted_source_row",
    "not_selected_yet",
    "true_no_upstream_url_evidence",
    "dropped_historical_url_evidence",
    "candidate_materialization_failure",
    "candidate_retrieval_failure",
    "source_review_rejected_wrong_institution",
    "source_review_rejected_wrong_scope_or_year",
    "source_review_rejected_insufficient_evidence",
    "provenance_taxonomy_conflict",
    "needs_text_validation",
    "historical_lead_only",
    "unresolved_unclassified",
]
INSTITUTION_ATTRITION_PRIORITY = [
    "provenance_taxonomy_conflict",
    "candidate_materialization_failure",
    "dropped_historical_url_evidence",
    "needs_text_validation",
    "candidate_retrieval_failure",
    "source_review_rejected_wrong_institution",
    "source_review_rejected_wrong_scope_or_year",
    "source_review_rejected_insufficient_evidence",
    "unresolved_unclassified",
    "true_no_upstream_url_evidence",
    "historical_lead_only",
    "accepted_source_row",
    "not_selected_yet",
]

AUDIT_OUTPUT_ROOT = Path("artifacts/PIPELINE_OUTPUTS/01_url_discovery/reports/step1_attrition_audit_001_040")
HISTORICAL_INVENTORY_ROOT = Path("artifacts/AUDIT_TRAILS/url_discovery_historical_inventory")
URL_DISCOVERY_ROOT = Path("artifacts/PIPELINE_OUTPUTS/01_url_discovery")
OLD_PUBLIC_FLOOR_MIN = 411
TARGET_START_YEAR = 2002
TARGET_END_YEAR = 2016
STEP2_POLICY_FLAGS_PANEL = Path("Stata Files/Data/step2_ipeds_universe_with_policy_flags.dta")
STEP2_BASELINE_2002_PANEL = Path("Stata Files/Data/step2_baseline_2002_representativeness_sample.dta")
TARGET_CONTROL_COLUMNS = [
    "instatetuition",
    "outofstatetuition",
    "faculty",
    "revenue",
    "costs",
    "blacksper",
    "hispper",
    "whitesper",
    "anyaid",
]
GRAD_OUTCOME_COLUMNS = ["grad4per", "grad5per", "grad6per"]
TARGET_PANEL_COLUMNS = [
    "unitid",
    "year",
    "instnm",
    "stabbr",
    "webaddr",
    "sector",
    "control",
    "iclevel",
    "valid_policy_year",
    "ever_collected",
    *TARGET_CONTROL_COLUMNS,
    *GRAD_OUTCOME_COLUMNS,
]
EXPECTED_TARGET_UNIVERSE_COUNTS = {
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


@dataclass(frozen=True)
class BatchArtifacts:
    batch_id: int
    input_dir: Path | None = None
    release_dir: Path | None = None


@dataclass(frozen=True)
class TargetUniverse:
    year_rows: pd.DataFrame
    memberships: pd.DataFrame
    old_public_411: pd.DataFrame
    source_panel: Path
    old_public_source_panel: Path | None


@dataclass(frozen=True)
class AuditResult:
    output_dir: Path
    institution_ledger: Path
    institution_year_ledger: Path
    report: Path
    summary_json: Path
    institution_rows: int
    institution_year_rows: int
    class_counts: dict[str, int]
    target_universe_counts: dict[str, dict[str, int]]
    columbus_class: str
    columbus_secondary_class: str


def clean_text(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        return ""
    return str(value).strip()


def read_csv_or_empty(path: Path | None) -> pd.DataFrame:
    if path is None or not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path, low_memory=False)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def to_int_series(values: object) -> pd.Series:
    return pd.to_numeric(values, errors="coerce").astype("Int64")


def truthy(value: object) -> bool:
    return clean_text(value).lower() in {"1", "1.0", "true", "yes", "y"}


def repo_relative(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        try:
            return path.resolve().relative_to(repo_root.parent.resolve()).as_posix()
        except ValueError:
            return path.as_posix()


def first_existing_path(repo_root: Path, relative_path: Path) -> Path:
    candidates = [
        repo_root / relative_path,
        repo_root.parent / relative_path,
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(f"Could not find {relative_path.as_posix()} from {repo_root}")


def batch_id_from_name(value: object) -> int | None:
    match = re.search(r"batch[_-](\d{3})", clean_text(value))
    if not match:
        return None
    return int(match.group(1))


def sector_label(value: object) -> str:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric):
        return ""
    return {1: "public", 2: "private"}.get(int(numeric), "")


def bool_series(values: object) -> pd.Series:
    if isinstance(values, pd.Series):
        series = values
    else:
        series = pd.Series(values)
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce").fillna(0).ne(0)
    return series.map(truthy)


def load_target_universe(repo_root: Path) -> TargetUniverse:
    source_panel = first_existing_path(repo_root, STEP2_POLICY_FLAGS_PANEL)
    panel = pd.read_stata(source_panel, columns=TARGET_PANEL_COLUMNS, convert_categoricals=False)
    for column in ["unitid", "year", "sector", "control", "iclevel", "valid_policy_year", "ever_collected"]:
        panel[column] = pd.to_numeric(panel[column], errors="coerce")
    for column in [*TARGET_CONTROL_COLUMNS, *GRAD_OUTCOME_COLUMNS]:
        panel[column] = pd.to_numeric(panel[column], errors="coerce")
    complete_mask = (
        panel["year"].between(TARGET_START_YEAR, TARGET_END_YEAR)
        & panel["sector"].isin([1, 2])
        & panel["iclevel"].eq(1)
        & panel[TARGET_CONTROL_COLUMNS].notna().all(axis=1)
        & panel[GRAD_OUTCOME_COLUMNS].notna().any(axis=1)
    )
    complete = panel.loc[complete_mask].copy()
    complete["unitid"] = to_int_series(complete["unitid"])
    complete["academic_year"] = to_int_series(complete["year"])
    complete["target_universe_sector"] = complete["sector"].map(sector_label)
    membership_counts = (
        complete.groupby(["target_universe_sector", "unitid"], dropna=False)
        .agg(sector_complete_years=("academic_year", "nunique"))
        .reset_index()
    )
    memberships = membership_counts.loc[membership_counts["sector_complete_years"].ge(2)].copy()
    complete = complete.merge(memberships[["target_universe_sector", "unitid"]], on=["target_universe_sector", "unitid"], how="inner")

    unit_year_count = (
        complete.groupby("unitid", dropna=False)
        .agg(membership_complete_institution_years=("academic_year", "nunique"))
        .reset_index()
    )
    memberships = memberships.merge(unit_year_count, on="unitid", how="left")
    membership_metadata = (
        complete.sort_values(["unitid", "academic_year"])
        .groupby(["target_universe_sector", "unitid"], dropna=False)
        .agg(
            institution_name=("instnm", lambda values: next((clean_text(v) for v in values if clean_text(v)), "")),
            state=("stabbr", lambda values: next((clean_text(v) for v in values if clean_text(v)), "")),
            homepage_url=("webaddr", lambda values: next((clean_text(v) for v in values if clean_text(v)), "")),
            old_collected_policy_institution=("ever_collected", lambda values: bool(pd.to_numeric(values, errors="coerce").fillna(0).ne(0).any())),
            valid_policy_year_rows=("valid_policy_year", lambda values: int(pd.to_numeric(values, errors="coerce").fillna(0).ne(0).sum())),
            first_complete_target_year=("academic_year", "min"),
            last_complete_target_year=("academic_year", "max"),
        )
        .reset_index()
    )
    memberships = memberships.merge(membership_metadata, on=["target_universe_sector", "unitid"], how="left")
    memberships["never_collected_policy_institution"] = ~memberships["old_collected_policy_institution"]

    old_public_source_panel: Path | None = None
    try:
        old_public_source_panel = first_existing_path(repo_root, STEP2_BASELINE_2002_PANEL)
        old_public_raw = pd.read_stata(
            old_public_source_panel,
            columns=["unitid", "year", "sector", "ever_collected"],
            convert_categoricals=False,
        )
        old_public_raw["unitid"] = to_int_series(old_public_raw["unitid"])
        old_public_raw["sector"] = pd.to_numeric(old_public_raw["sector"], errors="coerce")
        old_public_raw["ever_collected"] = pd.to_numeric(old_public_raw["ever_collected"], errors="coerce")
        old_public_411 = (
            old_public_raw.loc[old_public_raw["sector"].eq(1) & old_public_raw["ever_collected"].fillna(0).ne(0), ["unitid"]]
            .dropna()
            .drop_duplicates()
            .copy()
        )
        old_public_411["old_public_411_diagnostic_member"] = True
    except FileNotFoundError:
        old_public_411 = pd.DataFrame(columns=["unitid", "old_public_411_diagnostic_member"])

    memberships = memberships.merge(old_public_411, on="unitid", how="left")
    memberships["old_public_411_diagnostic_member"] = memberships["old_public_411_diagnostic_member"].fillna(False).astype(bool)

    sector_memberships = (
        memberships.groupby("unitid", dropna=False)
        .agg(target_universe_sector_memberships=("target_universe_sector", join_unique))
        .reset_index()
    )
    year_rows = (
        complete[
            [
                "unitid",
                "academic_year",
                "target_universe_sector",
                "instnm",
                "stabbr",
                "webaddr",
                "ever_collected",
                "valid_policy_year",
            ]
        ]
        .drop_duplicates(["unitid", "academic_year"], keep="first")
        .rename(
            columns={
                "instnm": "target_universe_institution_name",
                "stabbr": "target_universe_state",
                "webaddr": "target_universe_homepage_url",
            }
        )
    )
    year_rows = year_rows.merge(sector_memberships, on="unitid", how="left")
    year_rows = year_rows.merge(old_public_411, on="unitid", how="left")
    year_rows["target_universe_member"] = True
    year_rows["old_collected_policy_institution"] = pd.to_numeric(year_rows["ever_collected"], errors="coerce").fillna(0).ne(0)
    year_rows["old_public_411_diagnostic_member"] = year_rows["old_public_411_diagnostic_member"].fillna(False).astype(bool)
    year_rows = year_rows.drop(columns=["ever_collected"], errors="ignore")
    for column in ["unitid", "academic_year"]:
        year_rows[column] = to_int_series(year_rows[column])
    return TargetUniverse(
        year_rows=year_rows.sort_values(["unitid", "academic_year"]).reset_index(drop=True),
        memberships=memberships.sort_values(["target_universe_sector", "unitid"]).reset_index(drop=True),
        old_public_411=old_public_411.sort_values("unitid").reset_index(drop=True),
        source_panel=source_panel,
        old_public_source_panel=old_public_source_panel,
    )


def candidate_artifact_roots(repo_root: Path) -> list[Path]:
    roots = [repo_root]
    completed = repo_root.parent / "policy_scraper_worktrees" / "completed"
    if completed.exists():
        roots.extend(path for path in sorted(completed.iterdir()) if path.is_dir())
    return roots


def choose_artifact_dir(existing: Path | None, candidate: Path) -> Path:
    if existing is None:
        return candidate
    existing_key = ("attempt_history" in existing.as_posix(), len(existing.as_posix()), existing.as_posix())
    candidate_key = ("attempt_history" in candidate.as_posix(), len(candidate.as_posix()), candidate.as_posix())
    return candidate if candidate_key < existing_key else existing


def discover_batch_artifacts(repo_root: Path, batches: Iterable[int]) -> dict[int, BatchArtifacts]:
    wanted = set(batches)
    found: dict[int, BatchArtifacts] = {batch: BatchArtifacts(batch_id=batch) for batch in wanted}
    for root in candidate_artifact_roots(repo_root):
        base = root / URL_DISCOVERY_ROOT
        input_root = base / "production_inputs"
        if input_root.exists():
            for path in sorted(input_root.iterdir()):
                if not path.is_dir():
                    continue
                batch = batch_id_from_name(path.name)
                if batch not in wanted:
                    continue
                current = found[batch]
                found[batch] = BatchArtifacts(
                    batch_id=batch,
                    input_dir=choose_artifact_dir(current.input_dir, path),
                    release_dir=current.release_dir,
                )
        release_root = base / "production_releases"
        if release_root.exists():
            for path in sorted(release_root.iterdir()):
                if not path.is_dir():
                    continue
                batch = batch_id_from_name(path.name)
                if batch not in wanted:
                    continue
                current = found[batch]
                found[batch] = BatchArtifacts(
                    batch_id=batch,
                    input_dir=current.input_dir,
                    release_dir=choose_artifact_dir(current.release_dir, path),
                )
    return found


def discover_historical_inventory_dir(repo_root: Path) -> Path | None:
    candidates: list[tuple[int, str, Path]] = []
    for root in candidate_artifact_roots(repo_root):
        inventory = root / HISTORICAL_INVENTORY_ROOT
        priority = inventory / "institution_priority_buckets.csv"
        if not priority.exists():
            continue
        try:
            rows = len(pd.read_csv(priority, usecols=["unitid"], low_memory=False))
        except Exception:
            rows = 0
        candidates.append((rows, inventory.as_posix(), inventory))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (-item[0], item[1]))
    return candidates[0][2]


def add_batch_columns(frame: pd.DataFrame, batch_id: int, source_path: Path | None, repo_root: Path) -> pd.DataFrame:
    out = frame.copy()
    out["batch_id"] = f"{batch_id:03d}"
    out["artifact_path"] = repo_relative(source_path, repo_root) if source_path is not None else ""
    if "academic_year" not in out.columns and "target_year" in out.columns:
        out["academic_year"] = out["target_year"]
    if "unitid" in out.columns:
        out["unitid"] = to_int_series(out["unitid"])
    for year_col in ["academic_year", "target_year"]:
        if year_col in out.columns:
            out[year_col] = to_int_series(out[year_col])
    return out


def load_batch_frames(artifacts: dict[int, BatchArtifacts], repo_root: Path) -> dict[str, pd.DataFrame]:
    frames = {
        "target": [],
        "candidate": [],
        "benchmark": [],
        "review": [],
        "ledger": [],
    }
    for batch_id, batch in sorted(artifacts.items()):
        if batch.input_dir:
            for key, filename in [
                ("target", "target_panel.csv"),
                ("candidate", "candidate_url_ledger.csv"),
                ("benchmark", "benchmark_key.csv"),
                ("review", "source_review_log.csv"),
            ]:
                path = batch.input_dir / filename
                frame = read_csv_or_empty(path)
                if not frame.empty:
                    frames[key].append(add_batch_columns(frame, batch_id, path, repo_root))
        if batch.release_dir:
            for path in [batch.release_dir / "data/source_ledger.csv", batch.release_dir / "audit/source_ledger_delta.csv"]:
                frame = read_csv_or_empty(path)
                if not frame.empty:
                    frames["ledger"].append(add_batch_columns(frame, batch_id, path, repo_root))
                    break
    return {key: pd.concat(value, ignore_index=True, sort=False) if value else pd.DataFrame() for key, value in frames.items()}


def load_historical_frames(inventory_dir: Path | None, repo_root: Path) -> dict[str, pd.DataFrame]:
    if inventory_dir is None:
        return {
            "priority": pd.DataFrame(),
            "attempts": pd.DataFrame(),
            "discoveries": pd.DataFrame(),
            "inventory_dir": pd.DataFrame([{"inventory_dir": ""}]),
        }
    out = {
        "priority": read_csv_or_empty(inventory_dir / "institution_priority_buckets.csv"),
        "attempts": read_csv_or_empty(inventory_dir / "normalized_historical_url_attempts.csv"),
        "discoveries": read_csv_or_empty(inventory_dir / "normalized_historical_discoveries.csv"),
        "inventory_dir": pd.DataFrame([{"inventory_dir": repo_relative(inventory_dir, repo_root)}]),
    }
    for key in ["priority", "attempts", "discoveries"]:
        frame = out[key]
        if not frame.empty and "unitid" in frame.columns:
            frame["unitid"] = to_int_series(frame["unitid"])
        if not frame.empty and "academic_year" in frame.columns:
            frame["academic_year"] = to_int_series(frame["academic_year"])
    return out


def expand_raw_legacy_by_year(raw: pd.DataFrame, min_year: int = 2002, max_year: int = 2016) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame(columns=["unitid", "academic_year", "raw_url_count", "raw_legacy_url_count", "raw_lead_url_count"])
    rows: list[dict[str, object]] = []
    for _, record in raw.iterrows():
        unitid = pd.to_numeric(pd.Series([record.get("unitid")]), errors="coerce").iloc[0]
        start = pd.to_numeric(pd.Series([record.get("catalog_year_start")]), errors="coerce").iloc[0]
        end = pd.to_numeric(pd.Series([record.get("catalog_year_end")]), errors="coerce").iloc[0]
        if pd.isna(unitid) or pd.isna(start) or pd.isna(end):
            continue
        provenance = clean_text(record.get("legacy_input_provenance")).lower()
        source_type = clean_text(record.get("candidate_source_type")).lower()
        is_lead = provenance in {"imported_llm_candidate_lead", "historical_programmatic_lead"} or source_type in {
            "imported_llm_candidate_lead",
            "historical_programmatic_lead",
        }
        for year in range(max(min_year, int(start)), min(max_year, int(end)) + 1):
            rows.append(
                {
                    "unitid": int(unitid),
                    "academic_year": year,
                    "raw_url": clean_text(record.get("candidate_url")),
                    "raw_is_lead": is_lead,
                }
            )
    if not rows:
        return pd.DataFrame(columns=["unitid", "academic_year", "raw_url_count", "raw_legacy_url_count", "raw_lead_url_count"])
    expanded = pd.DataFrame(rows)
    grouped = (
        expanded.groupby(["unitid", "academic_year"], dropna=False)
        .agg(
            raw_url_count=("raw_url", "nunique"),
            raw_lead_url_count=("raw_is_lead", "sum"),
        )
        .reset_index()
    )
    grouped["raw_legacy_url_count"] = grouped["raw_url_count"] - grouped["raw_lead_url_count"]
    grouped["unitid"] = to_int_series(grouped["unitid"])
    grouped["academic_year"] = to_int_series(grouped["academic_year"])
    return grouped


def evidence_class_counts(frame: pd.DataFrame, group_cols: list[str], prefix: str) -> pd.DataFrame:
    if frame.empty or "evidence_class" not in frame.columns:
        return pd.DataFrame(columns=[*group_cols])
    working = frame.loc[frame["unitid"].notna()].copy()
    if "academic_year" in group_cols and "academic_year" in working.columns:
        working = working.loc[working["academic_year"].notna()].copy()
    if working.empty:
        return pd.DataFrame(columns=[*group_cols])
    working["evidence_class_clean"] = working["evidence_class"].map(clean_text).str.lower()
    categories = {
        f"{prefix}_valid_human_legacy_rows": "valid_human_legacy",
        f"{prefix}_prior_programmatic_accepted_rows": "prior_programmatic_accepted_needs_current_reverification",
        f"{prefix}_imported_llm_candidate_lead_rows": "imported_llm_candidate_lead_overlay",
        f"{prefix}_unreviewed_prior_programmatic_lead_rows": "unreviewed_prior_programmatic_candidate_lead",
        f"{prefix}_unreviewed_human_legacy_lead_rows": "unreviewed_human_legacy_candidate_lead",
        f"{prefix}_failed_attempt_rows": "programmatic_attempt_no_valid_discovery",
    }
    result = working[group_cols].drop_duplicates().copy()
    for column, evidence_class in categories.items():
        counts = (
            working.loc[working["evidence_class_clean"].eq(evidence_class), group_cols]
            .drop_duplicates()
            .groupby(group_cols, dropna=False)
            .size()
            .reset_index(name=column)
        )
        result = result.merge(counts, on=group_cols, how="left")
        result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0).astype(int)
    return result


def group_counts(frame: pd.DataFrame, group_cols: list[str], output_column: str) -> pd.DataFrame:
    if frame.empty or not set(group_cols).issubset(frame.columns):
        return pd.DataFrame(columns=[*group_cols, output_column])
    working = frame.dropna(subset=group_cols).copy()
    if working.empty:
        return pd.DataFrame(columns=[*group_cols, output_column])
    return working.groupby(group_cols, dropna=False).size().reset_index(name=output_column)


def prepare_unit_year_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["unitid", "academic_year"])
    if "academic_year" not in frame.columns and "target_year" in frame.columns:
        frame = frame.copy()
        frame["academic_year"] = frame["target_year"]
    if not {"unitid", "academic_year"}.issubset(frame.columns):
        return pd.DataFrame(columns=["unitid", "academic_year"])
    out = frame.copy()
    out["unitid"] = to_int_series(out["unitid"])
    out["academic_year"] = to_int_series(out["academic_year"])
    return out


def ensure_columns(frame: pd.DataFrame, defaults: dict[str, object]) -> pd.DataFrame:
    out = frame.copy()
    for column, default in defaults.items():
        if column not in out.columns:
            out[column] = default
    return out


def join_unique(values: object, limit: int = 8) -> str:
    cleaned = sorted({clean_text(value) for value in values if clean_text(value)})
    return "; ".join(cleaned[:limit])


def frame_join_unique(frame: pd.DataFrame, column: str, limit: int = 8) -> str:
    if column not in frame.columns:
        return ""
    return join_unique(frame[column], limit=limit)


def join_features(base: pd.DataFrame, features: list[pd.DataFrame], keys: list[str]) -> pd.DataFrame:
    out = base.copy()
    for feature in features:
        if feature.empty:
            continue
        out = out.merge(feature, on=keys, how="left")
    for column in out.columns:
        if column.endswith("_rows") or column.endswith("_count"):
            out[column] = pd.to_numeric(out[column], errors="coerce").fillna(0).astype(int)
    return out


def review_summary(review: pd.DataFrame) -> pd.DataFrame:
    review = prepare_unit_year_frame(review)
    if review.empty:
        return pd.DataFrame(columns=["unitid", "academic_year"])
    working = review.copy()
    working["review_decision_clean"] = working.get("review_decision", pd.Series("", index=working.index)).map(clean_text).str.lower()
    working["retrieval_status_clean"] = working.get("retrieval_status", pd.Series("", index=working.index)).map(clean_text).str.lower()
    grouped = working.groupby(["unitid", "academic_year"], dropna=False)
    rows = []
    for key, group in grouped:
        decisions = sorted({clean_text(value) for value in group.get("review_decision", []) if clean_text(value)})
        retrievals = sorted({clean_text(value) for value in group.get("retrieval_status", []) if clean_text(value)})
        decision_text = " ".join(value.lower() for value in decisions)
        retrieval_text = " ".join(value.lower() for value in retrievals)
        rows.append(
            {
                "unitid": key[0],
                "academic_year": key[1],
                "source_review_rows": len(group),
                "source_review_artifact_paths": join_unique(group.get("artifact_path", [])),
                "review_decisions": "; ".join(decisions),
                "retrieval_statuses": "; ".join(retrievals),
                "review_has_accept": any(value.startswith("accept") for value in group["review_decision_clean"]),
                "review_has_needs_text_validation": "needs_text_validation" in decision_text,
                "review_has_no_candidate": "no_target_year_candidate" in decision_text or "no_candidate" in decision_text,
                "review_has_retrieval_failure": any(
                    token in retrieval_text or token in decision_text
                    for token in ["http_error", "error", "unretrievable", "dead"]
                ),
                "review_has_wrong_institution": "wrong_institution" in decision_text,
                "review_has_wrong_scope_or_year": any(
                    token in decision_text for token in ["wrong_year", "wrong_scope", "not_catalog", "not_policy"]
                ),
                "review_has_insufficient_evidence": any(
                    token in decision_text for token in ["not_confirmed", "insufficient", "rejected"]
                ),
            }
        )
    return pd.DataFrame(rows)


def ledger_summary(ledger: pd.DataFrame) -> pd.DataFrame:
    ledger = prepare_unit_year_frame(ledger)
    if ledger.empty:
        return pd.DataFrame(columns=["unitid", "academic_year"])
    working = ledger.copy()
    url_col = "accepted_source_url" if "accepted_source_url" in working.columns else "source_url"
    if url_col not in working.columns:
        working[url_col] = ""
    grouped = (
        working.groupby(["unitid", "academic_year"], dropna=False)
        .agg(source_ledger_rows=(url_col, "size"), accepted_source_urls=(url_col, lambda values: "; ".join(sorted({clean_text(v) for v in values if clean_text(v)})[:5])))
        .reset_index()
    )
    artifact_paths = (
        working.groupby(["unitid", "academic_year"], dropna=False)
        .agg(source_ledger_artifact_paths=("artifact_path", join_unique))
        .reset_index()
    )
    grouped = grouped.merge(artifact_paths, on=["unitid", "academic_year"], how="left")
    return grouped


def provenance_taxonomy_conflict(row: pd.Series) -> bool:
    text = " ".join(
        clean_text(row.get(column)).lower()
        for column in [
            "review_decisions",
            "candidate_generation_methods",
            "candidate_source_types",
            "benchmark_groups",
            "provenance_types",
        ]
    )
    has_human_label = "human_legacy" in text or "raw_human_legacy_url" in text
    has_human_evidence = row.get("has_valid_human_legacy", False)
    has_lead_evidence = row.get("has_imported_llm_candidate_lead", False) or row.get("has_unreviewed_candidate_lead", False)
    return bool((has_human_label and not has_human_evidence) or (has_human_label and has_lead_evidence and not has_human_evidence))


def classify_year(row: pd.Series) -> tuple[str, str]:
    selected = bool(row.get("selected_in_accepted_batch", False))
    has_upstream = bool(row.get("has_upstream_url_evidence", False))
    has_historical = bool(row.get("has_historical_url_evidence", False))
    has_candidate = row.get("candidate_url_rows", 0) > 0
    has_benchmark = row.get("benchmark_key_rows", 0) > 0
    if row.get("source_ledger_rows", 0) > 0 or row.get("review_has_accept", False):
        return "accepted_source_row", ""
    if row.get("review_has_needs_text_validation", False):
        return "needs_text_validation", ""
    if row.get("provenance_taxonomy_conflict", False):
        return "provenance_taxonomy_conflict", ""
    if not selected:
        return "not_selected_yet", ""
    if has_upstream and not has_candidate and not has_benchmark:
        secondary = "dropped_historical_url_evidence" if has_historical else ""
        return "candidate_materialization_failure", secondary
    if not has_upstream:
        return "true_no_upstream_url_evidence", ""
    if row.get("review_has_retrieval_failure", False):
        return "candidate_retrieval_failure", ""
    if row.get("review_has_wrong_institution", False):
        return "source_review_rejected_wrong_institution", ""
    if row.get("review_has_wrong_scope_or_year", False):
        return "source_review_rejected_wrong_scope_or_year", ""
    if row.get("review_has_insufficient_evidence", False) or row.get("review_has_no_candidate", False):
        return "source_review_rejected_insufficient_evidence", ""
    if row.get("historical_lead_only", False):
        return "historical_lead_only", ""
    return "unresolved_unclassified", ""


def step2_eligibility(row: pd.Series) -> str:
    attrition = clean_text(row.get("attrition_class"))
    if attrition == "accepted_source_row":
        return "eligible_source_accepted"
    if attrition == "needs_text_validation":
        return "requires_text_validation"
    if attrition in {"candidate_materialization_failure", "dropped_historical_url_evidence", "provenance_taxonomy_conflict"}:
        return "blocked_flag_for_step2"
    return "not_eligible_without_review"


def build_institution_year_ledger(
    target: pd.DataFrame,
    candidate: pd.DataFrame,
    benchmark: pd.DataFrame,
    review: pd.DataFrame,
    ledger: pd.DataFrame,
    historical: dict[str, pd.DataFrame],
    raw_year: pd.DataFrame,
    target_universe_years: pd.DataFrame | None = None,
) -> pd.DataFrame:
    target_universe_years = prepare_unit_year_frame(target_universe_years) if target_universe_years is not None else pd.DataFrame()
    target = prepare_unit_year_frame(target)
    candidate = prepare_unit_year_frame(candidate)
    benchmark = prepare_unit_year_frame(benchmark)
    review = prepare_unit_year_frame(review)
    ledger = prepare_unit_year_frame(ledger)
    target = ensure_columns(
        target,
        {
            "batch_id": "",
            "artifact_path": "",
            "institution_name": "",
            "sector": "",
            "state": "",
            "homepage_url": "",
            "target_inclusion_reason": "",
            "has_human_legacy_source": False,
        },
    )
    candidate = ensure_columns(
        candidate,
        {
            "artifact_path": "",
            "candidate_url": "",
            "candidate_generation_method": "",
            "candidate_source_type": "",
        },
    )
    benchmark = ensure_columns(
        benchmark,
        {
            "artifact_path": "",
            "benchmark_url": "",
            "benchmark_group": "",
        },
    )
    review = ensure_columns(review, {"artifact_path": ""})
    ledger = ensure_columns(ledger, {"artifact_path": ""})
    if not target_universe_years.empty:
        base = ensure_columns(
            target_universe_years,
            {
                "target_universe_member": True,
                "target_universe_sector": "",
                "target_universe_sector_memberships": "",
                "target_universe_institution_name": "",
                "target_universe_state": "",
                "target_universe_homepage_url": "",
                "old_collected_policy_institution": False,
                "old_public_411_diagnostic_member": False,
            },
        ).copy()
    else:
        target_keys = target[["unitid", "academic_year"]].drop_duplicates().copy() if not target.empty else pd.DataFrame(columns=["unitid", "academic_year"])
        hist_attempt_keys = historical["attempts"][["unitid", "academic_year"]].dropna().drop_duplicates() if not historical["attempts"].empty else pd.DataFrame(columns=["unitid", "academic_year"])
        hist_discovery_keys = historical["discoveries"][["unitid", "academic_year"]].dropna().drop_duplicates() if not historical["discoveries"].empty else pd.DataFrame(columns=["unitid", "academic_year"])
        raw_keys = raw_year[["unitid", "academic_year"]].drop_duplicates() if not raw_year.empty else pd.DataFrame(columns=["unitid", "academic_year"])
        base = pd.concat([target_keys, hist_attempt_keys, hist_discovery_keys, raw_keys], ignore_index=True).drop_duplicates()
        base["target_universe_member"] = False
        base["target_universe_sector"] = ""
        base["target_universe_sector_memberships"] = ""
        base["target_universe_institution_name"] = ""
        base["target_universe_state"] = ""
        base["target_universe_homepage_url"] = ""
        base["old_collected_policy_institution"] = False
        base["old_public_411_diagnostic_member"] = False
    base["unitid"] = to_int_series(base["unitid"])
    base["academic_year"] = to_int_series(base["academic_year"])
    base = base.loc[base["unitid"].notna() & base["academic_year"].notna()].copy()

    selected = (
        target.groupby(["unitid", "academic_year"], dropna=False)
        .agg(
            selected_target_rows=("academic_year", "size"),
            selected_batches=("batch_id", join_unique),
            target_artifact_paths=("artifact_path", join_unique),
            target_inclusion_reasons=("target_inclusion_reason", join_unique),
            institution_name=("institution_name", lambda values: next((clean_text(v) for v in values if clean_text(v)), "")),
            sector=("sector", lambda values: next((clean_text(v) for v in values if clean_text(v)), "")),
            state=("state", lambda values: next((clean_text(v) for v in values if clean_text(v)), "")),
            homepage_url=("homepage_url", lambda values: next((clean_text(v) for v in values if clean_text(v)), "")),
            has_human_legacy_source=("has_human_legacy_source", lambda values: any(truthy(v) for v in values)),
        )
        .reset_index()
        if not target.empty
        else pd.DataFrame(columns=["unitid", "academic_year"])
    )
    candidate_counts = group_counts(candidate, ["unitid", "academic_year"], "candidate_url_rows")
    if not candidate.empty:
        candidate_extra = (
            candidate.groupby(["unitid", "academic_year"], dropna=False)
            .agg(
                candidate_urls=("candidate_url", lambda values: join_unique(values, limit=5)),
                candidate_generation_methods=("candidate_generation_method", lambda values: join_unique(values, limit=5)),
                candidate_source_types=("candidate_source_type", lambda values: join_unique(values, limit=5)),
                candidate_artifact_paths=("artifact_path", join_unique),
            )
            .reset_index()
        )
    else:
        candidate_extra = pd.DataFrame(columns=["unitid", "academic_year"])
    benchmark_counts = group_counts(benchmark, ["unitid", "academic_year"], "benchmark_key_rows")
    if not benchmark.empty:
        benchmark_extra = (
            benchmark.groupby(["unitid", "academic_year"], dropna=False)
            .agg(
                benchmark_urls=("benchmark_url", lambda values: join_unique(values, limit=5)),
                benchmark_groups=("benchmark_group", lambda values: join_unique(values, limit=5)),
                benchmark_artifact_paths=("artifact_path", join_unique),
            )
            .reset_index()
        )
    else:
        benchmark_extra = pd.DataFrame(columns=["unitid", "academic_year"])

    hist_attempt_counts = evidence_class_counts(historical["attempts"], ["unitid", "academic_year"], "historical_attempt")
    hist_discovery_counts = evidence_class_counts(historical["discoveries"], ["unitid", "academic_year"], "historical_discovery")
    review_counts = review_summary(review)
    ledger_counts = ledger_summary(ledger)

    out = join_features(
        base,
        [
            selected,
            candidate_counts,
            candidate_extra,
            benchmark_counts,
            benchmark_extra,
            raw_year,
            hist_attempt_counts,
            hist_discovery_counts,
            review_counts,
            ledger_counts,
        ],
        ["unitid", "academic_year"],
    )
    for text_col in [
        "institution_name",
        "sector",
        "state",
        "homepage_url",
        "selected_batches",
        "target_universe_sector",
        "target_universe_sector_memberships",
        "target_universe_institution_name",
        "target_universe_state",
        "target_universe_homepage_url",
    ]:
        if text_col not in out.columns:
            out[text_col] = ""
        out[text_col] = out[text_col].map(clean_text)
    out["target_universe_member"] = bool_series(out.get("target_universe_member", pd.Series(False, index=out.index)))
    out["old_collected_policy_institution"] = bool_series(out.get("old_collected_policy_institution", pd.Series(False, index=out.index)))
    out["old_public_411_diagnostic_member"] = bool_series(out.get("old_public_411_diagnostic_member", pd.Series(False, index=out.index)))
    out["institution_name"] = out["institution_name"].where(out["institution_name"].ne(""), out["target_universe_institution_name"])
    out["sector"] = out["sector"].where(out["sector"].ne(""), out["target_universe_sector"])
    out["state"] = out["state"].where(out["state"].ne(""), out["target_universe_state"])
    out["homepage_url"] = out["homepage_url"].where(out["homepage_url"].ne(""), out["target_universe_homepage_url"])
    out["selected_in_accepted_batch"] = out.get("selected_target_rows", pd.Series(0, index=out.index)).fillna(0).astype(int).gt(0)
    out["has_raw_url_evidence"] = out.get("raw_url_count", pd.Series(0, index=out.index)).fillna(0).astype(int).gt(0)
    out["has_historical_attempt_evidence"] = out.filter(like="historical_attempt_").sum(axis=1).gt(0)
    out["has_historical_discovery_evidence"] = out.filter(like="historical_discovery_").sum(axis=1).gt(0)
    out["has_historical_url_evidence"] = out["has_historical_attempt_evidence"] | out["has_historical_discovery_evidence"]
    out["has_upstream_url_evidence"] = out["has_raw_url_evidence"] | out["has_historical_url_evidence"]
    out["has_valid_human_legacy"] = (
        out.get("historical_attempt_valid_human_legacy_rows", pd.Series(0, index=out.index)).fillna(0).astype(int)
        + out.get("historical_discovery_valid_human_legacy_rows", pd.Series(0, index=out.index)).fillna(0).astype(int)
        + out.get("raw_legacy_url_count", pd.Series(0, index=out.index)).fillna(0).astype(int)
    ).gt(0)
    out["has_prior_programmatic_accepted"] = (
        out.get("historical_attempt_prior_programmatic_accepted_rows", pd.Series(0, index=out.index)).fillna(0).astype(int)
        + out.get("historical_discovery_prior_programmatic_accepted_rows", pd.Series(0, index=out.index)).fillna(0).astype(int)
    ).gt(0)
    out["has_imported_llm_candidate_lead"] = (
        out.get("historical_attempt_imported_llm_candidate_lead_rows", pd.Series(0, index=out.index)).fillna(0).astype(int)
        + out.get("historical_discovery_imported_llm_candidate_lead_rows", pd.Series(0, index=out.index)).fillna(0).astype(int)
    ).gt(0)
    out["has_unreviewed_candidate_lead"] = (
        out.get("historical_attempt_unreviewed_prior_programmatic_lead_rows", pd.Series(0, index=out.index)).fillna(0).astype(int)
        + out.get("historical_attempt_unreviewed_human_legacy_lead_rows", pd.Series(0, index=out.index)).fillna(0).astype(int)
        + out.get("historical_discovery_unreviewed_prior_programmatic_lead_rows", pd.Series(0, index=out.index)).fillna(0).astype(int)
        + out.get("historical_discovery_unreviewed_human_legacy_lead_rows", pd.Series(0, index=out.index)).fillna(0).astype(int)
    ).gt(0)
    out["has_failed_historical_attempt"] = (
        out.get("historical_attempt_failed_attempt_rows", pd.Series(0, index=out.index)).fillna(0).astype(int)
        + out.get("historical_discovery_failed_attempt_rows", pd.Series(0, index=out.index)).fillna(0).astype(int)
    ).gt(0)
    out["historical_lead_only"] = (
        (out["has_imported_llm_candidate_lead"] | out["has_unreviewed_candidate_lead"] | out["has_failed_historical_attempt"])
        & ~out["has_valid_human_legacy"]
        & ~out["has_prior_programmatic_accepted"]
    )
    out["provenance_taxonomy_conflict"] = out.apply(provenance_taxonomy_conflict, axis=1)
    classes = out.apply(classify_year, axis=1)
    out["attrition_class"] = [item[0] for item in classes]
    out["secondary_attrition_class"] = [item[1] for item in classes]
    out["step2_eligibility"] = out.apply(step2_eligibility, axis=1)
    return out.sort_values(["unitid", "academic_year"]).reset_index(drop=True)


def build_institution_ledger(
    year_ledger: pd.DataFrame,
    historical_priority: pd.DataFrame,
    target_universe_memberships: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if year_ledger.empty:
        return pd.DataFrame()
    priority = historical_priority.copy()
    if not priority.empty and "unitid" in priority.columns:
        priority["unitid"] = to_int_series(priority["unitid"])
        keep = [
            column
            for column in [
                "unitid",
                "priority_bucket",
                "valid_human_legacy_rows",
                "prior_programmatic_accepted_rows",
                "imported_llm_candidate_lead_rows",
                "unreviewed_candidate_lead_rows",
                "failed_attempt_rows",
            ]
            if column in priority.columns
        ]
        priority = priority[keep].drop_duplicates("unitid", keep="first")
    grouped_rows = []
    priority_order = {label: index for index, label in enumerate(INSTITUTION_ATTRITION_PRIORITY)}
    if target_universe_memberships is not None and not target_universe_memberships.empty:
        membership_iter = list(target_universe_memberships.iterrows())
    else:
        membership_iter = []
        for unitid, group in year_ledger.groupby("unitid", dropna=False):
            sector = next((clean_text(v) for v in group["sector"] if clean_text(v)), "")
            membership_iter.append(
                (
                    len(membership_iter),
                    pd.Series(
                        {
                            "unitid": unitid,
                            "target_universe_sector": sector,
                            "institution_name": next((clean_text(v) for v in group["institution_name"] if clean_text(v)), ""),
                            "state": next((clean_text(v) for v in group["state"] if clean_text(v)), ""),
                            "homepage_url": next((clean_text(v) for v in group["homepage_url"] if clean_text(v)), ""),
                            "membership_complete_institution_years": len(group),
                            "sector_complete_years": len(group),
                            "old_collected_policy_institution": False,
                            "never_collected_policy_institution": False,
                            "old_public_411_diagnostic_member": False,
                        }
                    ),
                )
            )
    for _, membership in membership_iter:
        unitid = membership["unitid"]
        group = year_ledger.loc[year_ledger["unitid"].eq(unitid)].copy()
        if group.empty:
            continue
        classes = group["attrition_class"].value_counts().to_dict()
        chosen = min(classes, key=lambda value: priority_order.get(value, 99))
        sector = clean_text(membership.get("target_universe_sector")) or next((clean_text(v) for v in group["sector"] if clean_text(v)), "")
        selected_rows = int(group["selected_in_accepted_batch"].sum())
        old_public_member = bool(membership.get("old_public_411_diagnostic_member", False))
        public_disposition = "not_old_public_411_member"
        if old_public_member:
            if int((group["attrition_class"] == "accepted_source_row").sum()) > 0:
                public_disposition = "accepted_source_row"
            elif selected_rows:
                public_disposition = "selected_unresolved"
            else:
                public_disposition = "not_selected_yet"
        grouped_rows.append(
            {
                "unitid": unitid,
                "institution_name": clean_text(membership.get("institution_name")) or next((clean_text(v) for v in group["institution_name"] if clean_text(v)), ""),
                "sector": sector,
                "state": clean_text(membership.get("state")) or next((clean_text(v) for v in group["state"] if clean_text(v)), ""),
                "homepage_url": clean_text(membership.get("homepage_url")),
                "target_universe_member": bool(target_universe_memberships is not None and not target_universe_memberships.empty),
                "complete_institution_years": int(pd.to_numeric(pd.Series([membership.get("membership_complete_institution_years")]), errors="coerce").fillna(len(group)).iloc[0]),
                "sector_specific_complete_years": int(pd.to_numeric(pd.Series([membership.get("sector_complete_years")]), errors="coerce").fillna(len(group)).iloc[0]),
                "old_collected_policy_institution": bool(membership.get("old_collected_policy_institution", False)),
                "never_collected_policy_institution": bool(membership.get("never_collected_policy_institution", False)),
                "old_public_411_diagnostic_member": old_public_member,
                "target_year_rows": selected_rows,
                "year_rows_in_audit": len(group),
                "accepted_source_rows": int((group["attrition_class"] == "accepted_source_row").sum()),
                "candidate_materialization_failure_rows": int((group["attrition_class"] == "candidate_materialization_failure").sum()),
                "dropped_historical_url_evidence_rows": int((group["secondary_attrition_class"] == "dropped_historical_url_evidence").sum()),
                "needs_text_validation_rows": int((group["attrition_class"] == "needs_text_validation").sum()),
                "not_selected_year_rows": int((group["attrition_class"] == "not_selected_yet").sum()),
                "has_upstream_url_evidence": bool(group["has_upstream_url_evidence"].any()),
                "has_valid_human_legacy": bool(group["has_valid_human_legacy"].any()),
                "has_prior_programmatic_accepted": bool(group["has_prior_programmatic_accepted"].any()),
                "has_historical_lead_only": bool(group["historical_lead_only"].any()),
                "old_public_411_diagnostic_disposition": public_disposition,
                "institution_attrition_class": chosen,
                "attrition_class_counts": json.dumps(classes, sort_keys=True),
                "selected_batches": "; ".join(sorted({clean_text(v) for v in group["selected_batches"] if clean_text(v)})),
                "target_artifact_paths": frame_join_unique(group, "target_artifact_paths"),
                "candidate_artifact_paths": frame_join_unique(group, "candidate_artifact_paths"),
                "benchmark_artifact_paths": frame_join_unique(group, "benchmark_artifact_paths"),
                "source_review_artifact_paths": frame_join_unique(group, "source_review_artifact_paths"),
                "source_ledger_artifact_paths": frame_join_unique(group, "source_ledger_artifact_paths"),
            }
        )
    out = pd.DataFrame(grouped_rows)
    if not priority.empty:
        out = out.merge(priority, on="unitid", how="left")
    return out.sort_values(["institution_attrition_class", "unitid"]).reset_index(drop=True)


def compact_count_table(series: pd.Series) -> str:
    counts = series.value_counts().rename_axis("class").reset_index(name="rows")
    if counts.empty:
        return "| class | rows |\n|---|---:|\n"
    lines = ["| class | rows |", "|---|---:|"]
    lines.extend(f"| {row['class']} | {int(row['rows'])} |" for _, row in counts.iterrows())
    return "\n".join(lines) + "\n"


def compact_count_dict(counts: dict[str, int]) -> str:
    if not counts:
        return "| class | rows |\n|---|---:|\n"
    ordered = sorted(counts.items(), key=lambda item: (-int(item[1]), item[0]))
    lines = ["| class | rows |", "|---|---:|"]
    lines.extend(f"| {label} | {int(count)} |" for label, count in ordered)
    return "\n".join(lines) + "\n"


def target_universe_count_summary(institution: pd.DataFrame, year: pd.DataFrame, old_public_411: pd.DataFrame) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = {}
    for sector in ["public", "private"]:
        sector_rows = institution.loc[institution["sector"].eq(sector)].copy()
        summary[sector] = {
            "institutions": int(len(sector_rows)),
            "membership_complete_institution_years": int(pd.to_numeric(sector_rows.get("complete_institution_years", pd.Series(dtype=int)), errors="coerce").fillna(0).sum()),
            "sector_specific_complete_years": int(pd.to_numeric(sector_rows.get("sector_specific_complete_years", pd.Series(dtype=int)), errors="coerce").fillna(0).sum()),
            "old_collected_policy_institutions": int(bool_series(sector_rows.get("old_collected_policy_institution", pd.Series(dtype=bool))).sum()),
            "never_collected_policy_institutions": int(bool_series(sector_rows.get("never_collected_policy_institution", pd.Series(dtype=bool))).sum()),
        }
    old_public_ids = set(to_int_series(old_public_411["unitid"]).dropna().astype(int).tolist()) if not old_public_411.empty else set()
    target_public_ids = set(to_int_series(institution.loc[institution["sector"].eq("public"), "unitid"]).dropna().astype(int).tolist())
    summary["old_public_411_diagnostic"] = {
        "institutions": int(len(old_public_ids)),
        "inside_target_universe": int(len(old_public_ids & target_public_ids)),
        "outside_target_universe": int(len(old_public_ids - target_public_ids)),
        "accepted_source_in_target": int(institution.loc[institution["old_public_411_diagnostic_member"] & institution["accepted_source_rows"].gt(0), "unitid"].nunique()),
        "selected_unresolved_in_target": int(
            institution.loc[
                institution["old_public_411_diagnostic_member"]
                & institution["target_year_rows"].gt(0)
                & institution["accepted_source_rows"].eq(0),
                "unitid",
            ].nunique()
        ),
        "not_selected_in_target": int(
            institution.loc[
                institution["old_public_411_diagnostic_member"]
                & institution["target_year_rows"].eq(0)
                & institution["accepted_source_rows"].eq(0),
                "unitid",
            ].nunique()
        ),
    }
    summary["total"] = {
        "sector_institution_memberships": int(len(institution)),
        "unique_institutions": int(institution["unitid"].nunique()),
        "unique_complete_institution_years": int(len(year)),
        "old_collected_policy_institutions": int(sum(summary[sector]["old_collected_policy_institutions"] for sector in ["public", "private"])),
        "never_collected_policy_institutions": int(sum(summary[sector]["never_collected_policy_institutions"] for sector in ["public", "private"])),
    }
    return summary


def target_universe_expected_match(summary: dict[str, dict[str, int]]) -> bool:
    checks = [
        summary.get("public", {}).get("institutions") == EXPECTED_TARGET_UNIVERSE_COUNTS["public"]["institutions"],
        summary.get("public", {}).get("membership_complete_institution_years")
        == EXPECTED_TARGET_UNIVERSE_COUNTS["public"]["membership_complete_institution_years"],
        summary.get("public", {}).get("old_collected_policy_institutions")
        == EXPECTED_TARGET_UNIVERSE_COUNTS["public"]["old_collected_policy_institutions"],
        summary.get("public", {}).get("never_collected_policy_institutions")
        == EXPECTED_TARGET_UNIVERSE_COUNTS["public"]["never_collected_policy_institutions"],
        summary.get("private", {}).get("institutions") == EXPECTED_TARGET_UNIVERSE_COUNTS["private"]["institutions"],
        summary.get("private", {}).get("membership_complete_institution_years")
        == EXPECTED_TARGET_UNIVERSE_COUNTS["private"]["membership_complete_institution_years"],
        summary.get("private", {}).get("old_collected_policy_institutions")
        == EXPECTED_TARGET_UNIVERSE_COUNTS["private"]["old_collected_policy_institutions"],
        summary.get("private", {}).get("never_collected_policy_institutions")
        == EXPECTED_TARGET_UNIVERSE_COUNTS["private"]["never_collected_policy_institutions"],
        summary.get("total", {}).get("sector_institution_memberships")
        == EXPECTED_TARGET_UNIVERSE_COUNTS["total"]["sector_institution_memberships"],
        summary.get("total", {}).get("unique_complete_institution_years")
        == EXPECTED_TARGET_UNIVERSE_COUNTS["total"]["unique_complete_institution_years"],
        summary.get("total", {}).get("old_collected_policy_institutions")
        == EXPECTED_TARGET_UNIVERSE_COUNTS["total"]["old_collected_policy_institutions"],
        summary.get("total", {}).get("never_collected_policy_institutions")
        == EXPECTED_TARGET_UNIVERSE_COUNTS["total"]["never_collected_policy_institutions"],
    ]
    return all(checks)


def write_report(
    output_dir: Path,
    institution: pd.DataFrame,
    year: pd.DataFrame,
    artifacts: dict[int, BatchArtifacts],
    historical: dict[str, pd.DataFrame],
    target_universe: TargetUniverse,
    target_counts: dict[str, dict[str, int]],
) -> Path:
    columbus_year = year.loc[year["unitid"].astype(str).eq("139366")].copy()
    columbus_inst = institution.loc[institution["unitid"].astype(str).eq("139366")].copy()
    class_counts = year["attrition_class"].value_counts().to_dict()
    secondary_counts = year["secondary_attrition_class"].replace("", pd.NA).dropna().value_counts().to_dict()
    batches_with_inputs = sum(1 for batch in artifacts.values() if batch.input_dir is not None)
    batches_with_releases = sum(1 for batch in artifacts.values() if batch.release_dir is not None)
    inventory_dir = historical["inventory_dir"].iloc[0]["inventory_dir"] if not historical["inventory_dir"].empty else ""
    old_collected = institution.loc[institution["old_collected_policy_institution"]]
    never_collected = institution.loc[institution["never_collected_policy_institution"]]
    valid_human = institution.loc[institution["has_valid_human_legacy"]]
    lead_only = institution.loc[institution["has_historical_lead_only"]]
    materialization = year.loc[year["attrition_class"].eq("candidate_materialization_failure")]
    conflict = year.loc[year["attrition_class"].eq("provenance_taxonomy_conflict")]
    needs_text = year.loc[year["attrition_class"].eq("needs_text_validation")]

    lines = [
        "# Step 1 Forensic Attrition Audit 001-040",
        "",
        "Diagnostic audit only. Prior accepted releases are read, not rewritten.",
        "",
        "## Inputs",
        "",
        f"- Accepted batch input directories found: {batches_with_inputs}/40",
        f"- Accepted batch release directories found: {batches_with_releases}/40",
        f"- Target universe source: `{repo_relative(target_universe.source_panel, output_dir.parents[4]) if len(output_dir.parents) > 4 else target_universe.source_panel.as_posix()}`",
        f"- Old public 411 diagnostic source: `{repo_relative(target_universe.old_public_source_panel, output_dir.parents[4]) if target_universe.old_public_source_panel and len(output_dir.parents) > 4 else clean_text(target_universe.old_public_source_panel)}`",
        f"- Historical inventory used: `{inventory_dir}`",
        "",
        "## Target-Universe Disposition",
        "",
        "| Sector | Target-universe institutions | Complete institution-years | Old collected-policy institutions | Never-collected institutions |",
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
        f"- Target-universe count check: {'matched expected 1,810 / 23,853 denominator' if target_universe_expected_match(target_counts) else 'NOT MATCHED'}",
        "- Sector institution-year subtotals are membership counts. The total complete institution-year count is the de-duplicated unitid-year denominator.",
        "",
        "## Old Collected-Policy vs Never-Collected",
        "",
        f"- Old collected-policy sector-institution memberships: {len(old_collected)}",
        f"- Never-collected sector-institution memberships: {len(never_collected)}",
        f"- Old collected-policy memberships with accepted source rows: {int(old_collected['accepted_source_rows'].gt(0).sum()) if not old_collected.empty else 0}",
        f"- Never-collected memberships with accepted source rows: {int(never_collected['accepted_source_rows'].gt(0).sum()) if not never_collected.empty else 0}",
        "",
        "## Attrition Class Counts",
        "",
        compact_count_table(year["attrition_class"]),
        "## Secondary Attrition Flags",
        "",
        compact_count_dict({str(key): int(value) for key, value in secondary_counts.items()}),
        "## Old Public 411 Diagnostic Subset",
        "",
        f"- Old public diagnostic institutions: {target_counts['old_public_411_diagnostic']['institutions']}",
        f"- Inside target universe: {target_counts['old_public_411_diagnostic']['inside_target_universe']}",
        f"- Outside target universe: {target_counts['old_public_411_diagnostic']['outside_target_universe']}",
        f"- Accepted source in target universe: {target_counts['old_public_411_diagnostic']['accepted_source_in_target']}",
        f"- Selected but unresolved in target universe: {target_counts['old_public_411_diagnostic']['selected_unresolved_in_target']}",
        f"- Not selected in target universe: {target_counts['old_public_411_diagnostic']['not_selected_in_target']}",
        f"- Old public floor reference: {OLD_PUBLIC_FLOOR_MIN}; diagnostic only, not the primary Step 1 denominator.",
        "",
        "## Valid-Human-Legacy Disposition",
        "",
        f"- Institutions with valid-human/raw legacy evidence: {valid_human['unitid'].nunique() if not valid_human.empty else 0}",
        f"- Valid-human rows with candidate materialization failure: {int(year.loc[year['has_valid_human_legacy'] & year['attrition_class'].eq('candidate_materialization_failure')].shape[0])}",
        "",
        "## Historical/Programmatic/LLM Lead Disposition",
        "",
        f"- Historical-lead-only institutions: {lead_only['unitid'].nunique() if not lead_only.empty else 0}",
        f"- Historical-lead-only rows not selected yet: {int(year.loc[year['historical_lead_only'] & year['attrition_class'].eq('not_selected_yet')].shape[0])}",
        "",
        "## Unresolved Cases With Upstream Evidence",
        "",
        f"- Candidate materialization failures: {len(materialization)}",
        f"- Dropped historical URL evidence flags: {int(year['secondary_attrition_class'].eq('dropped_historical_url_evidence').sum())}",
        f"- Provenance/taxonomy conflicts: {len(conflict)}",
        f"- Needs text validation: {len(needs_text)}",
        "",
        "## Columbus State Regression",
        "",
    ]
    if columbus_year.empty:
        lines.append("- `unitid=139366` was not found in the audit ledger.")
    else:
        columbus_classes = columbus_year["attrition_class"].value_counts().to_dict()
        secondary = columbus_year["secondary_attrition_class"].replace("", pd.NA).dropna().value_counts().to_dict()
        selected_batches = "; ".join(sorted({clean_text(v) for v in columbus_year["selected_batches"] if clean_text(v)}))
        lines.extend(
            [
                f"- Selected batches: {selected_batches or 'none'}",
                f"- Year rows: {len(columbus_year)}",
                f"- Attrition classes: `{json.dumps(columbus_classes, sort_keys=True)}`",
                f"- Secondary flags: `{json.dumps(secondary, sort_keys=True)}`",
                f"- Institution class: `{clean_text(columbus_inst.iloc[0]['institution_attrition_class']) if not columbus_inst.empty else ''}`",
                "- Required finding: Columbus State is a candidate-materialization/dropped-historical-URL process failure, not a true no-evidence failure.",
            ]
        )
    lines.extend(
        [
            "",
            "## Hard-Gate Recommendations",
            "",
            "- A selected institution with eligible historical URL evidence cannot have an empty candidate ledger unless an explicit exclusion reason is recorded.",
            "- True human legacy, prior programmatic accepted, imported LLM candidate lead, failed historical attempt, and unreviewed candidate lead must remain separate provenance classes.",
            "- `no_candidate_found` cannot be interpreted as true source failure when upstream eligible URL evidence exists.",
            "- Step 2 handoff must exclude or flag unresolved/provenance-conflicted rows.",
            "- Columbus State (`unitid=139366`) must remain a regression test.",
            "",
            "## Output Files",
            "",
            "- `institution_attrition_ledger.csv`",
            "- `institution_year_attrition_ledger.csv`",
            "- `attrition_summary.json`",
            "",
        ]
    )
    report = output_dir / "STEP1_ATTRITION_AUDIT_REPORT.md"
    report.write_text("\n".join(lines), encoding="utf-8")
    return report


def build_attrition_audit(repo_root: Path, output_dir: Path | None = None, batches: Iterable[int] = range(1, 41)) -> AuditResult:
    repo_root = repo_root.resolve()
    output_dir = (output_dir or repo_root / AUDIT_OUTPUT_ROOT).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    target_universe = load_target_universe(repo_root)
    artifacts = discover_batch_artifacts(repo_root, batches)
    batch_frames = load_batch_frames(artifacts, repo_root)
    historical = load_historical_frames(discover_historical_inventory_dir(repo_root), repo_root)
    try:
        raw = load_raw_legacy_url_rows(repo_root)
    except Exception:
        raw = pd.DataFrame()
    raw_year = expand_raw_legacy_by_year(raw)

    year_ledger = build_institution_year_ledger(
        batch_frames["target"],
        batch_frames["candidate"],
        batch_frames["benchmark"],
        batch_frames["review"],
        batch_frames["ledger"],
        historical,
        raw_year,
        target_universe.year_rows,
    )
    institution_ledger = build_institution_ledger(year_ledger, historical["priority"], target_universe.memberships)
    target_counts = target_universe_count_summary(institution_ledger, year_ledger, target_universe.old_public_411)

    institution_path = output_dir / "institution_attrition_ledger.csv"
    year_path = output_dir / "institution_year_attrition_ledger.csv"
    summary_path = output_dir / "attrition_summary.json"
    institution_ledger.to_csv(institution_path, index=False)
    year_ledger.to_csv(year_path, index=False)
    report_path = write_report(output_dir, institution_ledger, year_ledger, artifacts, historical, target_universe, target_counts)
    observed_class_counts = {key: int(value) for key, value in year_ledger["attrition_class"].value_counts().to_dict().items()}
    class_counts = {label: int(observed_class_counts.get(label, 0)) for label in ATTRITION_CLASSES}
    secondary_counts = {
        key: int(value)
        for key, value in year_ledger["secondary_attrition_class"].replace("", pd.NA).dropna().value_counts().to_dict().items()
    }
    columbus = year_ledger.loc[year_ledger["unitid"].astype(str).eq("139366")]
    columbus_class = clean_text(columbus["attrition_class"].mode().iloc[0]) if not columbus.empty else ""
    columbus_secondary = clean_text(columbus["secondary_attrition_class"].replace("", pd.NA).dropna().mode().iloc[0]) if not columbus.empty and not columbus["secondary_attrition_class"].replace("", pd.NA).dropna().empty else ""
    summary = {
        "institution_rows": int(len(institution_ledger)),
        "institution_year_rows": int(len(year_ledger)),
        "target_universe_counts": target_counts,
        "target_universe_expected_count_match": target_universe_expected_match(target_counts),
        "attrition_class_counts": class_counts,
        "secondary_attrition_class_counts": secondary_counts,
        "columbus_state_unitid": 139366,
        "columbus_state_attrition_class": columbus_class,
        "columbus_state_secondary_attrition_class": columbus_secondary,
        "output_dir": repo_relative(output_dir, repo_root),
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return AuditResult(
        output_dir=output_dir,
        institution_ledger=institution_path,
        institution_year_ledger=year_path,
        report=report_path,
        summary_json=summary_path,
        institution_rows=len(institution_ledger),
        institution_year_rows=len(year_ledger),
        class_counts=class_counts,
        target_universe_counts=target_counts,
        columbus_class=columbus_class,
        columbus_secondary_class=columbus_secondary,
    )


def parse_batch_range(value: str) -> list[int]:
    if "-" in value:
        start, end = value.split("-", 1)
        return list(range(int(start), int(end) + 1))
    return [int(piece) for piece in value.split(",") if piece.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--batches", default="1-40")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = build_attrition_audit(args.root, args.output_dir, parse_batch_range(args.batches))
    print(f"institution_rows={result.institution_rows}")
    print(f"institution_year_rows={result.institution_year_rows}")
    print(f"target_universe_expected_count_match={target_universe_expected_match(result.target_universe_counts)}")
    print(f"columbus_state_attrition_class={result.columbus_class}")
    print(f"columbus_state_secondary_attrition_class={result.columbus_secondary_class}")
    print(f"output_dir={result.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
