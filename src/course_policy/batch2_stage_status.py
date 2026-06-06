"""Normalize batch-2 institution-years to the Phase 3 stage ladder."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .ai_config import repo_root_from_cwd
from .batch2_runthrough import BATCH2_RETRIEVAL_COVERAGE_OUTPUT, BATCH2_RUNTHROUGH_YEAR_SUMMARY_OUTPUT
from .batch2_secondary_archive import (
    BATCH2_SECONDARY_ARCHIVE_CANDIDATES_OUTPUT,
    BATCH2_SECONDARY_ARCHIVE_YEAR_SUMMARY_OUTPUT,
)
from .batch2_year_candidates import BATCH2_YEAR_COVERAGE_OUTPUT


DATA_DIR = Path("../data_policy_pipeline")
INTERIM_DIR = DATA_DIR / "interim"
LOG_DIR = DATA_DIR / "logs"

BATCH2_STAGE_STATUS_OUTPUT = INTERIM_DIR / "catalog_batch2_stage_status.csv"
BATCH2_STAGE_STATUS_SUMMARY_OUTPUT = LOG_DIR / "phase3_batch2_stage_status_summary.md"

ARCHIVE_BOUND_START_YEARS = {
    139940: 2003,  # Georgia State bachelor-level undergraduate archive observed from AY 2003.
    220075: 2010,  # ETSU official undergraduate archive observed from AY 2010.
}


@dataclass(frozen=True)
class Batch2StageStatusOutputs:
    stage_status: Path
    summary_report: Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_inputs(repo_root: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    return (
        pd.read_csv(repo_root / BATCH2_RUNTHROUGH_YEAR_SUMMARY_OUTPUT, low_memory=False),
        pd.read_csv(repo_root / BATCH2_RETRIEVAL_COVERAGE_OUTPUT, low_memory=False),
        pd.read_csv(repo_root / BATCH2_SECONDARY_ARCHIVE_CANDIDATES_OUTPUT, low_memory=False),
        pd.read_csv(repo_root / BATCH2_SECONDARY_ARCHIVE_YEAR_SUMMARY_OUTPUT, low_memory=False),
        pd.read_csv(repo_root / BATCH2_YEAR_COVERAGE_OUTPUT, low_memory=False),
    )


def clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def best_retrieval_rows(retrieval: pd.DataFrame) -> pd.DataFrame:
    if retrieval.empty:
        return pd.DataFrame()
    method_rank = {"preferred_root_archive": 1, "legacy_gap_fill_outside_root_span": 2}
    out = retrieval.copy()
    out["method_rank"] = out["candidate_source_method"].map(method_rank).fillna(9)
    return (
        out.sort_values(["unitid", "target_year", "method_rank", "source_id"])
        .groupby(["unitid", "target_year"], as_index=False)
        .first()
    )


def secondary_rows(candidates: pd.DataFrame) -> pd.DataFrame:
    if candidates.empty:
        return pd.DataFrame()
    return (
        candidates.sort_values(["unitid", "target_year", "candidate_url"])
        .groupby(["unitid", "target_year"], as_index=False)
        .first()
    )


def stage_for_row(row: pd.Series) -> tuple[str, str, str, bool, str]:
    if bool(row.get("has_preferred_root_retrieved", False)):
        return (
            "source_retrieved",
            "policy_terms_not_searched",
            "policy_term_search",
            False,
            "Catalog source body was retrieved and saved; policy-term search has not run yet.",
        )
    if bool(row.get("has_secondary_archive_candidate", False)):
        return (
            "candidate_identified",
            "body_access_blocked",
            "retrieval_recovery",
            False,
            "Secondary institutional archive metadata confirms a catalog-year candidate, but catalog body retrieval is blocked/challenge-protected.",
        )
    if bool(row.get("has_legacy_gap_retrieved", False)):
        return (
            "source_retrieved",
            "policy_terms_not_searched",
            "policy_term_search",
            False,
            "Legacy gap-fill catalog source body was retrieved and saved; policy-term search has not run yet.",
        )
    unitid = int(row["unitid"])
    target_year = int(row["target_year"])
    if unitid in ARCHIVE_BOUND_START_YEARS and target_year < ARCHIVE_BOUND_START_YEARS[unitid]:
        return (
            "root_identified",
            "archive_bound",
            "defer_archive_bound",
            False,
            f"Preferred official archive/root is observed to start at AY {ARCHIVE_BOUND_START_YEARS[unitid]}; earlier year deferred for this batch.",
        )
    return (
        "root_identified",
        "no_candidate_found",
        "source_root_discovery",
        False,
        "Preferred root was identified, but no year-level catalog candidate has been found for this institution-year.",
    )


def build_stage_status(
    run_summary: pd.DataFrame,
    retrieval: pd.DataFrame,
    secondary_candidates: pd.DataFrame,
    secondary_summary: pd.DataFrame,
    year_coverage: pd.DataFrame,
) -> pd.DataFrame:
    best_retrieval = best_retrieval_rows(retrieval)
    sec = secondary_rows(secondary_candidates)
    rows = run_summary.copy()
    rows = rows.merge(
        year_coverage[
            [
                "unitid",
                "target_year",
                "candidate_url",
                "candidate_link_text",
                "archive_url",
                "catalog_year_start",
                "catalog_year_end",
            ]
        ].rename(
            columns={
                "candidate_url": "root_candidate_url",
                "candidate_link_text": "root_candidate_title",
                "archive_url": "root_archive_url",
                "catalog_year_start": "root_catalog_year_start",
                "catalog_year_end": "root_catalog_year_end",
            }
        ),
        on=["unitid", "target_year"],
        how="left",
    )
    if not best_retrieval.empty:
        rows = rows.merge(
            best_retrieval[
                [
                    "unitid",
                    "target_year",
                    "source_id",
                    "candidate_url",
                    "candidate_source_method",
                    "source_retrieved",
                    "best_retrieval_status",
                    "best_attempt_method",
                    "best_content_type",
                    "local_source_path",
                    "covers_target_year",
                ]
            ].rename(
                columns={
                    "source_id": "retrieved_source_id",
                    "candidate_url": "retrieved_candidate_url",
                    "candidate_source_method": "retrieved_candidate_method",
                    "source_retrieved": "has_retrieved_source",
                    "best_retrieval_status": "retrieval_status",
                    "best_attempt_method": "retrieval_method",
                    "best_content_type": "retrieved_content_type",
                }
            ),
            on=["unitid", "target_year"],
            how="left",
        )
    else:
        rows["has_retrieved_source"] = False
        rows["retrieved_candidate_method"] = ""
        rows["retrieved_source_id"] = ""
        rows["retrieved_candidate_url"] = ""
        rows["retrieval_status"] = ""
        rows["retrieval_method"] = ""
        rows["retrieved_content_type"] = ""
        rows["local_source_path"] = ""
    if not sec.empty:
        rows = rows.merge(
            sec[
                [
                    "unitid",
                    "target_year",
                    "candidate_url",
                    "candidate_title",
                    "secondary_source_root_name",
                    "secondary_source_set_spec",
                    "catalog_body_access_status",
                    "catalog_body_retrieval_status",
                    "catalog_body_content_type",
                ]
            ].rename(
                columns={
                    "candidate_url": "secondary_candidate_url",
                    "candidate_title": "secondary_candidate_title",
                }
            ),
            on=["unitid", "target_year"],
            how="left",
        )
    if not secondary_summary.empty:
        rows = rows.merge(
            secondary_summary[["unitid", "target_year", "has_secondary_archive_candidate"]],
            on=["unitid", "target_year"],
            how="left",
        )
    rows["has_retrieved_source"] = rows["has_retrieved_source"].where(rows["has_retrieved_source"].notna(), False).map(bool)
    rows["has_preferred_root_retrieved"] = rows["has_retrieved_source"] & rows["retrieved_candidate_method"].fillna("").eq(
        "preferred_root_archive"
    )
    rows["has_legacy_gap_retrieved"] = rows["has_retrieved_source"] & rows["retrieved_candidate_method"].fillna("").eq(
        "legacy_gap_fill_outside_root_span"
    )
    rows["has_secondary_archive_candidate"] = (
        rows["has_secondary_archive_candidate"].where(rows["has_secondary_archive_candidate"].notna(), False).map(bool)
    )

    stage_rows = []
    for _, row in rows.iterrows():
        stage, stop_reason, next_action, human_decision_needed, explanation = stage_for_row(row)
        stage_rows.append(
            {
                "batch2_rank": int(row["batch2_rank"]),
                "unitid": int(row["unitid"]),
                "institution_name": row["institution_name"],
                "target_year": int(row["target_year"]),
                "pipeline_stage": stage,
                "stop_reason": stop_reason,
                "next_batch_action": next_action,
                "human_decision_needed": human_decision_needed,
                "stage_explanation": explanation,
                "has_preferred_root_candidate": bool(row["has_root_archive_candidate"]),
                "has_preferred_root_retrieved": bool(row["has_preferred_root_retrieved"]),
                "has_legacy_gap_fill_candidate": bool(row["has_legacy_gap_fill_candidate"]),
                "has_legacy_gap_retrieved": bool(row["has_legacy_gap_retrieved"]),
                "has_secondary_archive_candidate": bool(row["has_secondary_archive_candidate"]),
                "root_candidate_url": clean_text(row.get("root_candidate_url", "")),
                "root_candidate_title": clean_text(row.get("root_candidate_title", "")),
                "root_archive_url": clean_text(row.get("root_archive_url", "")),
                "retrieved_source_id": clean_text(row.get("retrieved_source_id", "")),
                "retrieved_candidate_url": clean_text(row.get("retrieved_candidate_url", "")),
                "retrieved_candidate_method": clean_text(row.get("retrieved_candidate_method", "")),
                "retrieval_status": clean_text(row.get("retrieval_status", "")),
                "retrieval_method": clean_text(row.get("retrieval_method", "")),
                "retrieved_content_type": clean_text(row.get("retrieved_content_type", "")),
                "local_source_path": clean_text(row.get("local_source_path", "")),
                "secondary_candidate_url": clean_text(row.get("secondary_candidate_url", "")),
                "secondary_candidate_title": clean_text(row.get("secondary_candidate_title", "")),
                "secondary_source_root_name": clean_text(row.get("secondary_source_root_name", "")),
                "secondary_source_set_spec": clean_text(row.get("secondary_source_set_spec", "")),
                "secondary_body_access_status": clean_text(row.get("catalog_body_access_status", "")),
                "created_at": utc_now(),
            }
        )
    return pd.DataFrame(stage_rows).sort_values(["batch2_rank", "unitid", "target_year"])


def write_summary(path: Path, stage_status: pd.DataFrame) -> None:
    lines = [
        "# Phase 3 Batch 2 Stage Status",
        "",
        f"Generated at: {utc_now()}",
        "",
        "Scope: normalize batch-2 institution-years to `pipeline_stage`, `stop_reason`, and `next_batch_action`.",
        "",
        "## Pipeline Stages",
        "",
    ]
    for stage, count in stage_status["pipeline_stage"].value_counts().items():
        lines.append(f"- {stage}: {count}")
    lines.extend(["", "## Stop Reasons", ""])
    for reason, count in stage_status["stop_reason"].value_counts().items():
        lines.append(f"- {reason}: {count}")
    lines.extend(["", "## Next Batch Actions", ""])
    for action, count in stage_status["next_batch_action"].value_counts().items():
        lines.append(f"- {action}: {count}")
    lines.extend(["", "## Institutions", ""])
    for (unitid, name), group in stage_status.groupby(["unitid", "institution_name"], dropna=False):
        action_counts = ", ".join(f"{action}={count}" for action, count in group["next_batch_action"].value_counts().items())
        lines.append(f"- {name} ({int(unitid)}): {action_counts}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_batch2_stage_status(repo_root: Path) -> Batch2StageStatusOutputs:
    repo_root = repo_root.resolve()
    stage_status = build_stage_status(*read_inputs(repo_root))
    outputs = Batch2StageStatusOutputs(
        stage_status=(repo_root / BATCH2_STAGE_STATUS_OUTPUT).resolve(),
        summary_report=(repo_root / BATCH2_STAGE_STATUS_SUMMARY_OUTPUT).resolve(),
    )
    for output_path in outputs.__dict__.values():
        output_path.parent.mkdir(parents=True, exist_ok=True)
    stage_status.to_csv(outputs.stage_status, index=False)
    write_summary(outputs.summary_report, stage_status)
    return outputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build batch-2 Phase 3 stage-ladder status table.")
    parser.add_argument("--root", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve() if args.root else repo_root_from_cwd()
    outputs = run_batch2_stage_status(root)
    for label, output_path in outputs.__dict__.items():
        print(f"{label}: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
