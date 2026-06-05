"""Build the Phase 3 catalog discovery pilot inventory."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

from .ai_client import run_api_smoke
from .ai_config import load_ai_config, repo_root_from_cwd


TARGET_START_YEAR = 2000
TARGET_END_YEAR = 2020
PILOT_SIZE = 20

DATA_DIR = Path("../data_policy_pipeline")
INTERIM_DIR = DATA_DIR / "interim"
LOG_DIR = DATA_DIR / "logs"

INSTITUTION_UNIVERSE = INTERIM_DIR / "institution_universe.csv"
INSTITUTION_YEAR_TARGETS = INTERIM_DIR / "institution_year_targets.csv"
LEGACY_EVIDENCE_LINKS = INTERIM_DIR / "legacy_evidence_links.csv"

PILOT_INSTITUTIONS_OUTPUT = INTERIM_DIR / "catalog_pilot_institutions.csv"
CATALOG_INVENTORY_OUTPUT = INTERIM_DIR / "catalog_inventory_pilot.csv"
SUMMARY_OUTPUT = LOG_DIR / "phase3_catalog_discovery_pilot_summary.md"

BOOL_TRUE = {"true", "1", "yes", "y"}
AMBIGUOUS_THRESHOLDS = {"ANY", "UNKNOWN"}


@dataclass(frozen=True)
class Phase3Outputs:
    pilot_institutions: Path
    catalog_inventory: Path
    summary_report: Path


def to_bool(series: pd.Series) -> pd.Series:
    return series.astype("string").fillna("").str.strip().str.lower().isin(BOOL_TRUE)


def clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def unique_join(values: pd.Series) -> str:
    nonempty = values.dropna().astype(str).str.strip()
    nonempty = nonempty[nonempty.ne("")]
    return "; ".join(sorted(nonempty.unique()))


def read_phase2_inputs(repo_root: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    data_root = repo_root / DATA_DIR
    universe = pd.read_csv(repo_root / INSTITUTION_UNIVERSE, low_memory=False)
    targets = pd.read_csv(repo_root / INSTITUTION_YEAR_TARGETS, low_memory=False)
    links = pd.read_csv(repo_root / LEGACY_EVIDENCE_LINKS, low_memory=False)
    if not data_root.exists():
        raise FileNotFoundError(f"Expected generated data directory: {data_root}")
    return universe, targets, links


def build_public_pilot_features(universe: pd.DataFrame, links: pd.DataFrame) -> pd.DataFrame:
    public = universe[universe["sector"].eq("public_4_year")].copy()
    public_unitids = set(public["unitid"].dropna().astype(int))
    public_links = links[links["unitid"].isin(public_unitids) & links["legacy_workbook"].eq("public")].copy()

    if public_links.empty:
        features = public[["unitid", "institution_name", "state", "webaddr"]].copy()
        for col in FEATURE_COLUMNS:
            features[col] = False
        features["legacy_link_rows"] = 0
        return add_selection_fields(features)

    for col in FLAG_COLUMNS:
        if col in public_links.columns:
            public_links[col] = to_bool(public_links[col])
        else:
            public_links[col] = False

    public_links["legacy_url_clean"] = public_links.get("legacy_url", "").map(clean_text)
    public_links["has_url"] = public_links["legacy_url_clean"].ne("")
    public_links["has_selected_clean_url"] = (
        public_links["selected_as_prior_evidence"]
        & ~public_links["legacy_needs_review"]
        & public_links["has_url"]
    )
    public_links["malformed_threshold"] = (
        public_links["malformed_grade_avg_threshold"] | public_links["malformed_grade_forgive_threshold"]
    )
    public_links["threshold_values"] = public_links.apply(_threshold_values, axis=1)
    public_links["has_ambiguous_threshold"] = public_links["threshold_values"].map(
        lambda values: any(value in AMBIGUOUS_THRESHOLDS for value in values)
    )

    grouped = (
        public_links.groupby("unitid", dropna=True)
        .agg(
            legacy_link_rows=("legacy_link_id", "size"),
            legacy_year_count=("target_year", "nunique"),
            legacy_url_count=("legacy_url_clean", lambda s: s[s.ne("")].nunique()),
            legacy_workbook_count=("legacy_workbook", "nunique"),
            legacy_workbooks=("legacy_workbook", unique_join),
            legacy_policy_class_count=("legacy_policy_class", lambda s: s.dropna().astype(str).str.strip().nunique()),
            legacy_policy_classes=("legacy_policy_class", unique_join),
            selected_clean_url_count=("has_selected_clean_url", "sum"),
            missing_url_count=("missing_bulletin_url", "sum"),
            missing_excerpt_count=("missing_evidence_text", "sum"),
            student_note_count=("likely_student_note", "sum"),
            malformed_threshold_count=("malformed_threshold", "sum"),
            needs_review_count=("legacy_needs_review", "sum"),
            duplicate_count=("duplicate_institution_year", "sum"),
            conflicting_duplicate_count=("conflicting_duplicate_institution_year", "sum"),
            ambiguous_threshold_count=("has_ambiguous_threshold", "sum"),
            threshold_signature_count=("threshold_values", _threshold_signature_count),
        )
        .reset_index()
    )
    features = public[["unitid", "institution_name", "state", "webaddr"]].merge(grouped, on="unitid", how="left")
    count_cols = [
        "legacy_link_rows",
        "legacy_year_count",
        "legacy_url_count",
        "legacy_workbook_count",
        "legacy_policy_class_count",
        "selected_clean_url_count",
        "missing_url_count",
        "missing_excerpt_count",
        "student_note_count",
        "malformed_threshold_count",
        "needs_review_count",
        "duplicate_count",
        "conflicting_duplicate_count",
        "ambiguous_threshold_count",
        "threshold_signature_count",
    ]
    for col in count_cols:
        features[col] = features[col].fillna(0).astype(int)
    for col in ["legacy_workbooks", "legacy_policy_classes"]:
        features[col] = features[col].fillna("")
    return add_selection_fields(features)


FLAG_COLUMNS = [
    "legacy_needs_review",
    "missing_bulletin_url",
    "missing_evidence_text",
    "likely_student_note",
    "malformed_grade_avg_threshold",
    "malformed_grade_forgive_threshold",
    "duplicate_institution_year",
    "conflicting_duplicate_institution_year",
    "selected_as_prior_evidence",
]

FEATURE_COLUMNS = [
    "clean_case",
    "messy_case",
    "missing_url_case",
    "cross_workbook_legacy_case",
    "duplicate_or_conflicting_legacy_case",
    "multiple_policy_change_case",
    "ambiguous_threshold_case",
    "no_legacy_evidence_case",
]


def _threshold_values(row: pd.Series) -> tuple[str, ...]:
    values = []
    for col in ["grade_avg_threshold_normalized", "grade_forgive_threshold_normalized"]:
        value = clean_text(row.get(col, "")).upper()
        if value:
            values.append(value)
    return tuple(values)


def _threshold_signature_count(values: pd.Series) -> int:
    signatures = {tuple(value) for value in values if tuple(value)}
    return len(signatures)


def add_selection_fields(features: pd.DataFrame) -> pd.DataFrame:
    out = features.copy()
    out["clean_case"] = (
        out["selected_clean_url_count"].gt(0)
        & out["needs_review_count"].eq(0)
        & out["missing_url_count"].eq(0)
        & out["student_note_count"].eq(0)
        & out["malformed_threshold_count"].eq(0)
    )
    out["messy_case"] = (
        out["needs_review_count"].gt(0)
        | out["missing_excerpt_count"].gt(0)
        | out["student_note_count"].gt(0)
        | out["malformed_threshold_count"].gt(0)
    )
    out["missing_url_case"] = out["missing_url_count"].gt(0)
    out["cross_workbook_legacy_case"] = out["legacy_workbook_count"].gt(1)
    out["duplicate_or_conflicting_legacy_case"] = out["duplicate_count"].gt(0) | out["conflicting_duplicate_count"].gt(0)
    out["multiple_policy_change_case"] = (
        out["legacy_year_count"].gt(1)
        & (out["legacy_policy_class_count"].gt(1) | out["threshold_signature_count"].gt(1))
    )
    out["ambiguous_threshold_case"] = out["ambiguous_threshold_count"].gt(0) | out["malformed_threshold_count"].gt(0)
    out["no_legacy_evidence_case"] = out["legacy_link_rows"].eq(0)
    out["pilot_feature_count"] = out[FEATURE_COLUMNS].sum(axis=1)
    out["pilot_case_types"] = out.apply(case_types, axis=1)
    return out


def case_types(row: pd.Series) -> str:
    labels = []
    for col, label in [
        ("clean_case", "clean"),
        ("messy_case", "messy"),
        ("missing_url_case", "missing_url"),
        ("duplicate_or_conflicting_legacy_case", "duplicate_or_cross_workbook"),
        ("multiple_policy_change_case", "multiple_policy_changes"),
        ("ambiguous_threshold_case", "ambiguous_threshold"),
        ("no_legacy_evidence_case", "no_legacy_evidence"),
    ]:
        if bool(row.get(col, False)):
            labels.append(label)
    return "; ".join(labels)


def select_pilot_institutions(features: pd.DataFrame, pilot_size: int = PILOT_SIZE) -> pd.DataFrame:
    selected: list[pd.Series] = []
    selected_unitids: set[int] = set()

    quotas = [
        ("missing_url_case", 2),
        ("messy_case", 3),
        ("duplicate_or_conflicting_legacy_case", 2),
        ("multiple_policy_change_case", 4),
        ("ambiguous_threshold_case", 4),
        ("no_legacy_evidence_case", 2),
        ("clean_case", 7),
    ]
    for flag, quota in quotas:
        candidates = rank_candidates(features[features[flag] & ~features["unitid"].isin(selected_unitids)])
        for _, row in candidates.head(quota).iterrows():
            selected.append(row)
            selected_unitids.add(int(row["unitid"]))
            if len(selected) >= pilot_size:
                return finalize_selection(selected)

    if len(selected) < pilot_size:
        fill = rank_candidates(features[~features["unitid"].isin(selected_unitids)]).head(pilot_size - len(selected))
        for _, row in fill.iterrows():
            selected.append(row)
            selected_unitids.add(int(row["unitid"]))

    return finalize_selection(selected)


def rank_candidates(df: pd.DataFrame) -> pd.DataFrame:
    return df.sort_values(
        [
            "pilot_feature_count",
            "legacy_year_count",
            "legacy_link_rows",
            "institution_name",
            "unitid",
        ],
        ascending=[False, False, False, True, True],
    )


def finalize_selection(selected: list[pd.Series]) -> pd.DataFrame:
    out = pd.DataFrame(selected).copy()
    out["pilot_rank"] = range(1, len(out) + 1)
    return out[
        [
            "pilot_rank",
            "unitid",
            "institution_name",
            "state",
            "webaddr",
            "pilot_case_types",
            *FEATURE_COLUMNS,
            "legacy_link_rows",
            "legacy_year_count",
            "legacy_url_count",
            "legacy_workbooks",
            "legacy_policy_classes",
            "selected_clean_url_count",
            "missing_url_count",
            "missing_excerpt_count",
            "student_note_count",
            "malformed_threshold_count",
            "needs_review_count",
            "duplicate_count",
            "conflicting_duplicate_count",
            "ambiguous_threshold_count",
        ]
    ].sort_values("pilot_rank")


def build_catalog_inventory(pilot: pd.DataFrame, targets: pd.DataFrame, links: pd.DataFrame) -> pd.DataFrame:
    pilot_unitids = set(pilot["unitid"].dropna().astype(int))
    pilot_targets = targets[targets["unitid"].isin(pilot_unitids)].copy()
    pilot_targets = pilot_targets.merge(
        pilot[["unitid", "pilot_rank", "pilot_case_types"]], on="unitid", how="left"
    )
    pilot_links = links[links["unitid"].isin(pilot_unitids) & links["legacy_workbook"].eq("public")].copy()

    rows: list[dict[str, object]] = []
    created_at = datetime.now(timezone.utc).isoformat()
    source_counter = 1
    for _, target in pilot_targets.sort_values(["pilot_rank", "unitid", "year"]).iterrows():
        year_links = pilot_links[pilot_links["unitid"].eq(target["unitid"]) & pilot_links["target_year"].eq(target["year"])]
        if year_links.empty:
            rows.append(placeholder_inventory_row(source_counter, target, created_at))
            source_counter += 1
            continue

        for _, link in year_links.sort_values(["legacy_source_priority", "legacy_workbook", "legacy_excel_row"]).iterrows():
            rows.append(legacy_inventory_row(source_counter, target, link, created_at))
            source_counter += 1

    return pd.DataFrame(rows).sort_values(["pilot_rank", "unitid", "target_year", "source_id"])


def placeholder_inventory_row(source_counter: int, target: pd.Series, created_at: str) -> dict[str, object]:
    return {
        "source_id": f"pilot-{source_counter:05d}",
        "pilot_rank": int(target["pilot_rank"]),
        "pilot_case_types": target["pilot_case_types"],
        "unitid": int(target["unitid"]),
        "institution_name": target["institution_name"],
        "target_year": int(target["year"]),
        "candidate_url": "",
        "archived_url": "",
        "source_kind": "missing_legacy_url",
        "source_domain": "",
        "catalog_year_start": "",
        "catalog_year_end": "",
        "retrieval_status": "requires_review",
        "content_type": "",
        "local_source_path": "",
        "text_extract_status": "not_attempted",
        "source_confidence": 0.0,
        "discovery_method": "manual_review",
        "selected_for_use": False,
        "needs_human_review": True,
        "review_reason": "No exact legacy evidence link for this institution-year; deterministic discovery not yet attempted.",
        "legacy_workbook": "",
        "legacy_sheet_name": "",
        "legacy_excel_row": "",
        "legacy_link_id": "",
        "legacy_selected_as_prior_evidence": False,
        "legacy_needs_review": False,
        "legacy_review_reasons": "",
        "legacy_excerpt_present": False,
        "notes": "Phase 3 pilot scaffold placeholder.",
        "created_at": created_at,
        "updated_at": created_at,
    }


def legacy_inventory_row(source_counter: int, target: pd.Series, link: pd.Series, created_at: str) -> dict[str, object]:
    url = clean_text(link.get("legacy_url", ""))
    review_reasons = inventory_review_reasons(link, has_url=bool(url))
    years = infer_catalog_coverage_years(url, clean_text(link.get("legacy_excerpt", "")))
    return {
        "source_id": f"pilot-{source_counter:05d}",
        "pilot_rank": int(target["pilot_rank"]),
        "pilot_case_types": target["pilot_case_types"],
        "unitid": int(target["unitid"]),
        "institution_name": target["institution_name"],
        "target_year": int(target["year"]),
        "candidate_url": url,
        "archived_url": "",
        "source_kind": source_kind_from_url(url),
        "source_domain": source_domain(url),
        "catalog_year_start": years[0] if years else "",
        "catalog_year_end": years[1] if years else "",
        "retrieval_status": "not_attempted" if url else "requires_review",
        "content_type": "",
        "local_source_path": "",
        "text_extract_status": "not_attempted",
        "source_confidence": source_confidence(link, bool(url)),
        "discovery_method": "legacy_workbook" if url else "manual_review",
        "selected_for_use": False,
        "needs_human_review": bool(review_reasons),
        "review_reason": "; ".join(review_reasons),
        "legacy_workbook": link.get("legacy_workbook", ""),
        "legacy_sheet_name": link.get("legacy_sheet_name", ""),
        "legacy_excel_row": link.get("legacy_excel_row", ""),
        "legacy_link_id": link.get("legacy_link_id", ""),
        "legacy_selected_as_prior_evidence": bool_value(link.get("selected_as_prior_evidence", False)),
        "legacy_needs_review": bool_value(link.get("legacy_needs_review", False)),
        "legacy_review_reasons": clean_text(link.get("legacy_review_reasons", "")),
        "legacy_excerpt_present": bool(clean_text(link.get("legacy_excerpt", ""))),
        "notes": "Legacy URL lead; retrieval and source verification not yet attempted.",
        "created_at": created_at,
        "updated_at": created_at,
    }


def bool_value(value: object) -> bool:
    return str(value).strip().lower() in BOOL_TRUE


def inventory_review_reasons(link: pd.Series, *, has_url: bool) -> list[str]:
    reasons: list[str] = []
    if not has_url:
        reasons.append("missing legacy URL")
    flag_labels = {
        "legacy_needs_review": "legacy row needs review",
        "missing_evidence_text": "missing legacy evidence text",
        "likely_student_note": "legacy evidence may be collector note",
        "malformed_grade_avg_threshold": "malformed grade averaging threshold",
        "malformed_grade_forgive_threshold": "malformed grade forgiveness threshold",
        "duplicate_institution_year": "duplicate legacy institution-year",
        "conflicting_duplicate_institution_year": "conflicting legacy duplicate",
    }
    for flag, label in flag_labels.items():
        if bool_value(link.get(flag, False)):
            reasons.append(label)
    thresholds = _threshold_values(link)
    if any(value in AMBIGUOUS_THRESHOLDS for value in thresholds):
        reasons.append("ambiguous threshold prior evidence")
    return reasons


def source_confidence(link: pd.Series, has_url: bool) -> float:
    if not has_url:
        return 0.0
    confidence = 0.55
    if bool_value(link.get("selected_as_prior_evidence", False)):
        confidence += 0.15
    if bool_value(link.get("legacy_needs_review", False)):
        confidence -= 0.20
    if bool_value(link.get("likely_student_note", False)):
        confidence -= 0.10
    return round(max(0.0, min(1.0, confidence)), 2)


def source_domain(url: str) -> str:
    if not url:
        return ""
    return urlparse(url).netloc.lower()


def source_kind_from_url(url: str) -> str:
    if not url:
        return "missing_legacy_url"
    path = urlparse(url).path.lower()
    if path.endswith(".pdf"):
        return "undergraduate_catalog_pdf"
    if path.endswith((".html", ".htm")):
        return "catalog_or_policy_html"
    return "catalog_or_policy_webpage"


def infer_catalog_coverage_years(url: str, excerpt: str) -> tuple[int, int] | None:
    text = f"{url} {excerpt}"
    range_match = re.search(r"((?:19|20)\d{2})\D{0,8}((?:19|20)?\d{2})", text)
    if range_match:
        start = int(range_match.group(1))
        end_text = range_match.group(2)
        end = int(end_text) if len(end_text) == 4 else int(str(start)[:2] + end_text)
        if 1990 <= start <= 2030 and start <= end <= 2035:
            return start, end
    year_match = re.search(r"(?:19|20)\d{2}", text)
    if not year_match:
        return None
    year = int(year_match.group(0))
    return (year, year) if 1990 <= year <= 2030 else None


def write_summary_report(
    repo_root: Path,
    pilot: pd.DataFrame,
    inventory: pd.DataFrame,
    features: pd.DataFrame,
    output_path: Path,
    api_smoke_metadata: Path | None,
) -> None:
    lines = [
        "# Phase 3 Catalog Discovery Pilot",
        "",
        f"Generated at: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Scope",
        "",
        f"- Pilot institutions: {len(pilot)} public four-year institutions.",
        f"- Inventory rows: {len(inventory)}.",
        f"- Target years: {TARGET_START_YEAR}-{TARGET_END_YEAR}.",
        "- Full-scale discovery was not run.",
        "- Legacy URLs are treated as candidate leads, not verified selected sources.",
        "",
        "## Pilot Case Coverage",
        "",
    ]
    for col, label in [
        ("clean_case", "clean cases"),
        ("messy_case", "messy/review-flagged cases"),
        ("missing_url_case", "missing legacy URL cases"),
        ("duplicate_or_conflicting_legacy_case", "duplicate/cross-workbook legacy cases"),
        ("multiple_policy_change_case", "multiple policy-change cases"),
        ("ambiguous_threshold_case", "ambiguous threshold cases"),
        ("no_legacy_evidence_case", "no exact legacy evidence cases"),
    ]:
        lines.append(f"- {label}: {int(pilot[col].sum())}")

    public_duplicate_conflicts = int(features["duplicate_count"].sum() + features["conflicting_duplicate_count"].sum())
    lines.extend(
        [
            "",
            "## Duplicate/Conflict Note",
            "",
            f"- Public-institution legacy rows with explicit duplicate/conflict audit flags: {public_duplicate_conflicts}.",
            "- Private workbook example/training rows are excluded from the public pilot because they were student guides/training material, not public-institution source evidence.",
            "",
            "## Inventory Status",
            "",
            f"- Rows with legacy URL leads: {int(inventory['candidate_url'].astype(str).str.strip().ne('').sum())}",
            f"- Placeholder rows requiring deterministic discovery: {int(inventory['candidate_url'].astype(str).str.strip().eq('').sum())}",
            f"- Rows needing human review before source selection: {int(inventory['needs_human_review'].sum())}",
            "",
            "## API Workflow",
            "",
        ]
    )
    if api_smoke_metadata:
        lines.append(f"- API smoke-test metadata written to `{api_smoke_metadata}`.")
    else:
        lines.append("- API smoke test was not requested for this run.")
    lines.extend(
        [
            "- The API smoke test is a connectivity check only and does not create catalog evidence.",
            "",
            "## Outputs",
            "",
            f"- Pilot institutions: `{(repo_root / PILOT_INSTITUTIONS_OUTPUT).resolve()}`",
            f"- Catalog inventory pilot: `{(repo_root / CATALOG_INVENTORY_OUTPUT).resolve()}`",
            f"- Summary report: `{output_path}`",
            "",
        ]
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


def run_phase3_catalog_pilot(
    repo_root: Path,
    *,
    pilot_size: int = PILOT_SIZE,
    run_smoke: bool = False,
    config_path: Path | None = None,
) -> Phase3Outputs:
    repo_root = repo_root.resolve()
    universe, targets, links = read_phase2_inputs(repo_root)
    features = build_public_pilot_features(universe, links)
    pilot = select_pilot_institutions(features, pilot_size=pilot_size)
    inventory = build_catalog_inventory(pilot, targets, links)

    api_smoke_metadata = None
    if run_smoke:
        config = load_ai_config(config_path, root=repo_root)
        api_smoke = run_api_smoke(config)
        api_smoke_metadata = api_smoke.metadata_path

    pilot_path = (repo_root / PILOT_INSTITUTIONS_OUTPUT).resolve()
    inventory_path = (repo_root / CATALOG_INVENTORY_OUTPUT).resolve()
    summary_path = (repo_root / SUMMARY_OUTPUT).resolve()
    pilot_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    pilot.to_csv(pilot_path, index=False)
    inventory.to_csv(inventory_path, index=False)
    write_summary_report(repo_root, pilot, inventory, features, summary_path, api_smoke_metadata)

    return Phase3Outputs(
        pilot_institutions=pilot_path,
        catalog_inventory=inventory_path,
        summary_report=summary_path,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build Phase 3 catalog discovery pilot inventory.")
    parser.add_argument("--root", type=Path, default=None, help="Repository root. Defaults to auto-detection.")
    parser.add_argument("--pilot-size", type=int, default=PILOT_SIZE)
    parser.add_argument("--api-smoke", action="store_true", help="Also run/dry-run the API smoke-test workflow.")
    parser.add_argument("--config", type=Path, default=None, help="AI config path for --api-smoke.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve() if args.root else repo_root_from_cwd()
    outputs = run_phase3_catalog_pilot(
        root,
        pilot_size=args.pilot_size,
        run_smoke=args.api_smoke,
        config_path=args.config,
    )
    for label, path in outputs.__dict__.items():
        print(f"{label}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
