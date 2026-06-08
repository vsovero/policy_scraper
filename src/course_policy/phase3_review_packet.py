"""Build a streamlined Phase 3 review packet workbook."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .ai_config import repo_root_from_cwd
from .catalog_nonpass_explanations import (
    RECENT_EXPANSION_UNITIDS,
    build_nonpass_table,
    build_recent_summary,
    clean_text,
    explanation_for,
)
from .catalog_spotcheck_audit import SPOTCHECK_AUDIT_OUTPUT
from .manual_catalog_search_audit import MANUAL_AUDIT_OUTPUT
from .spotcheck_workbook import SPOTCHECK_WORKBOOK_OUTPUT, format_workbook


DATA_DIR = Path("../data_policy_pipeline")
REVIEW_DIR = DATA_DIR / "review"
LOG_DIR = DATA_DIR / "logs"

REVIEW_PACKET_OUTPUT = REVIEW_DIR / "phase3_catalog_discovery_review_packet.xlsx"
REVIEW_PACKET_SUMMARY_OUTPUT = LOG_DIR / "phase3_catalog_discovery_review_packet_summary.md"

YEAR_PANEL_COLUMNS = [
    "unitid",
    "institution_name",
    "start_year",
    "best_url",
    "legacy_url",
    "best_url_source",
    "best_url_status",
    "catalog_title_or_link_text",
    "stop_reason",
    "next_batch_action",
    "review_note",
    "manual_best_root_url",
    "manual_status",
    "manual_search_evidence",
]

SOURCE_ROOT_COLUMNS = [
    "unitid",
    "institution_name",
    "manual_status",
    "manual_best_root_url",
    "manual_root_type",
    "manual_coverage_start_year",
    "manual_coverage_end_year",
    "legacy_url_count",
    "legacy_urls_sample",
    "manual_search_evidence",
    "programmatic_fix_needed",
    "next_pipeline_action",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_inputs(repo_root: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    spotcheck = pd.read_excel(repo_root / SPOTCHECK_WORKBOOK_OUTPUT, sheet_name="spotcheck_mockup")
    audit = pd.read_csv(repo_root / SPOTCHECK_AUDIT_OUTPUT, low_memory=False)
    manual = pd.read_csv(repo_root / MANUAL_AUDIT_OUTPUT, low_memory=False)
    return spotcheck, audit, manual


def pass_explanation(row: pd.Series) -> str:
    status = clean_text(row["audit_status"])
    if status == "pass_basic_checks":
        return "All 21 panel years have best URLs and the audit found no missing-year or wrong-scope issues."
    if status == "needs_pipeline_fix":
        return "Pipeline fix required before this institution should be treated as review-ready."
    if status == "needs_ocr_or_visual_review":
        return "Candidate URLs are present, but OCR or visual confirmation is still queued."
    return "Some years are intentionally blank because the reviewed archive has a documented bound, source gap, or scope stop."


def build_institution_summary(audit: pd.DataFrame, spotcheck: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for _, audit_row in audit.sort_values(["audit_status", "institution_name"]).iterrows():
        unitid = int(audit_row["unitid"])
        group = spotcheck.loc[spotcheck["unitid"].eq(unitid)]
        if clean_text(audit_row.get("audit_status", "")) == "pass_basic_checks":
            explanation = pass_explanation(audit_row)
        else:
            explanation = explanation_for(group, audit_row)
        rows.append(
            {
                "unitid": unitid,
                "institution_name": audit_row["institution_name"],
                "audit_status": audit_row["audit_status"],
                "best_url_year_count": int(audit_row["best_url_year_count"]),
                "legacy_url_year_count": int(audit_row["legacy_url_year_count"]),
                "missing_best_url_years": clean_text(audit_row.get("missing_best_url_years", "")),
                "accepted_stop_reasons": clean_text(audit_row.get("accepted_stop_reasons", "")),
                "pipeline_fix_issues": clean_text(audit_row.get("pipeline_fix_issues", "")),
                "warnings": clean_text(audit_row.get("warnings", "")),
                "manual_best_root_url": clean_text(audit_row.get("manual_best_root_url", "")),
                "manual_coverage_start_year": audit_row.get("manual_coverage_start_year", ""),
                "manual_coverage_end_year": audit_row.get("manual_coverage_end_year", ""),
                "plain_language_status": explanation,
            }
        )
    return pd.DataFrame(rows)


def build_start_here(audit: pd.DataFrame, spotcheck: pd.DataFrame) -> pd.DataFrame:
    status_counts = audit["audit_status"].value_counts().to_dict()
    rows = [
        {
            "section": "Current Packet",
            "item": "Purpose",
            "detail": "Review-friendly entry point for Phase 3 catalog discovery results. Use this workbook before opening raw/interim files.",
        },
        {"section": "Current Packet", "item": "Generated at", "detail": utc_now()},
        {"section": "Current Packet", "item": "Institutions", "detail": int(spotcheck["unitid"].nunique())},
        {"section": "Current Packet", "item": "Institution-year rows", "detail": len(spotcheck)},
        {
            "section": "Audit Gate",
            "item": "needs_pipeline_fix",
            "detail": int(status_counts.get("needs_pipeline_fix", 0)),
        },
        {
            "section": "Audit Gate",
            "item": "pass_basic_checks",
            "detail": int(status_counts.get("pass_basic_checks", 0)),
        },
        {
            "section": "Audit Gate",
            "item": "accepted_dead_end_or_archive_bound",
            "detail": int(status_counts.get("accepted_dead_end_or_archive_bound", 0)),
        },
        {
            "section": "Audit Gate",
            "item": "needs_ocr_or_visual_review",
            "detail": int(status_counts.get("needs_ocr_or_visual_review", 0)),
        },
        {
            "section": "How To Review",
            "item": "1",
            "detail": "Start with institution_summary for the one-row-per-institution view.",
        },
        {
            "section": "How To Review",
            "item": "2",
            "detail": "Use nonpass_explanations for the plain-language reasons some panels are partial.",
        },
        {
            "section": "How To Review",
            "item": "3",
            "detail": "Use year_panel_review only when you need year-by-year URLs.",
        },
        {
            "section": "How To Review",
            "item": "4",
            "detail": "Use raw_full_mockup only as an audit/detail sheet; it is not the primary review interface.",
        },
    ]
    return pd.DataFrame(rows)


def build_year_panel_review(spotcheck: pd.DataFrame) -> pd.DataFrame:
    keep = [col for col in YEAR_PANEL_COLUMNS if col in spotcheck.columns]
    return spotcheck[keep].sort_values(["institution_name", "start_year"])


def unitid_name_map(*frames: pd.DataFrame) -> dict[int, str]:
    names: dict[int, str] = {}
    for frame in frames:
        if "unitid" not in frame.columns or "institution_name" not in frame.columns:
            continue
        for _, row in frame[["unitid", "institution_name"]].dropna(subset=["unitid"]).iterrows():
            name = clean_text(row.get("institution_name", ""))
            if name:
                names[int(row["unitid"])] = name
    return names


def build_source_roots(manual: pd.DataFrame, audit: pd.DataFrame, spotcheck: pd.DataFrame) -> pd.DataFrame:
    keep = [col for col in SOURCE_ROOT_COLUMNS if col in manual.columns]
    roots = manual[keep].copy()
    if "unitid" in roots.columns and "institution_name" in roots.columns:
        names = unitid_name_map(spotcheck, audit, manual)
        blank = roots["institution_name"].fillna("").astype(str).str.strip().eq("")
        roots.loc[blank, "institution_name"] = roots.loc[blank, "unitid"].map(lambda value: names.get(int(value), ""))
    existing_unitids = set(roots["unitid"].dropna().astype(int)) if "unitid" in roots.columns else set()
    if not spotcheck.empty:
        automated = spotcheck.loc[~spotcheck["unitid"].astype(int).isin(existing_unitids)].copy()
        if not automated.empty:
            rows = []
            for (unitid, institution_name), group in automated.groupby(["unitid", "institution_name"], dropna=False):
                root_url = first_nonempty_column(group, "preferred_source_root_url") or first_nonempty_column(
                    group, "archive_url"
                )
                rows.append(
                    {
                        "unitid": int(unitid),
                        "institution_name": clean_text(institution_name),
                        "manual_status": "automated_batch_root_discovery",
                        "manual_best_root_url": root_url,
                        "manual_root_type": "automated_preferred_or_archive_root" if root_url else "",
                        "manual_coverage_start_year": "",
                        "manual_coverage_end_year": "",
                        "legacy_url_count": int(group["legacy_url"].fillna("").astype(str).str.strip().ne("").sum())
                        if "legacy_url" in group.columns
                        else 0,
                        "legacy_urls_sample": joined_unique_column(group, "legacy_url"),
                        "manual_search_evidence": joined_unique_column(group, "comments", limit=2),
                        "programmatic_fix_needed": "",
                        "next_pipeline_action": joined_unique_column(group, "next_batch_action", limit=4),
                    }
                )
            roots = pd.concat([roots, pd.DataFrame(rows)], ignore_index=True, sort=False)
    for column in SOURCE_ROOT_COLUMNS:
        if column not in roots.columns:
            roots[column] = ""
    return roots.sort_values(["institution_name", "unitid"])


def first_nonempty_column(frame: pd.DataFrame, column: str) -> str:
    if column not in frame.columns:
        return ""
    for value in frame[column]:
        text = clean_text(value)
        if text:
            return text
    return ""


def joined_unique_column(frame: pd.DataFrame, column: str, *, limit: int = 3) -> str:
    if column not in frame.columns:
        return ""
    values = []
    for value in frame[column]:
        text = clean_text(value)
        if text and text not in values:
            values.append(text)
    return "; ".join(values[:limit])


def write_summary(repo_root: Path, packet_path: Path, audit: pd.DataFrame, spotcheck: pd.DataFrame) -> Path:
    output = repo_root / REVIEW_PACKET_SUMMARY_OUTPUT
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Phase 3 Catalog Discovery Review Packet",
        "",
        f"Generated at: {utc_now()}",
        "",
        f"Workbook: `{packet_path}`",
        "",
        "## Counts",
        "",
        f"- institutions: {spotcheck['unitid'].nunique()}",
        f"- institution-year rows: {len(spotcheck)}",
        "",
        "## Audit Status",
        "",
    ]
    for status, count in audit["audit_status"].value_counts().sort_index().items():
        lines.append(f"- {status}: {int(count)}")
    lines.extend(
        [
            "",
            "## Navigation",
            "",
            "- `START_HERE`: how to use the packet.",
            "- `institution_summary`: one row per institution.",
            "- `nonpass_explanations`: plain-language reasons for partial/non-pass cases.",
            "- `year_panel_review`: compact year-by-year URL panel.",
            "- `raw_full_mockup`: original detailed review sheet retained for auditability.",
        ]
    )
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def run(repo_root: Path) -> tuple[Path, Path]:
    repo_root = repo_root.resolve()
    spotcheck, audit, manual = read_inputs(repo_root)
    packet_path = repo_root / REVIEW_PACKET_OUTPUT
    packet_path.parent.mkdir(parents=True, exist_ok=True)

    institution_summary = build_institution_summary(audit, spotcheck)
    recent_summary = build_recent_summary(audit)
    recent_rows = spotcheck.loc[spotcheck["unitid"].isin(RECENT_EXPANSION_UNITIDS)].copy()
    nonpass = build_nonpass_table(audit, spotcheck)
    year_panel = build_year_panel_review(spotcheck)
    source_roots = build_source_roots(manual, audit, spotcheck)

    with pd.ExcelWriter(packet_path, engine="openpyxl") as writer:
        build_start_here(audit, spotcheck).to_excel(writer, sheet_name="START_HERE", index=False)
        institution_summary.to_excel(writer, sheet_name="institution_summary", index=False)
        recent_summary.to_excel(writer, sheet_name="recent_additions_summary", index=False)
        recent_rows.to_excel(writer, sheet_name="recent_additions", index=False)
        nonpass.to_excel(writer, sheet_name="nonpass_explanations", index=False)
        year_panel.to_excel(writer, sheet_name="year_panel_review", index=False)
        source_roots.to_excel(writer, sheet_name="source_roots", index=False)
        audit.to_excel(writer, sheet_name="audit_details", index=False)
        spotcheck.to_excel(writer, sheet_name="raw_full_mockup", index=False)

    format_workbook(packet_path)
    summary_path = write_summary(repo_root, packet_path, audit, spotcheck)
    return packet_path, summary_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = args.repo_root or repo_root_from_cwd()
    packet_path, summary_path = run(repo_root)
    print(f"review_packet: {packet_path}")
    print(f"summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
