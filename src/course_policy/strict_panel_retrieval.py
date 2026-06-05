"""Retrieve ready catalog candidates from the strict 5-institution panel expansion."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .ai_config import repo_root_from_cwd
from .catalog_retrieval import DEFAULT_TIMEOUT_SECONDS, build_coverage, build_retrieval_attempts
from .institution_universe import TARGET_END_YEAR, TARGET_START_YEAR
from .strict_pilot import build_strict_year_coverage, extract_strict_year_evidence


DATA_DIR = Path("../data_policy_pipeline")
INTERIM_DIR = DATA_DIR / "interim"
LOG_DIR = DATA_DIR / "logs"

STRICT_INSTITUTIONS_INPUT = INTERIM_DIR / "catalog_pilot_institutions_strict.csv"
INSTITUTION_YEAR_TARGETS_INPUT = INTERIM_DIR / "institution_year_targets.csv"
STRICT_RETRIEVAL_COVERAGE_INPUT = INTERIM_DIR / "catalog_retrieval_coverage_strict_pilot.csv"
PANEL_CANDIDATES_INPUT = INTERIM_DIR / "catalog_panel_candidates_strict_pilot.csv"
PANEL_YEAR_STATUS_INPUT = INTERIM_DIR / "catalog_panel_year_status_strict_pilot.csv"

PANEL_READY_INVENTORY_OUTPUT = INTERIM_DIR / "catalog_panel_ready_inventory_strict_pilot.csv"
PANEL_RETRIEVAL_ATTEMPTS_OUTPUT = INTERIM_DIR / "catalog_panel_retrieval_attempts_strict_pilot.csv"
PANEL_RETRIEVAL_COVERAGE_OUTPUT = INTERIM_DIR / "catalog_panel_retrieval_coverage_strict_pilot.csv"
PANEL_YEAR_COVERAGE_OUTPUT = INTERIM_DIR / "catalog_panel_year_coverage_retrieved_strict_pilot.csv"
PANEL_RETRIEVAL_SUMMARY_OUTPUT = LOG_DIR / "phase3_strict_panel_retrieval_summary.md"


@dataclass(frozen=True)
class StrictPanelRetrievalOutputs:
    ready_inventory: Path
    retrieval_attempts: Path
    retrieval_coverage: Path
    year_coverage: Path
    summary_report: Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_inputs(repo_root: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    return (
        pd.read_csv(repo_root / STRICT_INSTITUTIONS_INPUT, low_memory=False),
        pd.read_csv(repo_root / INSTITUTION_YEAR_TARGETS_INPUT, low_memory=False),
        pd.read_csv(repo_root / STRICT_RETRIEVAL_COVERAGE_INPUT, low_memory=False),
        pd.read_csv(repo_root / PANEL_CANDIDATES_INPUT, low_memory=False),
        pd.read_csv(repo_root / PANEL_YEAR_STATUS_INPUT, low_memory=False),
    )


def build_ready_inventory(institutions: pd.DataFrame, candidates: pd.DataFrame) -> pd.DataFrame:
    inst_meta = institutions[["unitid", "strict_pilot_rank", "strict_pilot_reason"]].copy()
    ready = candidates[candidates["source_status"].eq("ready_for_retrieval")].copy()
    ready = ready.merge(inst_meta, on="unitid", how="left")
    rows: list[dict[str, object]] = []
    created_at = utc_now()
    for _, source in ready.sort_values(["strict_pilot_rank", "unitid", "catalog_year_start", "source_id"]).iterrows():
        rows.append(
            {
                "source_id": source["source_id"],
                "pilot_rank": int(source["strict_pilot_rank"]),
                "strict_pilot_rank": int(source["strict_pilot_rank"]),
                "strict_pilot_reason": source["strict_pilot_reason"],
                "unitid": int(source["unitid"]),
                "institution_name": source["institution_name"],
                "target_year": int(source["catalog_year_start"]),
                "candidate_url": source["candidate_url"],
                "source_kind": source["source_kind"],
                "source_title": source["source_title"],
                "catalog_year_start": int(source["catalog_year_start"]),
                "catalog_year_end": int(source["catalog_year_end"]),
                "discovery_method": source["discovery_method"],
                "archive_page_url": source["archive_page_url"],
                "retrieval_status": "not_attempted",
                "text_extract_status": "not_attempted",
                "needs_human_review": False,
                "review_reason": "",
                "legacy_workbook": "",
                "legacy_sheet_name": "",
                "legacy_excel_row": "",
                "legacy_link_id": "",
                "legacy_selected_as_prior_evidence": "",
                "legacy_needs_review": "",
                "legacy_review_reasons": "",
                "created_at": created_at,
                "updated_at": created_at,
            }
        )
    return pd.DataFrame(rows)


def combine_strict_retrieval(existing_strict: pd.DataFrame, panel_retrieval: pd.DataFrame) -> pd.DataFrame:
    combined = pd.concat([existing_strict, panel_retrieval], ignore_index=True, sort=False)
    if combined.empty:
        return combined
    return combined.sort_values(["unitid", "target_year", "source_id"]).reset_index(drop=True)


def enrich_missing_year_reasons(year_coverage: pd.DataFrame, panel_year_status: pd.DataFrame) -> pd.DataFrame:
    status_cols = [
        "unitid",
        "target_year",
        "candidate_status",
        "candidate_title",
        "candidate_review_reason",
    ]
    status = panel_year_status.reindex(columns=status_cols).copy()
    merged = year_coverage.merge(status, on=["unitid", "target_year"], how="left")
    missing = ~merged["has_strict_catalog_source"].fillna(False)
    status_text = merged["candidate_status"].fillna("")
    reason_text = merged["candidate_review_reason"].fillna("")
    title_text = merged["candidate_title"].fillna("")
    enriched_reason = "Panel expansion status: " + status_text
    cleaned_reason = reason_text.str.rstrip(".")
    enriched_reason = enriched_reason.where(cleaned_reason.eq(""), enriched_reason + ". " + cleaned_reason)
    enriched_reason = enriched_reason.where(title_text.eq(""), enriched_reason + ". Candidate/title: " + title_text)
    merged.loc[missing & status_text.ne(""), "review_reason"] = enriched_reason[missing & status_text.ne("")]
    return merged.drop(columns=["candidate_status", "candidate_title", "candidate_review_reason"])


def write_summary(
    path: Path,
    ready_inventory: pd.DataFrame,
    attempts: pd.DataFrame,
    retrieval: pd.DataFrame,
    year_coverage: pd.DataFrame,
) -> None:
    total_years = len(year_coverage)
    covered_years = int(year_coverage["has_strict_catalog_source"].sum()) if total_years else 0
    newly_strict = int(retrieval["strict_covers_target_year"].sum()) if not retrieval.empty else 0
    retrieved_sources = int(retrieval["source_retrieved"].sum()) if not retrieval.empty else 0
    lines = [
        "# Phase 3 Strict Panel Retrieval",
        "",
        f"Generated at: {utc_now()}",
        "",
        "Scope: retrieve and validate only `ready_for_retrieval` candidates from the 5-institution strict panel expansion.",
        "",
        "## Retrieval Batch",
        "",
        f"- Ready candidate sources attempted: {len(ready_inventory)}",
        f"- Retrieval attempts: {len(attempts)}",
        f"- Candidate sources retrieved: {retrieved_sources}",
        f"- Retrieved candidate sources with strict catalog-year evidence for their start year: {newly_strict}",
        "",
        "## Combined Strict Year Coverage",
        "",
        f"- Institution-year rows: {total_years}",
        f"- Institution-years with strict source coverage: {covered_years}",
        f"- Institution-years missing strict source coverage: {total_years - covered_years}",
        f"- Strict coverage rate: {covered_years / total_years:.1%}" if total_years else "- Strict coverage rate: n/a",
        "",
        "## Retrieval Methods",
        "",
    ]
    if attempts.empty:
        lines.append("- none")
    else:
        for method, count in attempts["attempt_method"].value_counts(dropna=False).items():
            lines.append(f"- {method}: {count}")
    lines.extend(["", "## Retrieval Statuses", ""])
    if attempts.empty:
        lines.append("- none")
    else:
        for status, count in attempts["retrieval_status"].value_counts(dropna=False).items():
            lines.append(f"- {status}: {count}")
    lines.extend(["", "## Catalog-Year Evidence Types", ""])
    if retrieval.empty:
        lines.append("- none")
    else:
        for evidence_type, count in retrieval["catalog_year_evidence_type"].value_counts(dropna=False).items():
            lines.append(f"- {evidence_type}: {count}")
    lines.extend(["", "## Institutions", ""])
    for (unitid, name), group in year_coverage.groupby(["unitid", "institution_name"], dropna=False):
        covered = int(group["has_strict_catalog_source"].sum())
        lines.append(f"- {name} ({int(unitid)}): {covered}/{len(group)} strict-covered")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_strict_panel_retrieval(
    repo_root: Path,
    *,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> StrictPanelRetrievalOutputs:
    repo_root = repo_root.resolve()
    institutions, targets, existing_strict, candidates, panel_year_status = read_inputs(repo_root)
    ready_inventory = build_ready_inventory(institutions, candidates)
    attempts = build_retrieval_attempts(repo_root, ready_inventory, timeout_seconds=timeout_seconds)
    panel_retrieval = extract_strict_year_evidence(build_coverage(ready_inventory, attempts))
    combined_retrieval = combine_strict_retrieval(existing_strict, panel_retrieval)
    year_coverage = build_strict_year_coverage(institutions, targets, combined_retrieval)
    year_coverage = year_coverage[
        year_coverage["target_year"].between(TARGET_START_YEAR, TARGET_END_YEAR)
    ].sort_values(["strict_pilot_rank", "unitid", "target_year"])
    year_coverage = enrich_missing_year_reasons(year_coverage, panel_year_status)

    outputs = StrictPanelRetrievalOutputs(
        ready_inventory=(repo_root / PANEL_READY_INVENTORY_OUTPUT).resolve(),
        retrieval_attempts=(repo_root / PANEL_RETRIEVAL_ATTEMPTS_OUTPUT).resolve(),
        retrieval_coverage=(repo_root / PANEL_RETRIEVAL_COVERAGE_OUTPUT).resolve(),
        year_coverage=(repo_root / PANEL_YEAR_COVERAGE_OUTPUT).resolve(),
        summary_report=(repo_root / PANEL_RETRIEVAL_SUMMARY_OUTPUT).resolve(),
    )
    for output_path in outputs.__dict__.values():
        output_path.parent.mkdir(parents=True, exist_ok=True)
    ready_inventory.to_csv(outputs.ready_inventory, index=False)
    attempts.to_csv(outputs.retrieval_attempts, index=False)
    panel_retrieval.to_csv(outputs.retrieval_coverage, index=False)
    year_coverage.to_csv(outputs.year_coverage, index=False)
    write_summary(outputs.summary_report, ready_inventory, attempts, panel_retrieval, year_coverage)
    return outputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Retrieve ready candidates from the strict pilot panel expansion.")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve() if args.root else repo_root_from_cwd()
    outputs = run_strict_panel_retrieval(root, timeout_seconds=args.timeout_seconds)
    for label, output_path in outputs.__dict__.items():
        print(f"{label}: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
