"""Build a one-row-per-institution Phase 3 strict-pilot status summary."""

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

STRICT_INSTITUTIONS_INPUT = INTERIM_DIR / "catalog_pilot_institutions_strict.csv"
PANEL_YEAR_COVERAGE_INPUT = INTERIM_DIR / "catalog_panel_year_coverage_retrieved_strict_pilot.csv"
PANEL_YEAR_STATUS_INPUT = INTERIM_DIR / "catalog_panel_year_status_strict_pilot.csv"
SOURCE_ROOT_PLAN_INPUT = INTERIM_DIR / "catalog_source_root_plan_strict_pilot.csv"
ESCALATION_QUEUE_INPUT = INTERIM_DIR / "catalog_first_pass_escalation_queue_strict_pilot.csv"

PILOT_STATUS_SUMMARY_OUTPUT = INTERIM_DIR / "catalog_pilot_status_summary_strict_pilot.csv"
PILOT_STATUS_SUMMARY_REPORT_OUTPUT = LOG_DIR / "phase3_pilot_status_summary.md"

SUMMARY_COLUMNS = [
    "strict_pilot_rank",
    "unitid",
    "institution_name",
    "state",
    "overall_status",
    "institution_years",
    "strict_covered_years",
    "unresolved_years",
    "coverage_rate",
    "first_unresolved_year",
    "last_unresolved_year",
    "unresolved_statuses",
    "escalation_bucket",
    "primary_source_root_name",
    "primary_source_root_role",
    "primary_source_root_decision",
    "recommended_next_step",
    "notes",
    "created_at",
]


@dataclass(frozen=True)
class PilotStatusSummaryOutputs:
    status_summary: Path
    summary_report: Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_inputs(repo_root: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    return (
        pd.read_csv(repo_root / STRICT_INSTITUTIONS_INPUT, low_memory=False),
        pd.read_csv(repo_root / PANEL_YEAR_COVERAGE_INPUT, low_memory=False),
        pd.read_csv(repo_root / PANEL_YEAR_STATUS_INPUT, low_memory=False),
        pd.read_csv(repo_root / SOURCE_ROOT_PLAN_INPUT, low_memory=False),
        pd.read_csv(repo_root / ESCALATION_QUEUE_INPUT, low_memory=False),
    )


def bool_series(values: pd.Series) -> pd.Series:
    if values.dtype == bool:
        return values.fillna(False)
    return values.fillna(False).astype(str).str.lower().isin({"true", "1", "yes"})


def count_join(values: pd.Series) -> str:
    cleaned = values.fillna("").astype(str).str.strip()
    cleaned = cleaned[cleaned.ne("")]
    if cleaned.empty:
        return ""
    counts = cleaned.value_counts().sort_index()
    return "; ".join(f"{key}={value}" for key, value in counts.items())


def primary_root_for_unit(source_root_plan: pd.DataFrame, unitid: int) -> pd.Series | None:
    roots = source_root_plan.loc[source_root_plan["unitid"].eq(unitid)].copy()
    if roots.empty:
        return None
    roots["fallback_order_sort"] = pd.to_numeric(roots["fallback_order"], errors="coerce").fillna(999)
    return roots.sort_values(["fallback_order_sort", "source_root_role", "source_root_name"]).iloc[0]


def source_root_for_escalation(source_root_plan: pd.DataFrame, unitid: int, source_root_name: str) -> pd.Series | None:
    if not source_root_name:
        return None
    roots = source_root_plan.loc[
        source_root_plan["unitid"].eq(unitid)
        & source_root_plan["source_root_name"].fillna("").astype(str).eq(source_root_name)
    ]
    if roots.empty:
        return None
    return roots.iloc[0]


def escalation_for_unit(escalation_queue: pd.DataFrame, unitid: int) -> pd.Series | None:
    rows = escalation_queue.loc[escalation_queue["unitid"].eq(unitid)].copy()
    if rows.empty:
        return None
    return rows.sort_values(["strict_pilot_rank", "escalation_bucket", "source_root_name"]).iloc[0]


def derived_bucket(unresolved_statuses: str) -> str:
    if "official_archive_" in unresolved_statuses:
        return "archive_bound_revisit"
    if "review_before_retrieval" in unresolved_statuses:
        return "review_before_retrieval"
    return ""


def derived_next_step(bucket: str) -> str:
    steps = {
        "archive_bound_revisit": "Leave archive-bound years as first-pass stops unless this institution is revisited for deeper search.",
        "review_before_retrieval": "Review the ambiguous candidate before retrieval; otherwise leave it as a first-pass stop.",
    }
    return steps.get(bucket, "")


def overall_status(covered: int, total: int, escalation_bucket: str) -> str:
    if total and covered == total:
        return "complete_strict_catalog_coverage"
    if escalation_bucket:
        return escalation_bucket
    if covered:
        return "partial_coverage_no_escalation_bucket"
    return "no_strict_coverage_no_escalation_bucket"


def build_status_summary(
    institutions: pd.DataFrame,
    year_coverage: pd.DataFrame,
    year_status: pd.DataFrame,
    source_root_plan: pd.DataFrame,
    escalation_queue: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    year_coverage = year_coverage.copy()
    year_coverage["has_strict_catalog_source"] = bool_series(year_coverage["has_strict_catalog_source"])

    for _, inst in institutions.sort_values(["strict_pilot_rank", "unitid"]).iterrows():
        unitid = int(inst["unitid"])
        years = year_coverage.loc[year_coverage["unitid"].eq(unitid)].copy()
        statuses = year_status.loc[year_status["unitid"].eq(unitid)].copy()
        unresolved = years.loc[~years["has_strict_catalog_source"]].copy()
        covered = int(years["has_strict_catalog_source"].sum())
        total = int(len(years))
        escalation = escalation_for_unit(escalation_queue, unitid)
        root = primary_root_for_unit(source_root_plan, unitid)
        escalation_bucket = "" if escalation is None else str(escalation["escalation_bucket"])
        unresolved_statuses = statuses.loc[statuses["target_year"].isin(unresolved["target_year"])]
        unresolved_status_text = count_join(unresolved_statuses.get("candidate_status", pd.Series(dtype=str)))
        if not escalation_bucket:
            escalation_bucket = derived_bucket(unresolved_status_text)
        escalation_source_name = "" if escalation is None else str(escalation["source_root_name"])
        escalation_root = source_root_for_escalation(source_root_plan, unitid, escalation_source_name)
        if escalation_root is not None:
            root = escalation_root

        rows.append(
            {
                "strict_pilot_rank": int(inst["strict_pilot_rank"]),
                "unitid": unitid,
                "institution_name": inst["institution_name"],
                "state": inst["state"],
                "overall_status": overall_status(covered, total, escalation_bucket),
                "institution_years": total,
                "strict_covered_years": covered,
                "unresolved_years": total - covered,
                "coverage_rate": round(covered / total, 3) if total else 0,
                "first_unresolved_year": int(unresolved["target_year"].min()) if not unresolved.empty else "",
                "last_unresolved_year": int(unresolved["target_year"].max()) if not unresolved.empty else "",
                "unresolved_statuses": unresolved_status_text,
                "escalation_bucket": escalation_bucket,
                "primary_source_root_name": "" if root is None else root["source_root_name"],
                "primary_source_root_role": "" if root is None else root["source_root_role"],
                "primary_source_root_decision": "" if root is None else root["first_pass_decision"],
                "recommended_next_step": derived_next_step(escalation_bucket)
                if escalation is None
                else escalation["recommended_next_step"],
                "notes": "" if root is None else root["notes"],
                "created_at": utc_now(),
            }
        )
    return pd.DataFrame(rows, columns=SUMMARY_COLUMNS)


def write_summary_report(path: Path, summary: pd.DataFrame) -> None:
    lines = [
        "# Phase 3 Strict Pilot Status Summary",
        "",
        f"Generated at: {utc_now()}",
        "",
        "Purpose: one-row-per-institution dashboard for the strict Phase 3 catalog pilot.",
        "",
        "## Overall Status Counts",
        "",
    ]
    for status, count in summary["overall_status"].value_counts(dropna=False).items():
        lines.append(f"- {status}: {count}")
    lines.extend(["", "## Institution Actions", ""])
    for _, row in summary.sort_values(["strict_pilot_rank", "unitid"]).iterrows():
        lines.append(
            f"- {row['institution_name']}: {row['strict_covered_years']}/{row['institution_years']} "
            f"years covered; status={row['overall_status']}; next={row['recommended_next_step'] or 'none'}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_pilot_status_summary(repo_root: Path) -> PilotStatusSummaryOutputs:
    repo_root = repo_root.resolve()
    institutions, year_coverage, year_status, source_root_plan, escalation_queue = read_inputs(repo_root)
    summary = build_status_summary(institutions, year_coverage, year_status, source_root_plan, escalation_queue)
    outputs = PilotStatusSummaryOutputs(
        status_summary=(repo_root / PILOT_STATUS_SUMMARY_OUTPUT).resolve(),
        summary_report=(repo_root / PILOT_STATUS_SUMMARY_REPORT_OUTPUT).resolve(),
    )
    for output_path in outputs.__dict__.values():
        output_path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(outputs.status_summary, index=False)
    write_summary_report(outputs.summary_report, summary)
    return outputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build strict Phase 3 pilot status summary.")
    parser.add_argument("--root", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve() if args.root else repo_root_from_cwd()
    outputs = run_pilot_status_summary(root)
    for label, output_path in outputs.__dict__.items():
        print(f"{label}: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
