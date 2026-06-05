"""Trace the reverse-engineered process that produced current strict pilot results."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .ai_config import repo_root_from_cwd


DATA_DIR = Path("../data_policy_pipeline")
INTERIM_DIR = DATA_DIR / "interim"
LOG_DIR = DATA_DIR / "logs"

STRICT_RETRIEVAL_INPUT = INTERIM_DIR / "catalog_retrieval_coverage_strict_pilot.csv"
PANEL_CANDIDATES_INPUT = INTERIM_DIR / "catalog_panel_candidates_strict_pilot.csv"
PANEL_YEAR_STATUS_INPUT = INTERIM_DIR / "catalog_panel_year_status_strict_pilot.csv"
PANEL_RETRIEVAL_INPUT = INTERIM_DIR / "catalog_panel_retrieval_coverage_strict_pilot.csv"
PANEL_RETRIEVED_YEARS_INPUT = INTERIM_DIR / "catalog_panel_year_coverage_retrieved_strict_pilot.csv"

SOURCE_TRACE_OUTPUT = INTERIM_DIR / "catalog_current_process_source_trace_strict_pilot.csv"
YEAR_TRACE_OUTPUT = INTERIM_DIR / "catalog_current_process_year_trace_strict_pilot.csv"
TRACE_SUMMARY_OUTPUT = LOG_DIR / "phase3_current_process_trace_summary.md"


@dataclass(frozen=True)
class CurrentProcessTraceOutputs:
    source_trace: Path
    year_trace: Path
    summary_report: Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_inputs(repo_root: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    return (
        pd.read_csv(repo_root / STRICT_RETRIEVAL_INPUT, low_memory=False),
        pd.read_csv(repo_root / PANEL_CANDIDATES_INPUT, low_memory=False),
        pd.read_csv(repo_root / PANEL_YEAR_STATUS_INPUT, low_memory=False),
        pd.read_csv(repo_root / PANEL_RETRIEVAL_INPUT, low_memory=False),
        pd.read_csv(repo_root / PANEL_RETRIEVED_YEARS_INPUT, low_memory=False),
    )


def clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def actual_source_role(source_id: object, unitid: object, source_status: object = "") -> str:
    source_id_text = clean_text(source_id)
    unitid_text = clean_text(unitid)
    status_text = clean_text(source_status)
    if source_id_text.startswith("strict-"):
        return "legacy_prior_confirmed"
    if source_id_text.startswith("panel-sfsu-"):
        return "preferred_root_archive_fill"
    if source_id_text.startswith("panel-siu-"):
        if status_text == "review_before_retrieval":
            return "preferred_root_review_before_retrieval"
        return "preferred_root_repository_fill"
    if source_id_text.startswith("panel-uncc-"):
        return "fallback_official_gap_fill"
    if source_id_text.startswith("panel-abac-"):
        return "ocr_or_visual_review"
    if source_id_text.startswith("panel-ohsu-") or unitid_text == "209490":
        return "wrong_scope_or_fresh_discovery"
    return "unclassified_current_process"


def actual_year_role(row: pd.Series) -> str:
    if bool(row.get("has_strict_catalog_source", False)):
        return actual_source_role(row.get("source_id", ""), row.get("unitid", ""))
    status = clean_text(row.get("candidate_status", ""))
    if status in {"official_archive_lower_bound_reached", "official_archive_upper_bound_reached"}:
        return "archive_bound_stop"
    if status == "scanned_pdf_needs_ocr_or_visual_review":
        return "ocr_or_visual_review"
    if status == "fresh_discovery_needed":
        return "wrong_scope_or_fresh_discovery"
    if status == "review_before_retrieval":
        return "preferred_root_review_before_retrieval"
    if status == "ready_for_retrieval":
        return "ready_candidate_not_yet_in_combined_trace"
    return "unresolved_first_pass_gap"


def build_source_trace(
    strict_retrieval: pd.DataFrame,
    panel_candidates: pd.DataFrame,
    panel_retrieval: pd.DataFrame,
) -> pd.DataFrame:
    retrieved = pd.concat(
        [
            strict_retrieval.assign(source_trace_origin="legacy_strict_retrieval"),
            panel_retrieval.assign(source_trace_origin="panel_ready_retrieval"),
        ],
        ignore_index=True,
        sort=False,
    )
    retrieved["source_status"] = retrieved.get("source_status", "")
    retrieved["actual_process_role"] = retrieved.apply(
        lambda row: actual_source_role(row.get("source_id", ""), row.get("unitid", ""), row.get("source_status", "")),
        axis=1,
    )

    retrieved_ids = set(retrieved["source_id"].dropna().astype(str))
    candidate_only = panel_candidates[~panel_candidates["source_id"].astype(str).isin(retrieved_ids)].copy()
    candidate_only["source_trace_origin"] = "panel_candidate_not_retrieved"
    candidate_only["target_year"] = candidate_only["catalog_year_start"]
    candidate_only["source_retrieved"] = False
    candidate_only["strict_covers_target_year"] = False
    candidate_only["catalog_year_evidence_type"] = ""
    candidate_only["catalog_year_evidence_text"] = ""
    candidate_only["best_attempt_method"] = ""
    candidate_only["local_source_path"] = ""
    candidate_only["actual_process_role"] = candidate_only.apply(
        lambda row: actual_source_role(row.get("source_id", ""), row.get("unitid", ""), row.get("source_status", "")),
        axis=1,
    )

    combined = pd.concat([retrieved, candidate_only], ignore_index=True, sort=False)
    for col in [
        "source_id",
        "unitid",
        "institution_name",
        "target_year",
        "candidate_url",
        "source_retrieved",
        "strict_covers_target_year",
        "catalog_year_start",
        "catalog_year_end",
        "catalog_year_evidence_type",
        "catalog_year_evidence_text",
        "best_attempt_method",
        "local_source_path",
        "source_status",
        "review_reason",
        "actual_process_role",
        "source_trace_origin",
    ]:
        if col not in combined.columns:
            combined[col] = ""
    combined["created_at"] = utc_now()
    return combined[
        [
            "source_id",
            "unitid",
            "institution_name",
            "target_year",
            "candidate_url",
            "source_retrieved",
            "strict_covers_target_year",
            "catalog_year_start",
            "catalog_year_end",
            "catalog_year_evidence_type",
            "catalog_year_evidence_text",
            "best_attempt_method",
            "local_source_path",
            "source_status",
            "review_reason",
            "actual_process_role",
            "source_trace_origin",
            "created_at",
        ]
    ].sort_values(["unitid", "target_year", "source_id"])


def build_year_trace(panel_year_status: pd.DataFrame, panel_retrieved_years: pd.DataFrame) -> pd.DataFrame:
    status_cols = [
        "unitid",
        "target_year",
        "candidate_status",
        "candidate_source_id",
        "candidate_url",
        "candidate_title",
        "candidate_review_reason",
    ]
    status = panel_year_status.reindex(columns=status_cols).copy()
    years = panel_retrieved_years.merge(status, on=["unitid", "target_year"], how="left", suffixes=("", "_status"))
    if "candidate_url_status" in years.columns:
        years["candidate_url"] = years["candidate_url"].fillna(years["candidate_url_status"])
    years["actual_process_role"] = years.apply(actual_year_role, axis=1)
    years["reverse_engineered_step"] = years["actual_process_role"].map(
        {
            "legacy_prior_confirmed": "legacy_link_retrieved_and_strict_verified",
            "preferred_root_archive_fill": "preferred_source_root_gap_fill",
            "preferred_root_repository_fill": "preferred_source_root_gap_fill",
            "fallback_official_gap_fill": "fallback_official_root_gap_fill",
            "ocr_or_visual_review": "candidate_found_but_ocr_or_visual_review_needed",
            "wrong_scope_or_fresh_discovery": "wrong_scope_or_no_root_found",
            "archive_bound_stop": "first_pass_archive_bound_stop",
            "preferred_root_review_before_retrieval": "candidate_found_but_review_before_retrieval",
        }
    ).fillna("unresolved_first_pass_gap")
    years["created_at"] = utc_now()
    for col in [
        "strict_pilot_rank",
        "unitid",
        "institution_name",
        "target_year",
        "has_strict_catalog_source",
        "source_id",
        "candidate_status",
        "candidate_source_id",
        "candidate_title",
        "candidate_url",
        "actual_process_role",
        "reverse_engineered_step",
        "review_reason",
        "candidate_review_reason",
        "created_at",
    ]:
        if col not in years.columns:
            years[col] = ""
    return years[
        [
            "strict_pilot_rank",
            "unitid",
            "institution_name",
            "target_year",
            "has_strict_catalog_source",
            "source_id",
            "candidate_status",
            "candidate_source_id",
            "candidate_title",
            "candidate_url",
            "actual_process_role",
            "reverse_engineered_step",
            "review_reason",
            "candidate_review_reason",
            "created_at",
        ]
    ].sort_values(["strict_pilot_rank", "unitid", "target_year"])


def write_summary(path: Path, source_trace: pd.DataFrame, year_trace: pd.DataFrame) -> None:
    lines = [
        "# Phase 3 Current Process Trace",
        "",
        f"Generated at: {utc_now()}",
        "",
        "Purpose: reverse engineer the process that produced the current strict-pilot outputs, so current results can be replicated and audited without hiding the ad hoc discovery path.",
        "",
        "## Source-Level Roles",
        "",
    ]
    for role, count in source_trace["actual_process_role"].value_counts(dropna=False).items():
        lines.append(f"- {role}: {count}")
    lines.extend(["", "## Institution-Year Roles", ""])
    for role, count in year_trace["actual_process_role"].value_counts(dropna=False).items():
        lines.append(f"- {role}: {count}")
    lines.extend(["", "## Reverse-Engineered Steps", ""])
    for step, count in year_trace["reverse_engineered_step"].value_counts(dropna=False).items():
        lines.append(f"- {step}: {count}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_current_process_trace(repo_root: Path) -> CurrentProcessTraceOutputs:
    repo_root = repo_root.resolve()
    strict_retrieval, panel_candidates, panel_year_status, panel_retrieval, panel_retrieved_years = read_inputs(repo_root)
    source_trace = build_source_trace(strict_retrieval, panel_candidates, panel_retrieval)
    year_trace = build_year_trace(panel_year_status, panel_retrieved_years)

    outputs = CurrentProcessTraceOutputs(
        source_trace=(repo_root / SOURCE_TRACE_OUTPUT).resolve(),
        year_trace=(repo_root / YEAR_TRACE_OUTPUT).resolve(),
        summary_report=(repo_root / TRACE_SUMMARY_OUTPUT).resolve(),
    )
    for output_path in outputs.__dict__.values():
        output_path.parent.mkdir(parents=True, exist_ok=True)
    source_trace.to_csv(outputs.source_trace, index=False)
    year_trace.to_csv(outputs.year_trace, index=False)
    write_summary(outputs.summary_report, source_trace, year_trace)
    return outputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Trace current strict-pilot catalog discovery process.")
    parser.add_argument("--root", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve() if args.root else repo_root_from_cwd()
    outputs = run_current_process_trace(root)
    for label, output_path in outputs.__dict__.items():
        print(f"{label}: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
