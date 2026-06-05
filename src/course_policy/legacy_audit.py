"""Read-only audit utilities for legacy course repetition workbooks."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd


TARGET_START_YEAR = 2000
TARGET_END_YEAR = 2020

PUBLIC_WORKBOOK = Path("Ipeds raw Data files/Course repetition data.xlsx")
PRIVATE_WORKBOOK = Path("Stata Files/Data/gfprivatelist.xlsx")

INTERIM_DIR = Path("data_policy_pipeline/interim")
REVIEW_DIR = Path("data_policy_pipeline/review")
LOG_DIR = Path("data_policy_pipeline/logs")

ALLOWED_THRESHOLDS = {
    "F",
    "D-",
    "D",
    "D+",
    "C-",
    "C",
    "C+",
    "B-",
    "B",
    "B+",
    "A-",
    "A",
    "A+",
    "ANY",
    "UNKNOWN",
}

POLICY_CODE_COLUMNS = ("grade_averaging", "grade_forgiveness")
THRESHOLD_COLUMNS = ("grade_avg_threshold", "grade_forgive_threshold")

COLUMN_ALIASES = {
    "unitid": ["unitid"],
    "institution_name": ["institution name", "instnm"],
    "grade_averaging": ["repetition (grade averaging)"],
    "grade_avg_threshold": ["grade_rep"],
    "grade_forgiveness": ["forgiveness"],
    "grade_forgive_threshold": ["grade_forgive"],
    "start_year": ["start_year", "start_yr"],
    "bulletin_url": ["bulletin"],
    "evidence_text": ["notes", "excerpt"],
    "comments": ["comments", "notes "],
    "student": ["student"],
    "page_number": ["page_number"],
    "parent_url": ["parent_url"],
    "score": ["score"],
    "have_rep_policy": ["havereppolicy"],
    "have_forgive_policy": ["haveforgivepolicy"],
    "year_rep": ["yearrep"],
    "year_forgive": ["yearforgive"],
    "current_rep": ["currentrep"],
    "current_forgive": ["currentforg"],
    "change_year": ["change year "],
    "earliest_bulletin": ["earliest bulletin"],
    "current_bulletin": ["current bulletin"],
    "classified": ["classified?"],
}

POLICY_LIKE_COLUMNS = {
    "unitid",
    "institution_name",
    "grade_averaging",
    "grade_forgiveness",
    "start_year",
    "bulletin_url",
}

STUDENT_NOTE_PATTERNS = (
    r"\bsame policy\b",
    r"\bcurrent policy\b",
    r"\bcould not\b",
    r"\bcouldn't\b",
    r"\bcan't find\b",
    r"\bno catalog\b",
    r"\bnot found\b",
    r"\bno mention\b",
    r"\bi found\b",
    r"\baccording to\b",
    r"\blooks like\b",
    r"\bseems\b",
    r"\bemailed\b",
    r"\bwebsite\b",
    r"\burl\b",
)


@dataclass(frozen=True)
class WorkbookSpec:
    label: str
    path: Path
    output_name: str


def normalize_column_name(value: object) -> str:
    """Normalize an Excel column name for alias matching."""
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).strip().lower())


def clean_cell(value: object) -> object:
    if pd.isna(value):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def normalize_threshold(value: object) -> str:
    text = str(clean_cell(value)).strip()
    if not text:
        return ""
    upper = text.upper().replace(" ", "")
    if upper in {"ANY", "UNKNOWN"}:
        return upper
    return upper


def is_missing(value: object) -> bool:
    text = str(clean_cell(value)).strip()
    return text == "" or text.lower() in {"nan", "none", "null"}


def parse_year(value: object) -> int | None:
    text = str(clean_cell(value))
    if not text:
        return None
    match = re.search(r"(19|20)\d{2}", text)
    if not match:
        return None
    return int(match.group(0))


def normalize_policy_code(value: object) -> str:
    text = str(clean_cell(value)).strip().lower()
    if text in {"", "nan", "none"}:
        return ""
    if text in {"0", "0.0", "no", "false", "n"}:
        return "0"
    if text in {"1", "1.0", "yes", "true", "y"}:
        return "1"
    return str(clean_cell(value)).strip()


def workbook_file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def alias_map(columns: Iterable[object]) -> dict[str, str]:
    originals = [str(col) for col in columns]
    raw_lower_to_original: dict[str, str] = {}
    normalized_to_original: dict[str, str] = {}
    for original in originals:
        raw_lower_to_original.setdefault(original.lower(), original)
        normalized_to_original.setdefault(normalize_column_name(original), original)

    mapped: dict[str, str] = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            original = raw_lower_to_original.get(alias.lower())
            if original is None:
                original = normalized_to_original.get(normalize_column_name(alias))
            if original is not None:
                mapped[canonical] = original
                break
    return mapped


def canonicalize_sheet(df: pd.DataFrame, workbook_label: str, sheet_name: str) -> pd.DataFrame:
    mapped = alias_map(df.columns)
    out = pd.DataFrame(index=df.index)

    out["workbook"] = workbook_label
    out["sheet_name"] = sheet_name
    out["excel_row"] = df.index + 2

    for canonical in COLUMN_ALIASES:
        source = mapped.get(canonical)
        out[canonical] = df[source].map(clean_cell) if source else ""

    out["available_columns"] = "; ".join(str(col) for col in df.columns if not str(col).startswith("Unnamed:"))
    out["mapped_columns_json"] = json.dumps(mapped, sort_keys=True)
    out["has_policy_like_columns"] = POLICY_LIKE_COLUMNS.issubset(set(mapped))
    return out


def flag_likely_student_note(text: object) -> bool:
    cleaned = str(clean_cell(text))
    if not cleaned:
        return False
    lower = cleaned.lower()
    if len(cleaned) < 80:
        return True
    return any(re.search(pattern, lower) for pattern in STUDENT_NOTE_PATTERNS)


def add_row_flags(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    out["parsed_start_year"] = out["start_year"].map(parse_year)
    out["missing_start_year"] = out["parsed_start_year"].isna()
    out["start_year_outside_2000_2020"] = out["parsed_start_year"].notna() & (
        (out["parsed_start_year"] < TARGET_START_YEAR) | (out["parsed_start_year"] > TARGET_END_YEAR)
    )
    out["missing_bulletin_url"] = out["bulletin_url"].map(is_missing)
    out["missing_evidence_text"] = out["evidence_text"].map(is_missing)
    out["likely_student_note"] = out["evidence_text"].map(flag_likely_student_note)

    for col in POLICY_CODE_COLUMNS:
        normalized = out[col].map(normalize_policy_code)
        out[f"{col}_normalized"] = normalized
        out[f"malformed_{col}"] = ~normalized.isin({"", "0", "1"})

    for col in THRESHOLD_COLUMNS:
        normalized = out[col].map(normalize_threshold)
        out[f"{col}_normalized"] = normalized
        out[f"{col}_is_any"] = normalized.eq("ANY")
        out[f"{col}_is_unknown"] = normalized.eq("UNKNOWN")
        out[f"malformed_{col}"] = (normalized != "") & ~normalized.isin(ALLOWED_THRESHOLDS)

    out["unitid_year_key"] = (
        out["unitid"].astype(str).str.strip()
        + "|"
        + out["parsed_start_year"].fillna(-1).astype(int).astype(str)
    )
    key_is_usable = ~out["unitid"].map(is_missing) & out["parsed_start_year"].notna()
    out["duplicate_institution_year"] = False
    out.loc[key_is_usable, "duplicate_institution_year"] = out.loc[key_is_usable].duplicated(
        ["unitid", "parsed_start_year"], keep=False
    )

    policy_signature_cols = [
        "grade_averaging_normalized",
        "grade_avg_threshold_normalized",
        "grade_forgiveness_normalized",
        "grade_forgive_threshold_normalized",
    ]
    signature_counts = (
        out.loc[key_is_usable]
        .groupby(["unitid", "parsed_start_year"], dropna=False)[policy_signature_cols]
        .nunique(dropna=False)
        .max(axis=1)
    )
    conflicting_keys = set(signature_counts[signature_counts > 1].index)
    out["conflicting_duplicate_institution_year"] = [
        bool((row.unitid, row.parsed_start_year) in conflicting_keys) if pd.notna(row.parsed_start_year) else False
        for row in out.itertuples()
    ]

    flag_columns = [
        "missing_start_year",
        "start_year_outside_2000_2020",
        "missing_bulletin_url",
        "missing_evidence_text",
        "likely_student_note",
        "malformed_grade_averaging",
        "malformed_grade_forgiveness",
        "malformed_grade_avg_threshold",
        "malformed_grade_forgive_threshold",
        "duplicate_institution_year",
        "conflicting_duplicate_institution_year",
    ]
    out["needs_review"] = out[flag_columns].any(axis=1)
    out["review_reasons"] = out.apply(lambda row: "; ".join(col for col in flag_columns if bool(row[col])), axis=1)
    return out


def read_workbook_audit(spec: WorkbookSpec, root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    workbook_path = root / spec.path
    excel = pd.ExcelFile(workbook_path)
    rows: list[pd.DataFrame] = []
    sheet_summaries: list[dict[str, object]] = []

    for sheet_name in excel.sheet_names:
        raw = pd.read_excel(workbook_path, sheet_name=sheet_name, dtype=object)
        raw = raw.dropna(how="all")
        canonical = canonicalize_sheet(raw, spec.label, sheet_name)
        is_policy_sheet = bool(canonical["has_policy_like_columns"].any())
        if is_policy_sheet:
            rows.append(canonical)
        mapped = alias_map(raw.columns)
        sheet_summaries.append(
            {
                "workbook": spec.label,
                "workbook_path": str(spec.path),
                "sheet_name": sheet_name,
                "rows": len(raw),
                "columns": raw.shape[1],
                "is_policy_like_sheet": is_policy_sheet,
                "mapped_columns_json": json.dumps(mapped, sort_keys=True),
                "unmapped_columns": "; ".join(
                    str(col)
                    for col in raw.columns
                    if not str(col).startswith("Unnamed:")
                    and str(col) not in set(mapped.values())
                ),
            }
        )

    if rows:
        audited = add_row_flags(pd.concat(rows, ignore_index=True))
    else:
        audited = pd.DataFrame()
    return audited, pd.DataFrame(sheet_summaries)


def summarize_audit(df: pd.DataFrame, sheet_summary: pd.DataFrame) -> dict[str, object]:
    if df.empty:
        return {
            "policy_rows": 0,
            "policy_like_sheets": int(sheet_summary["is_policy_like_sheet"].sum()),
        }

    summary: dict[str, object] = {
        "policy_rows": int(len(df)),
        "policy_like_sheets": int(sheet_summary["is_policy_like_sheet"].sum()),
        "unique_unitids": int(df.loc[~df["unitid"].map(is_missing), "unitid"].nunique()),
        "needs_review_rows": int(df["needs_review"].sum()),
    }
    count_cols = [
        "missing_bulletin_url",
        "missing_evidence_text",
        "likely_student_note",
        "missing_start_year",
        "start_year_outside_2000_2020",
        "malformed_grade_averaging",
        "malformed_grade_forgiveness",
        "malformed_grade_avg_threshold",
        "malformed_grade_forgive_threshold",
        "duplicate_institution_year",
        "conflicting_duplicate_institution_year",
        "grade_avg_threshold_is_any",
        "grade_avg_threshold_is_unknown",
        "grade_forgive_threshold_is_any",
        "grade_forgive_threshold_is_unknown",
    ]
    for col in count_cols:
        summary[col] = int(df[col].sum())
    return summary


def write_review_workbook(
    public_audit: pd.DataFrame,
    private_audit: pd.DataFrame,
    sheet_summary: pd.DataFrame,
    summaries: list[dict[str, object]],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        pd.DataFrame(summaries).to_excel(writer, sheet_name="summary", index=False)
        sheet_summary.to_excel(writer, sheet_name="sheet_inventory", index=False)
        public_audit.loc[public_audit["needs_review"]].to_excel(
            writer, sheet_name="public_review_flags", index=False
        )
        private_audit.loc[private_audit["needs_review"]].to_excel(
            writer, sheet_name="private_review_flags", index=False
        )
        public_audit.head(250).to_excel(writer, sheet_name="public_sample", index=False)
        private_audit.head(250).to_excel(writer, sheet_name="private_sample", index=False)


def write_summary_report(
    root: Path,
    specs: list[WorkbookSpec],
    summaries: list[dict[str, object]],
    sheet_summary: pd.DataFrame,
    output_path: Path,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    lines = [
        "# Legacy Workbook Audit",
        "",
        f"Generated at: {now}",
        "",
        "## Inputs",
        "",
    ]
    for spec in specs:
        path = root / spec.path
        lines.extend(
            [
                f"- {spec.label}: `{spec.path}`",
                f"  - SHA256: `{workbook_file_hash(path)}`",
            ]
        )

    lines.extend(["", "## Workbook Summary", ""])
    for summary in summaries:
        label = summary["workbook"]
        lines.extend(
            [
                f"### {label}",
                "",
                f"- Policy rows audited: {summary['policy_rows']}",
                f"- Policy-like sheets: {summary['policy_like_sheets']}",
                f"- Unique unitids: {summary.get('unique_unitids', 0)}",
                f"- Rows flagged for review: {summary.get('needs_review_rows', 0)}",
                f"- Missing URLs: {summary.get('missing_bulletin_url', 0)}",
                f"- Missing evidence excerpts/notes: {summary.get('missing_evidence_text', 0)}",
                f"- Likely student notes: {summary.get('likely_student_note', 0)}",
                f"- Start years outside 2000-2020: {summary.get('start_year_outside_2000_2020', 0)}",
                f"- Duplicate institution-year rows: {summary.get('duplicate_institution_year', 0)}",
                f"- Conflicting duplicate institution-year rows: {summary.get('conflicting_duplicate_institution_year', 0)}",
                f"- `Any` thresholds: avg={summary.get('grade_avg_threshold_is_any', 0)}, "
                f"forgive={summary.get('grade_forgive_threshold_is_any', 0)}",
                f"- `Unknown` thresholds: avg={summary.get('grade_avg_threshold_is_unknown', 0)}, "
                f"forgive={summary.get('grade_forgive_threshold_is_unknown', 0)}",
                "",
            ]
        )

    lines.extend(["## Sheet Inventory", ""])
    for row in sheet_summary.itertuples(index=False):
        lines.append(
            f"- {row.workbook} / {row.sheet_name}: {row.rows} rows, {row.columns} columns, "
            f"policy-like={row.is_policy_like_sheet}"
        )

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- This audit reads the original Excel files but does not modify them.",
            "- `likely_student_note` is a heuristic flag for short text or wording that sounds like a collector note.",
            "- `Unknown` and `Any` thresholds are counted separately for downstream protocol review.",
            "",
        ]
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


def run_legacy_audit(root: Path) -> dict[str, Path]:
    specs = [
        WorkbookSpec("public", PUBLIC_WORKBOOK, "legacy_public_audit.csv"),
        WorkbookSpec("private", PRIVATE_WORKBOOK, "legacy_private_audit.csv"),
    ]

    interim_dir = root / INTERIM_DIR
    review_dir = root / REVIEW_DIR
    log_dir = root / LOG_DIR
    for directory in (interim_dir, review_dir, log_dir):
        directory.mkdir(parents=True, exist_ok=True)

    audits: dict[str, pd.DataFrame] = {}
    sheet_summaries: list[pd.DataFrame] = []
    summaries: list[dict[str, object]] = []

    for spec in specs:
        audit, sheet_summary = read_workbook_audit(spec, root)
        output_path = interim_dir / spec.output_name
        audit.to_csv(output_path, index=False)
        audits[spec.label] = audit
        sheet_summaries.append(sheet_summary)
        summary = summarize_audit(audit, sheet_summary)
        summary["workbook"] = spec.label
        summaries.append(summary)

    combined_sheet_summary = pd.concat(sheet_summaries, ignore_index=True)
    review_workbook = review_dir / "legacy_audit_review.xlsx"
    write_review_workbook(
        audits["public"],
        audits["private"],
        combined_sheet_summary,
        summaries,
        review_workbook,
    )

    summary_report = log_dir / "legacy_workbook_audit_summary.md"
    write_summary_report(root, specs, summaries, combined_sheet_summary, summary_report)

    return {
        "public_audit": interim_dir / "legacy_public_audit.csv",
        "private_audit": interim_dir / "legacy_private_audit.csv",
        "review_workbook": review_workbook,
        "summary_report": summary_report,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit legacy course repetition policy workbooks.")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Project root containing policy_pipeline and data_policy_pipeline.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    outputs = run_legacy_audit(args.root.resolve())
    for label, path in outputs.items():
        print(f"{label}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
