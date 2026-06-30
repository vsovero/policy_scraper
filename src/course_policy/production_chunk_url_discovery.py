"""Build Step 1 production URL chunks from reviewed URL evidence.

This module does not claim clean no-legacy discovery. Prior-programmatic
evidence is treated as a benchmark/diagnostic obligation, not as a source of
automatic promotion into the production source ledger.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from pandas.errors import EmptyDataError

from .ai_config import repo_root_from_cwd


PIPELINE_ROOT = Path("artifacts/PIPELINE_OUTPUTS")
URL_DISCOVERY_ROOT = PIPELINE_ROOT / "01_url_discovery"
PRODUCTION_CHUNKS_ROOT = URL_DISCOVERY_ROOT / "production_chunks"
AUDIT_ROOT = Path("artifacts/AUDIT_TRAILS")

DEFAULT_CHUNK_ID = "production_chunk_001"
DEFAULT_PRIOR_BATCH_SLUG = "pilot_batch_014_dev_009"
DEFAULT_PRIOR_AUDIT_SLUG = "url_discovery_pilot_batch_014_dev_009"
LEGACY_URL_DISCOVERY_AUDIT = AUDIT_ROOT / "url_discovery_step1_full_audit/outputs/reviewed_url_panel.csv"

BENCHMARK_GROUP_LABELS = {
    "valid_human_legacy": "valid human legacy benchmark URL",
    "prior_programmatic_audit": "prior reviewed programmatic URL",
}

INVALIDATED_BENCHMARK_TYPES = {
    "not_currently_retrievable",
    "old_audit_wrong_year",
    "old_audit_wrong_institution",
    "old_audit_graduate_or_wrong_year_source",
    "invalidated_dead_url",
    "invalidated_not_catalog_or_policy_source",
}

REQUIRED_REVIEW_FIELDS = (
    "source_opened",
    "institution_match_confirmed",
    "source_scope_confirmed",
    "source_type_confirmed",
    "year_coverage_confirmed",
    "panel_consistency_confirmed",
    "review_decision",
    "review_reason",
    "reviewed_by",
    "reviewed_at",
    "source_review_file",
)


@dataclass(frozen=True)
class ProductionChunkResult:
    output_dir: Path
    audit_dir: Path
    target_rows: int
    ready_rows: int
    unresolved_rows: int
    requirements_pass: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def clean_text(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except TypeError:
        pass
    return str(value).strip()


def truthy(value: object) -> bool:
    return clean_text(value).lower() in {"1", "1.0", "true", "yes", "y"}


def read_csv_or_empty(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path, low_memory=False)
    except EmptyDataError:
        return pd.DataFrame()


def boolish_series(series: pd.Series) -> pd.Series:
    return series.fillna(False).astype(str).str.strip().str.lower().isin({"true", "1", "1.0", "yes", "y"})


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_record(path: Path, *, repo_root: Path, role: str) -> dict[str, object]:
    resolved = path if path.is_absolute() else repo_root / path
    record: dict[str, object] = {
        "role": role,
        "path": str(resolved),
        "exists": resolved.exists(),
    }
    if not resolved.exists():
        record.update({"size_bytes": "", "sha256": "", "rows": "", "columns": ""})
        return record
    record["size_bytes"] = resolved.stat().st_size
    record["sha256"] = sha256_file(resolved)
    if resolved.suffix.lower() == ".csv":
        frame = read_csv_or_empty(resolved)
        record["rows"] = len(frame)
        record["columns"] = len(frame.columns)
    else:
        record["rows"] = ""
        record["columns"] = ""
    return record


def ready_mask(frame: pd.DataFrame) -> pd.Series:
    if "ready_for_text_extraction" not in frame.columns:
        return pd.Series(False, index=frame.index)
    return frame["ready_for_text_extraction"].map(truthy)


def nonempty_series(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(False, index=frame.index)
    return frame[column].map(clean_text).ne("")


def derive_unresolved_reason(row: pd.Series) -> str:
    for column in [
        "stop_reason",
        "url_status_reason",
        "attrition_reason",
        "review_reason",
        "next_required_action",
        "missing_year_reason",
    ]:
        value = clean_text(row.get(column))
        if value:
            return value
    return "Not ready for text extraction; no explicit prior reason was available."


def source_year_coverage(row: pd.Series) -> str:
    start = clean_text(row.get("source_year_start"))
    end = clean_text(row.get("source_year_end"))
    note = clean_text(row.get("source_year_coverage_note"))
    if start and end:
        span = f"{start}-{end}"
        return f"{span}: {note}" if note else span
    return note


def provenance_type(row: pd.Series) -> str:
    if truthy(row.get("human_legacy_url_used")) or clean_text(row.get("production_url_source")) == "human_legacy_url":
        return "prior_human"
    if clean_text(row.get("url_discovery_ai_call_id")):
        return "api_assisted"
    return "prior_programmatic"


def benchmark_url_from_old_row(row: pd.Series, benchmark_group: str) -> str:
    if benchmark_group == "valid_human_legacy":
        fields = ["human_legacy_final_url", "human_legacy_url", "production_best_url", "programmatic_url"]
    else:
        fields = ["production_best_url", "programmatic_url", "human_legacy_final_url", "human_legacy_url"]
    for field in fields:
        value = clean_text(row.get(field))
        if value:
            return value
    return ""


def benchmark_source_type(url: str) -> str:
    lower = url.lower()
    if lower.endswith(".pdf") or ".pdf" in lower:
        return "catalog_pdf"
    if "catalog" in lower or "bulletin" in lower:
        return "catalog_url"
    return "prior_valid_source"


def evidence_hash_or_cache_path(row: pd.Series) -> str:
    for column in ["external_evidence_cache_file", "cache_replay_file", "source_review_file", "candidate_source_file"]:
        value = clean_text(row.get(column))
        if value:
            path = Path(value)
            if path.exists():
                return f"{sha256_file(path)} {value}"
            return value
    return ""


def ensure_required_input_columns(frame: pd.DataFrame) -> None:
    required = {
        "unitid",
        "institution_name",
        "academic_year",
        "url_status",
        "ready_for_text_extraction",
        "url_for_text_extraction",
        "review_decision",
        "review_reason",
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"Prior batch output is missing required columns: {', '.join(missing)}")


def build_handoff(
    prior: pd.DataFrame,
    *,
    chunk_id: str,
    prior_batch_slug: str,
    prior_output_csv: Path,
    prior_audit_dir: Path,
) -> pd.DataFrame:
    handoff = prior.copy()
    handoff.insert(0, "run_type", "production_chunk")
    handoff.insert(0, "run_id", chunk_id)
    handoff["prior_batch_id"] = prior_batch_slug
    handoff["prior_batch_output_file"] = str(prior_output_csv)
    handoff["prior_audit_dir"] = str(prior_audit_dir)
    handoff["unresolved_reason"] = [
        "" if truthy(row.get("ready_for_text_extraction")) else derive_unresolved_reason(row)
        for _, row in handoff.iterrows()
    ]
    handoff["source_ledger_provenance_type"] = [
        provenance_type(row) if truthy(row.get("ready_for_text_extraction")) else ""
        for _, row in handoff.iterrows()
    ]
    handoff["production_chunk_created_at"] = utc_now()
    return handoff


def legacy_benchmark_rows(repo_root: Path, handoff: pd.DataFrame) -> pd.DataFrame:
    audit_path = repo_root / LEGACY_URL_DISCOVERY_AUDIT
    old = read_csv_or_empty(audit_path)
    columns = [
        "benchmark_group",
        "unitid",
        "institution_name",
        "academic_year",
        "benchmark_url",
        "benchmark_source_file",
        "benchmark_provenance_type",
        "old_ready_for_text_extraction",
        "old_has_valid_human_legacy_url",
    ]
    if old.empty:
        return pd.DataFrame(columns=columns)

    current = handoff.copy()
    current["unitid"] = pd.to_numeric(current["unitid"], errors="coerce").astype("Int64")
    current["academic_year"] = pd.to_numeric(current["academic_year"], errors="coerce").astype("Int64")
    target_keys = set(
        zip(
            current["unitid"].dropna().astype(int),
            current["academic_year"].dropna().astype(int),
        )
    )

    old = old.copy()
    old["unitid"] = pd.to_numeric(old["unitid"], errors="coerce").astype("Int64")
    old["academic_year"] = pd.to_numeric(old["target_year"], errors="coerce").astype("Int64")
    old = old.loc[
        [
            not pd.isna(unitid) and not pd.isna(year) and (int(unitid), int(year)) in target_keys
            for unitid, year in zip(old["unitid"], old["academic_year"])
        ]
    ].copy()
    if old.empty:
        return pd.DataFrame(columns=columns)

    old_ready = boolish_series(old.get("ready_for_text_extraction_step2", pd.Series(False, index=old.index)))
    valid_human = boolish_series(old.get("has_valid_human_legacy_url", pd.Series(False, index=old.index)))

    rows: list[dict[str, object]] = []
    for idx, old_row in old.iterrows():
        for benchmark_group, include in [
            ("valid_human_legacy", bool(valid_human.loc[idx])),
            ("prior_programmatic_audit", bool(old_ready.loc[idx])),
        ]:
            if not include:
                continue
            benchmark_url = benchmark_url_from_old_row(old_row, benchmark_group)
            rows.append(
                {
                    "benchmark_group": benchmark_group,
                    "unitid": int(old_row["unitid"]),
                    "institution_name": clean_text(old_row.get("institution_name")),
                    "academic_year": int(old_row["academic_year"]),
                    "benchmark_url": benchmark_url,
                    "benchmark_source_file": str(audit_path),
                    "benchmark_provenance_type": "prior_human"
                    if benchmark_group == "valid_human_legacy"
                    else "prior_programmatic",
                    "old_ready_for_text_extraction": bool(old_ready.loc[idx]),
                    "old_has_valid_human_legacy_url": bool(valid_human.loc[idx]),
                }
            )
    return pd.DataFrame(rows, columns=columns)


def apply_prior_benchmark_recovery(
    handoff: pd.DataFrame,
    benchmark_targets: pd.DataFrame,
    *,
    recovery_file: Path,
) -> tuple[pd.DataFrame, set[tuple[int, int, str]]]:
    """Promote only valid human legacy benchmark URLs.

    Prior-programmatic benchmark rows must be recovered by the current run or
    remain misses. Promoting them from old programmatic evidence would make the
    benchmark circular.
    """
    if benchmark_targets.empty:
        return handoff, set()

    updated = handoff.copy()
    updated["unitid"] = pd.to_numeric(updated["unitid"], errors="coerce").astype("Int64")
    updated["academic_year"] = pd.to_numeric(updated["academic_year"], errors="coerce").astype("Int64")
    currently_ready = set(
        zip(
            updated.loc[ready_mask(updated), "unitid"].astype(int),
            updated.loc[ready_mask(updated), "academic_year"].astype(int),
        )
    )

    promoted_keys: set[tuple[int, int, str]] = set()
    missing_current_ready = pd.Series(
        [
            (int(unitid), int(year)) not in currently_ready
            for unitid, year in zip(benchmark_targets["unitid"], benchmark_targets["academic_year"])
        ],
        index=benchmark_targets.index,
    )
    needed = benchmark_targets.loc[
        benchmark_targets["benchmark_url"].map(clean_text).ne("")
        & missing_current_ready
        & benchmark_targets["benchmark_group"].map(clean_text).eq("valid_human_legacy")
    ].copy()
    if needed.empty:
        return updated, promoted_keys

    needed["group_rank"] = needed["benchmark_group"].map({"valid_human_legacy": 0, "prior_programmatic_audit": 1})
    needed = needed.sort_values(["unitid", "academic_year", "group_rank"]).drop_duplicates(
        ["unitid", "academic_year"],
        keep="first",
    )
    promotion_columns = [
        "url_status",
        "url_status_reason",
        "ready_for_text_extraction",
        "stop_before_text_extraction",
        "stop_reason",
        "attrition_stage",
        "attrition_reason",
        "stage_specific_pass",
        "rolling_pass",
        "url_for_text_extraction",
        "url_source_bucket",
        "production_url_source",
        "source_type",
        "source_year_start",
        "source_year_end",
        "source_year_coverage_note",
        "human_legacy_url_available",
        "human_legacy_url_used",
        "human_legacy_url",
        "programmatic_candidate_available",
        "candidate_url",
        "candidate_generation_method",
        "candidate_source_type",
        "candidate_source_file",
        "source_review_file",
        "source_opened",
        "retrieval_status",
        "http_status",
        "final_url_after_redirect",
        "institution_match_confirmed",
        "campus_or_unitid_match_confirmed",
        "source_scope_confirmed",
        "source_type_confirmed",
        "year_coverage_confirmed",
        "archive_child_links_checked",
        "gap_fill_search_completed",
        "panel_consistency_confirmed",
        "review_decision",
        "review_reason",
        "reviewed_by",
        "reviewed_at",
        "source_evidence_note",
        "missing_year_reason",
        "next_required_action",
        "unresolved_reason",
        "source_ledger_provenance_type",
        "benchmark_recovery_action",
    ]
    for column in promotion_columns:
        if column not in updated.columns:
            updated[column] = ""
        updated[column] = updated[column].astype(object)
    reviewed_at = utc_now()
    for _, target in needed.iterrows():
        unitid = int(target["unitid"])
        year = int(target["academic_year"])
        mask = updated["unitid"].eq(unitid) & updated["academic_year"].eq(year)
        if not mask.any():
            continue
        benchmark_url = clean_text(target.get("benchmark_url"))
        benchmark_group = clean_text(target.get("benchmark_group"))
        provenance = clean_text(target.get("benchmark_provenance_type")) or "prior_programmatic"
        label = BENCHMARK_GROUP_LABELS.get(benchmark_group, benchmark_group)
        reason = (
            f"Recovered from {label} in the prior reviewed URL panel. "
            "The current batch did not rediscover this source, so production promotes "
            "the prior validated source instead of dropping the row."
        )
        source_type = benchmark_source_type(benchmark_url)
        updated.loc[mask, "url_status"] = "prior_benchmark_recovered"
        updated.loc[mask, "url_status_reason"] = reason
        updated.loc[mask, "ready_for_text_extraction"] = True
        updated.loc[mask, "stop_before_text_extraction"] = False
        updated.loc[mask, "stop_reason"] = ""
        updated.loc[mask, "attrition_stage"] = "ready_for_text_extraction"
        updated.loc[mask, "attrition_reason"] = ""
        updated.loc[mask, "stage_specific_pass"] = True
        updated.loc[mask, "rolling_pass"] = True
        updated.loc[mask, "url_for_text_extraction"] = benchmark_url
        updated.loc[mask, "url_source_bucket"] = "prior_valid_benchmark_recovery"
        updated.loc[mask, "production_url_source"] = benchmark_group
        updated.loc[mask, "source_type"] = source_type
        updated.loc[mask, "source_year_start"] = year
        updated.loc[mask, "source_year_end"] = year
        updated.loc[mask, "source_year_coverage_note"] = "Prior reviewed URL panel marked this source ready for the target year."
        updated.loc[mask, "human_legacy_url_available"] = benchmark_group == "valid_human_legacy"
        updated.loc[mask, "human_legacy_url_used"] = benchmark_group == "valid_human_legacy"
        if benchmark_group == "valid_human_legacy":
            updated.loc[mask, "human_legacy_url"] = benchmark_url
        updated.loc[mask, "programmatic_candidate_available"] = True
        updated.loc[mask, "candidate_url"] = benchmark_url
        updated.loc[mask, "candidate_generation_method"] = "prior_valid_benchmark_recovery"
        updated.loc[mask, "candidate_source_type"] = benchmark_group
        updated.loc[mask, "candidate_source_file"] = clean_text(target.get("benchmark_source_file"))
        updated.loc[mask, "source_review_file"] = str(recovery_file)
        updated.loc[mask, "source_opened"] = "prior_reviewed_ready"
        updated.loc[mask, "retrieval_status"] = "prior_reviewed_ready"
        updated.loc[mask, "http_status"] = ""
        updated.loc[mask, "final_url_after_redirect"] = benchmark_url
        updated.loc[mask, "institution_match_confirmed"] = "prior_reviewed_ready"
        updated.loc[mask, "campus_or_unitid_match_confirmed"] = "prior_reviewed_ready"
        updated.loc[mask, "source_scope_confirmed"] = "prior_reviewed_ready"
        updated.loc[mask, "source_type_confirmed"] = "prior_reviewed_ready"
        updated.loc[mask, "year_coverage_confirmed"] = "prior_reviewed_ready"
        updated.loc[mask, "archive_child_links_checked"] = "prior_reviewed_ready"
        updated.loc[mask, "gap_fill_search_completed"] = "prior_reviewed_ready"
        updated.loc[mask, "panel_consistency_confirmed"] = "prior_reviewed_ready"
        updated.loc[mask, "review_decision"] = "accept_prior_valid_benchmark_source_recovery"
        updated.loc[mask, "review_reason"] = reason
        updated.loc[mask, "reviewed_by"] = "codex_prior_valid_benchmark_recovery"
        updated.loc[mask, "reviewed_at"] = reviewed_at
        updated.loc[mask, "source_evidence_note"] = reason
        updated.loc[mask, "missing_year_reason"] = ""
        updated.loc[mask, "next_required_action"] = ""
        updated.loc[mask, "unresolved_reason"] = ""
        updated.loc[mask, "source_ledger_provenance_type"] = provenance
        updated.loc[mask, "benchmark_recovery_action"] = "promoted_from_prior_valid_benchmark_evidence"
        promoted_keys.add((unitid, year, benchmark_group))
    return updated, promoted_keys


def build_benchmark_recovery(
    handoff: pd.DataFrame,
    benchmark_targets: pd.DataFrame,
    promoted_keys: set[tuple[int, int, str]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    columns = [
        "benchmark_group",
        "unitid",
        "institution_name",
        "academic_year",
        "benchmark_url",
        "current_ready",
        "current_run_recovered",
        "source_ledger_resolved",
        "source_ledger_resolution_type",
        "valid_human_legacy_overlap",
        "accepted_source_url",
        "benchmark_recovery_status",
        "benchmark_miss_type",
        "benchmark_miss_requires_current_run_fix",
        "unresolved_for_production",
        "exception_type",
        "current_url_status",
        "current_review_decision",
        "source_ledger_provenance_type",
        "benchmark_source_file",
    ]
    if benchmark_targets.empty:
        empty = pd.DataFrame(columns=columns)
        return empty, empty.copy()

    current = handoff.copy()
    current["unitid"] = pd.to_numeric(current["unitid"], errors="coerce").astype("Int64")
    current["academic_year"] = pd.to_numeric(current["academic_year"], errors="coerce").astype("Int64")
    valid_human_keys = set(
        zip(
            benchmark_targets.loc[
                benchmark_targets["benchmark_group"].map(clean_text).eq("valid_human_legacy"), "unitid"
            ].astype(int),
            benchmark_targets.loc[
                benchmark_targets["benchmark_group"].map(clean_text).eq("valid_human_legacy"), "academic_year"
            ].astype(int),
        )
    )
    rows: list[dict[str, object]] = []
    for _, target in benchmark_targets.iterrows():
        unitid = int(target["unitid"])
        year = int(target["academic_year"])
        benchmark_group = clean_text(target.get("benchmark_group"))
        valid_human_overlap = (unitid, year) in valid_human_keys
        current_row = current.loc[current["unitid"].eq(unitid) & current["academic_year"].eq(year)]
        if current_row.empty:
            accepted_source_url = ""
            current_ready = False
            current_status = "not_in_current_target_panel"
            current_decision = ""
            provenance = ""
            prior_promotion_action = False
            source_ledger_resolution_type = ""
        else:
            row = current_row.iloc[0]
            current_ready = bool(truthy(row.get("ready_for_text_extraction")))
            accepted_source_url = clean_text(row.get("url_for_text_extraction")) if current_ready else ""
            current_status = clean_text(row.get("url_status"))
            current_decision = clean_text(row.get("review_decision"))
            provenance = clean_text(row.get("source_ledger_provenance_type"))
            prior_promotion_action = (
                clean_text(row.get("benchmark_recovery_action"))
                == "promoted_from_prior_valid_benchmark_evidence"
            )
            source_ledger_resolution_type = provenance if current_ready else ""

        promoted_for_this_benchmark = (unitid, year, benchmark_group) in promoted_keys
        current_run_ready = current_ready and not prior_promotion_action
        if current_ready and promoted_for_this_benchmark:
            status = "promoted_from_prior_valid_benchmark_evidence"
            exception_type = ""
            benchmark_miss_type = ""
        elif current_run_ready:
            status = "recovered_by_current_chunk"
            exception_type = ""
            benchmark_miss_type = ""
        else:
            status = "miss"
            exception_type = "needs_investigation_true_discovery_miss"
            if current_ready and valid_human_overlap and benchmark_group == "prior_programmatic_audit":
                benchmark_miss_type = "prior_programmatic_current_run_miss_source_resolved_by_valid_human"
            elif current_ready:
                benchmark_miss_type = "benchmark_miss_source_ledger_resolved_by_other_evidence"
            else:
                benchmark_miss_type = "benchmark_miss_source_ledger_unresolved"

        rows.append(
            {
                "benchmark_group": benchmark_group,
                "unitid": unitid,
                "institution_name": clean_text(target.get("institution_name")),
                "academic_year": year,
                "benchmark_url": clean_text(target.get("benchmark_url")),
                "current_ready": current_ready,
                "current_run_recovered": current_run_ready,
                "source_ledger_resolved": current_ready,
                "source_ledger_resolution_type": source_ledger_resolution_type,
                "valid_human_legacy_overlap": valid_human_overlap,
                "accepted_source_url": accepted_source_url,
                "benchmark_recovery_status": status,
                "benchmark_miss_type": benchmark_miss_type,
                "benchmark_miss_requires_current_run_fix": status == "miss",
                "unresolved_for_production": not current_ready,
                "exception_type": exception_type,
                "current_url_status": current_status,
                "current_review_decision": current_decision,
                "source_ledger_provenance_type": provenance,
                "benchmark_source_file": clean_text(target.get("benchmark_source_file")),
            }
        )

    recovery = pd.DataFrame(rows, columns=columns)
    misses = recovery.loc[
        recovery["benchmark_recovery_status"].eq("miss")
        & ~recovery["exception_type"].isin(INVALIDATED_BENCHMARK_TYPES)
    ].copy()
    return recovery, misses


def build_source_ledger_delta(handoff: pd.DataFrame) -> pd.DataFrame:
    ready = handoff.loc[ready_mask(handoff)].copy()
    rows: list[dict[str, object]] = []
    for _, row in ready.iterrows():
        rows.append(
            {
                "run_id": clean_text(row.get("run_id")),
                "run_type": "production_chunk",
                "unitid": row.get("unitid"),
                "institution_name": row.get("institution_name"),
                "sector": row.get("sector"),
                "state": row.get("state"),
                "academic_year": row.get("academic_year"),
                "accepted_source_url": clean_text(row.get("url_for_text_extraction")),
                "source_type": clean_text(row.get("source_type")),
                "source_year_coverage": source_year_coverage(row),
                "provenance_type": provenance_type(row),
                "prior_batch_id": clean_text(row.get("prior_batch_id")),
                "review_file": clean_text(row.get("source_review_file")),
                "review_decision": clean_text(row.get("review_decision")),
                "review_reason": clean_text(row.get("review_reason")),
                "reviewed_by": clean_text(row.get("reviewed_by")),
                "reviewed_at": clean_text(row.get("reviewed_at")),
                "evidence_hash_or_cache_path": evidence_hash_or_cache_path(row),
                "candidate_url": clean_text(row.get("candidate_url")),
                "retrieval_status": clean_text(row.get("retrieval_status")),
                "http_status": clean_text(row.get("http_status")),
                "final_url_after_redirect": clean_text(row.get("final_url_after_redirect")),
                "source_page_title": clean_text(row.get("source_page_title")),
                "source_opened": clean_text(row.get("source_opened")),
                "institution_match_confirmed": clean_text(row.get("institution_match_confirmed")),
                "source_scope_confirmed": clean_text(row.get("source_scope_confirmed")),
                "source_type_confirmed": clean_text(row.get("source_type_confirmed")),
                "year_coverage_confirmed": clean_text(row.get("year_coverage_confirmed")),
                "panel_consistency_confirmed": clean_text(row.get("panel_consistency_confirmed")),
            }
        )
    return pd.DataFrame(rows)


def build_unresolved_rows(handoff: pd.DataFrame) -> pd.DataFrame:
    unresolved = handoff.loc[~ready_mask(handoff)].copy()
    columns = [
        "run_id",
        "run_type",
        "unitid",
        "institution_name",
        "sector",
        "state",
        "academic_year",
        "url_status",
        "unresolved_reason",
        "stop_reason",
        "next_required_action",
        "candidate_url",
        "review_decision",
        "review_reason",
        "source_review_file",
        "prior_batch_id",
        "prior_batch_output_file",
    ]
    for column in columns:
        if column not in unresolved.columns:
            unresolved[column] = ""
    return unresolved[columns].copy()


def source_review_paths_exist(ledger: pd.DataFrame) -> bool:
    if ledger.empty:
        return True
    paths = ledger["review_file"].map(clean_text)
    if paths.eq("").any():
        return False
    return paths.map(lambda value: Path(value).exists()).all()


def build_requirements(
    *,
    handoff: pd.DataFrame,
    ledger: pd.DataFrame,
    unresolved: pd.DataFrame,
    benchmark_recovery: pd.DataFrame,
    benchmark_misses: pd.DataFrame,
    api_summary: pd.DataFrame,
    manifest_exists: bool = True,
) -> pd.DataFrame:
    now = utc_now()
    target_rows = len(handoff)
    ready_rows = int(ready_mask(handoff).sum())
    unresolved_rows = len(unresolved)
    duplicate_rows = int(handoff.duplicated(["unitid", "academic_year"]).sum())
    no_unreviewed = int(handoff["url_status"].fillna("").astype(str).eq("candidate_needs_source_review").sum()) == 0
    accepted_evidence_complete = True
    ready = handoff.loc[ready_mask(handoff)]
    for column in REQUIRED_REVIEW_FIELDS:
        if column not in ready.columns or ready[column].map(clean_text).eq("").any():
            accepted_evidence_complete = False
            break
    valid_human_denominator = int(benchmark_recovery["benchmark_group"].eq("valid_human_legacy").sum()) if not benchmark_recovery.empty else 0
    valid_human_misses = int(benchmark_misses["benchmark_group"].eq("valid_human_legacy").sum()) if not benchmark_misses.empty else 0
    prior_programmatic_denominator = (
        int(benchmark_recovery["benchmark_group"].eq("prior_programmatic_audit").sum())
        if not benchmark_recovery.empty
        else 0
    )
    prior_programmatic_misses = (
        int(benchmark_misses["benchmark_group"].eq("prior_programmatic_audit").sum())
        if not benchmark_misses.empty
        else 0
    )
    if benchmark_misses.empty or "source_ledger_resolved" not in benchmark_misses.columns:
        prior_programmatic_source_resolved_misses = 0
        prior_programmatic_source_unresolved_misses = prior_programmatic_misses
    else:
        prior_miss_mask = benchmark_misses["benchmark_group"].eq("prior_programmatic_audit")
        source_resolved_mask = boolish_series(benchmark_misses["source_ledger_resolved"])
        prior_programmatic_source_resolved_misses = int((prior_miss_mask & source_resolved_mask).sum())
        prior_programmatic_source_unresolved_misses = int((prior_miss_mask & ~source_resolved_mask).sum())
    requirements = [
        {
            "requirement_id": "chunk_target_panel_frozen",
            "pipeline_stage": "01_url_discovery_production_chunk",
            "requirement": "Target panel exists with one row per institution-year.",
            "acceptance_criterion": "Target rows > 0 and unitid+academic_year is unique.",
            "status": "pass" if target_rows > 0 and duplicate_rows == 0 else "fail",
            "evidence_file": "OUTPUT_urls_for_text_extraction.csv",
            "evidence_column_or_check": f"target_rows={target_rows}; duplicate_unitid_year_rows={duplicate_rows}",
            "gap_if_incomplete": "" if target_rows > 0 and duplicate_rows == 0 else "Fix target panel duplicates or empty input.",
            "last_checked_at": now,
        },
        {
            "requirement_id": "chunk_ledger_closure",
            "pipeline_stage": "01_url_discovery_production_chunk",
            "requirement": "Every row is represented in the source ledger or unresolved table.",
            "acceptance_criterion": "ledger rows + unresolved rows equals target rows.",
            "status": "pass" if len(ledger) + len(unresolved) == target_rows else "fail",
            "evidence_file": "OUTPUT_source_ledger_delta.csv; UNRESOLVED_ROWS.csv",
            "evidence_column_or_check": f"ledger_rows={len(ledger)}; unresolved_rows={len(unresolved)}; target_rows={target_rows}",
            "gap_if_incomplete": "" if len(ledger) + len(unresolved) == target_rows else "Reconcile ready and unresolved rows.",
            "last_checked_at": now,
        },
        {
            "requirement_id": "chunk_ready_rows_in_ledger",
            "pipeline_stage": "01_url_discovery_production_chunk",
            "requirement": "All ready rows appear in the source-ledger delta.",
            "acceptance_criterion": "Ready row count equals source-ledger row count and accepted URLs are nonblank.",
            "status": "pass"
            if ready_rows == len(ledger) and (ledger.empty or ledger["accepted_source_url"].map(clean_text).ne("").all())
            else "fail",
            "evidence_file": "OUTPUT_source_ledger_delta.csv",
            "evidence_column_or_check": f"ready_rows={ready_rows}; ledger_rows={len(ledger)}",
            "gap_if_incomplete": "" if ready_rows == len(ledger) else "Ready rows do not reconcile to ledger rows.",
            "last_checked_at": now,
        },
        {
            "requirement_id": "chunk_unresolved_rows_visible",
            "pipeline_stage": "01_url_discovery_production_chunk",
            "requirement": "Not-ready rows remain visible with explicit reasons.",
            "acceptance_criterion": "Unresolved rows equal not-ready rows and unresolved_reason is nonblank.",
            "status": "pass"
            if unresolved_rows == target_rows - ready_rows and unresolved["unresolved_reason"].map(clean_text).ne("").all()
            else "fail",
            "evidence_file": "UNRESOLVED_ROWS.csv",
            "evidence_column_or_check": f"not_ready_rows={target_rows - ready_rows}; unresolved_rows={unresolved_rows}",
            "gap_if_incomplete": "" if unresolved_rows == target_rows - ready_rows else "Not-ready rows are missing from unresolved table.",
            "last_checked_at": now,
        },
        {
            "requirement_id": "chunk_source_review_evidence",
            "pipeline_stage": "01_url_discovery_production_chunk",
            "requirement": "Accepted URLs have source-review evidence.",
            "acceptance_criterion": "Required review fields are nonblank and review files exist.",
            "status": "pass" if accepted_evidence_complete and source_review_paths_exist(ledger) else "fail",
            "evidence_file": "OUTPUT_urls_for_text_extraction.csv; OUTPUT_source_ledger_delta.csv",
            "evidence_column_or_check": "required source-review fields; review_file exists",
            "gap_if_incomplete": "" if accepted_evidence_complete else "Accepted source-review evidence is incomplete.",
            "last_checked_at": now,
        },
        {
            "requirement_id": "chunk_no_unreviewed_candidates",
            "pipeline_stage": "01_url_discovery_production_chunk",
            "requirement": "No row is stuck as candidate_needs_source_review.",
            "acceptance_criterion": "candidate_needs_source_review count is zero.",
            "status": "pass" if no_unreviewed else "fail",
            "evidence_file": "OUTPUT_urls_for_text_extraction.csv",
            "evidence_column_or_check": "candidate_needs_source_review rows=0",
            "gap_if_incomplete": "" if no_unreviewed else "Review or reject candidate rows before handoff.",
            "last_checked_at": now,
        },
        {
            "requirement_id": "chunk_provenance_recorded",
            "pipeline_stage": "01_url_discovery_production_chunk",
            "requirement": "Every accepted source has provenance.",
            "acceptance_criterion": "provenance_type is nonblank for source-ledger rows.",
            "status": "pass" if ledger.empty or ledger["provenance_type"].map(clean_text).ne("").all() else "fail",
            "evidence_file": "OUTPUT_source_ledger_delta.csv",
            "evidence_column_or_check": "provenance_type",
            "gap_if_incomplete": "" if ledger.empty or ledger["provenance_type"].map(clean_text).ne("").all() else "Fill provenance_type.",
            "last_checked_at": now,
        },
        {
            "requirement_id": "chunk_valid_human_benchmark_resolved",
            "pipeline_stage": "01_url_discovery_production_chunk",
            "requirement": "Every valid human legacy benchmark row is recovered, promoted, or row-invalidated.",
            "acceptance_criterion": "Valid human benchmark misses equal zero.",
            "status": "pass" if valid_human_misses == 0 else "fail",
            "evidence_file": "BENCHMARK_RECOVERY.csv; BENCHMARK_MISSES.csv",
            "evidence_column_or_check": (
                f"valid_human_benchmark_rows={valid_human_denominator}; "
                f"valid_human_unresolved_misses={valid_human_misses}"
            ),
            "gap_if_incomplete": ""
            if valid_human_misses == 0
            else "Recover or row-invalidate valid human benchmark misses before passing the chunk.",
            "last_checked_at": now,
        },
        {
            "requirement_id": "chunk_prior_programmatic_benchmark_resolved",
            "pipeline_stage": "01_url_discovery_production_chunk",
            "requirement": "Every prior valid programmatic discovery row is recovered by the current run or row-invalidated.",
            "acceptance_criterion": "Prior-programmatic current-run benchmark misses equal zero; prior-programmatic promotion is not allowed.",
            "status": "pass" if prior_programmatic_misses == 0 else "fail",
            "evidence_file": "BENCHMARK_RECOVERY.csv; BENCHMARK_MISSES.csv",
            "evidence_column_or_check": (
                f"prior_programmatic_benchmark_rows={prior_programmatic_denominator}; "
                f"prior_programmatic_current_run_misses={prior_programmatic_misses}; "
                f"source_ledger_resolved_by_other_evidence={prior_programmatic_source_resolved_misses}; "
                f"source_ledger_unresolved_programmatic_only_misses={prior_programmatic_source_unresolved_misses}"
            ),
            "gap_if_incomplete": ""
            if prior_programmatic_misses == 0
            else "Recover prior-programmatic benchmark misses in the current run, or row-invalidate them, before passing this benchmark check.",
            "last_checked_at": now,
        },
        {
            "requirement_id": "chunk_api_mode_documented",
            "pipeline_stage": "01_url_discovery_production_chunk",
            "requirement": "API mode or prior API failure is documented.",
            "acceptance_criterion": "API summary exists or report states API not used.",
            "status": "pass",
            "evidence_file": "CHUNK_REPORT.md",
            "evidence_column_or_check": f"api_summary_rows={len(api_summary)}",
            "gap_if_incomplete": "",
            "last_checked_at": now,
        },
        {
            "requirement_id": "chunk_manifest_written",
            "pipeline_stage": "01_url_discovery_production_chunk",
            "requirement": "Chunk output manifest is written.",
            "acceptance_criterion": "MANIFEST.json exists for the production chunk.",
            "status": "pass" if manifest_exists else "fail",
            "evidence_file": "MANIFEST.json",
            "evidence_column_or_check": "manifest file exists",
            "gap_if_incomplete": "" if manifest_exists else "Write MANIFEST.json after output files are complete.",
            "last_checked_at": now,
        },
    ]
    return pd.DataFrame(requirements)


def write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def benchmark_miss_split(benchmark_misses: pd.DataFrame) -> dict[str, int]:
    if benchmark_misses.empty:
        return {
            "prior_programmatic_current_run_misses": 0,
            "prior_programmatic_source_resolved_misses": 0,
            "prior_programmatic_source_unresolved_misses": 0,
        }
    prior_miss_mask = benchmark_misses["benchmark_group"].eq("prior_programmatic_audit")
    source_resolved = (
        boolish_series(benchmark_misses["source_ledger_resolved"])
        if "source_ledger_resolved" in benchmark_misses.columns
        else pd.Series(False, index=benchmark_misses.index)
    )
    return {
        "prior_programmatic_current_run_misses": int(prior_miss_mask.sum()),
        "prior_programmatic_source_resolved_misses": int((prior_miss_mask & source_resolved).sum()),
        "prior_programmatic_source_unresolved_misses": int((prior_miss_mask & ~source_resolved).sum()),
    }


def write_readme(
    path: Path,
    *,
    chunk_id: str,
    prior_batch_slug: str,
    prior_output_csv: Path,
    target_rows: int,
    ready_rows: int,
    unresolved_rows: int,
    benchmark_rows: int,
    benchmark_unique_rows: int,
    benchmark_misses: int,
    prior_programmatic_current_run_misses: int,
    prior_programmatic_source_resolved_misses: int,
    prior_programmatic_source_unresolved_misses: int,
) -> None:
    text = f"""# {chunk_id}

This is a Step 1 URL-discovery production chunk built from a reviewed prior
batch output.

It is not a clean no-legacy benchmark. Current-run accepted rows can enter the
source ledger with provenance. Prior-programmatic evidence is kept visible as
benchmark diagnostics unless the current run recovers and reviews the source.

## Input

```text
prior_batch_slug: {prior_batch_slug}
prior_output_csv: {prior_output_csv}
```

## Outputs

```text
OUTPUT_urls_for_text_extraction.csv
OUTPUT_source_ledger_delta.csv
UNRESOLVED_ROWS.csv
BENCHMARK_RECOVERY.csv
BENCHMARK_MISSES.csv
REQUIREMENTS_STATUS.csv
CHUNK_REPORT.md
MANIFEST.json
```

## Counts

```text
target_rows: {target_rows}
ready_for_text_extraction: {ready_rows}
source_ledger_unresolved_or_unrecoverable: {unresolved_rows}
benchmark_unique_institution_years: {benchmark_unique_rows}
benchmark_group_checks_resolved_under_current_rules: {benchmark_rows - benchmark_misses}
benchmark_current_run_misses: {benchmark_misses}
prior_programmatic_current_run_misses: {prior_programmatic_current_run_misses}
prior_programmatic_misses_source_ledger_resolved_by_valid_human: {prior_programmatic_source_resolved_misses}
programmatic_only_source_ledger_unresolved_misses: {prior_programmatic_source_unresolved_misses}
```

The production pass condition is stricter than ledger closure. Every target row
must appear either in the source-ledger delta or in the unresolved-row table with
a reason. Valid human legacy benchmark rows may be recovered, promoted with
human-legacy provenance, or row-invalidated. Prior-programmatic benchmark rows
must be recovered by the current run or row-invalidated; they cannot be promoted
from old programmatic evidence alone. `BENCHMARK_MISSES.csv` records current-run
benchmark misses; its source-ledger columns distinguish misses that already have
a valid human-legacy source from misses that still lack a production source.
"""
    path.write_text(text, encoding="utf-8")


def write_chunk_report(
    path: Path,
    *,
    chunk_id: str,
    prior_batch_slug: str,
    target_rows: int,
    institutions: int,
    ready_rows: int,
    unresolved_rows: int,
    ledger_rows: int,
    benchmark_recovery: pd.DataFrame,
    benchmark_misses: pd.DataFrame,
    requirements: pd.DataFrame,
    api_summary: pd.DataFrame,
) -> None:
    req_pass = int(requirements["status"].eq("pass").sum()) if not requirements.empty else 0
    req_total = len(requirements)
    api_note = "No API summary was present for the prior batch."
    if not api_summary.empty:
        parsed = int(pd.to_numeric(api_summary.get("parsed_rows", pd.Series(dtype="float64")), errors="coerce").fillna(0).sum())
        errors = int(pd.to_numeric(api_summary.get("api_error_rows", pd.Series(dtype="float64")), errors="coerce").fillna(0).sum())
        api_note = (
            f"Prior batch API rescue summary rows: {len(api_summary)}; "
            f"parsed rows: {parsed}; API error rows: {errors}. "
            "These prior API attempts are documented as evidence, not rerun for this chunk."
        )
    benchmark_rows = len(benchmark_recovery)
    benchmark_unique_rows = (
        len(benchmark_recovery.drop_duplicates(["unitid", "academic_year"])) if not benchmark_recovery.empty else 0
    )
    benchmark_miss_rows = len(benchmark_misses)
    promoted_rows = (
        int(benchmark_recovery["benchmark_recovery_status"].eq("promoted_from_prior_valid_benchmark_evidence").sum())
        if not benchmark_recovery.empty
        else 0
    )
    promoted_unique_rows = (
        len(
            benchmark_recovery.loc[
                benchmark_recovery["benchmark_recovery_status"].eq("promoted_from_prior_valid_benchmark_evidence")
            ].drop_duplicates(["unitid", "academic_year"])
        )
        if not benchmark_recovery.empty
        else 0
    )
    current_recovered_rows = (
        int(benchmark_recovery["benchmark_recovery_status"].eq("recovered_by_current_chunk").sum())
        if not benchmark_recovery.empty
        else 0
    )
    current_recovered_unique_rows = (
        len(
            benchmark_recovery.loc[
                benchmark_recovery["benchmark_recovery_status"].eq("recovered_by_current_chunk")
            ].drop_duplicates(["unitid", "academic_year"])
        )
        if not benchmark_recovery.empty
        else 0
    )
    valid_human_rows = (
        int(benchmark_recovery["benchmark_group"].eq("valid_human_legacy").sum()) if not benchmark_recovery.empty else 0
    )
    valid_human_misses = (
        int(benchmark_misses["benchmark_group"].eq("valid_human_legacy").sum()) if not benchmark_misses.empty else 0
    )
    prior_programmatic_rows = (
        int(benchmark_recovery["benchmark_group"].eq("prior_programmatic_audit").sum())
        if not benchmark_recovery.empty
        else 0
    )
    prior_programmatic_misses = (
        int(benchmark_misses["benchmark_group"].eq("prior_programmatic_audit").sum())
        if not benchmark_misses.empty
        else 0
    )
    miss_split = benchmark_miss_split(benchmark_misses)
    prior_programmatic_source_resolved_misses = miss_split["prior_programmatic_source_resolved_misses"]
    prior_programmatic_source_unresolved_misses = miss_split["prior_programmatic_source_unresolved_misses"]
    prior_programmatic_only = pd.DataFrame()
    if not benchmark_recovery.empty and "valid_human_legacy_overlap" in benchmark_recovery.columns:
        prior_programmatic_only = benchmark_recovery.loc[
            benchmark_recovery["benchmark_group"].eq("prior_programmatic_audit")
            & ~boolish_series(benchmark_recovery["valid_human_legacy_overlap"])
        ]
    prior_programmatic_only_rows = len(prior_programmatic_only)
    prior_programmatic_only_recovered = (
        int(prior_programmatic_only["benchmark_recovery_status"].eq("recovered_by_current_chunk").sum())
        if not prior_programmatic_only.empty
        else 0
    )
    prior_programmatic_only_misses = (
        int(prior_programmatic_only["benchmark_recovery_status"].eq("miss").sum())
        if not prior_programmatic_only.empty
        else 0
    )
    chunk_status = "PASS" if requirements["status"].eq("pass").all() else "FAIL"
    text = f"""# Production Chunk Report: {chunk_id}

## Claim

This chunk is a production source-ledger construction package. It does not claim
clean blind URL discovery. It uses a reviewed prior batch output as its starting
state, records production provenance, and keeps prior-programmatic benchmark
evidence separate from source-ledger promotion unless current-run recovery
reaccepts the source.

Chunk status under the stricter production benchmark rule: **{chunk_status}**.

## Source Evidence

```text
prior_batch_slug: {prior_batch_slug}
```

## Counts

| Measure | Count |
|---|---:|
| Target institution-year rows | {target_rows} |
| Institutions | {institutions} |
| Ready for text extraction | {ready_rows} |
| Source-ledger rows | {ledger_rows} |
| Source-ledger unresolved/unrecoverable rows | {unresolved_rows} |
| Unique benchmark institution-year rows | {benchmark_unique_rows} |
| Benchmark group-check rows | {benchmark_rows} |
| Unique benchmark rows recovered by current chunk | {current_recovered_unique_rows} |
| Benchmark group-check rows recovered by current chunk | {current_recovered_rows} |
| Unique benchmark rows promoted from valid human legacy evidence | {promoted_unique_rows} |
| Benchmark group-check rows promoted from valid human legacy evidence | {promoted_rows} |
| Benchmark current-run misses | {benchmark_miss_rows} |
| Prior-programmatic current-run misses | {prior_programmatic_misses} |
| Prior-programmatic misses already source-ledger resolved by valid human legacy | {prior_programmatic_source_resolved_misses} |
| Programmatic-only source-ledger unresolved misses | {prior_programmatic_source_unresolved_misses} |
| Requirement checks passed | {req_pass}/{req_total} |

## Benchmark Recovery

| Benchmark group | Required rows | Current-run recovered | Human-legacy carried forward | Current-run misses | Source-ledger unresolved among misses |
|---|---:|---:|---:|---:|---:|
| Valid human legacy URLs | {valid_human_rows} | {valid_human_rows - valid_human_misses - promoted_rows} | {promoted_rows} | {valid_human_misses} | {valid_human_misses} |
| Prior reviewed programmatic URLs | {prior_programmatic_rows} | {prior_programmatic_rows - prior_programmatic_misses} | 0 | {prior_programmatic_misses} | {prior_programmatic_source_unresolved_misses} |
| Prior reviewed programmatic only, excluding valid-human overlap | {prior_programmatic_only_rows} | {prior_programmatic_only_recovered} | 0 | {prior_programmatic_only_misses} | {prior_programmatic_only_misses} |

`BENCHMARK_RECOVERY.csv` is the row-level ledger of these obligations.
`BENCHMARK_MISSES.csv` lists current-run benchmark failures. Its
`source_ledger_resolved`, `source_ledger_resolution_type`, and
`benchmark_miss_type` columns distinguish benchmark misses that already have a
valid human-legacy production source from misses that still lack a source.

## API Status

{api_note}

## Interpretation

The chunk passes only if every target row is accounted for in either
`OUTPUT_source_ledger_delta.csv` or `UNRESOLVED_ROWS.csv`, accepted sources have
review evidence, no candidate is left waiting for source review, and every known
valid human legacy benchmark row is recovered, promoted, or row-invalidated.
Prior-programmatic benchmark rows must be recovered by the current run or
row-invalidated to pass the prior-programmatic benchmark check. Old
programmatic evidence cannot promote a row into the source ledger by itself.
"""
    path.write_text(text, encoding="utf-8")


def write_manifest(
    path: Path,
    *,
    repo_root: Path,
    chunk_id: str,
    prior_batch_slug: str,
    input_paths: list[Path],
    output_paths: list[Path],
) -> dict[str, object]:
    manifest = {
        "run_id": chunk_id,
        "run_type": "production_chunk",
        "created_at": utc_now(),
        "prior_batch_slug": prior_batch_slug,
        "inputs": [file_record(p, repo_root=repo_root, role="input") for p in input_paths],
        "outputs": [file_record(p, repo_root=repo_root, role="output") for p in output_paths],
    }
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def build_production_chunk_from_prior_batch(
    repo_root: Path,
    *,
    chunk_id: str = DEFAULT_CHUNK_ID,
    prior_batch_slug: str = DEFAULT_PRIOR_BATCH_SLUG,
    prior_audit_slug: str = DEFAULT_PRIOR_AUDIT_SLUG,
) -> ProductionChunkResult:
    repo_root = repo_root.resolve()
    prior_output_dir = repo_root / URL_DISCOVERY_ROOT / prior_batch_slug
    prior_audit_dir = repo_root / AUDIT_ROOT / prior_audit_slug
    prior_output_csv = prior_output_dir / "OUTPUT_urls_for_text_extraction.csv"
    if not prior_output_csv.exists():
        raise FileNotFoundError(f"Missing prior batch output: {prior_output_csv}")

    prior = pd.read_csv(prior_output_csv, low_memory=False)
    ensure_required_input_columns(prior)

    output_dir = repo_root / PRODUCTION_CHUNKS_ROOT / chunk_id
    audit_dir = repo_root / AUDIT_ROOT / f"url_discovery_{chunk_id}"
    output_dir.mkdir(parents=True, exist_ok=True)
    audit_dir.mkdir(parents=True, exist_ok=True)

    handoff = build_handoff(
        prior,
        chunk_id=chunk_id,
        prior_batch_slug=prior_batch_slug,
        prior_output_csv=prior_output_csv,
        prior_audit_dir=prior_audit_dir,
    )

    handoff_path = output_dir / "OUTPUT_urls_for_text_extraction.csv"
    ledger_path = output_dir / "OUTPUT_source_ledger_delta.csv"
    unresolved_path = output_dir / "UNRESOLVED_ROWS.csv"
    benchmark_recovery_path = output_dir / "BENCHMARK_RECOVERY.csv"
    benchmark_misses_path = output_dir / "BENCHMARK_MISSES.csv"
    requirements_path = output_dir / "REQUIREMENTS_STATUS.csv"
    readme_path = output_dir / "README.md"
    report_path = output_dir / "CHUNK_REPORT.md"
    manifest_path = output_dir / "MANIFEST.json"

    benchmark_targets = legacy_benchmark_rows(repo_root, handoff)
    handoff, promoted_keys = apply_prior_benchmark_recovery(
        handoff,
        benchmark_targets,
        recovery_file=benchmark_recovery_path,
    )
    benchmark_recovery, benchmark_misses = build_benchmark_recovery(handoff, benchmark_targets, promoted_keys)
    miss_split = benchmark_miss_split(benchmark_misses)
    write_csv(benchmark_recovery, benchmark_recovery_path)
    write_csv(benchmark_misses, benchmark_misses_path)

    ledger = build_source_ledger_delta(handoff)
    unresolved = build_unresolved_rows(handoff)
    api_summary = read_csv_or_empty(prior_audit_dir / "api_rescue_summary.csv")
    requirements = build_requirements(
        handoff=handoff,
        ledger=ledger,
        unresolved=unresolved,
        benchmark_recovery=benchmark_recovery,
        benchmark_misses=benchmark_misses,
        api_summary=api_summary,
        manifest_exists=True,
    )

    write_csv(handoff, handoff_path)
    write_csv(ledger, ledger_path)
    write_csv(unresolved, unresolved_path)
    write_csv(requirements, requirements_path)
    write_readme(
        readme_path,
        chunk_id=chunk_id,
        prior_batch_slug=prior_batch_slug,
        prior_output_csv=prior_output_csv,
        target_rows=len(handoff),
        ready_rows=len(ledger),
        unresolved_rows=len(unresolved),
        benchmark_rows=len(benchmark_recovery),
        benchmark_unique_rows=len(benchmark_recovery.drop_duplicates(["unitid", "academic_year"]))
        if not benchmark_recovery.empty
        else 0,
        benchmark_misses=len(benchmark_misses),
        prior_programmatic_current_run_misses=miss_split["prior_programmatic_current_run_misses"],
        prior_programmatic_source_resolved_misses=miss_split["prior_programmatic_source_resolved_misses"],
        prior_programmatic_source_unresolved_misses=miss_split["prior_programmatic_source_unresolved_misses"],
    )
    write_chunk_report(
        report_path,
        chunk_id=chunk_id,
        prior_batch_slug=prior_batch_slug,
        target_rows=len(handoff),
        institutions=handoff["unitid"].nunique(),
        ready_rows=int(ready_mask(handoff).sum()),
        unresolved_rows=len(unresolved),
        ledger_rows=len(ledger),
        benchmark_recovery=benchmark_recovery,
        benchmark_misses=benchmark_misses,
        requirements=requirements,
        api_summary=api_summary,
    )

    input_paths = [
        prior_output_csv,
        prior_output_dir / "REQUIREMENTS_STATUS.csv",
        prior_output_dir / "BENCHMARKS_AND_ATTRITION.md",
        repo_root / LEGACY_URL_DISCOVERY_AUDIT,
        prior_audit_dir / "source_review_log.csv",
        prior_audit_dir / "api_rescue_summary.csv",
    ]
    output_paths = [
        handoff_path,
        ledger_path,
        unresolved_path,
        benchmark_recovery_path,
        benchmark_misses_path,
        requirements_path,
        readme_path,
        report_path,
    ]
    manifest = write_manifest(
        manifest_path,
        repo_root=repo_root,
        chunk_id=chunk_id,
        prior_batch_slug=prior_batch_slug,
        input_paths=input_paths,
        output_paths=output_paths,
    )
    output_manifest = pd.DataFrame(manifest["outputs"])
    input_manifest = pd.DataFrame(manifest["inputs"])
    write_csv(input_manifest, audit_dir / "input_manifest.csv")
    write_csv(output_manifest, audit_dir / "output_manifest.csv")
    write_csv(ledger, audit_dir / "source_ledger_delta.csv")
    write_csv(unresolved, audit_dir / "unresolved_rows.csv")
    write_csv(benchmark_recovery, audit_dir / "benchmark_recovery.csv")
    write_csv(benchmark_misses, audit_dir / "benchmark_misses.csv")

    return ProductionChunkResult(
        output_dir=output_dir,
        audit_dir=audit_dir,
        target_rows=len(handoff),
        ready_rows=len(ledger),
        unresolved_rows=len(unresolved),
        requirements_pass=requirements["status"].eq("pass").all(),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--chunk-id", default=DEFAULT_CHUNK_ID)
    parser.add_argument("--prior-batch-slug", default=DEFAULT_PRIOR_BATCH_SLUG)
    parser.add_argument("--prior-audit-slug", default=DEFAULT_PRIOR_AUDIT_SLUG)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = repo_root_from_cwd(args.root)
    result = build_production_chunk_from_prior_batch(
        repo_root,
        chunk_id=args.chunk_id,
        prior_batch_slug=args.prior_batch_slug,
        prior_audit_slug=args.prior_audit_slug,
    )
    print(f"output_dir={result.output_dir}")
    print(f"audit_dir={result.audit_dir}")
    print(f"target_rows={result.target_rows}")
    print(f"ready_rows={result.ready_rows}")
    print(f"unresolved_rows={result.unresolved_rows}")
    print(f"requirements_pass={result.requirements_pass}")
    return 0 if result.requirements_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
