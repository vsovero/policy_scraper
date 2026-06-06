"""Run the batch-2 catalog-source pilot through legacy gap-fill and retrieval."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .ai_config import repo_root_from_cwd
from .batch2_pilot import BATCH2_LEGACY_LEADS_OUTPUT
from .batch2_year_candidates import BATCH2_YEAR_CANDIDATES_OUTPUT, BATCH2_YEAR_COVERAGE_OUTPUT
from .catalog_retrieval import DEFAULT_TIMEOUT_SECONDS, build_coverage, build_retrieval_attempts


DATA_DIR = Path("../data_policy_pipeline")
INTERIM_DIR = DATA_DIR / "interim"
LOG_DIR = DATA_DIR / "logs"

BATCH2_COMBINED_INVENTORY_OUTPUT = INTERIM_DIR / "catalog_batch2_combined_inventory.csv"
BATCH2_RETRIEVAL_ATTEMPTS_OUTPUT = INTERIM_DIR / "catalog_batch2_retrieval_attempts.csv"
BATCH2_RETRIEVAL_COVERAGE_OUTPUT = INTERIM_DIR / "catalog_batch2_retrieval_coverage.csv"
BATCH2_RUNTHROUGH_YEAR_SUMMARY_OUTPUT = INTERIM_DIR / "catalog_batch2_runthrough_year_summary.csv"
BATCH2_RUNTHROUGH_SUMMARY_OUTPUT = LOG_DIR / "phase3_batch2_runthrough_summary.md"


@dataclass(frozen=True)
class Batch2RunthroughOutputs:
    combined_inventory: Path
    retrieval_attempts: Path
    retrieval_coverage: Path
    year_summary: Path
    summary_report: Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_inputs(repo_root: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    return (
        pd.read_csv(repo_root / BATCH2_YEAR_CANDIDATES_OUTPUT, low_memory=False),
        pd.read_csv(repo_root / BATCH2_YEAR_COVERAGE_OUTPUT, low_memory=False),
        pd.read_csv(repo_root / BATCH2_LEGACY_LEADS_OUTPUT, low_memory=False),
    )


def clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def build_root_inventory(year_candidates: pd.DataFrame) -> pd.DataFrame:
    year_candidates = (
        year_candidates.sort_values(["batch2_rank", "unitid", "target_year", "candidate_priority", "candidate_url"])
        .groupby(["unitid", "target_year"], as_index=False)
        .first()
    )
    rows = []
    for _, row in year_candidates.iterrows():
        rows.append(
            {
                "source_id": f"batch2-root-{int(row['unitid'])}-{int(row['target_year'])}",
                "pilot_rank": int(row["batch2_rank"]),
                "unitid": int(row["unitid"]),
                "institution_name": row["institution_name"],
                "target_year": int(row["target_year"]),
                "candidate_url": row["candidate_url"],
                "source_title": row["candidate_link_text"],
                "catalog_year_start": int(row["catalog_year_start"]),
                "catalog_year_end": int(row["catalog_year_end"]),
                "candidate_source_method": "preferred_root_archive",
                "archive_url": row["archive_url"],
                "needs_human_review": False,
                "review_reason": "",
                "legacy_workbook": "",
                "legacy_sheet_name": "",
                "legacy_excel_row": "",
                "legacy_link_id": "",
                "legacy_selected_as_prior_evidence": "",
                "legacy_needs_review": "",
                "legacy_review_reasons": "",
                "created_at": utc_now(),
            }
        )
    return pd.DataFrame(rows)


def build_legacy_gap_fill_inventory(coverage: pd.DataFrame, legacy_leads: pd.DataFrame) -> pd.DataFrame:
    missing = coverage.loc[
        coverage["candidate_status"].ne("explicit_year_candidate_found"), ["unitid", "target_year"]
    ].copy()
    legacy = legacy_leads.copy()
    legacy["target_year"] = legacy["target_year"].astype(int)
    legacy["legacy_url"] = legacy["legacy_url"].map(clean_text)
    legacy = legacy[legacy["legacy_url"].ne("")]
    gap = legacy.merge(missing, on=["unitid", "target_year"], how="inner")
    rows = []
    for _, row in gap.iterrows():
        rows.append(
            {
                "source_id": f"batch2-legacy-gap-{int(row['unitid'])}-{int(row['target_year'])}-{int(row['legacy_link_id'])}",
                "pilot_rank": int(row["batch2_rank"]),
                "unitid": int(row["unitid"]),
                "institution_name": row["institution_name"],
                "target_year": int(row["target_year"]),
                "candidate_url": row["legacy_url"],
                "source_title": f"Legacy prior evidence lead for AY {int(row['target_year'])}",
                "catalog_year_start": int(row["target_year"]),
                "catalog_year_end": int(row["target_year"]) + 1,
                "candidate_source_method": "legacy_gap_fill_outside_root_span",
                "archive_url": row.get("legacy_url_parent", ""),
                "needs_human_review": True,
                "review_reason": "Legacy gap-fill candidate outside preferred-root explicit archive span; retrieve and verify catalog-year evidence before treating as strict coverage.",
                "legacy_workbook": "public",
                "legacy_sheet_name": "",
                "legacy_excel_row": "",
                "legacy_link_id": row["legacy_link_id"],
                "legacy_selected_as_prior_evidence": row["selected_as_prior_evidence"],
                "legacy_needs_review": row["legacy_needs_review"],
                "legacy_review_reasons": row["legacy_review_reasons"],
                "created_at": utc_now(),
            }
        )
    return pd.DataFrame(rows)


def build_combined_inventory(year_candidates: pd.DataFrame, coverage: pd.DataFrame, legacy_leads: pd.DataFrame) -> pd.DataFrame:
    combined = pd.concat(
        [build_root_inventory(year_candidates), build_legacy_gap_fill_inventory(coverage, legacy_leads)],
        ignore_index=True,
        sort=False,
    )
    return combined.sort_values(["pilot_rank", "unitid", "target_year", "candidate_source_method", "source_id"])


def build_year_summary(coverage: pd.DataFrame, retrieval_coverage: pd.DataFrame) -> pd.DataFrame:
    rows = []
    if retrieval_coverage.empty:
        retrieval_coverage = pd.DataFrame(columns=["unitid", "target_year", "source_retrieved", "candidate_source_method"])
    grouped = retrieval_coverage.groupby(["unitid", "target_year"], dropna=False)
    retrieved_pairs = {
        key: group
        for key, group in grouped
    }
    for _, row in coverage.iterrows():
        key = (row["unitid"], row["target_year"])
        group = retrieved_pairs.get(key, pd.DataFrame())
        method_values = group.get("candidate_source_method", pd.Series(dtype=object)).dropna().astype(str)
        retrieved = bool(group.get("source_retrieved", pd.Series(dtype=bool)).fillna(False).any()) if not group.empty else False
        has_root_candidate = clean_text(row.get("candidate_url", "")) != ""
        has_legacy_gap_fill = bool(method_values.eq("legacy_gap_fill_outside_root_span").any())
        rows.append(
            {
                "batch2_rank": row["batch2_rank"],
                "unitid": row["unitid"],
                "institution_name": row["institution_name"],
                "target_year": int(row["target_year"]),
                "has_root_archive_candidate": has_root_candidate,
                "has_legacy_gap_fill_candidate": has_legacy_gap_fill,
                "has_any_catalog_candidate": has_root_candidate or has_legacy_gap_fill,
                "any_candidate_retrieved": retrieved,
                "batch2_year_status": (
                    "root_candidate"
                    if has_root_candidate
                    else "legacy_gap_fill_candidate"
                    if has_legacy_gap_fill
                    else "missing_after_root_and_legacy"
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(["batch2_rank", "unitid", "target_year"])


def write_summary(
    path: Path,
    inventory: pd.DataFrame,
    attempts: pd.DataFrame,
    retrieval_coverage: pd.DataFrame,
    year_summary: pd.DataFrame,
) -> None:
    lines = [
        "# Phase 3 Batch 2 Run-Through",
        "",
        f"Generated at: {utc_now()}",
        "",
        "Scope: preferred-root catalog candidates plus controlled legacy gap-fill for years missing from the preferred root/archive span.",
        "",
        "## Candidate Inventory",
        "",
    ]
    for method, count in inventory["candidate_source_method"].value_counts(dropna=False).items():
        lines.append(f"- {method}: {count}")
    lines.extend(["", "## Retrieval Status", ""])
    if attempts.empty:
        lines.append("- none")
    else:
        for status, count in attempts["retrieval_status"].value_counts(dropna=False).items():
            lines.append(f"- {status}: {count}")
    lines.extend(["", "## Institution-Year Candidate Coverage", ""])
    for (unitid, name), group in year_summary.groupby(["unitid", "institution_name"], dropna=False):
        any_candidate = int(group["has_any_catalog_candidate"].sum())
        root_candidate = int(group["has_root_archive_candidate"].sum())
        legacy_gap = int(group["has_legacy_gap_fill_candidate"].sum())
        retrieved = int(group["any_candidate_retrieved"].sum())
        missing = group.loc[~group["has_any_catalog_candidate"], "target_year"].astype(int).tolist()
        lines.append(
            f"- {name} ({int(unitid)}): candidates {any_candidate}/21 "
            f"(root {root_candidate}, legacy gap-fill {legacy_gap}); retrieved {retrieved}/21; missing {missing or 'none'}"
        )
    lines.extend(["", "## Notes", ""])
    lines.append("- This is still source coverage, not final policy classification.")
    lines.append("- Legacy gap-fill candidates remain flagged for human review until catalog-year evidence is verified from the retrieved source.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_batch2_runthrough(repo_root: Path, *, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> Batch2RunthroughOutputs:
    repo_root = repo_root.resolve()
    year_candidates, coverage, legacy_leads = read_inputs(repo_root)
    inventory = build_combined_inventory(year_candidates, coverage, legacy_leads)
    attempts = build_retrieval_attempts(repo_root, inventory, timeout_seconds=timeout_seconds)
    retrieval_coverage = build_coverage(inventory, attempts)
    retrieval_coverage = retrieval_coverage.merge(
        inventory[["source_id", "candidate_source_method"]],
        on="source_id",
        how="left",
    )
    year_summary = build_year_summary(coverage, retrieval_coverage)

    outputs = Batch2RunthroughOutputs(
        combined_inventory=(repo_root / BATCH2_COMBINED_INVENTORY_OUTPUT).resolve(),
        retrieval_attempts=(repo_root / BATCH2_RETRIEVAL_ATTEMPTS_OUTPUT).resolve(),
        retrieval_coverage=(repo_root / BATCH2_RETRIEVAL_COVERAGE_OUTPUT).resolve(),
        year_summary=(repo_root / BATCH2_RUNTHROUGH_YEAR_SUMMARY_OUTPUT).resolve(),
        summary_report=(repo_root / BATCH2_RUNTHROUGH_SUMMARY_OUTPUT).resolve(),
    )
    for output_path in outputs.__dict__.values():
        output_path.parent.mkdir(parents=True, exist_ok=True)
    inventory.to_csv(outputs.combined_inventory, index=False)
    attempts.to_csv(outputs.retrieval_attempts, index=False)
    retrieval_coverage.to_csv(outputs.retrieval_coverage, index=False)
    year_summary.to_csv(outputs.year_summary, index=False)
    write_summary(outputs.summary_report, inventory, attempts, retrieval_coverage, year_summary)
    return outputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Phase 3 batch-2 catalog source pilot through retrieval.")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve() if args.root else repo_root_from_cwd()
    outputs = run_batch2_runthrough(root, timeout_seconds=args.timeout_seconds)
    for label, output_path in outputs.__dict__.items():
        print(f"{label}: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
