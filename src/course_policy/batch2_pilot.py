"""Set up the next 5-institution Phase 3 catalog-discovery test batch."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

from .ai_config import repo_root_from_cwd
from .institution_universe import TARGET_END_YEAR, TARGET_START_YEAR
from .strict_pilot import STRICT_PILOT_UNITIDS


DATA_DIR = Path("../data_policy_pipeline")
INTERIM_DIR = DATA_DIR / "interim"
LOG_DIR = DATA_DIR / "logs"

PILOT_INSTITUTIONS_INPUT = INTERIM_DIR / "catalog_pilot_institutions.csv"
LEGACY_EVIDENCE_LINKS_INPUT = INTERIM_DIR / "legacy_evidence_links.csv"
INSTITUTION_YEAR_TARGETS_INPUT = INTERIM_DIR / "institution_year_targets.csv"

BATCH2_INSTITUTIONS_OUTPUT = INTERIM_DIR / "catalog_batch2_institutions.csv"
BATCH2_LEGACY_LEADS_OUTPUT = INTERIM_DIR / "catalog_batch2_legacy_leads.csv"
BATCH2_SOURCE_ROOT_TASKS_OUTPUT = INTERIM_DIR / "catalog_batch2_source_root_tasks.csv"
BATCH2_YEAR_STATUS_OUTPUT = INTERIM_DIR / "catalog_batch2_year_status.csv"
BATCH2_STATUS_SUMMARY_OUTPUT = INTERIM_DIR / "catalog_batch2_status_summary.csv"
BATCH2_SUMMARY_OUTPUT = LOG_DIR / "phase3_batch2_setup_summary.md"

BATCH_SIZE = 5

BATCH2_COLUMNS = [
    "batch2_rank",
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


@dataclass(frozen=True)
class Batch2Outputs:
    institutions: Path
    legacy_leads: Path
    source_root_tasks: Path
    year_status: Path
    status_summary: Path
    summary_report: Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_inputs(repo_root: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    return (
        pd.read_csv(repo_root / PILOT_INSTITUTIONS_INPUT, low_memory=False),
        pd.read_csv(repo_root / LEGACY_EVIDENCE_LINKS_INPUT, low_memory=False),
        pd.read_csv(repo_root / INSTITUTION_YEAR_TARGETS_INPUT, low_memory=False),
    )


def select_batch2_institutions(pilot: pd.DataFrame, batch_size: int = BATCH_SIZE) -> pd.DataFrame:
    excluded = set(STRICT_PILOT_UNITIDS)
    selected = pilot.loc[~pilot["unitid"].astype(int).isin(excluded)].sort_values("pilot_rank").head(batch_size).copy()
    selected["batch2_rank"] = range(1, len(selected) + 1)
    selected["created_at"] = utc_now()
    for col in BATCH2_COLUMNS:
        if col not in selected.columns:
            selected[col] = ""
    return selected[BATCH2_COLUMNS]


def clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def source_domain(url: str) -> str:
    if not url:
        return ""
    return urlparse(url).netloc.lower()


def parent_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url)
    path = parsed.path
    if not path or path == "/":
        return f"{parsed.scheme}://{parsed.netloc}/"
    parent = path.rsplit("/", 1)[0] + "/"
    return parsed._replace(path=parent, params="", query="", fragment="").geturl()


def build_legacy_leads(batch: pd.DataFrame, links: pd.DataFrame) -> pd.DataFrame:
    batch_unitids = set(batch["unitid"].astype(int))
    batch_ranks = batch.set_index("unitid")["batch2_rank"].to_dict()
    batch_names = {int(row["unitid"]): row["institution_name"] for _, row in batch.iterrows()}
    leads = links.loc[links["unitid"].isin(batch_unitids) & links["legacy_workbook"].eq("public")].copy()
    if leads.empty:
        return pd.DataFrame()
    leads["batch2_rank"] = leads["unitid"].map(batch_ranks).astype(int)
    leads["institution_name"] = leads["unitid"].astype(int).map(batch_names)
    leads["legacy_url"] = leads["legacy_url"].map(clean_text)
    leads["legacy_url_domain"] = leads["legacy_url"].map(source_domain)
    leads["legacy_url_parent"] = leads["legacy_url"].map(parent_url)
    leads["legacy_lead_role"] = "prior_discovery_lead"
    leads["recommended_use"] = (
        "Inspect early as a discovery lead. Prefer official archive/root if found; use legacy URL as gap-fill only outside official archive coverage."
    )
    leads["created_at"] = utc_now()
    columns = [
        "batch2_rank",
        "unitid",
        "institution_name",
        "target_year",
        "legacy_link_id",
        "legacy_url",
        "legacy_url_domain",
        "legacy_url_parent",
        "legacy_policy_class",
        "selected_as_prior_evidence",
        "legacy_needs_review",
        "legacy_review_reasons",
        "legacy_lead_role",
        "recommended_use",
        "created_at",
    ]
    for col in columns:
        if col not in leads.columns:
            leads[col] = ""
    return leads[columns].sort_values(["batch2_rank", "target_year", "legacy_link_id"])


def unique_join(values: pd.Series) -> str:
    cleaned = values.dropna().astype(str).str.strip()
    cleaned = cleaned[cleaned.ne("")]
    return "; ".join(sorted(cleaned.unique()))


def build_source_root_tasks(batch: pd.DataFrame, legacy_leads: pd.DataFrame) -> pd.DataFrame:
    rows = []
    lead_summary = pd.DataFrame()
    if not legacy_leads.empty:
        lead_summary = (
            legacy_leads.groupby("unitid", dropna=False)
            .agg(
                legacy_lead_years=("target_year", lambda values: "; ".join(map(str, sorted(set(values))))),
                legacy_lead_domains=("legacy_url_domain", unique_join),
                legacy_lead_parent_urls=("legacy_url_parent", unique_join),
                legacy_selected_prior_count=("selected_as_prior_evidence", "sum"),
                legacy_review_count=("legacy_needs_review", "sum"),
            )
            .reset_index()
        )
    for _, inst in batch.iterrows():
        unitid = int(inst["unitid"])
        summary = lead_summary.loc[lead_summary["unitid"].eq(unitid)]
        summary_row = summary.iloc[0] if not summary.empty else pd.Series(dtype=object)
        rows.append(
            {
                "batch2_rank": int(inst["batch2_rank"]),
                "unitid": unitid,
                "institution_name": inst["institution_name"],
                "state": inst["state"],
                "webaddr": inst["webaddr"],
                "task_status": "source_root_discovery_needed",
                "preferred_source_root_name": "",
                "preferred_source_root_url": "",
                "preferred_source_root_type": "",
                "legacy_lead_years": summary_row.get("legacy_lead_years", ""),
                "legacy_lead_domains": summary_row.get("legacy_lead_domains", ""),
                "legacy_lead_parent_urls": summary_row.get("legacy_lead_parent_urls", ""),
                "legacy_selected_prior_count": int(summary_row.get("legacy_selected_prior_count", 0) or 0),
                "legacy_review_count": int(summary_row.get("legacy_review_count", 0) or 0),
                "recommended_next_step": (
                    "Inspect legacy URL parents and official registrar/catalog pages to identify one official archive/root. "
                    "Use Wayback only for dead official roots or legacy URLs. Do not search broad state/library digital archives unless they appear organically."
                ),
                "created_at": utc_now(),
            }
        )
    return pd.DataFrame(rows).sort_values(["batch2_rank", "unitid"])


def build_year_status(batch: pd.DataFrame, targets: pd.DataFrame, legacy_leads: pd.DataFrame) -> pd.DataFrame:
    batch_unitids = set(batch["unitid"].astype(int))
    status = targets.loc[targets["unitid"].isin(batch_unitids)].rename(columns={"year": "target_year"}).copy()
    status = status.merge(
        batch[["unitid", "batch2_rank", "pilot_case_types"]],
        on="unitid",
        how="left",
    )
    legacy_years = legacy_leads[["unitid", "target_year", "legacy_url"]].copy() if not legacy_leads.empty else pd.DataFrame()
    if not legacy_years.empty:
        legacy_years["has_legacy_url_lead"] = legacy_years["legacy_url"].fillna("").astype(str).str.strip().ne("")
        legacy_years = legacy_years.groupby(["unitid", "target_year"], as_index=False).agg(
            has_legacy_url_lead=("has_legacy_url_lead", "max"),
            legacy_url_leads=("legacy_url", unique_join),
        )
        status = status.merge(legacy_years, on=["unitid", "target_year"], how="left")
    else:
        status["has_legacy_url_lead"] = False
        status["legacy_url_leads"] = ""
    status["has_legacy_url_lead"] = status["has_legacy_url_lead"].map(lambda value: str(value).lower() == "true")
    status["legacy_url_leads"] = status["legacy_url_leads"].fillna("")
    status["candidate_status"] = "source_root_discovery_needed"
    status.loc[status["has_legacy_url_lead"], "candidate_status"] = "legacy_lead_available"
    status["has_strict_catalog_source"] = False
    status["source_id"] = ""
    status["candidate_review_reason"] = (
        "Batch 2 setup only: identify official archive/root before retrieving or counting catalog coverage."
    )
    status["created_at"] = utc_now()
    columns = [
        "batch2_rank",
        "unitid",
        "institution_name",
        "state",
        "target_year",
        "pilot_case_types",
        "has_strict_catalog_source",
        "candidate_status",
        "has_legacy_url_lead",
        "legacy_url_leads",
        "source_id",
        "candidate_review_reason",
        "created_at",
    ]
    for col in columns:
        if col not in status.columns:
            status[col] = ""
    return status[columns].sort_values(["batch2_rank", "unitid", "target_year"])


def build_status_summary(batch: pd.DataFrame, year_status: pd.DataFrame, source_root_tasks: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        year_status.groupby(["batch2_rank", "unitid", "institution_name", "state"], dropna=False)
        .agg(
            institution_years=("target_year", "count"),
            strict_covered_years=("has_strict_catalog_source", "sum"),
            legacy_lead_years=("has_legacy_url_lead", "sum"),
            unresolved_years=("has_strict_catalog_source", lambda values: int((~values.fillna(False)).sum())),
        )
        .reset_index()
    )
    grouped["overall_status"] = "source_root_discovery_needed"
    grouped["coverage_rate"] = 0.0
    out = grouped.merge(
        source_root_tasks[
            [
                "unitid",
                "task_status",
                "legacy_lead_domains",
                "legacy_lead_parent_urls",
                "recommended_next_step",
            ]
        ],
        on="unitid",
        how="left",
    )
    return out.sort_values(["batch2_rank", "unitid"])


def write_summary_report(path: Path, outputs: Batch2Outputs, summary: pd.DataFrame) -> None:
    lines = [
        "# Phase 3 Batch 2 Setup",
        "",
        f"Generated at: {utc_now()}",
        "",
        "Purpose: set up a 5-institution public expansion batch without running full discovery yet.",
        "",
        "## Batch Institutions",
        "",
    ]
    for _, row in summary.iterrows():
        lines.append(
            f"- {row['institution_name']} ({row['unitid']}): legacy lead years={int(row['legacy_lead_years'])}; "
            f"status={row['overall_status']}"
        )
    lines.extend(
        [
            "",
            "## Protocol",
            "",
            "- Inspect legacy URLs early as leads.",
            "- Identify one official archive/root before expanding coverage.",
            "- Use Wayback for dead official roots or dead legacy URLs.",
            "- Do not run broad state/library digital archive searches unless they appear organically.",
            "- Do not count any year until explicit catalog-year evidence is retrieved or visually confirmed.",
            "",
            "## Outputs",
            "",
        ]
    )
    for label, output_path in outputs.__dict__.items():
        if label != "summary_report":
            lines.append(f"- {label}: `{output_path}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_batch2_setup(repo_root: Path, *, batch_size: int = BATCH_SIZE) -> Batch2Outputs:
    repo_root = repo_root.resolve()
    pilot, links, targets = read_inputs(repo_root)
    batch = select_batch2_institutions(pilot, batch_size=batch_size)
    legacy_leads = build_legacy_leads(batch, links)
    source_root_tasks = build_source_root_tasks(batch, legacy_leads)
    year_status = build_year_status(batch, targets, legacy_leads)
    status_summary = build_status_summary(batch, year_status, source_root_tasks)

    outputs = Batch2Outputs(
        institutions=(repo_root / BATCH2_INSTITUTIONS_OUTPUT).resolve(),
        legacy_leads=(repo_root / BATCH2_LEGACY_LEADS_OUTPUT).resolve(),
        source_root_tasks=(repo_root / BATCH2_SOURCE_ROOT_TASKS_OUTPUT).resolve(),
        year_status=(repo_root / BATCH2_YEAR_STATUS_OUTPUT).resolve(),
        status_summary=(repo_root / BATCH2_STATUS_SUMMARY_OUTPUT).resolve(),
        summary_report=(repo_root / BATCH2_SUMMARY_OUTPUT).resolve(),
    )
    for output_path in outputs.__dict__.values():
        output_path.parent.mkdir(parents=True, exist_ok=True)
    batch.to_csv(outputs.institutions, index=False)
    legacy_leads.to_csv(outputs.legacy_leads, index=False)
    source_root_tasks.to_csv(outputs.source_root_tasks, index=False)
    year_status.to_csv(outputs.year_status, index=False)
    status_summary.to_csv(outputs.status_summary, index=False)
    write_summary_report(outputs.summary_report, outputs, status_summary)
    return outputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Set up Phase 3 batch-2 catalog discovery pilot.")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve() if args.root else repo_root_from_cwd()
    outputs = run_batch2_setup(root, batch_size=args.batch_size)
    for label, output_path in outputs.__dict__.items():
        print(f"{label}: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
