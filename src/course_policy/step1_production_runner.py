"""Clean Step 1 URL-discovery production runner.

This runner builds a URL-stage production chunk from explicit production inputs.
It does not consume historical pilot output folders or historical-inventory
outputs as runtime inputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import pandas as pd
from pandas.errors import EmptyDataError

from .ai_config import repo_root_from_cwd
from .production_release_url_stage import build_url_stage_release_package


PIPELINE_ROOT = Path("artifacts/PIPELINE_OUTPUTS")
URL_DISCOVERY_ROOT = PIPELINE_ROOT / "01_url_discovery"
PRODUCTION_CHUNKS_ROOT = URL_DISCOVERY_ROOT / "production_chunks"
AUDIT_ROOT = Path("artifacts/AUDIT_TRAILS")

REQUIRED_INPUT_FILES = (
    "target_panel.csv",
    "candidate_url_ledger.csv",
    "source_review_log.csv",
    "historical_case_precheck.csv",
    "run_config.json",
)
OPTIONAL_INPUT_FILES = (
    "source_evidence_manifest.csv",
    "benchmark_key.csv",
)
FORBIDDEN_RUNTIME_PATTERNS = (
    "pilot_batch_",
    "artifacts/PILOTS/",
    "artifacts\\PILOTS\\",
    "url_discovery_pilot_batch_",
    "historical_inventory/",
    "historical_inventory\\",
    "url_discovery_historical_inventory/",
    "url_discovery_historical_inventory\\",
    "normalized_historical_url_attempts",
    "normalized_historical_discoveries",
    "institution_priority_buckets",
    "source_family_summary",
)
HISTORICAL_CASE_PRECHECK_REQUIRED_COLUMNS = {
    "unitid",
    "institution_name",
    "historical_priority_bucket",
    "valid_human_legacy_rows",
    "prior_programmatic_accepted_rows",
    "unreviewed_candidate_lead_rows",
    "failed_attempt_rows",
    "known_source_family_summary",
    "known_failure_pattern_summary",
    "historical_precheck_completed",
    "runtime_input_guardrail_confirmed",
    "precheck_created_by",
    "precheck_created_at",
}
HISTORICAL_CASE_PRECHECK_COUNT_COLUMNS = (
    "valid_human_legacy_rows",
    "prior_programmatic_accepted_rows",
    "unreviewed_candidate_lead_rows",
    "failed_attempt_rows",
)
HISTORICAL_CASE_PRECHECK_TEXT_COLUMNS = (
    "historical_priority_bucket",
    "known_source_family_summary",
    "known_failure_pattern_summary",
    "precheck_created_by",
    "precheck_created_at",
)
FORBIDDEN_HISTORICAL_CASE_PRECHECK_COLUMNS = {
    "url",
    "urls",
    "candidate_url",
    "final_url",
    "source_url",
    "accepted_source_url",
    "benchmark_url",
}
DIRECT_URL_VALUE_RE = re.compile(
    r"(?i)(?:\b(?:https?|ftp)://|\b(?:www\.)?[a-z0-9.-]+\.(?:edu|org|com|net|gov|us)(?:/|\?)|"
    r"\b[a-z0-9._~%+-]+/[^\s,;]*\.(?:pdf|html?|php))"
)
ACCEPTED_DECISIONS = {
    "accept_exact_year_catalog",
    "accept_multi_year_catalog",
    "accept_official_policy_source",
    "accept_cached_external_evidence_replay",
    "accept_current_run_source_review",
}
REQUIRED_ACCEPTED_REVIEW_FIELDS = (
    "source_opened",
    "institution_match_confirmed",
    "source_scope_confirmed",
    "source_type_confirmed",
    "year_coverage_confirmed",
    "gap_fill_search_completed",
    "panel_consistency_confirmed",
    "review_decision",
    "review_reason",
    "reviewed_by",
    "reviewed_at",
)
CODE_SNAPSHOT_FILES = (
    "src/course_policy/ai_config.py",
    "src/course_policy/step1_proof_to_scale_url_production.py",
    "src/course_policy/step1_full_production_url_extraction.py",
    "src/course_policy/step1_production_input_builder.py",
    "src/course_policy/step1_production_runner.py",
    "src/course_policy/production_release_url_stage.py",
    "tests/test_step1_production_input_builder.py",
    "tests/test_step1_production_runner.py",
    "tests/test_production_release_url_stage.py",
)


@dataclass(frozen=True)
class Step1ProductionResult:
    output_dir: Path
    audit_dir: Path
    release_dir: Path | None
    target_rows: int
    ready_rows: int
    unresolved_rows: int
    requirements_pass: bool
    release_pass: bool | None


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


def write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_record(path: Path, *, repo_root: Path, role: str) -> dict[str, object]:
    resolved = path if path.is_absolute() else repo_root / path
    try:
        display_path = resolved.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        display_path = str(resolved)
    record: dict[str, object] = {"role": role, "path": display_path, "exists": resolved.exists()}
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


def portable_path(path: Path) -> str:
    parts = path.parts
    if "artifacts" in parts:
        return Path(*parts[parts.index("artifacts") :]).as_posix()
    return path.as_posix() if not path.is_absolute() else path.name


def run_git_command(repo_root: Path, args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception:
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def code_version_record(repo_root: Path) -> dict[str, object]:
    status = run_git_command(repo_root, ["status", "--short"])
    return {
        "git_commit": run_git_command(repo_root, ["rev-parse", "HEAD"]),
        "git_dirty": bool(status),
        "git_status_short": status,
    }


def contains_forbidden_runtime_reference(value: object) -> bool:
    text = clean_text(value).replace("\\", "/")
    return any(pattern.replace("\\", "/") in text for pattern in FORBIDDEN_RUNTIME_PATTERNS)


def assert_no_forbidden_runtime_inputs(input_dir: Path, frames: dict[str, pd.DataFrame]) -> None:
    if contains_forbidden_runtime_reference(input_dir):
        raise ValueError(f"Input directory is not allowed for clean production runner: {input_dir}")
    offenders: list[str] = []
    for name, frame in frames.items():
        for column in frame.columns:
            mask = frame[column].map(contains_forbidden_runtime_reference)
            if mask.any():
                offenders.append(f"{name}:{column}")
    if offenders:
        raise ValueError(
            "Clean production runner inputs contain forbidden non-production runtime references: "
            + ", ".join(sorted(set(offenders)))
        )


def assert_historical_case_precheck_is_not_source_input(precheck: pd.DataFrame) -> None:
    forbidden_columns = [
        column
        for column in precheck.columns
        if clean_text(column).lower() in FORBIDDEN_HISTORICAL_CASE_PRECHECK_COLUMNS
    ]
    if forbidden_columns:
        raise ValueError(
            "historical_case_precheck.csv must not contain row-specific URL columns: "
            + ", ".join(sorted(forbidden_columns))
        )

    offender_columns: list[str] = []
    for column in precheck.columns:
        values = precheck[column].map(clean_text)
        if values.str.contains(DIRECT_URL_VALUE_RE, regex=True, na=False).any():
            offender_columns.append(column)
    if offender_columns:
        raise ValueError(
            "historical_case_precheck.csv must not contain direct URLs; use source-family "
            "and failure-pattern summaries only. Offending columns: "
            + ", ".join(sorted(offender_columns))
        )


def require_columns(frame: pd.DataFrame, columns: set[str], name: str) -> None:
    missing = sorted(columns.difference(frame.columns))
    if missing:
        raise ValueError(f"{name} missing required columns: {', '.join(missing)}")


def normalized_key_frame(frame: pd.DataFrame, *, year_column: str = "academic_year") -> pd.DataFrame:
    out = frame.copy()
    out["unitid"] = pd.to_numeric(out["unitid"], errors="coerce").astype("Int64")
    out[year_column] = pd.to_numeric(out[year_column], errors="coerce").astype("Int64")
    return out.loc[out["unitid"].notna() & out[year_column].notna()].copy()


def load_inputs(
    input_dir: Path,
) -> tuple[dict[str, object], pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    missing = [name for name in REQUIRED_INPUT_FILES if not (input_dir / name).exists()]
    if missing:
        raise FileNotFoundError(f"Missing required production input files: {', '.join(missing)}")
    config = json.loads((input_dir / "run_config.json").read_text(encoding="utf-8"))
    target_panel = read_csv_or_empty(input_dir / "target_panel.csv")
    candidate_ledger = read_csv_or_empty(input_dir / "candidate_url_ledger.csv")
    source_review = read_csv_or_empty(input_dir / "source_review_log.csv")
    historical_case_precheck = read_csv_or_empty(input_dir / "historical_case_precheck.csv")
    evidence_manifest = read_csv_or_empty(input_dir / "source_evidence_manifest.csv")
    benchmark_key = read_csv_or_empty(input_dir / "benchmark_key.csv")

    require_columns(
        target_panel,
        {"unitid", "institution_name", "sector", "state", "academic_year"},
        "target_panel.csv",
    )
    require_columns(candidate_ledger, {"unitid", "academic_year", "candidate_url"}, "candidate_url_ledger.csv")
    require_columns(
        source_review,
        {
            "unitid",
            "academic_year",
            "candidate_url",
            "review_decision",
            "review_reason",
            "reviewed_by",
            "reviewed_at",
        },
        "source_review_log.csv",
    )
    require_columns(
        historical_case_precheck,
        HISTORICAL_CASE_PRECHECK_REQUIRED_COLUMNS,
        "historical_case_precheck.csv",
    )
    assert_historical_case_precheck_is_not_source_input(historical_case_precheck)
    frames = {
        "target_panel.csv": target_panel,
        "candidate_url_ledger.csv": candidate_ledger,
        "source_review_log.csv": source_review,
        "historical_case_precheck.csv": historical_case_precheck,
        "source_evidence_manifest.csv": evidence_manifest,
        "benchmark_key.csv": benchmark_key,
    }
    assert_no_forbidden_runtime_inputs(input_dir, frames)
    return config, target_panel, candidate_ledger, source_review, historical_case_precheck, evidence_manifest, benchmark_key


def selected_review_rows(source_review: pd.DataFrame) -> pd.DataFrame:
    if source_review.empty:
        return source_review
    review = normalized_key_frame(source_review)
    review["decision_rank"] = review["review_decision"].map(clean_text).isin(ACCEPTED_DECISIONS).map({True: 0, False: 1})
    return (
        review.sort_values(["unitid", "academic_year", "decision_rank", "reviewed_at"])
        .drop_duplicates(["unitid", "academic_year"], keep="first")
        .drop(columns=["decision_rank"])
    )


def candidate_by_row(candidate_ledger: pd.DataFrame) -> pd.DataFrame:
    if candidate_ledger.empty:
        return candidate_ledger
    candidates = normalized_key_frame(candidate_ledger)
    if "candidate_rank" not in candidates.columns:
        candidates["candidate_rank"] = 1
    candidates["candidate_rank"] = pd.to_numeric(candidates["candidate_rank"], errors="coerce").fillna(9999)
    return candidates.sort_values(["unitid", "academic_year", "candidate_rank"]).drop_duplicates(
        ["unitid", "academic_year"],
        keep="first",
    )


def evidence_lookup(evidence_manifest: pd.DataFrame) -> dict[tuple[int, int, str], dict[str, str]]:
    if evidence_manifest.empty:
        return {}
    evidence = normalized_key_frame(evidence_manifest)
    lookup: dict[tuple[int, int, str], dict[str, str]] = {}
    for _, row in evidence.iterrows():
        key = (int(row["unitid"]), int(row["academic_year"]), clean_text(row.get("candidate_url")))
        lookup[key] = {column: clean_text(row.get(column)) for column in evidence.columns}
    return lookup


def accepted_source_type(row: pd.Series) -> str:
    explicit = clean_text(row.get("source_type"))
    if explicit:
        return explicit
    url = clean_text(row.get("candidate_url"))
    content_type = clean_text(row.get("content_type")).lower()
    if ".pdf" in url.lower() or "pdf" in content_type:
        return "catalog_pdf"
    return "catalog_or_policy_source"


def build_handoff(
    *,
    chunk_id: str,
    target_panel: pd.DataFrame,
    candidate_ledger: pd.DataFrame,
    source_review: pd.DataFrame,
    evidence_manifest: pd.DataFrame,
    input_dir: Path,
) -> pd.DataFrame:
    target = normalized_key_frame(target_panel)
    candidates = candidate_by_row(candidate_ledger)
    reviews = selected_review_rows(source_review)
    evidence = evidence_lookup(evidence_manifest)
    candidate_map = {
        (int(row["unitid"]), int(row["academic_year"])): row
        for _, row in candidates.iterrows()
    }
    review_map = {
        (int(row["unitid"]), int(row["academic_year"])): row
        for _, row in reviews.iterrows()
    }

    rows: list[dict[str, object]] = []
    now = utc_now()
    for _, row in target.sort_values(["unitid", "academic_year"]).iterrows():
        unitid = int(row["unitid"])
        year = int(row["academic_year"])
        key = (unitid, year)
        candidate = candidate_map.get(key, pd.Series(dtype=object))
        review = review_map.get(key, pd.Series(dtype=object))
        decision = clean_text(review.get("review_decision"))
        candidate_url = clean_text(review.get("candidate_url")) or clean_text(candidate.get("candidate_url"))
        accepted = decision in ACCEPTED_DECISIONS
        evidence_row = evidence.get((unitid, year, candidate_url), {})
        evidence_path = clean_text(evidence_row.get("cached_text_path") or evidence_row.get("source_body_path"))
        evidence_hash = clean_text(evidence_row.get("cached_text_sha256") or evidence_row.get("source_body_sha256"))
        evidence_ref = f"{evidence_hash} {evidence_path}".strip()

        if accepted:
            status = "source_review_ready"
            ready = True
            unresolved_reason = ""
            url_for_text = clean_text(review.get("final_url_after_redirect")) or candidate_url
            stop_reason = ""
        elif candidate_url and decision:
            status = "source_review_rejected"
            ready = False
            unresolved_reason = clean_text(review.get("review_reason")) or "Candidate was reviewed and rejected."
            url_for_text = ""
            stop_reason = unresolved_reason
        elif candidate_url:
            status = "candidate_unreviewed"
            ready = False
            unresolved_reason = "Candidate URL exists but no source-review decision was supplied."
            url_for_text = ""
            stop_reason = unresolved_reason
        else:
            status = "no_candidate_found"
            ready = False
            unresolved_reason = "No candidate URL was supplied for this target row."
            url_for_text = ""
            stop_reason = unresolved_reason

        rows.append(
            {
                "run_id": chunk_id,
                "run_type": "production_chunk",
                "unitid": unitid,
                "institution_name": clean_text(row.get("institution_name")),
                "sector": clean_text(row.get("sector")),
                "state": clean_text(row.get("state")),
                "academic_year": year,
                "target_inclusion_reason": clean_text(row.get("target_inclusion_reason")),
                "estimation_sample_flag": clean_text(row.get("estimation_sample_flag")),
                "panel_fill_flag": clean_text(row.get("panel_fill_flag")),
                "url_status": status,
                "url_status_reason": clean_text(review.get("review_reason")) or unresolved_reason,
                "ready_for_text_extraction": ready,
                "url_for_text_extraction": url_for_text,
                "url_source_bucket": clean_text(review.get("url_source_bucket"))
                or clean_text(candidate.get("candidate_source_method"))
                or ("reviewed_source" if accepted else ""),
                "candidate_url": candidate_url,
                "candidate_generation_method": clean_text(candidate.get("candidate_generation_method"))
                or clean_text(candidate.get("candidate_source_method"))
                or clean_text(review.get("candidate_generation_method"))
                or clean_text(review.get("candidate_source_method")),
                "candidate_source_file": clean_text(candidate.get("candidate_source_file"))
                or clean_text(review.get("candidate_source_file")),
                "candidate_rank": clean_text(candidate.get("candidate_rank")),
                "deterministic_search_completed": clean_text(review.get("deterministic_search_completed")),
                "archive_expansion_completed": clean_text(review.get("archive_expansion_completed")),
                "api_web_rescue_mode": clean_text(review.get("api_web_rescue_mode")),
                "api_web_rescue_status": clean_text(review.get("api_web_rescue_status")),
                "api_web_rescue_reason": clean_text(review.get("api_web_rescue_reason")),
                "retrieval_status": clean_text(review.get("retrieval_status")),
                "http_status": clean_text(review.get("http_status")),
                "final_url_after_redirect": clean_text(review.get("final_url_after_redirect")) or candidate_url,
                "content_type": clean_text(review.get("content_type")),
                "source_page_title": clean_text(review.get("source_page_title")),
                "source_opened": clean_text(review.get("source_opened")),
                "institution_match_confirmed": clean_text(review.get("institution_match_confirmed")),
                "campus_or_unitid_match_confirmed": clean_text(review.get("campus_or_unitid_match_confirmed")),
                "source_scope_confirmed": clean_text(review.get("source_scope_confirmed")),
                "source_type_confirmed": clean_text(review.get("source_type_confirmed")),
                "year_coverage_confirmed": clean_text(review.get("year_coverage_confirmed")),
                "archive_child_links_checked": clean_text(review.get("archive_child_links_checked")),
                "gap_fill_search_completed": clean_text(review.get("gap_fill_search_completed")),
                "panel_consistency_confirmed": clean_text(review.get("panel_consistency_confirmed")),
                "source_type": accepted_source_type(review) if accepted else "",
                "source_year_start": clean_text(review.get("source_year_start")) or year if accepted else "",
                "source_year_end": clean_text(review.get("source_year_end")) or year if accepted else "",
                "source_year_coverage_note": clean_text(review.get("source_year_coverage_note")),
                "review_decision": decision or "not_reviewed_no_target_year_candidate",
                "review_reason": clean_text(review.get("review_reason")) or unresolved_reason,
                "reviewed_by": clean_text(review.get("reviewed_by")),
                "reviewed_at": clean_text(review.get("reviewed_at")),
                "source_review_file": portable_path(input_dir / "source_review_log.csv"),
                "source_evidence_note": clean_text(review.get("source_evidence_note")),
                "evidence_hash_or_cache_path": evidence_ref,
                "unresolved_reason": unresolved_reason,
                "stop_reason": stop_reason,
                "next_required_action": "" if accepted else "source_search_or_review_needed",
                "production_chunk_created_at": now,
            }
        )
    return pd.DataFrame(rows)


def source_year_coverage(row: pd.Series) -> str:
    start = clean_text(row.get("source_year_start"))
    end = clean_text(row.get("source_year_end"))
    note = clean_text(row.get("source_year_coverage_note"))
    if start and end:
        span = f"{start}-{end}"
        return f"{span}: {note}" if note else span
    return note


def provenance_type_for_handoff(row: pd.Series) -> str:
    text = " ".join(
        clean_text(row.get(column)).lower()
        for column in ["url_source_bucket", "candidate_generation_method", "candidate_source_file"]
    )
    if "human_legacy" in text or "legacy_url" in text:
        return "prior_human"
    if "api" in text:
        return "api_assisted"
    if "manual" in text:
        return "manual_review"
    if clean_text(row.get("candidate_url")):
        return "new_programmatic"
    return "manual_review"


def build_source_ledger_delta(handoff: pd.DataFrame) -> pd.DataFrame:
    ready = handoff.loc[handoff["ready_for_text_extraction"].map(truthy)].copy()
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
                "provenance_type": provenance_type_for_handoff(row),
                "review_file": clean_text(row.get("source_review_file")),
                "review_decision": clean_text(row.get("review_decision")),
                "review_reason": clean_text(row.get("review_reason")),
                "reviewed_by": clean_text(row.get("reviewed_by")),
                "reviewed_at": clean_text(row.get("reviewed_at")),
                "evidence_hash_or_cache_path": clean_text(row.get("evidence_hash_or_cache_path")),
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
    unresolved = handoff.loc[~handoff["ready_for_text_extraction"].map(truthy)].copy()
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
        "api_web_rescue_mode",
        "api_web_rescue_status",
        "api_web_rescue_reason",
        "source_review_file",
    ]
    for column in columns:
        if column not in unresolved.columns:
            unresolved[column] = ""
    return unresolved[columns].copy()


def source_review_lookup_by_key(source_review: pd.DataFrame) -> dict[tuple[int, int], pd.DataFrame]:
    if source_review.empty:
        return {}
    review = normalized_key_frame(source_review)
    return {
        (int(unitid), int(year)): group.copy()
        for (unitid, year), group in review.groupby(["unitid", "academic_year"], dropna=False)
    }


def build_benchmark_recovery(
    handoff: pd.DataFrame,
    benchmark_key: pd.DataFrame,
    source_review: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    columns = [
        "benchmark_group",
        "unitid",
        "institution_name",
        "sector",
        "academic_year",
        "benchmark_url",
        "original_benchmark_denominator",
        "active_benchmark_denominator",
        "active_benchmark_row",
        "current_ready",
        "current_run_recovered",
        "row_invalidated_by_current_review",
        "source_ledger_resolved_or_invalidated",
        "accepted_source_url",
        "benchmark_recovery_status",
        "benchmark_resolution_type",
        "benchmark_miss_type",
        "current_url_status",
        "current_review_decision",
        "current_review_reason",
    ]
    if benchmark_key.empty:
        empty = pd.DataFrame(columns=columns)
        return empty, empty.copy()
    require_columns(benchmark_key, {"unitid", "academic_year", "benchmark_url"}, "benchmark_key.csv")
    key = normalized_key_frame(benchmark_key)
    current = normalized_key_frame(handoff)
    review_lookup = source_review_lookup_by_key(source_review if source_review is not None else pd.DataFrame())
    rows: list[dict[str, object]] = []
    for _, target in key.iterrows():
        unitid = int(target["unitid"])
        year = int(target["academic_year"])
        benchmark_url = clean_text(target.get("benchmark_url"))
        current_row = current.loc[current["unitid"].eq(unitid) & current["academic_year"].eq(year)]
        if current_row.empty:
            sector = clean_text(target.get("sector"))
            ready = False
            accepted_url = ""
            invalidated = False
            source_resolved_or_invalidated = False
            status = "miss"
            resolution_type = "unresolved_benchmark_miss"
            miss_type = "not_in_target_panel"
            url_status = "not_in_target_panel"
            decision = ""
            review_reason = ""
        else:
            row = current_row.iloc[0]
            sector = clean_text(row.get("sector")) or clean_text(target.get("sector"))
            ready = truthy(row.get("ready_for_text_extraction"))
            accepted_url = clean_text(row.get("url_for_text_extraction")) if ready else ""
            candidate_url = clean_text(row.get("candidate_url"))
            final_url = clean_text(row.get("final_url_after_redirect"))
            decision = clean_text(row.get("review_decision"))
            review_reason = clean_text(row.get("review_reason"))
            benchmark_was_reviewed_candidate = any(
                benchmark_url_match(value, benchmark_url)
                for value in [candidate_url, final_url]
                if clean_text(value)
            ) and decision not in {"", "not_reviewed_no_target_year_candidate"}
            benchmark_reviewed_rejected = False
            key_reviews = review_lookup.get((unitid, year), pd.DataFrame())
            if not key_reviews.empty:
                for _, review_row in key_reviews.iterrows():
                    review_decision = clean_text(review_row.get("review_decision"))
                    if not review_decision.startswith("reject_"):
                        continue
                    reviewed_urls = [
                        review_row.get("candidate_url"),
                        review_row.get("final_url_after_redirect"),
                        review_row.get("source_query_or_root"),
                    ]
                    if any(benchmark_url_match(value, benchmark_url) for value in reviewed_urls if clean_text(value)):
                        benchmark_reviewed_rejected = True
                        break
            recovered = ready and any(
                benchmark_url_match(value, benchmark_url)
                for value in [accepted_url, candidate_url, final_url]
                if clean_text(value)
            )
            if recovered:
                status = "recovered_by_current_chunk"
                resolution_type = "current_run_recovered"
                miss_type = ""
                invalidated = False
                source_resolved_or_invalidated = True
            elif (benchmark_was_reviewed_candidate and decision.startswith("reject_")) or benchmark_reviewed_rejected:
                status = "row_invalidated_by_current_review"
                resolution_type = "row_invalidated_by_current_review"
                miss_type = ""
                invalidated = True
                source_resolved_or_invalidated = True
            else:
                status = "miss"
                resolution_type = "unresolved_benchmark_miss"
                miss_type = "benchmark_url_not_recovered"
                invalidated = False
                source_resolved_or_invalidated = False
            url_status = clean_text(row.get("url_status"))
            decision = clean_text(row.get("review_decision"))
        rows.append(
            {
                "benchmark_group": clean_text(target.get("benchmark_group")) or "benchmark_key",
                "unitid": unitid,
                "institution_name": clean_text(target.get("institution_name")),
                "sector": sector,
                "academic_year": year,
                "benchmark_url": benchmark_url,
                "original_benchmark_denominator": 1,
                "active_benchmark_denominator": 0 if invalidated else 1,
                "active_benchmark_row": not invalidated,
                "current_ready": ready,
                "current_run_recovered": status == "recovered_by_current_chunk",
                "row_invalidated_by_current_review": invalidated,
                "source_ledger_resolved_or_invalidated": source_resolved_or_invalidated,
                "accepted_source_url": accepted_url,
                "benchmark_recovery_status": status,
                "benchmark_resolution_type": resolution_type,
                "benchmark_miss_type": miss_type,
                "current_url_status": url_status,
                "current_review_decision": decision,
                "current_review_reason": review_reason,
            }
        )
    recovery = pd.DataFrame(rows, columns=columns)
    misses = recovery.loc[recovery["benchmark_recovery_status"].eq("miss")].copy()
    return recovery, misses


def comparable_url(value: object) -> str:
    text = clean_text(value)
    if not text:
        return ""
    parsed_for_archive = urlparse(text)
    if parsed_for_archive.netloc.lower() == "web.archive.org":
        match = re.match(r"^/web/\d{6,14}(?:[a-z_]+)?/(.+)$", parsed_for_archive.path)
        if match:
            text = match.group(1)
            if text.startswith("http:/") and not text.startswith("http://"):
                text = "http://" + text[len("http:/") :].lstrip("/")
            elif text.startswith("https:/") and not text.startswith("https://"):
                text = "https://" + text[len("https:/") :].lstrip("/")
    parsed = urlparse(text)
    if not parsed.scheme or not parsed.netloc:
        return text.rstrip("/")
    hostname = parsed.netloc.lower().split("@")[-1].split(":")[0]
    if hostname.startswith("www."):
        hostname = hostname[4:]
    query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)))
    path = parsed.path.rstrip("/") or "/"
    return urlunparse(("", hostname, path, "", query, ""))


def benchmark_url_match(accepted_url: object, benchmark_url: object) -> bool:
    accepted = clean_text(accepted_url)
    benchmark = clean_text(benchmark_url)
    return bool(accepted and benchmark) and (accepted == benchmark or comparable_url(accepted) == comparable_url(benchmark))


def accepted_review_evidence_complete(handoff: pd.DataFrame) -> tuple[bool, str]:
    accepted = handoff.loc[handoff["ready_for_text_extraction"].map(truthy)].copy()
    if accepted.empty:
        return True, "accepted_rows=0"
    missing: list[str] = []
    for field in REQUIRED_ACCEPTED_REVIEW_FIELDS:
        if field not in accepted.columns:
            missing.append(field)
            continue
        if accepted[field].map(clean_text).eq("").any():
            missing.append(field)
    return not missing, f"accepted_rows={len(accepted)}; missing_fields={','.join(sorted(set(missing)))}"


def accepted_source_cache_complete(handoff: pd.DataFrame) -> tuple[bool, str]:
    accepted = handoff.loc[handoff["ready_for_text_extraction"].map(truthy)].copy()
    if accepted.empty:
        return True, "accepted_rows=0"
    present = accepted["evidence_hash_or_cache_path"].map(clean_text).ne("")
    return bool(present.all()), f"accepted_rows={len(accepted)}; missing_evidence_refs={int((~present).sum())}"


def unreviewed_candidate_count(handoff: pd.DataFrame) -> int:
    return int(
        (
            handoff["candidate_url"].map(clean_text).ne("")
            & handoff["review_decision"].map(clean_text).eq("not_reviewed_no_target_year_candidate")
        ).sum()
    )


def float_config(config: dict[str, object], key: str, default: float) -> float:
    try:
        return float(clean_text(config.get(key)) or default)
    except ValueError:
        return default


def benchmark_required(config: dict[str, object]) -> bool:
    mode = clean_text(config.get("benchmark_mode")).lower()
    return mode not in {"", "not_tested", "none", "off", "not_applicable"}


def sector_ready_rate_detail(handoff: pd.DataFrame, min_sector_rate: float) -> tuple[bool, str]:
    if handoff.empty:
        return False, "target_rows=0"
    details: list[str] = []
    passes = True
    for sector, group in handoff.groupby("sector", dropna=False):
        denominator = len(group)
        ready = int(group["ready_for_text_extraction"].map(truthy).sum())
        rate = ready / denominator if denominator else 0.0
        details.append(f"{clean_text(sector) or 'missing_sector'}={ready}/{denominator} ({rate:.1%})")
        if denominator and rate < min_sector_rate:
            passes = False
    return passes, "; ".join(details)


def combined_ready_rate_detail(handoff: pd.DataFrame, min_ready_rate: float) -> tuple[bool, str]:
    target_rows = len(handoff)
    ready_rows = int(handoff["ready_for_text_extraction"].map(truthy).sum()) if target_rows else 0
    rate = ready_rows / target_rows if target_rows else 0.0
    if min_ready_rate <= 0:
        return True, f"floor_not_configured; ready_rows={ready_rows}; target_rows={target_rows}; ready_rate={rate:.1%}"
    return rate >= min_ready_rate, (
        f"floor={min_ready_rate:.1%}; ready_rows={ready_rows}; target_rows={target_rows}; ready_rate={rate:.1%}"
    )


def api_web_rescue_detail(config: dict[str, object], unresolved: pd.DataFrame) -> tuple[bool, str]:
    required = truthy(config.get("api_web_rescue_required_for_unresolved"))
    unresolved_rows = len(unresolved)
    mode = clean_text(config.get("api_web_rescue_mode")).lower()
    status = clean_text(config.get("api_web_rescue_status")).lower()
    if not required:
        return True, f"not_required_by_run_config; unresolved_rows={unresolved_rows}; mode={mode or 'not_recorded'}; status={status or 'not_recorded'}"
    if unresolved_rows == 0:
        return True, f"required_but_no_unresolved_rows; mode={mode or 'not_recorded'}; status={status or 'not_recorded'}"
    blocked_values = {"", "not_run", "off", "none", "documented_limited_scope_not_full_production_path"}
    global_attempted = mode not in blocked_values and status not in blocked_values and "not_run" not in status
    if unresolved.empty:
        row_attempted = True
    else:
        row_status = unresolved.get("api_web_rescue_status", pd.Series("", index=unresolved.index)).map(clean_text).str.lower()
        row_attempted = bool(row_status.ne("").all() and ~row_status.str.contains("not_run|limited_scope_not_full_production_path", regex=True).any())
    return global_attempted and row_attempted, (
        f"required={required}; unresolved_rows={unresolved_rows}; mode={mode or 'not_recorded'}; "
        f"status={status or 'not_recorded'}; row_level_attempted={row_attempted}"
    )


def benchmark_metric_counts(benchmark_recovery: pd.DataFrame) -> dict[str, int]:
    if benchmark_recovery.empty:
        return {
            "benchmark_rows": 0,
            "current_recovered": 0,
            "row_invalidated": 0,
            "unresolved_misses": 0,
            "active_denominator": 0,
        }
    status = benchmark_recovery["benchmark_recovery_status"].map(clean_text)
    active = pd.to_numeric(
        benchmark_recovery.get("active_benchmark_denominator", pd.Series(1, index=benchmark_recovery.index)),
        errors="coerce",
    ).fillna(1)
    return {
        "benchmark_rows": len(benchmark_recovery),
        "current_recovered": int(status.eq("recovered_by_current_chunk").sum()),
        "row_invalidated": int(status.eq("row_invalidated_by_current_review").sum()),
        "unresolved_misses": int(status.eq("miss").sum()),
        "active_denominator": int(active.sum()),
    }


def candidate_search_accounting_complete(handoff: pd.DataFrame) -> tuple[bool, str]:
    method_present = handoff["candidate_generation_method"].map(clean_text).ne("")
    has_candidate = handoff["candidate_url"].map(clean_text).ne("")
    no_candidate = handoff["url_status"].map(clean_text).eq("no_candidate_found")
    documented_no_candidate = (
        no_candidate
        & handoff.get("deterministic_search_completed", pd.Series("", index=handoff.index)).map(clean_text).ne("")
        & handoff.get("archive_expansion_completed", pd.Series("", index=handoff.index)).map(clean_text).ne("")
        & handoff.get("api_web_rescue_status", pd.Series("", index=handoff.index)).map(clean_text).ne("")
    )
    complete = (has_candidate & method_present) | documented_no_candidate
    return bool(complete.all()), (
        f"target_rows={len(handoff)}; candidate_url_rows={int(handoff['candidate_url'].map(clean_text).ne('').sum())}; "
        f"no_candidate_rows={int(no_candidate.sum())}; missing_search_accounting={int((~complete).sum())}"
    )


def historical_case_precheck_complete(handoff: pd.DataFrame, precheck: pd.DataFrame) -> tuple[bool, str]:
    target_unitids = sorted({int(value) for value in pd.to_numeric(handoff["unitid"], errors="coerce").dropna()})
    if not target_unitids:
        return False, "target_institutions=0; missing_precheck=target_panel_empty"
    if precheck.empty:
        return False, f"target_institutions={len(target_unitids)}; precheck_rows=0; missing_precheck={len(target_unitids)}"

    checked = precheck.copy()
    checked["unitid"] = pd.to_numeric(checked["unitid"], errors="coerce").astype("Int64")
    checked = checked.loc[checked["unitid"].notna()].copy()
    matched = checked.loc[checked["unitid"].isin(target_unitids)].copy()

    completed = (
        matched["historical_precheck_completed"].map(truthy)
        & matched["runtime_input_guardrail_confirmed"].map(truthy)
    )
    completed_unitids = {int(value) for value in matched.loc[completed, "unitid"].dropna()}
    missing_unitids = [unitid for unitid in target_unitids if unitid not in completed_unitids]
    duplicate_rows = int(matched["unitid"].duplicated(keep=False).sum())

    blank_text_fields = 0
    for column in HISTORICAL_CASE_PRECHECK_TEXT_COLUMNS:
        blank_text_fields += int(matched[column].map(clean_text).eq("").sum())

    invalid_count_fields = 0
    for column in HISTORICAL_CASE_PRECHECK_COUNT_COLUMNS:
        invalid_count_fields += int(pd.to_numeric(matched[column], errors="coerce").isna().sum())

    pass_gate = not missing_unitids and duplicate_rows == 0 and blank_text_fields == 0 and invalid_count_fields == 0
    missing_sample = ",".join(str(unitid) for unitid in missing_unitids[:10])
    return pass_gate, (
        f"target_institutions={len(target_unitids)}; precheck_rows={len(matched)}; "
        f"completed_and_guardrail_confirmed={len(completed_unitids)}; "
        f"missing_precheck={len(missing_unitids)}"
        + (f" sample_missing_unitids={missing_sample}" if missing_sample else "")
        + f"; duplicate_precheck_rows={duplicate_rows}; blank_required_text_fields={blank_text_fields}; "
        f"invalid_count_fields={invalid_count_fields}"
    )


def build_requirements(
    *,
    config: dict[str, object],
    handoff: pd.DataFrame,
    ledger: pd.DataFrame,
    unresolved: pd.DataFrame,
    benchmark_recovery: pd.DataFrame,
    benchmark_misses: pd.DataFrame,
    historical_case_precheck: pd.DataFrame,
    input_manifest: pd.DataFrame,
    manifest_exists: bool,
) -> pd.DataFrame:
    now = utc_now()
    target_rows = len(handoff)
    ready_rows = len(ledger)
    unresolved_rows = len(unresolved)
    row_accounting_pass = ready_rows + unresolved_rows == target_rows
    review_pass, review_detail = accepted_review_evidence_complete(handoff)
    cache_pass, cache_detail = accepted_source_cache_complete(handoff)
    unresolved_reasons_pass = unresolved.empty or unresolved["unresolved_reason"].map(clean_text).ne("").all()
    unreviewed = unreviewed_candidate_count(handoff)
    input_path_text = " ".join(input_manifest["path"].map(clean_text)) if not input_manifest.empty else ""
    no_pilot_inputs = not contains_forbidden_runtime_reference(input_path_text)
    precheck_pass, precheck_detail = historical_case_precheck_complete(handoff, historical_case_precheck)
    search_accounting_pass, search_accounting_detail = candidate_search_accounting_complete(handoff)
    min_ready_rate = float_config(config, "production_readiness_min_ready_rate", 0.0)
    min_sector_ready_rate = float_config(config, "production_readiness_min_sector_ready_rate", 0.0)
    combined_ready_pass, combined_ready_detail = combined_ready_rate_detail(handoff, min_ready_rate)
    sector_ready_pass, sector_ready_detail = sector_ready_rate_detail(handoff, min_sector_ready_rate)
    api_rescue_pass, api_rescue_detail = api_web_rescue_detail(config, unresolved)
    benchmark_needed = benchmark_required(config)
    benchmark_denominator = len(benchmark_recovery)
    benchmark_counts = benchmark_metric_counts(benchmark_recovery)
    benchmark_denominator_pass = benchmark_denominator > 0 if benchmark_needed else True
    rows = [
        {
            "requirement_id": "clean_runner_input_contract",
            "pipeline_stage": "01_url_discovery_clean_production_runner",
            "requirement": "Runtime inputs are explicit production files, not pilot or historical-inventory folders.",
            "acceptance_criterion": "Input manifest contains no pilot_batch, artifacts/PILOTS, or old pilot audit paths.",
            "status": "pass" if no_pilot_inputs else "fail",
            "evidence_file": "production_input_manifest.csv",
            "evidence_column_or_check": f"input_files={len(input_manifest)}",
            "gap_if_incomplete": "" if no_pilot_inputs else "Remove non-production runtime inputs from the production runner.",
            "last_checked_at": now,
        },
        {
            "requirement_id": "target_row_accounting",
            "pipeline_stage": "01_url_discovery_clean_production_runner",
            "requirement": "Every target row is in the source ledger or unresolved table.",
            "acceptance_criterion": "ready_rows + unresolved_rows equals target_rows.",
            "status": "pass" if row_accounting_pass else "fail",
            "evidence_file": "OUTPUT_source_ledger_delta.csv; UNRESOLVED_ROWS.csv",
            "evidence_column_or_check": f"target_rows={target_rows}; ready_rows={ready_rows}; unresolved_rows={unresolved_rows}",
            "gap_if_incomplete": "" if row_accounting_pass else "Fix ledger/unresolved row accounting.",
            "last_checked_at": now,
        },
        {
            "requirement_id": "historical_case_precheck_complete",
            "pipeline_stage": "01_url_discovery_clean_production_runner",
            "requirement": "Every target institution has a historical case precheck before coding or completion claims.",
            "acceptance_criterion": "historical_case_precheck.csv has one completed guardrail-confirmed row per target institution and contains no direct URLs.",
            "status": "pass" if precheck_pass else "fail",
            "evidence_file": "historical_case_precheck.csv",
            "evidence_column_or_check": precheck_detail,
            "gap_if_incomplete": "" if precheck_pass else "Create or fix the historical case precheck before claiming this chunk is complete.",
            "last_checked_at": now,
        },
        {
            "requirement_id": "accepted_source_review_evidence",
            "pipeline_stage": "01_url_discovery_clean_production_runner",
            "requirement": "Every accepted URL has source-review evidence.",
            "acceptance_criterion": "Accepted rows have required source-review fields.",
            "status": "pass" if review_pass else "fail",
            "evidence_file": "OUTPUT_urls_for_text_extraction.csv",
            "evidence_column_or_check": review_detail,
            "gap_if_incomplete": "" if review_pass else "Complete source-review evidence for accepted URLs.",
            "last_checked_at": now,
        },
        {
            "requirement_id": "unresolved_stop_reasons",
            "pipeline_stage": "01_url_discovery_clean_production_runner",
            "requirement": "Every unresolved row has an explicit stop reason.",
            "acceptance_criterion": "UNRESOLVED_ROWS.unresolved_reason is nonblank.",
            "status": "pass" if unresolved_reasons_pass else "fail",
            "evidence_file": "UNRESOLVED_ROWS.csv",
            "evidence_column_or_check": f"unresolved_rows={unresolved_rows}",
            "gap_if_incomplete": "" if unresolved_reasons_pass else "Add unresolved reasons.",
            "last_checked_at": now,
        },
        {
            "requirement_id": "source_review_handoff_complete",
            "pipeline_stage": "01_url_discovery_clean_production_runner",
            "requirement": "No candidate URL is left without a review decision at handoff.",
            "acceptance_criterion": "Unreviewed candidate count is zero.",
            "status": "pass" if unreviewed == 0 else "fail",
            "evidence_file": "OUTPUT_urls_for_text_extraction.csv",
            "evidence_column_or_check": f"unreviewed_candidate_count={unreviewed}",
            "gap_if_incomplete": "" if unreviewed == 0 else "Review or remove unreviewed candidate URLs.",
            "last_checked_at": now,
        },
        {
            "requirement_id": "benchmark_misses_resolved_when_key_present",
            "pipeline_stage": "01_url_discovery_clean_production_runner",
            "requirement": "Prior benchmark evidence is either recovered, invalidated, or left visible as a miss.",
            "acceptance_criterion": "BENCHMARK_MISSES.csv is empty for production-source-ledger closure; invalidations are not current-run recoveries.",
            "status": "pass" if benchmark_misses.empty else "fail",
            "evidence_file": "BENCHMARK_MISSES.csv",
            "evidence_column_or_check": (
                f"benchmark_rows={benchmark_denominator}; current_recovered={benchmark_counts['current_recovered']}; "
                f"row_invalidated={benchmark_counts['row_invalidated']}; unresolved_misses={len(benchmark_misses)}"
            ),
            "gap_if_incomplete": "" if benchmark_misses.empty else "Recover or row-invalidate benchmark misses.",
            "last_checked_at": now,
        },
        {
            "requirement_id": "benchmark_denominator_status",
            "pipeline_stage": "01_url_discovery_clean_production_runner",
            "requirement": "Benchmark denominator is nonempty when benchmark recovery is claimed.",
            "acceptance_criterion": "If benchmark_mode is tested, BENCHMARK_RECOVERY.csv has at least one row; otherwise report benchmark_not_tested.",
            "status": "pass" if benchmark_denominator_pass else "fail",
            "evidence_file": "BENCHMARK_RECOVERY.csv",
            "evidence_column_or_check": (
                f"benchmark_mode={clean_text(config.get('benchmark_mode')) or 'not_tested'}; "
                f"benchmark_rows={benchmark_denominator}"
            ),
            "gap_if_incomplete": "" if benchmark_denominator_pass else "Supply a benchmark key or mark benchmark_mode=not_tested.",
            "last_checked_at": now,
        },
        {
            "requirement_id": "candidate_generation_search_accounting",
            "pipeline_stage": "01_url_discovery_clean_production_runner",
            "requirement": "Every row has either a candidate URL or documented search/rescue accounting.",
            "acceptance_criterion": "No target row has blank candidate method and blank deterministic/archive/API rescue accounting.",
            "status": "pass" if search_accounting_pass else "fail",
            "evidence_file": "OUTPUT_urls_for_text_extraction.csv",
            "evidence_column_or_check": search_accounting_detail,
            "gap_if_incomplete": "" if search_accounting_pass else "Record search and rescue attempts for no-candidate rows.",
            "last_checked_at": now,
        },
        {
            "requirement_id": "source_discovery_combined_ready_floor",
            "pipeline_stage": "01_url_discovery_clean_production_runner",
            "requirement": "Combined source-readiness meets the configured production proof floor.",
            "acceptance_criterion": "If production_readiness_min_ready_rate is configured, observed combined ready rate is at or above the floor.",
            "status": "pass" if combined_ready_pass else "fail",
            "evidence_file": "OUTPUT_urls_for_text_extraction.csv",
            "evidence_column_or_check": combined_ready_detail,
            "gap_if_incomplete": "" if combined_ready_pass else "Improve source discovery/recovery before claiming a successful proof batch.",
            "last_checked_at": now,
        },
        {
            "requirement_id": "source_discovery_sector_ready_floor",
            "pipeline_stage": "01_url_discovery_clean_production_runner",
            "requirement": "Each sector meets the configured production proof floor.",
            "acceptance_criterion": "If production_readiness_min_sector_ready_rate is configured, every nonempty sector is at or above the floor.",
            "status": "pass" if sector_ready_pass else "fail",
            "evidence_file": "OUTPUT_urls_for_text_extraction.csv",
            "evidence_column_or_check": (
                f"floor={'not_configured' if min_sector_ready_rate <= 0 else f'{min_sector_ready_rate:.1%}'}; {sector_ready_detail}"
            ),
            "gap_if_incomplete": "" if sector_ready_pass else "Improve the failing sector before scaling; combined readiness is not enough.",
            "last_checked_at": now,
        },
        {
            "requirement_id": "api_web_rescue_attempted_when_required",
            "pipeline_stage": "01_url_discovery_clean_production_runner",
            "requirement": "The configured API/web rescue path is attempted before unresolved rows are frozen.",
            "acceptance_criterion": "When api_web_rescue_required_for_unresolved=true and unresolved rows remain, global and row-level rescue status must show an attempted rescue path.",
            "status": "pass" if api_rescue_pass else "fail",
            "evidence_file": "run_config.json; OUTPUT_urls_for_text_extraction.csv; UNRESOLVED_ROWS.csv",
            "evidence_column_or_check": api_rescue_detail,
            "gap_if_incomplete": "" if api_rescue_pass else "Run or replay the bounded API/web rescue path before packaging this as a production-path proof.",
            "last_checked_at": now,
        },
        {
            "requirement_id": "accepted_source_cached_evidence",
            "pipeline_stage": "01_url_discovery_clean_production_runner",
            "requirement": "Accepted rows have portable source-evidence references.",
            "acceptance_criterion": "Accepted rows have evidence hash/cache path references.",
            "status": "pass" if cache_pass else "fail",
            "evidence_file": "source_evidence_manifest.csv; OUTPUT_urls_for_text_extraction.csv",
            "evidence_column_or_check": cache_detail,
            "gap_if_incomplete": "" if cache_pass else "Package or document cached source evidence for accepted rows.",
            "last_checked_at": now,
        },
        {
            "requirement_id": "manifest_written",
            "pipeline_stage": "01_url_discovery_clean_production_runner",
            "requirement": "Production chunk manifest is written.",
            "acceptance_criterion": "MANIFEST.json exists.",
            "status": "pass" if manifest_exists else "fail",
            "evidence_file": "MANIFEST.json",
            "evidence_column_or_check": "manifest_exists",
            "gap_if_incomplete": "" if manifest_exists else "Write manifest.",
            "last_checked_at": now,
        },
    ]
    return pd.DataFrame(rows)


def sector_rate_rows(handoff: pd.DataFrame) -> list[str]:
    if handoff.empty:
        return ["target_rows=0"]
    rows: list[str] = []
    for sector, group in handoff.groupby("sector", dropna=False):
        denominator = len(group)
        ready = int(group["ready_for_text_extraction"].map(truthy).sum())
        rate = ready / denominator if denominator else 0.0
        rows.append(f"{clean_text(sector) or 'missing_sector'}={ready}/{denominator} ({rate:.1%})")
    return rows


def benchmark_sector_rows(benchmark_recovery: pd.DataFrame) -> list[str]:
    if benchmark_recovery.empty or "sector" not in benchmark_recovery.columns:
        return ["benchmark_rows=0"]
    rows: list[str] = []
    for sector, group in benchmark_recovery.groupby("sector", dropna=False):
        counts = benchmark_metric_counts(group)
        denominator = counts["benchmark_rows"]
        recovered = counts["current_recovered"]
        rate = recovered / denominator if denominator else 0.0
        rows.append(
            f"{clean_text(sector) or 'missing_sector'}="
            f"current_recovered {recovered}/{denominator} ({rate:.1%}); "
            f"invalidated={counts['row_invalidated']}; unresolved_misses={counts['unresolved_misses']}"
        )
    return rows


def uses_human_legacy_candidates(handoff: pd.DataFrame) -> bool:
    if handoff.empty:
        return False
    fields = [
        handoff.get("candidate_generation_method", pd.Series("", index=handoff.index)),
        handoff.get("url_source_bucket", pd.Series("", index=handoff.index)),
    ]
    text = " ".join(" ".join(series.map(clean_text).str.lower().tolist()) for series in fields)
    return "human_legacy" in text or "legacy_url" in text


def build_guideline_crosswalk(
    *,
    config: dict[str, object],
    handoff: pd.DataFrame,
    ledger: pd.DataFrame,
    unresolved: pd.DataFrame,
    benchmark_recovery: pd.DataFrame,
    benchmark_misses: pd.DataFrame,
    requirements: pd.DataFrame,
) -> pd.DataFrame:
    target_rows = len(handoff)
    ready_rows = len(ledger)
    unresolved_rows = len(unresolved)
    ready_rate = ready_rows / target_rows if target_rows else 0.0
    benchmark_counts = benchmark_metric_counts(benchmark_recovery)
    legacy_candidates_used = uses_human_legacy_candidates(handoff)
    benchmark_mode = clean_text(config.get("benchmark_mode")) or "not_tested"
    clean_benchmark_mode = benchmark_mode == "clean_no_legacy_benchmark" and not legacy_candidates_used
    req_pass = bool(not requirements.empty and requirements["status"].map(clean_text).str.lower().eq("pass").all())
    readiness_requirement_ids = {
        "source_discovery_combined_ready_floor",
        "source_discovery_sector_ready_floor",
        "api_web_rescue_attempted_when_required",
    }
    readiness_requirements = requirements.loc[requirements["requirement_id"].isin(readiness_requirement_ids)]
    readiness_gate_pass = bool(
        not readiness_requirements.empty
        and readiness_requirements["status"].map(clean_text).str.lower().eq("pass").all()
    )
    precheck_req = requirements.loc[requirements["requirement_id"].eq("historical_case_precheck_complete")]
    precheck_status = clean_text(precheck_req.iloc[0].get("status")) if not precheck_req.empty else "fail"
    precheck_detail = clean_text(precheck_req.iloc[0].get("evidence_column_or_check")) if not precheck_req.empty else ""
    current_recovery_rate = (
        benchmark_counts["current_recovered"] / benchmark_counts["benchmark_rows"]
        if benchmark_counts["benchmark_rows"]
        else 0.0
    )
    rows = [
        {
            "claim_id": "clean_runner_runtime_inputs",
            "authority_file": "docs/replication_standards/requirements_checklist.md",
            "binding_rule": "Production Step 1 commands must start from explicit production inputs and not require pilot or historical-inventory runtime folders.",
            "observed_value": "blocking_requirements_pass" if req_pass else "blocking_requirements_fail",
            "status": "pass" if req_pass else "fail",
            "supported_claim": "Clean-runner mechanics are satisfied for this chunk." if req_pass else "Clean-runner mechanics are not satisfied.",
            "limitation": "This does not by itself prove source-discovery readiness or journal-grade benchmark performance.",
        },
        {
            "claim_id": "historical_case_precheck_gate",
            "authority_file": "docs/replication_standards/codex_goals/step_1_url_discovery_run_contract.md",
            "binding_rule": "Every Step 1 coding/test batch must consult historical catalog memory through a URL-free case precheck before completion claims.",
            "observed_value": precheck_detail,
            "status": "pass" if precheck_status == "pass" else "fail",
            "supported_claim": "The coding batch had institution-level historical memory before completion was claimed."
            if precheck_status == "pass"
            else "Historical case precheck is missing or incomplete.",
            "limitation": "The precheck is planning memory only; it cannot promote URLs or serve as source evidence.",
        },
        {
            "claim_id": "source_ledger_row_accounting",
            "authority_file": "docs/replication_standards/codex_goals/step_1_url_discovery_run_contract.md",
            "binding_rule": "All target rows must have ready or explicit not-ready status.",
            "observed_value": f"target_rows={target_rows}; ready_rows={ready_rows}; unresolved_rows={unresolved_rows}; ready_rate={ready_rate:.1%}",
            "status": "pass" if ready_rows + unresolved_rows == target_rows else "fail",
            "supported_claim": "Source-ledger row accounting is closed.",
            "limitation": "Unresolved rows remain not ready for text extraction.",
        },
        {
            "claim_id": "source_review_evidence",
            "authority_file": "docs/replication_standards/url_source_review_standard.md",
            "binding_rule": "Accepted production URLs require row-level source evidence and panel-consistency review fields.",
            "observed_value": requirements.loc[
                requirements["requirement_id"].eq("accepted_source_review_evidence"),
                "evidence_column_or_check",
            ].iloc[0]
            if "accepted_source_review_evidence" in set(requirements["requirement_id"])
            else "",
            "status": "pass"
            if (
                "accepted_source_review_evidence" in set(requirements["requirement_id"])
                and requirements.loc[
                    requirements["requirement_id"].eq("accepted_source_review_evidence"), "status"
                ].iloc[0]
                == "pass"
            )
            else "fail",
            "supported_claim": "Accepted rows have required source-review evidence.",
            "limitation": "This is evidence-backed source review, not downstream policy classification.",
        },
        {
            "claim_id": "legacy_carry_forward_accounting",
            "authority_file": "docs/replication_standards/supporting_rules/benchmark_protocol.md",
            "binding_rule": "For production chunks, valid human legacy evidence must be recovered, promoted with provenance, row-invalidated, or left visible as a miss.",
            "observed_value": (
                f"benchmark_rows={benchmark_counts['benchmark_rows']}; "
                f"current_recovered={benchmark_counts['current_recovered']}; "
                f"row_invalidated={benchmark_counts['row_invalidated']}; "
                f"unresolved_misses={benchmark_counts['unresolved_misses']}; "
                f"by_sector={'; '.join(benchmark_sector_rows(benchmark_recovery))}"
            ),
            "status": "pass" if benchmark_counts["unresolved_misses"] == 0 else "fail",
            "supported_claim": "Legacy/prior benchmark rows are accounted for in the production ledger lane.",
            "limitation": "Rows invalidated by review are not current-run recoveries.",
        },
        {
            "claim_id": "clean_no_legacy_benchmark",
            "authority_file": "docs/replication_standards/supporting_rules/benchmark_protocol.md",
            "binding_rule": "A clean no-legacy benchmark cannot receive human legacy URLs, legacy-derived source hints, or source-trust labels as inputs.",
            "observed_value": (
                f"benchmark_mode={benchmark_mode}; human_legacy_candidates_used={legacy_candidates_used}; "
                f"current_recovery_rate={current_recovery_rate:.1%}; by_sector={'; '.join(benchmark_sector_rows(benchmark_recovery))}"
            ),
            "status": "pass"
            if clean_benchmark_mode and current_recovery_rate >= 0.90
            else ("not_tested" if legacy_candidates_used or benchmark_mode != "clean_no_legacy_benchmark" else "fail"),
            "supported_claim": "Clean no-legacy benchmark recovery is supported."
            if clean_benchmark_mode and current_recovery_rate >= 0.90
            else "No clean no-legacy benchmark pass is claimed.",
            "limitation": "Human legacy candidate input makes this a legacy carry-forward/review lane, not a clean discovery benchmark."
            if legacy_candidates_used
            else "",
        },
        {
            "claim_id": "source_discovery_readiness_to_scale",
            "authority_file": "docs/replication_standards/README.md; docs/replication_standards/requirements_checklist.md",
            "binding_rule": "Generated reports cannot authorize ready-to-scale or journal-standard status; a process review must crosswalk observed values to binding criteria.",
            "observed_value": (
                f"ready_rate={ready_rate:.1%}; by_sector={'; '.join(sector_rate_rows(handoff))}; "
                f"readiness_gate_pass={readiness_gate_pass}"
            ),
            "status": "under_review" if readiness_gate_pass else "fail",
            "supported_claim": "Substantive readiness gates are satisfied, pending process review."
            if readiness_gate_pass
            else "Substantive readiness gates failed; ready-to-scale status is not supported.",
            "limitation": "A human process review controls any final pass/fail readiness claim."
            if readiness_gate_pass
            else "Fix failing source-readiness requirements before process review can pass.",
        },
        {
            "claim_id": "api_web_rescue_scope",
            "authority_file": "docs/replication_standards/requirements_checklist.md",
            "binding_rule": "A deterministic-only run cannot pass as a full production-path URL test unless API/web rescue is documented as not eligible or not needed.",
            "observed_value": (
                f"api_web_rescue_mode={clean_text(config.get('api_web_rescue_mode')) or 'not_recorded'}; "
                f"api_web_rescue_status={clean_text(config.get('api_web_rescue_status')) or 'not_recorded'}"
            ),
            "status": "limited_scope",
            "supported_claim": "This run may support only the documented URL-stage scope.",
            "limitation": "Do not call this a full production-path URL test unless bounded API/web rescue is run or ruled out row by row.",
        },
        {
            "claim_id": "journal_release_readiness",
            "authority_file": "docs/replication_standards/requirements_checklist.md",
            "binding_rule": "Final journal releases must include downstream text retrieval, policy extraction/classification, adjudication, final panel construction, and release rebuild evidence.",
            "observed_value": "url_stage_only",
            "status": "not_claimed",
            "supported_claim": "This is not a full journal replication package.",
            "limitation": "Downstream stages are outside this URL-stage package.",
        },
    ]
    return pd.DataFrame(rows)


def write_code_snapshot(repo_root: Path, audit_dir: Path) -> pd.DataFrame:
    snapshot_dir = audit_dir / "code_snapshot"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    for relative in CODE_SNAPSHOT_FILES:
        source = repo_root / relative
        target = snapshot_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.exists():
            shutil.copy2(source, target)
        rows.append(
            {
                "source_path": relative,
                "snapshot_path": target.relative_to(audit_dir).as_posix(),
                "exists": source.exists(),
                "source_sha256": sha256_file(source) if source.exists() else "",
                "snapshot_sha256": sha256_file(target) if target.exists() else "",
            }
        )
    manifest = pd.DataFrame(rows)
    write_csv(manifest, audit_dir / "code_snapshot_manifest.csv")
    return manifest


def copy_source_evidence_to_audit(input_dir: Path, evidence_manifest: pd.DataFrame, audit_dir: Path) -> list[Path]:
    if evidence_manifest.empty:
        return []
    copied: list[Path] = []
    manifest_path = audit_dir / "source_evidence_manifest.csv"
    write_csv(evidence_manifest, manifest_path)
    copied.append(manifest_path)
    cache_root = input_dir / "source_evidence_cache"
    if not cache_root.exists():
        return copied
    target_root = audit_dir / "source_evidence_cache"
    if target_root.exists():
        shutil.rmtree(target_root)
    target_root.mkdir(parents=True, exist_ok=True)
    for source in sorted(cache_root.rglob("*")):
        if not source.is_file():
            continue
        target = target_root / source.relative_to(cache_root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied.append(target)
    return copied


def write_readme(path: Path, *, chunk_id: str, input_dir: Path, target_rows: int, ready_rows: int, unresolved_rows: int) -> None:
    text = f"""# {chunk_id}

This is a clean Step 1 production-runner chunk. It was built from explicit
production inputs, not from historical pilot batch outputs or historical-inventory outputs.

## Runtime Inputs

```text
input_dir: {portable_path(input_dir)}
target_panel.csv
candidate_url_ledger.csv
source_review_log.csv
historical_case_precheck.csv, as URL-free planning memory and guardrail evidence
source_evidence_manifest.csv
benchmark_key.csv, if supplied
run_config.json
```

## Counts

```text
target_rows: {target_rows}
ready_for_text_extraction: {ready_rows}
unresolved_rows: {unresolved_rows}
```
"""
    path.write_text(text, encoding="utf-8")


def write_chunk_report(
    path: Path,
    *,
    chunk_id: str,
    target_rows: int,
    ready_rows: int,
    unresolved_rows: int,
    benchmark_recovery: pd.DataFrame,
    benchmark_misses: pd.DataFrame,
    requirements: pd.DataFrame,
    guideline_crosswalk: pd.DataFrame,
) -> None:
    req_pass = int(requirements["status"].eq("pass").sum())
    ready_rate = ready_rows / target_rows if target_rows else 0.0
    benchmark_counts = benchmark_metric_counts(benchmark_recovery)
    clean_benchmark = guideline_crosswalk.loc[guideline_crosswalk["claim_id"].eq("clean_no_legacy_benchmark")]
    clean_benchmark_status = clean_text(clean_benchmark.iloc[0].get("status")) if not clean_benchmark.empty else "not_tested"
    readiness = guideline_crosswalk.loc[guideline_crosswalk["claim_id"].eq("source_discovery_readiness_to_scale")]
    readiness_status = clean_text(readiness.iloc[0].get("status")) if not readiness.empty else "under_review"
    precheck = requirements.loc[requirements["requirement_id"].eq("historical_case_precheck_complete")]
    precheck_status = clean_text(precheck.iloc[0].get("status")) if not precheck.empty else "fail"
    requirement_lines = []
    for _, row in requirements.iterrows():
        requirement_lines.append(
            "| "
            + " | ".join(
                [
                    clean_text(row.get("requirement_id")),
                    clean_text(row.get("status")),
                    clean_text(row.get("evidence_column_or_check")).replace("|", "/"),
                    clean_text(row.get("gap_if_incomplete")).replace("|", "/"),
                ]
            )
            + " |"
        )
    crosswalk_lines = []
    for _, row in guideline_crosswalk.iterrows():
        crosswalk_lines.append(
            "| "
            + " | ".join(
                [
                    clean_text(row.get("claim_id")),
                    clean_text(row.get("status")),
                    clean_text(row.get("observed_value")).replace("|", "/"),
                    clean_text(row.get("supported_claim")).replace("|", "/"),
                    clean_text(row.get("limitation")).replace("|", "/"),
                ]
            )
            + " |"
        )
    text = f"""# Clean Production Chunk Report: {chunk_id}

## Claim

This is a URL-stage production chunk. It tests whether explicit production
inputs can produce a reviewed source ledger, unresolved-row table, benchmark
files, manifest, and release package without depending on pilot or historical-inventory runtime folders.

This report does not claim downstream text extraction, policy classification, or
final journal-package completion.

## Gate Status

```text
Blocking clean-runner requirements: {req_pass}/{len(requirements)} pass
Historical case precheck:          {precheck_status}
Source-ledger accounting:           {'pass' if ready_rows + unresolved_rows == target_rows else 'fail'}
Ready/source-ledger rate:           {ready_rate:.1%}
Legacy/prior benchmark accounting:  {'not_tested' if benchmark_recovery.empty else ('pass' if benchmark_counts['unresolved_misses'] == 0 else 'fail')}
Clean no-legacy benchmark:          {clean_benchmark_status}
Ready-to-scale/journal claim:       {readiness_status}
```

## Counts

| Measure | Count |
|---|---:|
| Target rows | {target_rows} |
| Ready/source-ledger rows | {ready_rows} |
| Unresolved rows | {unresolved_rows} |
| Ready/source-ledger rate | {ready_rate:.1%} |
| Benchmark rows | {len(benchmark_recovery)} |
| Current-run benchmark recovered | {benchmark_counts['current_recovered']} |
| Benchmark rows invalidated by review | {benchmark_counts['row_invalidated']} |
| Unresolved benchmark misses | {benchmark_counts['unresolved_misses']} |
| Blocking requirement checks passed | {req_pass}/{len(requirements)} |

## Guideline Crosswalk

Generated reports are evidence, not authority. This crosswalk states what this
chunk can and cannot claim under the binding standards.

| Claim | Status | Observed Value | Supported Claim | Limitation |
|---|---|---|---|---|
{chr(10).join(crosswalk_lines)}

## Requirement Checks

| Requirement | Status | Evidence | Gap if incomplete |
|---|---|---|---|
{chr(10).join(requirement_lines)}
"""
    path.write_text(text, encoding="utf-8")


def write_manifest(
    path: Path,
    *,
    repo_root: Path,
    chunk_id: str,
    input_paths: list[Path],
    output_paths: list[Path],
    run_command: str,
) -> dict[str, object]:
    manifest = {
        "run_id": chunk_id,
        "run_type": "production_chunk",
        "created_at": utc_now(),
        "runner": "course_policy.step1_production_runner",
        "run_command": run_command,
        "code_version": code_version_record(repo_root),
        "inputs": [file_record(path, repo_root=repo_root, role="input") for path in input_paths],
        "outputs": [file_record(path, repo_root=repo_root, role="output") for path in output_paths],
    }
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def current_run_command(*, input_dir: Path, chunk_id: str, release_id: str | None, build_release: bool) -> str:
    command = [
        "python",
        "-m",
        "course_policy.step1_production_runner",
        "--input-dir",
        portable_path(input_dir),
        "--chunk-id",
        chunk_id,
    ]
    if release_id:
        command.extend(["--release-id", release_id])
    if build_release:
        command.append("--build-release")
    return "PYTHONPATH=src " + " ".join(command)


def build_step1_production_chunk(
    repo_root: Path,
    *,
    input_dir: Path,
    chunk_id: str,
    release_id: str | None = None,
    build_release: bool = False,
) -> Step1ProductionResult:
    repo_root = repo_root.resolve()
    input_dir = input_dir if input_dir.is_absolute() else repo_root / input_dir
    (
        config,
        target_panel,
        candidate_ledger,
        source_review,
        historical_case_precheck,
        evidence_manifest,
        benchmark_key,
    ) = load_inputs(input_dir)
    configured_chunk = clean_text(config.get("chunk_id"))
    if configured_chunk and configured_chunk != chunk_id:
        raise ValueError(f"run_config chunk_id {configured_chunk} does not match requested {chunk_id}")
    output_dir = repo_root / PRODUCTION_CHUNKS_ROOT / chunk_id
    audit_dir = repo_root / AUDIT_ROOT / f"url_discovery_{chunk_id}"
    if output_dir.exists():
        shutil.rmtree(output_dir)
    if audit_dir.exists():
        shutil.rmtree(audit_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    audit_dir.mkdir(parents=True, exist_ok=True)

    handoff = build_handoff(
        chunk_id=chunk_id,
        target_panel=target_panel,
        candidate_ledger=candidate_ledger,
        source_review=source_review,
        evidence_manifest=evidence_manifest,
        input_dir=input_dir,
    )
    ledger = build_source_ledger_delta(handoff)
    unresolved = build_unresolved_rows(handoff)
    benchmark_recovery, benchmark_misses = build_benchmark_recovery(handoff, benchmark_key, source_review)

    handoff_path = output_dir / "OUTPUT_urls_for_text_extraction.csv"
    ledger_path = output_dir / "OUTPUT_source_ledger_delta.csv"
    unresolved_path = output_dir / "UNRESOLVED_ROWS.csv"
    recovery_path = output_dir / "BENCHMARK_RECOVERY.csv"
    misses_path = output_dir / "BENCHMARK_MISSES.csv"
    requirements_path = output_dir / "REQUIREMENTS_STATUS.csv"
    crosswalk_path = output_dir / "GUIDELINE_CROSSWALK.csv"
    readme_path = output_dir / "README.md"
    report_path = output_dir / "CHUNK_REPORT.md"
    manifest_path = output_dir / "MANIFEST.json"
    run_command_path = audit_dir / "production_command.txt"

    input_paths = [input_dir / name for name in REQUIRED_INPUT_FILES if (input_dir / name).exists()]
    input_paths.extend(input_dir / name for name in OPTIONAL_INPUT_FILES if (input_dir / name).exists())
    input_manifest = pd.DataFrame([file_record(path, repo_root=repo_root, role="input") for path in input_paths])
    write_csv(input_manifest, audit_dir / "production_input_manifest.csv")

    requirements = build_requirements(
        config=config,
        handoff=handoff,
        ledger=ledger,
        unresolved=unresolved,
        benchmark_recovery=benchmark_recovery,
        benchmark_misses=benchmark_misses,
        historical_case_precheck=historical_case_precheck,
        input_manifest=input_manifest,
        manifest_exists=True,
    )
    guideline_crosswalk = build_guideline_crosswalk(
        config=config,
        handoff=handoff,
        ledger=ledger,
        unresolved=unresolved,
        benchmark_recovery=benchmark_recovery,
        benchmark_misses=benchmark_misses,
        requirements=requirements,
    )

    write_csv(handoff, handoff_path)
    write_csv(ledger, ledger_path)
    write_csv(unresolved, unresolved_path)
    write_csv(benchmark_recovery, recovery_path)
    write_csv(benchmark_misses, misses_path)
    write_csv(requirements, requirements_path)
    write_csv(guideline_crosswalk, crosswalk_path)
    write_readme(
        readme_path,
        chunk_id=chunk_id,
        input_dir=input_dir.relative_to(repo_root) if repo_root in input_dir.parents else input_dir,
        target_rows=len(handoff),
        ready_rows=len(ledger),
        unresolved_rows=len(unresolved),
    )
    write_chunk_report(
        report_path,
        chunk_id=chunk_id,
        target_rows=len(handoff),
        ready_rows=len(ledger),
        unresolved_rows=len(unresolved),
        benchmark_recovery=benchmark_recovery,
        benchmark_misses=benchmark_misses,
        requirements=requirements,
        guideline_crosswalk=guideline_crosswalk,
    )
    run_command = current_run_command(
        input_dir=input_dir.relative_to(repo_root) if repo_root in input_dir.parents else input_dir,
        chunk_id=chunk_id,
        release_id=release_id,
        build_release=build_release,
    )
    run_command_path.write_text(run_command + "\n", encoding="utf-8")
    source_evidence_audit_paths = copy_source_evidence_to_audit(input_dir, evidence_manifest, audit_dir)
    code_snapshot_manifest = write_code_snapshot(repo_root, audit_dir)

    output_paths = [
        handoff_path,
        ledger_path,
        unresolved_path,
        recovery_path,
        misses_path,
        requirements_path,
        crosswalk_path,
        readme_path,
        report_path,
        audit_dir / "production_input_manifest.csv",
        run_command_path,
        audit_dir / "code_snapshot_manifest.csv",
        audit_dir / "guideline_crosswalk.csv",
        *source_evidence_audit_paths,
    ]
    manifest = write_manifest(
        manifest_path,
        repo_root=repo_root,
        chunk_id=chunk_id,
        input_paths=input_paths,
        output_paths=output_paths,
        run_command=run_command,
    )
    output_manifest = pd.DataFrame(
        [
            *manifest["outputs"],
            file_record(manifest_path, repo_root=repo_root, role="output"),
        ]
    )
    write_csv(pd.DataFrame(manifest["inputs"]), audit_dir / "input_manifest.csv")
    write_csv(output_manifest, audit_dir / "output_manifest.csv")
    write_csv(ledger, audit_dir / "source_ledger_delta.csv")
    write_csv(unresolved, audit_dir / "unresolved_rows.csv")
    write_csv(benchmark_recovery, audit_dir / "benchmark_recovery.csv")
    write_csv(benchmark_misses, audit_dir / "benchmark_misses.csv")
    write_csv(guideline_crosswalk, audit_dir / "guideline_crosswalk.csv")
    if not code_snapshot_manifest.empty:
        pass

    requirements_pass = requirements["status"].eq("pass").all()
    release_dir: Path | None = None
    release_pass: bool | None = None
    if build_release:
        if not requirements_pass:
            raise ValueError("Production chunk requirements failed; refusing to build release.")
        resolved_release_id = release_id or f"production_release_{chunk_id}"
        release_result = build_url_stage_release_package(
            repo_root,
            chunk_id=chunk_id,
            release_id=resolved_release_id,
            overwrite=True,
        )
        release_dir = release_result.release_dir
        release_pass = release_result.package_pass

    return Step1ProductionResult(
        output_dir=output_dir,
        audit_dir=audit_dir,
        release_dir=release_dir,
        target_rows=len(handoff),
        ready_rows=len(ledger),
        unresolved_rows=len(unresolved),
        requirements_pass=bool(requirements_pass),
        release_pass=release_pass,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--chunk-id", required=True)
    parser.add_argument("--release-id", default=None)
    parser.add_argument("--build-release", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = repo_root_from_cwd(args.root)
    result = build_step1_production_chunk(
        repo_root,
        input_dir=args.input_dir,
        chunk_id=args.chunk_id,
        release_id=args.release_id,
        build_release=args.build_release,
    )
    print(f"output_dir={result.output_dir}")
    print(f"audit_dir={result.audit_dir}")
    if result.release_dir is not None:
        print(f"release_dir={result.release_dir}")
    print(f"target_rows={result.target_rows}")
    print(f"ready_rows={result.ready_rows}")
    print(f"unresolved_rows={result.unresolved_rows}")
    print(f"requirements_pass={result.requirements_pass}")
    if result.release_pass is not None:
        print(f"release_pass={result.release_pass}")
    return 0 if result.requirements_pass and (result.release_pass is not False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
