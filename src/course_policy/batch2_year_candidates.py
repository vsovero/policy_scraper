"""Build year-level catalog candidates from batch-2 preferred roots."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

from .ai_config import repo_root_from_cwd
from .batch2_pilot import BATCH2_SOURCE_ROOT_TASKS_OUTPUT, BATCH2_YEAR_STATUS_OUTPUT
from .batch2_root_check import BATCH2_SOURCE_ROOT_DECISIONS_OUTPUT
from .catalog_retrieval import retrieve_url, save_source_body
from .institution_universe import TARGET_END_YEAR, TARGET_START_YEAR


DATA_DIR = Path("../data_policy_pipeline")
INTERIM_DIR = DATA_DIR / "interim"
LOG_DIR = DATA_DIR / "logs"

BATCH2_ARCHIVE_PAGES_OUTPUT = INTERIM_DIR / "catalog_batch2_archive_pages.csv"
BATCH2_YEAR_CANDIDATES_OUTPUT = INTERIM_DIR / "catalog_batch2_year_candidates.csv"
BATCH2_YEAR_COVERAGE_OUTPUT = INTERIM_DIR / "catalog_batch2_year_coverage.csv"
BATCH2_YEAR_CANDIDATE_SUMMARY_OUTPUT = LOG_DIR / "phase3_batch2_year_candidate_summary.md"

ARCHIVE_TERMS = ("archive", "archives", "archived", "prior catalog", "previous catalog", "bulletins")
EXCLUDE_TERMS = (
    "law",
    "pharmacy",
    "medicine",
    "student handbook",
    "employee handbook",
    "addendum",
    "supplemental",
    "associate-level",
    "associate level",
    "georgia perimeter",
)


@dataclass(frozen=True)
class Batch2YearCandidateOutputs:
    archive_pages: Path
    year_candidates: Path
    year_coverage: Path
    year_status: Path
    summary_report: Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_inputs(repo_root: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    return (
        pd.read_csv(repo_root / BATCH2_SOURCE_ROOT_DECISIONS_OUTPUT, low_memory=False),
        pd.read_csv(repo_root / BATCH2_SOURCE_ROOT_TASKS_OUTPUT, low_memory=False),
        pd.read_csv(repo_root / BATCH2_YEAR_STATUS_OUTPUT, low_memory=False),
    )


def clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def normalized_year_range(text: str) -> tuple[int, int] | None:
    text = re.sub(r"\b22(\d{2})\s*[-–—_/]\s*(20\d{2})\b", lambda m: f"20{m.group(1)}-{m.group(2)}", text)
    match = re.search(r"((?:19|20)\d{2})\s*[-–—_/]\s*((?:19|20)?\d{2})", text)
    if not match:
        return None
    start = int(match.group(1))
    end_text = match.group(2)
    end = int(end_text) if len(end_text) == 4 else int(str(start)[:2] + end_text)
    if end < start:
        end += 100
    if not (1990 <= start <= 2030 and start < end <= 2035):
        return None
    return start, end


def catalog_year_range(text: object) -> tuple[int, int] | None:
    """Return an academic/catalog year span from catalog-like text.

    This is intentionally more permissive than ``normalized_year_range`` so
    production recovery code can reason about older archive ranges such as
    ``1970-2012`` without loosening the batch-2 target-year parser.
    """
    value = clean_text(text)
    if not value:
        return None
    value = re.sub(r"\b22(\d{2})\s*[-–—_/]\s*(20\d{2})\b", lambda m: f"20{m.group(1)}-{m.group(2)}", value)
    match = re.search(r"((?:18|19|20)\d{2})\s*[-–—_/]\s*((?:18|19|20)?\d{2})", value)
    if match:
        start = int(match.group(1))
        end_text = match.group(2)
        end = int(end_text) if len(end_text) == 4 else int(str(start)[:2] + end_text)
    else:
        match = re.search(r"(?<!\d)(\d{2})\s*[-–—_/]\s*(\d{2})(?!\d)", value)
        if not match:
            match = re.search(
                r"(?<!\d)(\d{2})(\d{2})(?=[^\d]*(?:catalog|catalogue|cat|bulletin|undergrad|ug|\.pdf|$))",
                value,
                flags=re.IGNORECASE,
            )
        if not match:
            return None
        start_two = int(match.group(1))
        end_two = int(match.group(2))
        start = 2000 + start_two if start_two <= 35 else 1900 + start_two
        end = (start // 100) * 100 + end_two
    if end <= start:
        end += 100
    if not (1800 <= start <= 2030 and start < end <= 2035):
        return None
    return start, end


def academic_years_from_range(start: int, end: int) -> list[int]:
    return [year for year in range(start, end) if TARGET_START_YEAR <= year <= TARGET_END_YEAR]


def link_text_blob(record: dict[str, str]) -> str:
    return f"{record.get('text', '')} {record.get('url', '')}".strip()


def is_archive_link(record: dict[str, str]) -> bool:
    blob = link_text_blob(record).lower()
    return (
        any(term in blob for term in ARCHIVE_TERMS)
        or "metadata.json" in blob
        or "metadata.csv" in blob
    )


def is_archive_pagination_link(record: dict[str, str]) -> bool:
    text = clean_text(record.get("text")).lower()
    parsed = urlparse(clean_text(record.get("url")).lower())
    if re.search(r"/index\.\d+\.html$", parsed.path):
        return True
    if text.isdigit() and any(term in parsed.path for term in ["archive", "catalog"]):
        return True
    query = parsed.query.lower()
    return bool(re.search(r"(^|[?&])(pg|page|p)=\d+($|&)", query))


def is_relevant_catalog_link(record: dict[str, str], institution_name: str) -> bool:
    blob = link_text_blob(record)
    lowered = blob.lower()
    if not normalized_year_range(blob):
        return False
    graduate_check = lowered.replace("undergraduate", "")
    if "graduate" in graduate_check:
        return False
    if any(term in lowered for term in EXCLUDE_TERMS):
        return False
    if institution_name == "George Mason University":
        return "mason_" in lowered or "catalog" in lowered or "archives/" in lowered
    if institution_name == "Colorado School of Mines":
        return "undergraduate" in lowered or "ug.pdf" in lowered or "bulletin" in lowered or "catalog.mines.edu/archives/" in lowered
    if "pdf" in lowered and "catalog" not in lowered and "bulletin" not in lowered:
        return False
    return "undergraduate" in lowered or "bulletin" in lowered or "catalog" in lowered


def candidate_archive_urls(root_result: dict[str, object], preferred_root_url: str) -> list[dict[str, str]]:
    rows = [
        {
            "archive_url": preferred_root_url,
            "archive_source": "preferred_root",
            "archive_link_text": "preferred root",
        }
    ]
    parsed_root = urlparse(preferred_root_url)
    path_parts = [part for part in parsed_root.path.split("/") if part]
    if len(path_parts) >= 3 and path_parts[0] == "digital" and path_parts[1] == "collection":
        alias = path_parts[2]
        for term in ["catalog", "bulletin"]:
            rows.append(
                {
                    "archive_url": f"{parsed_root.scheme}://{parsed_root.netloc}/digital/api/search/collection/{alias}/searchterm/{term}/field/title/maxRecords/250",
                    "archive_source": "contentdm_collection_api",
                    "archive_link_text": f"CONTENTdm collection API {term} title search",
                }
            )
    if parsed_root.netloc.lower().startswith(("catalog.", "catalogs.")):
        for path in ["resources/catalog-archives/", "resources/archives/", "archives/"]:
            rows.append(
                {
                    "archive_url": f"{parsed_root.scheme}://{parsed_root.netloc}/{path}",
                    "archive_source": "generated_catalog_resource_archive_path",
                    "archive_link_text": path,
                }
            )
    for record in root_result.get("link_records", []):
        if is_archive_pagination_link(record):
            rows.append(
                {
                    "archive_url": record["url"],
                    "archive_source": "archive_pagination_link",
                    "archive_link_text": record["text"] or urlparse(record["url"]).path.rsplit("/", 1)[-1],
                }
            )
            continue
        if is_archive_link(record):
            rows.append(
                {
                    "archive_url": record["url"],
                    "archive_source": "root_archive_link",
                    "archive_link_text": record["text"],
                }
            )
    seen = set()
    deduped = []
    for row in rows:
        if row["archive_url"] in seen:
            continue
        seen.add(row["archive_url"])
        deduped.append(row)
    return deduped


def build_archive_pages(repo_root: Path, decisions: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, dict[str, object]]]:
    archive_rows = []
    result_by_url: dict[str, dict[str, object]] = {}
    for _, decision in decisions.sort_values(["batch2_rank", "unitid"]).iterrows():
        root_url = clean_text(decision["preferred_source_root_url"])
        root_result = retrieve_url(root_url, max_bytes=5_000_000)
        result_by_url[root_url] = root_result
        root_archive_urls = candidate_archive_urls(root_result, root_url)
        for idx, archive in enumerate(root_archive_urls, 1):
            archive_url = archive["archive_url"]
            result = result_by_url.get(archive_url)
            if result is None:
                result = retrieve_url(archive_url, max_bytes=5_000_000)
                result_by_url[archive_url] = result
            local_source_path = ""
            if result["retrieval_status"] in {"retrieved", "retrieved_truncated"}:
                local_source_path = str(
                    save_source_body(
                        repo_root,
                        f"batch2-archive-{int(decision['unitid'])}-{idx:02d}",
                        "archive_page",
                        archive_url,
                        str(result["content_type"]),
                        result["body"],
                    )
                )
            archive_rows.append(
                {
                    "batch2_rank": int(decision["batch2_rank"]),
                    "unitid": int(decision["unitid"]),
                    "institution_name": decision["institution_name"],
                    "preferred_source_root_url": root_url,
                    "archive_url": archive_url,
                    "archive_source": archive["archive_source"],
                    "archive_link_text": archive["archive_link_text"],
                    "retrieval_status": result["retrieval_status"],
                    "http_status": result["http_status"],
                    "final_url": result["final_url"],
                    "content_type": result["content_type"],
                    "page_title": result["page_title"],
                    "link_count": len(result.get("link_records", [])),
                    "local_source_path": local_source_path,
                    "created_at": utc_now(),
                }
            )
    return pd.DataFrame(archive_rows), result_by_url


def build_year_candidates(archive_pages: pd.DataFrame, result_by_url: dict[str, dict[str, object]]) -> pd.DataFrame:
    rows = []
    for _, page in archive_pages.iterrows():
        if page["retrieval_status"] not in {"retrieved", "retrieved_truncated"}:
            continue
        result = result_by_url.get(page["archive_url"], {})
        for link_index, record in enumerate(result.get("link_records", []), 1):
            if not is_relevant_catalog_link(record, str(page["institution_name"])):
                continue
            year_range = normalized_year_range(link_text_blob(record))
            if not year_range:
                continue
            start, end = year_range
            years = academic_years_from_range(start, end)
            if not years:
                continue
            for target_year in years:
                rows.append(
                    {
                        "batch2_rank": int(page["batch2_rank"]),
                        "unitid": int(page["unitid"]),
                        "institution_name": page["institution_name"],
                        "target_year": target_year,
                        "catalog_year_start": start,
                        "catalog_year_end": end,
                        "academic_year_rule": "AY is the catalog start year; multi-year catalogs cover each start year through end-1.",
                        "candidate_url": record["url"],
                        "candidate_link_text": record["text"],
                        "archive_url": page["archive_url"],
                        "archive_page_title": page["page_title"],
                        "candidate_scope": "undergraduate_or_university_catalog",
                        "validation_status": "explicit_year_link_found",
                        "created_at": utc_now(),
                    }
                )
    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    out["candidate_priority"] = (out["candidate_link_text"] + " " + out["candidate_url"]).str.lower().map(candidate_priority)
    return out.sort_values(["batch2_rank", "unitid", "target_year", "candidate_priority", "candidate_url"])


def candidate_priority(text: object) -> int:
    text = clean_text(text).lower()
    if "undergraduate" in text and "bachelor" in text:
        return 5
    if "undergraduate" in text:
        return 10
    if "general catalog" in text or "general_and_graduate" in text:
        return 15
    if "bulletin" in text:
        return 20
    if "catalog" in text:
        return 30
    return 50


def candidate_document_priority(row: pd.Series | dict[str, object]) -> int:
    text = " ".join(
        clean_text(row.get(column))
        for column in ["candidate_link_text", "candidate_url", "candidate_evidence_text", "source_page_title"]
    ).lower()
    if any(
        term in text
        for term in [
            "academic calendar",
            "admission",
            "assessment report",
            "annual report",
            "application",
            "calendar",
            "fact book",
            "financial aid",
            "form",
            "internship",
            "schedule",
            "strategic plan",
            "tuition",
        ]
    ):
        return 90
    if re.search(r"(^|[/_.-])gr(?:aduate)?([/_.-]|$)", text) and "undergrad" not in text:
        return 60
    if any(term in text for term in ["undergraduate", "undergrad", "ugrad", "ug-catalog", "ug_catalog", "ugcat"]):
        return 10
    if "catalog" in text or "catalogue" in text or "bulletin" in text:
        return 20
    if ".pdf" in text and catalog_year_range(text):
        return 25
    return candidate_priority(text)


def candidate_selection_sort_columns(prefix_columns: list[str]) -> list[str]:
    columns = list(prefix_columns)
    for column in [
        "candidate_document_priority",
        "candidate_priority",
        "candidate_span_width",
        "candidate_selection_rank",
        "candidate_url",
    ]:
        if column not in columns:
            columns.append(column)
    return columns


def add_candidate_selection_rank_columns(candidates: pd.DataFrame) -> pd.DataFrame:
    out = candidates.copy()
    if out.empty:
        return out

    evidence = pd.Series("", index=out.index, dtype="object")
    for column in ["candidate_link_text", "candidate_url", "candidate_evidence_text"]:
        if column in out.columns:
            evidence = evidence.str.cat(out[column].fillna("").map(clean_text), sep=" ")
    computed_priority = evidence.map(candidate_priority)
    if "candidate_priority" in out.columns:
        existing_priority = pd.to_numeric(out["candidate_priority"], errors="coerce")
        out["candidate_priority"] = existing_priority.fillna(computed_priority).astype(int)
    else:
        out["candidate_priority"] = computed_priority.astype(int)

    out["candidate_document_priority"] = out.apply(candidate_document_priority, axis=1).astype(int)
    if {"catalog_year_start", "catalog_year_end"}.issubset(out.columns):
        start = pd.to_numeric(out["catalog_year_start"], errors="coerce")
        end = pd.to_numeric(out["catalog_year_end"], errors="coerce")
        width = end - start
        out["candidate_span_width"] = width.where(width.gt(0), 9999).fillna(9999).astype(int)
    else:
        out["candidate_span_width"] = 9999
    grouping_columns = [column for column in ["unitid", "target_year"] if column in out.columns]
    rank_sort_columns = grouping_columns + ["candidate_document_priority", "candidate_priority", "candidate_span_width"]
    if "candidate_url" in out.columns:
        rank_sort_columns.append("candidate_url")
    ranked = out.sort_values(rank_sort_columns, kind="mergesort").copy()
    if grouping_columns:
        ranked["candidate_selection_rank"] = ranked.groupby(grouping_columns, dropna=False).cumcount() + 1
    else:
        ranked["candidate_selection_rank"] = range(1, len(ranked) + 1)
    out["candidate_selection_rank"] = ranked["candidate_selection_rank"].reindex(out.index).astype(int)
    return out


def build_year_coverage(year_status: pd.DataFrame, candidates: pd.DataFrame) -> pd.DataFrame:
    coverage = year_status.drop(
        columns=[
            "candidate_url",
            "candidate_link_text",
            "archive_url",
            "catalog_year_start",
            "catalog_year_end",
            "candidate_status",
        ],
        errors="ignore",
    ).copy()
    chosen = pd.DataFrame()
    if not candidates.empty:
        chosen = (
            candidates.sort_values(["unitid", "target_year", "candidate_priority", "candidate_url"])
            .groupby(["unitid", "target_year"], as_index=False)
            .first()
        )
        coverage = coverage.merge(
            chosen[
                [
                    "unitid",
                    "target_year",
                    "candidate_url",
                    "candidate_link_text",
                    "archive_url",
                    "catalog_year_start",
                    "catalog_year_end",
                ]
            ],
            on=["unitid", "target_year"],
            how="left",
        )
    else:
        for col in [
            "candidate_url",
            "candidate_link_text",
            "archive_url",
            "catalog_year_start",
            "catalog_year_end",
        ]:
            coverage[col] = ""
    coverage["candidate_url"] = coverage["candidate_url"].fillna("")
    coverage["candidate_status"] = coverage["candidate_url"].map(
        lambda value: "explicit_year_candidate_found" if clean_text(value) else "no_explicit_year_candidate_from_root"
    )
    return coverage.sort_values(["batch2_rank", "unitid", "target_year"])


def write_summary(path: Path, archive_pages: pd.DataFrame, candidates: pd.DataFrame, coverage: pd.DataFrame) -> None:
    lines = [
        "# Phase 3 Batch 2 Year Candidate Summary",
        "",
        f"Generated at: {utc_now()}",
        "",
        "Scope: bounded expansion from preferred catalog roots and archive links only.",
        "",
        "## Archive Page Retrieval",
        "",
    ]
    for status, count in archive_pages["retrieval_status"].value_counts(dropna=False).items():
        lines.append(f"- {status}: {count}")
    lines.extend(["", "## Candidate Coverage by Institution", ""])
    summary = (
        coverage.groupby(["batch2_rank", "institution_name"], dropna=False)
        .agg(
            years_with_explicit_candidates=("candidate_status", lambda values: int((values == "explicit_year_candidate_found").sum())),
            years_without_explicit_candidates=("candidate_status", lambda values: int((values != "explicit_year_candidate_found").sum())),
            first_candidate_year=("target_year", lambda values: ""),
        )
        .reset_index()
    )
    for _, row in summary.iterrows():
        inst_coverage = coverage.loc[coverage["institution_name"].eq(row["institution_name"])]
        found_years = inst_coverage.loc[
            inst_coverage["candidate_status"].eq("explicit_year_candidate_found"), "target_year"
        ].astype(int)
        span = f"{found_years.min()}-{found_years.max()}" if not found_years.empty else "none"
        lines.append(
            f"- {row['institution_name']}: {row['years_with_explicit_candidates']}/21 years; candidate span {span}"
        )
    lines.extend(["", "## Notes", ""])
    lines.append("- Candidate years are not policy evidence yet; they are catalog-source leads with explicit academic-year link text.")
    lines.append("- Missing years remain unfilled unless an approved later step finds a source with explicit year evidence.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_batch2_year_candidates(repo_root: Path) -> Batch2YearCandidateOutputs:
    repo_root = repo_root.resolve()
    decisions, _tasks, year_status = read_inputs(repo_root)
    archive_pages, result_by_url = build_archive_pages(repo_root, decisions)
    candidates = build_year_candidates(archive_pages, result_by_url)
    coverage = build_year_coverage(year_status, candidates)

    outputs = Batch2YearCandidateOutputs(
        archive_pages=(repo_root / BATCH2_ARCHIVE_PAGES_OUTPUT).resolve(),
        year_candidates=(repo_root / BATCH2_YEAR_CANDIDATES_OUTPUT).resolve(),
        year_coverage=(repo_root / BATCH2_YEAR_COVERAGE_OUTPUT).resolve(),
        year_status=(repo_root / BATCH2_YEAR_STATUS_OUTPUT).resolve(),
        summary_report=(repo_root / BATCH2_YEAR_CANDIDATE_SUMMARY_OUTPUT).resolve(),
    )
    for output_path in outputs.__dict__.values():
        output_path.parent.mkdir(parents=True, exist_ok=True)
    archive_pages.to_csv(outputs.archive_pages, index=False)
    candidates.to_csv(outputs.year_candidates, index=False)
    coverage.to_csv(outputs.year_coverage, index=False)
    coverage.to_csv(outputs.year_status, index=False)
    write_summary(outputs.summary_report, archive_pages, candidates, coverage)
    return outputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build Phase 3 batch-2 year-level catalog candidates.")
    parser.add_argument("--root", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve() if args.root else repo_root_from_cwd()
    outputs = run_batch2_year_candidates(root)
    for label, output_path in outputs.__dict__.items():
        print(f"{label}: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
