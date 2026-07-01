"""Build one harmonized catalog URL database across current public/private runs."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote

import pandas as pd

from .ai_config import repo_root_from_cwd
from .benchmark_protocol import protocol_for_stream
from .production_streams import get_stream
from .public_fresh_discovery_pipeline import excel_safe_frame


INTERNAL_DATA_DIR = Path("artifacts/policy_data_internal")
DELIVERY_DIR = Path("../policy_data")
OUTPUT_STEM = "catalog_url_database"


@dataclass(frozen=True)
class HarmonizedInput:
    source_stream: str
    sector_stream: str
    candidate_paths: tuple[Path, ...]
    url_column: str = "best_url"
    year_column: str = "target_year"
    source_column: str = "best_url_source"
    status_column: str = "best_url_status"
    required: bool = True


@dataclass(frozen=True)
class HarmonizedOutputs:
    workbook: Path
    database_csv: Path
    institution_status_csv: Path
    scope_qc_csv: Path
    summary_md: Path


def current_inputs(
    repo_root: Path,
    *,
    include_review_gated_private_new: bool = True,
    include_clean_holdout: bool = False,
    only_clean_holdout: bool = False,
) -> list[HarmonizedInput]:
    delivery = (repo_root / DELIVERY_DIR).resolve()
    review = repo_root / INTERNAL_DATA_DIR / "review"
    archive = repo_root / INTERNAL_DATA_DIR / "archive" / "front_folder_cleanup_2026_06_10"
    clean_holdout_inputs = [
        HarmonizedInput(
            source_stream="public_clean_no_legacy_holdout",
            sector_stream="public",
            candidate_paths=(review / "streams/public_clean_no_legacy_holdout/current/year_panel.csv",),
            required=False,
        ),
        HarmonizedInput(
            source_stream="private_clean_no_legacy_holdout",
            sector_stream="private",
            candidate_paths=(review / "streams/private_clean_no_legacy_holdout/current/year_panel.csv",),
            required=False,
        ),
    ]
    if only_clean_holdout:
        return clean_holdout_inputs
    inputs = [
        HarmonizedInput(
            source_stream="public_legacy_url",
            sector_stream="public",
            candidate_paths=(
                review / "streams/public_legacy_url/current/year_panel.csv",
                review / "public/current/public_year_panel.csv",
                archive / "public_year_panel_legacy_recovered.csv",
                delivery / "public_year_panel_legacy_recovered.csv",
            ),
            year_column="start_year",
        ),
        HarmonizedInput(
            source_stream="public_fresh_discovery",
            sector_stream="public",
            candidate_paths=(
                review / "streams/public_fresh_discovery/current/year_panel.csv",
                archive / "public_fresh_discovery_rollup_year_panel.csv",
                delivery / "public_fresh_discovery_rollup_year_panel.csv",
            ),
            url_column="final_best_url",
            source_column="final_best_url_source",
            status_column="final_status",
        ),
        HarmonizedInput(
            source_stream="private_human_legacy_url",
            sector_stream="private",
            candidate_paths=(
                review / "streams/private_human_legacy_url/current/year_panel.csv",
                review / "private/current/private_year_panel.csv",
                archive / "private_year_panel_legacy_recovered.csv",
                delivery / "private_year_panel_legacy_recovered.csv",
            ),
            year_column="start_year",
        ),
        HarmonizedInput(
            source_stream="private_fresh_discovery",
            sector_stream="private",
            candidate_paths=(
                review / "streams/private_fresh_discovery/current/year_panel.csv",
            ),
            required=False,
        ),
    ]
    if include_review_gated_private_new:
        inputs.append(
            HarmonizedInput(
                source_stream="private_new_legacy_url",
                sector_stream="private",
                candidate_paths=(
                    review / "streams/private_new_legacy_url/current/year_panel.csv",
                    review / "private_step0_llm_year_panel_private_step0_llm_all374_v1.csv",
                    repo_root
                    / INTERNAL_DATA_DIR
                    / "audits/legacy_benchmark_current/private_step0_llm_year_panel_private_step0_llm_all374_v1.csv",
                    delivery / "private_step0_llm_year_panel_private_step0_llm_all374_v1.csv",
                ),
            )
        )
    if include_clean_holdout:
        inputs.extend(clean_holdout_inputs)
    return inputs


def clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def first_existing(row: pd.Series, names: list[str]) -> str:
    for name in names:
        if name in row.index:
            value = clean_text(row.get(name))
            if value:
                return value
    return ""


def resolve_input_path(input_spec: HarmonizedInput) -> Path | None:
    for path in input_spec.candidate_paths:
        if path.exists():
            return path
    if not input_spec.required:
        return None
    candidates = "\n".join(f"- {path}" for path in input_spec.candidate_paths)
    raise FileNotFoundError(f"Missing generated source file for {input_spec.source_stream}. Tried:\n{candidates}")


def source_trust_level(source_stream: str) -> str:
    if source_stream in {"public_legacy_url", "private_human_legacy_url"}:
        return "human_legacy_prior"
    if source_stream in {"public_fresh_discovery", "private_fresh_discovery"}:
        return "pipeline_discovered"
    if source_stream in {"public_clean_no_legacy_holdout", "private_clean_no_legacy_holdout"}:
        return "benchmark_holdout_discovered"
    if source_stream == "private_new_legacy_url":
        return "unverified_suggestion"
    return "unknown"


def review_gate_for_row(
    *,
    source_stream: str,
    scope_review_flag: str,
    best_url: str,
) -> str:
    if clean_text(scope_review_flag):
        return clean_text(scope_review_flag)
    if source_stream == "private_new_legacy_url" and clean_text(best_url):
        return "verify_official_scope_catalog_year_and_source_type"
    return ""


def catalog_evidence_ready(
    *,
    source_stream: str,
    best_url: str,
    scope_review_flag: str,
) -> bool:
    if not clean_text(best_url):
        return False
    if clean_text(scope_review_flag):
        return False
    if source_stream == "private_new_legacy_url":
        return False
    return True


def policy_extraction_ready(
    *,
    source_stream: str,
    best_url: str,
    scope_review_flag: str,
    source_scope_type: str,
) -> bool:
    if not clean_text(best_url):
        return False
    if source_stream == "private_new_legacy_url":
        return False
    protocol = protocol_for_stream(source_stream)
    if protocol.name == "known_url_execution_diagnostic":
        return True
    if clean_text(scope_review_flag):
        return False
    return source_scope_type in {"catalog_confirmed", "catalog_and_handbook"}


def normalize_panel(input_spec: HarmonizedInput) -> pd.DataFrame:
    path = resolve_input_path(input_spec)
    if path is None:
        return pd.DataFrame()
    raw = pd.read_csv(path, low_memory=False)
    stream = get_stream(input_spec.source_stream)
    rows = []
    for _, row in raw.iterrows():
        target_year = row.get(input_spec.year_column, row.get("year", row.get("start_year", row.get("target_year", ""))))
        url = clean_text(row.get(input_spec.url_column))
        source = clean_text(row.get(input_spec.source_column))
        status = clean_text(row.get(input_spec.status_column))
        link_text = first_existing(row, ["catalog_title_or_link_text", "candidate_link_text", "candidate_link_text_x", "candidate_link_text_y"])
        evidence_text = first_existing(row, ["candidate_evidence_text", "comments", "candidate_evidence_source"])
        archive_url = first_existing(row, ["archive_url", "archive_url_x", "archive_url_y"])
        legacy_url = clean_text(row.get("legacy_url"))
        preferred_root = clean_text(row.get("preferred_source_root_url"))
        existing_flag = clean_text(row.get("scope_review_flag"))
        scope_type, scope_flag = classify_scope(
            best_url=url,
            link_text=link_text,
            evidence_text=evidence_text,
            existing_scope_flag=existing_flag,
        )
        row_review_gate = review_gate_for_row(
            source_stream=input_spec.source_stream,
            scope_review_flag=scope_flag,
            best_url=url,
        )
        protocol = protocol_for_stream(input_spec.source_stream)
        ready_for_catalog = catalog_evidence_ready(
            source_stream=input_spec.source_stream,
            best_url=url,
            scope_review_flag=scope_flag,
        )
        ready_for_policy = policy_extraction_ready(
            source_stream=input_spec.source_stream,
            best_url=url,
            scope_review_flag=scope_flag,
            source_scope_type=scope_type,
        )
        rows.append(
            {
                "source_stream": input_spec.source_stream,
                "sector_stream": input_spec.sector_stream,
                "source_family": stream.source_family,
                "source_seed_types": "; ".join(stream.source_seed_types),
                "source_trust_level": source_trust_level(input_spec.source_stream),
                "benchmark_protocol": protocol.name,
                "counts_as_clean_no_legacy_benchmark": protocol.counts_as_clean_no_legacy,
                "requires_source_review": bool(row_review_gate),
                "review_gate": row_review_gate,
                "stream_status": stream.status,
                "catalog_evidence_ready": ready_for_catalog,
                "policy_extraction_ready": ready_for_policy,
                "unitid": int(row["unitid"]),
                "institution_name": clean_text(row.get("institution_name")),
                "state": first_existing(row, ["state", "state_x", "state_y"]),
                "target_year": int(float(target_year)) if clean_text(target_year) else pd.NA,
                "best_url": url,
                "best_url_source": source,
                "best_url_status": status or ("candidate_found" if url else "missing"),
                "source_scope_type": scope_type,
                "scope_review_flag": scope_flag,
                "catalog_title_or_link_text": link_text,
                "candidate_evidence_text": evidence_text,
                "archive_url": archive_url,
                "legacy_url": legacy_url,
                "preferred_source_root_url": preferred_root,
                "pipeline_stage": clean_text(row.get("pipeline_stage")),
                "stop_reason": clean_text(row.get("stop_reason")),
                "next_batch_action": clean_text(row.get("next_batch_action")),
                "retrieval_status": clean_text(row.get("retrieval_status")),
                "direct_http_status": clean_text(row.get("direct_http_status")),
                "direct_final_url": clean_text(row.get("direct_final_url")),
                "source_input_file": path.name,
                "source_input_path": str(path.resolve()),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    return pd.DataFrame(rows)


def classification_evidence(best_url: str, link_text: str, evidence_text: str) -> str:
    return unquote(f"{best_url} {link_text} {evidence_text}").lower()


def classify_scope(
    *,
    best_url: str,
    link_text: str = "",
    evidence_text: str = "",
    existing_scope_flag: str = "",
) -> tuple[str, str]:
    if not clean_text(best_url):
        return "missing_url", ""
    evidence = classification_evidence(best_url, link_text, evidence_text)
    catalogish = bool(re.search(r"(?:catalogs?|catalogue|bulletin|course[_-]?catalog|academic[_-]?catalog|ug[_-]?cat|ugrad)", evidence))
    handbook = "handbook" in evidence
    policyish = "policy" in evidence or "policies" in evidence
    nonacademic = bool(
        re.search(
            r"privacy|copyright|hipaa|drug\s*and\s*alcohol|plagiarism|refund|information\s*security|employee[\s_-]*handbook|public\s*policy\s*research|no_relevant_section_found|no relevant section found",
            evidence,
        )
    )
    if nonacademic and not catalogish:
        return "nonacademic_policy_or_wrong_scope", "exclude_from_catalog_coverage_review"
    if catalogish and handbook:
        return "catalog_and_handbook", ""
    if catalogish:
        return "catalog_confirmed", ""
    if handbook or existing_scope_flag == "handbook_possible_policy_source_not_catalog_confirmed":
        return "student_handbook_possible_policy_source", "handbook_possible_policy_source_not_catalog_confirmed"
    if policyish:
        return "policy_page_possible_policy_source", "policy_page_possible_policy_source_not_catalog_confirmed"
    return "unknown_scope", "scope_not_confirmed"


def build_institution_status(database: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (stream, unitid, name), group in database.groupby(["source_stream", "unitid", "institution_name"], dropna=False):
        with_url = group["best_url"].fillna("").astype(str).str.strip().ne("")
        rows.append(
            {
                "source_stream": stream,
                "unitid": int(unitid),
                "institution_name": name,
                "sector_stream": group["sector_stream"].iloc[0],
                "institution_year_rows": int(len(group)),
                "years_with_url": int(with_url.sum()),
                "coverage_pct": round(100 * with_url.sum() / len(group), 1) if len(group) else 0,
                "scope_types": "; ".join(sorted(group.loc[with_url, "source_scope_type"].dropna().astype(str).unique())),
                "scope_flags": "; ".join(sorted(flag for flag in group["scope_review_flag"].dropna().astype(str).unique() if flag)),
            }
        )
    return pd.DataFrame(rows).sort_values(["sector_stream", "source_stream", "institution_name", "unitid"])


def build_scope_qc(database: pd.DataFrame) -> pd.DataFrame:
    rows = []
    rows.append({"metric": "rows", "value": int(len(database))})
    rows.append({"metric": "institutions", "value": int(database["unitid"].nunique())})
    rows.append({"metric": "rows_with_url", "value": int(database["best_url"].fillna("").astype(str).str.strip().ne("").sum())})
    if "catalog_evidence_ready" in database.columns:
        rows.append({"metric": "rows_catalog_evidence_ready", "value": int(database["catalog_evidence_ready"].fillna(False).astype(bool).sum())})
    if "policy_extraction_ready" in database.columns:
        rows.append({"metric": "rows_policy_extraction_ready", "value": int(database["policy_extraction_ready"].fillna(False).astype(bool).sum())})
    if "requires_source_review" in database.columns:
        rows.append({"metric": "rows_requiring_source_review", "value": int(database["requires_source_review"].fillna(False).astype(bool).sum())})
    for scope, count in database["source_scope_type"].value_counts(dropna=False).sort_index().items():
        rows.append({"metric": f"source_scope_type:{scope}", "value": int(count)})
    for flag, count in database.loc[database["scope_review_flag"].fillna("").astype(str).str.strip().ne(""), "scope_review_flag"].value_counts().sort_index().items():
        rows.append({"metric": f"scope_review_flag:{flag}", "value": int(count)})
    if "review_gate" in database.columns:
        for gate, count in database.loc[database["review_gate"].fillna("").astype(str).str.strip().ne(""), "review_gate"].value_counts().sort_index().items():
            rows.append({"metric": f"review_gate:{gate}", "value": int(count)})
    for stream, group in database.groupby("source_stream"):
        rows.append({"metric": f"stream_rows:{stream}", "value": int(len(group))})
        rows.append({"metric": f"stream_rows_with_url:{stream}", "value": int(group["best_url"].fillna("").astype(str).str.strip().ne("").sum())})
    return pd.DataFrame(rows)


def output_paths(delivery: Path, output_stem: str = OUTPUT_STEM) -> HarmonizedOutputs:
    return HarmonizedOutputs(
        workbook=delivery / f"{output_stem}.xlsx",
        database_csv=delivery / f"{output_stem}.csv",
        institution_status_csv=delivery / f"{output_stem}_institution_status.csv",
        scope_qc_csv=delivery / f"{output_stem}_scope_qc.csv",
        summary_md=delivery / f"{output_stem}_summary.md",
    )


def write_summary(path: Path, database: pd.DataFrame, scope_qc: pd.DataFrame, outputs: HarmonizedOutputs) -> None:
    rows_with_url = int(database["best_url"].fillna("").astype(str).str.strip().ne("").sum())
    catalog_ready = int(database.get("catalog_evidence_ready", pd.Series(dtype=bool)).fillna(False).astype(bool).sum())
    policy_ready = int(database.get("policy_extraction_ready", pd.Series(dtype=bool)).fillna(False).astype(bool).sum())
    review_required = int(database.get("requires_source_review", pd.Series(dtype=bool)).fillna(False).astype(bool).sum())
    lines = [
        "# Catalog URL Database",
        "",
        f"Generated at: {datetime.now(timezone.utc).isoformat()}",
        "",
        "Scope: harmonized year-level catalog/source URL database across current public/private production streams. This does not overwrite stream-specific provenance files.",
        "",
        "## Bottom Line",
        "",
        f"- Rows: {len(database)}",
        f"- Institutions: {database['unitid'].nunique()}",
        f"- Rows with URL: {rows_with_url} ({round(100 * rows_with_url / len(database), 1)}%)",
        f"- Rows ready as catalog evidence: {catalog_ready}",
        f"- Rows ready for policy extraction: {policy_ready}",
        f"- Rows requiring source review before production use: {review_required}",
        "",
        "## Streams",
        "",
    ]
    for stream, group in database.groupby("source_stream"):
        url_count = int(group["best_url"].fillna("").astype(str).str.strip().ne("").sum())
        ready_count = int(group["catalog_evidence_ready"].fillna(False).astype(bool).sum())
        review_count = int(group["requires_source_review"].fillna(False).astype(bool).sum())
        lines.append(
            f"- {stream}: {len(group)} rows, {url_count} with URL, {ready_count} catalog-ready, {review_count} review-gated"
        )
    lines.extend([
        "",
        "## Scope Types",
        "",
    ])
    for scope, count in database["source_scope_type"].value_counts().sort_index().items():
        lines.append(f"- {scope}: {int(count)}")
    lines.extend(["", "## Scope Review Flags", ""])
    flags = database.loc[database["scope_review_flag"].fillna("").astype(str).str.strip().ne(""), "scope_review_flag"].value_counts().sort_index()
    if flags.empty:
        lines.append("- none")
    else:
        for flag, count in flags.items():
            lines.append(f"- {flag}: {int(count)}")
    lines.extend(["", "## Outputs", ""])
    for label, output_path in outputs.__dict__.items():
        lines.append(f"- {label}: `{output_path}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(
    repo_root: Path,
    *,
    output_stem: str = OUTPUT_STEM,
    include_review_gated_private_new: bool = True,
    include_clean_holdout: bool = False,
    only_clean_holdout: bool = False,
) -> HarmonizedOutputs:
    delivery = (repo_root / DELIVERY_DIR).resolve()
    delivery.mkdir(parents=True, exist_ok=True)
    frames = []
    for input_spec in current_inputs(
        repo_root,
        include_review_gated_private_new=include_review_gated_private_new,
        include_clean_holdout=include_clean_holdout,
        only_clean_holdout=only_clean_holdout,
    ):
        frame = normalize_panel(input_spec)
        if not frame.empty:
            frames.append(frame)
    if not frames:
        raise FileNotFoundError("No catalog URL stream inputs were available to harmonize.")
    database = pd.concat(frames, ignore_index=True, sort=False).sort_values(
        ["sector_stream", "source_stream", "institution_name", "unitid", "target_year"]
    )
    institution_status = build_institution_status(database)
    scope_qc = build_scope_qc(database)
    outputs = output_paths(delivery, output_stem)
    database.to_csv(outputs.database_csv, index=False)
    institution_status.to_csv(outputs.institution_status_csv, index=False)
    scope_qc.to_csv(outputs.scope_qc_csv, index=False)
    with pd.ExcelWriter(outputs.workbook, engine="openpyxl") as writer:
        for sheet, frame in {
            "scope_qc": scope_qc,
            "institution_status": institution_status,
            "catalog_url_database": database,
            "review_flag_rows": database.loc[database["scope_review_flag"].fillna("").astype(str).str.strip().ne("")],
        }.items():
            excel_safe_frame(frame).to_excel(writer, sheet_name=sheet[:31], index=False)
    write_summary(outputs.summary_md, database, scope_qc, outputs)
    return outputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--output-stem", default=OUTPUT_STEM)
    parser.add_argument(
        "--exclude-review-gated-private-new",
        action="store_true",
        help="Rebuild without the review-gated private automated/new-legacy stream.",
    )
    parser.add_argument(
        "--include-clean-holdout",
        action="store_true",
        help="Also include clean no-legacy benchmark holdout streams in the harmonized database.",
    )
    parser.add_argument(
        "--only-clean-holdout",
        action="store_true",
        help="Build a benchmark-only database from clean no-legacy holdout streams.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = args.root.resolve() if args.root else repo_root_from_cwd()
    outputs = run(
        repo_root,
        output_stem=args.output_stem,
        include_review_gated_private_new=not args.exclude_review_gated_private_new,
        include_clean_holdout=args.include_clean_holdout,
        only_clean_holdout=args.only_clean_holdout,
    )
    for label, output_path in outputs.__dict__.items():
        print(f"{label}: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
