"""Build the Phase 2 institution-year universe for policy collection."""

from __future__ import annotations

import argparse
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


TARGET_START_YEAR = 2000
TARGET_END_YEAR = 2020

PANEL_SOURCE = Path("Stata Files/Data/step2_ipeds_universe_with_policy_flags.dta")
OTHER_PANEL_CANDIDATES = (
    Path("Stata Files/Data/analysis_panel_events.dta"),
    Path("Stata Files/Data/mainpanelgf.dta"),
    Path("Stata Files/Data/mainpanelgf_clean.dta"),
    Path("Stata Files/Data/hdpanelgf.dta"),
    Path("Stata Files/Data/gfdatafull.dta"),
)

INTERIM_DIR = Path("data_policy_pipeline/interim")
LOG_DIR = Path("data_policy_pipeline/logs")

LEGACY_AUDIT_FILES = {
    "public": Path("data_policy_pipeline/interim/legacy_public_audit.csv"),
    "private": Path("data_policy_pipeline/interim/legacy_private_audit.csv"),
}

PANEL_COLUMNS = [
    "unitid",
    "year",
    "instnm",
    "stabbr",
    "sector",
    "control",
    "iclevel",
    "webaddr",
    "public_inst",
    "valid_policy_year",
    "ever_collected",
]

AUDIT_LINK_COLUMNS = [
    "workbook",
    "sheet_name",
    "excel_row",
    "unitid",
    "institution_name",
    "grade_averaging",
    "grade_avg_threshold",
    "grade_forgiveness",
    "grade_forgive_threshold",
    "grade_averaging_normalized",
    "grade_avg_threshold_normalized",
    "grade_forgiveness_normalized",
    "grade_forgive_threshold_normalized",
    "parsed_start_year",
    "bulletin_url",
    "evidence_text",
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
    "needs_review",
    "review_reasons",
]

REVIEW_FLAG_COLUMNS = [
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
    "needs_review",
]

PRIVATE_SOURCE_PRIORITIES = {
    "private": 10,
    "(Automated, 0121) Missing priva": 40,
    "example": 80,
    "LLM Training Set": 90,
}


@dataclass(frozen=True)
class BuildOutputs:
    institution_universe: Path
    institution_year_targets: Path
    legacy_evidence_links: Path
    summary_report: Path


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clean_unitid(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype("Int64")


def clean_year(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype("Int64")


def read_panel_source(root: Path) -> pd.DataFrame:
    source_path = root / PANEL_SOURCE
    df = pd.read_stata(source_path, columns=PANEL_COLUMNS, convert_categoricals=False)
    df["unitid"] = clean_unitid(df["unitid"])
    df["year"] = clean_year(df["year"])
    df = df[df["year"].between(TARGET_START_YEAR, TARGET_END_YEAR)].copy()
    df = df[df["unitid"].notna()].copy()
    df = df[df["sector"].isin([1, 2])].copy()
    if "iclevel" in df.columns:
        df = df[df["iclevel"].eq(1)].copy()
    return df


def first_nonempty(values: pd.Series) -> str:
    nonempty = values.dropna().astype(str).str.strip()
    nonempty = nonempty[nonempty.ne("")]
    return nonempty.iloc[-1] if not nonempty.empty else ""


def unique_join(values: pd.Series) -> str:
    nonempty = values.dropna().astype(str).str.strip()
    nonempty = nonempty[nonempty.ne("")]
    return "; ".join(sorted(nonempty.unique()))


def add_legacy_universe_flags(universe: pd.DataFrame, audits: pd.DataFrame) -> pd.DataFrame:
    audit_counts = (
        audits.groupby("unitid", dropna=True)
        .agg(
            legacy_row_count=("excel_row", "size"),
            legacy_conflict_count=("conflicting_duplicate_institution_year", "sum"),
            legacy_needs_review=("needs_review", "max"),
            source_in_legacy_public=("workbook", lambda s: bool(s.eq("public").any())),
            source_in_legacy_private=("workbook", lambda s: bool(s.eq("private").any())),
        )
        .reset_index()
    )
    out = universe.merge(audit_counts, on="unitid", how="left")
    out["legacy_row_count"] = out["legacy_row_count"].fillna(0).astype(int)
    out["legacy_conflict_count"] = out["legacy_conflict_count"].fillna(0).astype(int)
    for col in ["source_in_legacy_public", "source_in_legacy_private", "legacy_needs_review"]:
        out[col] = to_bool(out[col])
    return out


def build_institution_universe(panel: pd.DataFrame, audits: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        panel.sort_values(["unitid", "year"])
        .groupby("unitid", dropna=True)
        .agg(
            institution_name=("instnm", first_nonempty),
            state=("stabbr", first_nonempty),
            sector_code=("sector", "last"),
            control_code=("control", "last"),
            iclevel_code=("iclevel", "last"),
            webaddr=("webaddr", first_nonempty),
            ipeds_first_observed_year=("year", "min"),
            ipeds_last_observed_year=("year", "max"),
            active_in_ipeds_panel=("year", "size"),
            ipeds_panel_year_count=("year", "nunique"),
        )
        .reset_index()
    )
    grouped["sector"] = grouped["sector_code"].map({1: "public_4_year", 2: "private_nonprofit_4_year"})
    grouped["control"] = grouped["control_code"].map({1: "public", 2: "private_nonprofit", 3: "private_for_profit"})
    grouped["target_start_year"] = TARGET_START_YEAR
    grouped["target_end_year"] = TARGET_END_YEAR
    grouped["active_in_ipeds_panel"] = grouped["active_in_ipeds_panel"].gt(0)
    grouped["notes"] = ""

    out = add_legacy_universe_flags(grouped, audits)
    columns = [
        "unitid",
        "institution_name",
        "sector",
        "control",
        "state",
        "target_start_year",
        "target_end_year",
        "source_in_legacy_public",
        "source_in_legacy_private",
        "active_in_ipeds_panel",
        "legacy_row_count",
        "legacy_conflict_count",
        "legacy_needs_review",
        "notes",
        "sector_code",
        "control_code",
        "iclevel_code",
        "webaddr",
        "ipeds_first_observed_year",
        "ipeds_last_observed_year",
        "ipeds_panel_year_count",
    ]
    return out[columns].sort_values("unitid")


def read_legacy_audits(root: Path) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for workbook, rel_path in LEGACY_AUDIT_FILES.items():
        path = root / rel_path
        df = pd.read_csv(path, low_memory=False)
        if "workbook" not in df.columns:
            df["workbook"] = workbook
        df = df[[col for col in AUDIT_LINK_COLUMNS if col in df.columns]].copy()
        df["unitid"] = clean_unitid(df["unitid"])
        df["parsed_start_year"] = clean_year(df["parsed_start_year"])
        for col in REVIEW_FLAG_COLUMNS:
            if col in df.columns:
                df[col] = to_bool(df[col])
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def to_bool(series: pd.Series) -> pd.Series:
    text = series.astype("string").fillna("").str.strip().str.lower()
    return text.isin({"true", "1", "yes", "y"})


def source_priority(row: pd.Series) -> int:
    workbook = row.get("legacy_workbook", row.get("workbook", ""))
    sheet_name = row.get("legacy_sheet_name", row.get("sheet_name", ""))
    if workbook == "public":
        return 10
    return PRIVATE_SOURCE_PRIORITIES.get(str(sheet_name), 99)


def policy_signature(df: pd.DataFrame) -> pd.Series:
    signature_cols = [
        "grade_averaging_normalized",
        "grade_avg_threshold_normalized",
        "grade_forgiveness_normalized",
        "grade_forgive_threshold_normalized",
    ]
    parts = []
    for col in signature_cols:
        if col in df.columns:
            parts.append(df[col].fillna("").astype(str).str.strip())
        else:
            parts.append(pd.Series([""] * len(df), index=df.index))
    return parts[0] + "|" + parts[1] + "|" + parts[2] + "|" + parts[3]


def build_legacy_evidence_links(audits: pd.DataFrame, universe: pd.DataFrame) -> pd.DataFrame:
    in_scope_unitids = set(universe["unitid"].dropna().astype(int))
    links = audits[
        audits["unitid"].isin(in_scope_unitids)
        & audits["parsed_start_year"].between(TARGET_START_YEAR, TARGET_END_YEAR)
    ].copy()
    links = links.rename(
        columns={
            "parsed_start_year": "target_year",
            "workbook": "legacy_workbook",
            "sheet_name": "legacy_sheet_name",
            "excel_row": "legacy_excel_row",
            "bulletin_url": "legacy_url",
            "evidence_text": "legacy_excerpt",
            "needs_review": "legacy_needs_review",
            "review_reasons": "legacy_review_reasons",
        }
    )
    links["legacy_source_priority"] = links.apply(source_priority, axis=1)
    links["legacy_policy_class"] = links.apply(classify_legacy_policy, axis=1)
    links["policy_signature"] = policy_signature(
        links.rename(
            columns={
                "legacy_workbook": "workbook",
                "legacy_sheet_name": "sheet_name",
                "target_year": "parsed_start_year",
            }
        )
    )
    links["legacy_link_id"] = range(1, len(links) + 1)
    links["created_at"] = datetime.now(timezone.utc).isoformat()
    links["selected_as_prior_evidence"] = False

    if not links.empty:
        group_cols = ["unitid", "target_year"]
        min_priority = links.groupby(group_cols)["legacy_source_priority"].transform("min")
        clean_top = links["legacy_source_priority"].eq(min_priority) & ~links["legacy_needs_review"]
        top_signature_counts = (
            links[clean_top]
            .groupby(group_cols)["policy_signature"]
            .transform("nunique")
        )
        links.loc[clean_top & top_signature_counts.eq(1), "selected_as_prior_evidence"] = True

    output_columns = [
        "legacy_link_id",
        "unitid",
        "target_year",
        "legacy_workbook",
        "legacy_sheet_name",
        "legacy_excel_row",
        "legacy_source_priority",
        "legacy_url",
        "legacy_excerpt",
        "legacy_policy_class",
        "grade_averaging",
        "grade_avg_threshold",
        "grade_forgiveness",
        "grade_forgive_threshold",
        "grade_averaging_normalized",
        "grade_avg_threshold_normalized",
        "grade_forgiveness_normalized",
        "grade_forgive_threshold_normalized",
        "legacy_needs_review",
        "legacy_review_reasons",
        "missing_bulletin_url",
        "missing_evidence_text",
        "likely_student_note",
        "malformed_grade_averaging",
        "malformed_grade_forgiveness",
        "malformed_grade_avg_threshold",
        "malformed_grade_forgive_threshold",
        "duplicate_institution_year",
        "conflicting_duplicate_institution_year",
        "selected_as_prior_evidence",
        "created_at",
    ]
    return links[[col for col in output_columns if col in links.columns]].sort_values(
        ["unitid", "target_year", "legacy_source_priority", "legacy_workbook", "legacy_excel_row"]
    )


def classify_legacy_policy(row: pd.Series) -> str:
    avg = policy_code_text(row.get("grade_averaging_normalized", ""))
    forgive = policy_code_text(row.get("grade_forgiveness_normalized", ""))
    if avg == "1" and forgive == "1":
        return "both_or_ambiguous"
    if forgive == "1":
        return "grade_forgiveness"
    if avg == "1":
        return "grade_averaging"
    if avg == "0" and forgive == "0":
        return "neither"
    return "unknown"


def policy_code_text(value: object) -> str:
    text = str(value).strip().lower()
    if text in {"1", "1.0", "true", "yes"}:
        return "1"
    if text in {"0", "0.0", "false", "no"}:
        return "0"
    if text in {"", "nan", "none", "<na>"}:
        return ""
    return text


def build_targets(universe: pd.DataFrame, links: pd.DataFrame, panel: pd.DataFrame) -> pd.DataFrame:
    years = pd.DataFrame({"year": range(TARGET_START_YEAR, TARGET_END_YEAR + 1)})
    targets = universe[
        [
            "unitid",
            "institution_name",
            "sector",
            "control",
            "state",
            "source_in_legacy_public",
            "source_in_legacy_private",
        ]
    ].merge(years, how="cross")

    panel_presence = panel[["unitid", "year"]].drop_duplicates().assign(active_in_ipeds_panel_year=True)
    targets = targets.merge(panel_presence, on=["unitid", "year"], how="left")
    targets["active_in_ipeds_panel_year"] = to_bool(targets["active_in_ipeds_panel_year"])

    if links.empty:
        targets["legacy_evidence_row_count"] = 0
        targets["legacy_selected_prior_count"] = 0
        targets["legacy_needs_review"] = False
        targets["legacy_conflict_count"] = 0
        targets["prior_evidence_status"] = "missing"
    else:
        link_summary = (
            links.groupby(["unitid", "target_year"], dropna=True)
            .agg(
                legacy_evidence_row_count=("legacy_link_id", "size"),
                legacy_selected_prior_count=("selected_as_prior_evidence", "sum"),
                legacy_needs_review=("legacy_needs_review", "max"),
                legacy_conflict_count=("conflicting_duplicate_institution_year", "sum"),
                legacy_workbooks=("legacy_workbook", unique_join),
                legacy_sheet_names=("legacy_sheet_name", unique_join),
            )
            .reset_index()
            .rename(columns={"target_year": "year"})
        )
        targets = targets.merge(link_summary, on=["unitid", "year"], how="left")
        targets["legacy_evidence_row_count"] = targets["legacy_evidence_row_count"].fillna(0).astype(int)
        targets["legacy_selected_prior_count"] = targets["legacy_selected_prior_count"].fillna(0).astype(int)
        targets["legacy_needs_review"] = to_bool(targets["legacy_needs_review"])
        targets["legacy_conflict_count"] = targets["legacy_conflict_count"].fillna(0).astype(int)
        targets["legacy_workbooks"] = targets["legacy_workbooks"].fillna("")
        targets["legacy_sheet_names"] = targets["legacy_sheet_names"].fillna("")
        targets["prior_evidence_status"] = "missing"
        targets.loc[targets["legacy_evidence_row_count"].gt(0), "prior_evidence_status"] = "legacy_linked"
        targets.loc[targets["legacy_selected_prior_count"].gt(0), "prior_evidence_status"] = "legacy_prior_candidate"
        targets.loc[targets["legacy_needs_review"], "prior_evidence_status"] = "legacy_needs_review"

    targets["source_discovery_priority"] = targets["prior_evidence_status"].map(
        {
            "missing": "high",
            "legacy_needs_review": "high",
            "legacy_linked": "medium",
            "legacy_prior_candidate": "lower",
        }
    )
    return targets.sort_values(["unitid", "year"])


def panel_candidate_summary(root: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for rel_path in (PANEL_SOURCE,) + OTHER_PANEL_CANDIDATES:
        path = root / rel_path
        if not path.exists():
            rows.append({"path": str(rel_path), "exists": False})
            continue
        try:
            df = pd.read_stata(path, columns=None, convert_categoricals=False)
            rows.append(
                {
                    "path": str(rel_path),
                    "exists": True,
                    "rows": len(df),
                    "columns": len(df.columns),
                    "unitids": int(df["unitid"].nunique()) if "unitid" in df else "",
                    "year_min": int(df["year"].min()) if "year" in df else "",
                    "year_max": int(df["year"].max()) if "year" in df else "",
                    "has_sector": "sector" in df,
                    "has_iclevel": "iclevel" in df,
                }
            )
        except Exception as exc:  # pragma: no cover - defensive logging only.
            rows.append({"path": str(rel_path), "exists": True, "error": f"{type(exc).__name__}: {exc}"})
    return rows


def write_summary_report(
    root: Path,
    panel: pd.DataFrame,
    universe: pd.DataFrame,
    targets: pd.DataFrame,
    links: pd.DataFrame,
    output_path: Path,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    candidates = panel_candidate_summary(root)
    lines = [
        "# Phase 2 Institution-Year Universe",
        "",
        f"Generated at: {now}",
        "",
        "## Selected IPEDS/Stata Source",
        "",
        f"- Source: `{PANEL_SOURCE}`",
        f"- SHA256: `{file_hash(root / PANEL_SOURCE)}`",
        "- Rationale: this file is produced by `02_missingness_representativeness.do` after filtering "
        "`mainpanelgf_clean.dta` to non-manually-excluded IPEDS sector 1/2 four-year institutions and "
        "merging existing policy-year flags.",
        "",
        "## Candidate Source Inventory",
        "",
    ]
    for row in candidates:
        if not row.get("exists"):
            lines.append(f"- `{row['path']}`: missing")
        elif "error" in row:
            lines.append(f"- `{row['path']}`: error reading file ({row['error']})")
        else:
            lines.append(
                f"- `{row['path']}`: {row['rows']} rows, {row['columns']} columns, "
                f"{row['unitids']} unitids, years {row['year_min']}-{row['year_max']}, "
                f"sector column={row['has_sector']}, iclevel column={row['has_iclevel']}"
            )

    lines.extend(
        [
            "",
            "## Outputs",
            "",
            f"- Institution universe rows: {len(universe)}",
            f"- Institution-year target rows: {len(targets)}",
            f"- Target years: {TARGET_START_YEAR}-{TARGET_END_YEAR}",
            f"- Legacy evidence link rows: {len(links)}",
            f"- Selected legacy prior-evidence candidates: {int(links['selected_as_prior_evidence'].sum()) if not links.empty else 0}",
            f"- Target rows with no linked legacy evidence: {int(targets['prior_evidence_status'].eq('missing').sum())}",
            f"- Target rows needing review from legacy flags: {int(targets['prior_evidence_status'].eq('legacy_needs_review').sum())}",
            "",
            "## Universe By Sector",
            "",
        ]
    )
    for sector, count in universe["sector"].value_counts().sort_index().items():
        lines.append(f"- {sector}: {count}")

    lines.extend(["", "## Legacy Link Rules", ""])
    lines.extend(
        [
            "- Public audit rows use priority 10.",
            "- Private audit rows use priorities: private=10, automated missing-private=40, example=80, LLM training set=90.",
            "- A row is marked `selected_as_prior_evidence` only when it is a clean lowest-priority row for its institution-year and the lowest-priority rows agree on the normalized policy signature.",
            "- Duplicate, conflicting, malformed, student-note-like, or source-missing legacy rows remain in `legacy_evidence_links.csv` and are routed through review flags.",
            "",
        ]
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


def run_phase2_universe(root: Path) -> BuildOutputs:
    interim_dir = root / INTERIM_DIR
    log_dir = root / LOG_DIR
    interim_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    panel = read_panel_source(root)
    audits = read_legacy_audits(root)
    universe = build_institution_universe(panel, audits)
    links = build_legacy_evidence_links(audits, universe)
    targets = build_targets(universe, links, panel)

    universe_path = interim_dir / "institution_universe.csv"
    targets_path = interim_dir / "institution_year_targets.csv"
    links_path = interim_dir / "legacy_evidence_links.csv"
    summary_path = log_dir / "phase2_institution_year_universe_summary.md"

    universe.to_csv(universe_path, index=False)
    targets.to_csv(targets_path, index=False)
    links.to_csv(links_path, index=False)
    write_summary_report(root, panel, universe, targets, links, summary_path)

    return BuildOutputs(
        institution_universe=universe_path,
        institution_year_targets=targets_path,
        legacy_evidence_links=links_path,
        summary_report=summary_path,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build Phase 2 institution-year universe outputs.")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Project root containing policy_pipeline and data_policy_pipeline.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    outputs = run_phase2_universe(args.root.resolve())
    for label, path in outputs.__dict__.items():
        print(f"{label}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
