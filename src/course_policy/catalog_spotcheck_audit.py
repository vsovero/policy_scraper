"""Audit the Phase 3 catalog URL spot-check workbook before review."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

from .ai_config import repo_root_from_cwd
from .batch3_discovery import is_wrong_scope_catalog_url
from .spotcheck_workbook import SPOTCHECK_WORKBOOK_OUTPUT


DATA_DIR = Path("../data_policy_pipeline")
REVIEW_DIR = DATA_DIR / "review"
LOG_DIR = DATA_DIR / "logs"

SPOTCHECK_AUDIT_OUTPUT = REVIEW_DIR / "catalog_url_spotcheck_audit.csv"
SPOTCHECK_AUDIT_SUMMARY_OUTPUT = LOG_DIR / "catalog_url_spotcheck_audit_summary.md"

TARGET_START_YEAR = 2000
TARGET_END_YEAR = 2020
TARGET_YEARS = list(range(TARGET_START_YEAR, TARGET_END_YEAR + 1))

ACCEPTED_BOUND_REASONS = {
    "official_archive_lower_bound_reached",
    "official_archive_upper_bound_reached",
}
ACCEPTED_DEAD_END_REASONS = {
    "catalog_dead_end_wrong_scope",
    "wrong_scope",
}
ACCEPTED_GAP_REASONS = {
    "direct_pdf_pattern_unresolved",
    "secondary_archive_access_blocked",
    "verified_source_gap",
}
OCR_STATUSES = ("ocr", "visual_review")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def nonempty(value: object) -> bool:
    return clean_text(value) != ""


def year_list(values: list[int] | set[int]) -> str:
    return "; ".join(str(value) for value in sorted(set(values)))


def parse_year(value: object) -> int:
    text = clean_text(value)
    if not text:
        return 0
    try:
        return int(float(text))
    except ValueError:
        return 0


def url_host(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc.lower()


def is_wrong_scope_best_url(url: str) -> bool:
    lowered = clean_text(url).lower()
    if not lowered:
        return False
    if "undergraduate" in lowered or "undergrad" in lowered or "ugrad" in lowered:
        return False
    if "general_and_graduate" in lowered or "general catalog" in lowered or "general-and-graduate" in lowered:
        return False
    return is_wrong_scope_catalog_url(lowered)


def read_spotcheck_workbook(repo_root: Path) -> pd.DataFrame:
    path = repo_root / SPOTCHECK_WORKBOOK_OUTPUT
    return pd.read_excel(path, sheet_name="spotcheck_mockup")


def manual_span_years(group: pd.DataFrame) -> set[int]:
    start = parse_year(group["manual_coverage_start_year"].iloc[0])
    end = parse_year(group["manual_coverage_end_year"].iloc[0])
    status = clean_text(group["manual_status"].iloc[0]).lower()
    if start <= 0 or end <= 0 or "scope_dead_end" in status or "catalog_dead_end" in status:
        return set()
    return {year for year in TARGET_YEARS if start <= year <= end}


def audit_institution(group: pd.DataFrame) -> dict[str, object]:
    group = group.sort_values("start_year").copy()
    unitid = int(group["unitid"].iloc[0])
    institution_name = clean_text(group["institution_name"].iloc[0])
    manual_status = clean_text(group["manual_status"].iloc[0])
    manual_root = clean_text(group["manual_best_root_url"].iloc[0])
    manual_start = parse_year(group["manual_coverage_start_year"].iloc[0])
    manual_end = parse_year(group["manual_coverage_end_year"].iloc[0])

    best_mask = group["best_url"].map(nonempty)
    legacy_mask = group["legacy_url"].map(nonempty)
    best_years = set(group.loc[best_mask, "start_year"].astype(int))
    legacy_years = set(group.loc[legacy_mask, "start_year"].astype(int))
    accepted_gap_years = set(
        group.loc[group["stop_reason"].fillna("").astype(str).isin(ACCEPTED_GAP_REASONS), "start_year"].astype(int)
    )
    accepted_bound_years = set(
        group.loc[group["stop_reason"].fillna("").astype(str).isin(ACCEPTED_BOUND_REASONS), "start_year"].astype(int)
    )
    missing_best_years = set(TARGET_YEARS) - best_years
    span_years = manual_span_years(group)
    span_missing = span_years - best_years - accepted_gap_years

    pipeline_issues: list[str] = []
    ocr_issues: list[str] = []
    accepted_stops: list[str] = []
    warnings: list[str] = []

    manual_status_lower = manual_status.lower()
    stop_reasons = {clean_text(value) for value in group["stop_reason"].fillna("") if clean_text(value)}

    if any(token in manual_status_lower for token in OCR_STATUSES):
        ocr_issues.append("candidate_urls_need_ocr_or_visual_confirmation")

    if "catalog_dead_end" in manual_status_lower:
        accepted_stops.append("catalog_dead_end_wrong_scope")
    if "scope_dead_end" in manual_status_lower:
        accepted_stops.append("scope_dead_end")

    if manual_start > TARGET_END_YEAR and legacy_years:
        pipeline_issues.append("reviewed_root_starts_after_panel_despite_legacy_urls")

    if span_missing and not accepted_stops:
        pipeline_issues.append("missing_years_inside_reviewed_manual_span")

    if legacy_years:
        interior_legacy_years = {
            year
            for year in range(min(legacy_years), max(legacy_years) + 1)
            if TARGET_START_YEAR <= year <= TARGET_END_YEAR
        }
        missing_between_legacy = interior_legacy_years - best_years - accepted_gap_years
        if missing_between_legacy and not accepted_stops:
            pipeline_issues.append("missing_years_between_legacy_url_years")
    else:
        missing_between_legacy = set()

    wrong_scope_years = set(
        group.loc[group["best_url"].map(is_wrong_scope_best_url), "start_year"].astype(int)
    )
    if wrong_scope_years:
        pipeline_issues.append("wrong_scope_best_urls")

    malformed_url_years = set(
        group.loc[
            group["best_url"].fillna("").astype(str).str.contains("web.archive.org/web/[^/]+/https:/[^/]", regex=True),
            "start_year",
        ].astype(int)
    )
    if malformed_url_years:
        pipeline_issues.append("malformed_wayback_best_urls")

    if accepted_gap_years:
        accepted_stops.append("row_level_verified_source_gaps")

    if missing_best_years and not accepted_stops and not span_years:
        nonempty_stop_reasons = stop_reasons - ACCEPTED_BOUND_REASONS - ACCEPTED_DEAD_END_REASONS - ACCEPTED_GAP_REASONS
        if nonempty_stop_reasons or not stop_reasons:
            pipeline_issues.append("unexplained_missing_best_urls")

    if missing_best_years and missing_best_years.issubset(accepted_bound_years) and not pipeline_issues:
        accepted_stops.append("archive_bounds_explain_missing_years")

    best_hosts = {
        url_host(clean_text(url))
        for url in group.loc[best_mask, "best_url"]
        if url_host(clean_text(url))
    }
    if len(best_hosts) > 1:
        warnings.append("multiple_best_url_hosts")

    if pipeline_issues:
        audit_status = "needs_pipeline_fix"
    elif ocr_issues:
        audit_status = "needs_ocr_or_visual_review"
    elif accepted_stops:
        audit_status = "accepted_dead_end_or_archive_bound"
    else:
        audit_status = "pass_basic_checks"

    notes = []
    if span_missing:
        notes.append(f"Missing inside reviewed span: {year_list(span_missing)}")
    if missing_between_legacy:
        notes.append(f"Missing between legacy-url years: {year_list(missing_between_legacy)}")
    if wrong_scope_years:
        notes.append(f"Wrong-scope best URL years: {year_list(wrong_scope_years)}")
    if malformed_url_years:
        notes.append(f"Malformed Wayback URL years: {year_list(malformed_url_years)}")
    if accepted_stops:
        notes.append(f"Accepted stop: {'; '.join(sorted(set(accepted_stops)))}")
    if ocr_issues:
        notes.append("Candidate URLs exist but OCR/visual confirmation is still required.")

    return {
        "unitid": unitid,
        "institution_name": institution_name,
        "audit_status": audit_status,
        "best_url_year_count": len(best_years),
        "legacy_url_year_count": len(legacy_years),
        "missing_best_url_years": year_list(missing_best_years),
        "manual_span_missing_years": year_list(span_missing),
        "missing_between_legacy_url_years": year_list(missing_between_legacy),
        "wrong_scope_best_url_years": year_list(wrong_scope_years),
        "malformed_url_years": year_list(malformed_url_years),
        "pipeline_fix_issues": "; ".join(sorted(set(pipeline_issues))),
        "ocr_or_visual_review_issues": "; ".join(sorted(set(ocr_issues))),
        "accepted_stop_reasons": "; ".join(sorted(set(accepted_stops))),
        "warnings": "; ".join(sorted(set(warnings))),
        "manual_status": manual_status,
        "manual_best_root_url": manual_root,
        "manual_coverage_start_year": manual_start,
        "manual_coverage_end_year": manual_end,
        "audit_note": " | ".join(notes),
        "audited_at": utc_now(),
    }


def build_audit(spotcheck: pd.DataFrame) -> pd.DataFrame:
    audit = pd.DataFrame(
        [audit_institution(group) for _, group in spotcheck.groupby("unitid", sort=False)]
    )
    status_order = {
        "needs_pipeline_fix": 0,
        "needs_ocr_or_visual_review": 1,
        "accepted_dead_end_or_archive_bound": 2,
        "pass_basic_checks": 3,
    }
    audit["_status_order"] = audit["audit_status"].map(status_order).fillna(9)
    return audit.sort_values(["_status_order", "institution_name"]).drop(columns=["_status_order"])


def write_summary(path: Path, audit: pd.DataFrame, workbook_path: Path, audit_path: Path) -> None:
    lines = [
        "# Catalog URL Spot-Check Audit",
        "",
        f"Audited at: {utc_now()}",
        "",
        f"Workbook audited: `{workbook_path}`",
        f"Audit table: `{audit_path}`",
        "",
        "## Status Counts",
        "",
    ]
    for status, count in audit["audit_status"].value_counts().sort_index().items():
        lines.append(f"- {status}: {int(count)}")
    lines.extend(["", "## Pipeline Fix Issues", ""])
    issue_counts: dict[str, int] = {}
    for value in audit["pipeline_fix_issues"]:
        for issue in clean_text(value).split("; "):
            if issue:
                issue_counts[issue] = issue_counts.get(issue, 0) + 1
    if issue_counts:
        for issue, count in sorted(issue_counts.items()):
            lines.append(f"- {issue}: {count}")
    else:
        lines.append("- none")
    lines.extend(["", "## Institutions Requiring Pipeline Fixes", ""])
    fix_rows = audit.loc[audit["audit_status"].eq("needs_pipeline_fix")]
    if fix_rows.empty:
        lines.append("- none")
    else:
        for _, row in fix_rows.iterrows():
            lines.append(
                f"- {row['institution_name']} ({row['unitid']}): {row['pipeline_fix_issues']}."
            )
    lines.extend(["", "## Notes", ""])
    lines.append("- This audit is a gate: do not describe the workbook as review-ready until this file has been regenerated and checked.")
    lines.append("- OCR/visual-review rows are not manual troubleshooting requests; they belong in the OCR pipeline queue.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(repo_root: Path) -> tuple[Path, Path]:
    repo_root = repo_root.resolve()
    workbook_path = repo_root / SPOTCHECK_WORKBOOK_OUTPUT
    spotcheck = read_spotcheck_workbook(repo_root)
    audit = build_audit(spotcheck)
    audit_path = repo_root / SPOTCHECK_AUDIT_OUTPUT
    summary_path = repo_root / SPOTCHECK_AUDIT_SUMMARY_OUTPUT
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(audit_path, index=False)
    write_summary(summary_path, audit, workbook_path, audit_path)
    return audit_path, summary_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=None, help="Path to policy_pipeline repo root.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = args.repo_root or repo_root_from_cwd()
    audit_path, summary_path = run(repo_root)
    print(f"audit: {audit_path}")
    print(f"summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
