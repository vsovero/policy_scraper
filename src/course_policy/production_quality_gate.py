"""Quality gate for production policy extraction/classification blocks."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from pandas.errors import EmptyDataError

from .ai_config import repo_root_from_cwd


DATA_DIR = Path("artifacts/policy_data_internal")
INTERIM_DIR = DATA_DIR / "interim"
REVIEW_DIR = DATA_DIR / "review"
LOG_DIR = DATA_DIR / "logs"
DELIVERY_DIR = Path("../policy_data")

INFORMATIVE_CLASSES = {"grade_forgiveness", "grade_averaging", "both_or_ambiguous"}
WEAK_CLASSES = {"unknown", "no_relevant_policy", "wrong_scope", "blank", ""}


@dataclass(frozen=True)
class QualityGateThresholds:
    min_policy_term_rate: float = 0.50
    min_informative_reviewed_rate: float = 0.35
    min_informative_classified_rate: float = 0.60
    min_source_retrieval_rate: float = 0.85
    max_api_error_rate: float = 0.02
    max_short_text_no_terms_rate: float = 0.15
    min_substantive_text_chars: int = 5_000
    min_reviewed_rows_for_fail: int = 25


@dataclass(frozen=True)
class QualityGateResult:
    status: str
    metrics: dict[str, object]
    checks: list[dict[str, object]]

    @property
    def failed(self) -> bool:
        return self.status == "FAIL"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_csv_if_exists(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, low_memory=False)
    except EmptyDataError:
        return pd.DataFrame()


def bool_rate(numerator: int, denominator: int) -> float:
    return float(numerator / denominator) if denominator else 0.0


def safe_numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce")


def normalized_class_series(frame: pd.DataFrame) -> pd.Series:
    if "api_policy_class" not in frame.columns:
        return pd.Series([], dtype="object")
    return frame["api_policy_class"].fillna("").astype(str).str.strip()


def normalized_status_series(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series("", index=frame.index, dtype="object")
    return frame[column].fillna("").astype(str).str.strip()


def source_audit_path(repo_root: Path, source_slug: str, chunk_label: str) -> Path:
    return repo_root / INTERIM_DIR / f"catalog_policy_source_text_audit_production_queue_{source_slug}_{chunk_label}.csv"


def quality_gate_stem(source_slug: str, block_label: str, api_mode: str) -> str:
    return f"policy_classification_production_excerpt_{source_slug}_{block_label}_api_{api_mode}_quality_gate"


def evaluate_quality_gate(
    *,
    year_reviews: list[pd.DataFrame],
    source_audits: list[pd.DataFrame],
    combined: pd.DataFrame,
    thresholds: QualityGateThresholds = QualityGateThresholds(),
) -> QualityGateResult:
    year_review = pd.concat(year_reviews, ignore_index=True, sort=False) if year_reviews else pd.DataFrame()
    source_audit = pd.concat(source_audits, ignore_index=True, sort=False) if source_audits else pd.DataFrame()

    reviewed_rows = len(year_review)
    policy_terms_rows = (
        int(normalized_status_series(year_review, "policy_search_status").eq("policy_terms_found").sum())
        if not year_review.empty
        else 0
    )
    no_terms_rows = (
        int(normalized_status_series(year_review, "policy_search_status").eq("no_policy_terms_found").sum())
        if not year_review.empty
        else 0
    )

    source_attempts = len(source_audit)
    retrieved_statuses = {"retrieved", "retrieved_truncated"}
    source_retrieved = (
        int(normalized_status_series(source_audit, "retrieval_status").isin(retrieved_statuses).sum())
        if not source_audit.empty
        else 0
    )

    no_terms_short_text_rows = 0
    no_terms_substantive_text_rows = 0
    if not year_review.empty and not source_audit.empty and "policy_source_id" in year_review.columns:
        source_cols = ["policy_source_id"]
        for col in ["retrieval_status", "text_char_count", "policy_excerpt_count"]:
            if col in source_audit.columns:
                source_cols.append(col)
        source_one = source_audit[source_cols].copy()
        if "text_char_count" in source_one.columns:
            source_one["_text_chars"] = pd.to_numeric(source_one["text_char_count"], errors="coerce")
        else:
            source_one["_text_chars"] = pd.NA
        if "policy_excerpt_count" in source_one.columns:
            source_one["_excerpt_count"] = pd.to_numeric(source_one["policy_excerpt_count"], errors="coerce")
        else:
            source_one["_excerpt_count"] = pd.NA
        source_one["_retrieved"] = normalized_status_series(source_one, "retrieval_status").isin(retrieved_statuses)
        source_one = source_one.sort_values(
            ["policy_source_id", "_retrieved", "_text_chars"],
            ascending=[True, False, False],
        ).drop_duplicates("policy_source_id", keep="first")
        merged = year_review.merge(
            source_one[["policy_source_id", "_text_chars", "_excerpt_count", "_retrieved"]],
            on="policy_source_id",
            how="left",
        )
        no_terms = normalized_status_series(merged, "policy_search_status").eq("no_policy_terms_found")
        no_terms_short_text_rows = int(
            (no_terms & merged["_retrieved"].fillna(False) & merged["_text_chars"].fillna(0).lt(thresholds.min_substantive_text_chars)).sum()
        )
        no_terms_substantive_text_rows = int(
            (no_terms & merged["_retrieved"].fillna(False) & merged["_text_chars"].fillna(0).ge(thresholds.min_substantive_text_chars)).sum()
        )

    classification_rows = len(combined)
    classes = normalized_class_series(combined)
    informative_rows = int(classes.isin(INFORMATIVE_CLASSES).sum()) if classification_rows else 0
    weak_rows = int(classes.fillna("").isin(WEAK_CLASSES).sum()) if classification_rows else 0
    api_status = normalized_status_series(combined, "api_status")
    api_error_rows = int(api_status.eq("error").sum()) if classification_rows else 0
    api_blank_or_unparsed_rows = int(api_status.eq("").sum()) if classification_rows else 0

    metrics: dict[str, object] = {
        "reviewed_rows": reviewed_rows,
        "policy_terms_rows": policy_terms_rows,
        "no_terms_rows": no_terms_rows,
        "policy_term_rate": bool_rate(policy_terms_rows, reviewed_rows),
        "source_attempts": source_attempts,
        "source_retrieved": source_retrieved,
        "source_retrieval_rate": bool_rate(source_retrieved, source_attempts),
        "no_terms_short_text_rows": no_terms_short_text_rows,
        "no_terms_substantive_text_rows": no_terms_substantive_text_rows,
        "short_text_no_terms_rate": bool_rate(no_terms_short_text_rows, reviewed_rows),
        "classification_rows": classification_rows,
        "informative_rows": informative_rows,
        "informative_reviewed_rate": bool_rate(informative_rows, reviewed_rows),
        "informative_classified_rate": bool_rate(informative_rows, classification_rows),
        "weak_classification_rows": weak_rows,
        "weak_classification_reviewed_rate": bool_rate(weak_rows, reviewed_rows),
        "api_error_rows": api_error_rows,
        "api_error_rate": bool_rate(api_error_rows, classification_rows),
        "api_blank_or_unparsed_rows": api_blank_or_unparsed_rows,
    }

    enforce_fail = reviewed_rows >= thresholds.min_reviewed_rows_for_fail
    checks = [
        {
            "check": "policy_term_rate",
            "value": metrics["policy_term_rate"],
            "threshold": thresholds.min_policy_term_rate,
            "operator": ">=",
            "status": "PASS" if metrics["policy_term_rate"] >= thresholds.min_policy_term_rate else ("FAIL" if enforce_fail else "WARN"),
            "message": "Share of reviewed institution-years with policy terms.",
        },
        {
            "check": "informative_reviewed_rate",
            "value": metrics["informative_reviewed_rate"],
            "threshold": thresholds.min_informative_reviewed_rate,
            "operator": ">=",
            "status": "PASS"
            if metrics["informative_reviewed_rate"] >= thresholds.min_informative_reviewed_rate
            else ("FAIL" if enforce_fail else "WARN"),
            "message": "Share of reviewed institution-years classified as GF, GA, or both/ambiguous.",
        },
        {
            "check": "informative_classified_rate",
            "value": metrics["informative_classified_rate"],
            "threshold": thresholds.min_informative_classified_rate,
            "operator": ">=",
            "status": "PASS"
            if classification_rows == 0 or metrics["informative_classified_rate"] >= thresholds.min_informative_classified_rate
            else ("FAIL" if enforce_fail else "WARN"),
            "message": "Share of classified rows with an informative GF/GA class.",
        },
        {
            "check": "source_retrieval_rate",
            "value": metrics["source_retrieval_rate"],
            "threshold": thresholds.min_source_retrieval_rate,
            "operator": ">=",
            "status": "PASS"
            if source_attempts == 0 or metrics["source_retrieval_rate"] >= thresholds.min_source_retrieval_rate
            else ("FAIL" if enforce_fail else "WARN"),
            "message": "Share of source retrieval attempts that produced retrievable content.",
        },
        {
            "check": "short_text_no_terms_rate",
            "value": metrics["short_text_no_terms_rate"],
            "threshold": thresholds.max_short_text_no_terms_rate,
            "operator": "<=",
            "status": "PASS"
            if metrics["short_text_no_terms_rate"] <= thresholds.max_short_text_no_terms_rate
            else ("FAIL" if enforce_fail else "WARN"),
            "message": "Share of reviewed rows with no policy terms and landing-page-like short extracted text.",
        },
        {
            "check": "api_error_rate",
            "value": metrics["api_error_rate"],
            "threshold": thresholds.max_api_error_rate,
            "operator": "<=",
            "status": "PASS"
            if classification_rows == 0 or metrics["api_error_rate"] <= thresholds.max_api_error_rate
            else ("FAIL" if enforce_fail else "WARN"),
            "message": "Share of classified rows with API errors.",
        },
    ]
    statuses = {str(check["status"]) for check in checks}
    status = "FAIL" if "FAIL" in statuses else ("WARN" if "WARN" in statuses else "PASS")
    return QualityGateResult(status=status, metrics=metrics, checks=checks)


def write_quality_gate_report(
    repo_root: Path,
    *,
    source_slug: str,
    block_label: str,
    api_mode: str,
    result: QualityGateResult,
) -> tuple[Path, Path, Path]:
    stem = quality_gate_stem(source_slug, block_label, api_mode)
    internal_csv = (repo_root / REVIEW_DIR / f"{stem}.csv").resolve()
    internal_md = (repo_root / LOG_DIR / f"{stem}.md").resolve()
    delivery_md = (repo_root / DELIVERY_DIR / f"{stem}.md").resolve()
    for path in [internal_csv, internal_md, delivery_md]:
        path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for check in result.checks:
        rows.append(
            {
                "status": check["status"],
                "check": check["check"],
                "value": check["value"],
                "operator": check["operator"],
                "threshold": check["threshold"],
                "message": check["message"],
            }
        )
    checks = pd.DataFrame(rows)
    checks.to_csv(internal_csv, index=False)

    lines = [
        "# Policy Production Quality Gate",
        "",
        f"Generated at: {utc_now()}",
        f"Source stream: `{source_slug}`",
        f"Block: `{block_label}`",
        f"API mode: `{api_mode}`",
        f"Status: **{result.status}**",
        "",
        "## Metrics",
        "",
    ]
    for key, value in result.metrics.items():
        if isinstance(value, float):
            lines.append(f"- {key}: {value:.3f}")
        else:
            lines.append(f"- {key}: {value}")
    lines.extend(["", "## Checks", ""])
    for check in result.checks:
        value = check["value"]
        value_text = f"{value:.3f}" if isinstance(value, float) else str(value)
        lines.append(
            f"- {check['status']}: {check['check']} {value_text} {check['operator']} {check['threshold']} - {check['message']}"
        )
    lines.extend(
        [
            "",
            "## Gate Meaning",
            "",
            "A failed gate means broad automation should stop before starting the next block. Run a targeted source/excerpt/classification rescue, then rerun a bounded validation slice before resuming.",
        ]
    )
    internal_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    delivery_md.write_text(internal_md.read_text(encoding="utf-8"), encoding="utf-8")
    return internal_csv, internal_md, delivery_md


def run_quality_gate_for_block(
    repo_root: Path,
    *,
    source_slug: str,
    start_row: int,
    total_rows: int,
    chunk_labels: list[str],
    api_mode: str,
    combined_path: Path,
    thresholds: QualityGateThresholds = QualityGateThresholds(),
) -> tuple[QualityGateResult, Path, Path, Path]:
    end_row = start_row + total_rows - 1
    block_label = f"{start_row:03d}_{end_row:03d}"
    year_reviews = [
        read_csv_if_exists(repo_root / REVIEW_DIR / f"catalog_policy_excerpt_year_review_production_queue_{source_slug}_{label}.csv")
        for label in chunk_labels
    ]
    source_audits = [read_csv_if_exists(source_audit_path(repo_root, source_slug, label)) for label in chunk_labels]
    combined = read_csv_if_exists(combined_path)
    result = evaluate_quality_gate(
        year_reviews=year_reviews,
        source_audits=source_audits,
        combined=combined,
        thresholds=thresholds,
    )
    paths = write_quality_gate_report(
        repo_root,
        source_slug=source_slug,
        block_label=block_label,
        api_mode=api_mode,
        result=result,
    )
    return result, *paths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--source-slug", required=True)
    parser.add_argument("--start-row", type=int, required=True)
    parser.add_argument("--total-rows", type=int, required=True)
    parser.add_argument("--chunk-label", action="append", dest="chunk_labels", required=True)
    parser.add_argument("--api-mode", default="live")
    parser.add_argument("--combined-path", type=Path, required=True)
    parser.add_argument("--enforce", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = repo_root_from_cwd(args.root)
    combined = args.combined_path if args.combined_path.is_absolute() else repo_root / args.combined_path
    result, _, report, _ = run_quality_gate_for_block(
        repo_root,
        source_slug=args.source_slug,
        start_row=args.start_row,
        total_rows=args.total_rows,
        chunk_labels=args.chunk_labels,
        api_mode=args.api_mode,
        combined_path=combined,
    )
    print(f"quality_gate_status: {result.status}")
    print(f"quality_gate_report: {report}")
    return 2 if args.enforce and result.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
