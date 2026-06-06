"""Build Excel review mockups for catalog URL spot checks."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from .ai_config import repo_root_from_cwd


DATA_DIR = Path("../data_policy_pipeline")
INTERIM_DIR = DATA_DIR / "interim"
REVIEW_DIR = DATA_DIR / "review"
LOG_DIR = DATA_DIR / "logs"

LEGACY_EVIDENCE_LINKS_INPUT = INTERIM_DIR / "legacy_evidence_links.csv"
STAGE_STATUS_INPUTS = (
    INTERIM_DIR / "catalog_batch2_stage_status.csv",
    INTERIM_DIR / "catalog_batch3_stage_status.csv",
    INTERIM_DIR / "catalog_batch4_stage_status.csv",
)
UAH_LOUIS_AUDIT_INPUT = REVIEW_DIR / "uah_louis_catalog_year_audit.csv"

SPOTCHECK_WORKBOOK_OUTPUT = REVIEW_DIR / "catalog_url_spotcheck_mockup.xlsx"
SPOTCHECK_SUMMARY_OUTPUT = LOG_DIR / "catalog_url_spotcheck_mockup_summary.md"


MOCKUP_COLUMNS = [
    "unitid",
    "institution_name",
    "grade_averaging",
    "grade_avg_threshold",
    "grade_forgiveness",
    "grade_forgive_threshold",
    "start_year",
    "best_url",
    "legacy_url",
    "evidence_text",
    "comments",
    "best_url_source",
    "best_url_status",
    "legacy_url_count",
    "catalog_title_or_link_text",
    "pipeline_stage",
    "stop_reason",
    "next_batch_action",
    "preferred_source_root_url",
    "archive_url",
    "retrieval_status",
    "source_retrieved",
    "legacy_workbook",
    "legacy_excel_rows",
    "legacy_review_reasons",
    "legacy_excerpt",
    "stage_explanation",
    "review_note",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def first_nonempty(values: pd.Series) -> str:
    for value in values:
        text = clean_text(value)
        if text:
            return text
    return ""


def joined_unique(values: pd.Series, *, limit: int = 3) -> str:
    out: list[str] = []
    for value in values:
        text = clean_text(value)
        if text and text not in out:
            out.append(text)
    return "; ".join(out[:limit])


def read_stage_status(repo_root: Path) -> pd.DataFrame:
    frames = []
    for path in STAGE_STATUS_INPUTS:
        full_path = repo_root / path
        if not full_path.exists():
            continue
        frame = pd.read_csv(full_path, low_memory=False)
        frame["discovery_batch"] = path.name.replace("catalog_", "").replace("_stage_status.csv", "")
        frames.append(frame)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def read_legacy_links(repo_root: Path) -> pd.DataFrame:
    path = repo_root / LEGACY_EVIDENCE_LINKS_INPUT
    legacy = pd.read_csv(path, low_memory=False)
    legacy["legacy_url"] = legacy["legacy_url"].map(clean_text)
    legacy = legacy.loc[legacy["legacy_workbook"].eq("public")].copy()
    grouped = (
        legacy.sort_values(["unitid", "target_year", "selected_as_prior_evidence", "legacy_source_priority"], ascending=[True, True, False, True])
        .groupby(["unitid", "target_year"], as_index=False)
        .agg(
            legacy_url=("legacy_url", joined_unique),
            legacy_url_count=("legacy_url", lambda values: int(values.map(clean_text).ne("").sum())),
            legacy_workbook=("legacy_workbook", joined_unique),
            legacy_excel_rows=("legacy_excel_row", lambda values: joined_unique(values.astype(str), limit=8)),
            grade_averaging=("grade_averaging", first_nonempty),
            grade_avg_threshold=("grade_avg_threshold", first_nonempty),
            grade_forgiveness=("grade_forgiveness", first_nonempty),
            grade_forgive_threshold=("grade_forgive_threshold", first_nonempty),
            legacy_policy_class=("legacy_policy_class", first_nonempty),
            legacy_review_reasons=("legacy_review_reasons", joined_unique),
            legacy_excerpt=("legacy_excerpt", first_nonempty),
        )
    )
    return grouped


def best_url_for_row(row: pd.Series) -> tuple[str, str, str, str]:
    candidate_url = clean_text(row.get("candidate_url", ""))
    retrieved_url = clean_text(row.get("retrieved_candidate_url", ""))
    policy_page_url = clean_text(row.get("legacy_policy_page_url", ""))
    legacy_url = clean_text(row.get("legacy_url", ""))
    candidate_title = clean_text(row.get("candidate_link_text", "")) or clean_text(row.get("retrieved_candidate_link_text", ""))

    if candidate_url:
        return candidate_url, "preferred_or_secondary_archive_candidate", clean_text(row.get("retrieval_status", "")), candidate_title
    if retrieved_url:
        return retrieved_url, clean_text(row.get("retrieved_candidate_method", "")) or "retrieved_fallback_candidate", clean_text(row.get("retrieval_status", "")), candidate_title
    if policy_page_url:
        return policy_page_url, "legacy_policy_page_deferred", "policy_dating_needed", clean_text(row.get("retrieved_candidate_link_text", ""))
    if legacy_url:
        return legacy_url, "legacy_url_only", "not_checked_in_current_stage", ""
    return "", "", "", ""


def apply_uah_louis_override(repo_root: Path, mockup: pd.DataFrame) -> pd.DataFrame:
    path = repo_root / UAH_LOUIS_AUDIT_INPUT
    if not path.exists() or mockup.empty:
        return mockup
    audit = pd.read_csv(path, low_memory=False)
    if audit.empty:
        return mockup
    audit["unitid"] = audit["unitid"].fillna(100706).astype(int)
    audit["institution_name"] = audit["institution_name"].fillna("University of Alabama in Huntsville")
    audit["target_year"] = audit["target_year"].astype(int)
    lookup = audit.set_index(["unitid", "target_year"])
    out = mockup.copy()
    for idx, row in out.iterrows():
        key = (int(row["unitid"]), int(row["start_year"]))
        if key not in lookup.index:
            continue
        hit = lookup.loc[key]
        if clean_text(hit["status"]) == "candidate_found_in_louis":
            out.at[idx, "best_url"] = clean_text(hit["candidate_url"])
            out.at[idx, "best_url_source"] = "reviewed_louis_archive_candidate"
            out.at[idx, "best_url_status"] = clean_text(hit["status"])
            out.at[idx, "catalog_title_or_link_text"] = clean_text(hit["candidate_link_text"])
            out.at[idx, "archive_url"] = clean_text(hit["louis_collection_url"])
            out.at[idx, "stop_reason"] = "candidate_found_in_review_audit"
            out.at[idx, "next_batch_action"] = "retrieve_or_extract_candidate"
            out.at[idx, "review_note"] = "Best URL updated from reviewed UAH LOUIS archive audit."
        else:
            out.at[idx, "best_url_status"] = clean_text(hit["status"])
            out.at[idx, "archive_url"] = clean_text(hit["louis_collection_url"])
            out.at[idx, "stop_reason"] = "interior_archive_gap"
            out.at[idx, "next_batch_action"] = "targeted_archive_gap_search"
            out.at[idx, "review_note"] = clean_text(hit["note"])
    return out


def build_mockup(repo_root: Path) -> pd.DataFrame:
    stage = read_stage_status(repo_root)
    legacy = read_legacy_links(repo_root)
    if stage.empty:
        rows = legacy.rename(columns={"target_year": "start_year"}).copy()
        rows["best_url"] = rows["legacy_url"]
        rows["best_url_source"] = "legacy_url_only"
        rows["best_url_status"] = "not_checked_in_current_stage"
        rows["catalog_title_or_link_text"] = ""
        rows["review_note"] = "No batch stage-status files were available."
    else:
        rows = stage.merge(legacy, on=["unitid", "target_year"], how="left")
        rows = rows.rename(columns={"target_year": "start_year"})
        best = rows.apply(best_url_for_row, axis=1, result_type="expand")
        best.columns = ["best_url", "best_url_source", "best_url_status", "catalog_title_or_link_text"]
        for column in best.columns:
            rows[column] = best[column]
        rows["review_note"] = ""
    for column in MOCKUP_COLUMNS:
        if column not in rows.columns:
            rows[column] = ""
    rows["evidence_text"] = rows["legacy_excerpt"].map(clean_text)
    rows["comments"] = rows["stage_explanation"].map(clean_text)
    rows = apply_uah_louis_override(repo_root, rows)
    rows = rows[MOCKUP_COLUMNS].sort_values(["institution_name", "start_year", "legacy_url"]).reset_index(drop=True)
    return rows


def summary_rows(mockup: pd.DataFrame) -> pd.DataFrame:
    if mockup.empty:
        return pd.DataFrame([{"metric": "rows", "value": 0}])
    rows = [
        {"metric": "generated_at", "value": utc_now()},
        {"metric": "rows", "value": len(mockup)},
        {"metric": "institution_count", "value": mockup["unitid"].nunique()},
        {"metric": "rows_with_best_url", "value": int(mockup["best_url"].map(clean_text).ne("").sum())},
        {"metric": "rows_with_legacy_url", "value": int(mockup["legacy_url"].map(clean_text).ne("").sum())},
        {"metric": "interior_archive_gap_rows", "value": int(mockup["stop_reason"].eq("interior_archive_gap").sum())},
    ]
    for source, count in mockup["best_url_source"].fillna("").replace("", "missing").value_counts().items():
        rows.append({"metric": f"best_url_source::{source}", "value": int(count)})
    return pd.DataFrame(rows)


def format_workbook(path: Path) -> None:
    from openpyxl import load_workbook

    wb = load_workbook(path)
    header_fill = PatternFill("solid", fgColor="1F4E78")
    header_font = Font(color="FFFFFF", bold=True)
    for ws in wb.worksheets:
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
        for column_cells in ws.columns:
            header = clean_text(column_cells[0].value)
            max_len = max(len(clean_text(cell.value)) for cell in column_cells[:200])
            width = min(max(max_len + 2, len(header) + 2, 10), 70)
            ws.column_dimensions[get_column_letter(column_cells[0].column)].width = width
    wb.save(path)


def write_workbook(repo_root: Path, mockup: pd.DataFrame) -> Path:
    output = repo_root / SPOTCHECK_WORKBOOK_OUTPUT
    output.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        summary_rows(mockup).to_excel(writer, sheet_name="summary", index=False)
        mockup.to_excel(writer, sheet_name="spotcheck_mockup", index=False)
        mockup.loc[mockup["best_url"].map(clean_text).eq("")].to_excel(writer, sheet_name="missing_best_url", index=False)
        mockup.loc[mockup["legacy_url"].map(clean_text).ne("")].to_excel(writer, sheet_name="legacy_comparison", index=False)
    format_workbook(output)
    return output


def write_summary(repo_root: Path, mockup: pd.DataFrame, workbook_path: Path) -> Path:
    output = repo_root / SPOTCHECK_SUMMARY_OUTPUT
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Catalog URL Spot-Check Mockup",
        "",
        f"Generated at: {utc_now()}",
        "",
        f"Workbook: `{workbook_path}`",
        "",
        "## Summary",
        "",
    ]
    for row in summary_rows(mockup).to_dict("records"):
        lines.append(f"- {row['metric']}: {row['value']}")
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def run(repo_root: Path) -> tuple[Path, Path]:
    repo_root = repo_root.resolve()
    mockup = build_mockup(repo_root)
    workbook_path = write_workbook(repo_root, mockup)
    summary_path = write_summary(repo_root, mockup, workbook_path)
    return workbook_path, summary_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=None, help="Path to policy_pipeline repo root.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = args.repo_root or repo_root_from_cwd()
    workbook_path, summary_path = run(repo_root)
    print(f"workbook: {workbook_path}")
    print(f"summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
