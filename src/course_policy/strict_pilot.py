"""Build a smaller strict Phase 3 pilot for source-coverage protocol development."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .ai_config import repo_root_from_cwd
from .catalog_retrieval import (
    DEFAULT_TIMEOUT_SECONDS,
    build_coverage,
    build_retrieval_attempts,
)
from .institution_universe import TARGET_END_YEAR, TARGET_START_YEAR


DATA_DIR = Path("../data_policy_pipeline")
INTERIM_DIR = DATA_DIR / "interim"
LOG_DIR = DATA_DIR / "logs"

INSTITUTION_UNIVERSE_INPUT = INTERIM_DIR / "institution_universe.csv"
INSTITUTION_YEAR_TARGETS_INPUT = INTERIM_DIR / "institution_year_targets.csv"
LEGACY_EVIDENCE_LINKS_INPUT = INTERIM_DIR / "legacy_evidence_links.csv"

STRICT_INSTITUTIONS_OUTPUT = INTERIM_DIR / "catalog_pilot_institutions_strict.csv"
STRICT_INVENTORY_OUTPUT = INTERIM_DIR / "catalog_inventory_strict_pilot.csv"
STRICT_ATTEMPTS_OUTPUT = INTERIM_DIR / "catalog_retrieval_attempts_strict_pilot.csv"
STRICT_RETRIEVAL_COVERAGE_OUTPUT = INTERIM_DIR / "catalog_retrieval_coverage_strict_pilot.csv"
STRICT_YEAR_COVERAGE_OUTPUT = INTERIM_DIR / "catalog_year_coverage_strict_pilot.csv"
STRICT_SUMMARY_OUTPUT = LOG_DIR / "phase3_strict_pilot_summary.md"

STRICT_PILOT_UNITIDS = [
    122597,  # San Francisco State University: direct HTML catalog pages and stale archive page.
    149222,  # Southern Illinois University-Carbondale: repository wrapper case.
    138558,  # Abraham Baldwin Agricultural College: Wayback recovery case.
    199139,  # UNC Charlotte: multi-year PDF catalog case.
    209490,  # Oregon Health & Science University: missing legacy URL case.
]


@dataclass(frozen=True)
class StrictPilotOutputs:
    institutions: Path
    inventory: Path
    retrieval_attempts: Path
    retrieval_coverage: Path
    year_coverage: Path
    summary_report: Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def to_bool(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def read_inputs(repo_root: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    return (
        pd.read_csv(repo_root / INSTITUTION_UNIVERSE_INPUT, low_memory=False),
        pd.read_csv(repo_root / INSTITUTION_YEAR_TARGETS_INPUT, low_memory=False),
        pd.read_csv(repo_root / LEGACY_EVIDENCE_LINKS_INPUT, low_memory=False),
    )


def build_strict_institutions(universe: pd.DataFrame) -> pd.DataFrame:
    rows = universe[universe["unitid"].isin(STRICT_PILOT_UNITIDS)].copy()
    rows["strict_pilot_reason"] = rows["unitid"].map(
        {
            122597: "direct_html_catalog_and_stale_archive_page",
            149222: "repository_wrapper_case",
            138558: "wayback_recovery_case",
            199139: "multi_year_pdf_catalog_case",
            209490: "missing_legacy_url_case",
        }
    )
    rows["strict_pilot_rank"] = rows["unitid"].map({unitid: idx for idx, unitid in enumerate(STRICT_PILOT_UNITIDS, 1)})
    return rows.sort_values("strict_pilot_rank")


def build_strict_inventory(institutions: pd.DataFrame, targets: pd.DataFrame, links: pd.DataFrame) -> pd.DataFrame:
    unitids = set(institutions["unitid"].astype(int))
    public_links = links[links["unitid"].isin(unitids) & links["legacy_workbook"].eq("public")].copy()
    target_rows = targets[targets["unitid"].isin(unitids)].copy()
    inst_meta = institutions[["unitid", "strict_pilot_rank", "strict_pilot_reason"]]
    target_rows = target_rows.merge(inst_meta, on="unitid", how="left")

    rows: list[dict[str, object]] = []
    created_at = utc_now()
    source_counter = 1
    for _, target in target_rows.sort_values(["strict_pilot_rank", "unitid", "year"]).iterrows():
        year_links = public_links[
            public_links["unitid"].eq(target["unitid"]) & public_links["target_year"].eq(target["year"])
        ]
        if year_links.empty:
            continue
        for _, link in year_links.sort_values(["legacy_source_priority", "legacy_excel_row"]).iterrows():
            url = clean_text(link.get("legacy_url", ""))
            rows.append(
                {
                    "source_id": f"strict-{source_counter:05d}",
                    "pilot_rank": int(target["strict_pilot_rank"]),
                    "strict_pilot_rank": int(target["strict_pilot_rank"]),
                    "strict_pilot_reason": target["strict_pilot_reason"],
                    "unitid": int(target["unitid"]),
                    "institution_name": target["institution_name"],
                    "target_year": int(target["year"]),
                    "candidate_url": url,
                    "source_kind": source_kind_from_url(url),
                    "retrieval_status": "requires_review" if not url else "not_attempted",
                    "text_extract_status": "not_attempted",
                    "needs_human_review": not bool(url) or to_bool(link.get("legacy_needs_review", False)),
                    "review_reason": strict_inventory_review_reason(link, has_url=bool(url)),
                    "legacy_workbook": link.get("legacy_workbook", ""),
                    "legacy_sheet_name": link.get("legacy_sheet_name", ""),
                    "legacy_excel_row": link.get("legacy_excel_row", ""),
                    "legacy_link_id": link.get("legacy_link_id", ""),
                    "legacy_selected_as_prior_evidence": link.get("selected_as_prior_evidence", ""),
                    "legacy_needs_review": link.get("legacy_needs_review", ""),
                    "legacy_review_reasons": link.get("legacy_review_reasons", ""),
                    "created_at": created_at,
                    "updated_at": created_at,
                }
            )
            source_counter += 1
    return pd.DataFrame(rows)


def source_kind_from_url(url: str) -> str:
    if not url:
        return "missing_legacy_url"
    lower = url.lower()
    if lower.endswith(".pdf"):
        return "candidate_pdf"
    return "candidate_web_or_repository_page"


def strict_inventory_review_reason(link: pd.Series, *, has_url: bool) -> str:
    reasons = []
    if not has_url:
        reasons.append("missing legacy URL")
    if to_bool(link.get("legacy_needs_review", False)):
        reasons.append("legacy row needs review")
    if to_bool(link.get("likely_student_note", False)):
        reasons.append("legacy evidence may be collector note")
    return "; ".join(reasons)


def extract_strict_year_evidence(retrieval_coverage: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in retrieval_coverage.iterrows():
        evidence = classify_year_evidence(row)
        rows.append({**row.to_dict(), **evidence})
    return pd.DataFrame(rows)


def classify_year_evidence(row: pd.Series) -> dict[str, object]:
    if not to_bool(row.get("source_retrieved", False)):
        return evidence_result("not_retrieved", "", "", "", False, "Source was not retrieved.")

    path = Path(clean_text(row.get("local_source_path", "")))
    title = clean_text(row.get("best_page_title", ""))
    url = clean_text(row.get("best_final_url", "")) or clean_text(row.get("candidate_url", ""))
    content_type = clean_text(row.get("best_content_type", ""))

    text = ""
    if is_pdf_source(path, content_type):
        pdf_text, pdf_text_status = extract_pdf_text(path)
        parsed = parse_explicit_catalog_year(pdf_text)
        if parsed:
            start, end, evidence_text = parsed
            return evidence_result(
                "pdf_text",
                start,
                end,
                evidence_text,
                covers_target(row.get("target_year"), start, end),
                "",
            )
        parsed = parse_explicit_catalog_year(url)
        if parsed and clear_catalog_url(url):
            start, end, evidence_text = parsed
            return evidence_result(
                "filename_pattern_requires_review",
                start,
                end,
                evidence_text,
                False,
                f"Catalog year appears only in URL/filename; PDF text status: {pdf_text_status}.",
            )
        return evidence_result(
            "pdf_text_unavailable_or_inconclusive",
            "",
            "",
            "",
            False,
            f"PDF source was retrieved, but PDF text did not confirm catalog-year coverage; PDF text status: {pdf_text_status}.",
        )

    if path.exists() and "html" in content_type.lower():
        text = path.read_text(encoding="utf-8", errors="replace")[:12000]
    source_text = " ".join([title, visible_heading_text(text)])
    parsed = parse_explicit_catalog_year(source_text)
    if parsed:
        start, end, evidence_text = parsed
        return evidence_result(
            "html_title_or_heading",
            start,
            end,
            evidence_text,
            covers_target(row.get("target_year"), start, end),
            "",
        )

    parsed = parse_explicit_catalog_year(url)
    if parsed and clear_catalog_url(url):
        start, end, evidence_text = parsed
        return evidence_result(
            "filename_pattern_requires_review",
            start,
            end,
            evidence_text,
            False,
            "Catalog year appears only in URL/filename; requires review or extracted source text.",
        )

    return evidence_result(
        "unknown",
        "",
        "",
        "",
        False,
        "No explicit catalog-year evidence found in title/heading; requires text extraction or manual review.",
    )


def is_pdf_source(path: Path, content_type: str) -> bool:
    return "pdf" in content_type.lower()


def extract_pdf_text(path: Path, max_pages: int = 3) -> tuple[str, str]:
    if not path.exists():
        return "", "missing_local_pdf"
    try:
        from pypdf import PdfReader
    except ImportError:
        return "", "pypdf_unavailable"
    try:
        reader = PdfReader(str(path))
        pages = []
        for page in reader.pages[:max_pages]:
            pages.append(page.extract_text() or "")
        metadata = reader.metadata or {}
        metadata_text = " ".join(str(value) for value in metadata.values() if value)
        text = " ".join([metadata_text, *pages])[:12000]
        return text, "pdf_text_extracted" if text.strip() else "pdf_text_empty"
    except Exception as exc:
        return "", f"pdf_text_extraction_error:{type(exc).__name__}"


def visible_heading_text(text: str) -> str:
    headings = re.findall(r"<h[1-3][^>]*>(.*?)</h[1-3]>", text, flags=re.IGNORECASE | re.DOTALL)
    cleaned = [re.sub(r"<[^>]+>", " ", heading) for heading in headings]
    return " ".join(re.sub(r"\s+", " ", item).strip() for item in cleaned)[:2000]


def clear_catalog_url(url: str) -> bool:
    lower = url.lower()
    return any(keyword in lower for keyword in ["catalog", "bulletin", "undergrad"])


def parse_explicit_catalog_year(text: str) -> tuple[int, int, str] | None:
    if not text:
        return None
    context_pattern = r"(catalog|bulletin|undergraduate|academic standards|general policies)"
    range_pattern = r"((?:19|20)\d{2})\s*(?:-|/|\s+to\s+|\s+through\s+|\s+)\s*((?:19|20)?\d{2})"
    for match in re.finditer(range_pattern, text, flags=re.IGNORECASE):
        snippet = text[max(0, match.start() - 80) : min(len(text), match.end() + 80)]
        if not re.search(context_pattern, snippet, flags=re.IGNORECASE):
            continue
        start = int(match.group(1))
        end_text = match.group(2)
        end = int(end_text) if len(end_text) == 4 else int(str(start)[:2] + end_text)
        if 1990 <= start <= 2030 and start < end <= 2035:
            return start, end, re.sub(r"\s+", " ", snippet).strip()
    return None


def evidence_result(
    evidence_type: str,
    start: object,
    end: object,
    evidence_text: str,
    covers_year: bool,
    reason: str,
) -> dict[str, object]:
    return {
        "catalog_year_evidence_type": evidence_type,
        "catalog_year_start": start,
        "catalog_year_end": end,
        "catalog_year_evidence_text": evidence_text,
        "strict_covers_target_year": covers_year,
        "strict_coverage_reason": reason,
    }


def covers_target(target_year: object, start: int, end: int) -> bool:
    try:
        return start <= int(target_year) < end
    except (TypeError, ValueError):
        return False


def build_strict_year_coverage(
    institutions: pd.DataFrame,
    targets: pd.DataFrame,
    strict_retrieval: pd.DataFrame,
) -> pd.DataFrame:
    unitids = set(institutions["unitid"].astype(int))
    panel = targets[targets["unitid"].isin(unitids)].rename(columns={"year": "target_year"}).copy()
    panel = panel.merge(institutions[["unitid", "strict_pilot_rank", "strict_pilot_reason"]], on="unitid", how="left")
    usable = strict_retrieval[strict_retrieval["strict_covers_target_year"].eq(True)].copy()
    expanded_rows = []
    for _, row in usable.iterrows():
        start = int(row["catalog_year_start"])
        end = int(row["catalog_year_end"])
        for year in range(max(TARGET_START_YEAR, start), min(TARGET_END_YEAR + 1, end)):
            expanded_rows.append(
                {
                    "unitid": int(row["unitid"]),
                    "target_year": year,
                    "source_id": row["source_id"],
                    "candidate_url": row["candidate_url"],
                    "source_status": "strict_source_covers_year",
                    "catalog_year_start": start,
                    "catalog_year_end": end,
                    "catalog_year_evidence_type": row["catalog_year_evidence_type"],
                    "catalog_year_evidence_text": row["catalog_year_evidence_text"],
                    "retrieval_method": row["best_attempt_method"],
                    "local_source_path": row["local_source_path"],
                }
            )
    expanded = pd.DataFrame(expanded_rows)
    if expanded.empty:
        panel["source_status"] = "missing_source_for_year"
    else:
        expanded = expanded.sort_values(["unitid", "target_year", "source_id"]).groupby(
            ["unitid", "target_year"], as_index=False
        ).first()
        panel = panel.merge(expanded, on=["unitid", "target_year"], how="left")
        panel["source_status"] = panel["source_status"].fillna("missing_source_for_year")
    panel["has_strict_catalog_source"] = panel["source_status"].eq("strict_source_covers_year")
    panel["needs_human_review"] = ~panel["has_strict_catalog_source"]
    panel["review_reason"] = ""
    panel.loc[~panel["has_strict_catalog_source"], "review_reason"] = (
        "No retrieved source has explicit catalog-year evidence covering this academic year."
    )
    return panel.sort_values(["strict_pilot_rank", "unitid", "target_year"])


def write_summary(
    summary_path: Path,
    institutions: pd.DataFrame,
    inventory: pd.DataFrame,
    retrieval: pd.DataFrame,
    year_coverage: pd.DataFrame,
) -> None:
    covered = int(year_coverage["has_strict_catalog_source"].sum())
    total = len(year_coverage)
    lines = [
        "# Phase 3 Strict Catalog Pilot",
        "",
        f"Generated at: {utc_now()}",
        "",
        "## Scope",
        "",
        f"- Institutions: {len(institutions)}",
        f"- Inventory URL/source rows: {len(inventory)}",
        f"- Institution-year rows: {total}",
        "",
        "## Strict Coverage",
        "",
        f"- Institution-years with strict source coverage: {covered}",
        f"- Institution-years missing strict source coverage: {total - covered}",
        f"- Strict coverage rate: {covered / total:.1%}" if total else "- Strict coverage rate: n/a",
        "",
        "## Catalog-Year Evidence Types",
        "",
    ]
    for evidence_type, count in retrieval["catalog_year_evidence_type"].value_counts(dropna=False).items():
        lines.append(f"- {evidence_type}: {count}")
    lines.extend(["", "## Institutions", ""])
    for _, row in institutions.sort_values("strict_pilot_rank").iterrows():
        inst_cov = year_coverage[year_coverage["unitid"].eq(row["unitid"])]
        lines.append(
            f"- {row['institution_name']} ({int(row['unitid'])}): "
            f"{int(inst_cov['has_strict_catalog_source'].sum())}/{len(inst_cov)}; {row['strict_pilot_reason']}"
        )
    lines.extend(
        [
            "",
            "## Outputs",
            "",
            f"- Strict institutions: `{(summary_path.parents[1] / 'interim' / STRICT_INSTITUTIONS_OUTPUT.name).resolve()}`",
            f"- Strict inventory: `{(summary_path.parents[1] / 'interim' / STRICT_INVENTORY_OUTPUT.name).resolve()}`",
            f"- Strict retrieval attempts: `{(summary_path.parents[1] / 'interim' / STRICT_ATTEMPTS_OUTPUT.name).resolve()}`",
            f"- Strict retrieval coverage: `{(summary_path.parents[1] / 'interim' / STRICT_RETRIEVAL_COVERAGE_OUTPUT.name).resolve()}`",
            f"- Strict year coverage: `{(summary_path.parents[1] / 'interim' / STRICT_YEAR_COVERAGE_OUTPUT.name).resolve()}`",
            "",
        ]
    )
    summary_path.write_text("\n".join(lines), encoding="utf-8")


def run_strict_pilot(repo_root: Path, *, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> StrictPilotOutputs:
    repo_root = repo_root.resolve()
    universe, targets, links = read_inputs(repo_root)
    institutions = build_strict_institutions(universe)
    inventory = build_strict_inventory(institutions, targets, links)
    attempts = build_retrieval_attempts(repo_root, inventory, timeout_seconds=timeout_seconds)
    retrieval = extract_strict_year_evidence(build_coverage(inventory, attempts))
    year_coverage = build_strict_year_coverage(institutions, targets, retrieval)

    paths = StrictPilotOutputs(
        institutions=(repo_root / STRICT_INSTITUTIONS_OUTPUT).resolve(),
        inventory=(repo_root / STRICT_INVENTORY_OUTPUT).resolve(),
        retrieval_attempts=(repo_root / STRICT_ATTEMPTS_OUTPUT).resolve(),
        retrieval_coverage=(repo_root / STRICT_RETRIEVAL_COVERAGE_OUTPUT).resolve(),
        year_coverage=(repo_root / STRICT_YEAR_COVERAGE_OUTPUT).resolve(),
        summary_report=(repo_root / STRICT_SUMMARY_OUTPUT).resolve(),
    )
    for path in paths.__dict__.values():
        path.parent.mkdir(parents=True, exist_ok=True)

    institutions.to_csv(paths.institutions, index=False)
    inventory.to_csv(paths.inventory, index=False)
    attempts.to_csv(paths.retrieval_attempts, index=False)
    retrieval.to_csv(paths.retrieval_coverage, index=False)
    year_coverage.to_csv(paths.year_coverage, index=False)
    write_summary(paths.summary_report, institutions, inventory, retrieval, year_coverage)
    return paths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run strict 5-institution catalog pilot.")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve() if args.root else repo_root_from_cwd()
    outputs = run_strict_pilot(root, timeout_seconds=args.timeout_seconds)
    for label, path in outputs.__dict__.items():
        print(f"{label}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
