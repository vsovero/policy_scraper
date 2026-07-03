"""Run a proof-to-scale Step 1 URL-discovery production chunk.

This entry point starts from the actual target-panel universe, runs current URL
discovery under a fresh namespace, converts the current-run evidence into the
explicit Step 1 production-runner inputs, and optionally packages the passed
chunk as a URL-stage release.

It is intentionally not a pilot/mini wrapper: old pilot folders, old audit
outputs, and hidden legacy answers are not runtime inputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing as mp
import re
import signal
import shutil
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from queue import Empty
from urllib.parse import urlparse

import pandas as pd

from .ai_config import repo_root_from_cwd
from .catalog_retrieval import (
    decode_body,
    infer_catalog_coverage_years,
    parse_cdx_snapshots,
    parse_wayback_snapshot,
    raw_wayback_snapshot_url,
    retrieve_url,
    visible_page_text,
    wayback_available_latest_url,
    wayback_available_url,
    wayback_cdx_url,
)
from .clean_no_legacy_benchmark import (
    clean_text,
    inferred_year_url_replacements,
    read_best_full_year_panel,
    run_ai_year_gap_rescue_for_sector,
    run_archive_expansion_rescue_for_sector,
    run_discovery_for_sector,
    run_inferred_year_url_rescue_for_sector,
    run_wayback_cdx_rescue_for_sector,
    set_run_namespace,
    stream_id_for_sector,
    stream_outputs,
)
from .step1_production_runner import build_step1_production_chunk, write_csv


PIPELINE_ROOT = Path("artifacts/PIPELINE_OUTPUTS")
URL_DISCOVERY_ROOT = PIPELINE_ROOT / "01_url_discovery"
PRODUCTION_INPUTS_ROOT = URL_DISCOVERY_ROOT / "production_inputs"
PRODUCTION_SELECTION_ROOT = URL_DISCOVERY_ROOT / "production_selection"
HISTORICAL_PRIORITY_BUCKETS = Path("artifacts/AUDIT_TRAILS/url_discovery_historical_inventory/institution_priority_buckets.csv")

INSTITUTION_UNIVERSE = Path("artifacts/policy_data_internal/interim/institution_universe.csv")
INSTITUTION_YEAR_TARGETS_RUNTIME_INPUT = Path("artifacts/policy_data_internal/interim/institution_year_targets.csv")
ESTIMATION_START_YEAR = 2002
ESTIMATION_END_YEAR = 2016
RETRIEVED_STATUSES = {"retrieved", "retrieved_truncated"}
PRIOR_VALID_REVERIFICATION_BUCKETS = (
    "prior_programmatic_accepted_needs_current_reverification",
    "valid_human_legacy",
)
NO_HUMAN_LEGACY_HOLDOUT_BUCKETS = {
    "programmatic_attempt_no_valid_discovery",
    "no_historical_programmatic_attempt_found",
}

CANDIDATE_COLUMNS = [
    "unitid",
    "institution_name",
    "sector",
    "state",
    "academic_year",
    "candidate_url",
    "candidate_rank",
    "candidate_generation_method",
    "candidate_source_file",
    "candidate_source_type",
    "source_query_or_root",
    "candidate_generated_at",
]
EVIDENCE_COLUMNS = [
    "unitid",
    "academic_year",
    "candidate_url",
    "cached_text_path",
    "cached_text_sha256",
    "source_body_sha256",
]
SOURCE_REVIEW_COLUMNS = [
    "unitid",
    "institution_name",
    "sector",
    "state",
    "academic_year",
    "candidate_url",
    "final_url_after_redirect",
    "retrieval_status",
    "http_status",
    "content_type",
    "source_page_title",
    "source_opened",
    "institution_match_confirmed",
    "campus_or_unitid_match_confirmed",
    "source_scope_confirmed",
    "source_type_confirmed",
    "year_coverage_confirmed",
    "archive_child_links_checked",
    "gap_fill_search_completed",
    "panel_consistency_confirmed",
    "deterministic_search_completed",
    "archive_expansion_completed",
    "api_web_rescue_mode",
    "api_web_rescue_status",
    "api_web_rescue_reason",
    "retrieval_recovery_method",
    "retrieval_recovery_source",
    "candidate_generation_method",
    "candidate_source_file",
    "candidate_source_type",
    "source_query_or_root",
    "source_type",
    "source_year_start",
    "source_year_end",
    "source_year_coverage_note",
    "url_source_bucket",
    "review_decision",
    "review_reason",
    "reviewed_by",
    "reviewed_at",
    "source_evidence_note",
]
BENCHMARK_COLUMNS = [
    "benchmark_group",
    "unitid",
    "institution_name",
    "academic_year",
    "benchmark_url",
]
HISTORICAL_CASE_PRECHECK_COLUMNS = [
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
]


@dataclass(frozen=True)
class ProofToScaleResult:
    namespace: str
    input_dir: Path
    chunk_dir: Path
    release_dir: Path | None
    target_rows: int
    target_institutions: int
    ready_rows: int
    unresolved_rows: int
    requirements_pass: bool
    release_pass: bool | None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def safe_slug(value: object) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "_", clean_text(value)).strip("_").lower()
    return text[:80] or "source"


def boolish(value: object) -> bool:
    return clean_text(value).lower() in {"1", "1.0", "true", "yes", "y"}


def repo_relative(path_text: object, repo_root: Path) -> str:
    text = clean_text(path_text)
    if not text:
        return ""
    path = Path(text)
    if not path.is_absolute():
        return text
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.name


def count_value(row: pd.Series, column: str) -> int:
    value = pd.to_numeric(pd.Series([row.get(column, 0)]), errors="coerce").fillna(0).iloc[0]
    return int(value)


def load_historical_priority_buckets(repo_root: Path) -> pd.DataFrame:
    path = repo_root / HISTORICAL_PRIORITY_BUCKETS
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path, low_memory=False)
    if "unitid" not in frame.columns:
        return pd.DataFrame()
    frame["unitid"] = pd.to_numeric(frame["unitid"], errors="coerce").astype("Int64")
    return frame.loc[frame["unitid"].notna()].drop_duplicates("unitid", keep="first").copy()


def load_excluded_unitids(path: Path | None, repo_root: Path) -> set[int]:
    if path is None:
        return set()
    resolved = path if path.is_absolute() else repo_root / path
    if not resolved.exists():
        raise FileNotFoundError(f"Excluded-unitids file not found: {resolved}")
    frame = pd.read_csv(resolved, low_memory=False)
    if "unitid" not in frame.columns:
        raise ValueError(f"Excluded-unitids file must contain a unitid column: {resolved}")
    unitids = pd.to_numeric(frame["unitid"], errors="coerce").dropna().astype(int)
    return set(unitids.tolist())


def build_historical_case_precheck(repo_root: Path, target_panel: pd.DataFrame, namespace: str) -> pd.DataFrame:
    """Create URL-free historical-memory rows for the clean production runner."""
    priority = load_historical_priority_buckets(repo_root)
    priority_lookup = {
        int(row["unitid"]): row
        for _, row in priority.iterrows()
        if pd.notna(row.get("unitid"))
    }
    institution_rows = (
        target_panel.groupby("unitid", dropna=False)
        .agg(
            institution_name=("institution_name", "first"),
            target_rows=("academic_year", "nunique"),
            has_human_legacy_source=("has_human_legacy_source", "max"),
        )
        .reset_index()
    )
    rows: list[dict[str, object]] = []
    for _, target in institution_rows.iterrows():
        unitid = int(target["unitid"])
        historical = priority_lookup.get(unitid, pd.Series(dtype=object))
        legacy_rows = count_value(historical, "valid_human_legacy_rows")
        prior_programmatic_rows = count_value(historical, "prior_programmatic_accepted_rows")
        unreviewed_lead_rows = count_value(historical, "unreviewed_candidate_lead_rows")
        failed_rows = count_value(historical, "failed_attempt_rows")
        priority_bucket = clean_text(historical.get("priority_bucket"))
        if not priority_bucket:
            priority_bucket = (
                "valid_human_legacy"
                if boolish(target.get("has_human_legacy_source"))
                else "no_historical_programmatic_attempt_found"
            )
        if legacy_rows == 0 and boolish(target.get("has_human_legacy_source")):
            legacy_rows = 1
        rows.append(
            {
                "unitid": unitid,
                "institution_name": clean_text(target.get("institution_name")),
                "historical_priority_bucket": priority_bucket,
                "valid_human_legacy_rows": legacy_rows,
                "prior_programmatic_accepted_rows": prior_programmatic_rows,
                "unreviewed_candidate_lead_rows": unreviewed_lead_rows,
                "failed_attempt_rows": failed_rows,
                "known_source_family_summary": (
                    "URL-free historical precheck only: "
                    f"bucket={priority_bucket}; "
                    f"legacy_rows={legacy_rows}; "
                    f"prior_programmatic_rows={prior_programmatic_rows}; "
                    f"unreviewed_lead_rows={unreviewed_lead_rows}."
                ),
                "known_failure_pattern_summary": (
                    "URL-free historical precheck only: "
                    f"failed_attempt_rows={failed_rows}; target_rows={count_value(target, 'target_rows')}."
                ),
                "historical_precheck_completed": True,
                "runtime_input_guardrail_confirmed": True,
                "precheck_created_by": "course_policy.step1_proof_to_scale_url_production",
                "precheck_created_at": namespace,
            }
        )
    return pd.DataFrame(rows, columns=HISTORICAL_CASE_PRECHECK_COLUMNS)


def stata_panel_path(repo_root: Path) -> Path:
    candidates = [
        repo_root / "Stata Files" / "Data" / "mainpanelgf_clean.dta",
        repo_root.parent / "Stata Files" / "Data" / "mainpanelgf_clean.dta",
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError("Could not find Stata Files/Data/mainpanelgf_clean.dta")


def load_target_panel_universe(repo_root: Path) -> pd.DataFrame:
    columns = [
        "unitid",
        "year",
        "instnm",
        "stabbr",
        "sector",
        "control",
        "iclevel",
        "webaddr",
        "grad4per",
        "grad5per",
        "grad6per",
    ]
    panel = pd.read_stata(stata_panel_path(repo_root), columns=columns, convert_categoricals=False)
    panel["unitid"] = pd.to_numeric(panel["unitid"], errors="coerce").astype("Int64")
    panel["academic_year"] = pd.to_numeric(panel["year"], errors="coerce").astype("Int64")
    for column in ["sector", "control", "iclevel", "grad4per", "grad5per", "grad6per"]:
        panel[column] = pd.to_numeric(panel[column], errors="coerce")
    panel["has_grad_outcome"] = panel[["grad4per", "grad5per", "grad6per"]].notna().any(axis=1)
    panel = panel.loc[
        panel["academic_year"].between(ESTIMATION_START_YEAR, ESTIMATION_END_YEAR)
        & panel["sector"].isin([1, 2])
        & panel["iclevel"].eq(1)
        & panel["has_grad_outcome"]
    ].copy()
    panel["sector_stream"] = panel["sector"].map({1: "public", 2: "private"})
    panel["institution_name"] = panel["instnm"].map(clean_text)
    panel["state"] = panel["stabbr"].map(clean_text)
    panel["webaddr"] = panel["webaddr"].map(clean_text)

    universe_path = repo_root / INSTITUTION_UNIVERSE
    if universe_path.exists():
        universe = pd.read_csv(universe_path, low_memory=False)
        universe["unitid"] = pd.to_numeric(universe["unitid"], errors="coerce").astype("Int64")
        keep = [
            column
            for column in [
                "unitid",
                "institution_name",
                "source_in_legacy_public",
                "source_in_legacy_private",
                "active_in_ipeds_panel",
            ]
            if column in universe.columns
        ]
        panel = panel.merge(universe[keep].drop_duplicates("unitid"), on="unitid", how="left", suffixes=("", "_universe"))
        panel["institution_name"] = panel["institution_name_universe"].where(
            panel.get("institution_name_universe", pd.Series("", index=panel.index)).map(clean_text).ne(""),
            panel["institution_name"],
        )
        panel = panel.drop(columns=["institution_name_universe"], errors="ignore")
    for column in ["source_in_legacy_public", "source_in_legacy_private", "active_in_ipeds_panel"]:
        if column not in panel.columns:
            panel[column] = False
    panel["source_in_legacy_public"] = panel["source_in_legacy_public"].map(boolish)
    panel["source_in_legacy_private"] = panel["source_in_legacy_private"].map(boolish)
    panel["has_human_legacy_source"] = (
        panel["sector_stream"].eq("public") & panel["source_in_legacy_public"]
    ) | (
        panel["sector_stream"].eq("private") & panel["source_in_legacy_private"]
    )
    return panel.sort_values(["sector_stream", "institution_name", "unitid", "academic_year"]).reset_index(drop=True)


def institution_summary(target_universe: pd.DataFrame) -> pd.DataFrame:
    summary = (
        target_universe.groupby("unitid", dropna=False)
        .agg(
            institution_name=("institution_name", "first"),
            sector=("sector_stream", "first"),
            state=("state", "first"),
            webaddr=("webaddr", "first"),
            target_year_count=("academic_year", "nunique"),
            first_target_year=("academic_year", "min"),
            last_target_year=("academic_year", "max"),
            has_human_legacy_source=("has_human_legacy_source", "max"),
        )
        .reset_index()
    )
    summary["unitid"] = pd.to_numeric(summary["unitid"], errors="coerce").astype("Int64")
    summary["target_year_count"] = pd.to_numeric(summary["target_year_count"], errors="coerce").fillna(0).astype(int)
    summary["has_human_legacy_source"] = summary["has_human_legacy_source"].map(boolish)
    return summary.loc[summary["unitid"].notna()].copy()


def select_representative_institutions(
    target_universe: pd.DataFrame,
    *,
    institution_count: int,
    min_target_rows: int,
    max_target_rows: int,
) -> pd.DataFrame:
    summary = institution_summary(target_universe)
    eligible = summary.loc[summary["target_year_count"].ge(8)].copy()
    if eligible.empty:
        raise RuntimeError("No eligible institutions with at least 8 target years.")
    selected_frames: list[pd.DataFrame] = []
    bucket_count = max(1, institution_count // 4)
    buckets = [
        ("public", True, bucket_count),
        ("public", False, bucket_count),
        ("private", True, bucket_count),
        ("private", False, bucket_count),
    ]
    for sector, legacy_flag, count in buckets:
        bucket = eligible.loc[
            eligible["sector"].eq(sector) & eligible["has_human_legacy_source"].eq(legacy_flag)
        ].copy()
        bucket = bucket.sort_values(
            ["target_year_count", "institution_name", "unitid"],
            ascending=[False, True, True],
        ).head(count)
        selected_frames.append(bucket)
    selected = pd.concat(selected_frames, ignore_index=True) if selected_frames else pd.DataFrame()
    selected = selected.drop_duplicates("unitid", keep="first")
    if len(selected) < institution_count:
        remaining = eligible.loc[~eligible["unitid"].isin(selected["unitid"])].copy()
        remaining = remaining.sort_values(
            ["target_year_count", "sector", "has_human_legacy_source", "institution_name", "unitid"],
            ascending=[False, True, False, True, True],
        )
        selected = pd.concat([selected, remaining.head(institution_count - len(selected))], ignore_index=True)
    selected = selected.drop_duplicates("unitid", keep="first").head(institution_count).copy()

    target_rows = target_universe.loc[target_universe["unitid"].isin(selected["unitid"])].copy()
    if len(target_rows) > max_target_rows:
        selected = selected.sort_values(
            ["target_year_count", "sector", "has_human_legacy_source", "institution_name", "unitid"],
            ascending=[True, True, False, True, True],
        ).copy()
        while len(target_rows) > max_target_rows and len(selected) > 1:
            selected = selected.iloc[:-1].copy()
            target_rows = target_universe.loc[target_universe["unitid"].isin(selected["unitid"])].copy()
    if len(target_rows) < min_target_rows:
        remaining = eligible.loc[~eligible["unitid"].isin(selected["unitid"])].copy()
        remaining = remaining.sort_values(
            ["target_year_count", "sector", "has_human_legacy_source", "institution_name", "unitid"],
            ascending=[False, True, False, True, True],
        )
        for _, row in remaining.iterrows():
            selected = pd.concat([selected, row.to_frame().T], ignore_index=True)
            selected = selected.drop_duplicates("unitid", keep="first")
            target_rows = target_universe.loc[target_universe["unitid"].isin(selected["unitid"])].copy()
            if len(target_rows) >= min_target_rows or len(selected) >= 50:
                break
    if not min_target_rows <= len(target_rows) <= max_target_rows:
        raise RuntimeError(
            f"Selected target rows outside proof-to-scale bounds: {len(target_rows)} "
            f"not in [{min_target_rows}, {max_target_rows}]"
        )
    return selected.sort_values(["sector", "has_human_legacy_source", "institution_name", "unitid"]).reset_index(drop=True)


def target_panel_for_selection(target_universe: pd.DataFrame, selected: pd.DataFrame) -> pd.DataFrame:
    selected_unitids = set(pd.to_numeric(selected["unitid"], errors="coerce").dropna().astype(int))
    target = target_universe.loc[target_universe["unitid"].astype(int).isin(selected_unitids)].copy()
    out = pd.DataFrame(
        {
            "unitid": target["unitid"],
            "institution_name": target["institution_name"],
            "sector": target["sector_stream"],
            "state": target["state"],
            "academic_year": target["academic_year"],
            "target_inclusion_reason": "actual_target_panel_2002_2016_with_graduation_outcome",
            "estimation_sample_flag": True,
            "panel_fill_flag": False,
            "homepage_url": target["webaddr"],
            "has_human_legacy_source": target["has_human_legacy_source"],
        }
    )
    return out.sort_values(["sector", "institution_name", "unitid", "academic_year"]).reset_index(drop=True)


def load_raw_legacy_url_rows(repo_root: Path) -> pd.DataFrame:
    specs = [
        {
            "path": repo_root.parent / "Ipeds raw Data files" / "Course repetition data.xlsx",
            "sheet": "Sheet1",
            "url_columns": ["bulletin", "Earliest Bulletin", "Current Bulletin"],
            "name_column": "institution name",
            "sector_hint": "public",
            "source_type": "raw_public_legacy_workbook_url",
        },
        {
            "path": repo_root.parent / "Stata Files" / "Data" / "gfprivatelist.xlsx",
            "sheet": "private",
            "url_columns": ["bulletin"],
            "name_column": "instnm",
            "sector_hint": "private",
            "source_type": "raw_private_legacy_workbook_url",
        },
        {
            "path": repo_root.parent / "Stata Files" / "Data" / "gfprivatelist.xlsx",
            "sheet": "(Automated, 0121) Missing priva",
            "url_columns": ["bulletin"],
            "name_column": "instnm",
            "sector_hint": "private",
            "source_type": "raw_private_legacy_workbook_url",
        },
        {
            "path": repo_root.parent / "Stata Files" / "Data" / "gfprivatelist.xlsx",
            "sheet": "LLM Training Set",
            "url_columns": ["bulletin"],
            "name_column": "instnm",
            "sector_hint": "private",
            "source_type": "raw_private_legacy_workbook_url",
        },
    ]
    rows: list[dict[str, object]] = []
    for spec in specs:
        path = Path(spec["path"])
        if not path.exists():
            continue
        try:
            frame = pd.read_excel(path, sheet_name=str(spec["sheet"]))
        except Exception:
            continue
        for _, record in frame.iterrows():
            unitid_value = pd.to_numeric(pd.Series([record.get("unitid")]), errors="coerce").iloc[0]
            if pd.isna(unitid_value):
                continue
            for column in spec["url_columns"]:
                url = clean_text(record.get(column))
                if not url.startswith("http"):
                    continue
                inferred = infer_catalog_coverage_years(url)
                if not inferred:
                    continue
                rows.append(
                    {
                        "unitid": int(unitid_value),
                        "institution_name": clean_text(record.get(spec["name_column"])),
                        "sector": spec["sector_hint"],
                        "candidate_url": url,
                        "catalog_year_start": int(inferred[0]),
                        "catalog_year_end": int(inferred[1]),
                        "candidate_generation_method": spec["source_type"],
                        "candidate_source_type": "human_legacy_url",
                        "candidate_source_file": repo_relative(path, repo_root),
                        "source_query_or_root": str(spec["sheet"]),
                    }
                )
    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows).drop_duplicates(
        ["unitid", "sector", "candidate_url", "catalog_year_start", "catalog_year_end"],
        keep="first",
    )
    return out.sort_values(["sector", "unitid", "catalog_year_start", "candidate_url"]).reset_index(drop=True)


def raw_legacy_candidates_for_target(target_panel: pd.DataFrame, raw_legacy: pd.DataFrame) -> pd.DataFrame:
    if raw_legacy.empty or target_panel.empty:
        return pd.DataFrame()
    target = target_panel[["unitid", "institution_name", "sector", "state", "academic_year"]].copy()
    target["unitid"] = pd.to_numeric(target["unitid"], errors="coerce").astype("Int64")
    target["academic_year"] = pd.to_numeric(target["academic_year"], errors="coerce").astype("Int64")
    raw = raw_legacy.copy()
    raw["unitid"] = pd.to_numeric(raw["unitid"], errors="coerce").astype("Int64")
    merged = target.merge(raw, on=["unitid", "sector"], how="inner", suffixes=("", "_legacy"))
    merged = merged.loc[
        pd.to_numeric(merged["catalog_year_start"], errors="coerce").le(merged["academic_year"])
        & pd.to_numeric(merged["catalog_year_end"], errors="coerce").ge(merged["academic_year"])
    ].copy()
    if merged.empty:
        return pd.DataFrame()
    merged["candidate_rank"] = 0
    merged["candidate_generated_at"] = "raw_legacy_workbook"
    return (
        merged.sort_values(["unitid", "academic_year", "catalog_year_start", "candidate_url"])
        .drop_duplicates(["unitid", "academic_year"], keep="first")
        .reset_index(drop=True)
    )


def raw_legacy_coverage_summary(target_universe: pd.DataFrame, raw_legacy: pd.DataFrame) -> pd.DataFrame:
    target_panel = target_panel_for_selection(target_universe, institution_summary(target_universe))
    candidates = raw_legacy_candidates_for_target(target_panel, raw_legacy)
    target_counts = (
        target_panel.groupby(["unitid", "institution_name", "sector"], dropna=False)
        .agg(target_rows=("academic_year", "nunique"))
        .reset_index()
    )
    if candidates.empty:
        target_counts["legacy_covered_years"] = 0
    else:
        covered = (
            candidates.groupby("unitid", dropna=False)
            .agg(legacy_covered_years=("academic_year", "nunique"))
            .reset_index()
        )
        target_counts = target_counts.merge(covered, on="unitid", how="left")
        target_counts["legacy_covered_years"] = target_counts["legacy_covered_years"].fillna(0).astype(int)
    target_counts["legacy_coverage_rate"] = target_counts["legacy_covered_years"] / target_counts["target_rows"]
    return target_counts


def prior_valid_priority_summary(
    target_universe: pd.DataFrame,
    historical_priority: pd.DataFrame,
    raw_legacy: pd.DataFrame,
) -> pd.DataFrame:
    summary = institution_summary(target_universe)
    coverage = raw_legacy_coverage_summary(target_universe, raw_legacy)
    if not coverage.empty:
        coverage = coverage.sort_values(
            ["legacy_covered_years", "legacy_coverage_rate", "institution_name", "unitid"],
            ascending=[False, False, True, True],
        ).drop_duplicates("unitid", keep="first")
        summary = summary.merge(
            coverage[["unitid", "legacy_covered_years", "legacy_coverage_rate"]],
            on="unitid",
            how="left",
        )
    else:
        summary["legacy_covered_years"] = 0
        summary["legacy_coverage_rate"] = 0.0
    for column in ["legacy_covered_years", "legacy_coverage_rate"]:
        if column not in summary.columns:
            summary[column] = 0
    summary["legacy_covered_years"] = pd.to_numeric(summary["legacy_covered_years"], errors="coerce").fillna(0).astype(int)
    summary["legacy_coverage_rate"] = pd.to_numeric(summary["legacy_coverage_rate"], errors="coerce").fillna(0.0)

    priority = historical_priority.copy()
    if not priority.empty and "unitid" in priority.columns:
        priority["unitid"] = pd.to_numeric(priority["unitid"], errors="coerce").astype("Int64")
        priority = priority.loc[priority["unitid"].notna()].drop_duplicates("unitid", keep="first")
        keep_columns = [
            column
            for column in [
                "unitid",
                "priority_bucket",
                "valid_human_legacy_rows",
                "prior_programmatic_accepted_rows",
                "unreviewed_candidate_lead_rows",
                "failed_attempt_rows",
            ]
            if column in priority.columns
        ]
        summary = summary.merge(priority[keep_columns], on="unitid", how="left")
    for column in [
        "valid_human_legacy_rows",
        "prior_programmatic_accepted_rows",
        "unreviewed_candidate_lead_rows",
        "failed_attempt_rows",
    ]:
        if column not in summary.columns:
            summary[column] = 0
        summary[column] = pd.to_numeric(summary[column], errors="coerce").fillna(0).astype(int)
    summary["historical_priority_bucket"] = summary.get("priority_bucket", pd.Series("", index=summary.index)).map(clean_text)
    raw_or_human_legacy = summary["legacy_covered_years"].gt(0) | summary["has_human_legacy_source"].map(boolish)
    summary["historical_priority_bucket"] = summary["historical_priority_bucket"].where(
        summary["historical_priority_bucket"].ne(""),
        raw_or_human_legacy.map({True: "valid_human_legacy", False: "no_historical_programmatic_attempt_found"}),
    )
    rank_map = {bucket: index for index, bucket in enumerate(PRIOR_VALID_REVERIFICATION_BUCKETS)}
    summary["priority_rank"] = summary["historical_priority_bucket"].map(rank_map).fillna(99).astype(int)
    return summary


def select_prior_valid_legacy_reverification_institutions(
    target_universe: pd.DataFrame,
    historical_priority: pd.DataFrame,
    raw_legacy: pd.DataFrame,
    *,
    public_count: int,
    private_count: int,
    min_target_rows: int,
    max_target_rows: int,
    exclude_unitids: set[int] | None = None,
) -> pd.DataFrame:
    summary = prior_valid_priority_summary(target_universe, historical_priority, raw_legacy)
    eligible = summary.loc[
        summary["historical_priority_bucket"].isin(PRIOR_VALID_REVERIFICATION_BUCKETS)
        | summary["legacy_covered_years"].gt(0)
        | summary["has_human_legacy_source"].map(boolish)
    ].copy()
    eligible = eligible.loc[~eligible["historical_priority_bucket"].isin(NO_HUMAN_LEGACY_HOLDOUT_BUCKETS)].copy()
    if exclude_unitids:
        eligible = eligible.loc[~eligible["unitid"].isin(exclude_unitids)].copy()
    if eligible.empty:
        raise RuntimeError(
            "Prior-valid-legacy reverification selection found no eligible institutions; "
            "run or supply URL-free historical inventory/precheck memory before the next proof-to-scale chunk."
        )

    sort_columns = [
        "priority_rank",
        "prior_programmatic_accepted_rows",
        "valid_human_legacy_rows",
        "legacy_covered_years",
        "legacy_coverage_rate",
        "target_year_count",
        "institution_name",
        "unitid",
    ]
    ascending = [True, False, False, False, False, False, True, True]
    selected_frames: list[pd.DataFrame] = []
    for sector, count in [("public", public_count), ("private", private_count)]:
        if count <= 0:
            continue
        sector_frame = eligible.loc[eligible["sector"].eq(sector)].copy()
        sector_frame = sector_frame.sort_values(sort_columns, ascending=ascending).head(count)
        selected_frames.append(sector_frame)
    selected = pd.concat(selected_frames, ignore_index=True, sort=False) if selected_frames else pd.DataFrame()
    selected = selected.drop_duplicates("unitid", keep="first")

    target_rows = target_universe.loc[target_universe["unitid"].isin(selected["unitid"])].copy()
    if len(target_rows) < min_target_rows:
        remaining = eligible.loc[~eligible["unitid"].isin(selected["unitid"])].copy()
        remaining = remaining.sort_values(sort_columns, ascending=ascending)
        for _, row in remaining.iterrows():
            selected = pd.concat([selected, row.to_frame().T], ignore_index=True)
            selected = selected.drop_duplicates("unitid", keep="first")
            target_rows = target_universe.loc[target_universe["unitid"].isin(selected["unitid"])].copy()
            if len(target_rows) >= min_target_rows:
                break
    if len(target_rows) > max_target_rows:
        selected = selected.sort_values(sort_columns, ascending=ascending).copy()
        while len(target_rows) > max_target_rows and len(selected) > 1:
            selected = selected.iloc[:-1].copy()
            target_rows = target_universe.loc[target_universe["unitid"].isin(selected["unitid"])].copy()
    if selected.empty or not min_target_rows <= len(target_rows) <= max_target_rows:
        raise RuntimeError(
            f"Prior-valid-legacy reverification target rows outside proof-to-scale bounds: {len(target_rows)} "
            f"not in [{min_target_rows}, {max_target_rows}]"
        )
    selected["selection_mode"] = "prior_valid_legacy_reverification"
    return selected.sort_values(sort_columns, ascending=ascending).reset_index(drop=True)


def select_high_legacy_coverage_institutions(
    target_universe: pd.DataFrame,
    raw_legacy: pd.DataFrame,
    *,
    public_count: int,
    private_count: int,
    min_target_rows: int,
    max_target_rows: int,
) -> pd.DataFrame:
    coverage = raw_legacy_coverage_summary(target_universe, raw_legacy)
    selected_frames: list[pd.DataFrame] = []
    for sector, count in [("public", public_count), ("private", private_count)]:
        frame = coverage.loc[coverage["sector"].eq(sector) & coverage["legacy_covered_years"].gt(0)].copy()
        frame = frame.sort_values(
            ["legacy_covered_years", "legacy_coverage_rate", "institution_name", "unitid"],
            ascending=[False, False, True, True],
        ).drop_duplicates("unitid", keep="first").head(count)
        selected_frames.append(frame)
    selected = pd.concat(selected_frames, ignore_index=True, sort=False) if selected_frames else pd.DataFrame()
    selected = selected.drop_duplicates("unitid", keep="first")
    if selected.empty:
        raise RuntimeError("High-legacy-coverage selection found no institutions with raw legacy URL coverage.")
    target_rows = target_universe.loc[target_universe["unitid"].isin(selected["unitid"])].copy()
    if not min_target_rows <= len(target_rows) <= max_target_rows:
        raise RuntimeError(
            f"High-legacy-coverage target rows outside proof-to-scale bounds: {len(target_rows)} "
            f"not in [{min_target_rows}, {max_target_rows}]"
        )
    return selected.sort_values(["sector", "institution_name", "unitid"]).reset_index(drop=True)


def discovery_input_for_sector(target_panel: pd.DataFrame, sector: str) -> pd.DataFrame:
    institutions = target_panel.loc[target_panel["sector"].eq(sector)].copy()
    if institutions.empty:
        return pd.DataFrame()
    institutions = institutions.sort_values(["institution_name", "unitid"]).drop_duplicates("unitid", keep="first")
    stream_id = stream_id_for_sector(sector)
    rows = pd.DataFrame(
        {
            "source_stream": stream_id,
            "benchmark_protocol": "clean_no_legacy_benchmark",
            "counts_as_clean_no_legacy_benchmark": True,
            "fresh_rank": range(1, len(institutions) + 1),
            "batch3_rank": range(1, len(institutions) + 1),
            "unitid": institutions["unitid"],
            "institution_name": institutions["institution_name"],
            "state": institutions["state"],
            "webaddr": institutions["homepage_url"],
            "clean_holdout_status": "proof_to_scale_needs_current_url_discovery",
            "created_at": utc_now(),
        }
    )
    return rows.reset_index(drop=True)


def truth_rows_for_sector(target_panel: pd.DataFrame, sector: str) -> pd.DataFrame:
    rows = target_panel.loc[target_panel["sector"].eq(sector)].copy()
    if rows.empty:
        return pd.DataFrame()
    truth = pd.DataFrame(
        {
            "truth_sector": rows["sector"],
            "unitid": rows["unitid"],
            "institution_name": rows["institution_name"],
            "state": rows["state"],
            "target_year": rows["academic_year"],
            "webaddr": rows["homepage_url"],
            "has_grad_outcome": True,
        }
    )
    return truth.sort_values(["institution_name", "unitid", "target_year"]).reset_index(drop=True)


def runtime_year_targets_from_target_panel(target_panel: pd.DataFrame) -> pd.DataFrame:
    required = {"unitid", "institution_name", "academic_year"}
    missing = sorted(required - set(target_panel.columns))
    if missing:
        raise ValueError(f"target panel missing required year-target columns: {missing}")
    targets = pd.DataFrame(
        {
            "unitid": target_panel["unitid"],
            "institution_name": target_panel["institution_name"].map(clean_text),
            "year": target_panel["academic_year"],
            "state": target_panel.get("state", ""),
            "webaddr": target_panel.get("homepage_url", ""),
            "sector": target_panel.get("sector", ""),
        }
    )
    targets["unitid"] = pd.to_numeric(targets["unitid"], errors="coerce").astype("Int64")
    targets["year"] = pd.to_numeric(targets["year"], errors="coerce").astype("Int64")
    targets = targets.dropna(subset=["unitid", "year"]).copy()
    return (
        targets.drop_duplicates(["unitid", "institution_name", "year"])
        .sort_values(["institution_name", "unitid", "year"])
        .reset_index(drop=True)
    )


def write_runtime_year_targets(repo_root: Path, target_panel: pd.DataFrame) -> Path:
    """Materialize the discovery compatibility target file from Step 1 inputs."""
    path = repo_root / INSTITUTION_YEAR_TARGETS_RUNTIME_INPUT
    write_csv(runtime_year_targets_from_target_panel(target_panel), path)
    return path


def write_discovery_inputs(repo_root: Path, target_panel: pd.DataFrame, sectors: list[str]) -> None:
    write_runtime_year_targets(repo_root, target_panel)
    for sector in sectors:
        outputs = stream_outputs(repo_root, sector)
        for path in outputs.__dict__.values():
            path.parent.mkdir(parents=True, exist_ok=True)
        truth_rows_for_sector(target_panel, sector).to_csv(outputs.truth_csv, index=False)
        discovery_input_for_sector(target_panel, sector).to_csv(outputs.discovery_input_csv, index=False)


def retrieval_text(result: dict[str, object]) -> str:
    body = result.get("body", b"")
    if not isinstance(body, bytes):
        body = b""
    text = decode_body(body, clean_text(result.get("content_type")))
    visible = visible_page_text(text, clean_text(result.get("content_type")))
    title = clean_text(result.get("page_title"))
    return "\n".join(piece for piece in [title, visible[:12000]] if piece)


def result_retrieved(result: dict[str, object]) -> bool:
    return clean_text(result.get("retrieval_status")) in RETRIEVED_STATUSES


class RetrievalWallClockTimeout(TimeoutError):
    """Raised when one source retrieval exceeds the production wall clock."""


def retrieval_error_result(error_type: str, error_message: str) -> dict[str, object]:
    return {
        "url": "",
        "final_url": "",
        "http_status": "",
        "content_type": "",
        "body": b"",
        "sha256": "",
        "retrieval_status": "error",
        "error_type": error_type,
        "error_message": error_message,
        "page_title": "",
        "links": [],
        "link_records": [],
    }


def retrieval_wall_timeout_seconds(timeout_seconds: int, override_seconds: float | None = None) -> float:
    if override_seconds is not None:
        return max(0.1, float(override_seconds))
    base = max(1.0, float(timeout_seconds))
    return max(2.0, base + min(5.0, base))


def _raise_retrieval_wall_timeout(signum: int, frame: object) -> None:
    raise RetrievalWallClockTimeout("retrieval exceeded wall-clock timeout")


def _retrieve_url_worker(url: str, timeout_seconds: int, max_bytes: int, output_queue: object) -> None:
    try:
        output_queue.put(retrieve_url(url, timeout_seconds=timeout_seconds, max_bytes=max_bytes))
    except BaseException as exc:
        output_queue.put(retrieval_error_result(type(exc).__name__, str(exc)))


def retrieve_url_in_subprocess(
    url: str,
    *,
    timeout_seconds: int,
    max_bytes: int,
    wall_timeout_seconds: float | None = None,
    subprocess_start_method: str = "spawn",
) -> dict[str, object]:
    resolved_wall_timeout = retrieval_wall_timeout_seconds(timeout_seconds, wall_timeout_seconds)
    context = mp.get_context(subprocess_start_method)
    output_queue = context.Queue(maxsize=1)
    process = context.Process(target=_retrieve_url_worker, args=(url, timeout_seconds, max_bytes, output_queue))
    process.start()
    deadline = time.monotonic() + resolved_wall_timeout
    result: dict[str, object] | None = None
    while time.monotonic() < deadline:
        try:
            result = output_queue.get(timeout=min(0.1, max(0.01, deadline - time.monotonic())))
            break
        except Empty:
            if not process.is_alive():
                try:
                    result = output_queue.get_nowait()
                except Empty:
                    result = None
                break
    if result is not None:
        process.join(2)
        if process.is_alive():
            process.terminate()
            process.join(2)
        return result
    if process.is_alive():
        process.terminate()
        process.join(2)
    else:
        process.join(2)
        try:
            result = output_queue.get_nowait()
        except Empty:
            result = None
    if result is not None:
        return result
    return retrieval_error_result(
        "RetrievalWallClockTimeout",
        f"retrieval exceeded wall-clock timeout after {resolved_wall_timeout:.1f}s",
    )


def retrieve_url_bounded(
    url: str,
    *,
    timeout_seconds: int,
    max_bytes: int,
    wall_timeout_seconds: float | None = None,
    use_subprocess: bool = False,
    subprocess_start_method: str = "spawn",
) -> dict[str, object]:
    if use_subprocess:
        return retrieve_url_in_subprocess(
            url,
            timeout_seconds=timeout_seconds,
            max_bytes=max_bytes,
            wall_timeout_seconds=wall_timeout_seconds,
            subprocess_start_method=subprocess_start_method,
        )
    resolved_wall_timeout = retrieval_wall_timeout_seconds(timeout_seconds, wall_timeout_seconds)
    previous_handler = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, _raise_retrieval_wall_timeout)
    signal.setitimer(signal.ITIMER_REAL, resolved_wall_timeout)
    try:
        return retrieve_url(url, timeout_seconds=timeout_seconds, max_bytes=max_bytes)
    except RetrievalWallClockTimeout as exc:
        return retrieval_error_result(type(exc).__name__, str(exc))
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


def retrieve_url_with_retries(
    url: str,
    *,
    timeout_seconds: int,
    max_bytes: int,
    attempts: int,
    wall_timeout_seconds: float | None = None,
    use_subprocess: bool = False,
    subprocess_start_method: str = "spawn",
) -> dict[str, object]:
    result: dict[str, object] = {}
    for attempt in range(max(1, attempts)):
        result = retrieve_url_bounded(
            url,
            timeout_seconds=timeout_seconds,
            max_bytes=max_bytes,
            wall_timeout_seconds=wall_timeout_seconds,
            use_subprocess=use_subprocess,
            subprocess_start_method=subprocess_start_method,
        )
        if result_retrieved(result):
            return result
        if attempt + 1 < attempts:
            time.sleep(min(2, attempt + 1))
    return result


def retrieve_candidate_with_wayback_recovery(
    candidate_url: str,
    *,
    target_year: int,
    timeout_seconds: int,
    max_source_bytes: int,
    allow_wayback_recovery: bool,
) -> tuple[str, dict[str, object], str, str]:
    """Retrieve a source URL, then try bounded Wayback recovery for dead sources."""
    result = retrieve_url_bounded(candidate_url, timeout_seconds=timeout_seconds, max_bytes=max_source_bytes)
    if result_retrieved(result) or not allow_wayback_recovery or urlparse(candidate_url).netloc.lower() == "web.archive.org":
        return candidate_url, result, "direct_retrieval", ""

    wayback_timeout_seconds = max(4, min(timeout_seconds, 12))
    wayback_wall_timeout_seconds = wayback_timeout_seconds + 2
    lookup_urls = [
        wayback_available_url(candidate_url, target_year),
        wayback_available_latest_url(candidate_url),
        wayback_cdx_url(candidate_url),
    ]
    for lookup_url in lookup_urls:
        lookup_result = retrieve_url_with_retries(
            lookup_url,
            timeout_seconds=wayback_timeout_seconds,
            max_bytes=5 * 1024 * 1024,
            attempts=1,
            wall_timeout_seconds=wayback_wall_timeout_seconds,
            use_subprocess=True,
            subprocess_start_method="spawn",
        )
        if not result_retrieved(lookup_result):
            continue
        body = lookup_result.get("body", b"")
        if not isinstance(body, bytes):
            continue
        snapshots: list[str] = []
        if "cdx?" in lookup_url:
            snapshots = [raw_wayback_snapshot_url(url) for url in parse_cdx_snapshots(body, target_year)[:5]]
        else:
            snapshot = parse_wayback_snapshot(body)
            if snapshot:
                snapshots = [raw_wayback_snapshot_url(snapshot)]
        for snapshot_url in snapshots:
            snapshot_result = retrieve_url_with_retries(
                snapshot_url,
                timeout_seconds=wayback_timeout_seconds,
                max_bytes=max_source_bytes,
                attempts=1,
                wall_timeout_seconds=wayback_wall_timeout_seconds,
                use_subprocess=True,
                subprocess_start_method="spawn",
            )
            if result_retrieved(snapshot_result):
                return snapshot_url, snapshot_result, "wayback_recovery", lookup_url
    return candidate_url, result, "direct_retrieval_failed_no_wayback_recovery", ""


def add_unique_candidate_option(options: list[dict[str, object]], option: dict[str, object]) -> None:
    candidate_url = clean_text(option.get("candidate_url"))
    if not candidate_url:
        return
    if any(clean_text(existing.get("candidate_url")) == candidate_url for existing in options):
        return
    options.append(option)


def candidate_options_for_row(
    *,
    row: pd.Series,
    legacy_row: pd.Series,
    namespace: str,
    repo_root: Path,
) -> list[dict[str, object]]:
    unitid = int(row["unitid"])
    year = int(row["academic_year"])
    institution = clean_text(row.get("institution_name"))
    sector = clean_text(row.get("sector"))
    state = clean_text(row.get("state"))
    options: list[dict[str, object]] = []

    legacy_candidate = clean_text(legacy_row.get("candidate_url"))
    if legacy_candidate:
        add_unique_candidate_option(
            options,
            {
                "unitid": unitid,
                "institution_name": institution,
                "sector": sector,
                "state": state,
                "academic_year": year,
                "candidate_url": legacy_candidate,
                "candidate_rank": 0,
                "candidate_generation_method": clean_text(legacy_row.get("candidate_generation_method"))
                or "raw_human_legacy_url",
                "candidate_source_file": clean_text(legacy_row.get("candidate_source_file"))
                or "raw_human_legacy_workbook",
                "candidate_source_type": clean_text(legacy_row.get("candidate_source_type")) or "human_legacy_url",
                "source_query_or_root": clean_text(legacy_row.get("source_query_or_root")),
                "candidate_generated_at": "raw_legacy_workbook",
                "url_source_bucket": "active_human_legacy_url",
                "catalog_year_start": legacy_row.get("catalog_year_start"),
                "catalog_year_end": legacy_row.get("catalog_year_end"),
                "candidate_link_text": "raw human legacy URL matched to target year by inferred catalog span",
                "candidate_evidence_source": legacy_candidate,
            },
        )

    current_candidate = clean_text(row.get("best_url"))
    if current_candidate:
        add_unique_candidate_option(
            options,
            {
                "unitid": unitid,
                "institution_name": institution,
                "sector": sector,
                "state": state,
                "academic_year": year,
                "candidate_url": current_candidate,
                "candidate_rank": 1,
                "candidate_generation_method": clean_text(row.get("best_url_source")) or "current_production_discovery",
                "candidate_source_file": repo_relative(row.get("_current_run_file"), repo_root)
                or "current_run_discovery_output",
                "candidate_source_type": clean_text(row.get("best_url_source")) or "current_production_discovery",
                "source_query_or_root": clean_text(row.get("archive_url")),
                "candidate_generated_at": namespace,
                "url_source_bucket": "current_production_discovery",
                "catalog_year_start": row.get("catalog_year_start"),
                "catalog_year_end": row.get("catalog_year_end"),
                "candidate_link_text": clean_text(row.get("candidate_link_text")),
                "candidate_evidence_source": clean_text(row.get("candidate_evidence_source")),
            },
        )
    return options


def int_or_none(value: object) -> int | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(parsed):
        return None
    return int(parsed)


def source_family_gap_fill_lookup(
    *,
    merged: pd.DataFrame,
    legacy_candidates: pd.DataFrame,
    namespace: str,
) -> dict[tuple[int, int], list[dict[str, object]]]:
    seeds_by_unitid: dict[int, list[dict[str, object]]] = {}

    def add_seed(unitid_value: object, url: object, start_value: object, end_value: object, method: object, source_file: object) -> None:
        unitid = int_or_none(unitid_value)
        start = int_or_none(start_value)
        end = int_or_none(end_value)
        seed_url = clean_text(url)
        if unitid is None or start is None or end is None or not seed_url:
            return
        seeds_by_unitid.setdefault(unitid, []).append(
            {
                "seed_url": seed_url,
                "source_year_start": start,
                "source_year_end": end,
                "seed_method": clean_text(method) or "same_institution_source_family_seed",
                "seed_source_file": clean_text(source_file) or "same_institution_source_family_seed",
            }
        )

    if not legacy_candidates.empty:
        for _, seed in legacy_candidates.iterrows():
            add_seed(
                seed.get("unitid"),
                seed.get("candidate_url"),
                seed.get("catalog_year_start"),
                seed.get("catalog_year_end"),
                seed.get("candidate_generation_method"),
                seed.get("candidate_source_file"),
            )

    for _, seed in merged.iterrows():
        add_seed(
            seed.get("unitid"),
            seed.get("best_url"),
            seed.get("catalog_year_start"),
            seed.get("catalog_year_end"),
            seed.get("best_url_source"),
            seed.get("_current_run_file"),
        )

    lookup: dict[tuple[int, int], list[dict[str, object]]] = {}
    for _, row in merged.iterrows():
        unitid = int(row["unitid"])
        year = int(row["academic_year"])
        options: list[dict[str, object]] = []
        for seed in seeds_by_unitid.get(unitid, []):
            probe_urls: list[tuple[str, int, int, str]] = []
            if seed["source_year_start"] <= year <= seed["source_year_end"]:
                probe_urls.append(
                    (
                        seed["seed_url"],
                        seed["source_year_start"],
                        seed["source_year_end"],
                        "same_institution_existing_multi_year_catalog_span",
                    )
                )
            for probe_year in [year - 1, year]:
                for candidate_url in inferred_year_url_replacements(
                    seed["seed_url"],
                    source_year=seed["source_year_start"],
                    target_year=probe_year,
                )[:8]:
                    inferred = infer_catalog_coverage_years(candidate_url)
                    if inferred:
                        candidate_start, candidate_end = inferred
                    else:
                        candidate_start, candidate_end = probe_year, probe_year + 1
                    if candidate_start <= year <= candidate_end:
                        probe_urls.append(
                            (
                                candidate_url,
                                candidate_start,
                                candidate_end,
                                "same_institution_source_family_gap_fill",
                            )
                        )
            for candidate_url, candidate_start, candidate_end, generation_method in probe_urls:
                add_unique_candidate_option(
                    options,
                    {
                        "unitid": unitid,
                        "institution_name": clean_text(row.get("institution_name")),
                        "sector": clean_text(row.get("sector")),
                        "state": clean_text(row.get("state")),
                        "academic_year": year,
                        "candidate_url": candidate_url,
                        "candidate_rank": 2 + len(options),
                        "candidate_generation_method": generation_method,
                        "candidate_source_file": seed["seed_source_file"],
                        "candidate_source_type": generation_method,
                        "source_query_or_root": seed["seed_url"],
                        "candidate_generated_at": namespace,
                        "url_source_bucket": generation_method,
                        "catalog_year_start": candidate_start,
                        "catalog_year_end": candidate_end,
                        "candidate_link_text": (
                            f"same-institution source-family URL probe covering "
                            f"{candidate_start}-{candidate_end} for target {year}"
                        ),
                        "candidate_evidence_source": (
                            f"generated from same-institution seed {seed['seed_url']} "
                            f"covering {seed['source_year_start']}-{seed['source_year_end']}"
                        ),
                    },
                )
                if len(options) >= 12:
                    break
            if len(options) >= 12:
                break
        if options:
            lookup[(unitid, year)] = options
    return lookup


def year_bounds_from_evidence(panel_row: pd.Series, evidence_text: str, target_year: int) -> tuple[str, str]:
    start = clean_text(panel_row.get("catalog_year_start"))
    end = clean_text(panel_row.get("catalog_year_end"))
    haystack = " ".join(
        [
            clean_text(panel_row.get("best_url")),
            clean_text(panel_row.get("candidate_url")),
            clean_text(panel_row.get("candidate_link_text")),
            clean_text(panel_row.get("candidate_evidence_source")),
            evidence_text[:12000],
        ]
    )
    inferred = infer_catalog_coverage_years(haystack)
    if start and end:
        supplied = str(int(float(start))), str(int(float(end)))
        if year_supported(supplied[0], supplied[1], target_year):
            return supplied
        if inferred and inferred[0] <= target_year <= inferred[1]:
            return str(inferred[0]), str(inferred[1])
        return supplied
    if inferred:
        return str(inferred[0]), str(inferred[1])
    if re.search(rf"\b{target_year}\b", haystack) or re.search(rf"\b{target_year + 1}\b", haystack):
        return str(target_year), str(target_year + 1)
    return "", ""


def year_supported(start: str, end: str, year: int) -> bool:
    try:
        start_int = int(float(start))
        end_int = int(float(end))
    except ValueError:
        return False
    return start_int <= year <= end_int


def source_type_for_url(url: str, content_type: str) -> str:
    lowered = f"{url} {content_type}".lower()
    if "image/" in lowered or re.search(r"\.(jpg|jpeg|png|gif|webp)(\?|#|$)", lowered):
        return "non_catalog_image"
    if ".pdf" in lowered or "pdf" in lowered:
        return "catalog_pdf"
    return "catalog_html_or_policy_page"


def preferred_child_source_url(candidate_url: str, result: dict[str, object]) -> tuple[str, str]:
    records = result.get("link_records", [])
    if not isinstance(records, list):
        return candidate_url, ""
    parsed_candidate = urlparse(candidate_url)
    scored: list[tuple[int, str, str]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        child_url = clean_text(record.get("url"))
        if not child_url:
            continue
        parsed_child = urlparse(child_url)
        if parsed_child.netloc.lower() != parsed_candidate.netloc.lower():
            continue
        label_text = " ".join(
            clean_text(record.get(column))
            for column in ["text", "title"]
            if clean_text(record.get(column))
        )
        context_text = clean_text(record.get("context"))
        haystack = f"{child_url} {label_text} {context_text}".lower()
        if "content.php" not in parsed_child.path.lower():
            continue
        score = 0
        for term, points in [
            ("rules and regulations", 500),
            ("undergraduate", 40),
            ("academic", 25),
            ("policy", 25),
            ("policies", 25),
            ("regulation", 25),
            ("catalog", 25),
        ]:
            if term in haystack:
                score += points
        if score:
            scored.append((score, child_url, f"{label_text} {context_text}".strip()))
    if not scored:
        return candidate_url, ""
    scored.sort(key=lambda item: (-item[0], item[1]))
    _, child_url, text = scored[0]
    return child_url, text[:300]


def source_type_confirmed(url: str, panel_row: pd.Series, evidence_text: str, content_type: str) -> bool:
    lowered_url_type = f"{url} {content_type}".lower()
    if "image/" in lowered_url_type or re.search(r"\.(jpg|jpeg|png|gif|webp)(\?|#|$)", lowered_url_type):
        return False
    haystack = " ".join(
        [
            url,
            clean_text(panel_row.get("candidate_link_text")),
            clean_text(panel_row.get("candidate_evidence_source")),
            evidence_text[:5000],
            content_type,
        ]
    ).lower()
    return any(
        term in haystack
        for term in ["catalog", "catalogue", "bulletin", "academic", "student handbook", "undergraduate"]
    )


COMMON_INSTITUTION_TOKENS = {
    "the",
    "and",
    "of",
    "at",
    "for",
    "university",
    "college",
    "institute",
    "technology",
    "state",
    "campus",
    "immersion",
}


def hostname_base_domain(value: object) -> str:
    text = clean_text(value)
    if not text:
        return ""
    parsed = urlparse(text if "://" in text else f"https://{text}")
    hostname = parsed.netloc.lower().split("@")[-1].split(":")[0]
    if hostname.startswith("www."):
        hostname = hostname[4:]
    labels = [label for label in hostname.split(".") if label]
    if len(labels) < 2:
        return hostname
    return ".".join(labels[-2:])


def institution_acronyms(institution_name: str) -> set[str]:
    raw_tokens = [token for token in re.split(r"[^a-z0-9]+", institution_name.lower()) if token]
    meaningful = [token for token in raw_tokens if token not in COMMON_INSTITUTION_TOKENS and len(token) > 1]
    aliases: set[str] = set()
    if len(raw_tokens) >= 3:
        aliases.add("".join(token[0] for token in raw_tokens if token not in {"the", "of", "and", "at", "for"}))
    if len(meaningful) >= 2:
        aliases.add("".join(token[0] for token in meaningful))
    return {alias for alias in aliases if len(alias) >= 3}


def institution_confirmed(institution_name: str, url: str, evidence_text: str, homepage_url: object = "") -> bool:
    name = institution_name.lower()
    text = f"{url} {evidence_text[:5000]}".lower()
    if name and name in text:
        return True
    url_host = urlparse(url).netloc.lower()
    homepage_base = hostname_base_domain(homepage_url)
    if homepage_base and (url_host == homepage_base or url_host.endswith(f".{homepage_base}")):
        return True
    if homepage_base and homepage_base in text:
        return True
    for alias in institution_acronyms(institution_name):
        if re.search(rf"(^|[^a-z0-9]){re.escape(alias)}([^a-z0-9]|$)", f"{url_host} {urlparse(url).path.lower()} {text}"):
            return True
    tokens = [token for token in re.split(r"[^a-z0-9]+", name) if len(token) > 3]
    if not tokens:
        return False
    if sum(token in text for token in tokens) >= min(2, len(tokens)):
        return True
    hostname = urlparse(url).netloc.lower()
    distinctive_tokens = [token for token in tokens if token not in {"university", "college", "state"}]
    return bool(distinctive_tokens) and any(token in hostname for token in distinctive_tokens)


def current_panel_for_targets(repo_root: Path, target_panel: pd.DataFrame, sectors: list[str]) -> pd.DataFrame:
    frames = []
    for sector in sectors:
        panel = read_best_full_year_panel(repo_root, sector)
        if panel.empty:
            continue
        panel["sector"] = sector
        frames.append(panel)
    if not frames:
        return pd.DataFrame(columns=["unitid", "target_year", "best_url"])
    panel = pd.concat(frames, ignore_index=True, sort=False)
    panel["unitid"] = pd.to_numeric(panel["unitid"], errors="coerce").astype("Int64")
    panel["target_year"] = pd.to_numeric(panel["target_year"], errors="coerce").astype("Int64")
    panel["best_url"] = panel.get("best_url", pd.Series("", index=panel.index)).map(clean_text)
    target_keys = target_panel[["unitid", "academic_year"]].copy()
    target_keys["unitid"] = pd.to_numeric(target_keys["unitid"], errors="coerce").astype("Int64")
    target_keys["target_year"] = pd.to_numeric(target_keys["academic_year"], errors="coerce").astype("Int64")
    panel = panel.merge(target_keys[["unitid", "target_year"]].drop_duplicates(), on=["unitid", "target_year"], how="inner")
    panel["_has_url"] = panel["best_url"].ne("")
    panel = panel.sort_values(
        ["unitid", "target_year", "_has_url", "_selected_panel_priority"],
        ascending=[True, True, False, True],
    )
    return panel.drop_duplicates(["unitid", "target_year"], keep="first")


def frame_with_columns(rows: list[dict[str, object]], base_columns: list[str]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    for column in base_columns:
        if column not in frame.columns:
            frame[column] = ""
    extra_columns = [column for column in frame.columns if column not in base_columns]
    return frame[[*base_columns, *extra_columns]]


def step1_run_config(
    *,
    chunk_id: str,
    release_id: str | None,
    namespace: str,
    benchmark_rows: int,
    min_ready_rate: float,
    min_sector_ready_rate: float,
    api_web_rescue_required_for_unresolved: bool,
    api_web_rescue_mode: str,
    api_web_rescue_status: str,
    api_web_rescue_reason: str,
    archive_expansion_completed: bool,
    raw_human_legacy_candidate_rows: int,
    source_review_row_timeout_seconds: float | None,
    excluded_unitid_count: int = 0,
    excluded_unitids_source: str = "",
) -> dict[str, object]:
    return {
        "chunk_id": chunk_id,
        "release_id": release_id or "",
        "year_scope": f"{ESTIMATION_START_YEAR}-{ESTIMATION_END_YEAR}",
        "target_panel_source": "Stata Files/Data/mainpanelgf_clean.dta",
        "run_namespace": namespace,
        "front_door": "actual target panel -> current URL discovery -> retrieval evidence -> source review -> production runner",
        "benchmark_mode": "raw_human_legacy_url_tested" if benchmark_rows else "not_tested",
        "benchmark_key": (
            "raw human legacy URL rows in this target panel, scored after candidate retrieval/source review"
            if benchmark_rows
            else "not supplied; benchmark scoring not applicable for this proof-to-scale production closure run"
        ),
        "production_readiness_min_ready_rate": min_ready_rate,
        "production_readiness_min_sector_ready_rate": min_sector_ready_rate,
        "api_web_rescue_required_for_unresolved": api_web_rescue_required_for_unresolved,
        "api_web_rescue_mode": api_web_rescue_mode,
        "api_web_rescue_status": api_web_rescue_status,
        "api_web_rescue_reason": api_web_rescue_reason,
        "archive_expansion_completed": archive_expansion_completed,
        "raw_human_legacy_candidate_rows": raw_human_legacy_candidate_rows,
        "source_review_row_timeout_seconds": (
            source_review_row_timeout_seconds if source_review_row_timeout_seconds is not None else "disabled"
        ),
        "excluded_unitid_count": excluded_unitid_count,
        "excluded_unitids_source": excluded_unitids_source,
    }


def benchmark_rows_for_legacy_candidates(legacy_candidates: pd.DataFrame) -> list[dict[str, object]]:
    benchmark_rows: list[dict[str, object]] = []
    if legacy_candidates.empty:
        return benchmark_rows
    for _, benchmark in legacy_candidates.iterrows():
        benchmark_rows.append(
            {
                "benchmark_group": "raw_human_legacy_url",
                "unitid": int(benchmark["unitid"]),
                "institution_name": clean_text(benchmark.get("institution_name")),
                "academic_year": int(benchmark["academic_year"]),
                "benchmark_url": clean_text(benchmark.get("candidate_url")),
            }
        )
    return benchmark_rows


def write_step1_input_snapshot(
    input_dir: Path,
    *,
    target_panel: pd.DataFrame,
    candidate_rows: list[dict[str, object]],
    review_rows: list[dict[str, object]],
    historical_case_precheck: pd.DataFrame,
    evidence_rows: list[dict[str, object]],
    benchmark_rows: list[dict[str, object]],
    config: dict[str, object],
) -> None:
    input_dir.mkdir(parents=True, exist_ok=True)
    (input_dir / "run_config.json").write_text(json.dumps(config, indent=2, sort_keys=True), encoding="utf-8")
    write_csv(target_panel, input_dir / "target_panel.csv")
    write_csv(frame_with_columns(candidate_rows, CANDIDATE_COLUMNS), input_dir / "candidate_url_ledger.csv")
    write_csv(frame_with_columns(review_rows, SOURCE_REVIEW_COLUMNS), input_dir / "source_review_log.csv")
    write_csv(historical_case_precheck, input_dir / "historical_case_precheck.csv")
    write_csv(frame_with_columns(evidence_rows, EVIDENCE_COLUMNS), input_dir / "source_evidence_manifest.csv")
    write_csv(frame_with_columns(benchmark_rows, BENCHMARK_COLUMNS), input_dir / "benchmark_key.csv")


def write_initial_step1_input_snapshot(
    repo_root: Path,
    *,
    target_panel: pd.DataFrame,
    namespace: str,
    chunk_id: str,
    release_id: str | None,
    input_dir: Path,
    min_ready_rate: float,
    min_sector_ready_rate: float,
    api_web_rescue_mode: str,
    api_web_rescue_status: str,
    api_web_rescue_reason: str,
    api_web_rescue_required_for_unresolved: bool = False,
    archive_expansion_completed: bool = False,
    raw_human_legacy_candidate_rows: int = 0,
    source_review_row_timeout_seconds: float | None = None,
    excluded_unitid_count: int = 0,
    excluded_unitids_source: str = "",
) -> None:
    historical_case_precheck = build_historical_case_precheck(repo_root, target_panel, namespace)
    config = step1_run_config(
        chunk_id=chunk_id,
        release_id=release_id,
        namespace=namespace,
        benchmark_rows=0,
        min_ready_rate=min_ready_rate,
        min_sector_ready_rate=min_sector_ready_rate,
        api_web_rescue_required_for_unresolved=api_web_rescue_required_for_unresolved,
        api_web_rescue_mode=api_web_rescue_mode,
        api_web_rescue_status=api_web_rescue_status,
        api_web_rescue_reason=api_web_rescue_reason,
        archive_expansion_completed=archive_expansion_completed,
        raw_human_legacy_candidate_rows=raw_human_legacy_candidate_rows,
        source_review_row_timeout_seconds=source_review_row_timeout_seconds,
        excluded_unitid_count=excluded_unitid_count,
        excluded_unitids_source=excluded_unitids_source,
    )
    write_step1_input_snapshot(
        input_dir,
        target_panel=target_panel,
        candidate_rows=[],
        review_rows=[],
        historical_case_precheck=historical_case_precheck,
        evidence_rows=[],
        benchmark_rows=[],
        config=config,
    )


def csv_row_count(path: Path) -> int | str:
    if not path.exists() or path.stat().st_size == 0:
        return 0
    try:
        return len(pd.read_csv(path, low_memory=False))
    except Exception:
        return "unavailable"


def existing_partial_artifact_paths(repo_root: Path, namespace: str, input_dir: Path) -> list[Path]:
    candidates = [
        input_dir / "target_panel.csv",
        input_dir / "candidate_url_ledger.csv",
        input_dir / "source_review_log.csv",
        input_dir / "historical_case_precheck.csv",
        input_dir / "source_evidence_manifest.csv",
        input_dir / "benchmark_key.csv",
        input_dir / "run_config.json",
        repo_root / PRODUCTION_SELECTION_ROOT / namespace / "selected_institutions.csv",
        repo_root / PRODUCTION_SELECTION_ROOT / namespace / "selection_summary.csv",
        repo_root / INSTITUTION_YEAR_TARGETS_RUNTIME_INPUT,
    ]
    for stream_dir in (repo_root / URL_DISCOVERY_ROOT).glob(f"*{namespace}*"):
        if stream_dir.is_dir():
            candidates.append(stream_dir)
    return [path for path in candidates if path.exists()]


def write_run_stop_report(
    repo_root: Path,
    *,
    namespace: str,
    input_dir: Path,
    stage: str,
    reason: str,
    started_monotonic: float | None,
    target_panel: pd.DataFrame | None,
    exception: BaseException | None = None,
) -> Path:
    input_dir.mkdir(parents=True, exist_ok=True)
    elapsed = "" if started_monotonic is None else f"{time.monotonic() - started_monotonic:.1f}s"
    target_rows = "" if target_panel is None else len(target_panel)
    target_institutions = "" if target_panel is None or target_panel.empty else int(target_panel["unitid"].nunique())
    candidate_rows = csv_row_count(input_dir / "candidate_url_ledger.csv")
    review_rows = csv_row_count(input_dir / "source_review_log.csv")
    evidence_rows = csv_row_count(input_dir / "source_evidence_manifest.csv")
    completed_target_rows: int | str = 0
    review_path = input_dir / "source_review_log.csv"
    if review_path.exists() and review_path.stat().st_size > 0:
        try:
            review = pd.read_csv(review_path, low_memory=False)
            if {"unitid", "academic_year"}.issubset(review.columns):
                completed_target_rows = len(review[["unitid", "academic_year"]].drop_duplicates())
        except Exception:
            completed_target_rows = "unavailable"
    partial_paths = existing_partial_artifact_paths(repo_root, namespace, input_dir)
    lines = [
        "# Run Stop Report",
        "",
        f"- namespace: `{namespace}`",
        f"- stage_stopped: `{stage}`",
        f"- reason: {reason}",
        f"- elapsed_time: {elapsed or 'unavailable'}",
        f"- target_institutions: {target_institutions if target_institutions != '' else 'unavailable'}",
        f"- target_rows: {target_rows if target_rows != '' else 'unavailable'}",
        f"- completed_target_rows_with_review_entries: {completed_target_rows}",
        f"- candidate_url_ledger_rows: {candidate_rows}",
        f"- source_review_log_rows: {review_rows}",
        f"- source_evidence_manifest_rows: {evidence_rows}",
        "",
        "No valid `production_chunk_*` or `production_release_*` was produced by this stopped run.",
        "",
        "## Key Partial Artifacts",
    ]
    if partial_paths:
        lines.extend(f"- `{repo_relative(path, repo_root)}`" for path in partial_paths)
    else:
        lines.append("- None available before stop.")
    if exception is not None:
        lines.extend(
            [
                "",
                "## Exception",
                f"- type: `{type(exception).__name__}`",
                f"- message: {clean_text(exception)}",
            ]
        )
    report_path = input_dir / "RUN_STOP_REPORT.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def build_step1_inputs(
    repo_root: Path,
    *,
    target_panel: pd.DataFrame,
    sectors: list[str],
    namespace: str,
    chunk_id: str,
    release_id: str | None,
    input_dir: Path,
    timeout_seconds: int,
    max_source_bytes: int,
    raw_legacy: pd.DataFrame | None = None,
    include_raw_legacy_candidates: bool = False,
    archive_expansion_completed: bool = False,
    api_web_rescue_mode: str = "not_run",
    api_web_rescue_status: str = "not_run",
    api_web_rescue_reason: str = "",
    min_ready_rate: float = 0.0,
    min_sector_ready_rate: float = 0.0,
    api_web_rescue_required_for_unresolved: bool = False,
    allow_wayback_recovery: bool = True,
    source_review_row_timeout_seconds: float | None = 90.0,
    excluded_unitid_count: int = 0,
    excluded_unitids_source: str = "",
) -> Path:
    input_dir = input_dir if input_dir.is_absolute() else repo_root / input_dir
    if input_dir.exists():
        shutil.rmtree(input_dir)
    input_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = input_dir / "source_evidence_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    panel = current_panel_for_targets(repo_root, target_panel, sectors)
    raw_legacy = raw_legacy if raw_legacy is not None else pd.DataFrame()
    legacy_candidates = (
        raw_legacy_candidates_for_target(target_panel, raw_legacy)
        if include_raw_legacy_candidates and not raw_legacy.empty
        else pd.DataFrame()
    )
    legacy_lookup: dict[tuple[int, int], pd.Series] = {}
    if not legacy_candidates.empty:
        for _, legacy_row in legacy_candidates.iterrows():
            legacy_lookup[(int(legacy_row["unitid"]), int(legacy_row["academic_year"]))] = legacy_row
    benchmark_rows = benchmark_rows_for_legacy_candidates(legacy_candidates)
    historical_case_precheck = build_historical_case_precheck(repo_root, target_panel, namespace)
    config = step1_run_config(
        chunk_id=chunk_id,
        release_id=release_id,
        namespace=namespace,
        benchmark_rows=len(benchmark_rows),
        min_ready_rate=min_ready_rate,
        min_sector_ready_rate=min_sector_ready_rate,
        api_web_rescue_required_for_unresolved=api_web_rescue_required_for_unresolved,
        api_web_rescue_mode=api_web_rescue_mode,
        api_web_rescue_status=api_web_rescue_status,
        api_web_rescue_reason=api_web_rescue_reason,
        archive_expansion_completed=archive_expansion_completed,
        raw_human_legacy_candidate_rows=len(legacy_candidates),
        source_review_row_timeout_seconds=source_review_row_timeout_seconds,
        excluded_unitid_count=excluded_unitid_count,
        excluded_unitids_source=excluded_unitids_source,
    )
    merged = target_panel.merge(
        panel[
            [
                column
                for column in [
                    "unitid",
                    "target_year",
                    "best_url",
                    "best_url_source",
                    "catalog_year_start",
                    "catalog_year_end",
                    "candidate_link_text",
                    "candidate_evidence_source",
                    "archive_url",
                    "_current_run_file",
                    "_selected_panel_file",
                    "sector",
                ]
                if column in panel.columns
            ]
        ],
        left_on=["unitid", "academic_year", "sector"],
        right_on=["unitid", "target_year", "sector"],
        how="left",
    )
    merged["best_url"] = merged.get("best_url", pd.Series("", index=merged.index)).map(clean_text)
    gap_fill_lookup = source_family_gap_fill_lookup(
        merged=merged,
        legacy_candidates=legacy_candidates,
        namespace=namespace,
    )

    candidate_rows: list[dict[str, object]] = []
    review_rows: list[dict[str, object]] = []
    evidence_rows: list[dict[str, object]] = []
    retrieval_cache: dict[tuple[str, bool], tuple[str, dict[str, object], str, str]] = {}
    write_step1_input_snapshot(
        input_dir,
        target_panel=target_panel,
        candidate_rows=candidate_rows,
        review_rows=review_rows,
        historical_case_precheck=historical_case_precheck,
        evidence_rows=evidence_rows,
        benchmark_rows=benchmark_rows,
        config=config,
    )

    ordered_rows = merged.sort_values(["sector", "institution_name", "unitid", "academic_year"])
    total_rows = len(ordered_rows)
    for processed_index, (_, row) in enumerate(ordered_rows.iterrows(), start=1):
        if processed_index == 1 or processed_index % 25 == 0 or processed_index == total_rows:
            print(f"[source-review] {processed_index}/{total_rows} target rows", flush=True)
        row_started = time.monotonic()
        row_deadline = (
            row_started + max(0.1, float(source_review_row_timeout_seconds))
            if source_review_row_timeout_seconds is not None
            else None
        )
        reviewed_candidates_for_row = 0
        unitid = int(row["unitid"])
        year = int(row["academic_year"])
        institution = clean_text(row.get("institution_name"))
        legacy_row = legacy_lookup.get((unitid, year), pd.Series(dtype=object))
        row = row.copy()
        candidate_options = candidate_options_for_row(
            row=row,
            legacy_row=legacy_row,
            namespace=namespace,
            repo_root=repo_root,
        )
        for gap_option in gap_fill_lookup.get((unitid, year), []):
            add_unique_candidate_option(candidate_options, gap_option)
        if not candidate_options:
            review_rows.append(
                {
                    "unitid": unitid,
                    "institution_name": institution,
                    "sector": clean_text(row.get("sector")),
                    "state": clean_text(row.get("state")),
                    "academic_year": year,
                    "candidate_url": "",
                    "candidate_generation_method": "no_candidate_after_current_production_search",
                    "candidate_source_file": "current_production_discovery_output",
                    "candidate_source_type": "no_candidate_after_current_production_search",
                    "source_query_or_root": clean_text(row.get("homepage_url")),
                    "retrieval_status": "not_retrieved_no_candidate",
                    "source_opened": False,
                    "institution_match_confirmed": False,
                    "campus_or_unitid_match_confirmed": False,
                    "source_scope_confirmed": False,
                    "source_type_confirmed": False,
                    "year_coverage_confirmed": False,
                    "archive_child_links_checked": False,
                    "gap_fill_search_completed": True,
                    "panel_consistency_confirmed": False,
                    "deterministic_search_completed": True,
                    "archive_expansion_completed": archive_expansion_completed,
                    "api_web_rescue_mode": api_web_rescue_mode,
                    "api_web_rescue_status": api_web_rescue_status,
                    "api_web_rescue_reason": api_web_rescue_reason,
                    "review_decision": "not_reviewed_no_target_year_candidate",
                    "review_reason": (
                        "Current production discovery produced no candidate URL for this target row; "
                        f"archive_expansion_completed={archive_expansion_completed}; "
                        f"api_web_rescue_status={api_web_rescue_status or 'not_run'}."
                    ),
                    "reviewed_by": "codex_current_run_source_review_from_retrieval_evidence",
                    "reviewed_at": namespace,
                }
            )
            write_step1_input_snapshot(
                input_dir,
                target_panel=target_panel,
                candidate_rows=candidate_rows,
                review_rows=review_rows,
                historical_case_precheck=historical_case_precheck,
                evidence_rows=evidence_rows,
                benchmark_rows=benchmark_rows,
                config=config,
            )
            continue

        for option_index, option in enumerate(candidate_options, start=1):
            candidate_url_for_budget = clean_text(option.get("candidate_url"))
            if row_deadline is not None and time.monotonic() >= row_deadline:
                review_rows.append(
                    {
                        "unitid": unitid,
                        "institution_name": institution,
                        "sector": clean_text(row.get("sector")),
                        "state": clean_text(row.get("state")),
                        "academic_year": year,
                        "candidate_url": candidate_url_for_budget,
                        "final_url_after_redirect": candidate_url_for_budget,
                        "retrieval_status": "not_retrieved_source_review_budget_exceeded",
                        "http_status": "",
                        "content_type": "",
                        "source_page_title": "",
                        "source_opened": False,
                        "institution_match_confirmed": False,
                        "campus_or_unitid_match_confirmed": False,
                        "source_scope_confirmed": False,
                        "source_type_confirmed": False,
                        "year_coverage_confirmed": False,
                        "archive_child_links_checked": False,
                        "gap_fill_search_completed": True,
                        "panel_consistency_confirmed": False,
                        "deterministic_search_completed": True,
                        "archive_expansion_completed": archive_expansion_completed,
                        "api_web_rescue_mode": api_web_rescue_mode,
                        "api_web_rescue_status": api_web_rescue_status,
                        "api_web_rescue_reason": api_web_rescue_reason,
                        "retrieval_recovery_method": "source_review_row_budget_exceeded",
                        "retrieval_recovery_source": "",
                        "candidate_generation_method": clean_text(option.get("candidate_generation_method")),
                        "candidate_source_file": clean_text(option.get("candidate_source_file")),
                        "candidate_source_type": clean_text(option.get("candidate_source_type")),
                        "source_query_or_root": clean_text(option.get("source_query_or_root")),
                        "source_type": "",
                        "source_year_start": "",
                        "source_year_end": "",
                        "source_year_coverage_note": (
                            f"source-review row time budget exceeded after reviewing "
                            f"{reviewed_candidates_for_row} candidate(s)"
                        ),
                        "url_source_bucket": clean_text(option.get("url_source_bucket")),
                        "review_decision": "reject_source_review_budget_exceeded",
                        "review_reason": (
                            f"Source-review row time budget exceeded after reviewing "
                            f"{reviewed_candidates_for_row} candidate(s); remaining candidates were "
                            "closed unresolved for production-scale runtime control."
                        ),
                        "reviewed_by": "codex_current_run_source_review_from_retrieval_evidence",
                        "reviewed_at": namespace,
                        "source_evidence_note": "",
                    }
                )
                write_step1_input_snapshot(
                    input_dir,
                    target_panel=target_panel,
                    candidate_rows=candidate_rows,
                    review_rows=review_rows,
                    historical_case_precheck=historical_case_precheck,
                    evidence_rows=evidence_rows,
                    benchmark_rows=benchmark_rows,
                    config=config,
                )
                break
            option_row = row.copy()
            option_row["catalog_year_start"] = option.get("catalog_year_start")
            option_row["catalog_year_end"] = option.get("catalog_year_end")
            option_row["candidate_link_text"] = option.get("candidate_link_text")
            option_row["candidate_evidence_source"] = option.get("candidate_evidence_source")
            candidate_url = clean_text(option.get("candidate_url"))
            candidate_generation_method = clean_text(option.get("candidate_generation_method"))
            candidate_source_file = clean_text(option.get("candidate_source_file"))
            candidate_source_type = clean_text(option.get("candidate_source_type"))
            source_query_or_root = clean_text(option.get("source_query_or_root"))
            url_source_bucket = clean_text(option.get("url_source_bucket"))
            candidate_rows.append(
                {
                    "unitid": unitid,
                    "institution_name": institution,
                    "sector": clean_text(row.get("sector")),
                    "state": clean_text(row.get("state")),
                    "academic_year": year,
                    "candidate_url": candidate_url,
                    "candidate_rank": option.get("candidate_rank", option_index),
                    "candidate_generation_method": candidate_generation_method,
                    "candidate_source_file": candidate_source_file,
                    "candidate_source_type": candidate_source_type,
                    "source_query_or_root": source_query_or_root,
                    "candidate_generated_at": clean_text(option.get("candidate_generated_at")) or namespace,
                }
            )
            write_step1_input_snapshot(
                input_dir,
                target_panel=target_panel,
                candidate_rows=candidate_rows,
                review_rows=review_rows,
                historical_case_precheck=historical_case_precheck,
                evidence_rows=evidence_rows,
                benchmark_rows=benchmark_rows,
                config=config,
            )

            cache_key = (candidate_url, allow_wayback_recovery)
            if cache_key in retrieval_cache:
                candidate_url, result, retrieval_method, recovery_source = retrieval_cache[cache_key]
            else:
                candidate_url, result, retrieval_method, recovery_source = retrieve_candidate_with_wayback_recovery(
                    candidate_url,
                    target_year=year,
                    timeout_seconds=timeout_seconds,
                    max_source_bytes=max_source_bytes,
                    allow_wayback_recovery=allow_wayback_recovery,
                )
                retrieval_cache[cache_key] = (candidate_url, result, retrieval_method, recovery_source)
            reviewed_candidates_for_row += 1
            if retrieval_method == "wayback_recovery":
                candidate_rows[-1]["candidate_url"] = candidate_url
                candidate_rows[-1]["candidate_generation_method"] = f"{candidate_generation_method}_wayback_recovery"
                candidate_rows[-1]["candidate_source_type"] = f"{candidate_source_type}_wayback_recovery"
                candidate_rows[-1]["source_query_or_root"] = recovery_source
                candidate_generation_method = f"{candidate_generation_method}_wayback_recovery"
                candidate_source_type = f"{candidate_source_type}_wayback_recovery"
                source_query_or_root = recovery_source
                url_source_bucket = f"{url_source_bucket}_wayback_recovery"

            child_checked = bool(result.get("link_records"))
            promoted_url, promoted_link_text = preferred_child_source_url(candidate_url, result)
            if promoted_url != candidate_url:
                original_url = candidate_url
                candidate_url = promoted_url
                result = retrieve_url_bounded(candidate_url, timeout_seconds=timeout_seconds, max_bytes=max_source_bytes)
                child_checked = True
                candidate_rows[-1]["candidate_url"] = candidate_url
                candidate_rows[-1]["candidate_generation_method"] = "child_policy_link_from_catalog_page"
                candidate_rows[-1]["candidate_source_type"] = "child_policy_link_from_catalog_page"
                candidate_rows[-1]["source_query_or_root"] = original_url
                candidate_generation_method = "child_policy_link_from_catalog_page"
                candidate_source_type = "child_policy_link_from_catalog_page"
                source_query_or_root = original_url
                url_source_bucket = "child_policy_link_from_catalog_page"
                if promoted_link_text:
                    option_row = option_row.copy()
                    option_row["candidate_link_text"] = promoted_link_text

            source_text = retrieval_text(result)
            final_url = clean_text(result.get("final_url")) or candidate_url
            content_type = clean_text(result.get("content_type"))
            retrieved = result_retrieved(result)
            option_row = option_row.copy()
            option_row["candidate_url"] = candidate_url
            option_row["best_url"] = candidate_url
            start, end = year_bounds_from_evidence(option_row, source_text, year)
            institution_ok = retrieved and institution_confirmed(institution, final_url, source_text, row.get("homepage_url"))
            source_type_ok = retrieved and source_type_confirmed(final_url, option_row, source_text, content_type)
            year_ok = retrieved and year_supported(start, end, year)
            accepted = institution_ok and source_type_ok and year_ok
            evidence_excerpt = source_text[:12000] or f"{clean_text(result.get('page_title'))} {final_url}".strip()
            cache_path = cache_dir / f"{unitid}_{year}_{safe_slug(institution)}_{option_index}.txt"
            cache_text = evidence_excerpt + "\n"
            cache_path.write_text(cache_text, encoding="utf-8")
            evidence_sha = sha256_text(cache_text)
            evidence_rows.append(
                {
                    "unitid": unitid,
                    "academic_year": year,
                    "candidate_url": candidate_url,
                    "cached_text_path": cache_path.relative_to(input_dir).as_posix(),
                    "cached_text_sha256": evidence_sha,
                    "source_body_sha256": clean_text(result.get("sha256")) or evidence_sha,
                }
            )

            if accepted:
                decision = "accept_multi_year_catalog" if start != str(year) or end != str(year) else "accept_exact_year_catalog"
                reason = "Current-run retrieval confirmed institution, source type, and target year/span evidence."
                if retrieval_method == "wayback_recovery":
                    reason += " Dead source URL was recovered through bounded Wayback lookup."
            elif not retrieved:
                decision = "reject_dead_or_unretrievable"
                reason = f"Current-run retrieval failed: {clean_text(result.get('retrieval_status'))} {clean_text(result.get('error_type'))}"
                if allow_wayback_recovery:
                    reason += "; bounded Wayback recovery did not retrieve usable source evidence."
            elif not institution_ok:
                decision = "reject_wrong_institution"
                reason = "Current-run evidence did not confirm the target institution."
            elif not source_type_ok:
                decision = "reject_not_catalog_or_policy_source"
                reason = "Current-run evidence did not confirm catalog/bulletin/academic policy source type."
            else:
                decision = "reject_wrong_year"
                reason = f"Current-run evidence did not confirm target year {year}; inferred span {start or 'missing'}-{end or 'missing'}."

            review_rows.append(
                {
                    "unitid": unitid,
                    "institution_name": institution,
                    "sector": clean_text(row.get("sector")),
                    "state": clean_text(row.get("state")),
                    "academic_year": year,
                    "candidate_url": candidate_url,
                    "final_url_after_redirect": final_url,
                    "retrieval_status": clean_text(result.get("retrieval_status")),
                    "http_status": clean_text(result.get("http_status")),
                    "content_type": content_type,
                    "source_page_title": clean_text(result.get("page_title")),
                    "source_opened": retrieved,
                    "institution_match_confirmed": institution_ok,
                    "campus_or_unitid_match_confirmed": institution_ok,
                    "source_scope_confirmed": source_type_ok,
                    "source_type_confirmed": source_type_ok,
                    "year_coverage_confirmed": year_ok,
                    "archive_child_links_checked": child_checked,
                    "gap_fill_search_completed": True,
                    "panel_consistency_confirmed": accepted,
                    "deterministic_search_completed": True,
                    "archive_expansion_completed": archive_expansion_completed,
                    "api_web_rescue_mode": api_web_rescue_mode,
                    "api_web_rescue_status": api_web_rescue_status,
                    "api_web_rescue_reason": api_web_rescue_reason,
                    "retrieval_recovery_method": retrieval_method,
                    "retrieval_recovery_source": recovery_source,
                    "candidate_generation_method": candidate_generation_method,
                    "candidate_source_file": candidate_source_file,
                    "candidate_source_type": candidate_source_type,
                    "source_query_or_root": source_query_or_root,
                    "source_type": source_type_for_url(final_url, content_type),
                    "source_year_start": start,
                    "source_year_end": end,
                    "source_year_coverage_note": clean_text(option_row.get("candidate_link_text")) or f"inferred from current-run evidence: {start}-{end}",
                    "url_source_bucket": url_source_bucket,
                    "review_decision": decision,
                    "review_reason": reason,
                    "reviewed_by": "codex_current_run_source_review_from_retrieval_evidence",
                    "reviewed_at": namespace,
                    "source_evidence_note": cache_path.relative_to(input_dir).as_posix(),
                }
            )
            write_step1_input_snapshot(
                input_dir,
                target_panel=target_panel,
                candidate_rows=candidate_rows,
                review_rows=review_rows,
                historical_case_precheck=historical_case_precheck,
                evidence_rows=evidence_rows,
                benchmark_rows=benchmark_rows,
                config=config,
            )
            if accepted:
                break

    write_step1_input_snapshot(
        input_dir,
        target_panel=target_panel,
        candidate_rows=candidate_rows,
        review_rows=review_rows,
        historical_case_precheck=historical_case_precheck,
        evidence_rows=evidence_rows,
        benchmark_rows=benchmark_rows,
        config=config,
    )
    return input_dir


def write_selection_audit(repo_root: Path, namespace: str, selected: pd.DataFrame, target_panel: pd.DataFrame) -> None:
    out_dir = repo_root / PRODUCTION_SELECTION_ROOT / namespace
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    selected.to_csv(out_dir / "selected_institutions.csv", index=False)
    summary = (
        target_panel.groupby(["sector", "has_human_legacy_source"], dropna=False)
        .agg(institutions=("unitid", "nunique"), target_rows=("academic_year", "size"))
        .reset_index()
    )
    summary.to_csv(out_dir / "selection_summary.csv", index=False)


def run_proof_to_scale(
    repo_root: Path,
    *,
    namespace: str,
    chunk_id: str,
    release_id: str | None,
    selection_mode: str,
    institution_count: int,
    public_institution_count: int,
    private_institution_count: int,
    min_target_rows: int,
    max_target_rows: int,
    timeout_seconds: int,
    max_root_candidates_per_institution: int,
    max_archive_pages_per_institution: int,
    max_workers: int,
    run_inferred_year_rescue: bool,
    run_archive_expansion: bool,
    run_wayback_cdx_rescue: bool,
    run_ai_year_gap_rescue: bool,
    max_api_cases: int | None,
    include_raw_legacy_candidates: bool,
    min_ready_rate: float,
    min_sector_ready_rate: float,
    api_web_rescue_mode: str,
    api_web_rescue_status: str,
    api_web_rescue_reason: str,
    build_release: bool,
    source_review_row_timeout_seconds: float | None,
    exclude_unitids_file: Path | None = None,
) -> ProofToScaleResult:
    repo_root = repo_root.resolve()
    input_dir = repo_root / PRODUCTION_INPUTS_ROOT / namespace
    started_monotonic = time.monotonic()
    stage = "initializing"
    target_panel: pd.DataFrame | None = None
    try:
        set_run_namespace(namespace)
        stage = "loading target universe"
        target_universe = load_target_panel_universe(repo_root)
        raw_legacy = load_raw_legacy_url_rows(repo_root)
        historical_priority = load_historical_priority_buckets(repo_root)
        excluded_unitids = load_excluded_unitids(exclude_unitids_file, repo_root)
        excluded_unitids_source = repo_relative(exclude_unitids_file, repo_root) if exclude_unitids_file is not None else ""
        stage = "selecting target panel"
        if selection_mode == "high_legacy_coverage":
            selected = select_high_legacy_coverage_institutions(
                target_universe,
                raw_legacy,
                public_count=public_institution_count,
                private_count=private_institution_count,
                min_target_rows=min_target_rows,
                max_target_rows=max_target_rows,
            )
        elif selection_mode == "representative":
            selected = select_representative_institutions(
                target_universe,
                institution_count=institution_count,
                min_target_rows=min_target_rows,
                max_target_rows=max_target_rows,
            )
        else:
            selected = select_prior_valid_legacy_reverification_institutions(
                target_universe,
                historical_priority,
                raw_legacy,
                public_count=public_institution_count,
                private_count=private_institution_count,
                min_target_rows=min_target_rows,
                max_target_rows=max_target_rows,
                exclude_unitids=excluded_unitids,
            )
        target_panel = target_panel_for_selection(target_universe, selected)
        sectors = sorted(target_panel["sector"].dropna().map(clean_text).unique().tolist())
        stage = "writing selection audit"
        write_selection_audit(repo_root, namespace, selected, target_panel)
        stage = "writing discovery runtime inputs"
        write_discovery_inputs(repo_root, target_panel, sectors)
        if input_dir.exists():
            shutil.rmtree(input_dir)
        initial_raw_legacy_candidate_rows = (
            len(raw_legacy_candidates_for_target(target_panel, raw_legacy))
            if include_raw_legacy_candidates and not raw_legacy.empty
            else 0
        )
        write_initial_step1_input_snapshot(
            repo_root,
            target_panel=target_panel,
            namespace=namespace,
            chunk_id=chunk_id,
            release_id=release_id,
            input_dir=input_dir,
            min_ready_rate=min_ready_rate,
            min_sector_ready_rate=min_sector_ready_rate,
            api_web_rescue_mode=api_web_rescue_mode,
            api_web_rescue_status=api_web_rescue_status,
            api_web_rescue_reason=api_web_rescue_reason,
            api_web_rescue_required_for_unresolved=run_ai_year_gap_rescue,
            archive_expansion_completed=False,
            raw_human_legacy_candidate_rows=initial_raw_legacy_candidate_rows,
            source_review_row_timeout_seconds=source_review_row_timeout_seconds,
            excluded_unitid_count=len(excluded_unitids),
            excluded_unitids_source=excluded_unitids_source,
        )

        for sector in sectors:
            sector_institutions = int(target_panel.loc[target_panel["sector"].eq(sector), "unitid"].nunique())
            if sector_institutions == 0:
                continue
            stage = f"running {sector} discovery"
            run_discovery_for_sector(
                repo_root,
                sector,
                limit=None,
                rank_start=1,
                timeout_seconds=timeout_seconds,
                max_root_candidates_per_institution=max_root_candidates_per_institution,
                max_archive_pages_per_institution=max_archive_pages_per_institution,
                max_workers=max_workers,
                chunk_size=max(1, sector_institutions),
                resume=False,
                skip_network_preflight=True,
            )
            if run_inferred_year_rescue:
                stage = f"running {sector} inferred-year rescue"
                run_inferred_year_url_rescue_for_sector(repo_root, sector, timeout_seconds=timeout_seconds, max_workers=max_workers)
            if run_archive_expansion:
                stage = f"running {sector} archive expansion"
                run_archive_expansion_rescue_for_sector(
                    repo_root,
                    sector,
                    timeout_seconds=timeout_seconds,
                    max_archive_pages_per_institution=max_archive_pages_per_institution,
                    max_seed_roots_per_institution=max_archive_pages_per_institution,
                    max_workers=max_workers,
                )
            if run_wayback_cdx_rescue:
                stage = f"running {sector} wayback cdx rescue"
                run_wayback_cdx_rescue_for_sector(
                    repo_root,
                    sector,
                    timeout_seconds=timeout_seconds,
                    max_seed_roots_per_institution=max_archive_pages_per_institution,
                    max_snapshots_per_institution=max_archive_pages_per_institution,
                    max_workers=max_workers,
                )
            if run_ai_year_gap_rescue:
                stage = f"running {sector} ai year-gap rescue"
                run_ai_year_gap_rescue_for_sector(
                    repo_root,
                    sector,
                    config_path=None,
                    max_api_cases=max_api_cases,
                    timeout_seconds=timeout_seconds,
                    max_archive_pages_per_institution=max_archive_pages_per_institution,
                    max_workers=max_workers,
                    rerun_existing_cases=True,
                    rematerialize_unitids=set(),
                )

        resolved_api_web_rescue_mode = api_web_rescue_mode
        resolved_api_web_rescue_status = api_web_rescue_status
        resolved_api_web_rescue_reason = api_web_rescue_reason
        if run_ai_year_gap_rescue and clean_text(api_web_rescue_mode).lower() in {"", "not_run"}:
            resolved_api_web_rescue_mode = "live_or_cached_ai_year_gap_rescue"
        if run_ai_year_gap_rescue and clean_text(api_web_rescue_status).lower() in {"", "not_run"}:
            resolved_api_web_rescue_status = "attempted_by_current_production_command"
        if run_ai_year_gap_rescue and not clean_text(api_web_rescue_reason):
            resolved_api_web_rescue_reason = (
                "The current production command ran the configured AI/web year-gap rescue before source-review handoff."
            )
        stage = "building step1 production inputs"
        build_step1_inputs(
            repo_root,
            target_panel=target_panel,
            sectors=sectors,
            namespace=namespace,
            chunk_id=chunk_id,
            release_id=release_id,
            input_dir=input_dir,
            timeout_seconds=timeout_seconds,
            max_source_bytes=1_000_000,
            raw_legacy=raw_legacy,
            include_raw_legacy_candidates=include_raw_legacy_candidates,
            archive_expansion_completed=run_archive_expansion,
            api_web_rescue_mode=resolved_api_web_rescue_mode,
            api_web_rescue_status=resolved_api_web_rescue_status,
            api_web_rescue_reason=resolved_api_web_rescue_reason,
            min_ready_rate=min_ready_rate,
            min_sector_ready_rate=min_sector_ready_rate,
            api_web_rescue_required_for_unresolved=run_ai_year_gap_rescue,
            source_review_row_timeout_seconds=source_review_row_timeout_seconds,
            excluded_unitid_count=len(excluded_unitids),
            excluded_unitids_source=excluded_unitids_source,
        )
        stage = "packaging production chunk"
        result = build_step1_production_chunk(
            repo_root,
            input_dir=input_dir,
            chunk_id=chunk_id,
            release_id=release_id,
            build_release=build_release,
        )
        return ProofToScaleResult(
            namespace=namespace,
            input_dir=input_dir,
            chunk_dir=result.output_dir,
            release_dir=result.release_dir,
            target_rows=result.target_rows,
            target_institutions=int(target_panel["unitid"].nunique()),
            ready_rows=result.ready_rows,
            unresolved_rows=result.unresolved_rows,
            requirements_pass=result.requirements_pass,
            release_pass=result.release_pass,
        )
    except KeyboardInterrupt as exc:
        write_run_stop_report(
            repo_root,
            namespace=namespace,
            input_dir=input_dir,
            stage=stage,
            reason="interrupted by KeyboardInterrupt",
            started_monotonic=started_monotonic,
            target_panel=target_panel,
            exception=exc,
        )
        raise
    except Exception as exc:
        write_run_stop_report(
            repo_root,
            namespace=namespace,
            input_dir=input_dir,
            stage=stage,
            reason=f"{type(exc).__name__}: {exc}",
            started_monotonic=started_monotonic,
            target_panel=target_panel,
            exception=exc,
        )
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--chunk-id", required=True)
    parser.add_argument("--release-id", default=None)
    parser.add_argument(
        "--selection-mode",
        choices=["prior_valid_legacy_reverification", "representative", "high_legacy_coverage"],
        default="prior_valid_legacy_reverification",
    )
    parser.add_argument("--institution-count", type=int, default=32)
    parser.add_argument("--public-institution-count", type=int, default=8)
    parser.add_argument("--private-institution-count", type=int, default=20)
    parser.add_argument("--min-target-rows", type=int, default=300)
    parser.add_argument("--max-target-rows", type=int, default=750)
    parser.add_argument("--timeout-seconds", type=int, default=8)
    parser.add_argument("--max-root-candidates-per-institution", type=int, default=40)
    parser.add_argument("--max-archive-pages-per-institution", type=int, default=12)
    parser.add_argument("--max-workers", type=int, default=6)
    parser.add_argument("--run-inferred-year-rescue", action="store_true")
    parser.add_argument("--run-archive-expansion", action="store_true")
    parser.add_argument("--run-wayback-cdx-rescue", action="store_true")
    parser.add_argument("--run-ai-year-gap-rescue", action="store_true")
    parser.add_argument("--max-api-cases", type=int, default=None)
    parser.add_argument("--include-raw-legacy-candidates", action="store_true")
    parser.add_argument("--min-ready-rate", type=float, default=0.0)
    parser.add_argument("--min-sector-ready-rate", type=float, default=0.0)
    parser.add_argument("--api-web-rescue-mode", default="not_run")
    parser.add_argument("--api-web-rescue-status", default="not_run")
    parser.add_argument("--api-web-rescue-reason", default="")
    parser.add_argument("--build-release", action="store_true")
    parser.add_argument("--source-review-row-timeout-seconds", type=float, default=90.0)
    parser.add_argument(
        "--exclude-unitids-file",
        type=Path,
        default=None,
        help="Optional CSV with a unitid column to exclude already-completed institutions from prior-valid selection.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = repo_root_from_cwd(args.root)
    result = run_proof_to_scale(
        repo_root,
        namespace=args.namespace,
        chunk_id=args.chunk_id,
        release_id=args.release_id,
        selection_mode=args.selection_mode,
        institution_count=args.institution_count,
        public_institution_count=args.public_institution_count,
        private_institution_count=args.private_institution_count,
        min_target_rows=args.min_target_rows,
        max_target_rows=args.max_target_rows,
        timeout_seconds=args.timeout_seconds,
        max_root_candidates_per_institution=args.max_root_candidates_per_institution,
        max_archive_pages_per_institution=args.max_archive_pages_per_institution,
        max_workers=args.max_workers,
        run_inferred_year_rescue=args.run_inferred_year_rescue,
        run_archive_expansion=args.run_archive_expansion,
        run_wayback_cdx_rescue=args.run_wayback_cdx_rescue,
        run_ai_year_gap_rescue=args.run_ai_year_gap_rescue,
        max_api_cases=args.max_api_cases,
        include_raw_legacy_candidates=args.include_raw_legacy_candidates,
        min_ready_rate=args.min_ready_rate,
        min_sector_ready_rate=args.min_sector_ready_rate,
        api_web_rescue_mode=args.api_web_rescue_mode,
        api_web_rescue_status=args.api_web_rescue_status,
        api_web_rescue_reason=args.api_web_rescue_reason,
        build_release=args.build_release,
        source_review_row_timeout_seconds=args.source_review_row_timeout_seconds,
        exclude_unitids_file=args.exclude_unitids_file,
    )
    print(
        "proof_to_scale_result "
        f"namespace={result.namespace} "
        f"target_institutions={result.target_institutions} "
        f"target_rows={result.target_rows} "
        f"ready_rows={result.ready_rows} "
        f"unresolved_rows={result.unresolved_rows} "
        f"requirements_pass={result.requirements_pass} "
        f"release_pass={result.release_pass}"
    )
    print(f"input_dir={result.input_dir}")
    print(f"chunk_dir={result.chunk_dir}")
    if result.release_dir:
        print(f"release_dir={result.release_dir}")
    return 0 if result.requirements_pass and (result.release_pass is not False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
