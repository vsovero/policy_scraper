"""Build and score the clean no-legacy holdout benchmark.

The benchmark uses human legacy rows as withheld truth, but never as discovery
input. Discovery inputs contain institution identity and ordinary homepage
metadata only. Truth files are used after the run to score source discovery,
extraction readiness, and policy classification.
"""

from __future__ import annotations

import argparse
import html
import json
import multiprocessing as mp
import queue as queue_lib
import re
import shutil
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, as_completed, wait
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, quote, unquote, urlencode, urljoin, urlparse, urlunparse

import pandas as pd
from pandas.errors import EmptyDataError

from .ai_config import AIConfig, load_ai_config, repo_root_from_cwd
from .benchmark_protocol import assert_clean_no_legacy_frame, protocol_for_stream
from .batch2_year_candidates import academic_years_from_range, candidate_priority, catalog_year_range, normalized_year_range
from .catalog_url_harmonization import classify_scope, policy_extraction_ready
from .catalog_retrieval import decode_body, extract_link_records, raw_wayback_snapshot_url, retrieve_url, save_source_body
from .gfdatafull_panel_benchmark import (
    DEFAULT_GFDATAFULL,
    DEFAULT_LEGACY_LINKS,
    INFORMATIVE_CLASSES,
    SECTOR_CONFIGS,
    build_classification_flags,
    load_old_policy_panel,
    read_csv_if_exists,
)
from .institution_universe import TARGET_END_YEAR, TARGET_START_YEAR
from .legacy_reproduction_benchmark import normalized_url
from .production_streams import ensure_stream_workspace, get_stream
from .public_fresh_discovery import (
    build_archive_pages_concurrent,
    build_root_candidates_concurrent,
    build_year_panel,
    classify_institution_status,
    empty_legacy_leads,
    utc_now,
    write_workbook,
)
from .batch3_discovery import build_source_root_decisions, build_year_candidates
from .public_fresh_discovery_pipeline import (
    build_final_status,
    call_openai,
    decisions_from_ai_roots,
    direct_catalog_candidates,
    filter_candidate_rows,
    merge_final_panel,
    parse_json_list,
    safe_error_message,
    sha256_text,
    verify_ai_roots,
)


DATA_DIR = Path("artifacts/policy_data_internal")
AUDIT_DIR = DATA_DIR / "audits" / "clean_no_legacy_benchmark" / "current"
INTERIM_STREAM_ROOT = DATA_DIR / "interim" / "streams"
REVIEW_STREAM_ROOT = DATA_DIR / "review" / "streams"
LOG_STREAM_ROOT = DATA_DIR / "logs" / "streams"
EXTERNAL_EVIDENCE_CACHE_DIR = DATA_DIR / "interim" / "external_evidence_cache"
WAYBACK_CDX_VALIDATED_CACHE = EXTERNAL_EVIDENCE_CACHE_DIR / "wayback_cdx_validated_candidates.csv"
DELIVERY_DIR = Path("../policy_data")
INSTITUTION_UNIVERSE = DATA_DIR / "interim" / "institution_universe.csv"

SECTOR_STREAMS = {
    "public": "public_clean_no_legacy_holdout",
    "private": "private_clean_no_legacy_holdout",
}
RUN_NAMESPACE = "current"
AI_TASK_TYPE = "clean_no_legacy_root_web_discovery"
AI_PROMPT_VERSION = "clean_no_legacy_root_web_discovery_v0"
AI_YEAR_GAP_TASK_TYPE = "clean_no_legacy_year_gap_web_discovery"
AI_YEAR_GAP_PROMPT_VERSION = "clean_no_legacy_year_gap_web_discovery_v1"
AI_RESCUE_STATUSES = {
    "source_root_not_found",
    "root_candidates_retrieved_but_not_catalog",
    "source_root_found_no_explicit_years",
    "year_candidates_found",
}
RETRIEVED_STATUSES = {"retrieved", "retrieved_truncated"}
CATALOG_SOURCE_TERMS = (
    "catalog",
    "catalogue",
    "bulletin",
    "course catalog",
    "college catalog",
    "academic catalog",
    "undergraduate catalog",
    "repeat",
    "repeated",
    "repetition",
    "grading",
    "grade",
    "policy",
)
PLACEHOLDER_ERROR_TERMS = re.compile(
    r"\b(page not found|not found|404|forbidden|access denied|temporarily unavailable)\b",
    re.IGNORECASE,
)
GENERIC_LANDING_PATHS = {
    "",
    "/",
    "/index.html",
    "/index.htm",
    "/index.php",
    "/home",
    "/academics",
    "/academics/",
    "/academics/index.html",
    "/academics/index.htm",
    "/registrar",
    "/registrar/",
    "/registrar/index.html",
    "/registrar/index.htm",
}
SPECIALIZED_CATALOG_HOST_PREFIXES = (
    "registrar.",
    "library.",
    "inside.",
    "coursecat.",
    "coursecatalog.",
    "img2.",
    "libraryapps.",
    "catalog.",
    "catalogs.",
)

PROHIBITED_DISCOVERY_INPUT_COLUMNS = {
    "legacy_url",
    "legacy_excerpt",
    "legacy_policy_class",
    "legacy_link_id",
    "legacy_sheet_name",
    "legacy_excel_row",
    "grade_averaging",
    "grade_avg_threshold",
    "grade_forgiveness",
    "grade_forgive_threshold",
    "grade_averaging_normalized",
    "grade_avg_threshold_normalized",
    "grade_forgiveness_normalized",
    "grade_forgive_threshold_normalized",
}


@dataclass(frozen=True)
class HoldoutStreamOutputs:
    truth_csv: Path
    discovery_input_csv: Path
    institutions_csv: Path
    root_candidates_csv: Path
    source_root_decisions_csv: Path
    archive_pages_csv: Path
    year_candidates_csv: Path
    year_panel_csv: Path
    institution_status_csv: Path
    workbook: Path
    discovery_summary_md: Path


@dataclass(frozen=True)
class BenchmarkScoreOutputs:
    row_scores_csv: Path
    summary_csv: Path
    summary_md: Path


@dataclass(frozen=True)
class TruthUrlValidityOutputs:
    retrieval_csv: Path
    summary_csv: Path


@dataclass(frozen=True)
class AIRescueOutputs:
    ai_cases_csv: Path
    ai_triage_csv: Path
    ai_verified_roots_csv: Path
    ai_archive_pages_csv: Path
    ai_year_candidates_csv: Path
    ai_rescue_year_panel_csv: Path
    ai_rescue_status_csv: Path
    workbook: Path
    summary_md: Path


@dataclass(frozen=True)
class AIYearGapOutputs:
    ai_year_gap_cases_csv: Path
    ai_year_gap_triage_csv: Path
    ai_year_gap_verified_roots_csv: Path
    ai_year_gap_archive_pages_csv: Path
    ai_year_gap_candidates_csv: Path
    ai_year_gap_year_panel_csv: Path
    ai_year_gap_status_csv: Path
    workbook: Path
    summary_md: Path


@dataclass(frozen=True)
class InferredYearUrlOutputs:
    inferred_year_candidates_csv: Path
    inferred_year_panel_csv: Path
    inferred_year_status_csv: Path
    workbook: Path
    summary_md: Path


@dataclass(frozen=True)
class ArchiveExpansionOutputs:
    archive_expansion_seed_roots_csv: Path
    archive_expansion_pages_csv: Path
    archive_expansion_candidates_csv: Path
    archive_expansion_panel_csv: Path
    archive_expansion_status_csv: Path
    workbook: Path
    summary_md: Path


@dataclass(frozen=True)
class WaybackCdxOutputs:
    wayback_cdx_seed_roots_csv: Path
    wayback_cdx_lookups_csv: Path
    wayback_cdx_candidates_csv: Path
    wayback_cdx_panel_csv: Path
    wayback_cdx_status_csv: Path
    workbook: Path
    summary_md: Path


def clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def bool_series(values: pd.Series) -> pd.Series:
    if values.empty:
        return pd.Series(dtype=bool)
    if values.dtype == bool:
        return values.fillna(False)
    return values.astype("object").where(values.notna(), False).astype(str).str.strip().str.lower().isin(
        {"true", "1", "1.0", "yes", "y"}
    )


def parse_http_status(value: object) -> int | None:
    text = clean_text(value)
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def has_catalog_source_term(*values: object) -> bool:
    haystack = " ".join(clean_text(value).lower() for value in values)
    return any(term in haystack for term in CATALOG_SOURCE_TERMS)


def generic_landing_path(url: str) -> bool:
    parsed = urlparse(clean_text(url))
    path = parsed.path.lower().rstrip("/")
    if not path:
        path = "/"
    return path in GENERIC_LANDING_PATHS


def retrieval_placeholder_error(result: dict[str, object]) -> bool:
    content_type = clean_text(result.get("content_type")).lower()
    if "pdf" in content_type:
        return False
    page_title = clean_text(result.get("page_title"))
    if PLACEHOLDER_ERROR_TERMS.search(page_title):
        return True
    if "html" not in content_type:
        return False
    body = result.get("body", b"")
    if isinstance(body, bytes):
        body_text = decode_body(body[:20_000], content_type)
    else:
        body_text = clean_text(body)[:20_000]
    return bool(PLACEHOLDER_ERROR_TERMS.search(body_text[:5_000]))


def legacy_url_benchmark_validity(
    *,
    legacy_url: object,
    retrieval_status: object,
    http_status: object,
    final_url: object,
    content_type: object,
    page_title: object,
) -> tuple[bool, str]:
    """Return whether a human URL is still usable for the benchmark denominator.

    The raw retrieval status is not enough: some legacy URLs now resolve to
    unrelated homepages or web-application challenge shells. Those rows should
    stay visible in audit output, but they are not valid clean-pipeline
    reproduction targets.
    """
    status = clean_text(retrieval_status)
    if status not in RETRIEVED_STATUSES:
        return False, "not_retrieved"

    code = parse_http_status(http_status)
    if code == 202:
        return False, "http_202_challenge_or_placeholder"
    if code is not None and code >= 400:
        return False, f"http_{code}"

    legacy = clean_text(legacy_url)
    final = clean_text(final_url) or legacy
    ctype = clean_text(content_type).lower()
    title = clean_text(page_title)
    html_response = "html" in ctype or ctype == ""

    if html_response and normalized_url(legacy) != normalized_url(final):
        final_has_source_term = has_catalog_source_term(final, title)
        if generic_landing_path(final) and not final_has_source_term:
            return False, "generic_landing_redirect"

    return True, "valid"


def current_time() -> str:
    return datetime.now(timezone.utc).isoformat()


def set_run_namespace(namespace: str) -> None:
    global RUN_NAMESPACE
    cleaned = clean_text(namespace) or "current"
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", cleaned):
        raise ValueError("Run namespace may contain only letters, numbers, underscores, dots, and hyphens.")
    RUN_NAMESPACE = cleaned


def stream_run_dir(repo_root: Path, stream_id: str, area: Path) -> Path:
    return repo_root / area / stream_id / RUN_NAMESPACE


def benchmark_audit_dir(repo_root: Path) -> Path:
    return repo_root / DATA_DIR / "audits" / "clean_no_legacy_benchmark" / RUN_NAMESPACE


def stream_id_for_sector(sector: str) -> str:
    if sector not in SECTOR_STREAMS:
        valid = ", ".join(sorted(SECTOR_STREAMS))
        raise ValueError(f"Unknown clean benchmark sector '{sector}'. Valid sectors: {valid}")
    return SECTOR_STREAMS[sector]


def stream_outputs(repo_root: Path, sector: str) -> HoldoutStreamOutputs:
    stream_id = stream_id_for_sector(sector)
    interim = stream_run_dir(repo_root, stream_id, INTERIM_STREAM_ROOT)
    review = stream_run_dir(repo_root, stream_id, REVIEW_STREAM_ROOT)
    logs = stream_run_dir(repo_root, stream_id, LOG_STREAM_ROOT)
    return HoldoutStreamOutputs(
        truth_csv=review / "holdout_truth.csv",
        discovery_input_csv=review / "holdout_discovery_input.csv",
        institutions_csv=interim / "institutions.csv",
        root_candidates_csv=interim / "root_candidates.csv",
        source_root_decisions_csv=interim / "source_root_decisions.csv",
        archive_pages_csv=interim / "archive_pages.csv",
        year_candidates_csv=interim / "year_candidates.csv",
        year_panel_csv=review / "year_panel.csv",
        institution_status_csv=review / "institution_status.csv",
        workbook=review / "rollup.xlsx",
        discovery_summary_md=logs / "summary.md",
    )


def score_outputs(repo_root: Path) -> BenchmarkScoreOutputs:
    out = benchmark_audit_dir(repo_root)
    return BenchmarkScoreOutputs(
        row_scores_csv=out / "clean_no_legacy_holdout_row_scores.csv",
        summary_csv=out / "clean_no_legacy_holdout_summary.csv",
        summary_md=out / "clean_no_legacy_holdout_summary.md",
    )


def truth_url_validity_outputs(repo_root: Path) -> TruthUrlValidityOutputs:
    out = benchmark_audit_dir(repo_root)
    return TruthUrlValidityOutputs(
        retrieval_csv=out / "truth_legacy_url_retrieval.csv",
        summary_csv=out / "truth_legacy_url_retrieval_summary.csv",
    )


def ai_rescue_outputs(repo_root: Path, sector: str) -> AIRescueOutputs:
    stream_id = stream_id_for_sector(sector)
    interim = stream_run_dir(repo_root, stream_id, INTERIM_STREAM_ROOT)
    review = stream_run_dir(repo_root, stream_id, REVIEW_STREAM_ROOT)
    logs = stream_run_dir(repo_root, stream_id, LOG_STREAM_ROOT)
    return AIRescueOutputs(
        ai_cases_csv=review / "ai_rescue_cases.csv",
        ai_triage_csv=review / "ai_rescue_triage.csv",
        ai_verified_roots_csv=review / "ai_rescue_verified_roots.csv",
        ai_archive_pages_csv=interim / "ai_rescue_archive_pages.csv",
        ai_year_candidates_csv=interim / "ai_rescue_year_candidates.csv",
        ai_rescue_year_panel_csv=review / "ai_rescue_year_panel.csv",
        ai_rescue_status_csv=review / "ai_rescue_status.csv",
        workbook=review / "ai_rescue_rollup.xlsx",
        summary_md=logs / "ai_rescue_summary.md",
    )


def ai_year_gap_outputs(repo_root: Path, sector: str) -> AIYearGapOutputs:
    stream_id = stream_id_for_sector(sector)
    interim = stream_run_dir(repo_root, stream_id, INTERIM_STREAM_ROOT)
    review = stream_run_dir(repo_root, stream_id, REVIEW_STREAM_ROOT)
    logs = stream_run_dir(repo_root, stream_id, LOG_STREAM_ROOT)
    return AIYearGapOutputs(
        ai_year_gap_cases_csv=review / "ai_year_gap_cases.csv",
        ai_year_gap_triage_csv=review / "ai_year_gap_triage.csv",
        ai_year_gap_verified_roots_csv=review / "ai_year_gap_verified_roots.csv",
        ai_year_gap_archive_pages_csv=interim / "ai_year_gap_archive_pages.csv",
        ai_year_gap_candidates_csv=interim / "ai_year_gap_candidates.csv",
        ai_year_gap_year_panel_csv=review / "ai_year_gap_year_panel.csv",
        ai_year_gap_status_csv=review / "ai_year_gap_status.csv",
        workbook=review / "ai_year_gap_rollup.xlsx",
        summary_md=logs / "ai_year_gap_summary.md",
    )


def inferred_year_url_outputs(repo_root: Path, sector: str) -> InferredYearUrlOutputs:
    stream_id = stream_id_for_sector(sector)
    interim = stream_run_dir(repo_root, stream_id, INTERIM_STREAM_ROOT)
    review = stream_run_dir(repo_root, stream_id, REVIEW_STREAM_ROOT)
    logs = stream_run_dir(repo_root, stream_id, LOG_STREAM_ROOT)
    return InferredYearUrlOutputs(
        inferred_year_candidates_csv=interim / "inferred_year_url_candidates.csv",
        inferred_year_panel_csv=review / "inferred_year_url_year_panel.csv",
        inferred_year_status_csv=review / "inferred_year_url_status.csv",
        workbook=review / "inferred_year_url_rollup.xlsx",
        summary_md=logs / "inferred_year_url_summary.md",
    )


def archive_expansion_outputs(repo_root: Path, sector: str) -> ArchiveExpansionOutputs:
    stream_id = stream_id_for_sector(sector)
    interim = stream_run_dir(repo_root, stream_id, INTERIM_STREAM_ROOT)
    review = stream_run_dir(repo_root, stream_id, REVIEW_STREAM_ROOT)
    logs = stream_run_dir(repo_root, stream_id, LOG_STREAM_ROOT)
    return ArchiveExpansionOutputs(
        archive_expansion_seed_roots_csv=interim / "archive_expansion_seed_roots.csv",
        archive_expansion_pages_csv=interim / "archive_expansion_pages.csv",
        archive_expansion_candidates_csv=interim / "archive_expansion_candidates.csv",
        archive_expansion_panel_csv=review / "archive_expansion_year_panel.csv",
        archive_expansion_status_csv=review / "archive_expansion_status.csv",
        workbook=review / "archive_expansion_rollup.xlsx",
        summary_md=logs / "archive_expansion_summary.md",
    )


def wayback_cdx_outputs(repo_root: Path, sector: str) -> WaybackCdxOutputs:
    stream_id = stream_id_for_sector(sector)
    interim = stream_run_dir(repo_root, stream_id, INTERIM_STREAM_ROOT)
    review = stream_run_dir(repo_root, stream_id, REVIEW_STREAM_ROOT)
    logs = stream_run_dir(repo_root, stream_id, LOG_STREAM_ROOT)
    return WaybackCdxOutputs(
        wayback_cdx_seed_roots_csv=interim / "wayback_cdx_seed_roots.csv",
        wayback_cdx_lookups_csv=interim / "wayback_cdx_lookups.csv",
        wayback_cdx_candidates_csv=interim / "wayback_cdx_candidates.csv",
        wayback_cdx_panel_csv=review / "wayback_cdx_year_panel.csv",
        wayback_cdx_status_csv=review / "wayback_cdx_status.csv",
        workbook=review / "wayback_cdx_rollup.xlsx",
        summary_md=logs / "wayback_cdx_summary.md",
    )


def load_institution_universe(repo_root: Path) -> pd.DataFrame:
    path = repo_root / INSTITUTION_UNIVERSE
    if not path.exists():
        raise FileNotFoundError(path)
    universe = pd.read_csv(path, low_memory=False)
    universe["unitid"] = pd.to_numeric(universe["unitid"], errors="coerce").astype("Int64")
    return universe


def first_truth_link(links: pd.DataFrame, *, workbook_label: str) -> pd.DataFrame:
    if links.empty:
        return pd.DataFrame(columns=["unitid", "target_year"])
    links = links.loc[links["legacy_workbook"].map(clean_text).eq(workbook_label)].copy()
    if links.empty:
        return pd.DataFrame(columns=["unitid", "target_year"])
    links["target_year"] = pd.to_numeric(links["target_year"], errors="coerce").astype("Int64")
    links["has_human_legacy_url"] = links["legacy_url"].map(clean_text).str.startswith(("http://", "https://"))
    links = links.loc[links["has_human_legacy_url"]].copy()
    if links.empty:
        return pd.DataFrame(columns=["unitid", "target_year"])
    for column in ["legacy_source_priority", "legacy_link_id"]:
        if column not in links.columns:
            links[column] = 0
    return links.sort_values(["unitid", "target_year", "legacy_source_priority", "legacy_link_id"]).drop_duplicates(
        ["unitid", "target_year"],
        keep="first",
    )


def build_truth_rows_for_sector(repo_root: Path, sector: str) -> pd.DataFrame:
    config = SECTOR_CONFIGS[sector]
    old = load_old_policy_panel(repo_root / DEFAULT_GFDATAFULL, config)
    if old.empty:
        return pd.DataFrame()
    old = old.loc[bool_series(old["in_current_target_window_2000_2020"])].copy()
    links = read_csv_if_exists(repo_root / DEFAULT_LEGACY_LINKS)
    truth_links = first_truth_link(links, workbook_label=config.workbook_label)
    if truth_links.empty:
        return pd.DataFrame()
    truth = old.merge(truth_links, on=["unitid", "target_year"], how="inner", suffixes=("", "_legacy"))
    universe = load_institution_universe(repo_root)
    universe_keep = [
        "unitid",
        "institution_name",
        "state",
        "sector",
        "control",
        "webaddr",
    ]
    truth = truth.merge(
        universe[[column for column in universe_keep if column in universe.columns]],
        on="unitid",
        how="left",
        suffixes=("", "_universe"),
    )
    stream_id = stream_id_for_sector(sector)
    protocol = protocol_for_stream(stream_id)
    truth["truth_sector"] = sector
    truth["source_stream"] = stream_id
    truth["benchmark_protocol"] = protocol.name
    truth["counts_as_clean_no_legacy_benchmark"] = protocol.counts_as_clean_no_legacy
    truth["truth_policy_class_informative"] = truth["legacy_policy_class"].map(clean_text).isin(INFORMATIVE_CLASSES)
    truth["institution_name"] = truth["institution_name"].map(clean_text).where(
        truth["institution_name"].map(clean_text).ne(""),
        truth["instnm"].map(clean_text),
    )
    output_columns = [
        "truth_sector",
        "source_stream",
        "benchmark_protocol",
        "counts_as_clean_no_legacy_benchmark",
        "unitid",
        "institution_name",
        "state",
        "sector",
        "control",
        "webaddr",
        "target_year",
        "legacy_url",
        "legacy_policy_class",
        "truth_policy_class_informative",
        "legacy_link_id",
        "legacy_source_role",
        "legacy_sheet_name",
        "legacy_excel_row",
        "source_can_be_prior_evidence",
        "legacy_needs_review",
        "legacy_review_reasons",
        "has_grad_outcome",
        "avg",
        "gradeavg",
        "forgive",
        "gradeforgive",
    ]
    for column in output_columns:
        if column not in truth.columns:
            truth[column] = ""
    truth["unitid"] = pd.to_numeric(truth["unitid"], errors="coerce").astype("Int64")
    truth["target_year"] = pd.to_numeric(truth["target_year"], errors="coerce").astype("Int64")
    return truth[output_columns].sort_values(["truth_sector", "institution_name", "unitid", "target_year"])


def build_all_truth_rows(repo_root: Path, sectors: list[str]) -> pd.DataFrame:
    frames = [build_truth_rows_for_sector(repo_root, sector) for sector in sectors]
    frames = [frame for frame in frames if not frame.empty]
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def build_discovery_input(truth: pd.DataFrame, *, sector: str) -> pd.DataFrame:
    stream_id = stream_id_for_sector(sector)
    rows = truth.loc[truth["truth_sector"].eq(sector)].copy()
    rows = rows.sort_values(["institution_name", "unitid"]).drop_duplicates("unitid", keep="first")
    rows = rows.reset_index(drop=True)
    rows.insert(0, "fresh_rank", range(1, len(rows) + 1))
    rows["batch3_rank"] = rows["fresh_rank"]
    rows["clean_holdout_status"] = "clean_no_legacy_holdout_needs_discovery"
    rows["created_at"] = current_time()
    rows["source_stream"] = stream_id
    protocol = protocol_for_stream(stream_id)
    rows["benchmark_protocol"] = protocol.name
    rows["counts_as_clean_no_legacy_benchmark"] = protocol.counts_as_clean_no_legacy
    columns = [
        "source_stream",
        "benchmark_protocol",
        "counts_as_clean_no_legacy_benchmark",
        "fresh_rank",
        "batch3_rank",
        "unitid",
        "institution_name",
        "state",
        "webaddr",
        "clean_holdout_status",
        "created_at",
    ]
    for column in columns:
        if column not in rows.columns:
            rows[column] = ""
    discovery_input = rows[columns].copy()
    assert_discovery_input_clean(discovery_input)
    return discovery_input


def assert_discovery_input_clean(discovery_input: pd.DataFrame) -> None:
    present = PROHIBITED_DISCOVERY_INPUT_COLUMNS.intersection(discovery_input.columns)
    if present:
        raise ValueError(f"Clean holdout discovery input contains prohibited legacy columns: {sorted(present)}")
    assert_clean_no_legacy_frame(discovery_input)


def write_holdout_files(repo_root: Path, truth: pd.DataFrame, sectors: list[str]) -> None:
    for sector in sectors:
        outputs = stream_outputs(repo_root, sector)
        for path in outputs.__dict__.values():
            path.parent.mkdir(parents=True, exist_ok=True)
        sector_truth = truth.loc[truth["truth_sector"].eq(sector)].copy()
        sector_truth.to_csv(outputs.truth_csv, index=False)
        build_discovery_input(truth, sector=sector).to_csv(outputs.discovery_input_csv, index=False)


def read_holdout_truth(repo_root: Path, sectors: list[str]) -> pd.DataFrame:
    frames = []
    for sector in sectors:
        path = stream_outputs(repo_root, sector).truth_csv
        if path.exists():
            frames.append(pd.read_csv(path, low_memory=False))
    if frames:
        return pd.concat(frames, ignore_index=True, sort=False)
    truth = build_all_truth_rows(repo_root, sectors)
    write_holdout_files(repo_root, truth, sectors)
    return truth


def read_discovery_input(repo_root: Path, sector: str, *, limit: int | None, rank_start: int) -> pd.DataFrame:
    path = stream_outputs(repo_root, sector).discovery_input_csv
    if not path.exists():
        truth = build_truth_rows_for_sector(repo_root, sector)
        write_holdout_files(repo_root, truth, [sector])
    frame = pd.read_csv(path, low_memory=False)
    assert_discovery_input_clean(frame)
    frame = frame.sort_values(["fresh_rank", "unitid"]).copy()
    frame = frame.loc[pd.to_numeric(frame["fresh_rank"], errors="coerce").ge(rank_start)].copy()
    if limit is not None:
        frame = frame.head(limit).copy()
    frame["batch3_rank"] = range(1, len(frame) + 1)
    return frame


def concat_frames(frames: list[pd.DataFrame]) -> pd.DataFrame:
    frames = [frame for frame in frames if not frame.empty]
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def assert_network_preflight(timeout_seconds: int) -> None:
    result = retrieve_url("https://example.com/", timeout_seconds=timeout_seconds, max_bytes=100_000)
    if clean_text(result.get("retrieval_status")) not in {"retrieved", "retrieved_truncated"}:
        raise RuntimeError(
            "Network preflight failed before clean holdout discovery. "
            f"status={clean_text(result.get('retrieval_status'))}; "
            f"error={clean_text(result.get('error_type'))}: {clean_text(result.get('error_message'))}"
        )


def archive_existing_stream_outputs(outputs: HoldoutStreamOutputs, *, reason: str) -> list[Path]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archived: list[Path] = []
    for path in outputs.__dict__.values():
        if not path.exists() or path.name.startswith("holdout_"):
            continue
        archive_dir = path.parent.parent / "archive" / f"{stamp}_{reason}"
        archive_dir.mkdir(parents=True, exist_ok=True)
        target = archive_dir / path.name
        shutil.copy2(path, target)
        archived.append(target)
    return archived


def read_checkpoint(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size <= 1:
        return pd.DataFrame()
    try:
        return pd.read_csv(path, low_memory=False)
    except EmptyDataError:
        return pd.DataFrame()


def truth_url_retrieval_columns() -> list[str]:
    return [
        "legacy_url",
        "truth_legacy_url_retrieval_status",
        "truth_legacy_url_currently_valid",
        "truth_legacy_url_validity_reason",
        "truth_legacy_url_http_status",
        "truth_legacy_url_final_url",
        "truth_legacy_url_content_type",
        "truth_legacy_url_content_length_bytes",
        "truth_legacy_url_page_title",
        "truth_legacy_url_sha256",
        "truth_legacy_url_error_type",
        "truth_legacy_url_error_message",
        "truth_legacy_url_checked_at",
    ]


def retrieve_unique_truth_legacy_urls(
    urls: pd.Series,
    *,
    timeout_seconds: int,
    max_workers: int,
    max_bytes: int,
) -> pd.DataFrame:
    unique_urls = sorted({clean_text(url) for url in urls if clean_text(url).startswith(("http://", "https://"))})
    if not unique_urls:
        return pd.DataFrame(columns=truth_url_retrieval_columns())
    rows: list[dict[str, object]] = []
    checked_at = utc_now()
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(retrieve_url, url, timeout_seconds=timeout_seconds, max_bytes=max_bytes): url
            for url in unique_urls
        }
        for future in as_completed(futures):
            url = futures[future]
            try:
                result = future.result()
            except Exception as exc:  # pragma: no cover - network failures vary.
                result = {
                    "retrieval_status": "error",
                    "http_status": "",
                    "final_url": "",
                    "content_type": "",
                    "content_length_bytes": "",
                    "page_title": "",
                    "sha256": "",
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                }
            benchmark_valid, validity_reason = legacy_url_benchmark_validity(
                legacy_url=url,
                retrieval_status=result.get("retrieval_status"),
                http_status=result.get("http_status"),
                final_url=result.get("final_url"),
                content_type=result.get("content_type"),
                page_title=result.get("page_title"),
            )
            rows.append(
                {
                    "legacy_url": url,
                    "truth_legacy_url_retrieval_status": clean_text(result.get("retrieval_status")),
                    "truth_legacy_url_currently_valid": benchmark_valid,
                    "truth_legacy_url_validity_reason": validity_reason,
                    "truth_legacy_url_http_status": clean_text(result.get("http_status")),
                    "truth_legacy_url_final_url": clean_text(result.get("final_url")),
                    "truth_legacy_url_content_type": clean_text(result.get("content_type")),
                    "truth_legacy_url_content_length_bytes": result.get("content_length_bytes", ""),
                    "truth_legacy_url_page_title": clean_text(result.get("page_title")),
                    "truth_legacy_url_sha256": clean_text(result.get("sha256")),
                    "truth_legacy_url_error_type": clean_text(result.get("error_type")),
                    "truth_legacy_url_error_message": clean_text(result.get("error_message")),
                    "truth_legacy_url_checked_at": checked_at,
                }
            )
    return pd.DataFrame(rows, columns=truth_url_retrieval_columns()).sort_values("legacy_url")


def summarize_truth_url_validity(truth: pd.DataFrame, retrieval: pd.DataFrame) -> pd.DataFrame:
    if truth.empty:
        return pd.DataFrame(
            columns=["sector", "metric", "count", "percent_of_truth_rows_with_human_legacy_url"]
        )
    status = (
        retrieval.reindex(columns=truth_url_retrieval_columns()).copy()
        if not retrieval.empty
        else pd.DataFrame(columns=truth_url_retrieval_columns())
    )
    truth_urls = truth.copy()
    truth_urls["legacy_url"] = truth_urls["legacy_url"].map(clean_text)
    if not status.empty:
        status["legacy_url"] = status["legacy_url"].map(clean_text)
        truth_urls = truth_urls.merge(status.drop_duplicates("legacy_url", keep="last"), on="legacy_url", how="left")
    else:
        truth_urls["truth_legacy_url_retrieval_status"] = ""
    truth_urls["truth_legacy_url_currently_retrieved"] = truth_urls["truth_legacy_url_retrieval_status"].map(clean_text).isin(
        RETRIEVED_STATUSES
    )
    assessments = truth_urls.apply(
        lambda row: legacy_url_benchmark_validity(
            legacy_url=row.get("legacy_url"),
            retrieval_status=row.get("truth_legacy_url_retrieval_status"),
            http_status=row.get("truth_legacy_url_http_status"),
            final_url=row.get("truth_legacy_url_final_url"),
            content_type=row.get("truth_legacy_url_content_type"),
            page_title=row.get("truth_legacy_url_page_title"),
        ),
        axis=1,
    )
    truth_urls["truth_legacy_url_currently_valid"] = [valid for valid, _ in assessments]
    truth_urls["truth_legacy_url_validity_reason"] = [reason for _, reason in assessments]
    rows: list[dict[str, object]] = []

    def add(sector: str, metric: str, count: int, denominator: int) -> None:
        rows.append(
            {
                "sector": sector,
                "metric": metric,
                "count": int(count),
                "percent_of_truth_rows_with_human_legacy_url": round(100 * int(count) / denominator, 1)
                if denominator
                else 0.0,
            }
        )

    sectors = sorted(truth_urls["truth_sector"].map(clean_text).unique())
    for sector in sectors + ["all"]:
        group = truth_urls if sector == "all" else truth_urls.loc[truth_urls["truth_sector"].eq(sector)]
        denominator = len(group)
        checked = group["truth_legacy_url_retrieval_status"].map(clean_text).ne("")
        retrieved = bool_series(group["truth_legacy_url_currently_retrieved"])
        valid = bool_series(group["truth_legacy_url_currently_valid"])
        add(sector, "truth_rows_with_human_legacy_url", denominator, denominator)
        add(sector, "truth_rows_with_truth_url_retrieval_checked", int(checked.sum()), denominator)
        add(sector, "truth_rows_with_currently_retrieved_human_legacy_url", int(retrieved.sum()), denominator)
        add(sector, "truth_rows_with_currently_valid_human_legacy_url", int(valid.sum()), denominator)
        add(sector, "truth_rows_with_retrieved_but_invalid_human_legacy_url", int((retrieved & ~valid).sum()), denominator)
        add(sector, "truth_rows_with_human_legacy_url_not_currently_retrieved", int((checked & ~retrieved).sum()), denominator)
        add(sector, "unique_human_legacy_urls", group["legacy_url"].nunique(dropna=True), denominator)
    return pd.DataFrame(rows)


def audit_truth_legacy_url_validity(
    repo_root: Path,
    sectors: list[str],
    *,
    timeout_seconds: int,
    max_workers: int,
    max_bytes: int,
    resume: bool = True,
) -> TruthUrlValidityOutputs:
    outputs = truth_url_validity_outputs(repo_root)
    for path in outputs.__dict__.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    truth = read_holdout_truth(repo_root, sectors)
    existing = read_checkpoint(outputs.retrieval_csv) if resume else pd.DataFrame()
    urls = pd.Series(dtype=object) if truth.empty else truth["legacy_url"].map(clean_text)
    if not existing.empty and "legacy_url" in existing.columns:
        already_checked = set(existing["legacy_url"].map(clean_text))
        urls = urls.loc[~urls.map(clean_text).isin(already_checked)].copy()
    new_retrieval = retrieve_unique_truth_legacy_urls(
        urls,
        timeout_seconds=timeout_seconds,
        max_workers=max_workers,
        max_bytes=max_bytes,
    )
    retrieval = concat_frames([existing, new_retrieval])
    if not retrieval.empty:
        retrieval = retrieval.reindex(columns=truth_url_retrieval_columns())
        retrieval["legacy_url"] = retrieval["legacy_url"].map(clean_text)
        retrieval = retrieval.drop_duplicates("legacy_url", keep="last").sort_values("legacy_url")
    retrieval.to_csv(outputs.retrieval_csv, index=False)
    summarize_truth_url_validity(truth, retrieval).to_csv(outputs.summary_csv, index=False)
    return outputs


def select_ai_rescue_cases(
    status: pd.DataFrame,
    *,
    max_cases: int | None,
    exclude_unitids: set[int] | None = None,
) -> pd.DataFrame:
    if status.empty:
        return pd.DataFrame()
    cases = status.loc[status["fresh_discovery_status"].isin(AI_RESCUE_STATUSES)].copy()
    if exclude_unitids:
        cases = cases.loc[~pd.to_numeric(cases["unitid"], errors="coerce").astype("Int64").isin(exclude_unitids)].copy()
    cases["status_priority"] = cases["fresh_discovery_status"].map(
        {
            "source_root_found_no_explicit_years": 0,
            "root_candidates_retrieved_but_not_catalog": 1,
            "source_root_not_found": 2,
            "year_candidates_found": 3,
        }
    ).fillna(9)
    cases = cases.sort_values(["status_priority", "fresh_rank", "institution_name", "unitid"]).drop(columns=["status_priority"])
    if max_cases is not None:
        cases = cases.head(max_cases).copy()
    return cases


def add_year_gap_context_to_status(status: pd.DataFrame, panel: pd.DataFrame) -> pd.DataFrame:
    if status.empty or panel.empty:
        return status.copy()
    panel = panel.copy()
    panel["unitid"] = pd.to_numeric(panel["unitid"], errors="coerce").astype("Int64")
    year_column = "target_year" if "target_year" in panel.columns else "year"
    panel["target_year"] = pd.to_numeric(panel[year_column], errors="coerce").astype("Int64")
    url_column = "final_best_url" if "final_best_url" in panel.columns else "best_url"
    if url_column not in panel.columns:
        panel[url_column] = ""
    panel["has_clean_url"] = panel[url_column].map(clean_text).ne("")
    rows = []
    for unitid, group in panel.groupby("unitid", dropna=False):
        if pd.isna(unitid):
            continue
        observed = sorted(set(group.loc[group["has_clean_url"], "target_year"].dropna().astype(int).tolist()))
        missing = sorted(set(group.loc[~group["has_clean_url"], "target_year"].dropna().astype(int).tolist()))
        rows.append(
            {
                "unitid": int(unitid),
                "observed_candidate_years": "; ".join(map(str, observed)),
                "missing_target_years": "; ".join(map(str, missing)),
                "missing_target_year_count": len(missing),
            }
        )
    if not rows:
        return status.copy()
    out = status.drop(columns=["observed_candidate_years", "missing_target_years", "missing_target_year_count"], errors="ignore")
    return out.merge(pd.DataFrame(rows), on="unitid", how="left")


def build_ai_case_prompt(case: pd.Series, root_candidates: pd.DataFrame, *, sector: str) -> str:
    import json

    unitid = int(case["unitid"])
    tried = root_candidates.loc[pd.to_numeric(root_candidates.get("unitid", pd.Series(dtype=object)), errors="coerce").eq(unitid)].copy()
    tried = tried.sort_values(["retrieval_status", "candidate_url"]).head(18) if not tried.empty else pd.DataFrame()
    tried_rows = [
        {
            "candidate_url": clean_text(row.get("candidate_url")),
            "retrieval_status": clean_text(row.get("retrieval_status")),
            "http_status": clean_text(row.get("http_status")),
            "page_title": clean_text(row.get("page_title")),
            "catalog_link_count": int(row.get("catalog_link_count", 0) or 0),
            "archive_link_count": int(row.get("archive_link_count", 0) or 0),
        }
        for _, row in tried.iterrows()
    ]
    sector_label = "public" if sector == "public" else "private nonprofit"
    payload = {
        "role": "You are helping an auditable catalog-discovery pipeline find official college and university catalog archives.",
        "task": f"Find likely official catalog archive roots for a {sector_label} 4-year institution. Human legacy URLs are intentionally withheld.",
        "institution": {
            "unitid": unitid,
            "name": clean_text(case.get("institution_name")),
            "state": clean_text(case.get("state")),
            "webaddr": clean_text(case.get("webaddr")),
            "first_pass_status": clean_text(case.get("fresh_discovery_status")),
            "preferred_source_root_url": clean_text(case.get("preferred_source_root_url")),
            "observed_candidate_years": clean_text(case.get("observed_candidate_years")),
            "missing_target_years": clean_text(case.get("missing_target_years")),
            "missing_target_year_count": clean_text(case.get("missing_target_year_count")),
        },
        "already_tried": tried_rows,
        "rules": [
            "Use web search only for official college/university catalog, bulletin, registrar catalog, academic catalog archive, or institutional repository catalog collection roots.",
            "Prefer institution-wide undergraduate/general catalog archives over graduate, law, medical, seminary, school-specific, policy-only, or handbook-only pages.",
            "If the first pass already found some catalog years, look for additional official archive roots that may cover older or missing academic years rather than returning only the current catalog.",
            "Prioritize official catalog URLs or archive roots that cover the listed missing_target_years. The target years are panel years, not human legacy source hints.",
            "Do not use or infer any human legacy URL. Treat the institution name, state, homepage, and first-pass attempted URLs as the only inputs.",
            "Do not invent URLs. Return only URLs you found or URLs directly supported by an official page you found.",
            "If a current catalog page points to an archive page, return the archive page.",
            "Return compact JSON only.",
        ],
        "required_json_schema": {
            "root_candidates": [
                {
                    "url": "official root/archive/repository URL",
                    "root_type": "catalog_archive|current_catalog_with_archive_links|registrar_catalog_page|institutional_repository_collection|direct_catalog_pdf|other",
                    "confidence": "low|medium|high",
                    "evidence": "short explanation of why this URL is relevant",
                }
            ],
            "direct_catalog_urls": [
                {
                    "url": "direct catalog PDF or HTML URL if found",
                    "catalog_year_text": "catalog year/range shown on page or URL",
                    "evidence": "short explanation",
                }
            ],
            "search_queries_used": ["queries"],
            "stop_reason_if_no_root": "short explanation or empty string",
        },
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def flatten_ai_result(case: pd.Series, parsed: dict[str, object], log_record: dict[str, object]) -> dict[str, object]:
    import json

    roots = parsed.get("root_candidates", []) if isinstance(parsed.get("root_candidates", []), list) else []
    direct = parsed.get("direct_catalog_urls", []) if isinstance(parsed.get("direct_catalog_urls", []), list) else []
    return {
        "unitid": int(case["unitid"]),
        "institution_name": clean_text(case["institution_name"]),
        "fresh_rank": int(case["fresh_rank"]),
        "first_pass_status": clean_text(case["fresh_discovery_status"]),
        "api_validation_status": log_record["validation_status"],
        "api_root_candidate_count": len(roots),
        "api_direct_catalog_url_count": len(direct),
        "api_root_candidates_json": json.dumps(roots, sort_keys=True),
        "api_direct_catalog_urls_json": json.dumps(direct, sort_keys=True),
        "api_search_queries_used": json.dumps(parsed.get("search_queries_used", []), sort_keys=True),
        "api_stop_reason_if_no_root": clean_text(parsed.get("stop_reason_if_no_root", "")),
        "api_log_call_id": log_record["call_id"],
        "api_prompt_path": log_record["prompt_path"],
        "api_raw_response_path": log_record["raw_response_path"],
        "api_parsed_response_path": log_record["parsed_response_path"],
        "api_error_message": log_record["error_message"],
    }


def run_ai_triage_for_sector(
    repo_root: Path,
    *,
    sector: str,
    config: AIConfig,
    status: pd.DataFrame,
    root_candidates: pd.DataFrame,
    max_cases: int | None,
    exclude_unitids: set[int] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    import json
    import uuid

    cases = select_ai_rescue_cases(status, max_cases=max_cases, exclude_unitids=exclude_unitids)
    if config.live_enabled and len(cases) > config.workflow.max_requests_per_run:
        raise ValueError(
            f"selected AI cases={len(cases)} exceeds workflow.max_requests_per_run={config.workflow.max_requests_per_run}"
        )
    config.workflow.log_dir.mkdir(parents=True, exist_ok=True)
    config.workflow.raw_response_dir.mkdir(parents=True, exist_ok=True)
    config.workflow.parsed_response_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, object]] = []
    stream_id = stream_id_for_sector(sector)
    created_at = utc_now()
    for call_num, (_, case) in enumerate(cases.iterrows(), 1):
        call_id = f"{stream_id}_{AI_TASK_TYPE}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"
        prompt = build_ai_case_prompt(case, root_candidates, sector=sector)
        prompt_path = config.workflow.parsed_response_dir / f"{call_id}_prompt.json"
        prompt_path.write_text(prompt, encoding="utf-8")
        parsed: dict[str, object] = {}
        raw_path = parsed_path = None
        validation_status = "dry_run"
        error_message = ""
        print(f"[ai-rescue] {sector} {call_num}/{len(cases)} unitid={int(case['unitid'])} {clean_text(case['institution_name'])}", flush=True)
        if config.live_enabled:
            validation_status = "not_attempted"
            try:
                parsed, raw_path, parsed_path = call_openai(config, prompt, call_id)
                validation_status = "parsed"
            except Exception as exc:  # pragma: no cover - remote failures vary.
                validation_status = "api_error"
                error_message = type(exc).__name__ + ": " + safe_error_message(str(exc), config)
                raw_path = config.workflow.raw_response_dir / f"{call_id}.json"
                raw_path.write_text(json.dumps({"error_message": error_message}, indent=2), encoding="utf-8")
        log_record = {
            "call_id": call_id,
            "task_type": AI_TASK_TYPE,
            "unitid": int(case["unitid"]),
            "institution_name": clean_text(case["institution_name"]),
            "model": config.openai.model,
            "prompt_version": AI_PROMPT_VERSION,
            "schema_version": config.prompts.schema_version,
            "input_hash": sha256_text(prompt),
            "output_hash": sha256_text(json.dumps(parsed, sort_keys=True)) if parsed else "",
            "prompt_path": str(prompt_path),
            "raw_response_path": str(raw_path) if raw_path else "",
            "parsed_response_path": str(parsed_path) if parsed_path else "",
            "validation_status": validation_status,
            "error_message": error_message,
            "created_at": created_at,
        }
        with (config.workflow.log_dir / "api_call_log.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(log_record, sort_keys=True) + "\n")
        rows.append(flatten_ai_result(case, parsed, log_record))
    return cases, pd.DataFrame(rows)


def write_ai_rescue_summary(
    path: Path,
    *,
    sector: str,
    outputs: AIRescueOutputs,
    final_status: pd.DataFrame,
    ai_triage: pd.DataFrame,
    new_cases_attempted: int,
    priority_case_count: int,
) -> None:
    parsed = int(ai_triage["api_validation_status"].eq("parsed").sum()) if not ai_triage.empty else 0
    dry = int(ai_triage["api_validation_status"].eq("dry_run").sum()) if not ai_triage.empty else 0
    errors = int(ai_triage["api_validation_status"].eq("api_error").sum()) if not ai_triage.empty else 0
    added_years = int(final_status["ai_added_years"].sum()) if not final_status.empty and "ai_added_years" in final_status else 0
    recovered_institutions = int(final_status["ai_added_years"].gt(0).sum()) if not final_status.empty and "ai_added_years" in final_status else 0
    lines = [
        f"# {sector.title()} Clean No-Legacy AI Rescue",
        "",
        f"Generated at: {utc_now()}",
        "",
        "Scope: AI/web-search rescue for clean holdout discovery gaps. Human legacy truth remains withheld from prompts.",
        "",
        "## Bottom Line",
        "",
        f"- New API cases attempted in latest run: {new_cases_attempted}",
        f"- Cumulative AI cases attempted: {len(ai_triage)}",
        f"- Total unresolved first-pass cases in scope: {priority_case_count}",
        f"- Unattempted cases remaining: {max(priority_case_count - len(ai_triage), 0)}",
        f"- Parsed live API responses: {parsed}",
        f"- Dry-run prompts: {dry}",
        f"- API errors: {errors}",
        f"- Institutions with AI-added candidate years: {recovered_institutions}",
        f"- Candidate institution-year URLs added after AI/search: {added_years}",
        "",
        "## Outputs",
        "",
    ]
    for label, output_path in outputs.__dict__.items():
        lines.append(f"- {label}: `{output_path}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_ai_rescue_for_sector(
    repo_root: Path,
    sector: str,
    *,
    config_path: Path | None = None,
    max_api_cases: int | None = None,
    timeout_seconds: int = 4,
    max_archive_pages_per_institution: int = 12,
    max_workers: int = 12,
    rematerialize_unitids: set[int] | None = None,
) -> AIRescueOutputs:
    repo_root = repo_root.resolve()
    config = load_ai_config(config_path, root=repo_root)
    if max_api_cases is None:
        max_api_cases = config.workflow.max_requests_per_run if config.live_enabled else 0
    if config.live_enabled and max_api_cases > config.workflow.max_requests_per_run:
        raise ValueError(
            f"max_api_cases={max_api_cases} exceeds workflow.max_requests_per_run={config.workflow.max_requests_per_run}"
        )
    first = stream_outputs(repo_root, sector)
    first_status = read_checkpoint(first.institution_status_csv)
    current_panel = read_latest_full_year_panel(
        repo_root,
        sector,
        include_inferred=True,
        include_archive_expansion=True,
        include_wayback_cdx=True,
        include_ai_rescue=False,
        include_ai_year_gap=False,
    )
    current_panel = normalize_full_year_panel_for_rescue(current_panel) if not current_panel.empty else read_checkpoint(first.year_panel_csv)
    root_candidates = read_checkpoint(first.root_candidates_csv)
    outputs = ai_rescue_outputs(repo_root, sector)
    for output_path in outputs.__dict__.values():
        output_path.parent.mkdir(parents=True, exist_ok=True)

    first_status = add_year_gap_context_to_status(first_status, current_panel)
    priority_case_count = len(select_ai_rescue_cases(first_status, max_cases=None))

    existing_cases = read_checkpoint(outputs.ai_cases_csv)
    existing_triage = read_checkpoint(outputs.ai_triage_csv)
    existing_roots = read_checkpoint(outputs.ai_verified_roots_csv)
    existing_archive_pages = read_checkpoint(outputs.ai_archive_pages_csv)
    existing_candidates = read_checkpoint(outputs.ai_year_candidates_csv)
    already_attempted = non_retryable_ai_attempted_unitids(existing_triage)
    new_cases, new_triage = run_ai_triage_for_sector(
        repo_root,
        sector=sector,
        config=config,
        status=first_status,
        root_candidates=root_candidates,
        max_cases=max_api_cases,
        exclude_unitids=already_attempted,
    )
    if rematerialize_unitids:
        saved_triage_to_materialize = ai_triage_for_unitids(existing_triage, rematerialize_unitids)
    else:
        saved_triage_to_materialize = pd.DataFrame()
    triage_to_materialize = concat_frames([new_triage, saved_triage_to_materialize])
    if not triage_to_materialize.empty and "unitid" in triage_to_materialize.columns:
        triage_to_materialize = triage_to_materialize.drop_duplicates("unitid", keep="last")
    new_roots = (
        verify_ai_roots(triage_to_materialize, timeout_seconds=timeout_seconds)
        if not triage_to_materialize.empty
        else pd.DataFrame()
    )
    decisions = decisions_from_ai_roots(new_roots)
    new_archive_pages, result_by_url = (
        build_archive_pages_concurrent(
            repo_root,
            decisions,
            timeout_seconds=timeout_seconds,
            max_archive_pages_per_institution=max_archive_pages_per_institution,
            max_workers=max_workers,
            source_slug=stream_id_for_sector(sector).replace("_", "-") + "-ai",
        )
        if not decisions.empty
        else (pd.DataFrame(), {})
    )
    new_year_candidates = build_year_candidates(new_archive_pages, result_by_url) if not new_archive_pages.empty else pd.DataFrame()
    if not new_year_candidates.empty:
        new_year_candidates["candidate_source_method"] = "ai_verified_root_archive"
    new_direct_candidates = direct_catalog_candidates(triage_to_materialize, timeout_seconds=timeout_seconds)
    new_added_candidates = concat_frames([new_year_candidates, new_direct_candidates])

    ai_cases = concat_frames([existing_cases, new_cases])
    ai_triage = concat_frames([existing_triage, new_triage])
    ai_roots = concat_frames([existing_roots, new_roots])
    ai_archive_pages = concat_frames([existing_archive_pages, new_archive_pages])
    ai_added_candidates = concat_frames([existing_candidates, new_added_candidates])
    if not ai_cases.empty and "unitid" in ai_cases.columns:
        ai_cases = ai_cases.drop_duplicates("unitid", keep="last")
    if not ai_triage.empty and "unitid" in ai_triage.columns:
        ai_triage = ai_triage.drop_duplicates("unitid", keep="last")
    if not ai_roots.empty and {"unitid", "root_url"}.issubset(ai_roots.columns):
        ai_roots = ai_roots.drop_duplicates(["unitid", "root_url"], keep="last")
    if not ai_archive_pages.empty and {"unitid", "archive_url"}.issubset(ai_archive_pages.columns):
        ai_archive_pages = ai_archive_pages.drop_duplicates(["unitid", "archive_url"], keep="last")
    if not ai_added_candidates.empty and {"unitid", "target_year", "candidate_url"}.issubset(ai_added_candidates.columns):
        ai_added_candidates = ai_added_candidates.drop_duplicates(["unitid", "target_year", "candidate_url"], keep="last")

    all_candidates = filter_candidate_rows(ai_added_candidates) if not ai_added_candidates.empty else ai_added_candidates
    final_panel = merge_final_panel(current_panel, all_candidates)
    final_status = build_final_status(first_status, final_panel, ai_triage, ai_roots)

    ai_cases.to_csv(outputs.ai_cases_csv, index=False)
    ai_triage.to_csv(outputs.ai_triage_csv, index=False)
    ai_roots.to_csv(outputs.ai_verified_roots_csv, index=False)
    ai_archive_pages.to_csv(outputs.ai_archive_pages_csv, index=False)
    ai_added_candidates.to_csv(outputs.ai_year_candidates_csv, index=False)
    final_panel.to_csv(outputs.ai_rescue_year_panel_csv, index=False)
    final_status.to_csv(outputs.ai_rescue_status_csv, index=False)
    write_workbook(
        outputs.workbook,
        {
            "start_here": final_status,
            "ai_triage": ai_triage,
            "ai_verified_roots": ai_roots,
            "ai_year_candidates": ai_added_candidates,
            "ai_rescue_year_panel": final_panel,
            "first_pass_status": first_status,
        },
    )
    write_ai_rescue_summary(
        outputs.summary_md,
        sector=sector,
        outputs=outputs,
        final_status=final_status,
        ai_triage=ai_triage,
        new_cases_attempted=len(new_triage),
        priority_case_count=priority_case_count,
    )
    return outputs


def current_clean_panel_for_gap_search(repo_root: Path, sector: str) -> pd.DataFrame:
    panel = read_latest_full_year_panel(
        repo_root,
        sector,
        include_inferred=True,
        include_archive_expansion=True,
        include_wayback_cdx=True,
        include_ai_year_gap=True,
    )
    if panel.empty:
        return pd.DataFrame(columns=["unitid", "target_year", "best_url"])
    return normalize_full_year_panel_for_rescue(panel)


def read_latest_full_year_panel(
    repo_root: Path,
    sector: str,
    *,
    include_inferred: bool = True,
    include_archive_expansion: bool = True,
    include_wayback_cdx: bool = True,
    include_ai_rescue: bool = True,
    include_ai_year_gap: bool = True,
) -> pd.DataFrame:
    paths: list[Path] = []
    if include_wayback_cdx:
        paths.append(wayback_cdx_outputs(repo_root, sector).wayback_cdx_panel_csv)
    if include_archive_expansion:
        paths.append(archive_expansion_outputs(repo_root, sector).archive_expansion_panel_csv)
    if include_inferred:
        paths.append(inferred_year_url_outputs(repo_root, sector).inferred_year_panel_csv)
    if include_ai_year_gap:
        paths.append(ai_year_gap_outputs(repo_root, sector).ai_year_gap_year_panel_csv)
    if include_ai_rescue:
        paths.append(ai_rescue_outputs(repo_root, sector).ai_rescue_year_panel_csv)
    paths.append(stream_outputs(repo_root, sector).year_panel_csv)
    existing_paths = [(index, path) for index, path in enumerate(paths) if path.exists()]
    existing_paths = sorted(existing_paths, key=lambda item: (item[1].stat().st_mtime, -item[0]), reverse=True)
    for _, path in existing_paths:
        panel = read_checkpoint(path)
        if not panel.empty:
            return panel
    return pd.DataFrame()


def normalize_full_year_panel_for_rescue(panel: pd.DataFrame) -> pd.DataFrame:
    panel = panel.copy()
    year_column = "target_year" if "target_year" in panel.columns else "year"
    panel["target_year"] = pd.to_numeric(panel[year_column], errors="coerce").astype("Int64")
    if "final_best_url" in panel.columns:
        final_status = panel.get("final_status", pd.Series("", index=panel.index)).fillna("").map(clean_text)
        final_source = panel.get("final_best_url_source", pd.Series("", index=panel.index)).fillna("").map(clean_text)
        ai_or_gap_source = final_status.eq("ai_candidate_added") | final_source.str.startswith("ai_")
        base_link_text = panel.get("candidate_link_text_x", panel.get("candidate_link_text", pd.Series("", index=panel.index))).fillna("").map(clean_text)
        ai_link_text = panel.get("candidate_link_text_y", pd.Series("", index=panel.index)).fillna("").map(clean_text)
        plain_link_text = panel.get("candidate_link_text", pd.Series("", index=panel.index)).fillna("").map(clean_text)
        base_archive_url = panel.get("archive_url_x", panel.get("archive_url", pd.Series("", index=panel.index))).fillna("").map(clean_text)
        ai_archive_url = panel.get("archive_url_y", pd.Series("", index=panel.index)).fillna("").map(clean_text)
        plain_archive_url = panel.get("archive_url", pd.Series("", index=panel.index)).fillna("").map(clean_text)
        panel["best_url"] = panel["final_best_url"].fillna("").map(clean_text)
        panel["best_url_source"] = final_source
        panel["candidate_link_text"] = base_link_text
        panel.loc[ai_or_gap_source & ai_link_text.ne(""), "candidate_link_text"] = ai_link_text
        panel.loc[final_status.eq("ai_candidate_added") & plain_link_text.ne(""), "candidate_link_text"] = plain_link_text
        panel["archive_url"] = base_archive_url
        panel.loc[ai_or_gap_source & ai_archive_url.ne(""), "archive_url"] = ai_archive_url
        panel.loc[final_status.eq("ai_candidate_added") & plain_archive_url.ne(""), "archive_url"] = plain_archive_url
        panel["candidate_evidence_source"] = final_source
    elif "best_url" in panel.columns:
        panel["best_url"] = panel["best_url"].fillna("").map(clean_text)
    else:
        panel["best_url"] = ""
    panel = panel.drop(
        columns=[
            "ai_candidate_url",
            "candidate_source_method",
            "candidate_evidence_text",
            "candidate_link_text_x",
            "candidate_link_text_y",
            "archive_url_x",
            "archive_url_y",
        ],
        errors="ignore",
    )
    return panel


def read_best_full_year_panel(
    repo_root: Path,
    sector: str,
    *,
    include_inferred: bool = True,
    include_archive_expansion: bool = True,
    include_wayback_cdx: bool = True,
    include_ai_rescue: bool = True,
    include_ai_year_gap: bool = True,
) -> pd.DataFrame:
    """Return the row-wise best current panel across recovery layers."""
    paths: list[tuple[int, str, Path]] = []
    if include_archive_expansion:
        paths.append((0, "archive_expansion_year_panel.csv", archive_expansion_outputs(repo_root, sector).archive_expansion_panel_csv))
    if include_ai_year_gap:
        paths.append((1, "ai_year_gap_year_panel.csv", ai_year_gap_outputs(repo_root, sector).ai_year_gap_year_panel_csv))
    if include_ai_rescue:
        paths.append((2, "ai_rescue_year_panel.csv", ai_rescue_outputs(repo_root, sector).ai_rescue_year_panel_csv))
    if include_wayback_cdx:
        paths.append((3, "wayback_cdx_year_panel.csv", wayback_cdx_outputs(repo_root, sector).wayback_cdx_panel_csv))
    if include_inferred:
        paths.append((4, "inferred_year_url_year_panel.csv", inferred_year_url_outputs(repo_root, sector).inferred_year_panel_csv))
    paths.append((5, "year_panel.csv", stream_outputs(repo_root, sector).year_panel_csv))

    frames: list[pd.DataFrame] = []
    for priority, filename, path in paths:
        if not path.exists():
            continue
        panel = read_checkpoint(path)
        if panel.empty:
            continue
        panel = normalize_full_year_panel_for_rescue(panel)
        panel["_selected_panel_file"] = filename
        panel["_selected_panel_priority"] = priority
        panel["_current_run_file"] = str(path)
        frames.append(panel)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True, sort=False)
    out["unitid"] = pd.to_numeric(out.get("unitid"), errors="coerce").astype("Int64")
    out["target_year"] = pd.to_numeric(out.get("target_year"), errors="coerce").astype("Int64")
    out["best_url"] = out.get("best_url", pd.Series("", index=out.index)).fillna("").map(clean_text)
    out["best_url_source"] = out.get("best_url_source", pd.Series("", index=out.index)).fillna("").map(clean_text)
    out["_has_url"] = out["best_url"].ne("")
    url_lower = out["best_url"].str.lower()
    source_lower = out["best_url_source"].str.lower()
    generic_search = (
        url_lower.str.contains("archive.org/search", regex=False)
        | url_lower.str.contains("/search?", regex=False)
        | url_lower.str.contains("query=", regex=False)
    )
    generic_landing = url_lower.str.rstrip("/").str.endswith(
        ("catalog-archives", "catalog/archive", "catalog/archives")
    )
    risky_catalogarchive = out.apply(risky_catalogarchive_candidate, axis=1)
    out["_candidate_specificity_rank"] = 0
    out.loc[generic_landing, "_candidate_specificity_rank"] = 1
    out.loc[generic_search, "_candidate_specificity_rank"] = 2
    out.loc[risky_catalogarchive, "_candidate_specificity_rank"] = 2
    out.loc[source_lower.str.contains("direct_catalog_url", regex=False) & generic_search, "_candidate_specificity_rank"] = 3
    out = out.sort_values(
        ["unitid", "target_year", "_has_url", "_candidate_specificity_rank", "_selected_panel_priority"],
        ascending=[True, True, False, True, True],
    )
    return out.drop_duplicates(["unitid", "target_year"], keep="first").drop(
        columns=["_has_url", "_candidate_specificity_rank"],
        errors="ignore",
    )


def parse_years_list(value: object) -> list[int]:
    years = []
    for piece in clean_text(value).replace(",", ";").split(";"):
        piece = piece.strip()
        if piece.isdigit():
            year = int(piece)
            if 1990 <= year <= 2035:
                years.append(year)
    return sorted(set(years))


def build_ai_year_gap_cases(
    status: pd.DataFrame,
    panel: pd.DataFrame,
    *,
    max_cases: int | None,
    exclude_unitids: set[int] | None = None,
) -> pd.DataFrame:
    if status.empty or panel.empty:
        return pd.DataFrame()
    panel = panel.copy()
    panel["unitid"] = pd.to_numeric(panel["unitid"], errors="coerce").astype("Int64")
    panel["target_year"] = pd.to_numeric(panel["target_year"], errors="coerce").astype("Int64")
    panel["has_clean_url"] = panel["best_url"].map(clean_text).ne("")
    rows = []
    for unitid, group in panel.groupby("unitid", dropna=False):
        if pd.isna(unitid):
            continue
        observed = sorted(set(group.loc[group["has_clean_url"], "target_year"].dropna().astype(int).tolist()))
        missing = sorted(set(group.loc[~group["has_clean_url"], "target_year"].dropna().astype(int).tolist()))
        if not missing:
            continue
        rows.append(
            {
                "unitid": int(unitid),
                "observed_candidate_years": "; ".join(map(str, observed)),
                "missing_target_years": "; ".join(map(str, missing)),
                "missing_target_year_count": len(missing),
            }
        )
    if not rows:
        return pd.DataFrame()
    cases = pd.DataFrame(rows)
    status_columns = [
        "unitid",
        "fresh_rank",
        "institution_name",
        "state",
        "webaddr",
        "fresh_discovery_status",
        "final_discovery_status",
        "preferred_source_root_url",
        "preferred_source_root_type",
        "preferred_source_root_title",
    ]
    status_keep = status[[column for column in status_columns if column in status.columns]].copy()
    status_keep["unitid"] = pd.to_numeric(status_keep["unitid"], errors="coerce").astype("Int64")
    status_keep = status_keep.drop_duplicates("unitid", keep="last")
    cases = cases.merge(status_keep, on="unitid", how="left")
    if exclude_unitids:
        cases = cases.loc[~pd.to_numeric(cases["unitid"], errors="coerce").astype("Int64").isin(exclude_unitids)].copy()
    cases["status_priority"] = cases["fresh_discovery_status"].map(
        {
            "source_root_found_no_explicit_years": 0,
            "source_root_not_found": 1,
            "root_candidates_retrieved_but_not_catalog": 2,
            "year_candidates_found": 3,
        }
    ).fillna(9)
    if "fresh_rank" not in cases.columns:
        cases["fresh_rank"] = 0
    cases["fresh_rank"] = pd.to_numeric(cases["fresh_rank"], errors="coerce").fillna(0).astype(int)
    cases = cases.sort_values(
        ["status_priority", "missing_target_year_count", "fresh_rank", "institution_name", "unitid"],
        ascending=[True, False, True, True, True],
    ).drop(columns=["status_priority"])
    if max_cases is not None:
        cases = cases.head(max_cases).copy()
    return cases


def build_ai_year_gap_prompt(case: pd.Series, root_candidates: pd.DataFrame, *, sector: str) -> str:
    import json

    unitid = int(case["unitid"])
    tried = root_candidates.loc[pd.to_numeric(root_candidates.get("unitid", pd.Series(dtype=object)), errors="coerce").eq(unitid)].copy()
    tried = tried.sort_values(["retrieval_status", "candidate_url"]).head(18) if not tried.empty else pd.DataFrame()
    tried_rows = [
        {
            "candidate_url": clean_text(row.get("candidate_url")),
            "retrieval_status": clean_text(row.get("retrieval_status")),
            "http_status": clean_text(row.get("http_status")),
            "page_title": clean_text(row.get("page_title")),
            "catalog_link_count": int(row.get("catalog_link_count", 0) or 0),
            "archive_link_count": int(row.get("archive_link_count", 0) or 0),
        }
        for _, row in tried.iterrows()
    ]
    sector_label = "public" if sector == "public" else "private nonprofit"
    payload = {
        "role": "You are helping an auditable catalog-discovery pipeline find official college and university catalog sources.",
        "task": f"Find official catalog URLs that cover the listed missing panel years for a {sector_label} 4-year institution. Human legacy URLs are intentionally withheld.",
        "institution": {
            "unitid": unitid,
            "name": clean_text(case.get("institution_name")),
            "state": clean_text(case.get("state")),
            "webaddr": clean_text(case.get("webaddr")),
            "first_pass_status": clean_text(case.get("fresh_discovery_status")),
            "current_final_status": clean_text(case.get("final_discovery_status")),
            "preferred_source_root_url": clean_text(case.get("preferred_source_root_url")),
            "observed_candidate_years": clean_text(case.get("observed_candidate_years")),
            "missing_target_years": clean_text(case.get("missing_target_years")),
            "missing_target_year_count": clean_text(case.get("missing_target_year_count")),
        },
        "already_tried": tried_rows,
        "rules": [
            "The missing_target_years are clean panel years with no URL; they are not human legacy source hints.",
            "Do not use or infer any human legacy URL. Treat the institution name, state, homepage, observed years, missing years, and attempted URLs as the only inputs.",
            "For each missing year you can support, return a direct official catalog PDF/HTML/item URL. Do not stop after finding only recent catalogs if older missing years remain.",
            "Search official college pages, registrar/catalog pages, official catalog vendor systems, institutional repositories, library digital collections, and official files linked by the institution.",
            "Explicitly check common historical catalog systems: DigitalCommons/BePress, institutional repositories, DSpace, CONTENTdm, ArchivesSpace, Alma/Ex Libris digital collections, Internet Archive official collections, SmartCatalogIQ, Acalog/Catalogs, CourseLeaf, CollegeSource, Google Drive files linked from official pages, and school library/archive catalog collections.",
            "If a repository collection root is found, enumerate its catalog/bulletin items for the missing years instead of returning only the collection landing page.",
            "If a catalog item URL does not contain a year but the page title or record title names a catalog year, use that title to set covered_start_year and covered_end_year.",
            "Prefer institution-wide undergraduate/general catalogs over graduate, law, medical, seminary, school-specific, policy-only, or handbook-only pages.",
            "Do not invent URLs. Return only URLs you found or URLs directly supported by an official page you found.",
            "Use covered_start_year and covered_end_year as academic catalog range endpoints; a 2018-2019 catalog should be covered_start_year=2018 and covered_end_year=2019.",
            "If the institution has many missing years, return as many direct_catalog_urls as needed for the years you can verify, not just a sample.",
            "Return compact JSON only.",
        ],
        "required_json_schema": {
            "direct_catalog_urls": [
                {
                    "url": "direct catalog PDF or HTML URL",
                    "catalog_year_text": "catalog year/range shown on page, link, title, or URL",
                    "covered_start_year": 2018,
                    "covered_end_year": 2019,
                    "confidence": "low|medium|high",
                    "evidence": "short explanation of why this URL covers one or more missing years",
                }
            ],
            "root_candidates": [
                {
                    "url": "official root/archive/repository URL if direct URLs are not enough",
                    "root_type": "catalog_archive|current_catalog_with_archive_links|registrar_catalog_page|institutional_repository_collection|direct_catalog_pdf|other",
                    "confidence": "low|medium|high",
                    "evidence": "short explanation of why this URL is relevant",
                }
            ],
            "missing_years_not_found": [2001],
            "search_queries_used": ["queries"],
            "stop_reason_if_no_url": "short explanation or empty string",
        },
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def flatten_ai_year_gap_result(case: pd.Series, parsed: dict[str, object], log_record: dict[str, object]) -> dict[str, object]:
    import json

    direct = parsed.get("direct_catalog_urls", []) if isinstance(parsed.get("direct_catalog_urls", []), list) else []
    roots = parsed.get("root_candidates", []) if isinstance(parsed.get("root_candidates", []), list) else []
    return {
        "unitid": int(case["unitid"]),
        "institution_name": clean_text(case.get("institution_name")),
        "fresh_rank": int(case.get("fresh_rank", 0) or 0),
        "first_pass_status": clean_text(case.get("fresh_discovery_status")),
        "final_discovery_status_before_gap": clean_text(case.get("final_discovery_status")),
        "observed_candidate_years": clean_text(case.get("observed_candidate_years")),
        "missing_target_years": clean_text(case.get("missing_target_years")),
        "missing_target_year_count": int(case.get("missing_target_year_count", 0) or 0),
        "api_validation_status": log_record["validation_status"],
        "api_root_candidate_count": len(roots),
        "api_direct_catalog_url_count": len(direct),
        "api_root_candidates_json": json.dumps(roots, sort_keys=True),
        "api_direct_catalog_urls_json": json.dumps(direct, sort_keys=True),
        "api_missing_years_not_found": json.dumps(parsed.get("missing_years_not_found", []), sort_keys=True),
        "api_search_queries_used": json.dumps(parsed.get("search_queries_used", []), sort_keys=True),
        "api_stop_reason_if_no_root": clean_text(parsed.get("stop_reason_if_no_url", "")),
        "api_stop_reason_if_no_url": clean_text(parsed.get("stop_reason_if_no_url", "")),
        "api_prompt_version": log_record["prompt_version"],
        "api_log_call_id": log_record["call_id"],
        "api_prompt_path": log_record["prompt_path"],
        "api_raw_response_path": log_record["raw_response_path"],
        "api_parsed_response_path": log_record["parsed_response_path"],
        "api_error_message": log_record["error_message"],
    }


def run_ai_year_gap_triage_for_sector(
    repo_root: Path,
    *,
    sector: str,
    config: AIConfig,
    status: pd.DataFrame,
    panel: pd.DataFrame,
    root_candidates: pd.DataFrame,
    max_cases: int | None,
    exclude_unitids: set[int] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    import json
    import uuid

    cases = build_ai_year_gap_cases(status, panel, max_cases=max_cases, exclude_unitids=exclude_unitids)
    if config.live_enabled and len(cases) > config.workflow.max_requests_per_run:
        raise ValueError(
            f"selected AI year-gap cases={len(cases)} exceeds workflow.max_requests_per_run={config.workflow.max_requests_per_run}"
        )
    config.workflow.log_dir.mkdir(parents=True, exist_ok=True)
    config.workflow.raw_response_dir.mkdir(parents=True, exist_ok=True)
    config.workflow.parsed_response_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, object]] = []
    stream_id = stream_id_for_sector(sector)
    created_at = utc_now()
    for call_num, (_, case) in enumerate(cases.iterrows(), 1):
        call_id = f"{stream_id}_{AI_YEAR_GAP_TASK_TYPE}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"
        prompt = build_ai_year_gap_prompt(case, root_candidates, sector=sector)
        prompt_path = config.workflow.parsed_response_dir / f"{call_id}_prompt.json"
        prompt_path.write_text(prompt, encoding="utf-8")
        parsed: dict[str, object] = {}
        raw_path = parsed_path = None
        validation_status = "dry_run"
        error_message = ""
        print(f"[ai-year-gap] {sector} {call_num}/{len(cases)} unitid={int(case['unitid'])} {clean_text(case['institution_name'])}", flush=True)
        if config.live_enabled:
            validation_status = "not_attempted"
            try:
                parsed, raw_path, parsed_path = call_openai(config, prompt, call_id)
                validation_status = "parsed"
            except Exception as exc:  # pragma: no cover - remote failures vary.
                validation_status = "api_error"
                error_message = type(exc).__name__ + ": " + safe_error_message(str(exc), config)
                raw_path = config.workflow.raw_response_dir / f"{call_id}.json"
                raw_path.write_text(json.dumps({"error_message": error_message}, indent=2), encoding="utf-8")
        log_record = {
            "call_id": call_id,
            "task_type": AI_YEAR_GAP_TASK_TYPE,
            "unitid": int(case["unitid"]),
            "institution_name": clean_text(case["institution_name"]),
            "model": config.openai.model,
            "prompt_version": AI_YEAR_GAP_PROMPT_VERSION,
            "schema_version": config.prompts.schema_version,
            "input_hash": sha256_text(prompt),
            "output_hash": sha256_text(json.dumps(parsed, sort_keys=True)) if parsed else "",
            "prompt_path": str(prompt_path),
            "raw_response_path": str(raw_path) if raw_path else "",
            "parsed_response_path": str(parsed_path) if parsed_path else "",
            "validation_status": validation_status,
            "error_message": error_message,
            "created_at": created_at,
        }
        with (config.workflow.log_dir / "api_call_log.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(log_record, sort_keys=True) + "\n")
        rows.append(flatten_ai_year_gap_result(case, parsed, log_record))
    return cases, pd.DataFrame(rows)


def ai_log_prompt_versions(log_dir: Path, *, task_type: str) -> dict[str, str]:
    path = log_dir / "api_call_log.jsonl"
    if not path.exists():
        return {}
    versions: dict[str, str] = {}
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if clean_text(record.get("task_type")) != task_type:
                continue
            call_id = clean_text(record.get("call_id"))
            if call_id:
                versions[call_id] = clean_text(record.get("prompt_version"))
    return versions


def non_retryable_ai_triage(ai_triage: pd.DataFrame) -> pd.DataFrame:
    if ai_triage.empty or "api_validation_status" not in ai_triage.columns:
        return ai_triage
    status = ai_triage["api_validation_status"].fillna("").map(clean_text)
    return ai_triage.loc[~status.eq("api_error")].copy()


def non_retryable_ai_attempted_unitids(ai_triage: pd.DataFrame) -> set[int]:
    triage = non_retryable_ai_triage(ai_triage)
    if triage.empty or "unitid" not in triage.columns:
        return set()
    return set(pd.to_numeric(triage["unitid"], errors="coerce").dropna().astype(int).tolist())


def ai_triage_pending_status_materialization(ai_triage: pd.DataFrame, status: pd.DataFrame) -> pd.DataFrame:
    if ai_triage.empty or "unitid" not in ai_triage.columns:
        return pd.DataFrame()
    triage = non_retryable_ai_triage(ai_triage)
    if triage.empty:
        return pd.DataFrame()
    if status.empty or "unitid" not in status.columns or "api_validation_status" not in status.columns:
        return triage.copy()
    materialized = status.loc[status["api_validation_status"].fillna("").map(clean_text).ne(""), "unitid"]
    materialized_unitids = set(pd.to_numeric(materialized, errors="coerce").dropna().astype(int).tolist())
    triage_unitids = pd.to_numeric(triage["unitid"], errors="coerce")
    return triage.loc[~triage_unitids.isin(materialized_unitids)].copy()


def ai_triage_for_unitids(ai_triage: pd.DataFrame, unitids: set[int]) -> pd.DataFrame:
    if ai_triage.empty or not unitids or "unitid" not in ai_triage.columns:
        return pd.DataFrame()
    triage = non_retryable_ai_triage(ai_triage)
    triage_unitids = pd.to_numeric(triage["unitid"], errors="coerce")
    return triage.loc[triage_unitids.isin(unitids)].copy()


def current_prompt_attempted_unitids(ai_triage: pd.DataFrame, *, config: AIConfig) -> set[int]:
    if ai_triage.empty or "unitid" not in ai_triage.columns:
        return set()
    triage = non_retryable_ai_triage(ai_triage)
    if "api_prompt_version" not in triage.columns:
        triage["api_prompt_version"] = ""
    triage["api_prompt_version"] = triage["api_prompt_version"].fillna("").map(clean_text)
    missing_version = triage["api_prompt_version"].eq("")
    if missing_version.any() and "api_log_call_id" in triage.columns:
        versions = ai_log_prompt_versions(config.workflow.log_dir, task_type=AI_YEAR_GAP_TASK_TYPE)
        triage.loc[missing_version, "api_prompt_version"] = triage.loc[missing_version, "api_log_call_id"].map(
            lambda call_id: versions.get(clean_text(call_id), "")
        )
    attempted = triage.loc[triage["api_prompt_version"].eq(AI_YEAR_GAP_PROMPT_VERSION), "unitid"]
    return set(pd.to_numeric(attempted, errors="coerce").dropna().astype(int).tolist())


def year_range_from_ai_direct_item(item: dict[str, object]) -> tuple[int, int] | None:
    start_value = pd.to_numeric(pd.Series([item.get("covered_start_year")]), errors="coerce").iloc[0]
    end_value = pd.to_numeric(pd.Series([item.get("covered_end_year")]), errors="coerce").iloc[0]
    if not pd.isna(start_value):
        start = int(start_value)
        end = int(end_value) if not pd.isna(end_value) else start + 1
        if end <= start:
            end = start + 1
        if 1800 <= start <= 2030 and start < end <= 2035 and end > TARGET_START_YEAR and start <= TARGET_END_YEAR:
            return start, end
    evidence = f"{item.get('catalog_year_text', '')} {item.get('url', '')} {item.get('evidence', '')}"
    return catalog_year_range(evidence)


def direct_retrieval_timeout_result(url: str, *, timeout_seconds: int) -> dict[str, object]:
    return {
        "retrieval_status": "timeout",
        "http_status": "",
        "final_url": url,
        "content_type": "",
        "page_title": "",
        "error_type": "direct_retrieval_timeout",
        "error_message": f"AI direct URL retrieval exceeded {timeout_seconds} seconds",
    }


def direct_retrieval_error_result(url: str, *, error_type: str, error_message: str) -> dict[str, object]:
    return {
        "retrieval_status": "error",
        "http_status": "",
        "final_url": url,
        "content_type": "",
        "page_title": "",
        "error_type": error_type,
        "error_message": error_message,
    }


def retrieve_ai_direct_url_worker(
    result_queue: object,
    url: str,
    timeout_seconds: int,
    max_bytes: int,
) -> None:
    try:
        result_queue.put(retrieve_url(url, timeout_seconds=timeout_seconds, max_bytes=max_bytes))
    except Exception as exc:
        result_queue.put(
            direct_retrieval_error_result(url, error_type=type(exc).__name__, error_message=safe_error_message(exc))
        )


def retrieve_ai_direct_url(url: str, *, timeout_seconds: int, max_bytes: int) -> dict[str, object]:
    if urlparse(url).netloc.lower() == "drive.google.com":
        return retrieve_url(url, timeout_seconds=timeout_seconds, max_bytes=max_bytes)
    if getattr(retrieve_url, "__module__", "") != "course_policy.catalog_retrieval":
        return retrieve_url(url, timeout_seconds=timeout_seconds, max_bytes=max_bytes)
    budget_seconds = max(1, timeout_seconds + 2)
    start_method = "spawn" if "spawn" in mp.get_all_start_methods() else mp.get_start_method()
    context = mp.get_context(start_method)
    result_queue = context.Queue(maxsize=1)
    process = context.Process(
        target=retrieve_ai_direct_url_worker,
        args=(result_queue, url, timeout_seconds, max_bytes),
    )
    process.daemon = True
    process.start()
    process.join(budget_seconds)
    try:
        if process.is_alive():
            process.terminate()
            process.join(1)
            return direct_retrieval_timeout_result(url, timeout_seconds=budget_seconds)
        try:
            return result_queue.get_nowait()
        except queue_lib.Empty:
            return direct_retrieval_error_result(
                url,
                error_type="direct_retrieval_worker_empty",
                error_message=f"AI direct URL worker exited with code {process.exitcode}",
            )
    finally:
        result_queue.close()
        result_queue.join_thread()


ACALOG_MEDIA_BUCKET_PRIORITY = ["37", "44", "21", "33", "31", "35", "27", "14", "15", "2"]


def acalog_media_bucket_variants(url: str, *, max_bucket: int = 80) -> list[str]:
    parsed = urlparse(clean_text(url))
    parts = parsed.path.split("/")
    try:
        mime_index = next(
            index
            for index in range(len(parts) - 3)
            if parts[index] == "mime" and parts[index + 1] == "media"
        )
    except StopIteration:
        return [clean_text(url)] if clean_text(url) else []
    bucket = parts[mime_index + 2]
    media_id = parts[mime_index + 3]
    if not bucket.isdigit() or not media_id.isdigit():
        return [clean_text(url)]
    bucket_values = [bucket] + ACALOG_MEDIA_BUCKET_PRIORITY + [str(value) for value in range(1, max_bucket + 1)]
    variants: list[str] = []
    for bucket_value in dict.fromkeys(bucket_values):
        new_parts = list(parts)
        new_parts[mime_index + 2] = bucket_value
        append_unique_url(variants, urlunparse(parsed._replace(path="/".join(new_parts))))
    return variants


def retrieve_ai_direct_url_with_variants(url: str, *, timeout_seconds: int, max_bytes: int) -> tuple[str, dict[str, object]]:
    last_url = clean_text(url)
    last_result: dict[str, object] = {}
    for index, candidate_url in enumerate(acalog_media_bucket_variants(url)):
        last_url = candidate_url
        try:
            result = retrieve_url(
                candidate_url,
                timeout_seconds=timeout_seconds if index == 0 else min(timeout_seconds, 2),
                max_bytes=max_bytes,
            )
        except Exception as exc:
            result = direct_retrieval_error_result(
                candidate_url,
                error_type=type(exc).__name__,
                error_message=safe_error_message(exc),
            )
        last_result = result
        if clean_text(result.get("retrieval_status")) in RETRIEVED_STATUSES:
            return candidate_url, result
    return last_url, last_result


def ai_year_gap_direct_candidates(ai_triage: pd.DataFrame, *, timeout_seconds: int) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    if ai_triage.empty:
        return pd.DataFrame()
    direct_total = 0
    for _, triage in ai_triage.iterrows():
        for item in parse_json_list(triage.get("api_direct_catalog_urls_json")):
            if clean_text(item.get("url")) and year_range_from_ai_direct_item(item):
                direct_total += 1
    direct_index = 0
    for _, triage in ai_triage.iterrows():
        missing_years = set(parse_years_list(triage.get("missing_target_years")))
        for item in parse_json_list(triage.get("api_direct_catalog_urls_json")):
            url = clean_text(item.get("url"))
            year_range = year_range_from_ai_direct_item(item)
            if not url or not year_range:
                continue
            direct_index += 1
            print(
                f"[ai-year-gap-direct] {direct_index}/{direct_total} unitid={triage.get('unitid')} {triage.get('institution_name')}",
                flush=True,
            )
            evidence = f"{item.get('catalog_year_text', '')} {url} {item.get('evidence', '')}"
            try:
                retrieved_url, result = retrieve_ai_direct_url_with_variants(
                    url,
                    timeout_seconds=timeout_seconds,
                    max_bytes=250_000,
                )
            except Exception:
                continue
            if result["retrieval_status"] not in RETRIEVED_STATUSES:
                continue
            candidate_evidence_text = clean_text(item.get("evidence"))
            if retrieved_url != url:
                candidate_evidence_text = (
                    f"{candidate_evidence_text}; retrieved Modern Campus media bucket variant from API URL {url}"
                ).strip("; ")
            start, end = year_range
            for target_year in academic_years_from_range(start, end):
                if missing_years and target_year not in missing_years:
                    continue
                rows.append(
                    {
                        "batch3_rank": 0,
                        "unitid": int(triage["unitid"]),
                        "institution_name": clean_text(triage["institution_name"]),
                        "target_year": target_year,
                        "catalog_year_start": start,
                        "catalog_year_end": end,
                        "academic_year_rule": "AY is the catalog start year; multi-year catalogs cover each start year through end-1.",
                        "candidate_url": retrieved_url,
                        "candidate_link_text": clean_text(item.get("catalog_year_text")) or "AI year-gap direct catalog URL",
                        "candidate_evidence_text": candidate_evidence_text,
                        "candidate_evidence_source": "ai_year_gap_direct_catalog_url",
                        "archive_url": "",
                        "archive_page_title": "",
                        "candidate_scope": "undergraduate_or_university_catalog",
                        "validation_status": "ai_year_gap_direct_catalog_year",
                        "candidate_priority": candidate_priority(evidence),
                        "candidate_source_method": "ai_year_gap_direct_catalog_url",
                        "candidate_retrieval_status": result["retrieval_status"],
                        "candidate_http_status": result["http_status"],
                        "candidate_page_title": result["page_title"],
                        "created_at": utc_now(),
                    }
                )
    return pd.DataFrame(rows)


def write_ai_year_gap_summary(
    path: Path,
    *,
    sector: str,
    outputs: AIYearGapOutputs,
    final_status: pd.DataFrame,
    ai_triage: pd.DataFrame,
    new_cases_attempted: int,
    priority_case_count: int,
) -> None:
    parsed = int(ai_triage["api_validation_status"].eq("parsed").sum()) if not ai_triage.empty else 0
    dry = int(ai_triage["api_validation_status"].eq("dry_run").sum()) if not ai_triage.empty else 0
    errors = int(ai_triage["api_validation_status"].eq("api_error").sum()) if not ai_triage.empty else 0
    added_years = int(final_status["ai_added_years"].sum()) if not final_status.empty and "ai_added_years" in final_status else 0
    recovered_institutions = int(final_status["ai_added_years"].gt(0).sum()) if not final_status.empty and "ai_added_years" in final_status else 0
    lines = [
        f"# {sector.title()} Clean No-Legacy AI Year-Gap Rescue",
        "",
        f"Generated at: {utc_now()}",
        "",
        "Scope: AI/web-search rescue for exact clean panel year gaps. Human legacy truth remains withheld from prompts.",
        "",
        "## Bottom Line",
        "",
        f"- New API cases attempted in latest run: {new_cases_attempted}",
        f"- Cumulative AI year-gap cases attempted: {len(ai_triage)}",
        f"- Total current clean-panel gap cases in scope: {priority_case_count}",
        f"- Unattempted cases remaining: {max(priority_case_count - len(ai_triage), 0)}",
        f"- Parsed live API responses: {parsed}",
        f"- Dry-run prompts: {dry}",
        f"- API errors: {errors}",
        f"- Institutions with year-gap-added candidate years: {recovered_institutions}",
        f"- Candidate institution-year URLs added after year-gap search: {added_years}",
        "",
        "## Outputs",
        "",
    ]
    for label, output_path in outputs.__dict__.items():
        lines.append(f"- {label}: `{output_path}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_ai_year_gap_rescue_for_sector(
    repo_root: Path,
    sector: str,
    *,
    config_path: Path | None = None,
    max_api_cases: int | None = None,
    timeout_seconds: int = 4,
    max_archive_pages_per_institution: int = 12,
    max_workers: int = 12,
    rerun_existing_cases: bool = False,
    rematerialize_unitids: set[int] | None = None,
) -> AIYearGapOutputs:
    repo_root = repo_root.resolve()
    config = load_ai_config(config_path, root=repo_root)
    if max_api_cases is None:
        max_api_cases = config.workflow.max_requests_per_run if config.live_enabled else 0
    if config.live_enabled and max_api_cases > config.workflow.max_requests_per_run:
        raise ValueError(
            f"max_api_cases={max_api_cases} exceeds workflow.max_requests_per_run={config.workflow.max_requests_per_run}"
        )
    first = stream_outputs(repo_root, sector)
    first_status = read_checkpoint(first.institution_status_csv)
    case_status_path = ai_rescue_outputs(repo_root, sector).ai_rescue_status_csv
    case_status = read_checkpoint(case_status_path) if case_status_path.exists() else first_status
    current_panel = current_clean_panel_for_gap_search(repo_root, sector)
    root_candidates = read_checkpoint(first.root_candidates_csv)
    outputs = ai_year_gap_outputs(repo_root, sector)
    for output_path in outputs.__dict__.values():
        output_path.parent.mkdir(parents=True, exist_ok=True)

    existing_cases = read_checkpoint(outputs.ai_year_gap_cases_csv)
    existing_triage = read_checkpoint(outputs.ai_year_gap_triage_csv)
    existing_roots = read_checkpoint(outputs.ai_year_gap_verified_roots_csv)
    existing_archive_pages = read_checkpoint(outputs.ai_year_gap_archive_pages_csv)
    existing_candidates = read_checkpoint(outputs.ai_year_gap_candidates_csv)
    if rerun_existing_cases:
        already_attempted = current_prompt_attempted_unitids(existing_triage, config=config)
    else:
        already_attempted = non_retryable_ai_attempted_unitids(existing_triage)
    priority_case_count = len(build_ai_year_gap_cases(case_status, current_panel, max_cases=None))
    new_cases, new_triage = run_ai_year_gap_triage_for_sector(
        repo_root,
        sector=sector,
        config=config,
        status=case_status,
        panel=current_panel,
        root_candidates=root_candidates,
        max_cases=max_api_cases,
        exclude_unitids=already_attempted,
    )
    checkpoint_cases = concat_frames([existing_cases, new_cases])
    checkpoint_triage = concat_frames([existing_triage, new_triage])
    if not checkpoint_cases.empty and "unitid" in checkpoint_cases.columns:
        checkpoint_cases = checkpoint_cases.drop_duplicates("unitid", keep="last")
    if not checkpoint_triage.empty and "unitid" in checkpoint_triage.columns:
        checkpoint_triage = checkpoint_triage.drop_duplicates("unitid", keep="last")
    if "api_stop_reason_if_no_root" not in checkpoint_triage.columns and "api_stop_reason_if_no_url" in checkpoint_triage.columns:
        checkpoint_triage["api_stop_reason_if_no_root"] = checkpoint_triage["api_stop_reason_if_no_url"]
    checkpoint_cases.to_csv(outputs.ai_year_gap_cases_csv, index=False)
    checkpoint_triage.to_csv(outputs.ai_year_gap_triage_csv, index=False)

    if rematerialize_unitids:
        pending_triage = ai_triage_for_unitids(checkpoint_triage, rematerialize_unitids)
    else:
        pending_triage = ai_triage_pending_status_materialization(
            checkpoint_triage,
            read_checkpoint(outputs.ai_year_gap_status_csv),
        )
    triage_to_materialize = concat_frames([new_triage, pending_triage])
    if not triage_to_materialize.empty and "unitid" in triage_to_materialize.columns:
        triage_to_materialize = triage_to_materialize.drop_duplicates("unitid", keep="last")
    new_roots = verify_ai_roots(triage_to_materialize, timeout_seconds=timeout_seconds) if not triage_to_materialize.empty else pd.DataFrame()
    decisions = decisions_from_ai_roots(new_roots)
    new_archive_pages, result_by_url = (
        build_archive_pages_concurrent(
            repo_root,
            decisions,
            timeout_seconds=timeout_seconds,
            max_archive_pages_per_institution=max_archive_pages_per_institution,
            max_workers=max_workers,
            source_slug=stream_id_for_sector(sector).replace("_", "-") + "-year-gap",
        )
        if not decisions.empty
        else (pd.DataFrame(), {})
    )
    new_year_candidates = build_year_candidates(new_archive_pages, result_by_url) if not new_archive_pages.empty else pd.DataFrame()
    if not new_year_candidates.empty:
        new_year_candidates["candidate_source_method"] = "ai_year_gap_verified_root_archive"
    new_direct_candidates = ai_year_gap_direct_candidates(triage_to_materialize, timeout_seconds=timeout_seconds)
    new_added_candidates = concat_frames([new_year_candidates, new_direct_candidates])

    ai_cases = concat_frames([existing_cases, new_cases])
    ai_triage = concat_frames([existing_triage, new_triage])
    ai_roots = concat_frames([existing_roots, new_roots])
    ai_archive_pages = concat_frames([existing_archive_pages, new_archive_pages])
    ai_added_candidates = concat_frames([existing_candidates, new_added_candidates])
    if not ai_cases.empty and "unitid" in ai_cases.columns:
        ai_cases = ai_cases.drop_duplicates("unitid", keep="last")
    if not ai_triage.empty and "unitid" in ai_triage.columns:
        ai_triage = ai_triage.drop_duplicates("unitid", keep="last")
    if "api_stop_reason_if_no_root" not in ai_triage.columns and "api_stop_reason_if_no_url" in ai_triage.columns:
        ai_triage["api_stop_reason_if_no_root"] = ai_triage["api_stop_reason_if_no_url"]
    if not ai_roots.empty and {"unitid", "root_url"}.issubset(ai_roots.columns):
        ai_roots = ai_roots.drop_duplicates(["unitid", "root_url"], keep="last")
    if not ai_archive_pages.empty and {"unitid", "archive_url"}.issubset(ai_archive_pages.columns):
        ai_archive_pages = ai_archive_pages.drop_duplicates(["unitid", "archive_url"], keep="last")
    if not ai_added_candidates.empty and {"unitid", "target_year", "candidate_url"}.issubset(ai_added_candidates.columns):
        ai_added_candidates = ai_added_candidates.drop_duplicates(["unitid", "target_year", "candidate_url"], keep="last")

    all_candidates = filter_candidate_rows(ai_added_candidates) if not ai_added_candidates.empty else ai_added_candidates
    final_panel = merge_final_panel(current_panel, all_candidates)
    final_status = build_final_status(first_status, final_panel, ai_triage, ai_roots)

    ai_cases.to_csv(outputs.ai_year_gap_cases_csv, index=False)
    ai_triage.to_csv(outputs.ai_year_gap_triage_csv, index=False)
    ai_roots.to_csv(outputs.ai_year_gap_verified_roots_csv, index=False)
    ai_archive_pages.to_csv(outputs.ai_year_gap_archive_pages_csv, index=False)
    ai_added_candidates.to_csv(outputs.ai_year_gap_candidates_csv, index=False)
    final_panel.to_csv(outputs.ai_year_gap_year_panel_csv, index=False)
    final_status.to_csv(outputs.ai_year_gap_status_csv, index=False)
    write_workbook(
        outputs.workbook,
        {
            "start_here": final_status,
            "ai_year_gap_triage": ai_triage,
            "ai_year_gap_verified_roots": ai_roots,
            "ai_year_gap_candidates": ai_added_candidates,
            "ai_year_gap_year_panel": final_panel,
            "current_panel_before_gap": current_panel,
        },
    )
    write_ai_year_gap_summary(
        outputs.summary_md,
        sector=sector,
        outputs=outputs,
        final_status=final_status,
        ai_triage=ai_triage,
        new_cases_attempted=len(new_triage),
        priority_case_count=priority_case_count,
    )
    return outputs


def parse_url_year_range_match(match: object, *, source_year: int) -> tuple[int, int, str, str] | None:
    groups = match.groups()
    start_text = groups[0]
    sep = groups[1] if len(groups) > 1 else ""
    end_text = groups[2] if len(groups) > 2 else ""
    if len(start_text) == 2:
        century = source_year // 100 * 100
        start = century + int(start_text)
        if start > source_year + 20:
            start -= 100
    else:
        start = int(start_text)
    if not end_text:
        return None
    end = int(end_text) if len(end_text) == 4 else (start // 100 * 100) + int(end_text)
    if end <= start:
        end += 100
    if start != source_year:
        return None
    if not (1990 <= start <= 2030 and start < end <= 2035):
        return None
    return start, end, sep, end_text


def parse_compact_url_year_range_match(match: object, *, source_year: int) -> tuple[int, int, str, str] | None:
    text = clean_text(match.group(1))
    end_text = ""
    try:
        if getattr(match, "lastindex", 0) and match.lastindex >= 2:
            end_text = clean_text(match.group(2))
    except IndexError:
        end_text = ""
    if end_text:
        start_two = text
        end_two = end_text
    elif len(text) == 4:
        start_two = text[:2]
        end_two = text[2:]
    else:
        return None
    if not (len(start_two) == 2 and start_two.isdigit() and len(end_two) == 2 and end_two.isdigit()):
        return None
    century = source_year // 100 * 100
    start = century + int(start_two)
    if start > source_year + 20:
        start -= 100
    end = (start // 100 * 100) + int(end_two)
    if end <= start:
        end += 100
    if start != source_year:
        return None
    if not (1990 <= start <= 2030 and start < end <= 2035):
        return None
    return start, end, "", end_two


def parse_compact_full_url_year_range_match(match: object, *, source_year: int) -> tuple[int, int, str, str] | None:
    start = int(match.group(1))
    end = int(match.group(2))
    if start != source_year:
        return None
    if not (1990 <= start <= 2030 and start < end <= 2035):
        return None
    return start, end, "", match.group(2)


def append_unique_url(rows: list[str], value: str) -> None:
    value = clean_text(value)
    if value and value not in rows:
        rows.append(value)


def replacement_year_range_specs(
    *,
    source_start: int,
    source_end: int,
    target_year: int,
) -> list[tuple[int, int]]:
    duration = max(1, min(6, source_end - source_start))
    specs = [(target_year, target_year + duration), (target_year, target_year + 1), (target_year, target_year + 2)]
    if target_year > TARGET_START_YEAR:
        specs.append((target_year - 1, target_year + 1))
    if target_year > TARGET_START_YEAR + 1:
        specs.append((target_year - 2, target_year + 1))
    out: list[tuple[int, int]] = []
    for start, end in specs:
        if 1990 <= start <= 2030 and start < end <= 2035 and (start, end) not in out:
            out.append((start, end))
    return out


def formatted_year_range(start: int, end: int, *, sep: str, original_start: str, original_end: str) -> str:
    start_text = f"{start % 100:02d}" if len(original_start) == 2 else str(start)
    end_text = str(end) if len(original_end) == 4 else f"{end % 100:02d}"
    return f"{start_text}{sep}{end_text}"


def catalog_archive_named_catalog_variants(source_url: str, *, target_year: int) -> list[str]:
    parsed = urlparse(clean_text(source_url))
    path = parsed.path
    lowered = path.lower()
    if "catalog_archive" not in lowered or "catalog" not in lowered:
        return []
    directory = path.rsplit("/", 1)[0]
    names = [
        f"{target_year}-{target_year + 1}%20Catalog.pdf",
        f"{target_year}-{target_year + 1} Catalog.pdf",
        f"{target_year}-{(target_year + 1) % 100:02d}-Catalog.pdf",
        f"{target_year}-{(target_year + 1) % 100:02d}-UG-GR-Catalog.pdf",
    ]
    out: list[str] = []
    for name in names:
        new_path = f"{directory}/{name}"
        append_unique_url(out, urlunparse(parsed._replace(path=new_path)))
    return out


def wordpress_upload_date_variants(source_url: str, *, target_year: int) -> list[str]:
    parsed = urlparse(clean_text(source_url))
    path = parsed.path
    if "/wp-content/uploads/" not in path:
        return []
    parts = path.split("/")
    out: list[str] = []
    preferred_months = ["08", "09", "07", "02", "01", "10", "11", "12", "03", "04", "05", "06"]
    for index in range(len(parts) - 1):
        if parts[index] != "uploads":
            continue
        # WordPress multisite paths can be uploads/sites/<id>/<yyyy>/<mm>/...
        year_index = index + 1
        if year_index < len(parts) and parts[year_index] == "sites" and year_index + 2 < len(parts):
            year_index += 2
        if year_index + 1 >= len(parts):
            continue
        if not re.fullmatch(r"(?:19|20)\d{2}", parts[year_index]) or not re.fullmatch(r"\d{2}", parts[year_index + 1]):
            continue
        for upload_year in range(target_year, min(target_year + 4, 2035)):
            for month in preferred_months:
                new_parts = list(parts)
                new_parts[year_index] = str(upload_year)
                new_parts[year_index + 1] = month
                append_unique_url(out, urlunparse(parsed._replace(path="/".join(new_parts))))
        break
    return out


def acalog_media_sibling_variants(source_url: str, *, source_year: int, target_year: int) -> list[str]:
    parsed = urlparse(clean_text(source_url))
    parts = parsed.path.split("/")
    try:
        mime_index = next(
            index
            for index in range(len(parts) - 4)
            if parts[index] == "mime" and parts[index + 1] == "media"
        )
    except StopIteration:
        return []
    bucket = parts[mime_index + 2]
    media_id_text = parts[mime_index + 3]
    filename = parts[mime_index + 4]
    if not bucket.isdigit() or not media_id_text.isdigit():
        return []
    range_match = re.search(
        r"(?<!\d)((?:19|20)\d{2}|\d{2})([-_])((?:19|20)\d{2}|\d{2})(?!\d)",
        filename,
        flags=re.IGNORECASE,
    )
    compact_match = None if range_match else re.search(r"(?<!\d)(\d{2})(\d{2})(?!\d)", filename)
    if not range_match and not compact_match:
        return []
    if range_match:
        parsed_range = parse_url_year_range_match(range_match, source_year=source_year)
        if parsed_range is None:
            return []
        source_start, source_end, sep, original_end = parsed_range
        original_start = range_match.group(1)
    else:
        parsed_range = parse_compact_url_year_range_match(compact_match, source_year=source_year)
        if parsed_range is None:
            return []
        source_start, source_end, sep, original_end = parsed_range
        original_start = compact_match.group(1)[:2]

    media_id = int(media_id_text)
    bucket_options = [bucket]
    host = parsed.netloc.lower()
    if host.startswith(("catalog.", "catalogs.")):
        bucket_options.extend(["14", "15"])

    replacement_filenames: list[str] = []
    for start, end in replacement_year_range_specs(
        source_start=source_start,
        source_end=source_end,
        target_year=target_year,
    ):
        if range_match:
            year_text = formatted_year_range(start, end, sep=sep, original_start=original_start, original_end=original_end)
            candidate_filename = filename[: range_match.start()] + year_text + filename[range_match.end() :]
        else:
            year_text = f"{start % 100:02d}{end % 100:02d}"
            candidate_filename = filename[: compact_match.start()] + year_text + filename[compact_match.end() :]
        if candidate_filename not in replacement_filenames:
            replacement_filenames.append(candidate_filename)

    out: list[str] = []
    year_delta = source_start - target_year
    media_offsets = [0, year_delta, year_delta - 1, year_delta + 1]
    media_offsets.extend(range(-100, 21))
    for candidate_filename in replacement_filenames:
        for candidate_bucket in dict.fromkeys(bucket_options):
            for offset in dict.fromkeys(media_offsets):
                candidate_media_id = media_id + int(offset)
                if candidate_media_id <= 0:
                    continue
                new_parts = list(parts)
                new_parts[mime_index + 2] = candidate_bucket
                new_parts[mime_index + 3] = str(candidate_media_id)
                new_parts[mime_index + 4] = candidate_filename
                append_unique_url(out, urlunparse(parsed._replace(path="/".join(new_parts))))
    return out


def inferred_year_url_replacements(source_url: str, *, source_year: int, target_year: int) -> list[str]:
    url = clean_text(source_url)
    if not url or source_year == target_year:
        return []
    catalogish = re.search(
        r"(catalog|catalogue|bulletin|undergrad|ug[_-]?cat|course[_-]?catalog|academic[_-]?catalog|[\\W_]ug[\\W_]|wp-content/uploads)",
        url,
        re.IGNORECASE,
    )
    if not catalogish:
        return []
    patterns = [
        (
            re.compile(r"(?<!\d)((?:19|20)\d{2})([-_/]|%20|%2D)((?:19|20)\d{2})(?!\d)", flags=re.IGNORECASE),
            parse_url_year_range_match,
        ),
        (
            re.compile(r"(?<!\d)((?:19|20)\d{2})([-_/]|%20|%2D)(\d{2})(?!\d)", flags=re.IGNORECASE),
            parse_url_year_range_match,
        ),
        (
            re.compile(r"(?<!\d)(\d{2})([-_/])(\d{2})(?!\d)", flags=re.IGNORECASE),
            parse_url_year_range_match,
        ),
        (
            re.compile(r"(?<!\d)((?:19|20)\d{2})((?:19|20)\d{2})(?!\d)", flags=re.IGNORECASE),
            parse_compact_full_url_year_range_match,
        ),
        (
            re.compile(r"(?<!\d)(\d{4})(?=(?:[_-]?(?:catalog|catalogue|bulletin|undergrad|ug|academic))|(?:[_-]?cat)|\.)", flags=re.IGNORECASE),
            parse_compact_url_year_range_match,
        ),
    ]
    out: list[str] = []
    for pattern, parser in patterns:
        for match in pattern.finditer(url):
            parsed = parser(match, source_year=source_year)
            if parsed is None:
                continue
            start, end, sep, original_end = parsed
            target_end = target_year + max(1, min(6, end - start))
            if len(match.group(1)) == 2:
                start_text = f"{target_year % 100:02d}"
            elif sep == "" and len(match.group(1)) == 4 and len(original_end) == 2:
                start_text = f"{target_year % 100:02d}"
            else:
                start_text = str(target_year)
            end_text = str(target_end) if len(original_end) == 4 else f"{target_end % 100:02d}"
            candidate = url[: match.start()] + start_text + sep + end_text + url[match.end() :]
            if candidate != url:
                append_unique_url(out, candidate)
                for variant in wordpress_upload_date_variants(candidate, target_year=target_year):
                    append_unique_url(out, variant)
    term_year_pattern = re.compile(
        r"(?<!\d)((?:19|20)\d{2})(?=(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec|spring|summer|fall|winter)(?:[/_.-]|$))",
        flags=re.IGNORECASE,
    )
    for match in term_year_pattern.finditer(url):
        if int(match.group(1)) != source_year:
            continue
        candidate = url[: match.start()] + str(target_year) + url[match.end() :]
        if candidate != url:
            append_unique_url(out, candidate)
    catalog_id_pattern = re.compile(r"(?<!\d)((?:19|20)\d{2})([0-9])(?=(?:[/#?&]|$))", flags=re.IGNORECASE)
    for match in catalog_id_pattern.finditer(url):
        if int(match.group(1)) not in {source_year, source_year + 1}:
            continue
        candidate = url[: match.start()] + str(target_year) + match.group(2) + url[match.end() :]
        if candidate != url:
            append_unique_url(out, candidate)
    for candidate in catalog_archive_named_catalog_variants(url, target_year=target_year):
        append_unique_url(out, candidate)
    for candidate in acalog_media_sibling_variants(url, source_year=source_year, target_year=target_year):
        append_unique_url(out, candidate)
    for candidate in same_directory_year_range_pdf_variants(url, source_year=source_year, target_year=target_year):
        append_unique_url(out, candidate)
    return out


def same_directory_year_range_pdf_variants(source_url: str, *, source_year: int, target_year: int) -> list[str]:
    """Try simple year-range PDF names beside a current-run catalog PDF."""
    url = clean_text(source_url)
    parsed = urlparse(url)
    path = parsed.path
    if not parsed.netloc or not path.lower().endswith(".pdf"):
        return []
    filename = unquote(path.rsplit("/", 1)[-1])
    lowered = filename.lower()
    if not re.search(r"(catalog|catalogue|bulletin|undergrad|academic)", lowered):
        return []
    if not re.search(r"(?<!\d)(?:19|20)\d{2}[-_](?:(?:19|20)\d{2}|\d{2})(?!\d)", filename):
        return []
    source_range = catalog_year_range(filename) or normalized_year_range(filename)
    if not source_range or source_range[0] != source_year:
        return []
    directory = path.rsplit("/", 1)[0] + "/"
    yy_next = f"{(target_year + 1) % 100:02d}"
    names = [
        f"{target_year}-{target_year + 1}.pdf",
        f"{target_year}-{yy_next}.pdf",
        f"{target_year}_{target_year + 1}.pdf",
        f"{target_year}_{yy_next}.pdf",
    ]
    if "undergrad" in lowered:
        names.extend(
            [
                f"{target_year}-{target_year + 1}_Undergraduate_Catalog.pdf",
                f"{target_year}-{yy_next}_Undergraduate_Catalog.pdf",
                f"{target_year}_{target_year + 1}_Undergraduate_Catalog.pdf",
                f"{target_year}_{yy_next}_Undergraduate_Catalog.pdf",
            ]
        )
    if "academic" in lowered or "catalog" in lowered:
        names.extend(
            [
                f"{target_year}-{target_year + 1}_Academic_Catalog.pdf",
                f"{target_year}-{yy_next}_Academic_Catalog.pdf",
                f"{target_year}-{target_year + 1}_Catalog.pdf",
                f"{target_year}-{yy_next}_Catalog.pdf",
            ]
        )
    out: list[str] = []
    for name in names:
        encoded_name = quote(name)
        append_unique_url(out, urlunparse(parsed._replace(path=directory + encoded_name, query="", fragment="")))
    return out


def catalog_root_pdf_template_urls(root_url: str, *, target_year: int) -> list[str]:
    """Generate a small set of common catalog-root PDF paths for one target year."""
    parsed = urlparse(clean_text(root_url))
    if not parsed.netloc:
        return []
    host = parsed.netloc.lower()
    first_label = host.split(".", 1)[0]
    if first_label not in {"catalog", "catalogs", "academiccatalog", "coursecatalog", "ecatalog", "bulletin", "bulletins"}:
        return []
    base_path = parsed.path if parsed.path.endswith("/") else f"{parsed.path.rsplit('/', 1)[0]}/"
    root = urlunparse(parsed._replace(path=base_path or "/", query="", fragment=""))
    yy = f"{target_year % 100:02d}"
    yy_next = f"{(target_year + 1) % 100:02d}"
    names = [
        f"pdf/{target_year}-{yy_next}_Undergraduate_Catalog.pdf",
        f"pdf/{target_year}-{yy_next}_Academic_Catalog.pdf",
        f"pdf/{target_year}-{yy_next}_Catalog.pdf",
        f"pdf/{target_year}-{yy_next}.pdf",
        f"pdf/{target_year}-{target_year + 1}_Undergraduate_Catalog.pdf",
        f"pdf/{target_year}-{target_year + 1}_Academic_Catalog.pdf",
        f"pdf/{target_year}-{target_year + 1}_Catalog.pdf",
        f"pdf/{target_year}-{target_year + 1}Undergraduate_Catalog.pdf",
        f"previous/catalog-{yy}-{yy_next}.pdf",
    ]
    out: list[str] = []
    scheme_options = [parsed.scheme or "https"]
    if parsed.scheme == "https":
        scheme_options.append("http")
    elif parsed.scheme == "http":
        scheme_options.append("https")
    for scheme in dict.fromkeys(scheme_options):
        scheme_root = urlunparse(urlparse(root)._replace(scheme=scheme))
        for name in names:
            append_unique_url(out, urljoin(scheme_root, name))
    return out


def institution_catalog_name_tokens(institution_name: str, host: str) -> list[str]:
    words = [
        word.lower()
        for word in re.findall(r"[A-Za-z]+", clean_text(institution_name))
        if word.lower() not in {"the", "of", "and", "at", "campus"}
    ]
    tokens: list[str] = []
    if words:
        full_acronym = "".join(word[0] for word in words[:4])
        if len(full_acronym) >= 2:
            append_unique_url(tokens, full_acronym)
    meaningful = [word for word in words if word not in {"university", "college", "state", "institute", "technology"}]
    if meaningful:
        acronym = "".join(word[0] for word in meaningful[:4])
        if len(acronym) >= 2:
            append_unique_url(tokens, acronym)
    if words:
        append_unique_url(tokens, words[0])
    host_label = host.split(".", 1)[0].lower()
    if host_label not in {"www", "catalog", "catalogs", "academiccatalog", "coursecatalog", "ecatalog"}:
        append_unique_url(tokens, host_label)
    return tokens[:4]


def official_homepage_hosts_for_templates(home_url: str) -> list[str]:
    raw = clean_text(home_url)
    if not raw:
        return []
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urlparse(raw)
    host = parsed.netloc.lower().strip("/")
    if not host:
        return []
    hosts: list[str] = []
    labels = host.split(".")
    if len(labels) >= 2 and labels[-1] == "edu":
        domain = ".".join(labels[-2:])
        append_unique_url(hosts, "registrar." + domain)
        append_unique_url(hosts, "library." + domain)
        append_unique_url(hosts, "inside." + domain)
        append_unique_url(hosts, "coursecat." + domain)
        append_unique_url(hosts, "coursecatalog." + domain)
    append_unique_url(hosts, host)
    if host.startswith("www."):
        append_unique_url(hosts, host[4:])
    else:
        append_unique_url(hosts, "www." + host)
    if len(labels) >= 2 and labels[-1] == "edu":
        domain = ".".join(labels[-2:])
        append_unique_url(hosts, "img2." + domain)
        append_unique_url(hosts, "libraryapps." + domain)
        append_unique_url(hosts, "catalog." + domain)
        append_unique_url(hosts, "catalogs." + domain)
    return hosts[:12]


def official_domain_pdf_template_names(
    institution_name: str,
    host: str,
    *,
    target_year: int,
) -> list[str]:
    yy = f"{target_year % 100:02d}"
    out: list[str] = []
    spans: list[dict[str, str]] = []
    for start_year, end_year in [
        (target_year, target_year + 1),
        (target_year - 1, target_year),
        (target_year - 1, target_year + 1),
        (target_year, target_year + 2),
    ]:
        yy_start = f"{start_year % 100:02d}"
        yy_end = f"{end_year % 100:02d}"
        spans.append(
            {
                "start_year": str(start_year),
                "full_range": f"{start_year}-{end_year}",
                "short_range": f"{start_year}-{yy_end}",
                "yy_range": f"{yy_start}-{yy_end}",
            }
        )
    tokens = institution_catalog_name_tokens(institution_name, host)
    words = [
        word.lower()
        for word in re.findall(r"[A-Za-z]+", clean_text(institution_name))
        if word.lower() not in {"the", "of", "and", "at", "campus"}
    ]
    primary_word = words[0] if words else ""
    full_acronym = "".join(word[0] for word in words[:4]) if words else ""
    meaningful_words = [word for word in words if word not in {"university", "college", "state", "institute", "technology"}]
    meaningful_acronym = "".join(word[0] for word in meaningful_words[:4]) if meaningful_words else ""
    slug_forms: list[str] = []
    if words:
        append_unique_url(slug_forms, "-".join(words))
        append_unique_url(slug_forms, "-".join(word[:1].upper() + word[1:] for word in words))
        append_unique_url(slug_forms, "_".join(word[:1].upper() + word[1:] for word in words))
    if meaningful_words:
        append_unique_url(slug_forms, "-".join(meaningful_words))
    priority_word_forms: list[str] = []
    if primary_word:
        append_unique_url(priority_word_forms, primary_word)
        append_unique_url(priority_word_forms, primary_word[:1].upper() + primary_word[1:])
    priority_acronym_forms: list[str] = []
    for acronym in [full_acronym, meaningful_acronym]:
        if len(acronym) >= 2:
            append_unique_url(priority_acronym_forms, acronym.upper())
            append_unique_url(priority_acronym_forms, acronym)
    token_forms: list[str] = []
    for token in tokens:
        append_unique_url(token_forms, token)
        append_unique_url(token_forms, token[:1].upper() + token[1:])
        if len(token) <= 4:
            append_unique_url(token_forms, token.upper())

    for span in spans:
        yy_start, yy_end = span["yy_range"].split("-", 1)
        for name in [
            f"{span['full_range']}.pdf",
            f"{span['short_range']}.pdf",
            f"{span['full_range']}-catalog.pdf",
            f"{span['short_range']}-catalog.pdf",
            f"{span['full_range']}catalog.pdf",
            f"{span['short_range']}catalog.pdf",
            f"{span['full_range']}catalog-original.pdf",
            f"{span['short_range']}catalog-original.pdf",
            f"{span['full_range']}-ug-catalog.pdf",
            f"{span['short_range']}-ug-catalog.pdf",
            f"{span['full_range']}-Academic-Catalog.pdf",
            f"{span['short_range']}-Academic-Catalog.pdf",
            f"{span['full_range']}-academic-catalog.pdf",
            f"{span['short_range']}-academic-catalog.pdf",
            f"{span['full_range']}-Undergraduate-Catalog.pdf",
            f"{span['short_range']}-Undergraduate-Catalog.pdf",
            f"{span['full_range']}-undergraduate-catalog.pdf",
            f"{span['short_range']}-undergraduate-catalog.pdf",
            f"{span['short_range']}CourseCatalog.pdf",
            f"{span['full_range']}CourseCatalog.pdf",
            f"Catalog{span['short_range']}.pdf",
            f"Catalog{span['full_range']}.pdf",
            f"catalog{span['short_range']}.pdf",
            f"catalog{span['full_range']}.pdf",
            f"CATALOG-{span['full_range']}-FINAL.pdf",
            f"Catalog-{span['full_range']}-FINAL.pdf",
            f"{span['start_year']}-All.pdf",
            f"{span['start_year']}-all.pdf",
            f"{span['full_range']}_Undergraduate.pdf",
            f"{span['short_range']}_Undergraduate.pdf",
            f"{span['start_year']}_gen_bulletin.pdf",
            f"{span['start_year']}_gen_color.pdf",
        ]:
            append_unique_url(out, name)
        for slug in slug_forms:
            for name in [
                f"{slug}_{yy_start}_{yy_end}.pdf",
                f"{slug}_{yy_start}-{yy_end}.pdf",
                f"{slug}-{yy_start}-{yy_end}.pdf",
                f"{span['full_range']}-{slug}-Undergraduate-Catalog-Addendum.pdf",
                f"{span['full_range']}_{slug}_Undergraduate_Catalog-Addendum.pdf",
            ]:
                append_unique_url(out, name)
        for token in priority_word_forms:
            for name in [
                f"{token}catalog-{span['full_range']}.pdf",
                f"{token}catalog-{span['short_range']}.pdf",
            ]:
                append_unique_url(out, name)
        for acronym in priority_acronym_forms:
            for name in [
                f"{acronym}_Catalog_{span['yy_range']}.pdf",
                f"{acronym}_Catalog_{span['short_range']}.pdf",
            ]:
                append_unique_url(out, name)
        for slug in slug_forms:
            for name in [
                f"{slug}-bulletin-{span['short_range']}.pdf",
                f"{slug}-bulletin-{span['full_range']}.pdf",
                f"{slug}-catalog-{span['short_range']}.pdf",
                f"{slug}-catalog-{span['full_range']}.pdf",
            ]:
                append_unique_url(out, name)
        yy_compact = span["yy_range"].replace("-", "")
        for acronym in priority_acronym_forms:
            lower_acronym = acronym.lower()
            for name in [
                f"{lower_acronym}-catalog-{span['full_range']}.pdf",
                f"{lower_acronym}-catalog-{span['short_range']}.pdf",
                f"{lower_acronym}catalog{yy_compact}final.pdf",
                f"{lower_acronym}catalog{yy_compact}.pdf",
            ]:
                append_unique_url(out, name)
        for name in [
            f"Day-Catalog-{span['yy_range']}.pdf",
            f"{span['yy_range']}_Catalog.pdf",
            f"{span['yy_range']}-Catalog.pdf",
            f"{span['yy_range']}Catalog.pdf",
            f"catalog{span['start_year']}.pdf",
            f"Catalog{span['start_year']}.pdf",
            f"catalog-{span['start_year']}.pdf",
            f"Catalog-{span['start_year']}.pdf",
            f"College_catalog_{yy_compact}.pdf",
            f"college_catalog_{yy_compact}.pdf",
        ]:
            append_unique_url(out, name)

    for span in spans:
        for name in [
            f"{span['full_range']}-catalog.pdf",
            f"{span['short_range']}-catalog.pdf",
            f"{span['full_range']}-ug-catalog.pdf",
            f"{span['short_range']}-ug-catalog.pdf",
        ]:
            append_unique_url(out, name)
    for token in priority_word_forms:
        for span in spans:
            for name in [
                f"{token}catalog-{span['full_range']}.pdf",
                f"{token}catalog-{span['short_range']}.pdf",
            ]:
                append_unique_url(out, name)
    for acronym in priority_acronym_forms:
        for span in spans:
            for name in [
                f"{acronym}_Catalog_{span['yy_range']}.pdf",
                f"{acronym}_Catalog_{span['short_range']}.pdf",
            ]:
                append_unique_url(out, name)

    for span in spans:
        for token in priority_word_forms:
            for name in [
                f"{token}catalog-{span['full_range']}.pdf",
                f"{token}catalog-{span['short_range']}.pdf",
                f"{token}_Catalog{span['full_range']}.pdf",
                f"{token}_Catalog{span['short_range']}.pdf",
            ]:
                append_unique_url(out, name)
        for acronym in priority_acronym_forms:
            for name in [
                f"{acronym}_Catalog_{span['yy_range']}.pdf",
                f"{acronym}_Catalog_{span['short_range']}.pdf",
                f"{acronym}_Catalog_{span['full_range']}.pdf",
            ]:
                append_unique_url(out, name)

    for span in spans:
        full_range = span["full_range"]
        short_range = span["short_range"]
        for name in [
            f"{full_range}-ug-catalog.pdf",
            f"{short_range}-ug-catalog.pdf",
            f"{full_range}-UG-Catalog.pdf",
            f"{short_range}-UG-Catalog.pdf",
            f"{full_range}-catalog.pdf",
            f"{short_range}-catalog.pdf",
            f"{full_range}_catalog.pdf",
            f"{short_range}_catalog.pdf",
        ]:
            append_unique_url(out, name)

    token_patterns = [
        lambda token, span: f"{token}catalog-{span['full_range']}.pdf",
        lambda token, span: f"{token.upper()}_Catalog_{span['yy_range']}.pdf",
        lambda token, span: f"{token}catalog-{span['short_range']}.pdf",
        lambda token, span: f"{token}-catalog-{span['full_range']}.pdf",
        lambda token, span: f"{token}-catalog-{span['short_range']}.pdf",
        lambda token, span: f"{token}_Catalog{span['full_range']}.pdf",
        lambda token, span: f"{token}_Catalog{span['short_range']}.pdf",
        lambda token, span: f"{token}_Catalog_{span['full_range']}.pdf",
        lambda token, span: f"{token}_Catalog_{span['short_range']}.pdf",
        lambda token, span: f"{token.upper()}_Catalog_{span['short_range']}.pdf",
    ]
    for make_name in token_patterns:
        for span in spans:
            for token in token_forms:
                append_unique_url(out, make_name(token, span))

    for span in spans:
        full_range = span["full_range"]
        short_range = span["short_range"]
        for name in [
            f"{full_range}-undergraduate-catalog.pdf",
            f"{short_range}-undergraduate-catalog.pdf",
            f"{full_range}_Undergraduate_Catalog.pdf",
            f"{short_range}_Undergraduate_Catalog.pdf",
            f"{full_range}Undergraduate_Catalog.pdf",
            f"{short_range}Undergraduate_Catalog.pdf",
            f"UG {full_range} Catalog.pdf",
            f"UG {short_range} Catalog.pdf",
            f"UG_Catalog_{full_range}.pdf",
            f"UG_Catalog_{short_range}.pdf",
            f"Undergraduate_Catalog_{full_range}.pdf",
            f"Undergraduate_Catalog_{short_range}.pdf",
            f"Catalog_{full_range}.pdf",
            f"Catalog_{short_range}.pdf",
            f"Catalog{full_range}.pdf",
            f"Catalog{short_range}.pdf",
            f"catalog{full_range}.pdf",
            f"catalog{short_range}.pdf",
            f"{short_range}CourseCatalog.pdf",
            f"{full_range}CourseCatalog.pdf",
            f"Academic_Catalog_{full_range}.pdf",
            f"Academic_Catalog_{short_range}.pdf",
            f"hu_academic_catalog_rev{full_range}.pdf",
        ]:
            append_unique_url(out, name)
    return out


def official_domain_pdf_template_urls(
    home_url: str,
    institution_name: str,
    *,
    target_year: int,
    max_urls: int = 1250,
) -> list[str]:
    hosts = official_homepage_hosts_for_templates(home_url)
    if not hosts:
        return []
    folders = [
        "academics/_documents/",
        "_resources/pdfs/",
        "docs/acad_affairs/",
        "pdf/",
        "academics/essentials/registrar/",
        "wp-content/uploads/",
        "wp-content/uploads/2022/07/",
        "_files/pdfs/academics/undergraduate-catalog-archive/",
        "registrar/bulletin/",
        "registrar/bulletin/Undergraduate/",
        "archives/catalogs/",
        "PDFFiles/Academic%20Affairs/",
        "hu/docs/catalogs/",
        "wp-content/uploads/sites/13/2014/04/",
        "wp-content/uploads/sites/13/",
        "records-and-registration/wp-content/uploads/sites/364/2022/09/",
        "wp-content/uploads/sites/364/2022/09/",
        "sites/default/files/website_files/Academics/Academic_Affairs/",
    ]
    out: list[str] = []
    names_by_host = {host: official_domain_pdf_template_names(institution_name, host, target_year=target_year) for host in hosts}

    def append_folder_name_templates(host: str, host_folders: list[str], host_names: list[str]) -> bool:
        for folder in host_folders:
            for name in host_names:
                encoded_name = quote(name)
                base = f"https://{host}/{folder}"
                append_unique_url(out, urljoin(base, encoded_name))
                if len(out) >= max_urls:
                    return True
        return False

    priority_folders_by_prefix = {
        "registrar.": [
            "wp-content/uploads/sites/13/2014/04/",
            "wp-content/uploads/sites/13/",
        ],
        "library.": ["archives/catalogs/"],
        "inside.": [
            "records-and-registration/wp-content/uploads/sites/364/2022/09/",
            "wp-content/uploads/sites/364/2022/09/",
        ],
    }
    for host in hosts:
        if host.startswith("catalog."):
            for candidate_url in modern_campus_direct_media_template_urls(
                host,
                institution_name,
                target_year=target_year,
            ):
                append_unique_url(out, candidate_url)
                if len(out) >= max_urls:
                    return out

    for host in hosts:
        for prefix, host_folders in priority_folders_by_prefix.items():
            if not host.startswith(prefix):
                continue
            if prefix == "registrar.":
                day_names = [name for name in names_by_host[host] if name.startswith("Day-Catalog-")]
                bulletin_names = [name for name in names_by_host[host] if "_gen_" in name or "bulletin" in name.lower()]
                other_names = [name for name in names_by_host[host] if "-catalog-" in name]
                priority_names = (day_names + bulletin_names + other_names)[:16]
            elif prefix == "library.":
                bulletin_names = [name for name in names_by_host[host] if "bulletin" in name]
                other_names = [name for name in names_by_host[host] if "-catalog-" in name]
                priority_names = (bulletin_names + other_names)[:8]
            else:
                priority_names = [
                    name
                    for name in names_by_host[host]
                    if re.match(r"\d{2}-\d{2}[_-]?Catalog\.pdf", name) or name.endswith("_Catalog.pdf")
                ][:8]
            if append_folder_name_templates(host, host_folders, priority_names):
                return out
            break

    early_historical_folders = [
        "academics/_documents/",
        "_resources/pdfs/",
        "docs/acad_affairs/",
        "pdf/",
        "academics/essentials/registrar/",
        "sites/default/files/website_files/Academics/Academic_Affairs/",
        "wp-content/uploads/",
        "wp-content/uploads/2022/07/",
        "_files/pdfs/academics/undergraduate-catalog-archive/",
        "registrar/bulletin/",
        "registrar/bulletin/Undergraduate/",
    ]
    for host in hosts:
        if host.startswith(SPECIALIZED_CATALOG_HOST_PREFIXES):
            continue
        early_names = official_domain_early_historical_template_names(names_by_host[host])
        if append_folder_name_templates(host, early_historical_folders, early_names):
            return out
        break

    core_folders = [
        "academics/_documents/",
        "_resources/pdfs/",
        "docs/acad_affairs/",
        "pdf/",
        "academics/essentials/registrar/",
        "wp-content/uploads/",
        "wp-content/uploads/2022/07/",
        "_files/pdfs/academics/undergraduate-catalog-archive/",
        "registrar/bulletin/",
        "registrar/bulletin/Undergraduate/",
        "sites/default/files/website_files/Academics/Academic_Affairs/",
    ]
    for host in hosts:
        if host.startswith(SPECIALIZED_CATALOG_HOST_PREFIXES):
            continue
        core_names = official_domain_core_template_names(names_by_host[host])
        if append_folder_name_templates(host, core_folders, core_names):
            return out
        break
    for host in hosts:
        priority_folders = ["wp-content/uploads/2022/07/", "archives/catalogs/"]
        priority_names = names_by_host[host][:34]
        for prefix, host_folders in priority_folders_by_prefix.items():
            if host.startswith(prefix):
                priority_folders = host_folders
                if prefix == "registrar.":
                    day_names = [name for name in names_by_host[host] if name.startswith("Day-Catalog-")]
                    bulletin_names = [name for name in names_by_host[host] if "_gen_" in name or "bulletin" in name.lower()]
                    other_names = [name for name in names_by_host[host] if "-catalog-" in name]
                    priority_names = (day_names + bulletin_names + other_names)[:16]
                elif prefix == "library.":
                    bulletin_names = [name for name in names_by_host[host] if "bulletin" in name]
                    other_names = [name for name in names_by_host[host] if "-catalog-" in name]
                    priority_names = (bulletin_names + other_names)[:8]
                elif prefix == "inside.":
                    priority_names = [
                        name
                        for name in names_by_host[host]
                        if re.match(r"\d{2}-\d{2}[_-]?Catalog\.pdf", name) or name.endswith("_Catalog.pdf")
                    ][:8]
                break
        if not any(host.startswith(prefix) for prefix in priority_folders_by_prefix):
            priority_folders = [
                "academics/_documents/",
                "_resources/pdfs/",
                "docs/acad_affairs/",
                "pdf/",
                "academics/essentials/registrar/",
                "wp-content/uploads/",
                "wp-content/uploads/2022/07/",
                "_files/pdfs/academics/undergraduate-catalog-archive/",
                "registrar/bulletin/",
                "registrar/bulletin/Undergraduate/",
                "sites/default/files/website_files/Academics/Academic_Affairs/",
                "PDFFiles/Academic%20Affairs/",
                "archives/catalogs/",
            ]
            priority_names = official_domain_priority_template_names(names_by_host[host])
        if append_folder_name_templates(host, priority_folders, priority_names):
            return out
    for host in hosts:
        names = names_by_host[host]
        for name in names:
            encoded_name = quote(name)
            for folder in folders:
                base = f"https://{host}/{folder}"
                append_unique_url(out, urljoin(base, encoded_name))
                if len(out) >= max_urls:
                    return out
    return out


def official_domain_pdf_template_seed_urls(
    home_url: str,
    institution_name: str,
    *,
    target_year: int,
    max_urls: int = 36,
) -> list[str]:
    """Production-sized official-domain PDF probes used by live rescue."""
    hosts = official_homepage_hosts_for_templates(home_url)
    if not hosts:
        return []
    out: list[str] = []
    domain = registrable_domain_from_webaddr(home_url)
    if domain:
        yy = f"{target_year % 100:02d}"
        yy_next = f"{(target_year + 1) % 100:02d}"
        year_page_urls = [
            f"https://{target_year}bulletin.{domain}/undergraduate.html",
            f"https://{target_year}bulletin.{domain}/undergraduate/index.php.html",
            f"https://{target_year}bulletin.{domain}/undergraduate/",
        ]
        for candidate_url in year_page_urls:
            append_unique_url(out, candidate_url)
            if len(out) >= max_urls:
                return out
        domain_label = domain.split(".", 1)[0]
        if 2 <= len(domain_label) <= 4:
            for name in [
                f"undergrad-catalog-{target_year}-{target_year + 1}.pdf",
                f"undergrad-catalog-{target_year}-{yy_next}.pdf",
                f"undergraduate-catalog-{target_year}-{target_year + 1}.pdf",
                f"undergraduate-catalog-{target_year}-{yy_next}.pdf",
            ]:
                append_unique_url(out, f"https://s3.amazonaws.com/{domain_label}/files/resources/{name}")
                if len(out) >= max_urls:
                    return out
        words = [
            word.lower()
            for word in re.findall(r"[A-Za-z]+", clean_text(institution_name))
            if word.lower() not in {"the", "of", "and", "at", "campus", "university", "college"}
        ]
        if target_year <= 2010 and words:
            archive_slug = words[0][:4]
            for name in [
                f"catalog{yy}{yy_next}{archive_slug}",
                f"{archive_slug}catalog{yy}{yy_next}",
            ]:
                append_unique_url(out, f"https://archive.org/download/{name}/{name}.pdf")
                if len(out) >= max_urls:
                    return out

    def append_folder_name_templates(host: str, host_folders: list[str], host_names: list[str]) -> bool:
        for folder in host_folders:
            for name in host_names:
                append_unique_url(out, urljoin(f"https://{host}/{folder}", quote(name)))
                if len(out) >= max_urls:
                    return True
        return False

    seed_folders = [
        "pdf/",
        "catalog/pdfs/",
        "registrar/files/archived-academic-catalogs/",
        "academics/info/course-catalogs/",
        "uploaded/documents/academics/catalogs/",
        "sites/default/files/2023-03/",
        "sites/default/files/2023-02/",
        "_resources/images/catalog/catalogs/",
        "academics/catalog/docs/",
        "sites/default/files/documents/",
        "previouscatalogs/",
        "site/assets/files/3995/",
        "wp-content/uploads/",
        "_files/pdfs/academics/undergraduate-catalog-archive/",
        "registrar/bulletin/",
        "_media/department/registrar/documents/catalogues/",
    ]
    for host in hosts:
        if host.startswith(("registrar.", "library.", "inside.", "img2.", "libraryapps.", "catalog.", "catalogs.")):
            continue
        seed_names = official_domain_compact_seed_template_names(institution_name, host, target_year=target_year)
        if host.startswith(("coursecat.", "coursecatalog.")):
            priority_pairs = [
                ("previouscatalogs/", [name for name in seed_names if "ug_catalog-min" in name.lower()][:1]),
            ]
        else:
            reg_names: list[str] = []
            yy = f"{target_year % 100:02d}"
            prev_yy = f"{(target_year - 1) % 100:02d}"
            yy_next = f"{(target_year + 1) % 100:02d}"
            yy_plus2 = f"{(target_year + 2) % 100:02d}"
            for name in [
                f"REG_UG_Catalog_{yy}-{yy_next}_11.pdf",
                f"REG_UGBulletin{yy}-{yy_plus2}-1.pdf",
                f"REG_ugbulletin{yy}-{yy_plus2}.pdf",
                f"REG_ugbulletin{yy}_{yy_plus2}.pdf",
                f"REG_ugbulletin{prev_yy}-{yy_next}.pdf",
                f"REG_ugbulletin{prev_yy}_{yy_next}.pdf",
                f"REG_{prev_yy}_{yy_next}_ugradb.pdf",
            ]:
                if name in seed_names:
                    append_unique_url(reg_names, name)
            for name in seed_names:
                if name.startswith("REG_") and not name.startswith("REG_Undergrad"):
                    append_unique_url(reg_names, name)
            raw_course_catalog_names = [
                name
                for name in seed_names
                if "undergrad-catalog" in name.lower()
                or "undergraduate-catalog" in name.lower()
                or re.match(r"[a-z]{3,}-\d{2}-\d{2}-catalog\.pdf$", name.lower())
            ]
            course_catalog_names: list[str] = []
            for name in raw_course_catalog_names:
                if re.match(r"[a-z]{3,}-\d{2}-\d{2}-catalog\.pdf$", name.lower()):
                    append_unique_url(course_catalog_names, name)
            for name in raw_course_catalog_names:
                if re.match(r"\d{4}-\d{4}-[a-z]{2,}-undergraduate-catalog\.pdf$", name.lower()):
                    append_unique_url(course_catalog_names, name)
            for name in raw_course_catalog_names:
                if re.match(r"\d{4}-\d{4}-undergraduate-catalog\.pdf$", name.lower()):
                    append_unique_url(course_catalog_names, name)
            for name in raw_course_catalog_names:
                if re.match(r"undergraduate-catalog-\d{4}-\d{4}\.pdf$", name.lower()):
                    append_unique_url(course_catalog_names, name)
            for name in raw_course_catalog_names:
                append_unique_url(course_catalog_names, name)
            uploaded_catalog_names = [
                name
                for name in seed_names
                if "undergraduate_and_graduate_catalog" in name.lower()
                or re.fullmatch(r"\d{4}_\d{4}_catalog\.pdf", name.lower())
            ]
            def uploaded_catalog_priority(name: str) -> tuple[int, str]:
                lowered = name.lower()
                if re.fullmatch(r"\d{4}_\d{4}_undergraduate_and_graduate_catalog\.pdf", lowered):
                    return (0, lowered)
                if re.fullmatch(r"\d{4}_\d{4}_catalog\.pdf", lowered):
                    return (1, lowered)
                if "undergraduate_and_graduate_catalog" in lowered:
                    return (2, lowered)
                return (3, lowered)

            uploaded_catalog_names = sorted(uploaded_catalog_names, key=uploaded_catalog_priority)
            bulletin_names = [
                name
                for name in seed_names
                if "bulletin" in name.lower() or "course-bulletin" in name.lower()
            ]
            site_bulletin_names = [
                name
                for name in bulletin_names
                if not name.startswith("REG_")
            ]
            def site_bulletin_priority(name: str) -> tuple[int, str]:
                lowered = name.lower()
                if re.fullmatch(r"bulletin_\d{4}-\d{4}\.pdf", lowered):
                    return (0, lowered)
                if re.fullmatch(r"bulletin_\d{4}-\d{4}_0\.pdf", lowered):
                    return (1, lowered)
                if any(
                    token in lowered
                    for token in [
                        "final_052110",
                        "rev_final",
                        "copy_sep14",
                        "finalpdf",
                        "final_",
                        "_bulletin_4",
                    ]
                ):
                    return (2, lowered)
                if "course-bulletin" in lowered:
                    return (3, lowered)
                return (4, lowered)

            site_bulletin_names = sorted(site_bulletin_names, key=site_bulletin_priority)
            high_priority_site_bulletin_names = [
                name
                for name in site_bulletin_names
                if any(
                    token in name.lower()
                    for token in [
                        "final_052110",
                        "finalpdf",
                        "final_",
                        "_bulletin_4",
                    ]
                )
            ]
            def high_priority_site_bulletin_priority(name: str) -> tuple[int, str]:
                lowered = name.lower()
                if "final_052110" in lowered:
                    return (-3, lowered)
                if re.match(r"final_\d{4}-\d{4}_bulletin_27-jan-15\.pdf$", lowered):
                    return (-2, lowered)
                if "_bulletin_4" in lowered:
                    return (-1, lowered)
                if "finalpdf" in lowered:
                    return (0, lowered)
                if "final_" in lowered:
                    return (2, lowered)
                return (4, lowered)

            high_priority_site_bulletin_names = sorted(
                high_priority_site_bulletin_names,
                key=high_priority_site_bulletin_priority,
            )
            academic_catalog_names = [
                name
                for name in seed_names
                if re.fullmatch(r"\d{4}-\d{4}-academic-catalog\.pdf", name.lower())
            ]
            ugc_catalogue_names = [
                name
                for name in seed_names
                if re.fullmatch(r"ugc\d{4}\.pdf", name.lower())
            ]
            catalog_docs_names = [
                name
                for name in seed_names
                if re.match(r"[A-Z]{2,}\d{4}-\d{2}catalog\.pdf$", name)
            ]
            historical_archive_names: list[str] = []
            for name in [
                f"{target_year - 1}-{target_year + 1}.pdf",
                f"{target_year}-{target_year + 1}.pdf",
                f"{target_year}-{(target_year + 1) % 100:02d}.pdf",
            ]:
                if name in seed_names:
                    append_unique_url(historical_archive_names, name)
            registrar_bulletin_names: list[str] = []
            for name in [f"{target_year}-All.pdf", f"{target_year}-all.pdf"]:
                if name in seed_names:
                    append_unique_url(registrar_bulletin_names, name)
            priority_pairs = [
                ("pdf/", reg_names[:7]),
                ("academics/info/course-catalogs/", course_catalog_names[:7]),
                ("academics/catalog/docs/", catalog_docs_names[:4]),
                ("registrar/bulletin/", registrar_bulletin_names[:2]),
                ("uploaded/documents/academics/catalogs/", uploaded_catalog_names[:4]),
                ("wp-content/uploads/", academic_catalog_names[:2]),
                ("_media/department/registrar/documents/catalogues/", ugc_catalogue_names[:2]),
                ("sites/default/files/2023-03/", high_priority_site_bulletin_names[:6]),
                ("_files/pdfs/academics/undergraduate-catalog-archive/", historical_archive_names[:3]),
                ("sites/default/files/2023-03/", site_bulletin_names[:12]),
                ("sites/default/files/2023-02/", site_bulletin_names[:12]),
                ("catalog/pdfs/", course_catalog_names[:8]),
                ("registrar/files/archived-academic-catalogs/", course_catalog_names[:10]),
                ("_resources/images/catalog/catalogs/", [f"catalog{target_year}.pdf"]),
                ("academics/catalog/docs/", catalog_docs_names),
                ("sites/default/files/documents/", [name for name in seed_names if "ugcatalog" in name.lower() or "ugrad_catalog" in name.lower()]),
                ("site/assets/files/3995/", [name for name in seed_names if name.lower().startswith("ugcatalog_")]),
            ]
        for folder, names in priority_pairs:
            for name in names[:12]:
                append_unique_url(out, urljoin(f"https://{host}/{folder}", quote(name)))
                if len(out) >= max_urls:
                    return out
    for host in hosts:
        if host.startswith(SPECIALIZED_CATALOG_HOST_PREFIXES):
            continue
        seed_names = official_domain_compact_seed_template_names(institution_name, host, target_year=target_year)
        if append_folder_name_templates(host, seed_folders, seed_names):
            return out
        break
    return out


def modern_campus_direct_media_template_urls(host: str, institution_name: str, *, target_year: int) -> list[str]:
    words = [
        word.lower()
        for word in re.findall(r"[A-Za-z]+", clean_text(institution_name))
        if word.lower() not in {"the", "of", "and", "at", "campus"}
    ]
    if not words:
        return []
    slug = "-".join(words)
    yy = f"{target_year % 100:02d}"
    yy_next = f"{(target_year + 1) % 100:02d}"
    filenames = [f"{yy}-{yy_next}-{slug}-catalog.pdf"]
    out: list[str] = []
    # Modern Campus media IDs are opaque. Keep this a narrow, auditable probe band
    # around the target year rather than an open-ended media crawl.
    for media_id in range(target_year + 20, target_year + 61):
        for filename in filenames:
            append_unique_url(out, f"https://{host}/mime/media/7/{media_id}/{filename}")
    return out


def official_domain_priority_template_names(names: list[str]) -> list[str]:
    priority: list[str] = []
    for name in names[:72]:
        append_unique_url(priority, name)
    for name in names:
        lowered = name.lower()
        if (
            re.fullmatch(r"[a-z]+catalog-\d{4}-\d{4}\.pdf", lowered)
            or re.fullmatch(r"[a-z]+catalog\d{4}final\.pdf", lowered)
            or re.fullmatch(r"[a-z]+catalog-\d{4}-\d{2}\.pdf", lowered)
            or re.fullmatch(r"[a-z]+catalog-\d{4}-\d{4}\.pdf", lowered)
            or re.fullmatch(r"[a-z]+catalog-\d{4}-\d{2}\.pdf", lowered)
            or re.fullmatch(r"[a-z-]+-catalog-\d{4}-\d{4}\.pdf", lowered)
            or re.fullmatch(r"[a-z-]+-catalog-\d{4}-\d{2}\.pdf", lowered)
            or re.fullmatch(r"college_catalog_\d{4}\.pdf", lowered)
            or re.fullmatch(r"catalog\d{4}\.pdf", lowered)
            or re.fullmatch(r"(?:catalog)?\d{4}-\d{2}coursecatalog\.pdf", lowered)
            or re.fullmatch(r"catalog\d{4}-\d{4}\.pdf", lowered)
            or re.fullmatch(r"catalog\d{4}-\d{2}\.pdf", lowered)
            or re.fullmatch(r"\d{4}-\d{4}\.pdf", lowered)
            or re.fullmatch(r"\d{4}-\d{2}\.pdf", lowered)
            or re.fullmatch(r"\d{4}-all\.pdf", lowered)
            or re.fullmatch(r"\d{4}-\d{4}-academic-catalog\.pdf", lowered)
            or re.fullmatch(r"\d{4}-\d{2}-academic-catalog\.pdf", lowered)
            or re.fullmatch(r"\d{4}-\d{4}-undergraduate-catalog\.pdf", lowered)
            or re.fullmatch(r"\d{4}-\d{2}-undergraduate-catalog\.pdf", lowered)
            or re.fullmatch(r"[a-z-]+_\d{2}_\d{2}\.pdf", lowered)
            or re.fullmatch(r"\d{4}-\d{4}[_-][a-z_-]+[_-]undergraduate[_-]catalog-addendum\.pdf", lowered)
            or re.fullmatch(r"\d{4}_gen_(?:bulletin|color)\.pdf", lowered)
        ):
            append_unique_url(priority, name)
    return priority


def official_domain_early_historical_template_names(names: list[str]) -> list[str]:
    """Small ordered set of validated historical catalog PDF name shapes."""
    early: list[str] = []
    for name in names[:48]:
        append_unique_url(early, name)
    ordered_patterns = [
        r"[a-z]+catalog\d{4}final\.pdf",
        r"[a-z]+catalog\d{4}\.pdf",
        r"catalog\d{4}\.pdf",
        r"[a-z-]+-catalog-\d{4}-\d{4}\.pdf",
        r"[a-z-]+-catalog-\d{4}-\d{2}\.pdf",
        r"college_catalog_\d{4}\.pdf",
        r"[a-z]{2,}_catalog_\d{2}-\d{2}\.pdf",
        r"[a-z]{2,}_catalog_\d{4}-\d{4}\.pdf",
        r"\d{4}-\d{4}\.pdf",
        r"\d{4}-\d{2}\.pdf",
        r"\d{4}-all\.pdf",
        r"[a-z]+catalog-\d{4}-\d{4}\.pdf",
        r"[a-z]+catalog-\d{4}-\d{2}\.pdf",
        r"catalog\d{4}(?:-\d{4}|-\d{2})?\.pdf",
        r"(?:catalog)?\d{4}-\d{2}coursecatalog\.pdf",
        r"(?:catalog)?\d{2}-\d{2}coursecatalog\.pdf",
        r"\d{4}-\d{4}-ug-catalog\.pdf",
        r"\d{4}-\d{2}-ug-catalog\.pdf",
        r"\d{4}-\d{4}-academic-catalog\.pdf",
        r"\d{4}-\d{2}-academic-catalog\.pdf",
        r"\d{4}-\d{4}-undergraduate-catalog\.pdf",
        r"\d{4}-\d{2}-undergraduate-catalog\.pdf",
        r"[a-z-]+_\d{2}_\d{2}\.pdf",
        r"\d{4}-\d{4}[_-][a-z_-]+[_-]undergraduate[_-]catalog-addendum\.pdf",
    ]
    for pattern in ordered_patterns:
        added_for_pattern = 0
        pattern_limit = 8 if pattern.startswith(r"[a-z-]+-catalog") else 4
        for name in names:
            if re.fullmatch(pattern, name.lower()):
                append_unique_url(early, name)
                added_for_pattern += 1
                if added_for_pattern >= pattern_limit:
                    break
    return early[:96]


def official_domain_compact_seed_template_names(
    institution_name: str,
    host: str,
    *,
    target_year: int,
) -> list[str]:
    """Very small production probe set for live official-domain PDF rescue."""
    out: list[str] = []
    full_range = f"{target_year}-{target_year + 1}"
    underscore_range = f"{target_year}_{target_year + 1}"
    short_range = f"{target_year}-{(target_year + 1) % 100:02d}"
    short_underscore_range = f"{target_year % 100:02d}_{(target_year + 1) % 100:02d}"
    enclosing_range = f"{target_year - 1}-{target_year + 1}"
    prev_target_year = target_year - 1
    prev_enclosing_range = f"{prev_target_year}-{target_year + 1}"
    prev_yy = f"{prev_target_year % 100:02d}"
    yy = f"{target_year % 100:02d}"
    yy_next = f"{(target_year + 1) % 100:02d}"
    yy_plus2 = f"{(target_year + 2) % 100:02d}"
    domain_label = registrable_domain_from_webaddr(host).split(".", 1)[0]
    short_domain_label = domain_label[:3] if len(domain_label) >= 3 else ""
    medium_domain_label = domain_label[:6] if len(domain_label) >= 6 else domain_label
    words = [
        word.lower()
        for word in re.findall(r"[A-Za-z]+", clean_text(institution_name))
        if word.lower() not in {"the", "of", "and", "at", "campus"}
    ]
    acronyms = []
    if words:
        append_unique_url(acronyms, "".join(word[0] for word in words[:4]).upper())
    meaningful_words = [word for word in words if word not in {"university", "college", "state", "institute", "technology"}]
    if meaningful_words:
        append_unique_url(acronyms, "".join(word[0] for word in meaningful_words[:4]).upper())
    for name in [
        f"REG_UGBulletin{prev_yy}-{yy_next}-1.pdf",
        f"REG_ugbulletin{prev_yy}-{yy_next}.pdf",
        f"REG_ugbulletin{prev_yy}_{yy_next}.pdf",
        f"REG_{prev_yy}_{yy_next}_ugradb.pdf",
        f"REG_Undergrad{prev_target_year}{target_year + 1}.pdf",
        f"REG_UGBulletin{yy}-{yy_plus2}-1.pdf",
        f"REG_ugbulletin{yy}-{yy_plus2}.pdf",
        f"REG_ugbulletin{yy}_{yy_plus2}.pdf",
        f"REG_{yy}_{yy_plus2}_ugradb.pdf",
        f"REG_Undergrad{target_year}{target_year + 2}.pdf",
        f"REG_UG_Catalog_{yy}-{yy_next}_11.pdf",
        f"{yy}-{yy_next}ugcatalog.pdf",
        f"{yy}-{yy_next}_ugrad_catalog.pdf",
        f"{yy}-{yy_next}-ugrad-catalog.pdf",
        f"ugcatalog_{yy}{yy_next}.pdf",
        f"{full_range}-Academic-Catalog.pdf",
        f"{full_range}-catalog.pdf",
        f"{full_range}-Undergraduate-Catalog.pdf",
        f"{full_range}.pdf",
        f"{target_year}-All.pdf",
        f"{enclosing_range}.pdf",
        f"{prev_enclosing_range}.pdf",
        f"{short_range}CourseCatalog.pdf",
        f"catalog{target_year}.pdf",
        f"ugc{yy}{yy_next}.pdf",
        f"undergrad-catalog-{full_range}.pdf",
        f"undergrad-catalog-{short_range}.pdf",
        f"undergraduate-catalog-{full_range}.pdf",
        f"undergraduate-catalog-{short_range}.pdf",
        f"{full_range}-undergraduate-catalog.pdf",
        f"{full_range}-{domain_label}-undergraduate-catalog.pdf",
        f"{target_year}-{target_year + 1}-{domain_label}-undergraduate-catalog.pdf",
        f"bulletin_{full_range}.pdf",
        f"bulletin_{full_range}_0.pdf",
        f"bulletin_{underscore_range}.pdf",
        f"bulletin_{short_underscore_range}final_052110.pdf",
        f"bulletin_{yy}-{yy_next}_rev_final_6.pdf",
        f"course-bulletin-{full_range}.pdf",
        f"{full_range}_bulletin_4.pdf",
        f"{full_range}_bulletin_copy_sep14.pdf",
        f"final_{full_range}_bulletin.pdf",
        f"final_{full_range}_bulletin_27-jan-15.pdf",
        f"{medium_domain_label}_bulletin_{full_range}_finalpdf1.pdf",
        f"{medium_domain_label}_{full_range}_bulletin.pdf",
        f"{medium_domain_label}_{full_range}_bulletin_9_5_17_jw_0.pdf",
        f"{target_year}-catalog-online.pdf",
        f"{target_year}-catalog-web-version.pdf",
        f"{target_year}-{yy_next}-undergraduate-catalog.pdf",
        f"{full_range}_undergraduate_and_graduate_catalog.pdf",
        f"{full_range}_Undergraduate_and_Graduate_Catalog.pdf",
        f"{underscore_range}_catalog.pdf",
        f"{underscore_range}_undergraduate_and_graduate_catalog.pdf",
        f"{underscore_range}_Undergraduate_and_Graduate_Catalog.pdf",
    ]:
        append_unique_url(out, name)
    for label in [domain_label, short_domain_label]:
        if label:
            append_unique_url(out, f"{label}-{yy}-{yy_next}-catalog.pdf")
    for acronym in acronyms:
        for name in [
            f"{acronym}{target_year}-{yy_plus2}catalog.pdf",
            f"{acronym}{target_year}-{target_year + 2}catalog.pdf",
            f"{full_range}_{acronym}_UG_catalog-min.pdf",
            f"{short_range}_{acronym}_UG_catalog-min.pdf",
        ]:
            append_unique_url(out, name)
    return out


def official_domain_core_template_names(names: list[str]) -> list[str]:
    """Small high-yield subset tried across common historical PDF folders first."""
    priority_names = official_domain_priority_template_names(names)
    core: list[str] = []
    for name in priority_names[:8]:
        append_unique_url(core, name)
    high_yield_patterns = [
        r"\d{4}-\d{4}\.pdf",
        r"\d{4}-\d{2}\.pdf",
        r"\d{4}-all\.pdf",
        r"\d{4}-\d{4}-academic-catalog\.pdf",
        r"\d{4}-\d{2}-academic-catalog\.pdf",
        r"\d{4}-\d{4}-undergraduate-catalog\.pdf",
        r"\d{4}-\d{2}-undergraduate-catalog\.pdf",
        r"[a-z]+catalog-\d{4}-\d{4}\.pdf",
        r"[a-z]+catalog-\d{4}-\d{2}\.pdf",
        r"[a-z-]+-catalog-\d{4}-\d{4}\.pdf",
        r"[a-z-]+-catalog-\d{4}-\d{2}\.pdf",
        r"[a-z-]+_\d{2}_\d{2}\.pdf",
        r"\d{4}-\d{4}[_-][a-z_-]+[_-]undergraduate[_-]catalog-addendum\.pdf",
        r"(?:catalog)?\d{4}-\d{2}coursecatalog\.pdf",
        r"(?:catalog)?\d{2}-\d{2}coursecatalog\.pdf",
        r"[a-z]{2,}_catalog_\d{2}-\d{2}\.pdf",
        r"[a-z]{2,}_catalog_\d{4}-\d{4}\.pdf",
        r"college_catalog_\d{4}\.pdf",
        r"\d{4}_gen_(?:bulletin|color)\.pdf",
        r"catalog\d{4}(?:-\d{4}|-\d{2})?\.pdf",
        r"\d{4}-\d{4}catalog(?:-original)?\.pdf",
        r"\d{4}-\d{2}catalog(?:-original)?\.pdf",
        r"[a-z]+catalog\d{4}final\.pdf",
        r"[a-z]+catalog\d{4}\.pdf",
        r"[a-z-]+-college-catalog-\d{4}-\d{4}\.pdf",
        r"[a-z-]+-college-catalog-\d{4}-\d{2}\.pdf",
        r"[a-z]+catalog-\d{4}-\d{4}\.pdf",
        r"[a-z]+catalog-\d{4}-\d{2}\.pdf",
        r"\d{4}-\d{4}-ug-catalog\.pdf",
        r"\d{4}-\d{2}-ug-catalog\.pdf",
        r"\d{4}-\d{4}-catalog\.pdf",
        r"\d{4}-\d{2}-catalog\.pdf",
    ]
    for pattern in high_yield_patterns:
        for name in priority_names:
            if re.fullmatch(pattern, name.lower()):
                append_unique_url(core, name)
    for name in priority_names[:36]:
        append_unique_url(core, name)
    return core[:60]


def official_domain_pdf_template_seed_rows(repo_root: Path, sector: str, panel: pd.DataFrame) -> pd.DataFrame:
    if panel.empty:
        return pd.DataFrame()
    frame = panel.copy()
    frame["unitid"] = pd.to_numeric(frame["unitid"], errors="coerce").astype("Int64")
    frame["target_year"] = pd.to_numeric(frame["target_year"], errors="coerce").astype("Int64")
    frame["best_url"] = frame["best_url"].map(clean_text)
    needs_template_rescue = frame["best_url"].eq("") | frame.apply(risky_catalogarchive_candidate, axis=1)
    missing_by_unit = {
        int(unitid): sorted(set(group.loc[needs_template_rescue.loc[group.index], "target_year"].dropna().astype(int).tolist()))
        for unitid, group in frame.groupby("unitid", dropna=False)
        if not pd.isna(unitid)
    }
    discovery = read_checkpoint(stream_outputs(repo_root, sector).discovery_input_csv)
    if discovery.empty or "unitid" not in discovery.columns or "webaddr" not in discovery.columns:
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    for _, institution in discovery.iterrows():
        unitid = institution.get("unitid")
        if pd.isna(unitid):
            continue
        unitid_int = int(unitid)
        missing_years = missing_by_unit.get(unitid_int, [])
        if not missing_years:
            continue
        home_url = clean_text(institution.get("webaddr"))
        name = clean_text(institution.get("institution_name"))
        for target_year in missing_years:
            for candidate_url in official_domain_pdf_template_seed_urls(
                home_url,
                name,
                target_year=target_year,
            ):
                rows.append(
                    {
                        "unitid": unitid_int,
                        "institution_name": name,
                        "target_year": target_year,
                        "source_target_year": target_year,
                        "source_url": home_url,
                        "candidate_url": candidate_url,
                        "candidate_link_text": f"Generated official-domain catalog PDF probe for {target_year}-{target_year + 1}",
                        "candidate_evidence_text": (
                            f"Bounded official-domain PDF template from clean homepage webaddr={home_url}"
                        ),
                        "archive_url": home_url,
                    }
                )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).drop_duplicates(["unitid", "target_year", "candidate_url"])


def risky_catalogarchive_candidate(row: pd.Series) -> bool:
    url = clean_text(row.get("best_url")).lower()
    if not url:
        return False
    parsed = urlparse(url if "://" in url else f"https://{url}")
    return parsed.netloc.lower().startswith("catalogarchive.") and not parsed.path.lower().endswith(".pdf")


def candidate_source_artifact_paths(repo_root: Path, sector: str) -> list[Path]:
    first = stream_outputs(repo_root, sector)
    archive = archive_expansion_outputs(repo_root, sector)
    ai = ai_rescue_outputs(repo_root, sector)
    ai_gap = ai_year_gap_outputs(repo_root, sector)
    return [
        first.year_candidates_csv,
        archive.archive_expansion_candidates_csv,
        ai.ai_year_candidates_csv,
        ai_gap.ai_year_gap_candidates_csv,
    ]


def archive_page_source_artifact_paths(repo_root: Path, sector: str) -> list[Path]:
    first = stream_outputs(repo_root, sector)
    archive = archive_expansion_outputs(repo_root, sector)
    ai = ai_rescue_outputs(repo_root, sector)
    ai_gap = ai_year_gap_outputs(repo_root, sector)
    return [
        first.archive_pages_csv,
        archive.archive_expansion_pages_csv,
        ai.ai_archive_pages_csv,
        ai_gap.ai_year_gap_archive_pages_csv,
    ]


def inferred_source_year(row: pd.Series, *, url_column: str) -> int | None:
    target_value = pd.to_numeric(pd.Series([row.get("target_year")]), errors="coerce").iloc[0]
    if not pd.isna(target_value):
        return int(target_value)
    evidence = " ".join(
        clean_text(row.get(column))
        for column in [
            url_column,
            "candidate_link_text",
            "candidate_evidence_text",
            "archive_link_text",
            "page_title",
            "year_hints",
        ]
    )
    year_range = catalog_year_range(evidence)
    if year_range:
        return year_range[0]
    return None


def current_run_inferred_source_rows(repo_root: Path, sector: str) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for path in candidate_source_artifact_paths(repo_root, sector):
        frame = read_checkpoint(path)
        if frame.empty or "unitid" not in frame.columns or "candidate_url" not in frame.columns:
            continue
        for _, row in frame.iterrows():
            source_url = clean_text(row.get("candidate_url"))
            source_year = inferred_source_year(row, url_column="candidate_url")
            if not source_url or source_year is None:
                continue
            rows.append(
                {
                    "unitid": row.get("unitid"),
                    "institution_name": clean_text(row.get("institution_name")),
                    "source_target_year": source_year,
                    "source_url": source_url,
                    "candidate_link_text": clean_text(row.get("candidate_link_text")),
                    "candidate_evidence_text": clean_text(row.get("candidate_evidence_text")),
                    "archive_url": clean_text(row.get("archive_url")),
                    "source_artifact": str(path),
                }
            )
    for path in archive_page_source_artifact_paths(repo_root, sector):
        frame = read_checkpoint(path)
        if frame.empty or "unitid" not in frame.columns or "archive_url" not in frame.columns:
            continue
        for _, row in frame.iterrows():
            source_url = clean_text(row.get("archive_url"))
            source_year = inferred_source_year(row, url_column="archive_url")
            if not source_url or source_year is None:
                continue
            rows.append(
                {
                    "unitid": row.get("unitid"),
                    "institution_name": clean_text(row.get("institution_name")),
                    "source_target_year": source_year,
                    "source_url": source_url,
                    "candidate_link_text": clean_text(row.get("archive_link_text")),
                    "candidate_evidence_text": " ".join(
                        clean_text(row.get(column)) for column in ["archive_link_text", "page_title", "year_hints"]
                    ).strip(),
                    "archive_url": source_url,
                    "source_artifact": str(path),
                }
            )
    for path in [
        ai_rescue_outputs(repo_root, sector).ai_triage_csv,
        ai_year_gap_outputs(repo_root, sector).ai_year_gap_triage_csv,
    ]:
        frame = read_checkpoint(path)
        if frame.empty or "unitid" not in frame.columns or "api_direct_catalog_urls_json" not in frame.columns:
            continue
        for _, row in frame.iterrows():
            if clean_text(row.get("api_validation_status")) != "parsed":
                continue
            for item in parse_json_list(row.get("api_direct_catalog_urls_json")):
                if not isinstance(item, dict):
                    continue
                source_url = clean_text(item.get("url"))
                if not source_url:
                    continue
                source_year_value = pd.to_numeric(pd.Series([item.get("covered_start_year")]), errors="coerce").iloc[0]
                if pd.isna(source_year_value):
                    evidence = " ".join(
                        [
                            source_url,
                            clean_text(item.get("catalog_year_text")),
                            clean_text(item.get("evidence")),
                        ]
                    )
                    year_range = catalog_year_range(evidence)
                    if not year_range:
                        continue
                    source_year = year_range[0]
                else:
                    source_year = int(source_year_value)
                rows.append(
                    {
                        "unitid": row.get("unitid"),
                        "institution_name": clean_text(row.get("institution_name")),
                        "source_target_year": source_year,
                        "source_url": source_url,
                        "candidate_link_text": clean_text(item.get("catalog_year_text")),
                        "candidate_evidence_text": clean_text(item.get("evidence")),
                        "archive_url": clean_text(item.get("url")),
                        "source_artifact": str(path),
                    }
                )
    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    out["unitid"] = pd.to_numeric(out["unitid"], errors="coerce").astype("Int64")
    out = out.loc[out["unitid"].notna()].copy()
    return out.drop_duplicates(["unitid", "source_target_year", "source_url"])


def inferred_year_url_seed_rows_from_source_artifacts(panel: pd.DataFrame, sources: pd.DataFrame) -> pd.DataFrame:
    if panel.empty or sources.empty:
        return pd.DataFrame()
    frame = panel.copy()
    frame["unitid"] = pd.to_numeric(frame["unitid"], errors="coerce").astype("Int64")
    frame["target_year"] = pd.to_numeric(frame["target_year"], errors="coerce").astype("Int64")
    frame["best_url"] = frame["best_url"].map(clean_text)
    missing_by_unit = {
        int(unitid): sorted(set(group.loc[group["best_url"].eq(""), "target_year"].dropna().astype(int).tolist()))
        for unitid, group in frame.groupby("unitid", dropna=False)
        if not pd.isna(unitid)
    }
    rows: list[dict[str, object]] = []
    for _, source in sources.iterrows():
        unitid = source.get("unitid")
        if pd.isna(unitid):
            continue
        unitid_int = int(unitid)
        missing_years = missing_by_unit.get(unitid_int, [])
        if not missing_years:
            continue
        source_url = clean_text(source.get("source_url"))
        source_year = int(source["source_target_year"])
        for target_year in missing_years:
            for candidate_url in inferred_year_url_replacements(
                source_url,
                source_year=source_year,
                target_year=target_year,
            ):
                rows.append(
                    {
                        "unitid": unitid_int,
                        "institution_name": clean_text(source.get("institution_name")),
                        "target_year": target_year,
                        "source_target_year": source_year,
                        "source_url": source_url,
                        "candidate_url": candidate_url,
                        "candidate_link_text": f"Inferred {target_year}-{target_year + 1} catalog URL from current-run candidate artifact",
                        "candidate_evidence_text": (
                            f"Template source target_year={source_year}; source_url={source_url}; "
                            f"source_artifact={clean_text(source.get('source_artifact'))}"
                        ),
                        "archive_url": clean_text(source.get("archive_url")),
                    }
                )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).drop_duplicates(["unitid", "target_year", "candidate_url"])


def catalog_root_pdf_template_seed_rows(repo_root: Path, sector: str, panel: pd.DataFrame) -> pd.DataFrame:
    if panel.empty:
        return pd.DataFrame()
    frame = panel.copy()
    frame["unitid"] = pd.to_numeric(frame["unitid"], errors="coerce").astype("Int64")
    frame["target_year"] = pd.to_numeric(frame["target_year"], errors="coerce").astype("Int64")
    frame["best_url"] = frame["best_url"].map(clean_text)
    missing_by_unit = {
        int(unitid): sorted(set(group.loc[group["best_url"].eq(""), "target_year"].dropna().astype(int).tolist()))
        for unitid, group in frame.groupby("unitid", dropna=False)
        if not pd.isna(unitid)
    }
    roots = read_checkpoint(stream_outputs(repo_root, sector).root_candidates_csv)
    if roots.empty or "unitid" not in roots.columns or "candidate_url" not in roots.columns:
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    template_root_count_by_unitid: dict[int, int] = {}
    for _, root in roots.iterrows():
        unitid = root.get("unitid")
        if pd.isna(unitid):
            continue
        unitid_int = int(unitid)
        missing_years = missing_by_unit.get(unitid_int, [])
        if not missing_years:
            continue
        root_urls = [
            clean_text(root.get("candidate_url")),
            clean_text(root.get("final_url")),
        ]
        for root_url in dict.fromkeys(url for url in root_urls if url):
            if template_root_count_by_unitid.get(unitid_int, 0) >= 2:
                continue
            root_rows: list[dict[str, object]] = []
            for target_year in missing_years:
                for candidate_url in catalog_root_pdf_template_urls(root_url, target_year=target_year):
                    root_rows.append(
                        {
                            "unitid": unitid_int,
                            "institution_name": clean_text(root.get("institution_name")),
                            "target_year": target_year,
                            "source_target_year": target_year,
                            "source_url": root_url,
                            "candidate_url": candidate_url,
                            "candidate_link_text": f"Inferred {target_year}-{target_year + 1} catalog PDF from current-run catalog root",
                            "candidate_evidence_text": (
                                f"Catalog-root PDF template; root_url={root_url}; "
                                f"root_source_type={clean_text(root.get('candidate_source_type'))}"
                            ),
                            "archive_url": root_url,
                        }
                    )
            if root_rows:
                template_root_count_by_unitid[unitid_int] = template_root_count_by_unitid.get(unitid_int, 0) + 1
                rows.extend(root_rows)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).drop_duplicates(["unitid", "target_year", "candidate_url"])


def inferred_year_url_seed_rows(panel: pd.DataFrame) -> pd.DataFrame:
    if panel.empty:
        return pd.DataFrame()
    frame = panel.copy()
    frame["unitid"] = pd.to_numeric(frame["unitid"], errors="coerce").astype("Int64")
    frame["target_year"] = pd.to_numeric(frame["target_year"], errors="coerce").astype("Int64")
    frame["best_url"] = frame["best_url"].map(clean_text)
    rows: list[dict[str, object]] = []
    for unitid, group in frame.groupby("unitid", dropna=False):
        if pd.isna(unitid):
            continue
        observed = group.loc[group["best_url"].ne("")].copy()
        missing_years = sorted(set(group.loc[group["best_url"].eq(""), "target_year"].dropna().astype(int).tolist()))
        if observed.empty or not missing_years:
            continue
        for _, source in observed.iterrows():
            source_year = int(source["target_year"])
            source_url = clean_text(source.get("best_url"))
            for target_year in missing_years:
                for candidate_url in inferred_year_url_replacements(
                    source_url,
                    source_year=source_year,
                    target_year=target_year,
                ):
                    rows.append(
                        {
                            "unitid": int(unitid),
                            "institution_name": clean_text(source.get("institution_name")),
                            "target_year": target_year,
                            "source_target_year": source_year,
                            "source_url": source_url,
                            "candidate_url": candidate_url,
                            "candidate_link_text": f"Inferred {target_year}-{target_year + 1} catalog URL from discovered year pattern",
                            "candidate_evidence_text": f"Template source target_year={source_year}; source_url={source_url}",
                            "archive_url": clean_text(source.get("archive_url")),
                        }
                    )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).drop_duplicates(["unitid", "target_year", "candidate_url"])


def target_year_url_tokens(target_year: int) -> tuple[str, ...]:
    return (
        str(target_year),
        str(target_year + 1),
        f"{target_year % 100:02d}",
        f"{(target_year + 1) % 100:02d}",
        f"{target_year}-{target_year + 1}",
        f"{target_year}_{target_year + 1}",
        f"{target_year % 100:02d}-{(target_year + 1) % 100:02d}",
        f"{target_year % 100:02d}_{(target_year + 1) % 100:02d}",
    )


def compact_two_digit_year_range(text: str) -> tuple[int, int] | None:
    match = re.search(r"(?<!\d)(\d{2})[-_](\d{2})(?!\d)", clean_text(text))
    if not match:
        return None
    start_two = int(match.group(1))
    end_two = int(match.group(2))
    start = 2000 + start_two if start_two <= 35 else 1900 + start_two
    end = (start // 100 * 100) + end_two
    if end <= start:
        end += 100
    if 1900 <= start <= 2030 and start < end <= 2035 and end - start <= 4:
        return start, end
    return None


def inferred_seed_priority(row: pd.Series) -> tuple[int, int, int, int, str]:
    """Rank inferred URL probes so live validation stays bounded and reproducible."""
    candidate = clean_text(row.get("candidate_url")).lower()
    source_url = clean_text(row.get("source_url")).lower()
    target_year = int(row.get("target_year"))
    source_year = int(row.get("source_target_year"))
    distance = abs(source_year - target_year)
    tokens = target_year_url_tokens(target_year)
    leaf = unquote(urlparse(candidate).path.rsplit("/", 1)[-1].lower())
    target_in_leaf = int(not any(token in leaf for token in tokens))
    target_in_url = int(not any(token in candidate for token in tokens))
    stable_source = int("wp-content/uploads" in source_url and "wp-content/uploads" not in candidate)
    return (distance, target_in_leaf, target_in_url, stable_source, candidate)


def cap_inferred_year_url_seeds(
    seeds: pd.DataFrame,
    *,
    max_per_institution_year: int = 40,
) -> pd.DataFrame:
    if seeds.empty or max_per_institution_year <= 0:
        return seeds
    frame = seeds.copy()
    frame["unitid"] = pd.to_numeric(frame["unitid"], errors="coerce").astype("Int64")
    frame["target_year"] = pd.to_numeric(frame["target_year"], errors="coerce").astype("Int64")
    frame = frame.loc[frame["unitid"].notna() & frame["target_year"].notna()].copy()
    if frame.empty:
        return frame
    priorities = frame.apply(inferred_seed_priority, axis=1, result_type="expand")
    priority_columns = [
        "_priority_distance",
        "_priority_target_in_leaf",
        "_priority_target_in_url",
        "_priority_stable_source",
        "_priority_url",
    ]
    priorities.columns = priority_columns
    frame = pd.concat([frame.reset_index(drop=True), priorities.reset_index(drop=True)], axis=1)
    frame = frame.sort_values(["unitid", "target_year", *priority_columns])
    frame = frame.groupby(["unitid", "target_year"], group_keys=False).head(max_per_institution_year).copy()
    return frame.drop(columns=priority_columns)


def materialize_inferred_year_url_candidates(
    seeds: pd.DataFrame,
    *,
    timeout_seconds: int,
    max_workers: int,
    min_wall_timeout_seconds: int = 60,
    max_wall_timeout_seconds: int = 180,
    progress_label: str = "",
    progress_interval_seconds: int = 15,
) -> pd.DataFrame:
    if seeds.empty:
        return pd.DataFrame()
    unique_urls: list[str] = []
    seen_urls: set[str] = set()
    for value in seeds["candidate_url"].dropna():
        url = clean_text(value)
        if url and url not in seen_urls:
            unique_urls.append(url)
            seen_urls.add(url)
    result_by_url: dict[str, dict[str, object]] = {}
    wall_timeout = max(
        min_wall_timeout_seconds,
        min(
            max_wall_timeout_seconds,
            timeout_seconds * (max(1, (len(unique_urls) + max_workers - 1) // max_workers) + 2),
        ),
    )
    executor = ThreadPoolExecutor(max_workers=max_workers)
    futures = {
        executor.submit(retrieve_url, url, timeout_seconds=timeout_seconds, max_bytes=250_000): url
        for url in unique_urls
    }
    pending = set(futures)
    completed = 0
    deadline = time.monotonic() + wall_timeout
    label = progress_label or "inferred-year-url-materialization"
    if progress_label:
        print(f"[{label}] probes={len(unique_urls)} wall_timeout={wall_timeout}s", flush=True)
    try:
        while pending:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            done, pending = wait(
                pending,
                timeout=min(progress_interval_seconds, max(0.1, remaining)),
                return_when=FIRST_COMPLETED,
            )
            if not done:
                if progress_label:
                    print(f"[{label}] completed {completed}/{len(unique_urls)}", flush=True)
                continue
            for future in done:
                completed += 1
                url = futures[future]
                try:
                    result_by_url[url] = future.result()
                except Exception as exc:  # pragma: no cover - network failures vary.
                    result_by_url[url] = {
                        "retrieval_status": "error",
                        "http_status": "",
                        "page_title": "",
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                    }
            if progress_label and (completed % 25 == 0 or completed == len(unique_urls)):
                print(f"[{label}] completed {completed}/{len(unique_urls)}", flush=True)
        for future in list(pending):
            url = futures[future]
            if future.done():
                completed += 1
                try:
                    result_by_url[url] = future.result()
                    continue
                except Exception as exc:  # pragma: no cover - network failures vary.
                    result_by_url[url] = {
                        "retrieval_status": "error",
                        "http_status": "",
                        "page_title": "",
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                    }
                    continue
            future.cancel()
            result_by_url[url] = {
                "retrieval_status": "timeout",
                "http_status": "",
                "page_title": "",
                "error_type": "materialize_inferred_year_url_timeout",
                "error_message": f"inferred-year materialization wall-clock timeout after {wall_timeout} seconds",
            }
        if progress_label and pending:
            print(
                f"[{label}] timed out {len(pending)}/{len(unique_urls)} probes after {wall_timeout}s",
                flush=True,
            )
    finally:
        executor.shutdown(wait=False, cancel_futures=True)
    rows = []
    for _, seed in seeds.iterrows():
        url = clean_text(seed.get("candidate_url"))
        result = result_by_url.get(url, {})
        rows.extend(inferred_year_candidate_rows_from_seed_result(seed, result))
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).drop_duplicates(
        ["unitid", "target_year", "candidate_url"],
        keep="first",
    )


def inferred_year_candidate_rows_from_seed_result(seed: pd.Series, result: dict[str, object]) -> list[dict[str, object]]:
    url = clean_text(seed.get("candidate_url"))
    if clean_text(result.get("retrieval_status")) not in RETRIEVED_STATUSES:
        return []
    if retrieval_placeholder_error(result):
        return []
    http_status = pd.to_numeric(pd.Series([result.get("http_status")]), errors="coerce").iloc[0]
    if not pd.isna(http_status) and int(http_status) == 202:
        return []
    target_year = int(seed["target_year"])
    url_leaf = unquote(urlparse(url).path.rsplit("/", 1)[-1])
    explicit_range = (
        catalog_year_range(url_leaf)
        or normalized_year_range(url_leaf)
        or compact_two_digit_year_range(url_leaf)
        or catalog_year_range(url)
        or normalized_year_range(url)
        or compact_two_digit_year_range(url)
    )
    if explicit_range:
        start, end = explicit_range
        start_year_covered = start <= target_year < end or start == target_year
        end_year_compatible = end - start == 1 and target_year == end
        if not (start_year_covered or end_year_compatible):
            return []
        covered_years = [target_year] if end_year_compatible else academic_years_from_range(start, end)
        academic_year_rule = (
            "AY accepted by one-year end-year compatibility rule for legacy/catalog date conventions."
            if end_year_compatible
            else "AY is the catalog start year; inferred multi-year URLs cover each start year through end-1."
        )
    else:
        start, end = target_year, target_year + 1
        covered_years = [target_year]
        academic_year_rule = "AY is the catalog start year; inferred URL has no explicit broader range."
    rows: list[dict[str, object]] = []
    for covered_year in covered_years:
        rows.append(
            {
                "batch3_rank": 0,
                "unitid": int(seed["unitid"]),
                "institution_name": clean_text(seed["institution_name"]),
                "target_year": covered_year,
                "catalog_year_start": start,
                "catalog_year_end": end,
                "academic_year_rule": academic_year_rule,
                "candidate_url": url,
                "candidate_link_text": clean_text(seed.get("candidate_link_text")),
                "candidate_evidence_text": clean_text(seed.get("candidate_evidence_text")),
                "candidate_evidence_source": "inferred_year_url_pattern",
                "archive_url": clean_text(seed.get("archive_url")),
                "archive_page_title": "",
                "candidate_scope": "undergraduate_or_university_catalog",
                "validation_status": "inferred_year_url_retrieved",
                "candidate_priority": 18,
                "candidate_source_method": "inferred_year_url_pattern",
                "candidate_retrieval_status": clean_text(result.get("retrieval_status")),
                "candidate_http_status": clean_text(result.get("http_status")),
                "candidate_page_title": clean_text(result.get("page_title")),
                "created_at": utc_now(),
            }
        )
    return rows


def materialize_official_domain_year_url_candidates(
    seeds: pd.DataFrame,
    *,
    timeout_seconds: int,
    max_workers: int,
    min_wall_timeout_seconds: int = 12,
    max_probes_per_institution_year: int = 16,
) -> pd.DataFrame:
    """Retrieve official-domain PDF probes in bounded year-candidate rounds."""
    if seeds.empty:
        return pd.DataFrame()
    work = seeds.copy()
    work["_seed_order"] = range(len(work))
    work["unitid"] = pd.to_numeric(work["unitid"], errors="coerce").astype("Int64")
    work["target_year"] = pd.to_numeric(work["target_year"], errors="coerce").astype("Int64")
    work["candidate_url"] = work["candidate_url"].map(clean_text)
    work = work.loc[work["unitid"].notna() & work["target_year"].notna() & work["candidate_url"].ne("")].copy()
    if work.empty:
        return pd.DataFrame()
    grouped_seed_rows: list[tuple[tuple[int, int], pd.DataFrame]] = []
    for (unitid, target_year), group in work.sort_values(["unitid", "target_year", "_seed_order"]).groupby(
        ["unitid", "target_year"],
        sort=False,
    ):
        group = group.sort_values("_seed_order").copy()
        if max_probes_per_institution_year > 0:
            group = group.head(max_probes_per_institution_year).copy()
        grouped_seed_rows.append(((int(unitid), int(target_year)), group))
    max_group_size = max((len(group) for _, group in grouped_seed_rows), default=0)
    covered_keys: set[tuple[int, int]] = set()
    frames: list[pd.DataFrame] = []
    worker_count = max(1, min(max_workers, 64))
    for probe_index in range(max_group_size):
        round_rows: list[dict[str, object]] = []
        for key, group in grouped_seed_rows:
            if key in covered_keys or probe_index >= len(group):
                continue
            round_rows.append(group.iloc[probe_index].drop(labels=["_seed_order"], errors="ignore").to_dict())
        if not round_rows:
            continue
        round_candidates = materialize_inferred_year_url_candidates(
            pd.DataFrame(round_rows),
            timeout_seconds=timeout_seconds,
            max_workers=worker_count,
            min_wall_timeout_seconds=min_wall_timeout_seconds,
            progress_label=f"official-domain-inferred-year-round-{probe_index + 1}",
        )
        if round_candidates.empty:
            continue
        frames.append(round_candidates)
        for _, candidate in round_candidates.iterrows():
            covered_keys.add((int(candidate["unitid"]), int(candidate["target_year"])))
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).drop_duplicates(
        ["unitid", "target_year", "candidate_url"],
        keep="first",
    )


def write_inferred_year_url_summary(
    path: Path,
    *,
    sector: str,
    outputs: InferredYearUrlOutputs,
    seeds: pd.DataFrame,
    candidates: pd.DataFrame,
    final_status: pd.DataFrame,
) -> None:
    added_years = int(final_status["ai_added_years"].sum()) if not final_status.empty and "ai_added_years" in final_status else 0
    lines = [
        f"# {sector.title()} Clean No-Legacy Inferred Year-URL Rescue",
        "",
        f"Generated at: {utc_now()}",
        "",
        "Scope: deterministic URL-pattern inference from clean-discovered URLs only. Human legacy URLs remain withheld.",
        "",
        "## Bottom Line",
        "",
        f"- Inferred URL seeds generated: {len(seeds)}",
        f"- Retrieved inferred institution-year candidates kept: {len(candidates)}",
        f"- Candidate institution-year URLs added after inferred URL rescue: {added_years}",
        "",
        "## Outputs",
        "",
    ]
    for label, output_path in outputs.__dict__.items():
        lines.append(f"- {label}: `{output_path}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_inferred_year_url_rescue_for_sector(
    repo_root: Path,
    sector: str,
    *,
    timeout_seconds: int = 4,
    max_workers: int = 12,
) -> InferredYearUrlOutputs:
    repo_root = repo_root.resolve()
    first = stream_outputs(repo_root, sector)
    first_status = read_checkpoint(first.institution_status_csv)
    current_panel = current_clean_panel_for_gap_search(repo_root, sector)
    outputs = inferred_year_url_outputs(repo_root, sector)
    for output_path in outputs.__dict__.values():
        output_path.parent.mkdir(parents=True, exist_ok=True)
    panel_seeds = inferred_year_url_seed_rows(current_panel)
    artifact_sources = current_run_inferred_source_rows(repo_root, sector)
    artifact_seeds = inferred_year_url_seed_rows_from_source_artifacts(current_panel, artifact_sources)
    root_template_seeds = catalog_root_pdf_template_seed_rows(repo_root, sector, current_panel)
    official_domain_template_seeds = official_domain_pdf_template_seed_rows(repo_root, sector, current_panel)
    seed_frames = [
        frame
        for frame in [panel_seeds, official_domain_template_seeds, artifact_seeds, root_template_seeds]
        if not frame.empty
    ]
    seeds = pd.concat(seed_frames, ignore_index=True) if seed_frames else pd.DataFrame()
    if not seeds.empty:
        seeds = seeds.drop_duplicates(["unitid", "target_year", "candidate_url"])
    candidate_frames: list[pd.DataFrame] = []
    if not official_domain_template_seeds.empty:
        official_candidates = materialize_official_domain_year_url_candidates(
            official_domain_template_seeds.drop_duplicates(["unitid", "target_year", "candidate_url"]),
            timeout_seconds=max(timeout_seconds, 4),
            max_workers=max_workers,
            max_probes_per_institution_year=32,
        )
        if not official_candidates.empty:
            candidate_frames.append(official_candidates)
    other_seed_frames = [
        frame
        for frame in [panel_seeds, artifact_seeds, root_template_seeds]
        if not frame.empty
    ]
    other_seeds = pd.concat(other_seed_frames, ignore_index=True) if other_seed_frames else pd.DataFrame()
    if not other_seeds.empty:
        other_seeds = other_seeds.drop_duplicates(["unitid", "target_year", "candidate_url"])
        other_seeds = cap_inferred_year_url_seeds(other_seeds, max_per_institution_year=4)
        other_candidates = materialize_inferred_year_url_candidates(
            other_seeds,
            timeout_seconds=min(timeout_seconds, 2),
            max_workers=max_workers,
            min_wall_timeout_seconds=30,
            progress_label=f"{sector}-inferred-year-other-seeds",
        )
        if not other_candidates.empty:
            candidate_frames.append(other_candidates)
    candidates = pd.concat(candidate_frames, ignore_index=True) if candidate_frames else pd.DataFrame()
    if not candidates.empty:
        candidates = candidates.drop_duplicates(["unitid", "target_year", "candidate_url"])
    candidates = filter_candidate_rows(candidates) if not candidates.empty else candidates
    final_panel = merge_final_panel(current_panel, candidates)
    final_status = build_final_status(first_status, final_panel, pd.DataFrame(), pd.DataFrame())
    candidates.to_csv(outputs.inferred_year_candidates_csv, index=False)
    final_panel.to_csv(outputs.inferred_year_panel_csv, index=False)
    final_status.to_csv(outputs.inferred_year_status_csv, index=False)
    write_workbook(
        outputs.workbook,
        {
            "start_here": final_status,
            "inferred_year_candidates": candidates,
            "inferred_year_panel": final_panel,
            "current_panel_before_inference": current_panel,
            "inference_seeds": seeds,
        },
    )
    write_inferred_year_url_summary(
        outputs.summary_md,
        sector=sector,
        outputs=outputs,
        seeds=seeds,
        candidates=candidates,
        final_status=final_status,
    )
    return outputs


def registrable_domain_from_webaddr(webaddr: object) -> str:
    raw = clean_text(webaddr)
    if not raw:
        return ""
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    host = parsed.netloc.lower().strip("/")
    if host.startswith("www."):
        host = host[4:]
    parts = [part for part in host.split(".") if part]
    if len(parts) <= 2:
        return host
    return ".".join(parts[-2:])


def hostname_from_webaddr(webaddr: object) -> str:
    raw = clean_text(webaddr)
    if not raw:
        return ""
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    return parsed.netloc.lower().strip("/")


def generated_repository_seed_roots(current_panel: pd.DataFrame) -> pd.DataFrame:
    if current_panel.empty:
        return pd.DataFrame()
    frame = current_panel.copy()
    frame["unitid"] = pd.to_numeric(frame["unitid"], errors="coerce").astype("Int64")
    frame["target_year"] = pd.to_numeric(frame["target_year"], errors="coerce").astype("Int64")
    if "best_url" not in frame.columns:
        frame["best_url"] = ""
    frame["best_url"] = frame["best_url"].map(clean_text)
    if "webaddr" not in frame.columns:
        frame["webaddr"] = ""
    rows: list[dict[str, object]] = []
    host_templates = [
        ("img2.{domain}/hu/docs/catalogs", "generated_repository_img2_hu_docs_catalogs_path"),
        ("img2.{domain}/hu/docs", "generated_repository_img2_hu_docs_path"),
        ("www.{domain}/library/archives", "generated_repository_library_archives_path"),
        ("{domain}/library/archives", "generated_repository_library_archives_path"),
        ("www.{domain}/library/specialcollections", "generated_repository_library_specialcollections_path"),
        ("academicarchive.{domain}", "generated_repository_academicarchive_subdomain"),
        ("digitalcommons.{domain}", "generated_repository_digitalcommons_subdomain"),
        ("publications.{domain}", "generated_repository_publications_subdomain"),
        ("repository.{domain}", "generated_repository_repository_subdomain"),
        ("archives.{domain}", "generated_repository_archives_subdomain"),
        ("digitalcollections.{domain}", "generated_repository_digitalcollections_subdomain"),
        ("scholarworks.{domain}", "generated_repository_scholarworks_subdomain"),
        ("digital.{domain}", "generated_repository_digital_subdomain"),
    ]
    for unitid, group in frame.groupby("unitid", dropna=False):
        if pd.isna(unitid):
            continue
        missing = group.loc[group["best_url"].eq(""), "target_year"].dropna()
        if missing.empty:
            continue
        first = group.iloc[0]
        domain = registrable_domain_from_webaddr(first.get("webaddr"))
        if not domain:
            continue
        for host_template, source_detail in host_templates:
            host = host_template.format(domain=domain)
            rows.append(
                {
                    "unitid": int(unitid),
                    "institution_name": clean_text(first.get("institution_name")),
                    "seed_url": f"https://{host.rstrip('/')}/",
                    "seed_source": "generated_repository_root",
                    "seed_source_detail": source_detail,
                }
            )
        smartcatalog_labels: list[str] = []
        web_host = hostname_from_webaddr(first.get("webaddr"))
        for value in [domain.split(".")[0], web_host.split(".")[0] if web_host else ""]:
            value = value.lower().strip()
            if value and value not in {"www", "catalog", "catalogs"} and value not in smartcatalog_labels:
                smartcatalog_labels.append(value)
        for label in smartcatalog_labels:
            rows.append(
                {
                    "unitid": int(unitid),
                    "institution_name": clean_text(first.get("institution_name")),
                    "seed_url": f"https://{label}.smartcatalogiq.com/",
                    "seed_source": "generated_catalog_vendor_root",
                    "seed_source_detail": "generated_smartcatalogiq_subdomain",
                }
            )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).drop_duplicates(["unitid", "seed_url"], keep="first")


def sitemap_urls_for_webaddr(webaddr: object) -> list[str]:
    host = hostname_from_webaddr(webaddr)
    domain = registrable_domain_from_webaddr(webaddr)
    hosts: list[str] = []
    for value in [host, f"www.{domain}" if domain and not domain.startswith("www.") else domain, domain]:
        value = clean_text(value).lower().strip("/")
        if value and value not in hosts:
            hosts.append(value)
    urls: list[str] = []
    for host_value in hosts:
        for path in ["sitemap.xml", "sitemap_index.xml"]:
            append_unique_url(urls, f"https://{host_value}/{path}")
    return urls


def is_sitemap_catalog_page_url(url: str) -> bool:
    lowered = clean_text(url).lower()
    if not lowered.startswith(("http://", "https://")):
        return False
    if re.search(r"\.(pdf|docx?|xlsx?|pptx?|jpg|jpeg|png|gif|zip)(?:[?#].*)?$", lowered):
        return False
    if any(term in lowered for term in ["academic-calendar", "academic_calendar", "/calendar", "schedule-of-classes"]):
        return False
    return "catalog" in lowered or "bulletin" in lowered


def sitemap_catalog_page_seed_roots(
    current_panel: pd.DataFrame,
    *,
    timeout_seconds: int = 6,
    max_pages_per_institution: int = 8,
) -> pd.DataFrame:
    if current_panel.empty:
        return pd.DataFrame()
    frame = current_panel.copy()
    frame["unitid"] = pd.to_numeric(frame["unitid"], errors="coerce").astype("Int64")
    if "best_url" not in frame.columns:
        frame["best_url"] = ""
    frame["best_url"] = frame["best_url"].map(clean_text)
    if "webaddr" not in frame.columns:
        frame["webaddr"] = ""
    rows: list[dict[str, object]] = []
    for unitid, group in frame.groupby("unitid", dropna=False):
        if pd.isna(unitid):
            continue
        if group.loc[group["best_url"].eq("")].empty:
            continue
        first = group.iloc[0]
        found_for_unitid = 0
        for sitemap_url in sitemap_urls_for_webaddr(first.get("webaddr")):
            try:
                result = retrieve_url(sitemap_url, timeout_seconds=timeout_seconds, max_bytes=750_000)
            except Exception:
                continue
            if clean_text(result.get("retrieval_status")) not in RETRIEVED_STATUSES:
                continue
            body = result.get("body", b"") or b""
            if not isinstance(body, bytes):
                continue
            text = body.decode("utf-8", errors="ignore")
            for match in re.finditer(r"<loc[^>]*>(.*?)</loc>", text, flags=re.IGNORECASE | re.DOTALL):
                candidate_url = unquote(html.unescape(re.sub(r"\s+", "", match.group(1))))
                if not is_sitemap_catalog_page_url(candidate_url):
                    continue
                rows.append(
                    {
                        "unitid": int(unitid),
                        "institution_name": clean_text(first.get("institution_name")),
                        "seed_url": candidate_url,
                        "seed_source": "generated_sitemap_catalog_page",
                        "seed_source_detail": f"sitemap={sitemap_url}",
                    }
                )
                found_for_unitid += 1
                if found_for_unitid >= max_pages_per_institution:
                    break
            if found_for_unitid >= max_pages_per_institution:
                break
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).drop_duplicates(["unitid", "seed_url"], keep="first")


CURRENT_SITE_CATALOG_PAGE_PATHS = [
    "catalog",
    "catalogs",
    "academic-catalog",
    "academic-catalogs",
    "course-catalog",
    "course-catalogs",
    "academics/catalog",
    "academics/catalogs",
    "academics/academic-catalog",
    "academics/academic-catalogs",
    "academics/course-catalog",
    "academics/course-catalogs",
    "publications/catalog-archive",
    "publications/catalog-archives",
    "registrar/catalog",
    "registrar/catalogs",
    "registrar/academic-catalog",
    "registrar/academic-catalogs",
    "registrar/course-catalog",
    "registrar/course-catalogs",
    "course-schedules-and-catalogs",
    "catalogs-and-course-schedules",
    "about/office-registrar/catalogs-and-course-schedules",
    "about/office-registrar/course-schedules-and-catalogs",
    "registrar/catalogs-and-course-schedules",
    "registrar/course-schedules-and-catalogs",
    "office-registrar/catalogs-and-course-schedules",
    "academics/registrar/catalogs-and-course-schedules",
]

REGISTRAR_ARCHIVE_PAGE_PATHS = [
    "archive",
    "archives",
    "bulletin/archive",
    "bulletin/archives",
    "catalog/archive",
    "catalog/archives",
    "catalogs/archive",
    "catalogs/archives",
]


def generated_current_site_catalog_page_seed_roots(current_panel: pd.DataFrame) -> pd.DataFrame:
    if current_panel.empty:
        return pd.DataFrame()
    frame = current_panel.copy()
    frame["unitid"] = pd.to_numeric(frame["unitid"], errors="coerce").astype("Int64")
    if "best_url" not in frame.columns:
        frame["best_url"] = ""
    frame["best_url"] = frame["best_url"].map(clean_text)
    if "webaddr" not in frame.columns:
        frame["webaddr"] = ""
    rows: list[dict[str, object]] = []
    for unitid, group in frame.groupby("unitid", dropna=False):
        if pd.isna(unitid):
            continue
        if group.loc[group["best_url"].eq("")].empty:
            continue
        first = group.iloc[0]
        web_host = hostname_from_webaddr(first.get("webaddr"))
        domain = registrable_domain_from_webaddr(first.get("webaddr"))
        host_paths: list[tuple[str, list[str]]] = []
        standard_hosts: list[str] = []
        for value in [web_host, f"www.{domain}" if domain and not domain.startswith("www.") else domain]:
            value = clean_text(value).lower().strip("/")
            if value and value not in standard_hosts:
                standard_hosts.append(value)
        for host_value in standard_hosts:
            host_paths.append((host_value, CURRENT_SITE_CATALOG_PAGE_PATHS))
        registrar_host = f"registrar.{domain}" if domain else ""
        if registrar_host and registrar_host not in standard_hosts:
            host_paths.append((registrar_host, REGISTRAR_ARCHIVE_PAGE_PATHS + CURRENT_SITE_CATALOG_PAGE_PATHS))
        for host_value, paths in host_paths:
            for path in paths:
                rows.append(
                    {
                        "unitid": int(unitid),
                        "institution_name": clean_text(first.get("institution_name")),
                        "seed_url": f"https://{host_value}/{path}",
                        "seed_source": "generated_current_site_catalog_page",
                        "seed_source_detail": path,
                    }
                )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).drop_duplicates(["unitid", "seed_url"], keep="first")


def archive_expansion_seed_roots(
    repo_root: Path,
    sector: str,
    current_panel: pd.DataFrame,
    *,
    max_seed_roots_per_institution: int = 12,
) -> pd.DataFrame:
    """Collect clean-discovered roots/archive pages for deeper crawling.

    The inputs here are only first-pass/AI clean outputs and clean-discovered
    panel URLs. Withheld human legacy URLs are intentionally not read.
    """
    first = stream_outputs(repo_root, sector)
    frames: list[pd.DataFrame] = []
    status = read_checkpoint(first.institution_status_csv)
    status_keep = pd.DataFrame()
    if not status.empty:
        status_columns = [column for column in ["unitid", "batch3_rank", "fresh_rank", "institution_name"] if column in status.columns]
        status_keep = status[status_columns].copy()
        status_keep["unitid"] = pd.to_numeric(status_keep["unitid"], errors="coerce").astype("Int64")
        status_keep = status_keep.drop_duplicates("unitid", keep="last")

    def normalize_seed_frame(frame: pd.DataFrame, url_column: str, source_column: str, source_label: str) -> pd.DataFrame:
        if frame.empty or url_column not in frame.columns:
            return pd.DataFrame()
        out = frame.copy()
        out["unitid"] = pd.to_numeric(out["unitid"], errors="coerce").astype("Int64")
        out["seed_url"] = out[url_column].map(clean_text)
        out = out.loc[out["unitid"].notna() & out["seed_url"].str.startswith(("http://", "https://"))].copy()
        if out.empty:
            return pd.DataFrame()
        out["seed_source"] = source_label
        out["seed_source_detail"] = out[source_column].map(clean_text) if source_column in out.columns else ""
        keep_seed = [
            is_archive_expansion_seed_url(url, source_label=source_label, source_detail=detail)
            for url, detail in zip(out["seed_url"], out["seed_source_detail"])
        ]
        out = out.loc[keep_seed].copy()
        if out.empty:
            return pd.DataFrame()
        keep = ["unitid", "institution_name", "seed_url", "seed_source", "seed_source_detail"]
        for column in keep:
            if column not in out.columns:
                out[column] = ""
        return out[keep]

    roots = read_checkpoint(first.source_root_decisions_csv)
    if not roots.empty:
        roots = roots.loc[roots.get("decision_status", pd.Series("", index=roots.index)).map(clean_text).eq("preferred_source_root_identified")].copy()
        frames.append(normalize_seed_frame(roots, "preferred_source_root_url", "preferred_source_root_type", "first_pass_preferred_root"))

    root_candidates = read_checkpoint(first.root_candidates_csv)
    if not root_candidates.empty:
        likely = bool_series(root_candidates.get("likely_catalog_root", pd.Series(False, index=root_candidates.index)))
        retrieved = root_candidates.get("retrieval_status", pd.Series("", index=root_candidates.index)).map(clean_text).isin(RETRIEVED_STATUSES)
        roots_from_candidates = root_candidates.loc[likely & retrieved].copy()
        frames.append(normalize_seed_frame(roots_from_candidates, "candidate_url", "candidate_source_type", "retrieved_likely_root_candidate"))

    archive_inputs = [
        (read_checkpoint(first.archive_pages_csv), "archive_url", "archive_source", "first_pass_archive_page"),
        (
            read_checkpoint(ai_rescue_outputs(repo_root, sector).ai_archive_pages_csv),
            "archive_url",
            "archive_source",
            "ai_rescue_archive_page",
        ),
        (
            read_checkpoint(ai_year_gap_outputs(repo_root, sector).ai_year_gap_archive_pages_csv),
            "archive_url",
            "archive_source",
            "ai_year_gap_archive_page",
        ),
    ]
    for frame, url_column, source_column, source_label in archive_inputs:
        if frame.empty:
            continue
        if "retrieval_status" in frame.columns:
            frame = frame.loc[frame["retrieval_status"].map(clean_text).isin(RETRIEVED_STATUSES)].copy()
        frames.append(normalize_seed_frame(frame, url_column, source_column, source_label))

    if not current_panel.empty:
        panel = current_panel.copy()
        if "archive_url" in panel.columns:
            frames.append(normalize_seed_frame(panel, "archive_url", "best_url_source", "current_panel_archive_url"))
        repo_seeds = generated_repository_seed_roots(panel)
        if not repo_seeds.empty:
            frames.append(repo_seeds)
        sitemap_seeds = sitemap_catalog_page_seed_roots(panel)
        if not sitemap_seeds.empty:
            frames.append(sitemap_seeds)
        current_site_catalog_page_seeds = generated_current_site_catalog_page_seed_roots(panel)
        if not current_site_catalog_page_seeds.empty:
            frames.append(current_site_catalog_page_seeds)

    seeds = concat_frames(frames)
    if seeds.empty:
        return pd.DataFrame(
            columns=[
                "batch3_rank",
                "unitid",
                "institution_name",
                "decision_status",
                "preferred_source_root_url",
                "preferred_source_root_type",
                "preferred_source_root_title",
            ]
        )
    seeds["unitid"] = pd.to_numeric(seeds["unitid"], errors="coerce").astype("Int64")
    seeds["seed_url"] = seeds["seed_url"].map(clean_text)
    seeds = seeds.loc[seeds["unitid"].notna() & seeds["seed_url"].ne("")].copy()
    seeds = seeds.sort_values(["unitid", "seed_source", "seed_url"]).drop_duplicates(["unitid", "seed_url"], keep="first")
    if not status_keep.empty:
        seeds = seeds.merge(status_keep, on="unitid", how="left", suffixes=("", "_status"))
        if "institution_name_status" in seeds.columns:
            seeds["institution_name"] = seeds["institution_name"].map(clean_text).where(
                seeds["institution_name"].map(clean_text).ne(""),
                seeds["institution_name_status"].map(clean_text),
            )
    if "batch3_rank" not in seeds.columns:
        seeds["batch3_rank"] = 0
    seeds["batch3_rank"] = pd.to_numeric(seeds["batch3_rank"], errors="coerce").fillna(0).astype(int)
    seeds["decision_status"] = "preferred_source_root_identified"
    seeds["preferred_source_root_url"] = seeds["seed_url"]
    seeds["preferred_source_root_type"] = seeds["seed_source"] + ":" + seeds["seed_source_detail"]
    seeds["preferred_source_root_title"] = ""
    seeds["seed_priority"] = [
        archive_expansion_seed_priority(label, detail, url)
        for label, detail, url in zip(seeds["seed_source"], seeds["seed_source_detail"], seeds["seed_url"])
    ]
    seeds = seeds.sort_values(["unitid", "seed_priority", "preferred_source_root_url"])
    if max_seed_roots_per_institution > 0:
        seeds = seeds.groupby("unitid", group_keys=False).head(max_seed_roots_per_institution).copy()
    keep = [
        "batch3_rank",
        "unitid",
        "institution_name",
        "decision_status",
        "preferred_source_root_url",
        "preferred_source_root_type",
        "preferred_source_root_title",
    ]
    return seeds[keep].sort_values(["batch3_rank", "unitid", "preferred_source_root_url"])


def archive_expansion_seed_priority(source_label: str, source_detail: str, url: str) -> int:
    label = clean_text(source_label)
    detail = clean_text(source_detail).lower()
    lowered = clean_text(url).lower()
    if "wp-json/wp/v2/media" in lowered and "wordpress_media_catalog_api" in detail:
        return -1
    if label == "generated_repository_root":
        if "/library/archives" in lowered:
            return 0
        if "/library/specialcollections" in lowered:
            return 1
        if (
            "academicarchive" in lowered
            or "digitalcollections" in lowered
            or "archives" in lowered
            or "digitalcommons" in lowered
            or "publications" in lowered
            or "repository" in lowered
        ):
            return 0
        return 3
    if label == "generated_catalog_vendor_root":
        if "smartcatalogiq" in lowered:
            return 0
        return 8
    if label == "generated_sitemap_catalog_page":
        return 1
    if label == "generated_current_site_catalog_page":
        if "registrar." in lowered and "archive" in lowered:
            return 0
        if "archive" in lowered or "archives" in lowered:
            return 1
        if "registrar." in lowered and any(term in lowered for term in ["catalog", "catalogs", "bulletin"]):
            return 2
        return 8
    if label == "first_pass_preferred_root":
        return 0
    if label == "retrieved_likely_root_candidate" and "wordpress_media_catalog_api" in detail:
        return -1
    if label == "retrieved_likely_root_candidate" and any(term in detail for term in ["catalog_subdomain", "catalogs_subdomain", "bulletin_subdomain"]):
        return 1
    if label == "retrieved_likely_root_candidate":
        return 2
    if "catalog_list" in lowered or "contentdm_collection_api" in detail:
        return 3
    if "root_catalog_collection" in detail:
        return 4
    if "archive" in lowered or "archive" in detail:
        return 5
    if label.startswith("ai_year_gap"):
        return 6
    if label.startswith("ai_rescue"):
        return 7
    return 9


def is_archive_expansion_seed_url(url: str, *, source_label: str, source_detail: str) -> bool:
    parsed_text = clean_text(url)
    if not parsed_text:
        return False
    lowered = parsed_text.lower()
    if re.search(r"\.(pdf|docx?|xlsx?|pptx?|jpg|jpeg|png|gif|zip)(?:[?#].*)?$", lowered):
        return False
    detail = clean_text(source_detail).lower()
    label = clean_text(source_label).lower()
    if label == "generated_repository_root":
        return any(
            term in lowered or term in detail
            for term in [
                "academicarchive",
                "digitalcommons",
                "publications",
                "repository",
                "archives",
                "digitalcollections",
                "scholarworks",
                "digital",
            ]
        )
    if label == "generated_catalog_vendor_root":
        return "smartcatalogiq" in lowered or "smartcatalogiq" in detail
    if label == "generated_sitemap_catalog_page":
        return is_sitemap_catalog_page_url(parsed_text)
    if label == "generated_current_site_catalog_page":
        return is_sitemap_catalog_page_url(parsed_text)
    if catalog_year_range(f"{parsed_text} {detail}"):
        return False
    root_like_label = label in {"first_pass_preferred_root", "retrieved_likely_root_candidate"}
    archiveish = any(
        term in lowered or term in detail
        for term in [
            "archive",
            "archives",
            "archived",
            "catalog_list",
            "catalog collection",
            "root_catalog_collection",
            "contentdm_collection_api",
        ]
    )
    catalog_rootish = (
        root_like_label
        and any(term in lowered for term in ["catalog", "catalogs", "bulletin", "bulletins", "coursecatalog"])
    )
    wordpress_media_api = root_like_label and "wp-json/wp/v2/media" in lowered and "wordpress_media_catalog_api" in detail
    return archiveish or catalog_rootish or wordpress_media_api


def wordpress_media_api_search_url(source_url: str, search_term: str) -> str:
    parsed = urlparse(clean_text(source_url))
    params = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True) if key not in {"search", "page"}]
    params.append(("search", search_term))
    if not any(key == "per_page" for key, _ in params):
        params.append(("per_page", "100"))
    return urlunparse(parsed._replace(query=urlencode(params)))


def wordpress_media_year_search_terms(missing_years: list[int]) -> list[str]:
    years = sorted(dict.fromkeys(int(year) for year in missing_years))
    terms: list[str] = []
    for year in years:
        terms.append(str(year))
    for year in years:
        terms.append(f"{year % 100:02d}_{(year + 1) % 100:02d}")
    for year in years:
        terms.append(f"{year % 100:02d}-{(year + 2) % 100:02d}")
    terms.append("undergraduate catalog addendum")
    terms.append("catalog addendum")
    for year in years:
        terms.append(f"{year}-{year + 1}")
    for year in years:
        terms.append(f"{year % 100:02d}-{(year + 1) % 100:02d}")
    for year in years:
        for span_start in [year, year - 1]:
            span_end = span_start + 2
            if not (TARGET_START_YEAR - 5 <= span_start <= TARGET_END_YEAR + 5):
                continue
            terms.append(f"{span_start % 100:02d}_{span_end % 100:02d}")
            terms.append(f"{span_start}-{span_end}")
            terms.append(f"{span_start % 100:02d}-{span_end % 100:02d}")
    return list(dict.fromkeys(terms))


def wordpress_media_year_search_seed_roots(
    selected_seed_roots: pd.DataFrame,
    current_panel: pd.DataFrame,
    *,
    max_search_roots_per_institution: int = 96,
) -> pd.DataFrame:
    if selected_seed_roots.empty or current_panel.empty or max_search_roots_per_institution <= 0:
        return pd.DataFrame()
    panel = current_panel.copy()
    panel["unitid"] = pd.to_numeric(panel["unitid"], errors="coerce").astype("Int64")
    panel["target_year"] = pd.to_numeric(panel["target_year"], errors="coerce").astype("Int64")
    panel["best_url"] = panel.get("best_url", pd.Series("", index=panel.index)).map(clean_text)
    missing_by_unit = {
        int(unitid): sorted(group.loc[group["best_url"].eq(""), "target_year"].dropna().astype(int).tolist())
        for unitid, group in panel.groupby("unitid", dropna=False)
        if not pd.isna(unitid)
    }
    roots = selected_seed_roots.copy()
    roots["unitid"] = pd.to_numeric(roots["unitid"], errors="coerce").astype("Int64")
    roots["preferred_source_root_url"] = roots["preferred_source_root_url"].map(clean_text)
    roots["preferred_source_root_type"] = roots["preferred_source_root_type"].map(clean_text)
    roots = roots.loc[
        roots["unitid"].notna()
        & roots["preferred_source_root_url"].str.contains("/wp-json/wp/v2/media", case=False, regex=False)
        & roots["preferred_source_root_type"].str.contains("wordpress_media", case=False, regex=False)
    ].copy()
    rows: list[dict[str, object]] = []
    for _, root in roots.iterrows():
        unitid = int(root["unitid"])
        missing_years = missing_by_unit.get(unitid, [])
        if not missing_years:
            continue
        terms = wordpress_media_year_search_terms(missing_years)[:max_search_roots_per_institution]
        for term in terms:
            search_url = wordpress_media_api_search_url(clean_text(root["preferred_source_root_url"]), term)
            rows.append(
                {
                    "batch3_rank": int(pd.to_numeric(pd.Series([root.get("batch3_rank")]), errors="coerce").fillna(0).iloc[0]),
                    "unitid": unitid,
                    "institution_name": clean_text(root.get("institution_name")),
                    "decision_status": "preferred_source_root_identified",
                    "preferred_source_root_url": search_url,
                    "preferred_source_root_type": f"generated_wordpress_media_year_search_api:{term}",
                    "preferred_source_root_title": "",
                }
            )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).drop_duplicates(["unitid", "preferred_source_root_url"], keep="first")


def exlibris_primo_collection_page_url(value: object) -> bool:
    parsed = urlparse(clean_text(value))
    return "exlibrisgroup.com" in parsed.netloc.lower() and "/discovery/collectiondiscovery" in parsed.path.lower()


def primo_catalog_search_name(value: object) -> str:
    name = clean_text(value)
    name = re.sub(r"\s*-\s*main\s+campus$", "", name, flags=re.I)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def exlibris_primo_pnxs_search_url(collection_url: str, institution_name: str, *, offset: int = 0, limit: int = 100) -> str:
    parsed = urlparse(clean_text(collection_url))
    if not parsed.scheme or not parsed.netloc:
        return ""
    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    vid = clean_text(params.get("vid"))
    inst = clean_text(params.get("inst"))
    query_name = primo_catalog_search_name(institution_name)
    if not vid or not inst or not query_name:
        return ""
    search_params = {
        "offset": str(offset),
        "inst": inst,
        "limit": str(limit),
        "vid": vid,
        "scope": "browse_search",
        "tab": "default_tab",
        "q": f"any,contains,{query_name} Catalog",
        "qInclude": "",
        "qExclude": "",
        "lang": "en",
        "sort": "date_d",
        "rtaLinks": "true",
        "disableCache": "false",
        "getMore": "0",
        "skipDelivery": "Y",
    }
    return urlunparse(parsed._replace(path="/primaws/rest/pub/pnxs", query=urlencode(search_params), fragment=""))


def exlibris_primo_search_archive_pages(
    archive_pages: pd.DataFrame,
    result_by_url: dict[str, dict[str, object]],
    *,
    timeout_seconds: int,
    max_offsets_per_collection: int = 2,
    repo_root: Path | None = None,
    source_slug: str = "exlibris-primo-pnxs",
) -> tuple[pd.DataFrame, dict[str, dict[str, object]]]:
    if archive_pages.empty or max_offsets_per_collection <= 0:
        return pd.DataFrame(), result_by_url
    rows: list[dict[str, object]] = []
    expanded_results = dict(result_by_url)
    seen_unitids: set[int] = set()
    for _, page in archive_pages.iterrows():
        unitid_value = pd.to_numeric(pd.Series([page.get("unitid")]), errors="coerce").iloc[0]
        if pd.isna(unitid_value):
            continue
        unitid = int(unitid_value)
        if unitid in seen_unitids:
            continue
        page_url = clean_text(page.get("archive_url"))
        result = result_by_url.get(page_url, {})
        collection_url = clean_text(result.get("final_url")) or clean_text(page.get("final_url")) or page_url
        if not exlibris_primo_collection_page_url(collection_url):
            continue
        seen_unitids.add(unitid)
        for offset_index in range(max_offsets_per_collection):
            offset = offset_index * 100
            api_url = exlibris_primo_pnxs_search_url(
                collection_url,
                clean_text(page.get("institution_name")),
                offset=offset,
                limit=100,
            )
            if not api_url:
                continue
            api_result = retrieve_url(
                api_url,
                timeout_seconds=max(timeout_seconds, 6),
                max_bytes=1_500_000,
            )
            expanded_results[api_url] = api_result
            local_source_path = ""
            body = api_result.get("body") if isinstance(api_result.get("body"), bytes) else b""
            if repo_root is not None and clean_text(api_result.get("retrieval_status")) == "retrieved" and body:
                local_source_path = str(
                    save_source_body(
                        repo_root,
                        f"{source_slug}-primo-{unitid}-{offset_index:02d}",
                        "pnxs_search",
                        api_url,
                        clean_text(api_result.get("content_type")),
                        body,
                    )
                )
            rows.append(
                {
                    "batch3_rank": int(pd.to_numeric(pd.Series([page.get("batch3_rank")]), errors="coerce").fillna(0).iloc[0]),
                    "unitid": unitid,
                    "institution_name": clean_text(page.get("institution_name")),
                    "preferred_source_root_url": collection_url,
                    "archive_url": api_url,
                    "archive_source": "exlibris_primo_pnxs_catalog_search_api",
                    "archive_link_text": f"Ex Libris Primo PNX catalog search offset {offset}",
                    "retrieval_status": clean_text(api_result.get("retrieval_status")),
                    "http_status": clean_text(api_result.get("http_status")),
                    "final_url": clean_text(api_result.get("final_url")) or api_url,
                    "content_type": clean_text(api_result.get("content_type")),
                    "page_title": clean_text(api_result.get("page_title")),
                    "year_hints": clean_text(api_result.get("year_hints")),
                    "link_count": len(api_result.get("link_records", [])),
                    "local_source_path": local_source_path,
                    "created_at": utc_now(),
                }
            )
    if not rows:
        return pd.DataFrame(), expanded_results
    return pd.DataFrame(rows), expanded_results


def write_archive_expansion_summary(
    path: Path,
    *,
    sector: str,
    outputs: ArchiveExpansionOutputs,
    seed_roots: pd.DataFrame,
    archive_pages: pd.DataFrame,
    candidates: pd.DataFrame,
    final_status: pd.DataFrame,
) -> None:
    added_years = int(final_status["ai_added_years"].sum()) if not final_status.empty and "ai_added_years" in final_status else 0
    lines = [
        f"# {sector.title()} Clean No-Legacy Archive Expansion Rescue",
        "",
        f"Generated at: {utc_now()}",
        "",
        "Scope: deeper crawl of clean-discovered catalog roots, archive pages, and clean panel URLs. Human legacy URLs remain withheld.",
        "",
        "## Bottom Line",
        "",
        f"- Clean seed roots/archive pages used: {len(seed_roots)}",
        f"- Expanded archive pages retrieved/checked: {len(archive_pages)}",
        f"- Retrieved expanded institution-year candidates kept: {len(candidates)}",
        f"- Candidate institution-year URLs added after archive expansion: {added_years}",
        "",
        "## Outputs",
        "",
    ]
    for label, output_path in outputs.__dict__.items():
        lines.append(f"- {label}: `{output_path}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_archive_expansion_rescue_for_sector(
    repo_root: Path,
    sector: str,
    *,
    timeout_seconds: int = 4,
    max_archive_pages_per_institution: int = 80,
    max_seed_roots_per_institution: int = 12,
    max_workers: int = 12,
) -> ArchiveExpansionOutputs:
    repo_root = repo_root.resolve()
    first = stream_outputs(repo_root, sector)
    first_status = read_checkpoint(first.institution_status_csv)
    current_panel = read_latest_full_year_panel(
        repo_root,
        sector,
        include_inferred=True,
        include_archive_expansion=False,
        include_wayback_cdx=False,
        include_ai_rescue=False,
        include_ai_year_gap=False,
    )
    current_panel = normalize_full_year_panel_for_rescue(current_panel) if not current_panel.empty else current_panel
    outputs = archive_expansion_outputs(repo_root, sector)
    for output_path in outputs.__dict__.values():
        output_path.parent.mkdir(parents=True, exist_ok=True)
    seed_roots = archive_expansion_seed_roots(
        repo_root,
        sector,
        current_panel,
        max_seed_roots_per_institution=max_seed_roots_per_institution,
    )
    wp_year_search_roots = wordpress_media_year_search_seed_roots(seed_roots, current_panel)
    if not wp_year_search_roots.empty:
        seed_roots = pd.concat([seed_roots, wp_year_search_roots], ignore_index=True).drop_duplicates(
            ["unitid", "preferred_source_root_url"],
            keep="first",
        )
    print(f"[archive-expansion] {sector} seed_roots={len(seed_roots)}", flush=True)
    seed_roots.to_csv(outputs.archive_expansion_seed_roots_csv, index=False)
    print(f"[archive-expansion] {sector} fetching archive pages", flush=True)
    archive_pages, result_by_url = (
        build_archive_pages_concurrent(
            repo_root,
            seed_roots,
            timeout_seconds=timeout_seconds,
            max_archive_pages_per_institution=max_archive_pages_per_institution,
            max_workers=max_workers,
            source_slug=stream_id_for_sector(sector).replace("_", "-") + "-archive-expansion",
        )
        if not seed_roots.empty
        else (pd.DataFrame(), {})
    )
    print(f"[archive-expansion] {sector} archive_pages={len(archive_pages)}", flush=True)
    primo_pages, result_by_url = exlibris_primo_search_archive_pages(
        archive_pages,
        result_by_url,
        timeout_seconds=timeout_seconds,
        repo_root=repo_root,
        source_slug=stream_id_for_sector(sector).replace("_", "-") + "-archive-expansion",
    )
    if not primo_pages.empty:
        archive_pages = pd.concat([archive_pages, primo_pages], ignore_index=True, sort=False)
        print(f"[archive-expansion] {sector} exlibris_primo_pages={len(primo_pages)}", flush=True)
    archive_pages.to_csv(outputs.archive_expansion_pages_csv, index=False)
    print(f"[archive-expansion] {sector} building year candidates", flush=True)
    candidates = build_year_candidates(archive_pages, result_by_url) if not archive_pages.empty else pd.DataFrame()
    if not candidates.empty:
        candidates["candidate_source_method"] = "clean_archive_expansion"
        candidates = filter_candidate_rows(candidates)
    print(f"[archive-expansion] {sector} candidates={len(candidates)}", flush=True)
    final_panel = merge_final_panel(current_panel, candidates) if not current_panel.empty else current_panel
    final_status = build_final_status(first_status, final_panel, pd.DataFrame(), pd.DataFrame())
    print(f"[archive-expansion] {sector} writing outputs", flush=True)
    candidates.to_csv(outputs.archive_expansion_candidates_csv, index=False)
    final_panel.to_csv(outputs.archive_expansion_panel_csv, index=False)
    final_status.to_csv(outputs.archive_expansion_status_csv, index=False)
    write_workbook(
        outputs.workbook,
        {
            "start_here": final_status,
            "archive_expansion_seed_roots": seed_roots,
            "archive_expansion_pages": archive_pages,
            "archive_expansion_candidates": candidates,
            "archive_expansion_year_panel": final_panel,
            "current_panel_before_archive_expansion": current_panel,
        },
    )
    write_archive_expansion_summary(
        outputs.summary_md,
        sector=sector,
        outputs=outputs,
        seed_roots=seed_roots,
        archive_pages=archive_pages,
        candidates=candidates,
        final_status=final_status,
    )
    return outputs


def cached_archive_page_result(page: pd.Series) -> dict[str, object]:
    archive_url = clean_text(page.get("archive_url"))
    final_url = clean_text(page.get("final_url")) or archive_url
    content_type = clean_text(page.get("content_type"))
    body = b""
    local_source_path = clean_text(page.get("local_source_path"))
    if local_source_path:
        path = Path(local_source_path)
        if path.exists() and path.is_file():
            body = path.read_bytes()
    text = decode_body(body, content_type) if body else ""
    link_records = extract_link_records(text, final_url, content_type) if text else []
    return {
        "retrieval_status": clean_text(page.get("retrieval_status")),
        "http_status": clean_text(page.get("http_status")),
        "final_url": final_url,
        "content_type": content_type,
        "content_length_bytes": len(body) if body else clean_text(page.get("content_length_bytes")),
        "page_title": clean_text(page.get("page_title")),
        "year_hints": clean_text(page.get("year_hints")),
        "body": body,
        "links": [record["url"] for record in link_records],
        "link_records": link_records,
    }


def rebuild_archive_expansion_rescue_from_cache_for_sector(repo_root: Path, sector: str) -> ArchiveExpansionOutputs:
    repo_root = repo_root.resolve()
    first = stream_outputs(repo_root, sector)
    first_status = read_checkpoint(first.institution_status_csv)
    current_panel = read_latest_full_year_panel(
        repo_root,
        sector,
        include_inferred=True,
        include_archive_expansion=False,
        include_wayback_cdx=False,
        include_ai_rescue=False,
        include_ai_year_gap=False,
    )
    current_panel = normalize_full_year_panel_for_rescue(current_panel) if not current_panel.empty else current_panel
    outputs = archive_expansion_outputs(repo_root, sector)
    archive_pages = read_checkpoint(outputs.archive_expansion_pages_csv)
    print(f"[archive-expansion-cache] {sector} archive_pages={len(archive_pages)}", flush=True)
    result_by_url = {
        clean_text(page.get("archive_url")): cached_archive_page_result(page)
        for _, page in archive_pages.iterrows()
        if clean_text(page.get("archive_url"))
    }
    candidates = build_year_candidates(archive_pages, result_by_url) if not archive_pages.empty else pd.DataFrame()
    if not candidates.empty:
        candidates["candidate_source_method"] = "clean_archive_expansion"
        candidates = filter_candidate_rows(candidates)
    print(f"[archive-expansion-cache] {sector} candidates={len(candidates)}", flush=True)
    final_panel = merge_final_panel(current_panel, candidates) if not current_panel.empty else current_panel
    final_status = build_final_status(first_status, final_panel, pd.DataFrame(), pd.DataFrame())
    candidates.to_csv(outputs.archive_expansion_candidates_csv, index=False)
    final_panel.to_csv(outputs.archive_expansion_panel_csv, index=False)
    final_status.to_csv(outputs.archive_expansion_status_csv, index=False)
    return outputs


def wayback_original_url(url: str) -> str:
    parsed = urlparse(clean_text(url))
    if parsed.netloc.lower() != "web.archive.org":
        return clean_text(url)
    match = re.match(r"^/web/\d{6,14}(?:[a-z_]+)?/(.+)$", parsed.path)
    if not match:
        return ""
    original = match.group(1)
    if parsed.query:
        original = f"{original}?{parsed.query}"
    lowered = original.lower()
    for scheme in ("http", "https"):
        malformed_prefix = f"{scheme}:///"
        if lowered.startswith(malformed_prefix):
            return f"{scheme}://" + original[len(malformed_prefix) :].lstrip("/")
    if original.startswith(("http://", "https://")):
        return original
    if original.startswith("http:/"):
        return "http://" + original[len("http:/") :].lstrip("/")
    if original.startswith("https:/"):
        return "https://" + original[len("https:/") :].lstrip("/")
    return original


def dedupe_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def wayback_cdx_query_url(target: str, *, from_year: int = 1998, to_year: int = 2022, limit: int = 20) -> str:
    query = (
        f"url={quote(target, safe='')}"
        "&output=json&fl=timestamp,original,mimetype,statuscode,digest"
        "&filter=statuscode:200&collapse=urlkey"
        f"&from={from_year}&to={to_year}&limit={limit}"
    )
    return f"http://web.archive.org/cdx?{query}"


def wayback_cdx_query_targets_from_url(url: str) -> list[str]:
    original = wayback_original_url(url)
    parsed = urlparse(original)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return []
    path = parsed.path or "/"
    path_lower = path.lower()
    queryless = parsed._replace(params="", query="", fragment="")
    targets: list[str] = []

    def root_target(candidate_path: str) -> str:
        if not candidate_path.startswith("/"):
            candidate_path = "/" + candidate_path
        if not candidate_path.endswith("/"):
            candidate_path = candidate_path.rsplit("/", 1)[0] + "/"
        return urlunparse(queryless._replace(path=candidate_path)) + "*"

    if path_lower.endswith((".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".jpg", ".jpeg", ".png")):
        targets.append(root_target(path))
    elif catalog_year_range(original):
        targets.append(root_target(path))
    elif path in {"", "/"}:
        targets.append(urlunparse(queryless._replace(path="/")) + "*")
    elif any(term in f"{parsed.netloc.lower()} {path_lower}" for term in ["catalog", "catalogue", "bulletin", "coursecatalog", "academiccatalog"]):
        clean_path = path if path.endswith("/") else path + "/"
        targets.append(urlunparse(queryless._replace(path=clean_path)) + "*")
        parent = path.rstrip("/").rsplit("/", 1)[0] + "/"
        if parent != clean_path:
            targets.append(urlunparse(queryless._replace(path=parent)) + "*")
    else:
        targets.append(urlunparse(queryless._replace(path="/")) + "*")

    if parsed.scheme == "https":
        targets.extend(target.replace("https://", "http://", 1) for target in list(targets))
    elif parsed.scheme == "http":
        targets.extend(target.replace("http://", "https://", 1) for target in list(targets))
    return dedupe_preserving_order(targets)


def is_wayback_cdx_seed_url(url: str, *, source_detail: str = "") -> bool:
    cleaned = clean_text(url)
    if not cleaned.startswith(("http://", "https://")):
        return False
    lowered = f"{cleaned} {source_detail}".lower()
    if any(term in lowered for term in ["calendar", "tuition", "financial-aid", "financial_aid", "admission", "athletic"]):
        return False
    return any(
        term in lowered
        for term in [
            "catalog",
            "catalogue",
            "bulletin",
            "coursecatalog",
            "academiccatalog",
            "undergraduate-catalog",
            "undergraduate_catalog",
            "registrar",
        ]
    )


def wayback_cdx_seed_priority(row: pd.Series) -> int:
    source_label = clean_text(row.get("seed_source"))
    detail = clean_text(row.get("seed_source_detail")).lower()
    url = clean_text(row.get("seed_url")).lower()
    retrieved = clean_text(row.get("retrieval_status")).lower() in RETRIEVED_STATUSES
    likely = bool(row.get("likely_catalog_root", False))
    if likely and retrieved:
        return 0
    if "catalog_subdomain" in detail or "coursecatalog_subdomain" in detail or "bulletin_subdomain" in detail:
        return 1
    if source_label in {"first_pass_preferred_root", "current_panel_archive_url"}:
        return 2
    if retrieved:
        return 3
    if "archive" in url or "archive" in detail:
        return 4
    return 5


def wayback_cdx_seed_roots(
    repo_root: Path,
    sector: str,
    current_panel: pd.DataFrame,
    *,
    max_seed_roots_per_institution: int = 8,
) -> pd.DataFrame:
    """Build clean CDX seed targets from generated/current pipeline outputs only."""
    first = stream_outputs(repo_root, sector)
    status = read_checkpoint(first.institution_status_csv)
    missing_context = pd.DataFrame()
    if not current_panel.empty:
        panel = current_panel.copy()
        panel["unitid"] = pd.to_numeric(panel["unitid"], errors="coerce").astype("Int64")
        panel["target_year"] = pd.to_numeric(panel["target_year"], errors="coerce").astype("Int64")
        panel["best_url"] = panel.get("best_url", pd.Series("", index=panel.index)).fillna("").map(clean_text)
        rows = []
        for unitid, group in panel.groupby("unitid", dropna=False):
            if pd.isna(unitid):
                continue
            missing = sorted(set(group.loc[group["best_url"].eq(""), "target_year"].dropna().astype(int).tolist()))
            observed = sorted(set(group.loc[group["best_url"].ne(""), "target_year"].dropna().astype(int).tolist()))
            if missing:
                rows.append(
                    {
                        "unitid": int(unitid),
                        "missing_target_years": "; ".join(map(str, missing)),
                        "observed_candidate_years": "; ".join(map(str, observed)),
                        "missing_target_year_count": len(missing),
                    }
                )
        missing_context = pd.DataFrame(rows)
    if missing_context.empty:
        return pd.DataFrame()

    frames: list[pd.DataFrame] = []

    def add_seed_frame(frame: pd.DataFrame, url_column: str, detail_column: str, source_label: str) -> None:
        if frame.empty or url_column not in frame.columns:
            return
        out = frame.copy()
        out["unitid"] = pd.to_numeric(out["unitid"], errors="coerce").astype("Int64")
        out["seed_url"] = out[url_column].map(clean_text)
        out["seed_source"] = source_label
        out["seed_source_detail"] = out[detail_column].map(clean_text) if detail_column in out.columns else ""
        if "institution_name" not in out.columns:
            out["institution_name"] = ""
        if "retrieval_status" not in out.columns:
            out["retrieval_status"] = ""
        if "likely_catalog_root" not in out.columns:
            out["likely_catalog_root"] = False
        out = out.loc[out["unitid"].notna() & out["seed_url"].map(is_wayback_cdx_seed_url)].copy()
        if not out.empty:
            frames.append(
                out[
                    [
                        "unitid",
                        "institution_name",
                        "seed_url",
                        "seed_source",
                        "seed_source_detail",
                        "retrieval_status",
                        "likely_catalog_root",
                    ]
                ]
            )

    roots = read_checkpoint(first.source_root_decisions_csv)
    if not roots.empty:
        roots = roots.loc[roots.get("decision_status", pd.Series("", index=roots.index)).map(clean_text).eq("preferred_source_root_identified")].copy()
        add_seed_frame(roots, "preferred_source_root_url", "preferred_source_root_type", "first_pass_preferred_root")

    root_candidates = read_checkpoint(first.root_candidates_csv)
    add_seed_frame(root_candidates, "candidate_url", "candidate_source_type", "generated_root_candidate")

    archive_inputs = [
        (read_checkpoint(first.archive_pages_csv), "archive_url", "archive_source", "first_pass_archive_page"),
        (
            read_checkpoint(ai_rescue_outputs(repo_root, sector).ai_archive_pages_csv),
            "archive_url",
            "archive_source",
            "ai_rescue_archive_page",
        ),
        (
            read_checkpoint(ai_year_gap_outputs(repo_root, sector).ai_year_gap_archive_pages_csv),
            "archive_url",
            "archive_source",
            "ai_year_gap_archive_page",
        ),
        (
            read_checkpoint(archive_expansion_outputs(repo_root, sector).archive_expansion_pages_csv),
            "archive_url",
            "archive_source",
            "archive_expansion_archive_page",
        ),
    ]
    for frame, url_column, detail_column, source_label in archive_inputs:
        add_seed_frame(frame, url_column, detail_column, source_label)

    if not current_panel.empty:
        add_seed_frame(current_panel, "best_url", "best_url_source", "current_panel_best_url")
        add_seed_frame(current_panel, "archive_url", "best_url_source", "current_panel_archive_url")

    seeds = concat_frames(frames)
    if seeds.empty:
        return pd.DataFrame()
    seeds["unitid"] = pd.to_numeric(seeds["unitid"], errors="coerce").astype("Int64")
    seeds = seeds.merge(missing_context, on="unitid", how="inner")
    if status.empty:
        seeds["batch3_rank"] = 0
    else:
        status_keep = status[[column for column in ["unitid", "batch3_rank", "fresh_rank", "institution_name"] if column in status.columns]].copy()
        status_keep["unitid"] = pd.to_numeric(status_keep["unitid"], errors="coerce").astype("Int64")
        status_keep = status_keep.drop_duplicates("unitid", keep="last")
        seeds = seeds.merge(status_keep, on="unitid", how="left", suffixes=("", "_status"))
        if "institution_name_status" in seeds.columns:
            seeds["institution_name"] = seeds["institution_name"].map(clean_text).where(
                seeds["institution_name"].map(clean_text).ne(""),
                seeds["institution_name_status"].map(clean_text),
            )
    if "batch3_rank" not in seeds.columns:
        seeds["batch3_rank"] = seeds.get("fresh_rank", pd.Series(0, index=seeds.index))
    seeds["batch3_rank"] = pd.to_numeric(seeds["batch3_rank"], errors="coerce").fillna(0).astype(int)
    seeds["seed_priority"] = seeds.apply(wayback_cdx_seed_priority, axis=1)

    expanded_rows: list[dict[str, object]] = []
    for _, seed in seeds.iterrows():
        for target in wayback_cdx_query_targets_from_url(clean_text(seed.get("seed_url")))[:2]:
            row = seed.to_dict()
            row["cdx_query_target"] = target
            row["cdx_query_url"] = wayback_cdx_query_url(target)
            expanded_rows.append(row)
    if not expanded_rows:
        return pd.DataFrame()
    expanded = pd.DataFrame(expanded_rows)
    expanded = expanded.drop_duplicates(["unitid", "cdx_query_target"], keep="first")
    expanded = expanded.sort_values(["unitid", "seed_priority", "cdx_query_target"])
    if max_seed_roots_per_institution > 0:
        expanded = expanded.groupby("unitid", group_keys=False).head(max_seed_roots_per_institution).copy()
    keep = [
        "batch3_rank",
        "unitid",
        "institution_name",
        "missing_target_years",
        "observed_candidate_years",
        "missing_target_year_count",
        "seed_url",
        "seed_source",
        "seed_source_detail",
        "retrieval_status",
        "likely_catalog_root",
        "seed_priority",
        "cdx_query_target",
        "cdx_query_url",
    ]
    for column in keep:
        if column not in expanded.columns:
            expanded[column] = ""
    return expanded[keep].sort_values(["batch3_rank", "unitid", "seed_priority", "cdx_query_target"])


def timestamp_in_academic_year(timestamp: str, target_year: int) -> bool:
    if not re.match(r"^\d{8,14}$", clean_text(timestamp)):
        return False
    year = int(timestamp[:4])
    month = int(timestamp[4:6])
    return (year == target_year and month >= 7) or (year == target_year + 1 and month <= 8)


def timestamp_distance_to_academic_year(timestamp: str, target_year: int) -> int:
    if not re.match(r"^\d{8,14}$", clean_text(timestamp)):
        return 999
    year = int(timestamp[:4])
    month = int(timestamp[4:6])
    target_month_index = target_year * 12 + 10
    stamp_month_index = year * 12 + month
    return abs(stamp_month_index - target_month_index)


def year_range_covers_target(year_range: tuple[int, int] | None, target_year: int) -> bool:
    if not year_range:
        return False
    start, end = year_range
    return start <= target_year < end or start == target_year


def cdx_candidate_score(original_url: str, mimetype: str, timestamp: str, target_year: int) -> tuple[int, str]:
    lowered = clean_text(original_url).lower()
    path = urlparse(lowered).path
    if not any(term in lowered for term in ["catalog", "catalogue", "bulletin", "coursecatalog", "academiccatalog"]):
        return -1000, "not_catalogish_url"
    if any(term in lowered for term in ["calendar", "tuition", "admission", "financial", "athletic", "directory", "faculty"]):
        return -1000, "wrong_scope_url"
    if any(term in path for term in ["/courses/", "/course-descriptions", "/course_descriptions", "/programs/", "/majors/", "/minors/"]):
        return -1000, "catalog_child_wrong_scope"
    score = 0
    reason = "timestamp_catalog_candidate"
    explicit = catalog_year_range(original_url)
    if year_range_covers_target(explicit, target_year):
        score += 300
        reason = "explicit_url_year"
    elif explicit:
        score -= 80
    if str(target_year) in lowered or str(target_year + 1) in lowered:
        score += 70
    if timestamp_in_academic_year(timestamp, target_year):
        score += 70
        if reason == "timestamp_catalog_candidate":
            reason = "timestamp_in_academic_year"
    else:
        distance = timestamp_distance_to_academic_year(timestamp, target_year)
        score += max(-40, 40 - distance * 4)
    if "pdf" in clean_text(mimetype).lower() or urlparse(lowered).path.endswith(".pdf"):
        score += 25
    elif "html" in clean_text(mimetype).lower() or urlparse(lowered).path.endswith((".html", ".htm", ".php", ".asp", ".aspx", "/")):
        score += 10
    if "undergrad" in lowered:
        score += 20
    if "archive" in lowered or "archives" in lowered:
        score += 10
    return score, reason


def parse_wayback_cdx_rows(
    body: bytes,
    *,
    seed: pd.Series,
    max_candidates_per_year: int = 3,
) -> list[dict[str, object]]:
    try:
        rows = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return []
    if not isinstance(rows, list) or len(rows) < 2:
        return []
    missing_years = parse_years_list(seed.get("missing_target_years"))
    candidates: list[dict[str, object]] = []
    for row in rows[1:]:
        if not isinstance(row, list) or len(row) < 2:
            continue
        timestamp = clean_text(row[0])
        original_url = clean_text(row[1])
        mimetype = clean_text(row[2]) if len(row) > 2 else ""
        status = clean_text(row[3]) if len(row) > 3 else ""
        digest = clean_text(row[4]) if len(row) > 4 else ""
        if status not in {"", "200"} or not timestamp.isdigit() or not original_url.startswith(("http://", "https://")):
            continue
        for target_year in missing_years:
            score, reason = cdx_candidate_score(original_url, mimetype, timestamp, target_year)
            if score < 50:
                continue
            candidates.append(
                {
                    "batch3_rank": int(seed.get("batch3_rank", 0) or 0),
                    "unitid": int(seed["unitid"]),
                    "institution_name": clean_text(seed.get("institution_name")),
                    "target_year": target_year,
                    "seed_url": clean_text(seed.get("seed_url")),
                    "seed_source": clean_text(seed.get("seed_source")),
                    "cdx_query_target": clean_text(seed.get("cdx_query_target")),
                    "cdx_query_url": clean_text(seed.get("cdx_query_url")),
                    "wayback_timestamp": timestamp,
                    "wayback_original_url": original_url,
                    "wayback_mimetype": mimetype,
                    "wayback_digest": digest,
                    "wayback_candidate_score": score,
                    "wayback_match_reason": reason,
                    "snapshot_url": raw_wayback_snapshot_url(f"http://web.archive.org/web/{timestamp}/{original_url}"),
                }
            )
    if not candidates:
        return []
    frame = pd.DataFrame(candidates).sort_values(
        ["unitid", "target_year", "wayback_candidate_score", "snapshot_url"],
        ascending=[True, True, False, True],
    )
    frame = frame.groupby(["unitid", "target_year"], group_keys=False).head(max_candidates_per_year)
    return frame.to_dict("records")


def wayback_snapshot_catalogish(url: str, result: dict[str, object]) -> bool:
    evidence = f"{url} {result.get('page_title', '')} {result.get('year_hints', '')}".lower()
    if any(term in evidence for term in ["calendar", "tuition", "admission", "financial aid", "athletics"]):
        return False
    return any(term in evidence for term in ["catalog", "catalogue", "bulletin", "coursecatalog", "undergraduate"])


def validated_wayback_candidate_row(row: pd.Series, result: dict[str, object]) -> dict[str, object] | None:
    if clean_text(result.get("retrieval_status")) not in RETRIEVED_STATUSES:
        return None
    target_year = int(row["target_year"])
    evidence_text = (
        f"{row.get('wayback_original_url', '')} {row.get('snapshot_url', '')} "
        f"{result.get('page_title', '')} {result.get('year_hints', '')}"
    )
    result_range = None
    start_value = pd.to_numeric(pd.Series([result.get("catalog_year_start")]), errors="coerce").iloc[0]
    end_value = pd.to_numeric(pd.Series([result.get("catalog_year_end")]), errors="coerce").iloc[0]
    if not pd.isna(start_value):
        start = int(start_value)
        end = int(end_value) if not pd.isna(end_value) else start + 1
        result_range = (start, max(end, start + 1))
    explicit_range = result_range or catalog_year_range(evidence_text)
    validation_status = ""
    if year_range_covers_target(explicit_range, target_year):
        validation_status = "wayback_explicit_catalog_year"
    elif timestamp_in_academic_year(clean_text(row.get("wayback_timestamp")), target_year) and wayback_snapshot_catalogish(
        clean_text(row.get("snapshot_url")),
        result,
    ):
        validation_status = "wayback_timestamp_catalog_snapshot"
    else:
        return None
    start, end = explicit_range if explicit_range and year_range_covers_target(explicit_range, target_year) else (target_year, target_year + 1)
    link_text = (
        f"{start}-{end} archived catalog"
        if validation_status == "wayback_explicit_catalog_year"
        else f"Wayback catalog snapshot captured {clean_text(row.get('wayback_timestamp'))[:8]}"
    )
    return {
        "batch3_rank": int(row.get("batch3_rank", 0) or 0),
        "unitid": int(row["unitid"]),
        "institution_name": clean_text(row.get("institution_name")),
        "target_year": target_year,
        "catalog_year_start": start,
        "catalog_year_end": end,
        "academic_year_rule": "AY is the catalog start year; Wayback candidates require explicit year evidence or an in-year catalog snapshot.",
        "candidate_url": clean_text(row.get("snapshot_url")),
        "candidate_link_text": link_text,
        "candidate_evidence_text": (
            f"clean_seed={clean_text(row.get('seed_url'))}; "
            f"cdx_target={clean_text(row.get('cdx_query_target'))}; "
            f"original={clean_text(row.get('wayback_original_url'))}; "
            f"timestamp={clean_text(row.get('wayback_timestamp'))}; "
            f"validation={validation_status}; title={clean_text(result.get('page_title'))}"
        ),
        "candidate_evidence_source": validation_status,
        "archive_url": clean_text(row.get("cdx_query_target")),
        "archive_page_title": "",
        "candidate_scope": "undergraduate_or_university_catalog",
        "validation_status": validation_status,
        "candidate_priority": candidate_priority(evidence_text) if validation_status == "wayback_explicit_catalog_year" else 35,
        "candidate_source_method": "clean_wayback_cdx_content_dating",
        "candidate_retrieval_status": clean_text(result.get("retrieval_status")),
        "candidate_http_status": clean_text(result.get("http_status")),
        "candidate_page_title": clean_text(result.get("page_title")),
        "created_at": utc_now(),
    }


def materialize_wayback_cdx_candidates(
    seeds: pd.DataFrame,
    *,
    timeout_seconds: int,
    max_workers: int,
    max_snapshots_per_institution: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if seeds.empty:
        return pd.DataFrame(), pd.DataFrame()
    lookup_rows: list[dict[str, object]] = []
    raw_candidates: list[dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(retrieve_url, clean_text(seed["cdx_query_url"]), timeout_seconds=timeout_seconds, max_bytes=10 * 1024 * 1024): seed
            for _, seed in seeds.iterrows()
        }
        completed = 0
        for future in as_completed(futures):
            completed += 1
            seed = futures[future]
            result: dict[str, object]
            try:
                result = future.result()
            except Exception as exc:  # pragma: no cover - network failures vary.
                result = {
                    "retrieval_status": "error",
                    "http_status": "",
                    "content_length_bytes": "",
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "body": b"",
                }
            body = result.get("body", b"")
            parsed_candidates = (
                parse_wayback_cdx_rows(body, seed=seed)
                if clean_text(result.get("retrieval_status")) in RETRIEVED_STATUSES and isinstance(body, bytes)
                else []
            )
            raw_candidates.extend(parsed_candidates)
            lookup_rows.append(
                {
                    "unitid": int(seed["unitid"]),
                    "institution_name": clean_text(seed.get("institution_name")),
                    "seed_url": clean_text(seed.get("seed_url")),
                    "cdx_query_target": clean_text(seed.get("cdx_query_target")),
                    "cdx_query_url": clean_text(seed.get("cdx_query_url")),
                    "retrieval_status": clean_text(result.get("retrieval_status")),
                    "http_status": clean_text(result.get("http_status")),
                    "content_length_bytes": result.get("content_length_bytes", ""),
                    "parsed_candidate_count": len(parsed_candidates),
                    "error_type": clean_text(result.get("error_type")),
                    "error_message": clean_text(result.get("error_message")),
                    "created_at": utc_now(),
                }
            )
            if completed % 50 == 0 or completed == len(futures):
                print(f"[wayback-cdx] completed {completed}/{len(futures)} CDX lookups", flush=True)
    lookups = pd.DataFrame(lookup_rows)
    if not raw_candidates:
        return lookups, pd.DataFrame()
    raw = pd.DataFrame(raw_candidates).sort_values(
        ["unitid", "target_year", "wayback_candidate_score", "snapshot_url"],
        ascending=[True, True, False, True],
    )
    raw = raw.drop_duplicates(["unitid", "target_year", "snapshot_url"], keep="first")
    raw = raw.groupby(["unitid", "target_year"], group_keys=False).head(2).copy()
    if max_snapshots_per_institution > 0:
        raw = raw.sort_values(["unitid", "wayback_candidate_score", "target_year"], ascending=[True, False, True])
        raw = raw.groupby("unitid", group_keys=False).head(max_snapshots_per_institution).copy()

    snapshot_urls = sorted(raw["snapshot_url"].dropna().map(clean_text).unique())
    result_by_url: dict[str, dict[str, object]] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(retrieve_url, url, timeout_seconds=timeout_seconds, max_bytes=500_000): url
            for url in snapshot_urls
        }
        completed = 0
        for future in as_completed(futures):
            completed += 1
            url = futures[future]
            try:
                result_by_url[url] = future.result()
            except Exception as exc:  # pragma: no cover - network failures vary.
                result_by_url[url] = {
                    "retrieval_status": "error",
                    "http_status": "",
                    "page_title": "",
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                }
            if completed % 50 == 0 or completed == len(futures):
                print(f"[wayback-cdx] retrieved {completed}/{len(futures)} candidate snapshots", flush=True)
    rows = []
    for _, raw_row in raw.iterrows():
        validated = validated_wayback_candidate_row(raw_row, result_by_url.get(clean_text(raw_row["snapshot_url"]), {}))
        if validated:
            rows.append(validated)
    candidates = pd.DataFrame(rows)
    if not candidates.empty:
        candidates = candidates.drop_duplicates(["unitid", "target_year", "candidate_url"], keep="first")
    return lookups, candidates


def replay_validated_wayback_cdx_cache(repo_root: Path, sector: str, current_panel: pd.DataFrame) -> pd.DataFrame:
    """Replay validated external-archive candidates for current missing panel rows."""
    cache_path = repo_root / WAYBACK_CDX_VALIDATED_CACHE
    cache = read_checkpoint(cache_path)
    if cache.empty or current_panel.empty:
        return pd.DataFrame()
    current = current_panel.copy()
    current["unitid"] = pd.to_numeric(current["unitid"], errors="coerce").astype("Int64")
    current["target_year"] = pd.to_numeric(current["target_year"], errors="coerce").astype("Int64")
    current["best_url"] = current.get("best_url", pd.Series("", index=current.index)).fillna("").map(clean_text)
    missing = current.loc[current["best_url"].eq(""), ["unitid", "target_year"]].dropna().copy()
    if missing.empty:
        return pd.DataFrame()

    cache = cache.copy()
    cache["unitid"] = pd.to_numeric(cache["unitid"], errors="coerce").astype("Int64")
    cache["target_year"] = pd.to_numeric(cache["target_year"], errors="coerce").astype("Int64")
    if "source_stream" in cache.columns:
        stream_id = stream_id_for_sector(sector)
        cache = cache.loc[cache["source_stream"].fillna("").map(clean_text).eq(stream_id)].copy()
    elif "sector" in cache.columns:
        cache = cache.loc[cache["sector"].fillna("").map(clean_text).eq(sector)].copy()
    cache = cache.merge(missing, on=["unitid", "target_year"], how="inner")
    if cache.empty:
        return pd.DataFrame()

    defaults = {
        "candidate_source_method": "cached_wayback_cdx_validated_candidate",
        "candidate_evidence_source": "cached_wayback_cdx_validated_candidate",
        "candidate_scope": "undergraduate_or_university_catalog",
        "validation_status": "cached_wayback_cdx_validated_candidate",
        "candidate_retrieval_status": "retrieved",
        "candidate_http_status": "200",
        "created_at": utc_now(),
    }
    for column, value in defaults.items():
        if column not in cache.columns:
            cache[column] = value
        else:
            cache[column] = cache[column].fillna("").map(clean_text).replace("", value)
    if "candidate_priority" not in cache.columns:
        cache["candidate_priority"] = 0
    cache["candidate_priority"] = pd.to_numeric(cache["candidate_priority"], errors="coerce").fillna(0).astype(int)
    cache["cache_replay_status"] = "replayed_validated_external_evidence"
    cache["cache_source_path"] = str(cache_path)
    return cache


def write_wayback_cdx_summary(
    path: Path,
    *,
    sector: str,
    outputs: WaybackCdxOutputs,
    seed_roots: pd.DataFrame,
    lookups: pd.DataFrame,
    candidates: pd.DataFrame,
    final_status: pd.DataFrame,
) -> None:
    added_years = int(final_status["ai_added_years"].sum()) if not final_status.empty and "ai_added_years" in final_status else 0
    lines = [
        f"# {sector.title()} Clean No-Legacy Wayback CDX Rescue",
        "",
        f"Generated at: {utc_now()}",
        "",
        "Scope: CDX lookup and snapshot validation from clean-generated catalog roots only. Human legacy URLs remain withheld.",
        "",
        "## Bottom Line",
        "",
        f"- Clean CDX seed targets used: {len(seed_roots)}",
        f"- CDX lookups completed: {len(lookups)}",
        f"- Retrieved/validated Wayback institution-year candidates kept: {len(candidates)}",
        f"- Candidate institution-year URLs added after Wayback CDX rescue: {added_years}",
        "",
        "## Outputs",
        "",
    ]
    for label, output_path in outputs.__dict__.items():
        lines.append(f"- {label}: `{output_path}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_wayback_cdx_rescue_for_sector(
    repo_root: Path,
    sector: str,
    *,
    timeout_seconds: int = 8,
    max_seed_roots_per_institution: int = 8,
    max_snapshots_per_institution: int = 12,
    max_workers: int = 8,
) -> WaybackCdxOutputs:
    repo_root = repo_root.resolve()
    first = stream_outputs(repo_root, sector)
    first_status = read_checkpoint(first.institution_status_csv)
    current_panel = read_latest_full_year_panel(
        repo_root,
        sector,
        include_inferred=True,
        include_archive_expansion=True,
        include_wayback_cdx=False,
        include_ai_rescue=False,
        include_ai_year_gap=False,
    )
    current_panel = normalize_full_year_panel_for_rescue(current_panel) if not current_panel.empty else current_panel
    outputs = wayback_cdx_outputs(repo_root, sector)
    for output_path in outputs.__dict__.values():
        output_path.parent.mkdir(parents=True, exist_ok=True)
    seed_roots = wayback_cdx_seed_roots(
        repo_root,
        sector,
        current_panel,
        max_seed_roots_per_institution=max_seed_roots_per_institution,
    )
    seed_roots.to_csv(outputs.wayback_cdx_seed_roots_csv, index=False)
    lookups, candidates = materialize_wayback_cdx_candidates(
        seed_roots,
        timeout_seconds=timeout_seconds,
        max_workers=max_workers,
        max_snapshots_per_institution=max_snapshots_per_institution,
    )
    lookups.to_csv(outputs.wayback_cdx_lookups_csv, index=False)
    cached_candidates = replay_validated_wayback_cdx_cache(repo_root, sector, current_panel)
    if not cached_candidates.empty:
        candidates = concat_frames([candidates, cached_candidates])
    if not candidates.empty:
        candidates = filter_candidate_rows(candidates)
    final_panel = merge_final_panel(current_panel, candidates) if not current_panel.empty else current_panel
    final_status = build_final_status(first_status, final_panel, pd.DataFrame(), pd.DataFrame())
    candidates.to_csv(outputs.wayback_cdx_candidates_csv, index=False)
    final_panel.to_csv(outputs.wayback_cdx_panel_csv, index=False)
    final_status.to_csv(outputs.wayback_cdx_status_csv, index=False)
    write_workbook(
        outputs.workbook,
        {
            "start_here": final_status,
            "wayback_cdx_seed_roots": seed_roots,
            "wayback_cdx_lookups": lookups,
            "wayback_cdx_candidates": candidates,
            "wayback_cdx_year_panel": final_panel,
            "current_panel_before_wayback": current_panel,
        },
    )
    write_wayback_cdx_summary(
        outputs.summary_md,
        sector=sector,
        outputs=outputs,
        seed_roots=seed_roots,
        lookups=lookups,
        candidates=candidates,
        final_status=final_status,
    )
    return outputs


def write_discovery_summary(
    path: Path,
    *,
    sector: str,
    institutions: pd.DataFrame,
    status: pd.DataFrame,
    year_panel: pd.DataFrame,
    outputs: HoldoutStreamOutputs,
) -> None:
    counts = status["fresh_discovery_status"].value_counts().to_dict() if not status.empty else {}
    rows_with_url = int(year_panel["best_url"].map(clean_text).ne("").sum()) if not year_panel.empty else 0
    lines = [
        f"# {sector.title()} Clean No-Legacy Holdout Discovery",
        "",
        f"Generated at: {utc_now()}",
        "",
        "Scope: clean benchmark discovery with human legacy URLs, legacy excerpts, and legacy classifications withheld.",
        "",
        "## Bottom Line",
        "",
        f"- Institutions processed: {status['unitid'].nunique() if not status.empty else 0}",
        f"- Institution-year rows with candidate URL: {rows_with_url}",
        f"- Institutions with explicit year candidates: {int(counts.get('year_candidates_found', 0))}",
        f"- Institutions with source root but no explicit years: {int(counts.get('source_root_found_no_explicit_years', 0))}",
        f"- Institutions with retrieved non-catalog roots only: {int(counts.get('root_candidates_retrieved_but_not_catalog', 0))}",
        f"- Institutions with no retrieved source root: {int(counts.get('source_root_not_found', 0))}",
        "",
        "## Outputs",
        "",
    ]
    for label, output_path in outputs.__dict__.items():
        lines.append(f"- {label}: `{output_path}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_discovery_for_sector(
    repo_root: Path,
    sector: str,
    *,
    limit: int | None,
    rank_start: int,
    timeout_seconds: int,
    max_root_candidates_per_institution: int,
    max_archive_pages_per_institution: int,
    max_workers: int,
    chunk_size: int,
    resume: bool = True,
    skip_network_preflight: bool = False,
) -> HoldoutStreamOutputs:
    repo_root = repo_root.resolve()
    stream_id = stream_id_for_sector(sector)
    ensure_stream_workspace(repo_root, [stream_id])
    outputs = stream_outputs(repo_root, sector)
    for path in outputs.__dict__.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    institutions = read_discovery_input(repo_root, sector, limit=limit, rank_start=rank_start)
    legacy_leads = empty_legacy_leads()

    existing_institutions = read_checkpoint(outputs.institutions_csv) if resume else pd.DataFrame()
    existing_status = read_checkpoint(outputs.institution_status_csv) if resume else pd.DataFrame()
    already_processed = (
        set(pd.to_numeric(existing_status.get("unitid", pd.Series(dtype=object)), errors="coerce").dropna().astype(int))
        if not existing_status.empty
        else set()
    )
    if already_processed:
        institutions = institutions.loc[~pd.to_numeric(institutions["unitid"], errors="coerce").astype("Int64").isin(already_processed)].copy()
    checkpoint_institutions = concat_frames([existing_institutions, institutions])
    if not checkpoint_institutions.empty:
        checkpoint_institutions = checkpoint_institutions.sort_values(["fresh_rank", "unitid"]).drop_duplicates("unitid", keep="last")

    if len(institutions) and not skip_network_preflight:
        assert_network_preflight(timeout_seconds)
    if len(institutions) and not resume:
        archived = archive_existing_stream_outputs(outputs, reason="pre_reset")
        if archived:
            print(f"{stream_id}: archived {len(archived)} existing output file(s) before reset", flush=True)

    root_frames: list[pd.DataFrame] = [read_checkpoint(outputs.root_candidates_csv)] if resume else []
    decision_frames: list[pd.DataFrame] = [read_checkpoint(outputs.source_root_decisions_csv)] if resume else []
    archive_frames: list[pd.DataFrame] = [read_checkpoint(outputs.archive_pages_csv)] if resume else []
    year_candidate_frames: list[pd.DataFrame] = [read_checkpoint(outputs.year_candidates_csv)] if resume else []
    year_panel_frames: list[pd.DataFrame] = [read_checkpoint(outputs.year_panel_csv)] if resume else []
    status_frames: list[pd.DataFrame] = [existing_status] if resume else []

    effective_chunk_size = len(institutions) if chunk_size <= 0 else max(1, chunk_size)
    total_chunks = (len(institutions) + effective_chunk_size - 1) // effective_chunk_size if len(institutions) else 0
    print(
        f"{stream_id}: processing {len(institutions)} institutions in {total_chunks} chunk(s); "
        f"{len(already_processed)} already checkpointed",
        flush=True,
    )
    for chunk_index, start in enumerate(range(0, len(institutions), effective_chunk_size), 1):
        chunk_institutions = institutions.iloc[start : start + effective_chunk_size].copy()
        chunk_start_rank = int(chunk_institutions["batch3_rank"].min())
        chunk_end_rank = int(chunk_institutions["batch3_rank"].max())
        print(f"{stream_id}: chunk {chunk_index}/{total_chunks}, ranks {chunk_start_rank}-{chunk_end_rank}", flush=True)
        roots = build_root_candidates_concurrent(
            repo_root,
            legacy_leads,
            chunk_institutions,
            timeout_seconds=timeout_seconds,
            max_candidates_per_institution=max_root_candidates_per_institution,
            max_workers=max_workers,
            source_slug=stream_id.replace("_", "-"),
        )
        decisions = build_source_root_decisions(roots, chunk_institutions)
        archives, result_by_url = build_archive_pages_concurrent(
            repo_root,
            decisions,
            timeout_seconds=timeout_seconds,
            max_archive_pages_per_institution=max_archive_pages_per_institution,
            max_workers=max_workers,
            source_slug=stream_id.replace("_", "-"),
        )
        year_candidates = build_year_candidates(archives, result_by_url)
        year_panel = build_year_panel(repo_root, chunk_institutions, year_candidates)
        status = classify_institution_status(chunk_institutions, roots, decisions, archives, year_candidates, year_panel)

        root_frames.append(roots)
        decision_frames.append(decisions)
        archive_frames.append(archives)
        year_candidate_frames.append(year_candidates)
        year_panel_frames.append(year_panel)
        status_frames.append(status)

        current_roots = concat_frames(root_frames)
        current_decisions = concat_frames(decision_frames)
        current_archives = concat_frames(archive_frames)
        current_year_candidates = concat_frames(year_candidate_frames)
        current_year_panel = concat_frames(year_panel_frames)
        current_status = concat_frames(status_frames)
        checkpoint_institutions.to_csv(outputs.institutions_csv, index=False)
        current_roots.to_csv(outputs.root_candidates_csv, index=False)
        current_decisions.to_csv(outputs.source_root_decisions_csv, index=False)
        current_archives.to_csv(outputs.archive_pages_csv, index=False)
        current_year_candidates.to_csv(outputs.year_candidates_csv, index=False)
        current_year_panel.to_csv(outputs.year_panel_csv, index=False)
        current_status.to_csv(outputs.institution_status_csv, index=False)
        url_count = int(current_year_panel["best_url"].map(clean_text).ne("").sum()) if not current_year_panel.empty else 0
        print(
            f"{stream_id}: checkpoint after chunk {chunk_index}/{total_chunks}; "
            f"{current_status['unitid'].nunique() if not current_status.empty else 0} institutions, "
            f"{url_count} institution-year URLs",
            flush=True,
        )

    root_candidates = concat_frames(root_frames)
    decisions = concat_frames(decision_frames)
    archive_pages = concat_frames(archive_frames)
    year_candidates = concat_frames(year_candidate_frames)
    year_panel = concat_frames(year_panel_frames)
    status = concat_frames(status_frames)
    if not root_candidates.empty and {"unitid", "candidate_url"}.issubset(root_candidates.columns):
        root_candidates = root_candidates.drop_duplicates(["unitid", "candidate_url"], keep="last")
    if not decisions.empty and "unitid" in decisions.columns:
        decisions = decisions.drop_duplicates("unitid", keep="last")
    if not archive_pages.empty and {"unitid", "archive_url"}.issubset(archive_pages.columns):
        archive_pages = archive_pages.drop_duplicates(["unitid", "archive_url"], keep="last")
    if not year_candidates.empty and {"unitid", "target_year", "candidate_url"}.issubset(year_candidates.columns):
        year_candidates = year_candidates.drop_duplicates(["unitid", "target_year", "candidate_url"], keep="last")
    if not year_panel.empty and {"unitid", "target_year"}.issubset(year_panel.columns):
        year_panel = year_panel.drop_duplicates(["unitid", "target_year"], keep="last")
    if not status.empty and "unitid" in status.columns:
        status = status.drop_duplicates("unitid", keep="last")
    root_candidates.to_csv(outputs.root_candidates_csv, index=False)
    decisions.to_csv(outputs.source_root_decisions_csv, index=False)
    archive_pages.to_csv(outputs.archive_pages_csv, index=False)
    year_candidates.to_csv(outputs.year_candidates_csv, index=False)
    year_panel.to_csv(outputs.year_panel_csv, index=False)
    status.to_csv(outputs.institution_status_csv, index=False)
    checkpoint_institutions.to_csv(outputs.institutions_csv, index=False)
    write_workbook(
        outputs.workbook,
        {
            "start_here": status,
            "year_panel": year_panel,
            "year_candidates": year_candidates,
            "source_root_decisions": decisions,
            "root_candidates": root_candidates,
            "archive_pages": archive_pages,
        },
    )
    write_discovery_summary(
        outputs.discovery_summary_md,
        sector=sector,
        institutions=institutions,
        status=status,
        year_panel=year_panel,
        outputs=outputs,
    )
    return outputs


def classification_paths(repo_root: Path, sectors: list[str], explicit_paths: list[Path] | None = None) -> list[Path]:
    if explicit_paths:
        return [path if path.is_absolute() else repo_root / path for path in explicit_paths]
    delivery = (repo_root / DELIVERY_DIR).resolve()
    paths: list[Path] = []
    for sector in sectors:
        stream_id = stream_id_for_sector(sector)
        patterns = [
            f"policy_classification_production_excerpt_{stream_id}_*.csv",
            f"policy_classification_batch_results_production_excerpt_{stream_id}_*.csv",
        ]
        for pattern in patterns:
            paths.extend(sorted(delivery.glob(pattern)))
    return paths


def read_classifications(repo_root: Path, sectors: list[str], explicit_paths: list[Path] | None = None) -> pd.DataFrame:
    frames = []
    for path in classification_paths(repo_root, sectors, explicit_paths):
        frame = read_csv_if_exists(path)
        if frame.empty:
            continue
        frame["_classification_source_file"] = str(path.resolve())
        frames.append(frame)
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def compact_year_panel(repo_root: Path, sector: str) -> pd.DataFrame:
    panel = read_latest_full_year_panel(repo_root, sector, include_inferred=True, include_archive_expansion=True)
    if panel.empty:
        return pd.DataFrame(columns=["unitid", "target_year"])
    panel = panel.copy()
    panel["unitid"] = pd.to_numeric(panel["unitid"], errors="coerce").astype("Int64")
    year_column = "target_year" if "target_year" in panel.columns else "year"
    panel["target_year"] = pd.to_numeric(panel[year_column], errors="coerce").astype("Int64")
    if "final_best_url" in panel.columns:
        final_status = panel.get("final_status", pd.Series("", index=panel.index)).fillna("").map(clean_text)
        ai_added = final_status.eq("ai_candidate_added")
        base_link_text = panel.get("candidate_link_text_x", panel.get("candidate_link_text", pd.Series("", index=panel.index))).fillna("")
        ai_link_text = panel.get("candidate_link_text_y", pd.Series("", index=panel.index)).fillna("")
        base_archive_url = panel.get("archive_url_x", panel.get("archive_url", pd.Series("", index=panel.index))).fillna("")
        ai_archive_url = panel.get("archive_url_y", pd.Series("", index=panel.index)).fillna("")
        panel["best_url"] = panel["final_best_url"]
        if "final_best_url_source" in panel.columns:
            panel["candidate_evidence_source"] = panel["final_best_url_source"]
        panel["candidate_link_text"] = base_link_text
        panel.loc[ai_added & ai_link_text.map(clean_text).ne(""), "candidate_link_text"] = ai_link_text
        panel["archive_url"] = base_archive_url
        panel.loc[ai_added & ai_archive_url.map(clean_text).ne(""), "archive_url"] = ai_archive_url
    if "best_url" not in panel.columns:
        panel["best_url"] = ""
    for column in ["candidate_link_text", "candidate_evidence_source", "catalog_year_start", "catalog_year_end", "archive_url"]:
        if column not in panel.columns:
            panel[column] = ""
    panel["clean_output_row_present"] = True
    panel["clean_best_url"] = panel["best_url"].map(clean_text)
    link_text = panel["candidate_link_text"].map(clean_text)
    evidence_text = (
        panel["candidate_evidence_source"].map(clean_text)
        + " "
        + panel["catalog_year_start"].map(clean_text)
        + " "
        + panel["catalog_year_end"].map(clean_text)
        + " "
        + panel["archive_url"].map(clean_text)
    )
    scope = [
        classify_scope(best_url=url, link_text=link, evidence_text=evidence)
        for url, link, evidence in zip(panel["clean_best_url"], link_text, evidence_text)
    ]
    panel["clean_source_scope_type"] = [item[0] for item in scope]
    panel["clean_scope_review_flag"] = [item[1] for item in scope]
    stream_id = stream_id_for_sector(sector)
    panel["clean_policy_extraction_ready"] = [
        policy_extraction_ready(
            source_stream=stream_id,
            best_url=row.clean_best_url,
            scope_review_flag=row.clean_scope_review_flag,
            source_scope_type=row.clean_source_scope_type,
        )
        for row in panel.itertuples(index=False)
    ]
    keep = [
        "unitid",
        "target_year",
        "clean_output_row_present",
        "clean_best_url",
        "clean_source_scope_type",
        "clean_scope_review_flag",
        "clean_policy_extraction_ready",
        "candidate_link_text",
        "candidate_evidence_source",
        "archive_url",
    ]
    return panel[keep].sort_values(["unitid", "target_year", "clean_best_url"]).drop_duplicates(
        ["unitid", "target_year"],
        keep="last",
    )


def score_rows(
    repo_root: Path,
    sectors: list[str],
    *,
    classification_path: list[Path] | None = None,
) -> pd.DataFrame:
    truth = read_holdout_truth(repo_root, sectors)
    if truth.empty:
        return pd.DataFrame()
    panels = [compact_year_panel(repo_root, sector) for sector in sectors]
    panel = concat_frames(panels)
    if panel.empty:
        panel = pd.DataFrame(columns=["unitid", "target_year"])
    classes = build_classification_flags(read_classifications(repo_root, sectors, classification_path))
    scored = truth.copy()
    scored["unitid"] = pd.to_numeric(scored["unitid"], errors="coerce").astype("Int64")
    scored["target_year"] = pd.to_numeric(scored["target_year"], errors="coerce").astype("Int64")
    scored = scored.merge(panel, on=["unitid", "target_year"], how="left")
    if not classes.empty:
        scored = scored.merge(classes, on=["unitid", "target_year"], how="left")
    else:
        for column in [
            "classification_row_present",
            "api_parsed",
            "api_has_policy_class",
            "classification_has_informative_class",
            "classification_policy_class_clean",
            "source_retrieval_status",
            "classification_text_extract_status",
            "classification_policy_search_status",
            "classification_api_status",
            "_classification_source_file",
        ]:
            scored[column] = False if column.endswith("_present") or column.startswith("api_") or column.startswith("classification_has") else ""
    for column in [
        "clean_output_row_present",
        "clean_policy_extraction_ready",
        "classification_row_present",
        "api_parsed",
        "api_has_policy_class",
        "classification_has_informative_class",
    ]:
        if column not in scored.columns:
            scored[column] = False
        scored[column] = bool_series(scored[column])
    for column in ["clean_best_url", "clean_source_scope_type", "clean_scope_review_flag", "classification_policy_class_clean"]:
        if column not in scored.columns:
            scored[column] = ""
        scored[column] = scored[column].map(clean_text)
    scored["clean_has_url"] = scored["clean_best_url"].map(clean_text).ne("")
    scored["legacy_url_normalized"] = scored["legacy_url"].map(normalized_url)
    scored["clean_best_url_normalized"] = scored["clean_best_url"].map(normalized_url)
    scored["clean_url_exact_match_to_legacy"] = (
        scored["legacy_url_normalized"].ne("") & scored["legacy_url_normalized"].eq(scored["clean_best_url_normalized"])
    )
    validity = read_checkpoint(truth_url_validity_outputs(repo_root).retrieval_csv)
    if not validity.empty:
        validity = validity.reindex(columns=truth_url_retrieval_columns())
        validity["legacy_url"] = validity["legacy_url"].map(clean_text)
        validity = validity.drop_duplicates("legacy_url", keep="last")
        scored["legacy_url"] = scored["legacy_url"].map(clean_text)
        scored = scored.merge(validity, on="legacy_url", how="left")
        scored["truth_legacy_url_validity_checked"] = scored["truth_legacy_url_retrieval_status"].map(clean_text).ne("")
        scored["truth_legacy_url_currently_retrieved"] = scored["truth_legacy_url_retrieval_status"].map(clean_text).isin(
            RETRIEVED_STATUSES
        )
        assessments = scored.apply(
            lambda row: legacy_url_benchmark_validity(
                legacy_url=row.get("legacy_url"),
                retrieval_status=row.get("truth_legacy_url_retrieval_status"),
                http_status=row.get("truth_legacy_url_http_status"),
                final_url=row.get("truth_legacy_url_final_url"),
                content_type=row.get("truth_legacy_url_content_type"),
                page_title=row.get("truth_legacy_url_page_title"),
            ),
            axis=1,
        )
        scored["truth_legacy_url_currently_valid"] = [valid for valid, _ in assessments]
        scored["truth_legacy_url_validity_reason"] = [reason for _, reason in assessments]
    else:
        for column in truth_url_retrieval_columns():
            if column != "legacy_url":
                scored[column] = ""
        scored["truth_legacy_url_validity_checked"] = False
        scored["truth_legacy_url_currently_retrieved"] = False
        scored["truth_legacy_url_currently_valid"] = False
        scored["truth_legacy_url_validity_reason"] = ""
    scored["truth_policy_class_clean"] = scored["legacy_policy_class"].map(clean_text)
    scored["truth_policy_class_informative"] = scored["truth_policy_class_clean"].isin(INFORMATIVE_CLASSES)
    scored["exact_policy_class_match"] = (
        scored["truth_policy_class_informative"]
        & scored["classification_has_informative_class"]
        & scored["truth_policy_class_clean"].eq(scored["classification_policy_class_clean"])
    )
    scored["clean_pipeline_success"] = scored["exact_policy_class_match"]
    scored["loss_bucket"] = scored.apply(score_loss_bucket, axis=1)
    return scored.sort_values(["truth_sector", "institution_name", "unitid", "target_year"])


def score_loss_bucket(row: pd.Series) -> str:
    if not bool(row.get("truth_policy_class_informative", False)):
        return "00_truth_policy_class_not_informative"
    if not bool(row.get("clean_output_row_present", False)):
        return "01_no_clean_holdout_output_row"
    if not bool(row.get("clean_has_url", False)):
        return "02_clean_holdout_row_no_url"
    if not bool(row.get("clean_policy_extraction_ready", False)):
        return "03_clean_url_not_policy_extraction_ready"
    if not bool(row.get("classification_row_present", False)):
        return "04_no_classification_row"
    if not bool(row.get("api_parsed", False)) and not bool(row.get("classification_has_informative_class", False)):
        return "05_classification_row_but_api_not_parsed"
    if not bool(row.get("classification_has_informative_class", False)):
        return "06_non_informative_classification"
    if not bool(row.get("exact_policy_class_match", False)):
        return "07_informative_class_mismatch"
    return "08_exact_class_match_success"


def summarize_scores(scores: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    if scores.empty:
        return pd.DataFrame(columns=["sector", "denominator", "metric", "count", "percent_of_denominator"])
    sectors = sorted(scores["truth_sector"].map(clean_text).unique())
    for sector in sectors + ["all"]:
        group = scores if sector == "all" else scores.loc[scores["truth_sector"].eq(sector)]
        source_n = len(group)
        informative = group.loc[bool_series(group["truth_policy_class_informative"])].copy()
        class_n = len(informative)

        def add(denominator: str, metric: str, count: int, n: int) -> None:
            rows.append(
                {
                    "sector": sector,
                    "denominator": denominator,
                    "metric": metric,
                    "count": int(count),
                    "percent_of_denominator": round(100 * int(count) / n, 1) if n else 0.0,
                }
            )

        add("truth_rows_with_human_legacy_url", "denominator", source_n, source_n)
        add("truth_rows_with_human_legacy_url", "clean_output_row_present", int(group["clean_output_row_present"].sum()), source_n)
        add("truth_rows_with_human_legacy_url", "clean_has_url", int(group["clean_has_url"].sum()), source_n)
        add(
            "truth_rows_with_human_legacy_url",
            "clean_policy_extraction_ready",
            int(group["clean_policy_extraction_ready"].sum()),
            source_n,
        )
        add(
            "truth_rows_with_human_legacy_url",
            "clean_url_exact_match_to_legacy",
            int(group["clean_url_exact_match_to_legacy"].sum()),
            source_n,
        )
        if "truth_legacy_url_validity_checked" in group.columns and bool_series(group["truth_legacy_url_validity_checked"]).any():
            checked = group.loc[bool_series(group["truth_legacy_url_validity_checked"])].copy()
            if "truth_legacy_url_currently_valid" not in checked.columns:
                checked["truth_legacy_url_currently_valid"] = checked["truth_legacy_url_currently_retrieved"]
            checked_n = len(checked)
            retrieved = checked.loc[bool_series(checked["truth_legacy_url_currently_retrieved"])].copy()
            retrieved_n = len(retrieved)
            valid = checked.loc[bool_series(checked["truth_legacy_url_currently_valid"])].copy()
            valid_n = len(valid)
            add("truth_rows_with_checked_human_legacy_url", "denominator", checked_n, checked_n)
            add(
                "truth_rows_with_checked_human_legacy_url",
                "truth_legacy_url_currently_retrieved",
                retrieved_n,
                checked_n,
            )
            add(
                "truth_rows_with_checked_human_legacy_url",
                "truth_legacy_url_currently_valid",
                valid_n,
                checked_n,
            )
            add(
                "truth_rows_with_checked_human_legacy_url",
                "truth_legacy_url_retrieved_but_invalid",
                retrieved_n - valid_n,
                checked_n,
            )
            add(
                "truth_rows_with_checked_human_legacy_url",
                "truth_legacy_url_not_currently_retrieved",
                checked_n - retrieved_n,
                checked_n,
            )
            add(
                "truth_rows_with_checked_human_legacy_url",
                "clean_has_url",
                int(checked["clean_has_url"].sum()),
                checked_n,
            )
            add("truth_rows_with_currently_retrieved_human_legacy_url", "denominator", retrieved_n, retrieved_n)
            add(
                "truth_rows_with_currently_retrieved_human_legacy_url",
                "clean_output_row_present",
                int(retrieved["clean_output_row_present"].sum()),
                retrieved_n,
            )
            add(
                "truth_rows_with_currently_retrieved_human_legacy_url",
                "clean_has_url",
                int(retrieved["clean_has_url"].sum()),
                retrieved_n,
            )
            add(
                "truth_rows_with_currently_retrieved_human_legacy_url",
                "clean_policy_extraction_ready",
                int(retrieved["clean_policy_extraction_ready"].sum()),
                retrieved_n,
            )
            add(
                "truth_rows_with_currently_retrieved_human_legacy_url",
                "clean_url_exact_match_to_legacy",
                int(retrieved["clean_url_exact_match_to_legacy"].sum()),
                retrieved_n,
            )
            add("truth_rows_with_currently_valid_human_legacy_url", "denominator", valid_n, valid_n)
            add(
                "truth_rows_with_currently_valid_human_legacy_url",
                "clean_output_row_present",
                int(valid["clean_output_row_present"].sum()),
                valid_n,
            )
            add(
                "truth_rows_with_currently_valid_human_legacy_url",
                "clean_has_url",
                int(valid["clean_has_url"].sum()),
                valid_n,
            )
            add(
                "truth_rows_with_currently_valid_human_legacy_url",
                "clean_policy_extraction_ready",
                int(valid["clean_policy_extraction_ready"].sum()),
                valid_n,
            )
            add(
                "truth_rows_with_currently_valid_human_legacy_url",
                "clean_url_exact_match_to_legacy",
                int(valid["clean_url_exact_match_to_legacy"].sum()),
                valid_n,
            )
        add("informative_truth_policy_rows", "denominator", class_n, class_n)
        for metric in [
            "clean_output_row_present",
            "clean_has_url",
            "clean_policy_extraction_ready",
            "classification_row_present",
            "classification_has_informative_class",
            "exact_policy_class_match",
            "clean_pipeline_success",
        ]:
            add("informative_truth_policy_rows", metric, int(informative[metric].sum()) if class_n else 0, class_n)
        for bucket, count in informative["loss_bucket"].value_counts().sort_index().items():
            add("informative_truth_policy_rows", f"loss_bucket:{bucket}", int(count), class_n)
    return pd.DataFrame(rows)


def write_score_summary(path: Path, scores: pd.DataFrame, summary: pd.DataFrame, outputs: BenchmarkScoreOutputs) -> None:
    lookup = {(row["sector"], row["denominator"], row["metric"]): row for _, row in summary.iterrows()}

    def value(sector: str, denominator: str, metric: str, field: str = "count") -> object:
        row = lookup.get((sector, denominator, metric))
        return "" if row is None else row[field]

    lines = [
        "# Clean No-Legacy Holdout Benchmark",
        "",
        f"Generated at: {utc_now()}",
        "",
        "## Rule",
        "",
        "Human legacy URLs/classes are withheld from discovery input. They are used only after the run as truth labels.",
        "",
        "## Main Score",
        "",
    ]
    for sector in ["public", "private", "all"]:
        if (sector, "truth_rows_with_human_legacy_url", "denominator") not in lookup:
            continue
        source_denominator = "truth_rows_with_human_legacy_url"
        class_denominator = "informative_truth_policy_rows"
        retrieved_denominator = "truth_rows_with_currently_retrieved_human_legacy_url"
        valid_denominator = "truth_rows_with_currently_valid_human_legacy_url"
        lines.extend(
            [
                f"### {sector.title()}",
                "",
                f"- Truth rows with human legacy URL: {value(sector, source_denominator, 'denominator')}",
                f"- Clean rows with URL: {value(sector, source_denominator, 'clean_has_url')} ({value(sector, source_denominator, 'clean_has_url', 'percent_of_denominator')}%)",
                f"- Clean rows extraction-ready: {value(sector, source_denominator, 'clean_policy_extraction_ready')} ({value(sector, source_denominator, 'clean_policy_extraction_ready', 'percent_of_denominator')}%)",
                f"- Informative truth rows scored for final class: {value(sector, class_denominator, 'denominator')}",
                f"- Classification rows present: {value(sector, class_denominator, 'classification_row_present')} ({value(sector, class_denominator, 'classification_row_present', 'percent_of_denominator')}%)",
                f"- Exact policy-class matches: {value(sector, class_denominator, 'exact_policy_class_match')} ({value(sector, class_denominator, 'exact_policy_class_match', 'percent_of_denominator')}%)",
            ]
        )
        if (sector, valid_denominator, "denominator") in lookup:
            checked_denominator = "truth_rows_with_checked_human_legacy_url"
            lines.extend(
                [
                    f"- Human-URL rows checked for current retrieval: {value(sector, checked_denominator, 'denominator')}",
                    f"- Human-URL rows retrieved over HTTP: {value(sector, retrieved_denominator, 'denominator')} ({value(sector, checked_denominator, 'truth_legacy_url_currently_retrieved', 'percent_of_denominator')}% of checked)",
                    f"- Retrieved human-URL rows rejected as not currently usable catalog/policy sources: {value(sector, checked_denominator, 'truth_legacy_url_retrieved_but_invalid')}",
                    f"- Valid human-URL benchmark rows: {value(sector, valid_denominator, 'denominator')} ({value(sector, checked_denominator, 'truth_legacy_url_currently_valid', 'percent_of_denominator')}% of checked)",
                    f"- Clean rows with URL among valid human-URL benchmark rows: {value(sector, valid_denominator, 'clean_has_url')} ({value(sector, valid_denominator, 'clean_has_url', 'percent_of_denominator')}%)",
                    f"- Clean rows extraction-ready among valid human-URL benchmark rows: {value(sector, valid_denominator, 'clean_policy_extraction_ready')} ({value(sector, valid_denominator, 'clean_policy_extraction_ready', 'percent_of_denominator')}%)",
                ]
            )
        lines.append("")
    lines.extend(["## Loss Buckets", ""])
    if scores.empty:
        lines.append("- no scored rows")
    else:
        for (sector, bucket), count in scores.loc[bool_series(scores["truth_policy_class_informative"])].groupby(
            ["truth_sector", "loss_bucket"]
        ).size().sort_index().items():
            lines.append(f"- {sector} `{bucket}`: {int(count)}")
    lines.extend(["", "## Outputs", ""])
    for label, output_path in outputs.__dict__.items():
        lines.append(f"- {label}: `{output_path}`")
    validity_retrieval_csv = outputs.row_scores_csv.parent / "truth_legacy_url_retrieval.csv"
    validity_summary_csv = outputs.row_scores_csv.parent / "truth_legacy_url_retrieval_summary.csv"
    if validity_retrieval_csv.exists():
        lines.append(f"- truth_url_retrieval_csv: `{validity_retrieval_csv}`")
        lines.append(f"- truth_url_retrieval_summary_csv: `{validity_summary_csv}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_score(
    repo_root: Path,
    sectors: list[str],
    *,
    classification_path: list[Path] | None = None,
) -> BenchmarkScoreOutputs:
    outputs = score_outputs(repo_root)
    for path in outputs.__dict__.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    scores = score_rows(repo_root, sectors, classification_path=classification_path)
    summary = summarize_scores(scores)
    scores.to_csv(outputs.row_scores_csv, index=False)
    summary.to_csv(outputs.summary_csv, index=False)
    write_score_summary(outputs.summary_md, scores, summary, outputs)
    return outputs


def default_benchmark_policy_extraction_queue_path(repo_root: Path) -> Path:
    return repo_root / DATA_DIR / "interim" / "clean_no_legacy_benchmark_policy_extraction_queue.csv"


def build_benchmark_policy_extraction_queue(
    repo_root: Path,
    sectors: list[str],
    *,
    valid_truth_denominator_only: bool = True,
) -> pd.DataFrame:
    scores = score_rows(repo_root, sectors)
    if scores.empty:
        return pd.DataFrame()
    eligible = bool_series(scores["clean_policy_extraction_ready"]) & scores["clean_best_url"].map(clean_text).ne("")
    if valid_truth_denominator_only:
        eligible = eligible & bool_series(scores["truth_legacy_url_currently_valid"])
    selected = scores.loc[eligible].copy()
    rows: list[dict[str, object]] = []
    for _, row in selected.iterrows():
        sector = clean_text(row.get("truth_sector"))
        stream_id = stream_id_for_sector(sector)
        stream = get_stream(stream_id)
        rows.append(
            {
                "source_stream": stream_id,
                "sector_stream": sector,
                "source_family": stream.source_family,
                "source_seed_types": "; ".join(stream.source_seed_types),
                "source_trust_level": "benchmark_holdout_discovered",
                "benchmark_protocol": "clean_no_legacy_benchmark",
                "counts_as_clean_no_legacy_benchmark": True,
                "unitid": int(row["unitid"]),
                "institution_name": clean_text(row.get("institution_name")),
                "state": clean_text(row.get("state")),
                "target_year": int(row["target_year"]),
                "source_url": clean_text(row.get("clean_best_url")),
                "best_url": clean_text(row.get("clean_best_url")),
                "best_url_source": clean_text(row.get("candidate_evidence_source")) or "clean_no_legacy_benchmark",
                "best_url_status": "clean_benchmark_candidate_found",
                "source_scope_type": clean_text(row.get("clean_source_scope_type")),
                "catalog_title_or_link_text": clean_text(row.get("candidate_link_text")),
                "candidate_evidence_text": clean_text(row.get("candidate_evidence_source")),
                "archive_url": clean_text(row.get("archive_url")),
                "requires_source_review": False,
                "review_gate": clean_text(row.get("clean_scope_review_flag")),
                "catalog_evidence_ready": True,
                "policy_extraction_ready": True,
                "policy_extraction_queue_status": "ready_for_clean_no_legacy_benchmark_policy_extraction",
                "clean_benchmark_denominator": "valid_human_legacy_url_rows"
                if valid_truth_denominator_only
                else "all_clean_extraction_ready_rows",
                "source_input_file": "clean_no_legacy_holdout_row_scores.csv",
                "source_input_path": str(score_outputs(repo_root).row_scores_csv.resolve()),
                "created_at": utc_now(),
            }
        )
    queue = pd.DataFrame(rows)
    if queue.empty:
        return queue
    assert_clean_no_legacy_frame(queue)
    return queue.sort_values(["source_stream", "institution_name", "unitid", "target_year"]).drop_duplicates(
        ["source_stream", "unitid", "target_year", "source_url"],
        keep="last",
    )


def write_benchmark_policy_extraction_queue(
    repo_root: Path,
    sectors: list[str],
    *,
    output_path: Path | None = None,
    valid_truth_denominator_only: bool = True,
) -> Path:
    queue = build_benchmark_policy_extraction_queue(
        repo_root,
        sectors,
        valid_truth_denominator_only=valid_truth_denominator_only,
    )
    path = output_path or default_benchmark_policy_extraction_queue_path(repo_root)
    if not path.is_absolute():
        path = repo_root / path
    path.parent.mkdir(parents=True, exist_ok=True)
    queue.to_csv(path, index=False)
    return path


def sector_list(value: str) -> list[str]:
    if value == "both":
        return ["public", "private"]
    return [value]


def parse_unitid_set(value: str) -> set[int]:
    unitids: set[int] = set()
    for piece in clean_text(value).split(","):
        piece = piece.strip()
        if not piece:
            continue
        unitids.add(int(piece))
    return unitids


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--sector", choices=["public", "private", "both"], default="both")
    parser.add_argument(
        "--run-namespace",
        default="current",
        help=(
            "Output namespace under each clean holdout stream. Use 'current' for the active run "
            "or a batch label such as 'pilot_batch_002' for isolated replication pilots."
        ),
    )
    parser.add_argument("--run-discovery", action="store_true", help="Run live clean holdout discovery after building inputs.")
    parser.add_argument("--run-ai-rescue", action="store_true", help="Run AI/web-search rescue against clean holdout first-pass gaps.")
    parser.add_argument(
        "--rematerialize-ai-rescue-unitids",
        default="",
        help="Comma-separated unitids whose saved AI-rescue triage should be reverified/rematerialized after parser changes.",
    )
    parser.add_argument(
        "--run-ai-year-gap-rescue",
        action="store_true",
        help="Run AI/web-search rescue for exact clean-panel target years that still have no URL.",
    )
    parser.add_argument(
        "--rerun-ai-year-gap-cases",
        action="store_true",
        help="Allow the current AI year-gap prompt version to reattempt unitids already present in the year-gap triage file.",
    )
    parser.add_argument(
        "--rematerialize-ai-year-gap-unitids",
        default="",
        help="Comma-separated unitids whose saved parsed year-gap triage should be reverified/rematerialized after parser changes.",
    )
    parser.add_argument(
        "--run-inferred-year-url-rescue",
        action="store_true",
        help="Run deterministic adjacent-year URL-pattern inference from clean-discovered URLs.",
    )
    parser.add_argument(
        "--run-archive-expansion-rescue",
        action="store_true",
        help="Run deeper clean archive-page expansion from clean-discovered roots and URLs.",
    )
    parser.add_argument(
        "--rebuild-archive-expansion-from-cache",
        action="store_true",
        help="Rebuild archive-expansion candidates/panel from already cached archive page bodies without live fetching.",
    )
    parser.add_argument(
        "--run-wayback-cdx-rescue",
        action="store_true",
        help="Run clean Wayback CDX lookup/content-dating from clean-generated catalog roots.",
    )
    parser.add_argument("--score-only", action="store_true", help="Do not rebuild truth/input files before scoring.")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--max-api-cases", type=int, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--rank-start", type=int, default=1)
    parser.add_argument("--timeout-seconds", type=int, default=4)
    parser.add_argument("--max-root-candidates-per-institution", type=int, default=60)
    parser.add_argument("--max-archive-pages-per-institution", type=int, default=12)
    parser.add_argument("--max-archive-expansion-seed-roots-per-institution", type=int, default=12)
    parser.add_argument("--max-wayback-cdx-seed-roots-per-institution", type=int, default=8)
    parser.add_argument("--max-wayback-cdx-snapshots-per-institution", type=int, default=12)
    parser.add_argument("--max-workers", type=int, default=16)
    parser.add_argument("--chunk-size", type=int, default=25)
    parser.add_argument("--reset-discovery", action="store_true", help="Ignore existing clean holdout checkpoints for this run.")
    parser.add_argument(
        "--audit-truth-url-validity",
        action="store_true",
        help="Post-hoc check whether withheld human legacy URLs are currently retrievable for denominator diagnostics.",
    )
    parser.add_argument(
        "--refresh-truth-url-validity",
        action="store_true",
        help="Recheck all truth legacy URLs instead of resuming the existing truth URL validity audit.",
    )
    parser.add_argument("--truth-url-max-bytes", type=int, default=250_000)
    parser.add_argument(
        "--skip-network-preflight",
        action="store_true",
        help="Skip the external retrieval preflight before live discovery. Use only for deliberate offline tests.",
    )
    parser.add_argument("--classification-path", action="append", type=Path, default=None)
    parser.add_argument(
        "--write-policy-extraction-queue",
        action="store_true",
        help="Write a clean benchmark policy-extraction queue from scored clean URLs.",
    )
    parser.add_argument(
        "--policy-extraction-queue-output",
        type=Path,
        default=None,
        help="Optional output path for --write-policy-extraction-queue.",
    )
    parser.add_argument(
        "--policy-extraction-queue-all-clean-ready",
        action="store_true",
        help="Queue all clean extraction-ready rows instead of only rows in the valid human-URL benchmark denominator.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    set_run_namespace(args.run_namespace)
    repo_root = args.root.resolve() if args.root else repo_root_from_cwd()
    sectors = sector_list(args.sector)
    rematerialize_ai_rescue_unitids = parse_unitid_set(args.rematerialize_ai_rescue_unitids)
    rematerialize_ai_year_gap_unitids = parse_unitid_set(args.rematerialize_ai_year_gap_unitids)
    ensure_stream_workspace(repo_root, [stream_id_for_sector(sector) for sector in sectors])
    if not args.score_only:
        truth = build_all_truth_rows(repo_root, sectors)
        write_holdout_files(repo_root, truth, sectors)
    if args.run_discovery:
        for sector in sectors:
            run_discovery_for_sector(
                repo_root,
                sector,
                limit=args.limit,
                rank_start=args.rank_start,
                timeout_seconds=args.timeout_seconds,
                max_root_candidates_per_institution=args.max_root_candidates_per_institution,
                max_archive_pages_per_institution=args.max_archive_pages_per_institution,
                max_workers=args.max_workers,
                chunk_size=args.chunk_size,
                resume=not args.reset_discovery,
                skip_network_preflight=args.skip_network_preflight,
            )
    if args.run_ai_rescue:
        for sector in sectors:
            run_ai_rescue_for_sector(
                repo_root,
                sector,
                config_path=args.config,
                max_api_cases=args.max_api_cases,
                timeout_seconds=args.timeout_seconds,
                max_archive_pages_per_institution=args.max_archive_pages_per_institution,
                max_workers=args.max_workers,
                rematerialize_unitids=rematerialize_ai_rescue_unitids,
            )
    if args.run_ai_year_gap_rescue:
        for sector in sectors:
            run_ai_year_gap_rescue_for_sector(
                repo_root,
                sector,
                config_path=args.config,
                max_api_cases=args.max_api_cases,
                timeout_seconds=args.timeout_seconds,
                max_archive_pages_per_institution=args.max_archive_pages_per_institution,
                max_workers=args.max_workers,
                rerun_existing_cases=args.rerun_ai_year_gap_cases,
                rematerialize_unitids=rematerialize_ai_year_gap_unitids,
            )
    if args.run_inferred_year_url_rescue:
        for sector in sectors:
            run_inferred_year_url_rescue_for_sector(
                repo_root,
                sector,
                timeout_seconds=args.timeout_seconds,
                max_workers=args.max_workers,
            )
    if args.run_archive_expansion_rescue:
        for sector in sectors:
            run_archive_expansion_rescue_for_sector(
                repo_root,
                sector,
                timeout_seconds=args.timeout_seconds,
                max_archive_pages_per_institution=args.max_archive_pages_per_institution,
                max_seed_roots_per_institution=args.max_archive_expansion_seed_roots_per_institution,
                max_workers=args.max_workers,
            )
    if args.rebuild_archive_expansion_from_cache:
        for sector in sectors:
            rebuild_archive_expansion_rescue_from_cache_for_sector(repo_root, sector)
    if args.run_wayback_cdx_rescue:
        for sector in sectors:
            run_wayback_cdx_rescue_for_sector(
                repo_root,
                sector,
                timeout_seconds=args.timeout_seconds,
                max_seed_roots_per_institution=args.max_wayback_cdx_seed_roots_per_institution,
                max_snapshots_per_institution=args.max_wayback_cdx_snapshots_per_institution,
                max_workers=args.max_workers,
            )
    if args.audit_truth_url_validity:
        validity_outputs = audit_truth_legacy_url_validity(
            repo_root,
            sectors,
            timeout_seconds=args.timeout_seconds,
            max_workers=args.max_workers,
            max_bytes=args.truth_url_max_bytes,
            resume=not args.refresh_truth_url_validity,
        )
        for label, output_path in validity_outputs.__dict__.items():
            print(f"{label}: {output_path}")
    outputs = run_score(repo_root, sectors, classification_path=args.classification_path)
    for label, output_path in outputs.__dict__.items():
        print(f"{label}: {output_path}")
    if args.write_policy_extraction_queue:
        queue_path = write_benchmark_policy_extraction_queue(
            repo_root,
            sectors,
            output_path=args.policy_extraction_queue_output,
            valid_truth_denominator_only=not args.policy_extraction_queue_all_clean_ready,
        )
        print(f"policy_extraction_queue: {queue_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
