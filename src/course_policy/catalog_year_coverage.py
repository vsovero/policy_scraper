"""Build institution-year catalog source coverage for the Phase 3 public pilot."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .ai_config import repo_root_from_cwd
from .institution_universe import TARGET_END_YEAR, TARGET_START_YEAR


DATA_DIR = Path("../data_policy_pipeline")
INTERIM_DIR = DATA_DIR / "interim"
LOG_DIR = DATA_DIR / "logs"

PILOT_INSTITUTIONS_INPUT = INTERIM_DIR / "catalog_pilot_institutions.csv"
INSTITUTION_YEAR_TARGETS_INPUT = INTERIM_DIR / "institution_year_targets.csv"
RETRIEVAL_COVERAGE_INPUT = INTERIM_DIR / "catalog_retrieval_coverage_pilot.csv"
YEAR_COVERAGE_OUTPUT = INTERIM_DIR / "catalog_year_coverage_pilot.csv"
SUMMARY_OUTPUT = LOG_DIR / "phase3_catalog_year_coverage_pilot_summary.md"


@dataclass(frozen=True)
class YearCoverageOutputs:
    year_coverage: Path
    summary_report: Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def to_bool(series: pd.Series) -> pd.Series:
    return series.astype("string").fillna("").str.strip().str.lower().isin({"true", "1", "yes"})


def source_priority(row: pd.Series) -> tuple[int, int, str]:
    method_rank = {
        "direct": 1,
        "wayback_snapshot": 2,
        "wayback_cdx_snapshot": 3,
        "parent_link": 4,
    }.get(clean_text(row.get("best_attempt_method", "")), 9)
    review_rank = 1 if bool(row.get("needs_human_review", False)) else 0
    return method_rank, review_rank, clean_text(row.get("source_id", ""))


def expand_sources_to_years(retrieval_coverage: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    retrieved = retrieval_coverage[to_bool(retrieval_coverage["source_retrieved"])].copy()
    for _, source in retrieved.iterrows():
        start = pd.to_numeric(source.get("best_catalog_year_start", ""), errors="coerce")
        end = pd.to_numeric(source.get("best_catalog_year_end", ""), errors="coerce")
        if pd.isna(start) or pd.isna(end):
            continue
        start = int(start)
        end = int(end)
        if end <= start:
            continue
        for year in range(max(start, TARGET_START_YEAR), min(end, TARGET_END_YEAR + 1)):
            rows.append(
                {
                    "unitid": int(source["unitid"]),
                    "target_year": year,
                    "source_id": source["source_id"],
                    "candidate_url": source["candidate_url"],
                    "source_status": "source_covers_year",
                    "catalog_year_start": start,
                    "catalog_year_end": end,
                    "retrieval_status": source["best_retrieval_status"],
                    "retrieval_method": source["best_attempt_method"],
                    "final_url": source["best_final_url"],
                    "content_type": source["best_content_type"],
                    "page_title": source["best_page_title"],
                    "local_source_path": source["local_source_path"],
                    "sha256": source["sha256"],
                    "needs_human_review": bool(source.get("needs_human_review", False)),
                    "review_reason": clean_text(source.get("review_reason", "")),
                    "legacy_workbook": source.get("legacy_workbook", ""),
                    "legacy_sheet_name": source.get("legacy_sheet_name", ""),
                    "legacy_excel_row": source.get("legacy_excel_row", ""),
                    "legacy_link_id": source.get("legacy_link_id", ""),
                }
            )
    return pd.DataFrame(rows)


def select_best_source(expanded: pd.DataFrame) -> pd.DataFrame:
    if expanded.empty:
        return pd.DataFrame(
            columns=[
                "unitid",
                "target_year",
                "source_id",
                "candidate_url",
                "source_status",
                "catalog_year_start",
                "catalog_year_end",
                "retrieval_status",
                "retrieval_method",
                "final_url",
                "content_type",
                "page_title",
                "local_source_path",
                "sha256",
                "needs_human_review",
                "review_reason",
                "legacy_workbook",
                "legacy_sheet_name",
                "legacy_excel_row",
                "legacy_link_id",
            ]
        )
    ranked = expanded.copy()
    ranked[["method_rank", "review_rank", "source_sort"]] = ranked.apply(
        lambda row: pd.Series(source_priority(row)), axis=1
    )
    return (
        ranked.sort_values(["unitid", "target_year", "method_rank", "review_rank", "source_sort"])
        .groupby(["unitid", "target_year"], as_index=False)
        .first()
        .drop(columns=["method_rank", "review_rank", "source_sort"])
    )


def build_year_coverage(
    pilot_institutions: pd.DataFrame,
    targets: pd.DataFrame,
    retrieval_coverage: pd.DataFrame,
) -> pd.DataFrame:
    pilot_unitids = set(pilot_institutions["unitid"].dropna().astype(int))
    panel = targets[targets["unitid"].isin(pilot_unitids)].copy()
    panel = panel.rename(columns={"year": "target_year"})
    panel = panel[
        [
            "unitid",
            "institution_name",
            "sector",
            "control",
            "state",
            "target_year",
            "prior_evidence_status",
            "source_discovery_priority",
        ]
    ]
    expanded = expand_sources_to_years(retrieval_coverage)
    best = select_best_source(expanded)
    out = panel.merge(best, on=["unitid", "target_year"], how="left")
    out["source_status"] = out["source_status"].fillna("missing_source_for_year")
    out["has_catalog_source"] = out["source_status"].eq("source_covers_year")
    out["needs_human_review"] = to_bool(out["needs_human_review"])
    out.loc[~out["has_catalog_source"], "needs_human_review"] = True
    out["review_reason"] = out["review_reason"].fillna("")
    out.loc[~out["has_catalog_source"], "review_reason"] = "No retrieved catalog source currently covers this academic year."

    for col in [
        "source_id",
        "candidate_url",
        "catalog_year_start",
        "catalog_year_end",
        "retrieval_status",
        "retrieval_method",
        "final_url",
        "content_type",
        "page_title",
        "local_source_path",
        "sha256",
        "legacy_workbook",
        "legacy_sheet_name",
        "legacy_excel_row",
        "legacy_link_id",
    ]:
        if col in out.columns:
            out[col] = out[col].fillna("")
    return out.sort_values(["unitid", "target_year"])


def write_summary(summary_path: Path, coverage: pd.DataFrame) -> None:
    total = len(coverage)
    covered = int(coverage["has_catalog_source"].sum())
    lines = [
        "# Phase 3 Pilot Institution-Year Catalog Coverage",
        "",
        f"Generated at: {utc_now()}",
        "",
        "## Scope",
        "",
        f"- Institution-year rows: {total}",
        f"- Institutions: {coverage['unitid'].nunique()}",
        f"- Target years: {coverage['target_year'].min()}-{coverage['target_year'].max()}",
        "",
        "## Coverage",
        "",
        f"- Institution-years with retrieved catalog source coverage: {covered}",
        f"- Institution-years missing retrieved source coverage: {total - covered}",
        f"- Coverage rate: {covered / total:.1%}" if total else "- Coverage rate: n/a",
        "",
        "## Source Status",
        "",
    ]
    for status, count in coverage["source_status"].value_counts(dropna=False).items():
        lines.append(f"- {status}: {count}")
    lines.extend(["", "## Coverage By Institution", ""])
    inst = (
        coverage.groupby(["unitid", "institution_name"], dropna=False)
        .agg(covered_years=("has_catalog_source", "sum"), total_years=("target_year", "size"))
        .reset_index()
        .sort_values(["covered_years", "institution_name"], ascending=[False, True])
    )
    for _, row in inst.iterrows():
        lines.append(f"- {row['institution_name']} ({int(row['unitid'])}): {int(row['covered_years'])}/{int(row['total_years'])}")
    lines.extend(
        [
            "",
            "## Output",
            "",
            f"- Year coverage table: `{(summary_path.parents[1] / 'interim' / YEAR_COVERAGE_OUTPUT.name).resolve()}`",
            "",
        ]
    )
    summary_path.write_text("\n".join(lines), encoding="utf-8")


def run_phase3_year_coverage(repo_root: Path) -> YearCoverageOutputs:
    repo_root = repo_root.resolve()
    pilot = pd.read_csv(repo_root / PILOT_INSTITUTIONS_INPUT, low_memory=False)
    targets = pd.read_csv(repo_root / INSTITUTION_YEAR_TARGETS_INPUT, low_memory=False)
    retrieval = pd.read_csv(repo_root / RETRIEVAL_COVERAGE_INPUT, low_memory=False)
    coverage = build_year_coverage(pilot, targets, retrieval)

    output_path = (repo_root / YEAR_COVERAGE_OUTPUT).resolve()
    summary_path = (repo_root / SUMMARY_OUTPUT).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    coverage.to_csv(output_path, index=False)
    write_summary(summary_path, coverage)
    return YearCoverageOutputs(year_coverage=output_path, summary_report=summary_path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build full institution-year source coverage for the Phase 3 pilot.")
    parser.add_argument("--root", type=Path, default=None, help="Repository root. Defaults to auto-detection.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve() if args.root else repo_root_from_cwd()
    outputs = run_phase3_year_coverage(root)
    for label, path in outputs.__dict__.items():
        print(f"{label}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
