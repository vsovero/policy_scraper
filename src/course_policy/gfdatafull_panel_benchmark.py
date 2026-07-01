"""Benchmark legacy policy builds against the old gfdatafull panel.

The denominator for legacy coverage is the downstream gfdatafull valid-policy
panel for the sector being measured, not the raw student change-log rows and
not the newly generated URL universe. This module makes that benchmark
repeatable for both public legacy and private human-legacy streams.
"""

from __future__ import annotations

import argparse
import hashlib
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, unquote, urlparse, urlunparse

import pandas as pd

from .ai_config import repo_root_from_cwd


DATA_DIR = Path("artifacts/policy_data_internal")
INTERIM_DIR = DATA_DIR / "interim"
REVIEW_DIR = DATA_DIR / "review"
LOG_DIR = DATA_DIR / "logs"
DELIVERY_DIR = Path("../policy_data")

DEFAULT_OUTPUT_DIR = REVIEW_DIR / "url_fix_validation" / "current"
DEFAULT_GFDATAFULL = Path("../Stata Files/Data/gfdatafull.dta")
DEFAULT_PUBLIC_YEAR_PANEL = REVIEW_DIR / "streams/public_legacy_url/current/year_panel.csv"
DEFAULT_PRIVATE_YEAR_PANEL = REVIEW_DIR / "streams/private_human_legacy_url/current/year_panel.csv"
DEFAULT_CATALOG_DB = DELIVERY_DIR / "catalog_url_database.csv"
DEFAULT_PUBLIC_CLASSIFICATION = DELIVERY_DIR / "policy_classification_production_excerpt_public_legacy_url_001_5111_api_live.csv"
DEFAULT_PRIVATE_CLASSIFICATION = DELIVERY_DIR / "policy_classification_production_excerpt_private_human_legacy_url_001_600_api_live.csv"
DEFAULT_LOSS_AUDIT = DELIVERY_DIR / "public_legacy_outcome_loss_audit.csv"
DEFAULT_LEGACY_LINKS = INTERIM_DIR / "legacy_evidence_links.csv"
DEFAULT_PUBLIC_AUDIT = INTERIM_DIR / "legacy_public_audit.csv"
DEFAULT_PRIVATE_AUDIT = INTERIM_DIR / "legacy_private_audit.csv"

INFORMATIVE_CLASSES = {"grade_forgiveness", "grade_averaging", "both_or_ambiguous"}
POLICY_SIGNATURE_COLUMNS = ("avg", "gradeavg", "forgive", "gradeforgive")
SHELL_SOURCE_HINTS = (
    "yumpu.com",
    "biblioboard.com",
    "sharepoint.com",
    "drive.google.com",
    "docs.google.com",
)
DIRECT_CATALOG_HINTS = (
    "catalog.",
    "/catalog",
    "bulletin",
    "archive",
    "archives",
    "content.php",
)


@dataclass(frozen=True)
class SectorBenchmarkConfig:
    sector: str
    public_value: int
    stream_id: str
    workbook_label: str
    year_panel_path: Path
    classification_path: Path
    audit_path: Path
    loss_audit_path: Path | None

    @property
    def output_prefix(self) -> str:
        return f"gfdatafull_{self.sector}_valid_policy_panel_attrition"

    @property
    def old_panel_column(self) -> str:
        return f"old_gfdatafull_{self.sector}_valid_policy"


SECTOR_CONFIGS = {
    "public": SectorBenchmarkConfig(
        sector="public",
        public_value=1,
        stream_id="public_legacy_url",
        workbook_label="public",
        year_panel_path=DEFAULT_PUBLIC_YEAR_PANEL,
        classification_path=DEFAULT_PUBLIC_CLASSIFICATION,
        audit_path=DEFAULT_PUBLIC_AUDIT,
        loss_audit_path=DEFAULT_LOSS_AUDIT,
    ),
    "private": SectorBenchmarkConfig(
        sector="private",
        public_value=0,
        stream_id="private_human_legacy_url",
        workbook_label="private",
        year_panel_path=DEFAULT_PRIVATE_YEAR_PANEL,
        classification_path=DEFAULT_PRIVATE_CLASSIFICATION,
        audit_path=DEFAULT_PRIVATE_AUDIT,
        loss_audit_path=None,
    ),
}


@dataclass(frozen=True)
class GfdatafullBenchmarkOutputs:
    attrition_csv: Path
    summary_csv: Path
    summary_md: Path
    policy_spell_priority_csv: Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def bool_series(values: pd.Series, *, default: bool = False) -> pd.Series:
    if values.empty:
        return pd.Series(dtype=bool)
    if values.dtype == bool:
        return values.fillna(default)
    filled = values.astype("object").where(values.notna(), default)
    return filled.astype(str).str.strip().str.lower().isin({"true", "1", "1.0", "yes"})


def read_csv_if_exists(path: Path | None) -> pd.DataFrame:
    if path is None:
        return pd.DataFrame()
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, low_memory=False)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def read_stata_if_exists(path: Path) -> pd.DataFrame:
    return pd.read_stata(path, convert_categoricals=False) if path.exists() else pd.DataFrame()


def read_csv_many(paths: list[Path]) -> pd.DataFrame:
    frames = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        frame = read_csv_if_exists(resolved)
        if frame.empty:
            continue
        frame["_classification_source_file"] = str(resolved)
        frames.append(frame)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True, sort=False)


def first_existing(repo_root: Path, paths: list[Path]) -> Path | None:
    for path in paths:
        candidate = path if path.is_absolute() else repo_root / path
        if candidate.exists():
            return candidate
    return None


def load_old_policy_panel(path: Path, config: SectorBenchmarkConfig) -> pd.DataFrame:
    gf = read_stata_if_exists(path)
    if gf.empty:
        return pd.DataFrame()
    required = {"unitid", "year", "public", "has_valid_policy"}
    missing = required - set(gf.columns)
    if missing:
        raise ValueError(f"gfdatafull is missing required columns: {sorted(missing)}")
    grad_cols = [column for column in ["grad4per", "grad5per", "grad6per"] if column in gf.columns]
    if grad_cols:
        has_grad_outcome = gf[grad_cols].notna().any(axis=1)
    else:
        has_grad_outcome = pd.Series(False, index=gf.index)
    target_year = pd.to_numeric(gf["year"], errors="coerce").astype("Int64")
    old = gf.loc[gf["public"].eq(config.public_value) & gf["has_valid_policy"].eq(1)].copy()
    old["target_year"] = target_year.loc[old.index].array
    old["has_grad_outcome"] = has_grad_outcome.loc[old.index].to_numpy()
    columns = [
        "unitid",
        "target_year",
        "instnm",
        "avg",
        "gradeavg",
        "forgive",
        "gradeforgive",
        "has_valid_policy",
        "has_grad_outcome",
    ]
    for column in columns:
        if column not in old.columns:
            old[column] = ""
    old = old[columns].drop_duplicates(["unitid", "target_year"], keep="first")
    old[config.old_panel_column] = True
    old["in_current_target_window_2000_2020"] = old["target_year"].between(2000, 2020)
    return old


def build_raw_change_log_flags(audit_frame: pd.DataFrame) -> pd.DataFrame:
    if audit_frame.empty:
        return pd.DataFrame(columns=["unitid", "target_year"])
    audit = audit_frame.copy()
    audit["unitid"] = pd.to_numeric(audit["unitid"], errors="coerce").astype("Int64")
    audit["target_year"] = pd.to_numeric(audit.get("parsed_start_year"), errors="coerce").astype("Int64")
    missing_start = bool_series(audit.get("missing_start_year", pd.Series(False, index=audit.index)))
    outside_window = bool_series(audit.get("start_year_outside_2000_2020", pd.Series(False, index=audit.index)))
    missing_url = bool_series(audit.get("missing_bulletin_url", pd.Series(False, index=audit.index)))
    audit = audit.loc[~missing_start & ~outside_window].copy()
    if audit.empty:
        return pd.DataFrame(columns=["unitid", "target_year"])
    audit["raw_change_log_has_url"] = ~missing_url.loc[audit.index]
    out = audit.groupby(["unitid", "target_year"], as_index=False).agg(
        in_raw_legacy_change_log_exact_year=("unitid", "size"),
        raw_change_log_has_url=("raw_change_log_has_url", "max"),
    )
    out["in_raw_legacy_change_log_exact_year"] = out["in_raw_legacy_change_log_exact_year"].gt(0)
    return out


def build_legacy_bridge_flags(legacy_links: pd.DataFrame, *, workbook_label: str) -> pd.DataFrame:
    if legacy_links.empty:
        return pd.DataFrame(columns=["unitid", "target_year"])
    links = legacy_links.loc[legacy_links["legacy_workbook"].map(clean_text).eq(workbook_label)].copy()
    if links.empty:
        return pd.DataFrame(columns=["unitid", "target_year"])
    links["target_year"] = pd.to_numeric(links["target_year"], errors="coerce").astype("Int64")
    links["has_legacy_url"] = links["legacy_url"].map(clean_text).str.startswith(("http://", "https://"))
    links["selected_prior"] = bool_series(links.get("selected_as_prior_evidence", pd.Series(False, index=links.index)))
    out = links.groupby(["unitid", "target_year"], as_index=False).agg(
        in_legacy_evidence_bridge_exact_year=("unitid", "size"),
        bridge_has_human_url=("has_legacy_url", "max"),
        bridge_selected_prior=("selected_prior", "max"),
    )
    out["in_legacy_evidence_bridge_exact_year"] = out["in_legacy_evidence_bridge_exact_year"].gt(0)
    return out


def build_current_panel_flags(year_panel: pd.DataFrame) -> pd.DataFrame:
    if year_panel.empty:
        return pd.DataFrame(columns=["unitid", "target_year"])
    current = year_panel.copy()
    year_column = "start_year" if "start_year" in current.columns else "target_year"
    current["target_year"] = pd.to_numeric(current[year_column], errors="coerce").astype("Int64")
    current["current_panel_row_present"] = True
    current["current_has_best_url"] = current.get("best_url", pd.Series("", index=current.index)).map(clean_text).ne("")
    current = current.sort_values(["unitid", "target_year", "current_has_best_url"], ascending=[True, True, False])
    current = current.drop_duplicates(["unitid", "target_year"], keep="first")
    keep = [
        "unitid",
        "target_year",
        "current_panel_row_present",
        "current_has_best_url",
        "best_url",
        "best_url_source",
        "best_url_status",
        "pipeline_stage",
        "stop_reason",
        "next_batch_action",
    ]
    for column in keep:
        if column not in current.columns:
            current[column] = ""
    return current[keep].rename(
        columns={
            "best_url": "current_best_url",
            "best_url_source": "current_best_url_source",
            "best_url_status": "current_best_url_status",
        }
    )


def build_catalog_flags(catalog_db: pd.DataFrame, *, stream_id: str) -> pd.DataFrame:
    if catalog_db.empty:
        return pd.DataFrame(columns=["unitid", "target_year"])
    if "source_stream" in catalog_db.columns:
        catalog_db = catalog_db.loc[catalog_db["source_stream"].map(clean_text).eq(stream_id)].copy()
    else:
        catalog_db = catalog_db.copy()
    if catalog_db.empty:
        return pd.DataFrame(columns=["unitid", "target_year"])
    catalog_db["target_year"] = pd.to_numeric(catalog_db["target_year"], errors="coerce").astype("Int64")
    catalog_db["catalog_db_row_present"] = True
    catalog_db["catalog_db_has_best_url"] = catalog_db.get("best_url", pd.Series("", index=catalog_db.index)).map(clean_text).ne("")
    catalog_db["policy_extraction_ready"] = bool_series(
        catalog_db.get("policy_extraction_ready", pd.Series(False, index=catalog_db.index))
    )
    catalog_db = catalog_db.sort_values(
        ["unitid", "target_year", "catalog_db_has_best_url", "policy_extraction_ready"],
        ascending=[True, True, False, False],
    ).drop_duplicates(["unitid", "target_year"], keep="first")
    keep = [
        "unitid",
        "target_year",
        "catalog_db_row_present",
        "catalog_db_has_best_url",
        "best_url",
        "policy_extraction_ready",
        "source_scope_type",
        "review_gate",
        "scope_review_flag",
    ]
    for column in keep:
        if column not in catalog_db.columns:
            catalog_db[column] = ""
    return catalog_db[keep].rename(columns={"best_url": "catalog_db_best_url"})


def build_classification_flags(classification: pd.DataFrame) -> pd.DataFrame:
    if classification.empty:
        return pd.DataFrame(columns=["unitid", "target_year"])
    out = classification.copy()
    year_values = out["target_year"] if "target_year" in out.columns else out.get("start_year")
    out["target_year"] = pd.to_numeric(year_values, errors="coerce").astype("Int64")
    out["classification_row_present"] = True
    out["api_parsed"] = out.get("api_status", pd.Series("", index=out.index)).map(clean_text).eq("parsed")
    out["api_policy_class_clean"] = out.get("api_policy_class", pd.Series("", index=out.index)).map(clean_text)
    out["api_most_generous_legacy_policy_class_clean"] = out.get(
        "api_most_generous_legacy_policy_class",
        pd.Series("", index=out.index),
    ).map(clean_text)
    out["api_has_most_generous_legacy_policy_class"] = out[
        "api_most_generous_legacy_policy_class_clean"
    ].isin(INFORMATIVE_CLASSES)
    out["api_has_policy_class"] = out["api_policy_class_clean"].isin(INFORMATIVE_CLASSES)
    out["coded_policy_class_clean"] = out.get("coded_policy_class", pd.Series("", index=out.index)).map(clean_text)
    out["coded_has_policy_class"] = out["coded_policy_class_clean"].isin(INFORMATIVE_CLASSES)
    out["classification_policy_class_clean"] = out["api_most_generous_legacy_policy_class_clean"].where(
        out["api_has_most_generous_legacy_policy_class"],
        out["api_policy_class_clean"].where(
            out["api_has_policy_class"],
            out["coded_policy_class_clean"].where(
                out["coded_has_policy_class"],
                out["api_policy_class_clean"].where(out["api_policy_class_clean"].ne(""), out["coded_policy_class_clean"]),
            ),
        ),
    )
    out["classification_has_informative_class"] = out["classification_policy_class_clean"].isin(INFORMATIVE_CLASSES)
    out = out.sort_values(
        [
            "unitid",
            "target_year",
            "classification_has_informative_class",
            "api_parsed",
            "api_has_most_generous_legacy_policy_class",
            "api_has_policy_class",
        ],
        ascending=[True, True, False, False, False, False],
    ).drop_duplicates(["unitid", "target_year"], keep="first")
    keep = [
        "unitid",
        "target_year",
        "classification_row_present",
        "api_parsed",
        "api_has_policy_class",
        "api_has_most_generous_legacy_policy_class",
        "classification_has_informative_class",
        "source_retrieval_status",
        "text_extract_status",
        "policy_search_status",
        "api_status",
        "api_policy_class",
        "api_most_generous_legacy_policy_class",
        "coded_policy_class",
        "classification_policy_class_clean",
        "api_grade_forgiveness",
        "api_grade_averaging",
        "manual_audit_status",
        "api_needs_human_review",
        "_classification_source_file",
    ]
    for column in keep:
        if column not in out.columns:
            out[column] = ""
    return out[keep].rename(
        columns={
            "text_extract_status": "classification_text_extract_status",
            "policy_search_status": "classification_policy_search_status",
            "api_status": "classification_api_status",
        }
    )


def build_loss_audit_flags(loss_audit: pd.DataFrame) -> pd.DataFrame:
    if loss_audit.empty:
        return pd.DataFrame(columns=["unitid", "target_year"])
    out = loss_audit.copy()
    out["target_year"] = pd.to_numeric(out["target_year"], errors="coerce").astype("Int64")
    out["loss_audit_row_present"] = True
    out["strict_usable_gf_ga"] = bool_series(out.get("is_informative_gf_ga_both", pd.Series(False, index=out.index)))
    if "has_classification_row" in out.columns:
        out["_has_classification_row"] = bool_series(out["has_classification_row"])
    else:
        out["_has_classification_row"] = False
    out = out.sort_values(
        ["unitid", "target_year", "strict_usable_gf_ga", "_has_classification_row"],
        ascending=[True, True, False, False],
    ).drop_duplicates(["unitid", "target_year"], keep="first")
    keep = [
        "unitid",
        "target_year",
        "loss_audit_row_present",
        "loss_bucket",
        "rescue_priority",
        "strict_usable_gf_ga",
        "is_informative_gf_ga_both",
        "has_classification_row",
    ]
    for column in keep:
        if column not in out.columns:
            out[column] = ""
    return out[keep]


def build_attrition(
    old_panel: pd.DataFrame,
    *,
    workbook_label: str = "public",
    stream_id: str = "public_legacy_url",
    raw_legacy_audit: pd.DataFrame | None = None,
    raw_public_audit: pd.DataFrame | None = None,
    legacy_links: pd.DataFrame | None = None,
    current_year_panel: pd.DataFrame | None = None,
    catalog_db: pd.DataFrame | None = None,
    classification: pd.DataFrame | None = None,
    loss_audit: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if old_panel.empty:
        return pd.DataFrame()
    if raw_legacy_audit is None:
        raw_legacy_audit = raw_public_audit if raw_public_audit is not None else pd.DataFrame()
    legacy_links = legacy_links if legacy_links is not None else pd.DataFrame()
    current_year_panel = current_year_panel if current_year_panel is not None else pd.DataFrame()
    catalog_db = catalog_db if catalog_db is not None else pd.DataFrame()
    classification = classification if classification is not None else pd.DataFrame()
    loss_audit = loss_audit if loss_audit is not None else pd.DataFrame()
    has_loss_audit_source = not loss_audit.empty
    out = old_panel.copy()
    out = out.merge(build_raw_change_log_flags(raw_legacy_audit), on=["unitid", "target_year"], how="left")
    out = out.merge(
        build_legacy_bridge_flags(legacy_links, workbook_label=workbook_label),
        on=["unitid", "target_year"],
        how="left",
    )
    out = out.merge(build_current_panel_flags(current_year_panel), on=["unitid", "target_year"], how="left")
    out = out.merge(build_catalog_flags(catalog_db, stream_id=stream_id), on=["unitid", "target_year"], how="left")
    out = out.merge(build_classification_flags(classification), on=["unitid", "target_year"], how="left")
    out = out.merge(build_loss_audit_flags(loss_audit), on=["unitid", "target_year"], how="left")

    bool_columns = [
        "has_grad_outcome",
        "in_current_target_window_2000_2020",
        "in_raw_legacy_change_log_exact_year",
        "raw_change_log_has_url",
        "in_legacy_evidence_bridge_exact_year",
        "bridge_has_human_url",
        "bridge_selected_prior",
        "current_panel_row_present",
        "current_has_best_url",
        "catalog_db_row_present",
        "catalog_db_has_best_url",
        "policy_extraction_ready",
        "classification_row_present",
        "api_parsed",
        "api_has_policy_class",
        "classification_has_informative_class",
        "loss_audit_row_present",
        "strict_usable_gf_ga",
    ]
    for column in bool_columns:
        if column not in out.columns:
            out[column] = False
        out[column] = bool_series(out[column])
    if has_loss_audit_source:
        out["strict_usable_gf_ga"] = out["strict_usable_gf_ga"] | out["classification_has_informative_class"]
    else:
        out["strict_usable_gf_ga"] = out["classification_has_informative_class"]
    out["current_any_url_for_year"] = out["current_has_best_url"] | out["catalog_db_has_best_url"]
    out = add_policy_spell_coverage(out)
    out["attrition_stage"] = out.apply(attrition_stage, axis=1)
    return out


def policy_signature(row: pd.Series) -> tuple[str, ...]:
    return tuple(clean_text(row.get(column)) for column in POLICY_SIGNATURE_COLUMNS)


def add_policy_spell_coverage(attrition: pd.DataFrame) -> pd.DataFrame:
    """Add expansion-aware policy spell coverage across contiguous old-panel rows."""
    if attrition.empty:
        return attrition
    out = attrition.copy()
    for column in POLICY_SIGNATURE_COLUMNS:
        if column not in out.columns:
            out[column] = ""
    ordered = out.sort_values(["unitid", "target_year"]).copy()
    spell_by_index: dict[int, int] = {}
    last_unitid: int | None = None
    last_year: int | None = None
    last_signature: tuple[str, ...] | None = None
    spell_id = -1
    for idx, row in ordered.iterrows():
        unitid = int(row["unitid"])
        year = int(row["target_year"])
        signature = policy_signature(row)
        starts_new_spell = (
            unitid != last_unitid
            or last_year is None
            or year != last_year + 1
            or signature != last_signature
        )
        if starts_new_spell:
            spell_id += 1
        spell_by_index[idx] = spell_id
        last_unitid = unitid
        last_year = year
        last_signature = signature

    out["policy_spell_id"] = pd.Series(spell_by_index)
    grouped = out.groupby("policy_spell_id", dropna=False)
    out["policy_spell_start_year"] = grouped["target_year"].transform("min")
    out["policy_spell_end_year"] = grouped["target_year"].transform("max")
    out["policy_spell_panel_rows"] = grouped["target_year"].transform("size")
    spell_metrics = [
        ("current_any_url_for_year", "policy_spell_has_url"),
        ("policy_extraction_ready", "policy_spell_has_policy_extraction_ready"),
        ("classification_row_present", "policy_spell_has_classification_row"),
        ("api_parsed", "policy_spell_has_api_parsed"),
        ("api_has_policy_class", "policy_spell_has_api_has_policy_class"),
        ("classification_has_informative_class", "policy_spell_has_classification_informative_class"),
        ("strict_usable_gf_ga", "policy_spell_has_strict_usable_gf_ga"),
    ]
    for source_column, spell_column in spell_metrics:
        if source_column not in out.columns:
            out[source_column] = False
        values = bool_series(out[source_column])
        out[spell_column] = values.groupby(out["policy_spell_id"]).transform("max")
    return out


def attrition_stage(row: pd.Series) -> str:
    if not bool(row.get("in_current_target_window_2000_2020", False)):
        return "00_outside_current_2000_2020_scope"
    if not bool(row.get("current_panel_row_present", False)):
        return "01_missing_from_current_legacy_panel"
    if not bool(row.get("current_any_url_for_year", False)):
        return "02_current_panel_year_but_no_best_url"
    if not bool(row.get("policy_extraction_ready", False)):
        return "03_has_url_but_not_policy_extraction_ready"
    if not bool(row.get("classification_row_present", False)):
        return "04_extraction_or_policy_search_did_not_make_classification_row"
    if bool(row.get("strict_usable_gf_ga", False)):
        return "07_strict_usable_gf_ga"
    if not bool(row.get("api_parsed", False)):
        return "05_classification_row_but_api_not_parsed"
    return "06_classified_but_not_strict_usable_gf_ga"


def summarize_attrition(attrition: pd.DataFrame, *, sector: str = "public") -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    def add_denominator(label: str, mask: pd.Series) -> None:
        denominator = attrition.loc[mask]
        n = len(denominator)
        rows.append({"denominator": label, "metric": "denominator", "count": n, "percent_of_denominator": 100.0 if n else 0.0})
        metrics = [
            ("in_raw_legacy_change_log_exact_year", "in_raw_legacy_change_log_exact_year"),
            ("in_legacy_evidence_bridge_exact_year", "in_legacy_evidence_bridge_exact_year"),
            ("has_grad_outcome", "has_grad_outcome"),
            ("current_panel_row_present", "current_panel_row_present"),
            ("current_any_url_for_year", "current_any_url_for_year"),
            ("policy_extraction_ready", "policy_extraction_ready"),
            ("classification_row_present", "classification_row_present"),
            ("api_parsed", "api_parsed"),
            ("strict_usable_gf_ga", "strict_usable_gf_ga"),
            ("classification_has_informative_class", "classification_has_informative_class"),
            ("policy_spell_has_url", "policy_spell_has_url"),
            ("policy_spell_has_policy_extraction_ready", "policy_spell_has_policy_extraction_ready"),
            ("policy_spell_has_classification_row", "policy_spell_has_classification_row"),
            ("policy_spell_has_api_parsed", "policy_spell_has_api_parsed"),
            ("policy_spell_has_api_has_policy_class", "policy_spell_has_api_has_policy_class"),
            ("policy_spell_has_classification_informative_class", "policy_spell_has_classification_informative_class"),
            ("policy_spell_has_strict_usable_gf_ga", "policy_spell_has_strict_usable_gf_ga"),
        ]
        for metric, column in metrics:
            count = int(attrition.loc[denominator.index, column].sum()) if n else 0
            pct = round(100 * count / n, 1) if n else 0.0
            rows.append({"denominator": label, "metric": metric, "count": count, "percent_of_denominator": pct})
        stage_counts = denominator["attrition_stage"].value_counts().sort_index()
        for stage, count in stage_counts.items():
            rows.append(
                {
                    "denominator": label,
                    "metric": f"attrition_stage:{stage}",
                    "count": int(count),
                    "percent_of_denominator": round(100 * int(count) / n, 1) if n else 0.0,
                }
            )

    all_mask = pd.Series(True, index=attrition.index)
    in_scope = attrition["in_current_target_window_2000_2020"]
    outcome_valid = in_scope & attrition["has_grad_outcome"]
    add_denominator(f"old_gfdatafull_{sector}_valid_policy_all_years", all_mask)
    add_denominator(f"old_gfdatafull_{sector}_valid_policy_2000_2020", in_scope)
    add_denominator(f"old_gfdatafull_{sector}_valid_policy_2000_2020_with_grad_outcome", outcome_valid)
    return pd.DataFrame(rows)


def write_markdown_summary(
    path: Path,
    summary: pd.DataFrame,
    *,
    sector: str,
    stream_id: str,
    attrition_csv: Path,
    summary_csv: Path,
    priority_csv: Path,
) -> None:
    lookup = {
        (row["denominator"], row["metric"]): row
        for _, row in summary.iterrows()
    }
    denominator = f"old_gfdatafull_{sector}_valid_policy_2000_2020"
    outcome_denominator = f"old_gfdatafull_{sector}_valid_policy_2000_2020_with_grad_outcome"

    def value(denom: str, metric: str, field: str = "count") -> object:
        row = lookup.get((denom, metric))
        return "" if row is None else row[field]

    lines = [
        f"# gfdatafull {sector.title()} Legacy Panel Benchmark",
        "",
        f"Generated at: {utc_now()}",
        f"Stream: `{stream_id}`",
        "",
        "## Benchmark Rule",
        "",
        f"The denominator is the old downstream `gfdatafull` {sector} valid-policy panel. Raw student change-log rows are diagnostic context only; they are not the coverage denominator.",
        "",
        "## Main Benchmark",
        "",
        f"- Old {sector} valid-policy panel rows, 2000-2020: {value(denominator, 'denominator')}",
        f"- Current legacy panel rows present: {value(denominator, 'current_panel_row_present')} ({value(denominator, 'current_panel_row_present', 'percent_of_denominator')}%)",
        f"- Current rows with any URL: {value(denominator, 'current_any_url_for_year')} ({value(denominator, 'current_any_url_for_year', 'percent_of_denominator')}%)",
        f"- Classification rows present: {value(denominator, 'classification_row_present')} ({value(denominator, 'classification_row_present', 'percent_of_denominator')}%)",
        f"- Informative local/API classification rows: {value(denominator, 'classification_has_informative_class')} ({value(denominator, 'classification_has_informative_class', 'percent_of_denominator')}%)",
        f"- Strict usable GF/GA rows: {value(denominator, 'strict_usable_gf_ga')} ({value(denominator, 'strict_usable_gf_ga', 'percent_of_denominator')}%)",
        "",
        "## Policy-Spell Coverage",
        "",
        "These metrics respect the old panel expansion: if one row in a contiguous same-policy spell has coverage, every row in that old policy spell is counted as covered for this diagnostic.",
        "",
        f"- Policy-spell source URL coverage: {value(denominator, 'policy_spell_has_url')} ({value(denominator, 'policy_spell_has_url', 'percent_of_denominator')}%)",
        f"- Policy-spell extraction-ready coverage: {value(denominator, 'policy_spell_has_policy_extraction_ready')} ({value(denominator, 'policy_spell_has_policy_extraction_ready', 'percent_of_denominator')}%)",
        f"- Policy-spell classification coverage: {value(denominator, 'policy_spell_has_classification_row')} ({value(denominator, 'policy_spell_has_classification_row', 'percent_of_denominator')}%)",
        f"- Policy-spell informative API coverage: {value(denominator, 'policy_spell_has_api_has_policy_class')} ({value(denominator, 'policy_spell_has_api_has_policy_class', 'percent_of_denominator')}%)",
        f"- Policy-spell informative local/API coverage: {value(denominator, 'policy_spell_has_classification_informative_class')} ({value(denominator, 'policy_spell_has_classification_informative_class', 'percent_of_denominator')}%)",
        "",
        "## Outcome-Valid Subset",
        "",
        f"- Old {sector} valid-policy rows with graduation outcomes: {value(outcome_denominator, 'denominator')}",
        f"- Current rows with any URL: {value(outcome_denominator, 'current_any_url_for_year')} ({value(outcome_denominator, 'current_any_url_for_year', 'percent_of_denominator')}%)",
        f"- Classification rows present: {value(outcome_denominator, 'classification_row_present')} ({value(outcome_denominator, 'classification_row_present', 'percent_of_denominator')}%)",
        f"- Informative local/API classification rows: {value(outcome_denominator, 'classification_has_informative_class')} ({value(outcome_denominator, 'classification_has_informative_class', 'percent_of_denominator')}%)",
        f"- Strict usable GF/GA rows: {value(outcome_denominator, 'strict_usable_gf_ga')} ({value(outcome_denominator, 'strict_usable_gf_ga', 'percent_of_denominator')}%)",
        f"- Policy-spell source URL coverage: {value(outcome_denominator, 'policy_spell_has_url')} ({value(outcome_denominator, 'policy_spell_has_url', 'percent_of_denominator')}%)",
        f"- Policy-spell classification coverage: {value(outcome_denominator, 'policy_spell_has_classification_row')} ({value(outcome_denominator, 'policy_spell_has_classification_row', 'percent_of_denominator')}%)",
        f"- Policy-spell informative local/API coverage: {value(outcome_denominator, 'policy_spell_has_classification_informative_class')} ({value(outcome_denominator, 'policy_spell_has_classification_informative_class', 'percent_of_denominator')}%)",
        "",
        "## Artifacts",
        "",
        f"- Row-level attrition: `{attrition_csv}`",
        f"- Summary table: `{summary_csv}`",
        f"- Policy-spell classification priority queue: `{priority_csv}`",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def first_nonblank(values: pd.Series) -> str:
    for value in values:
        text = clean_text(value)
        if text:
            return text
    return ""


def source_id_for_url(url: str) -> str:
    return "policy-src-" + hashlib.sha256(clean_text(url).encode("utf-8")).hexdigest()[:16]


def is_pdf_url(url: str) -> bool:
    lowered = clean_text(url).lower().split("?", 1)[0]
    return lowered.endswith(".pdf")


def has_any_hint(url: str, hints: tuple[str, ...]) -> bool:
    lowered = clean_text(url).lower()
    return any(hint in lowered for hint in hints)


def numeric_cache_value(value: object) -> int:
    number = pd.to_numeric(pd.Series([value]), errors="coerce").fillna(0).iloc[0]
    return int(number)


def source_cache_lookup(source_audit_cache: pd.DataFrame) -> dict[str, dict[str, object]]:
    if source_audit_cache.empty or "policy_source_id" not in source_audit_cache.columns:
        return {}
    out: dict[str, dict[str, object]] = {}
    for _, row in source_audit_cache.iterrows():
        out[clean_text(row.get("policy_source_id"))] = row.to_dict()
    return out


def same_spell_candidate_score(candidate: dict[str, object]) -> int:
    """Rank alternate URLs inside a known same-policy spell.

    Cached excerpts are best. Failed/empty/shell pages are worst. Untested
    direct catalog PDFs beat a representative that was already tried and
    produced no policy terms.
    """
    url = clean_text(candidate.get("url"))
    retrieval_status = clean_text(candidate.get("retrieval_status"))
    if retrieval_status not in {"retrieved", "retrieved_truncated"} and quote_url_path(url) != url:
        retrieval_status = ""
    excerpt_count = numeric_cache_value(candidate.get("policy_excerpt_count"))
    text_chars = numeric_cache_value(candidate.get("text_char_count"))
    score = 0
    if bool(candidate.get("policy_extraction_ready")):
        score += 2_000
    if excerpt_count > 0:
        score += 1_000_000 + min(excerpt_count, 50) * 1_000
    elif not retrieval_status:
        score += 50_000
    elif retrieval_status in {"retrieved", "retrieved_truncated"}:
        score += 20_000 + min(text_chars, 5_000)
        if text_chars < 5_000:
            score -= 40_000
    else:
        score -= 80_000
    if is_pdf_url(url):
        score += 25_000
    if has_any_hint(url, DIRECT_CATALOG_HINTS):
        score += 8_000
    if has_any_hint(url, SHELL_SOURCE_HINTS):
        score -= 55_000
    if "x-goog-" in url.lower():
        score -= 25_000
    return score


def quote_url_path(url: str) -> str:
    parsed = urlparse(clean_text(url))
    if not parsed.scheme or not parsed.netloc:
        return url
    path = quote(unquote(parsed.path), safe="/:%@")
    query = quote(unquote(parsed.query), safe="=&?/:+,%@")
    return urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, query, parsed.fragment))


def candidate_source_from_row(
    row: pd.Series,
    *,
    cache_by_source_id: dict[str, dict[str, object]],
    representative_target_year: int,
) -> dict[str, object]:
    url = clean_text(row.get("current_best_url")) or clean_text(row.get("catalog_db_best_url"))
    source_id = source_id_for_url(url)
    cache = cache_by_source_id.get(source_id, {})
    target_year = int(row["target_year"])
    candidate = {
        "target_year": target_year,
        "url": url,
        "policy_source_id": source_id,
        "policy_extraction_ready": bool(row.get("policy_extraction_ready", False)),
        "retrieval_status": clean_text(cache.get("retrieval_status")),
        "text_extract_status": clean_text(cache.get("text_extract_status")),
        "text_char_count": numeric_cache_value(cache.get("text_char_count")),
        "policy_excerpt_count": numeric_cache_value(cache.get("policy_excerpt_count")),
        "policy_terms_found": clean_text(cache.get("policy_terms_found")),
        "source_audit_cache_path": clean_text(cache.get("_source_audit_cache_path")),
        "year_distance_from_representative": abs(target_year - representative_target_year),
    }
    candidate["selection_score"] = same_spell_candidate_score(candidate)
    return candidate


def select_same_spell_source_candidate(
    group: pd.DataFrame,
    *,
    representative: pd.Series,
    source_audit_cache: pd.DataFrame | None = None,
    cache_by_source_id: dict[str, dict[str, object]] | None = None,
) -> dict[str, object]:
    if cache_by_source_id is None:
        cache_by_source_id = source_cache_lookup(source_audit_cache if source_audit_cache is not None else pd.DataFrame())
    representative_year = int(representative["target_year"])
    candidate_rows = group.loc[
        bool_series(group["policy_extraction_ready"])
        & (
            group.get("current_best_url", pd.Series("", index=group.index)).map(clean_text).ne("")
            | group.get("catalog_db_best_url", pd.Series("", index=group.index)).map(clean_text).ne("")
        )
    ].copy()
    if candidate_rows.empty:
        candidate_rows = pd.DataFrame([representative])
    candidates = [
        candidate_source_from_row(row, cache_by_source_id=cache_by_source_id, representative_target_year=representative_year)
        for _, row in candidate_rows.iterrows()
    ]
    candidates = [candidate for candidate in candidates if clean_text(candidate.get("url"))]
    if not candidates:
        return candidate_source_from_row(
            representative,
            cache_by_source_id=cache_by_source_id,
            representative_target_year=representative_year,
        )
    candidates.sort(
        key=lambda candidate: (
            int(candidate.get("selection_score", 0)),
            -int(candidate.get("year_distance_from_representative", 0)),
            -int(candidate.get("target_year", 0)),
        ),
        reverse=True,
    )
    return candidates[0]


def load_source_audit_cache(repo_root: Path, stream_id: str) -> pd.DataFrame:
    patterns = [f"catalog_policy_source_text_audit_production_queue_{stream_id}_*.csv"]
    if stream_id == "public_legacy_url":
        patterns.append("catalog_policy_source_text_audit_production_queue_public_legacy_*.csv")
    frames = []
    for pattern in patterns:
        for path in (repo_root / INTERIM_DIR).glob(pattern):
            try:
                frame = pd.read_csv(path, low_memory=False)
            except (pd.errors.EmptyDataError, UnicodeDecodeError):
                continue
            if "policy_source_id" not in frame.columns:
                continue
            frame["_source_audit_cache_path"] = str(path.resolve())
            frames.append(frame)
    if not frames:
        return pd.DataFrame()
    cache = pd.concat(frames, ignore_index=True, sort=False)
    cache["policy_excerpt_count_num"] = pd.to_numeric(cache.get("policy_excerpt_count"), errors="coerce").fillna(0)
    cache["text_char_count_num"] = pd.to_numeric(cache.get("text_char_count"), errors="coerce").fillna(0)
    status = cache.get("retrieval_status", pd.Series("", index=cache.index)).map(clean_text)
    retrieved = status.isin({"retrieved", "retrieved_truncated"})
    cache["_cache_score"] = (
        cache["policy_excerpt_count_num"].gt(0).astype(int) * 1_000_000
        + retrieved.astype(int) * 100_000
        + cache["text_char_count_num"].clip(upper=99_999)
    )
    return (
        cache.sort_values(["policy_source_id", "_cache_score"])
        .drop_duplicates("policy_source_id", keep="last")
        .drop(columns=["_cache_score"])
        .reset_index(drop=True)
    )


def policy_spell_work_bucket(row: pd.Series) -> str:
    if not clean_text(row.get("source_retrieval_status")):
        return "needs_source_retrieval"
    excerpt_count = int(row.get("cached_policy_excerpt_count", 0) or 0)
    text_chars = int(row.get("cached_text_char_count", 0) or 0)
    retrieval_status = clean_text(row.get("source_retrieval_status"))
    if excerpt_count > 0:
        return "cached_policy_terms_ready_for_classification"
    if retrieval_status in {"retrieved", "retrieved_truncated"}:
        if text_chars < 5_000:
            return "cached_retrieved_short_or_empty_no_terms"
        return "cached_retrieved_long_text_no_terms"
    return "cached_retrieval_failed"


def build_policy_spell_priority_queue(attrition: pd.DataFrame, *, source_audit_cache: pd.DataFrame | None = None) -> pd.DataFrame:
    if attrition.empty:
        return pd.DataFrame()
    source_audit_cache = source_audit_cache if source_audit_cache is not None else pd.DataFrame()
    cache_by_source_id = source_cache_lookup(source_audit_cache)
    in_scope = attrition.loc[bool_series(attrition["in_current_target_window_2000_2020"])].copy()
    if in_scope.empty:
        return pd.DataFrame()
    rows = []
    total_panel_rows = len(in_scope)
    spell_groups = in_scope.groupby("policy_spell_id", dropna=False)
    for spell_id, group in spell_groups:
        group = group.sort_values("target_year")
        ready_rows = group.loc[bool_series(group["policy_extraction_ready"])].copy()
        representative = ready_rows.iloc[0] if not ready_rows.empty else group.iloc[0]
        selected_source = select_same_spell_source_candidate(
            group,
            representative=representative,
            cache_by_source_id=cache_by_source_id,
        )
        representative_url = clean_text(representative.get("current_best_url")) or clean_text(representative.get("catalog_db_best_url"))
        panel_rows = len(group)
        rows.append(
            {
                "policy_spell_id": int(spell_id),
                "unitid": int(group["unitid"].iloc[0]),
                "institution_name": first_nonblank(group.get("instnm", pd.Series(dtype=object))) or first_nonblank(group.get("institution_name", pd.Series(dtype=object))),
                "spell_start_year": int(group["target_year"].min()),
                "spell_end_year": int(group["target_year"].max()),
                "spell_panel_rows": panel_rows,
                "spell_outcome_valid_rows": int(bool_series(group["has_grad_outcome"]).sum()),
                "policy_signature_avg": first_nonblank(group["avg"]),
                "policy_signature_gradeavg": first_nonblank(group["gradeavg"]),
                "policy_signature_forgive": first_nonblank(group["forgive"]),
                "policy_signature_gradeforgive": first_nonblank(group["gradeforgive"]),
                "spell_has_url": bool(group["policy_spell_has_url"].iloc[0]),
                "spell_extraction_ready": bool(group["policy_spell_has_policy_extraction_ready"].iloc[0]),
                "spell_has_classification": bool(group["policy_spell_has_classification_row"].iloc[0]),
                "spell_api_parsed": bool(group["policy_spell_has_api_parsed"].iloc[0]),
                "spell_api_informative": bool(group["policy_spell_has_api_has_policy_class"].iloc[0]),
                "spell_informative_classification": bool(group["policy_spell_has_classification_informative_class"].iloc[0]),
                "spell_strict_usable_gf_ga": bool(group["policy_spell_has_strict_usable_gf_ga"].iloc[0]),
                "representative_target_year": int(representative["target_year"]),
                "representative_best_url": representative_url,
                "representative_best_url_source": clean_text(representative.get("current_best_url_source")) or clean_text(representative.get("best_url_source")),
                "selected_target_year": int(selected_source["target_year"]),
                "selected_best_url": clean_text(selected_source["url"]),
                "selected_policy_source_id": clean_text(selected_source["policy_source_id"]),
                "selected_source_selection_score": int(selected_source["selection_score"]),
                "selected_source_retrieval_status": clean_text(selected_source["retrieval_status"]),
                "selected_source_text_extract_status": clean_text(selected_source["text_extract_status"]),
                "selected_cached_text_char_count": int(selected_source["text_char_count"]),
                "selected_cached_policy_excerpt_count": int(selected_source["policy_excerpt_count"]),
                "selected_policy_terms_found": clean_text(selected_source["policy_terms_found"]),
                "selected_source_audit_cache_path": clean_text(selected_source["source_audit_cache_path"]),
                "same_spell_alternate_selected": bool(
                    int(selected_source["target_year"]) != int(representative["target_year"])
                    or clean_text(selected_source["url"]) != representative_url
                ),
                "target_years_in_spell": ";".join(str(int(year)) for year in group["target_year"]),
            }
        )
    spells = pd.DataFrame(rows)
    if spells.empty:
        return spells
    spells["representative_policy_source_id"] = spells["representative_best_url"].map(source_id_for_url)
    if not source_audit_cache.empty and "policy_source_id" in source_audit_cache.columns:
        keep = [
            "policy_source_id",
            "retrieval_status",
            "http_status",
            "content_type",
            "text_extract_status",
            "text_char_count",
            "policy_excerpt_count",
            "policy_terms_found",
            "_source_audit_cache_path",
        ]
        cache = source_audit_cache[[column for column in keep if column in source_audit_cache.columns]].copy()
        spells = spells.merge(
            cache,
            left_on="representative_policy_source_id",
            right_on="policy_source_id",
            how="left",
        )
    for column in ["retrieval_status", "text_extract_status", "policy_terms_found", "_source_audit_cache_path"]:
        if column not in spells.columns:
            spells[column] = ""
    spells["cached_text_char_count"] = pd.to_numeric(spells.get("text_char_count"), errors="coerce").fillna(0).astype(int)
    spells["cached_policy_excerpt_count"] = pd.to_numeric(spells.get("policy_excerpt_count"), errors="coerce").fillna(0).astype(int)
    spells = spells.rename(
        columns={
            "retrieval_status": "source_retrieval_status",
            "text_extract_status": "source_text_extract_status",
            "_source_audit_cache_path": "source_audit_cache_path",
        }
    )
    spells["policy_spell_work_bucket"] = spells.apply(policy_spell_work_bucket, axis=1)
    current_classed_panel_rows = int(spells.loc[spells["spell_has_classification"], "spell_panel_rows"].sum())
    current_informative_panel_rows = int(spells.loc[spells["spell_informative_classification"], "spell_panel_rows"].sum())
    need_for_70 = max(0, math.ceil(total_panel_rows * 0.70) - current_informative_panel_rows)
    need_for_80 = max(0, math.ceil(total_panel_rows * 0.80) - current_informative_panel_rows)
    queue = spells.loc[spells["spell_extraction_ready"] & ~spells["spell_informative_classification"]].copy()
    bucket_order = {
        "cached_policy_terms_ready_for_classification": 0,
        "needs_source_retrieval": 1,
        "cached_retrieved_short_or_empty_no_terms": 2,
        "cached_retrieved_long_text_no_terms": 3,
        "cached_retrieval_failed": 4,
    }
    queue["_work_bucket_order"] = queue["policy_spell_work_bucket"].map(bucket_order).fillna(9).astype(int)
    queue = queue.sort_values(
        ["spell_panel_rows", "spell_outcome_valid_rows", "_work_bucket_order", "institution_name"],
        ascending=[False, False, True, True],
    )
    queue["priority_rank"] = range(1, len(queue) + 1)
    queue["cumulative_panel_rows_if_classified"] = queue["spell_panel_rows"].cumsum()
    queue["needed_to_reach_70pct_panel_classification"] = queue["cumulative_panel_rows_if_classified"].le(need_for_70) | (
        queue["cumulative_panel_rows_if_classified"].sub(queue["spell_panel_rows"]).lt(need_for_70)
    )
    queue["needed_to_reach_80pct_panel_classification"] = queue["cumulative_panel_rows_if_classified"].le(need_for_80) | (
        queue["cumulative_panel_rows_if_classified"].sub(queue["spell_panel_rows"]).lt(need_for_80)
    )
    queue.insert(0, "total_panel_rows", total_panel_rows)
    queue.insert(1, "current_spell_classified_panel_rows", current_classed_panel_rows)
    queue.insert(2, "current_spell_informative_panel_rows", current_informative_panel_rows)
    queue.insert(3, "panel_rows_needed_for_70pct", need_for_70)
    queue.insert(4, "panel_rows_needed_for_80pct", need_for_80)
    return queue.drop(columns=["_work_bucket_order"], errors="ignore")


def run(
    repo_root: Path,
    *,
    sector: str = "public",
    gfdatafull_path: Path | None = None,
    current_year_panel_path: Path | None = None,
    catalog_db_path: Path | None = None,
    classification_path: Path | None = None,
    loss_audit_path: Path | None = None,
    legacy_links_path: Path | None = None,
    audit_path: Path | None = None,
    public_audit_path: Path | None = None,
    output_dir: Path | None = None,
) -> GfdatafullBenchmarkOutputs:
    repo_root = repo_root.resolve()
    if sector not in SECTOR_CONFIGS:
        raise ValueError(f"Unknown sector: {sector}. Expected one of {sorted(SECTOR_CONFIGS)}")
    config = SECTOR_CONFIGS[sector]

    def resolve_path(path: Path | None, default: Path | None = None) -> Path | None:
        selected = path if path is not None else default
        if selected is None:
            return None
        return selected if selected.is_absolute() else repo_root / selected

    output_dir = resolve_path(output_dir, DEFAULT_OUTPUT_DIR)
    assert output_dir is not None
    output_dir.mkdir(parents=True, exist_ok=True)

    gf_path = resolve_path(gfdatafull_path, DEFAULT_GFDATAFULL)
    assert gf_path is not None
    old_panel = load_old_policy_panel(gf_path, config)
    if old_panel.empty:
        raise FileNotFoundError(f"Missing or empty gfdatafull benchmark panel: {gf_path}")

    if classification_path is None:
        default_classification = resolve_path(None, config.classification_path)
        classification_paths = [default_classification] if default_classification is not None else []
        classification_paths.extend(
            sorted((repo_root / DELIVERY_DIR).glob(f"policy_classification_production_excerpt_{config.stream_id}*_api_*.csv"))
        )
        classification = read_csv_many(classification_paths)
    else:
        classification = read_csv_if_exists(resolve_path(classification_path))

    audit_source = audit_path if audit_path is not None else public_audit_path
    attrition = build_attrition(
        old_panel,
        workbook_label=config.workbook_label,
        stream_id=config.stream_id,
        raw_legacy_audit=read_csv_if_exists(resolve_path(audit_source, config.audit_path)),
        legacy_links=read_csv_if_exists(resolve_path(legacy_links_path, DEFAULT_LEGACY_LINKS)),
        current_year_panel=read_csv_if_exists(resolve_path(current_year_panel_path, config.year_panel_path)),
        catalog_db=read_csv_if_exists(resolve_path(catalog_db_path, DEFAULT_CATALOG_DB)),
        classification=classification,
        loss_audit=read_csv_if_exists(resolve_path(loss_audit_path, config.loss_audit_path)),
    )
    summary = summarize_attrition(attrition, sector=config.sector)

    attrition_csv = (output_dir / f"{config.output_prefix}.csv").resolve()
    summary_csv = (output_dir / f"{config.output_prefix}_summary.csv").resolve()
    summary_md = (output_dir / f"{config.output_prefix}_summary.md").resolve()
    priority_csv = (output_dir / f"gfdatafull_{config.sector}_policy_spell_classification_priority.csv").resolve()
    attrition.to_csv(attrition_csv, index=False)
    summary.to_csv(summary_csv, index=False)
    source_cache = load_source_audit_cache(repo_root, config.stream_id)
    build_policy_spell_priority_queue(attrition, source_audit_cache=source_cache).to_csv(priority_csv, index=False)
    write_markdown_summary(
        summary_md,
        summary,
        sector=config.sector,
        stream_id=config.stream_id,
        attrition_csv=attrition_csv,
        summary_csv=summary_csv,
        priority_csv=priority_csv,
    )
    return GfdatafullBenchmarkOutputs(
        attrition_csv=attrition_csv,
        summary_csv=summary_csv,
        summary_md=summary_md,
        policy_spell_priority_csv=priority_csv,
    )


def run_all(
    repo_root: Path,
    *,
    sectors: tuple[str, ...] = ("public", "private"),
    gfdatafull_path: Path | None = None,
    catalog_db_path: Path | None = None,
    legacy_links_path: Path | None = None,
    output_dir: Path | None = None,
) -> dict[str, GfdatafullBenchmarkOutputs]:
    return {
        sector: run(
            repo_root,
            sector=sector,
            gfdatafull_path=gfdatafull_path,
            catalog_db_path=catalog_db_path,
            legacy_links_path=legacy_links_path,
            output_dir=output_dir,
        )
        for sector in sectors
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--sector", choices=sorted(SECTOR_CONFIGS), default="public")
    parser.add_argument("--all-sectors", action="store_true")
    parser.add_argument("--gfdatafull", type=Path, default=None)
    parser.add_argument("--current-year-panel", type=Path, default=None)
    parser.add_argument("--catalog-db", type=Path, default=None)
    parser.add_argument("--classification", type=Path, default=None)
    parser.add_argument("--loss-audit", type=Path, default=None)
    parser.add_argument("--legacy-links", type=Path, default=None)
    parser.add_argument("--audit", type=Path, default=None)
    parser.add_argument("--public-audit", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = repo_root_from_cwd(args.root)
    if args.all_sectors:
        outputs_by_sector = run_all(
            repo_root,
            sectors=tuple(SECTOR_CONFIGS),
            gfdatafull_path=args.gfdatafull,
            catalog_db_path=args.catalog_db,
            legacy_links_path=args.legacy_links,
            output_dir=args.output_dir,
        )
        for sector, outputs in outputs_by_sector.items():
            for label, path in outputs.__dict__.items():
                print(f"{sector}_{label}: {path}")
    else:
        outputs = run(
            repo_root,
            sector=args.sector,
            gfdatafull_path=args.gfdatafull,
            current_year_panel_path=args.current_year_panel,
            catalog_db_path=args.catalog_db,
            classification_path=args.classification,
            loss_audit_path=args.loss_audit,
            legacy_links_path=args.legacy_links,
            audit_path=args.audit,
            public_audit_path=args.public_audit,
            output_dir=args.output_dir,
        )
        for label, path in outputs.__dict__.items():
            print(f"{label}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
