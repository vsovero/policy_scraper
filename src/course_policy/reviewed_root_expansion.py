"""Expand reviewed catalog roots into year-level candidates for review.

This is the bridge between the manual source-finding pass and the review
mockup. Reviewed roots are not treated as vague notes; they are retrieved,
expanded through archive/pagination links, and converted into year-level
candidate URLs where explicit year evidence is visible.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .ai_config import repo_root_from_cwd
from .batch2_year_candidates import candidate_archive_urls, normalized_year_range
from .batch3_discovery import build_year_candidates, is_policy_page_lead, is_wrong_scope_catalog_url
from .catalog_retrieval import retrieve_url
from .manual_catalog_search_audit import MANUAL_AUDIT_OUTPUT, run as run_manual_audit


DATA_DIR = Path("../data_policy_pipeline")
INTERIM_DIR = DATA_DIR / "interim"
LOG_DIR = DATA_DIR / "logs"

LEGACY_EVIDENCE_LINKS_INPUT = INTERIM_DIR / "legacy_evidence_links.csv"
INSTITUTION_YEAR_TARGETS_INPUT = INTERIM_DIR / "institution_year_targets.csv"
STRICT_RETRIEVED_COVERAGE_INPUT = INTERIM_DIR / "catalog_panel_year_coverage_retrieved_strict_pilot.csv"

REVIEWED_ROOT_ARCHIVE_PAGES_OUTPUT = INTERIM_DIR / "catalog_reviewed_root_archive_pages.csv"
REVIEWED_ROOT_YEAR_CANDIDATES_OUTPUT = INTERIM_DIR / "catalog_reviewed_root_year_candidates.csv"
REVIEWED_ROOT_YEAR_COVERAGE_OUTPUT = INTERIM_DIR / "catalog_reviewed_root_year_coverage.csv"
REVIEWED_ROOT_SUMMARY_OUTPUT = LOG_DIR / "phase3_reviewed_root_expansion_summary.md"

RETRIEVED_STATUSES = {"retrieved", "retrieved_truncated"}
TARGET_START_YEAR = 2000
TARGET_END_YEAR = 2020


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def read_manual_audit(repo_root: Path) -> pd.DataFrame:
    path = repo_root / MANUAL_AUDIT_OUTPUT
    if not path.exists():
        run_manual_audit(repo_root)
    audit = pd.read_csv(path, low_memory=False)
    audit = audit.loc[audit["manual_best_root_url"].fillna("").astype(str).str.strip().ne("")].copy()
    audit["reviewed_rank"] = range(1, len(audit) + 1)
    return audit


def expand_reviewed_roots(
    manual_audit: pd.DataFrame,
    *,
    timeout_seconds: int,
    max_archives_per_root: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    archive_rows: list[dict[str, object]] = []
    result_by_url: dict[str, dict[str, object]] = {}

    for _, root in manual_audit.sort_values(["reviewed_rank", "unitid"]).iterrows():
        root_url = clean_text(root["manual_best_root_url"])
        if not root_url or root_url.lower().endswith(".pdf"):
            continue
        root_result = retrieve_url(root_url, timeout_seconds=timeout_seconds, max_bytes=5_000_000)
        result_by_url[root_url] = root_result
        archives = candidate_archive_urls(root_result, root_url)[:max_archives_per_root]
        for archive_index, archive in enumerate(archives, 1):
            archive_url = clean_text(archive["archive_url"])
            if archive_url not in result_by_url:
                result_by_url[archive_url] = retrieve_url(archive_url, timeout_seconds=timeout_seconds, max_bytes=5_000_000)
            result = result_by_url[archive_url]
            archive_rows.append(
                {
                    "batch3_rank": int(root["reviewed_rank"]),
                    "unitid": int(root["unitid"]),
                    "institution_name": clean_text(root.get("institution_name", "")),
                    "manual_status": clean_text(root.get("manual_status", "")),
                    "manual_root_type": clean_text(root.get("manual_root_type", "")),
                    "reviewed_root_url": root_url,
                    "archive_url": archive_url,
                    "archive_source": clean_text(archive["archive_source"]),
                    "archive_link_text": clean_text(archive["archive_link_text"]),
                    "retrieval_status": result["retrieval_status"],
                    "http_status": result["http_status"],
                    "final_url": result["final_url"],
                    "content_type": result["content_type"],
                    "page_title": result["page_title"],
                    "year_hints": result["year_hints"],
                    "link_count": len(result.get("link_records", [])),
                    "created_at": utc_now(),
                }
            )

    archive_pages = pd.DataFrame(archive_rows)
    if archive_pages.empty:
        return archive_pages, pd.DataFrame()
    year_candidates = build_year_candidates(archive_pages, result_by_url)
    if year_candidates.empty:
        return archive_pages, year_candidates
    year_candidates["candidate_source_method"] = "reviewed_root_archive"
    year_candidates["reviewed_root_url"] = year_candidates["archive_url"].map(
        archive_pages.drop_duplicates("archive_url").set_index("archive_url")["reviewed_root_url"].to_dict()
    )
    year_candidates["manual_root_type"] = year_candidates["archive_url"].map(
        archive_pages.drop_duplicates("archive_url").set_index("archive_url")["manual_root_type"].to_dict()
    )
    return archive_pages, year_candidates


def legacy_catalog_candidates(repo_root: Path, unitids: set[int]) -> pd.DataFrame:
    legacy = pd.read_csv(repo_root / LEGACY_EVIDENCE_LINKS_INPUT, low_memory=False)
    legacy = legacy.loc[legacy["unitid"].isin(unitids) & legacy["legacy_workbook"].eq("public")].copy()
    legacy["legacy_url"] = legacy["legacy_url"].map(clean_text)
    legacy = legacy.loc[legacy["legacy_url"].ne("")]
    if legacy.empty:
        return pd.DataFrame()

    rows: list[dict[str, object]] = []
    for _, row in legacy.iterrows():
        url = clean_text(row["legacy_url"])
        if is_policy_page_lead(url):
            continue
        if is_wrong_scope_catalog_url(url):
            continue
        evidence_blob = " ".join(
            [
                url,
                clean_text(row.get("legacy_excerpt", "")),
                clean_text(row.get("missing_evidence_text", "")),
            ]
        )
        year_range = normalized_year_range(evidence_blob)
        if year_range:
            start, end = year_range
        else:
            start = int(row["target_year"])
            end = start + 1
        for target_year in range(max(start, TARGET_START_YEAR), min(end, TARGET_END_YEAR + 1)):
            rows.append(
                {
                    "batch3_rank": 0,
                    "unitid": int(row["unitid"]),
                    "institution_name": "",
                    "target_year": target_year,
                    "catalog_year_start": start,
                    "catalog_year_end": end,
                    "academic_year_rule": "AY is the catalog start year; multi-year catalogs cover each start year through end-1.",
                    "candidate_url": url,
                    "candidate_link_text": "legacy workbook catalog URL",
                    "candidate_evidence_text": evidence_blob,
                    "candidate_evidence_source": "legacy_url_context",
                    "archive_url": clean_text(row.get("legacy_url_parent", "")),
                    "archive_page_title": "",
                    "candidate_scope": "legacy_catalog_lead",
                    "validation_status": "legacy_url_catalog_candidate",
                    "candidate_priority": 25,
                    "candidate_source_method": "legacy_catalog_prior",
                    "reviewed_root_url": "",
                    "manual_root_type": "",
                    "created_at": utc_now(),
                }
            )
    return pd.DataFrame(rows)


def strict_retrieved_catalog_candidates(repo_root: Path, unitids: set[int]) -> pd.DataFrame:
    path = repo_root / STRICT_RETRIEVED_COVERAGE_INPUT
    if not path.exists():
        return pd.DataFrame()
    strict = pd.read_csv(path, low_memory=False)
    strict = strict.loc[
        strict["unitid"].isin(unitids)
        & strict["has_strict_catalog_source"].fillna(False).astype(bool)
        & strict["candidate_url"].fillna("").astype(str).str.strip().ne("")
    ].copy()
    if strict.empty:
        return pd.DataFrame()
    rows = []
    for _, row in strict.iterrows():
        url = clean_text(row["candidate_url"])
        if is_wrong_scope_catalog_url(url):
            continue
        rows.append(
            {
                "batch3_rank": 0,
                "unitid": int(row["unitid"]),
                "institution_name": clean_text(row.get("institution_name", "")),
                "target_year": int(row["target_year"]),
                "catalog_year_start": row.get("catalog_year_start", ""),
                "catalog_year_end": row.get("catalog_year_end", ""),
                "academic_year_rule": "AY is the catalog start year; strict pilot source has catalog-year evidence.",
                "candidate_url": url,
                "candidate_link_text": clean_text(row.get("catalog_year_evidence_text", "")) or clean_text(row.get("source_id", "")),
                "candidate_evidence_text": clean_text(row.get("catalog_year_evidence_text", "")),
                "candidate_evidence_source": clean_text(row.get("catalog_year_evidence_type", "")) or "strict_pilot_catalog_year_evidence",
                "archive_url": "",
                "archive_page_title": "",
                "candidate_scope": "strict_pilot_catalog_source",
                "validation_status": clean_text(row.get("source_status", "")) or "strict_source_covers_year",
                "candidate_priority": 5,
                "candidate_source_method": "strict_pilot_verified_source",
                "reviewed_root_url": "",
                "manual_root_type": "",
                "created_at": utc_now(),
            }
        )
    return pd.DataFrame(rows)


def choose_best_candidates(candidates: pd.DataFrame) -> pd.DataFrame:
    if candidates.empty:
        return candidates
    out = candidates.copy()
    row_scope_text = (
        out.get("candidate_url", pd.Series("", index=out.index)).fillna("").astype(str)
        + " "
        + out.get("candidate_link_text", pd.Series("", index=out.index)).fillna("").astype(str)
        + " "
        + out.get("candidate_evidence_text", pd.Series("", index=out.index)).fillna("").astype(str)
    )
    has_undergrad_scope = row_scope_text.str.lower().str.contains("undergraduate|undergrad|\\bug\\b", regex=True)
    has_general_catalog_scope = row_scope_text.str.lower().str.contains(
        "general catalog|general and graduate catalog|general_and_graduate",
        regex=True,
    )
    out = out.loc[
        ~(row_scope_text.map(is_wrong_scope_catalog_url) & ~has_undergrad_scope & ~has_general_catalog_scope)
    ].copy()
    if out.empty:
        return out
    if "candidate_priority" not in out.columns:
        out["candidate_priority"] = 50
    source_priority = {
        "strict_pilot_verified_source": 0,
        "reviewed_root_archive": 1,
        "legacy_catalog_prior": 2,
    }
    out["candidate_source_priority"] = out["candidate_source_method"].map(source_priority).fillna(9).astype(int)
    return (
        out.sort_values(["unitid", "target_year", "candidate_source_priority", "candidate_priority", "candidate_url"])
        .groupby(["unitid", "target_year"], as_index=False)
        .first()
        .sort_values(["unitid", "target_year"])
    )


def build_coverage(repo_root: Path, manual_audit: pd.DataFrame, candidates: pd.DataFrame) -> pd.DataFrame:
    unitids = set(manual_audit["unitid"].astype(int))
    targets = pd.read_csv(repo_root / INSTITUTION_YEAR_TARGETS_INPUT, low_memory=False)
    targets = targets.loc[
        targets["unitid"].isin(unitids)
        & targets["year"].between(TARGET_START_YEAR, TARGET_END_YEAR)
    ].rename(columns={"year": "target_year"})
    if "institution_name" in targets.columns:
        targets = targets.drop(columns=["institution_name"])
    targets = targets.merge(
        manual_audit[
            [
                "unitid",
                "institution_name",
                "manual_status",
                "manual_best_root_url",
                "manual_root_type",
                "manual_coverage_start_year",
                "manual_coverage_end_year",
            ]
        ].drop_duplicates("unitid"),
        on="unitid",
        how="left",
    )
    chosen = choose_best_candidates(candidates)
    if not chosen.empty:
        keep = [
            "unitid",
            "target_year",
            "candidate_url",
            "candidate_link_text",
            "candidate_evidence_text",
            "candidate_evidence_source",
            "candidate_source_method",
            "catalog_year_start",
            "catalog_year_end",
            "archive_url",
            "reviewed_root_url",
            "validation_status",
        ]
        targets = targets.merge(chosen[[col for col in keep if col in chosen.columns]], on=["unitid", "target_year"], how="left")
    for col in [
        "candidate_url",
        "candidate_link_text",
        "candidate_evidence_text",
        "candidate_evidence_source",
        "candidate_source_method",
        "catalog_year_start",
        "catalog_year_end",
        "archive_url",
        "reviewed_root_url",
        "validation_status",
    ]:
        if col not in targets.columns:
            targets[col] = ""
    targets["reviewed_candidate_status"] = targets["candidate_url"].map(clean_text).map(
        lambda value: "reviewed_candidate_found" if value else "no_reviewed_candidate_found"
    )
    targets["created_at"] = utc_now()
    return targets.sort_values(["institution_name", "target_year"])


def write_summary(
    path: Path,
    archive_pages: pd.DataFrame,
    candidates: pd.DataFrame,
    coverage: pd.DataFrame,
) -> None:
    lines = [
        "# Reviewed Root Expansion",
        "",
        f"Created: {utc_now()}",
        "",
        "## Summary",
        "",
        f"- archive pages checked: {len(archive_pages)}",
        f"- year-level candidate rows: {len(candidates)}",
        f"- coverage rows: {len(coverage)}",
        f"- coverage rows with reviewed candidate: {int(coverage['candidate_url'].map(clean_text).ne('').sum())}",
        "",
        "## Candidate Source Methods",
        "",
    ]
    if not candidates.empty:
        for method, count in candidates["candidate_source_method"].value_counts().items():
            lines.append(f"- {method}: {int(count)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(
    repo_root: Path,
    *,
    timeout_seconds: int = 12,
    max_archives_per_root: int = 12,
    refresh_unitids: set[int] | None = None,
) -> tuple[Path, Path, Path, Path]:
    repo_root = repo_root.resolve()
    manual_audit = read_manual_audit(repo_root)
    refresh_unitids = refresh_unitids or set()
    expansion_audit = manual_audit
    if refresh_unitids:
        expansion_audit = manual_audit.loc[manual_audit["unitid"].astype(int).isin(refresh_unitids)].copy()
    archive_pages, root_candidates = expand_reviewed_roots(
        expansion_audit,
        timeout_seconds=timeout_seconds,
        max_archives_per_root=max_archives_per_root,
    )
    existing_path = repo_root / REVIEWED_ROOT_YEAR_CANDIDATES_OUTPUT
    if refresh_unitids and existing_path.exists():
        existing_candidates = pd.read_csv(existing_path, low_memory=False)
        if "unitid" in existing_candidates.columns:
            existing_candidates = existing_candidates.loc[
                ~existing_candidates["unitid"].astype(int).isin(refresh_unitids)
            ].copy()
        root_candidates = pd.concat(
            [frame for frame in [existing_candidates, root_candidates] if not frame.empty],
            ignore_index=True,
            sort=False,
        )
    legacy_candidates = legacy_catalog_candidates(repo_root, set(manual_audit["unitid"].astype(int)))
    strict_candidates = strict_retrieved_catalog_candidates(repo_root, set(manual_audit["unitid"].astype(int)))
    candidate_frames = [frame for frame in [root_candidates, strict_candidates, legacy_candidates] if not frame.empty]
    candidates = pd.concat(candidate_frames, ignore_index=True, sort=False) if candidate_frames else pd.DataFrame()
    coverage = build_coverage(repo_root, manual_audit, candidates)

    archive_path = repo_root / REVIEWED_ROOT_ARCHIVE_PAGES_OUTPUT
    candidates_path = repo_root / REVIEWED_ROOT_YEAR_CANDIDATES_OUTPUT
    coverage_path = repo_root / REVIEWED_ROOT_YEAR_COVERAGE_OUTPUT
    summary_path = repo_root / REVIEWED_ROOT_SUMMARY_OUTPUT
    for path in [archive_path, candidates_path, coverage_path, summary_path]:
        path.parent.mkdir(parents=True, exist_ok=True)
    archive_pages.to_csv(archive_path, index=False)
    candidates.to_csv(candidates_path, index=False)
    coverage.to_csv(coverage_path, index=False)
    write_summary(summary_path, archive_pages, candidates, coverage)
    return archive_path, candidates_path, coverage_path, summary_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout-seconds", type=int, default=12)
    parser.add_argument("--max-archives-per-root", type=int, default=12)
    parser.add_argument(
        "--refresh-unitids",
        default="",
        help="Comma-separated unitids to refresh and merge with existing reviewed-root candidates.",
    )
    args = parser.parse_args()
    repo_root = repo_root_from_cwd()
    refresh_unitids = {
        int(value.strip())
        for value in args.refresh_unitids.split(",")
        if value.strip()
    }
    archive_path, candidates_path, coverage_path, summary_path = run(
        repo_root,
        timeout_seconds=args.timeout_seconds,
        max_archives_per_root=args.max_archives_per_root,
        refresh_unitids=refresh_unitids,
    )
    print(f"archive_pages: {archive_path}")
    print(f"year_candidates: {candidates_path}")
    print(f"year_coverage: {coverage_path}")
    print(f"summary: {summary_path}")


if __name__ == "__main__":
    main()
