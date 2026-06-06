"""Run the next Phase 3 catalog-discovery expansion batch."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .ai_config import repo_root_from_cwd
from .batch3_discovery import (
    BATCH_SIZE,
    add_legacy_gap_status,
    build_archive_pages,
    build_inventory,
    build_legacy_gap_candidates,
    build_legacy_leads,
    build_observed_candidate_bounds,
    build_retrieval_attempts,
    build_root_candidates,
    build_source_root_decisions,
    build_stage_status,
    build_year_candidates,
    build_year_coverage,
    build_coverage,
    source_root_tasks,
    utc_now,
)
from .catalog_retrieval import retrieve_url, save_source_body


DATA_DIR = Path("../data_policy_pipeline")
INTERIM_DIR = DATA_DIR / "interim"
LOG_DIR = DATA_DIR / "logs"

INSTITUTION_UNIVERSE_INPUT = INTERIM_DIR / "institution_universe.csv"
LEGACY_EVIDENCE_LINKS_INPUT = INTERIM_DIR / "legacy_evidence_links.csv"
INSTITUTION_YEAR_TARGETS_INPUT = INTERIM_DIR / "institution_year_targets.csv"
STRICT_INSTITUTIONS_INPUT = INTERIM_DIR / "catalog_pilot_institutions_strict.csv"
BATCH2_INSTITUTIONS_INPUT = INTERIM_DIR / "catalog_batch2_institutions.csv"
BATCH3_INSTITUTIONS_INPUT = INTERIM_DIR / "catalog_batch3_institutions.csv"

BATCH4_INSTITUTIONS_OUTPUT = INTERIM_DIR / "catalog_batch4_institutions.csv"
BATCH4_LEGACY_LEADS_OUTPUT = INTERIM_DIR / "catalog_batch4_legacy_leads.csv"
BATCH4_ROOT_CANDIDATES_OUTPUT = INTERIM_DIR / "catalog_batch4_root_candidates.csv"
BATCH4_SOURCE_ROOT_DECISIONS_OUTPUT = INTERIM_DIR / "catalog_batch4_source_root_decisions.csv"
BATCH4_ARCHIVE_PAGES_OUTPUT = INTERIM_DIR / "catalog_batch4_archive_pages.csv"
BATCH4_SECONDARY_ARCHIVE_SEEDS_OUTPUT = INTERIM_DIR / "catalog_batch4_secondary_archive_seeds.csv"
BATCH4_YEAR_CANDIDATES_OUTPUT = INTERIM_DIR / "catalog_batch4_year_candidates.csv"
BATCH4_YEAR_COVERAGE_OUTPUT = INTERIM_DIR / "catalog_batch4_year_coverage.csv"
BATCH4_LEGACY_GAP_CANDIDATES_OUTPUT = INTERIM_DIR / "catalog_batch4_legacy_gap_candidates.csv"
BATCH4_COMBINED_INVENTORY_OUTPUT = INTERIM_DIR / "catalog_batch4_combined_inventory.csv"
BATCH4_RETRIEVAL_ATTEMPTS_OUTPUT = INTERIM_DIR / "catalog_batch4_retrieval_attempts.csv"
BATCH4_RETRIEVAL_COVERAGE_OUTPUT = INTERIM_DIR / "catalog_batch4_retrieval_coverage.csv"
BATCH4_STAGE_STATUS_OUTPUT = INTERIM_DIR / "catalog_batch4_stage_status.csv"
BATCH4_SUMMARY_OUTPUT = LOG_DIR / "phase3_batch4_discovery_summary.md"


@dataclass(frozen=True)
class Batch4Outputs:
    institutions: Path
    legacy_leads: Path
    root_candidates: Path
    source_root_decisions: Path
    archive_pages: Path
    secondary_archive_seeds: Path
    year_candidates: Path
    year_coverage: Path
    legacy_gap_candidates: Path
    combined_inventory: Path
    retrieval_attempts: Path
    retrieval_coverage: Path
    stage_status: Path
    summary_report: Path


def read_inputs(repo_root: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    return (
        pd.read_csv(repo_root / INSTITUTION_UNIVERSE_INPUT, low_memory=False),
        pd.read_csv(repo_root / LEGACY_EVIDENCE_LINKS_INPUT, low_memory=False),
        pd.read_csv(repo_root / INSTITUTION_YEAR_TARGETS_INPUT, low_memory=False),
        pd.read_csv(repo_root / STRICT_INSTITUTIONS_INPUT, low_memory=False),
        pd.read_csv(repo_root / BATCH2_INSTITUTIONS_INPUT, low_memory=False),
        pd.read_csv(repo_root / BATCH3_INSTITUTIONS_INPUT, low_memory=False),
    )


def select_batch4_institutions(
    universe: pd.DataFrame,
    links: pd.DataFrame,
    strict: pd.DataFrame,
    batch2: pd.DataFrame,
    batch3: pd.DataFrame,
    *,
    batch_size: int = BATCH_SIZE,
) -> pd.DataFrame:
    prior_unitids = set(strict["unitid"].dropna().astype(int))
    prior_unitids |= set(batch2["unitid"].dropna().astype(int))
    prior_unitids |= set(batch3["unitid"].dropna().astype(int))

    public_links = links.loc[links["legacy_workbook"].eq("public")].copy()
    link_summary = (
        public_links.groupby("unitid", as_index=False)
        .agg(
            legacy_link_rows=("legacy_link_id", "count"),
            legacy_year_count=("target_year", "nunique"),
            legacy_url_count=("legacy_url", lambda values: int(values.fillna("").astype(str).str.strip().ne("").sum())),
            selected_clean_url_count=(
                "selected_as_prior_evidence",
                lambda values: int(values.fillna(False).astype(bool).sum()),
            ),
            missing_url_count=("missing_bulletin_url", lambda values: int(values.fillna(False).astype(bool).sum())),
            needs_review_count=("legacy_needs_review", lambda values: int(values.fillna(False).astype(bool).sum())),
        )
    )
    candidates = universe.loc[
        universe["sector"].eq("public_4_year")
        & universe["active_in_ipeds_panel"].fillna(False).astype(bool)
        & universe["source_in_legacy_public"].fillna(False).astype(bool)
        & ~universe["unitid"].astype(int).isin(prior_unitids)
    ].copy()
    candidates = candidates.merge(link_summary, on="unitid", how="left")
    candidates["legacy_link_rows"] = candidates["legacy_link_rows"].fillna(0).astype(int)
    candidates["legacy_year_count"] = candidates["legacy_year_count"].fillna(0).astype(int)
    candidates["legacy_url_count"] = candidates["legacy_url_count"].fillna(0).astype(int)
    candidates = candidates.loc[candidates["legacy_url_count"].gt(0)].sort_values(
        ["legacy_url_count", "legacy_year_count", "unitid"],
        ascending=[False, False, True],
    )
    selected = candidates.head(batch_size).copy()
    selected["batch3_rank"] = range(1, len(selected) + 1)
    selected["batch4_rank"] = selected["batch3_rank"]
    selected["pilot_rank"] = selected["batch4_rank"]
    selected["pilot_case_types"] = "batch4_public_legacy_expansion"
    selected["created_at"] = utc_now()
    columns = [
        "batch4_rank",
        "batch3_rank",
        "pilot_rank",
        "unitid",
        "institution_name",
        "state",
        "webaddr",
        "pilot_case_types",
        "legacy_link_rows",
        "legacy_year_count",
        "legacy_url_count",
        "selected_clean_url_count",
        "missing_url_count",
        "needs_review_count",
        "created_at",
    ]
    for col in columns:
        if col not in selected.columns:
            selected[col] = ""
    return selected[columns]


def reviewed_secondary_archive_seeds(batch: pd.DataFrame) -> pd.DataFrame:
    rows = []
    reviewed = {
        100706: {
            "archive_url": "https://louis.uah.edu/catalogs/",
            "archive_source": "reviewed_root_page_pointer",
            "archive_link_text": "UAH root page points to library archive course catalogs.",
        }
    }
    for _, inst in batch.iterrows():
        seed = reviewed.get(int(inst["unitid"]))
        if not seed:
            continue
        rows.append(
            {
                "batch3_rank": int(inst["batch3_rank"]),
                "unitid": int(inst["unitid"]),
                "institution_name": inst["institution_name"],
                "preferred_source_root_url": "",
                "archive_url": seed["archive_url"],
                "archive_source": seed["archive_source"],
                "archive_link_text": seed["archive_link_text"],
                "created_at": utc_now(),
            }
        )
    return pd.DataFrame(rows)


def append_secondary_archive_pages(
    repo_root: Path,
    archive_pages: pd.DataFrame,
    result_by_url: dict[str, dict[str, object]],
    seeds: pd.DataFrame,
    *,
    timeout_seconds: int,
) -> tuple[pd.DataFrame, dict[str, dict[str, object]]]:
    if seeds.empty:
        return archive_pages, result_by_url
    rows = []
    existing_urls = set(archive_pages["archive_url"].fillna("").astype(str)) if not archive_pages.empty else set()
    for idx, seed in seeds.sort_values(["batch3_rank", "unitid", "archive_url"]).iterrows():
        archive_url = seed["archive_url"]
        if archive_url in existing_urls:
            continue
        result = retrieve_url(archive_url, timeout_seconds=timeout_seconds, max_bytes=5_000_000)
        result_by_url[archive_url] = result
        local_source_path = ""
        if result["retrieval_status"] in {"retrieved", "retrieved_truncated"}:
            local_source_path = str(
                save_source_body(
                    repo_root,
                    f"batch4-secondary-archive-{int(seed['unitid'])}-{len(rows) + 1:02d}",
                    "archive_page",
                    archive_url,
                    str(result["content_type"]),
                    result["body"],
                )
            )
        rows.append(
            {
                "batch3_rank": int(seed["batch3_rank"]),
                "unitid": int(seed["unitid"]),
                "institution_name": seed["institution_name"],
                "preferred_source_root_url": seed.get("preferred_source_root_url", ""),
                "archive_url": archive_url,
                "archive_source": seed["archive_source"],
                "archive_link_text": seed["archive_link_text"],
                "retrieval_status": result["retrieval_status"],
                "http_status": result["http_status"],
                "final_url": result["final_url"],
                "content_type": result["content_type"],
                "page_title": result["page_title"],
                "year_hints": result["year_hints"],
                "link_count": len(result.get("link_records", [])),
                "local_source_path": local_source_path,
                "created_at": utc_now(),
            }
        )
    if rows:
        archive_pages = pd.concat([archive_pages, pd.DataFrame(rows)], ignore_index=True)
    return archive_pages, result_by_url


def run_batch4_discovery(
    repo_root: Path,
    *,
    batch_size: int = BATCH_SIZE,
    timeout_seconds: int = 12,
) -> Batch4Outputs:
    repo_root = repo_root.resolve()
    universe, links, targets, strict, batch2, batch3 = read_inputs(repo_root)
    batch = select_batch4_institutions(universe, links, strict, batch2, batch3, batch_size=batch_size)
    legacy_leads = build_legacy_leads(batch, links)
    tasks = source_root_tasks(batch, legacy_leads)
    root_candidates = build_root_candidates(repo_root, legacy_leads, tasks, timeout_seconds=timeout_seconds)
    decisions = build_source_root_decisions(root_candidates, tasks)
    archive_pages, result_by_url = build_archive_pages(repo_root, decisions, timeout_seconds=timeout_seconds)
    secondary_archive_seeds = reviewed_secondary_archive_seeds(batch)
    archive_pages, result_by_url = append_secondary_archive_pages(
        repo_root,
        archive_pages,
        result_by_url,
        secondary_archive_seeds,
        timeout_seconds=timeout_seconds,
    )
    year_candidates = build_year_candidates(archive_pages, result_by_url)
    observed_bounds = build_observed_candidate_bounds(archive_pages, result_by_url)
    year_coverage = build_year_coverage(batch, targets, decisions, year_candidates, archive_pages, observed_bounds)
    legacy_gap_candidates = build_legacy_gap_candidates(year_coverage, legacy_leads)
    year_coverage = add_legacy_gap_status(year_coverage, legacy_gap_candidates)
    inventory = build_inventory(year_coverage, legacy_gap_candidates, source_prefix="batch4")
    retrieval_attempts = build_retrieval_attempts(repo_root, inventory, timeout_seconds=timeout_seconds) if not inventory.empty else pd.DataFrame()
    retrieval_coverage = build_coverage(inventory, retrieval_attempts) if not inventory.empty else pd.DataFrame()
    if not retrieval_coverage.empty:
        retrieval_coverage = retrieval_coverage.merge(
            inventory[["source_id", "candidate_source_method", "candidate_link_text", "archive_url"]],
            on="source_id",
            how="left",
        )
    stage_status = build_stage_status(year_coverage, retrieval_coverage)

    outputs = Batch4Outputs(
        institutions=(repo_root / BATCH4_INSTITUTIONS_OUTPUT).resolve(),
        legacy_leads=(repo_root / BATCH4_LEGACY_LEADS_OUTPUT).resolve(),
        root_candidates=(repo_root / BATCH4_ROOT_CANDIDATES_OUTPUT).resolve(),
        source_root_decisions=(repo_root / BATCH4_SOURCE_ROOT_DECISIONS_OUTPUT).resolve(),
        archive_pages=(repo_root / BATCH4_ARCHIVE_PAGES_OUTPUT).resolve(),
        secondary_archive_seeds=(repo_root / BATCH4_SECONDARY_ARCHIVE_SEEDS_OUTPUT).resolve(),
        year_candidates=(repo_root / BATCH4_YEAR_CANDIDATES_OUTPUT).resolve(),
        year_coverage=(repo_root / BATCH4_YEAR_COVERAGE_OUTPUT).resolve(),
        legacy_gap_candidates=(repo_root / BATCH4_LEGACY_GAP_CANDIDATES_OUTPUT).resolve(),
        combined_inventory=(repo_root / BATCH4_COMBINED_INVENTORY_OUTPUT).resolve(),
        retrieval_attempts=(repo_root / BATCH4_RETRIEVAL_ATTEMPTS_OUTPUT).resolve(),
        retrieval_coverage=(repo_root / BATCH4_RETRIEVAL_COVERAGE_OUTPUT).resolve(),
        stage_status=(repo_root / BATCH4_STAGE_STATUS_OUTPUT).resolve(),
        summary_report=(repo_root / BATCH4_SUMMARY_OUTPUT).resolve(),
    )
    for output_path in outputs.__dict__.values():
        output_path.parent.mkdir(parents=True, exist_ok=True)
    batch.to_csv(outputs.institutions, index=False)
    legacy_leads.to_csv(outputs.legacy_leads, index=False)
    root_candidates.to_csv(outputs.root_candidates, index=False)
    decisions.to_csv(outputs.source_root_decisions, index=False)
    archive_pages.to_csv(outputs.archive_pages, index=False)
    secondary_archive_seeds.to_csv(outputs.secondary_archive_seeds, index=False)
    year_candidates.to_csv(outputs.year_candidates, index=False)
    year_coverage.to_csv(outputs.year_coverage, index=False)
    legacy_gap_candidates.to_csv(outputs.legacy_gap_candidates, index=False)
    inventory.to_csv(outputs.combined_inventory, index=False)
    retrieval_attempts.to_csv(outputs.retrieval_attempts, index=False)
    retrieval_coverage.to_csv(outputs.retrieval_coverage, index=False)
    stage_status.to_csv(outputs.stage_status, index=False)
    write_summary(outputs.summary_report, stage_status, outputs)
    return outputs


def write_summary(path: Path, stage_status: pd.DataFrame, outputs: Batch4Outputs) -> None:
    lines = [
        "# Phase 3 Batch 4 Catalog Discovery",
        "",
        f"Generated at: {utc_now()}",
        "",
        "Scope: next 10 public institutions selected from the full institution universe by public legacy URL availability.",
        "",
        "## Pipeline Stages",
        "",
    ]
    for stage, count in stage_status["pipeline_stage"].value_counts(dropna=False).items():
        lines.append(f"- {stage}: {count}")
    lines.extend(["", "## Next Batch Actions", ""])
    for action, count in stage_status["next_batch_action"].value_counts(dropna=False).items():
        lines.append(f"- {action}: {count}")
    lines.extend(["", "## Institutions", ""])
    for (unitid, name), group in stage_status.groupby(["unitid", "institution_name"], dropna=False):
        action_counts = ", ".join(f"{action}={count}" for action, count in group["next_batch_action"].value_counts().items())
        stages = ", ".join(f"{stage}={count}" for stage, count in group["pipeline_stage"].value_counts().items())
        lines.append(f"- {name} ({int(unitid)}): {action_counts}; stages: {stages}")
    lines.extend(["", "## Outputs", ""])
    for label, output_path in outputs.__dict__.items():
        if label != "summary_report":
            lines.append(f"- {label}: `{output_path}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Phase 3 batch-4 catalog discovery.")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    parser.add_argument("--timeout-seconds", type=int, default=12)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve() if args.root else repo_root_from_cwd()
    outputs = run_batch4_discovery(root, batch_size=args.batch_size, timeout_seconds=args.timeout_seconds)
    for label, output_path in outputs.__dict__.items():
        print(f"{label}: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
