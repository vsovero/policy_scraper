"""Run a generalized Phase 3 catalog-discovery expansion batch."""

from __future__ import annotations

import argparse
import html
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd

from .ai_config import repo_root_from_cwd
from .batch2_pilot import clean_text, parent_url, source_domain, unique_join
from .batch2_root_check import (
    candidate_urls_for_task,
    likely_catalog_root,
    link_score,
    root_priority,
)
from .batch2_year_candidates import (
    academic_years_from_range,
    candidate_archive_urls,
    candidate_priority,
    normalized_year_range,
)
from .catalog_retrieval import build_coverage, build_retrieval_attempts, retrieve_url, save_source_body
from .strict_pilot import STRICT_PILOT_UNITIDS


DATA_DIR = Path("../data_policy_pipeline")
INTERIM_DIR = DATA_DIR / "interim"
LOG_DIR = DATA_DIR / "logs"

PILOT_INSTITUTIONS_INPUT = INTERIM_DIR / "catalog_pilot_institutions.csv"
LEGACY_EVIDENCE_LINKS_INPUT = INTERIM_DIR / "legacy_evidence_links.csv"
INSTITUTION_YEAR_TARGETS_INPUT = INTERIM_DIR / "institution_year_targets.csv"
BATCH2_INSTITUTIONS_INPUT = INTERIM_DIR / "catalog_batch2_institutions.csv"

BATCH3_INSTITUTIONS_OUTPUT = INTERIM_DIR / "catalog_batch3_institutions.csv"
BATCH3_LEGACY_LEADS_OUTPUT = INTERIM_DIR / "catalog_batch3_legacy_leads.csv"
BATCH3_ROOT_CANDIDATES_OUTPUT = INTERIM_DIR / "catalog_batch3_root_candidates.csv"
BATCH3_SOURCE_ROOT_DECISIONS_OUTPUT = INTERIM_DIR / "catalog_batch3_source_root_decisions.csv"
BATCH3_ARCHIVE_PAGES_OUTPUT = INTERIM_DIR / "catalog_batch3_archive_pages.csv"
BATCH3_YEAR_CANDIDATES_OUTPUT = INTERIM_DIR / "catalog_batch3_year_candidates.csv"
BATCH3_YEAR_COVERAGE_OUTPUT = INTERIM_DIR / "catalog_batch3_year_coverage.csv"
BATCH3_LEGACY_GAP_CANDIDATES_OUTPUT = INTERIM_DIR / "catalog_batch3_legacy_gap_candidates.csv"
BATCH3_COMBINED_INVENTORY_OUTPUT = INTERIM_DIR / "catalog_batch3_combined_inventory.csv"
BATCH3_RETRIEVAL_ATTEMPTS_OUTPUT = INTERIM_DIR / "catalog_batch3_retrieval_attempts.csv"
BATCH3_RETRIEVAL_COVERAGE_OUTPUT = INTERIM_DIR / "catalog_batch3_retrieval_coverage.csv"
BATCH3_STAGE_STATUS_OUTPUT = INTERIM_DIR / "catalog_batch3_stage_status.csv"
BATCH3_SUMMARY_OUTPUT = LOG_DIR / "phase3_batch3_discovery_summary.md"

BATCH_SIZE = 10
RETRIEVED_STATUSES = {"retrieved", "retrieved_truncated"}
ROOT_RETRIEVAL_BYTES = 5_000_000

ARCHIVE_BOUND_GRACE_YEARS = 2
EXCLUDE_TERMS = (
    "law",
    "pharmacy",
    "medicine",
    "medical",
    "dental",
    "veterinary",
    "graduate",
    "grad",
    "student handbook",
    "employee handbook",
    "addendum",
    "supplement",
    "course schedule",
    "class schedule",
    "senate policy",
    "policy catalog",
)
GRADUATE_ONLY_TERMS = ("graduate", "grad")
NON_SCOPE_EXCLUDE_TERMS = tuple(term for term in EXCLUDE_TERMS if term not in GRADUATE_ONLY_TERMS)


@dataclass(frozen=True)
class Batch3Outputs:
    institutions: Path
    legacy_leads: Path
    root_candidates: Path
    source_root_decisions: Path
    archive_pages: Path
    year_candidates: Path
    year_coverage: Path
    legacy_gap_candidates: Path
    combined_inventory: Path
    retrieval_attempts: Path
    retrieval_coverage: Path
    stage_status: Path
    summary_report: Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_inputs(repo_root: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    pilot = pd.read_csv(repo_root / PILOT_INSTITUTIONS_INPUT, low_memory=False)
    links = pd.read_csv(repo_root / LEGACY_EVIDENCE_LINKS_INPUT, low_memory=False)
    targets = pd.read_csv(repo_root / INSTITUTION_YEAR_TARGETS_INPUT, low_memory=False)
    batch2 = pd.read_csv(repo_root / BATCH2_INSTITUTIONS_INPUT, low_memory=False)
    return pilot, links, targets, batch2


def select_batch3_institutions(
    pilot: pd.DataFrame,
    batch2: pd.DataFrame,
    *,
    batch_size: int = BATCH_SIZE,
) -> pd.DataFrame:
    excluded = set(STRICT_PILOT_UNITIDS) | set(batch2["unitid"].dropna().astype(int))
    selected = pilot.loc[~pilot["unitid"].astype(int).isin(excluded)].sort_values("pilot_rank").head(batch_size).copy()
    selected["batch3_rank"] = range(1, len(selected) + 1)
    selected["created_at"] = utc_now()
    columns = [
        "batch3_rank",
        "pilot_rank",
        "unitid",
        "institution_name",
        "state",
        "webaddr",
        "pilot_case_types",
        "legacy_link_rows",
        "legacy_year_count",
        "legacy_url_count",
        "selected_clean_url_count",
        "missing_url_count",
        "needs_review_count",
        "created_at",
    ]
    for col in columns:
        if col not in selected.columns:
            selected[col] = ""
    return selected[columns]


def build_legacy_leads(batch: pd.DataFrame, links: pd.DataFrame) -> pd.DataFrame:
    batch_unitids = set(batch["unitid"].astype(int))
    ranks = batch.set_index("unitid")["batch3_rank"].to_dict()
    names = batch.set_index("unitid")["institution_name"].to_dict()
    leads = links.loc[links["unitid"].isin(batch_unitids) & links["legacy_workbook"].eq("public")].copy()
    if leads.empty:
        return pd.DataFrame()
    leads["batch3_rank"] = leads["unitid"].map(ranks).astype(int)
    leads["institution_name"] = leads["unitid"].map(names)
    leads["legacy_url"] = leads["legacy_url"].map(clean_text)
    leads["legacy_url_domain"] = leads["legacy_url"].map(source_domain)
    leads["legacy_url_parent"] = leads["legacy_url"].map(parent_url)
    leads["legacy_lead_role"] = "prior_discovery_lead"
    leads["recommended_use"] = (
        "Use as an early catalog lead only. Prefer the official catalog/archive root when it provides explicit year coverage."
    )
    leads["created_at"] = utc_now()
    columns = [
        "batch3_rank",
        "unitid",
        "institution_name",
        "target_year",
        "legacy_link_id",
        "legacy_url",
        "legacy_url_domain",
        "legacy_url_parent",
        "legacy_policy_class",
        "selected_as_prior_evidence",
        "legacy_needs_review",
        "legacy_review_reasons",
        "legacy_lead_role",
        "recommended_use",
        "created_at",
    ]
    for col in columns:
        if col not in leads.columns:
            leads[col] = ""
    return leads[columns].sort_values(["batch3_rank", "target_year", "legacy_link_id"])


def source_root_tasks(batch: pd.DataFrame, legacy_leads: pd.DataFrame) -> pd.DataFrame:
    lead_summary = pd.DataFrame()
    if not legacy_leads.empty:
        lead_summary = (
            legacy_leads.groupby("unitid", dropna=False)
            .agg(
                legacy_lead_years=("target_year", lambda values: "; ".join(map(str, sorted(set(values))))),
                legacy_lead_domains=("legacy_url_domain", unique_join),
                legacy_lead_parent_urls=("legacy_url_parent", unique_join),
                legacy_selected_prior_count=("selected_as_prior_evidence", "sum"),
                legacy_review_count=("legacy_needs_review", "sum"),
            )
            .reset_index()
        )
    rows = []
    for _, inst in batch.iterrows():
        summary = lead_summary.loc[lead_summary["unitid"].eq(inst["unitid"])]
        summary_row = summary.iloc[0] if not summary.empty else pd.Series(dtype=object)
        rows.append(
            {
                "batch3_rank": int(inst["batch3_rank"]),
                "unitid": int(inst["unitid"]),
                "institution_name": inst["institution_name"],
                "state": inst["state"],
                "webaddr": inst["webaddr"],
                "legacy_lead_years": summary_row.get("legacy_lead_years", ""),
                "legacy_lead_domains": summary_row.get("legacy_lead_domains", ""),
                "legacy_lead_parent_urls": summary_row.get("legacy_lead_parent_urls", ""),
                "legacy_selected_prior_count": int(summary_row.get("legacy_selected_prior_count", 0) or 0),
                "legacy_review_count": int(summary_row.get("legacy_review_count", 0) or 0),
                "created_at": utc_now(),
            }
        )
    return pd.DataFrame(rows).sort_values(["batch3_rank", "unitid"])


def build_root_candidates(
    repo_root: Path,
    legacy_leads: pd.DataFrame,
    tasks: pd.DataFrame,
    *,
    timeout_seconds: int,
) -> pd.DataFrame:
    rows = []
    for _, task in tasks.sort_values(["batch3_rank", "unitid"]).iterrows():
        for idx, candidate in enumerate(candidate_urls_for_task(task, legacy_leads), 1):
            result = retrieve_url(
                candidate["candidate_url"],
                timeout_seconds=timeout_seconds,
                max_bytes=ROOT_RETRIEVAL_BYTES,
            )
            local_source_path = ""
            if result["retrieval_status"] in RETRIEVED_STATUSES:
                local_source_path = str(
                    save_source_body(
                        repo_root,
                        f"batch3-root-{int(task['unitid'])}-{idx:02d}",
                        "root_check",
                        candidate["candidate_url"],
                        str(result["content_type"]),
                        result["body"],
                    )
                )
            catalog_links, archive_links = link_score(result)
            is_likely = likely_catalog_root(result, candidate["candidate_url"], candidate["candidate_source_type"])
            rows.append(
                {
                    "root_candidate_id": f"batch3-root-{int(task['batch3_rank']):02d}-{idx:02d}",
                    "batch3_rank": int(task["batch3_rank"]),
                    "unitid": int(task["unitid"]),
                    "institution_name": task["institution_name"],
                    "candidate_url": candidate["candidate_url"],
                    "candidate_source_type": candidate["candidate_source_type"],
                    "retrieval_status": result["retrieval_status"],
                    "http_status": result["http_status"],
                    "final_url": result["final_url"],
                    "content_type": result["content_type"],
                    "page_title": result["page_title"],
                    "year_hints": result["year_hints"],
                    "catalog_link_count": catalog_links,
                    "archive_link_count": archive_links,
                    "likely_catalog_root": is_likely,
                    "root_priority": root_priority(candidate["candidate_source_type"], result, candidate["candidate_url"]),
                    "local_source_path": local_source_path,
                    "created_at": utc_now(),
                }
            )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["batch3_rank", "root_priority", "candidate_url"])


def build_source_root_decisions(root_candidates: pd.DataFrame, tasks: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, task in tasks.sort_values(["batch3_rank", "unitid"]).iterrows():
        group = root_candidates.loc[root_candidates["unitid"].eq(task["unitid"])] if not root_candidates.empty else pd.DataFrame()
        usable = group.loc[group["likely_catalog_root"].fillna(False)].copy() if not group.empty else pd.DataFrame()
        if usable.empty:
            rows.append(
                {
                    "batch3_rank": int(task["batch3_rank"]),
                    "unitid": int(task["unitid"]),
                    "institution_name": task["institution_name"],
                    "decision_status": "source_root_not_found",
                    "preferred_source_root_url": "",
                    "preferred_source_root_type": "",
                    "preferred_source_root_title": "",
                    "created_at": utc_now(),
                }
            )
            continue
        preferred = usable.sort_values(["root_priority", "candidate_source_type", "candidate_url"]).iloc[0]
        rows.append(
            {
                "batch3_rank": int(task["batch3_rank"]),
                "unitid": int(task["unitid"]),
                "institution_name": task["institution_name"],
                "decision_status": "preferred_source_root_identified",
                "preferred_source_root_url": preferred["candidate_url"],
                "preferred_source_root_type": preferred["candidate_source_type"],
                "preferred_source_root_title": preferred["page_title"],
                "created_at": utc_now(),
            }
        )
    return pd.DataFrame(rows).sort_values(["batch3_rank", "unitid"])


def build_archive_pages(
    repo_root: Path,
    decisions: pd.DataFrame,
    *,
    timeout_seconds: int,
) -> tuple[pd.DataFrame, dict[str, dict[str, object]]]:
    rows = []
    result_by_url: dict[str, dict[str, object]] = {}
    usable = decisions.loc[decisions["decision_status"].eq("preferred_source_root_identified")].copy()
    for _, decision in usable.sort_values(["batch3_rank", "unitid"]).iterrows():
        root_url = clean_text(decision["preferred_source_root_url"])
        root_result = retrieve_url(root_url, timeout_seconds=timeout_seconds, max_bytes=ROOT_RETRIEVAL_BYTES)
        result_by_url[root_url] = root_result
        for idx, archive in enumerate(candidate_archive_urls(root_result, root_url), 1):
            archive_url = archive["archive_url"]
            result = result_by_url.get(archive_url)
            if result is None:
                result = retrieve_url(archive_url, timeout_seconds=timeout_seconds, max_bytes=ROOT_RETRIEVAL_BYTES)
                result_by_url[archive_url] = result
            local_source_path = ""
            if result["retrieval_status"] in RETRIEVED_STATUSES:
                local_source_path = str(
                    save_source_body(
                        repo_root,
                        f"batch3-archive-{int(decision['unitid'])}-{idx:02d}",
                        "archive_page",
                        archive_url,
                        str(result["content_type"]),
                        result["body"],
                    )
                )
            rows.append(
                {
                    "batch3_rank": int(decision["batch3_rank"]),
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
                    "year_hints": result["year_hints"],
                    "link_count": len(result.get("link_records", [])),
                    "local_source_path": local_source_path,
                    "created_at": utc_now(),
                }
            )
    return pd.DataFrame(rows), result_by_url


def is_relevant_catalog_link(record: dict[str, str]) -> bool:
    link_text = clean_text(record.get("text", ""))
    evidence_text = clean_text(record.get("evidence_text", link_text))
    lowered = evidence_text.lower()
    if not normalized_year_range(evidence_text):
        return False
    if any(term in lowered for term in NON_SCOPE_EXCLUDE_TERMS):
        return False

    has_undergraduate = "undergraduate" in lowered or re.search(r"\bundergrad\b", lowered) is not None
    has_graduate = (
        "graduate" in lowered.replace("undergraduate", "")
        or re.search(r"\bgrad\b", lowered.replace("undergrad", "")) is not None
    )
    if has_undergraduate:
        return True
    if has_graduate:
        return False
    if "catalog" in lowered or "bulletin" in lowered:
        return True
    return False


def build_year_candidates(archive_pages: pd.DataFrame, result_by_url: dict[str, dict[str, object]]) -> pd.DataFrame:
    rows = []
    for _, page in archive_pages.iterrows():
        if page["retrieval_status"] not in RETRIEVED_STATUSES:
            continue
        result = result_by_url.get(page["archive_url"], {})
        records = contextual_link_records(result, page)
        for link_index, record in enumerate(records, 1):
            if not is_relevant_catalog_link(record):
                continue
            year_range = normalized_year_range(clean_text(record.get("evidence_text", record.get("text", ""))))
            if not year_range:
                continue
            start, end = year_range
            for target_year in academic_years_from_range(start, end):
                rows.append(
                    {
                        "batch3_rank": int(page["batch3_rank"]),
                        "unitid": int(page["unitid"]),
                        "institution_name": page["institution_name"],
                        "target_year": target_year,
                        "catalog_year_start": start,
                        "catalog_year_end": end,
                        "academic_year_rule": "AY is the catalog start year; multi-year catalogs cover each start year through end-1.",
                        "candidate_url": record["url"],
                        "candidate_link_text": record["text"],
                        "candidate_evidence_text": record.get("evidence_text", record["text"]),
                        "candidate_evidence_source": record.get("evidence_source", "visible_link_text"),
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
    return out.sort_values(["batch3_rank", "unitid", "target_year", "candidate_priority", "candidate_url"])


def contextual_link_records(result: dict[str, object], page: pd.Series) -> list[dict[str, str]]:
    records = [
        {
            **record,
            "evidence_text": clean_text(record.get("text", "")),
            "evidence_source": "visible_link_text",
        }
        for record in result.get("link_records", [])
    ]
    body = result.get("body", b"")
    content_type = clean_text(result.get("content_type", ""))
    if isinstance(body, bytes) and "html" in content_type.lower():
        text = body.decode("utf-8", errors="replace")
        records.extend(table_row_context_records(text, clean_text(page["archive_url"])))
        records.extend(select_option_context_records(text, clean_text(page["archive_url"])))
        records.extend(bepress_gallery_context_records(text, clean_text(page["archive_url"])))
    title_context = clean_text(page.get("page_title", "")).lower()
    if "undergraduate" in title_context and "catalog" in title_context:
        for record in result.get("link_records", []):
            link_text = clean_text(record.get("text", ""))
            if normalized_year_range(link_text):
                records.append(
                    {
                        **record,
                        "text": link_text,
                        "evidence_text": f"{link_text} {page.get('page_title', '')}",
                        "evidence_source": "archive_page_title_context",
                    }
                )
    return dedupe_context_records(records)


def table_row_context_records(text: str, base_url: str) -> list[dict[str, str]]:
    rows = []
    for row_match in re.finditer(r"<tr\b[^>]*>(.*?)</tr>", text, flags=re.IGNORECASE | re.DOTALL):
        row_html = row_match.group(1)
        row_text = visible_fragment_text(row_html)
        if not normalized_year_range(row_text):
            continue
        for link_match in re.finditer(r"""<a\b[^>]*href=["']([^"']+)["'][^>]*>(.*?)</a>""", row_html, flags=re.IGNORECASE | re.DOTALL):
            href = html.unescape(link_match.group(1)).strip()
            link_text = visible_fragment_text(link_match.group(2))
            url = urljoin(base_url, href)
            context = f"{row_text} {href}"
            rows.append(
                {
                    "url": url,
                    "text": link_text or row_text,
                    "evidence_text": context,
                    "evidence_source": "table_row_context",
                }
            )
    return rows


def select_option_context_records(text: str, base_url: str) -> list[dict[str, str]]:
    rows = []
    for match in re.finditer(r"<option\b[^>]*value=[\"']?([^\"'\s>]+)[\"']?[^>]*>(.*?)</option>", text, flags=re.IGNORECASE | re.DOTALL):
        value = html.unescape(match.group(1)).strip()
        option_text = visible_fragment_text(match.group(2))
        if not value or not normalized_year_range(option_text):
            continue
        rows.append(
            {
                "url": urljoin(base_url, f"/index.php?catoid={value}") if value.isdigit() else urljoin(base_url, value),
                "text": option_text,
                "evidence_text": option_text,
                "evidence_source": "select_option_context",
            }
        )
    return rows


def bepress_gallery_context_records(text: str, base_url: str) -> list[dict[str, str]]:
    rows = []
    parsed_base = urljoin(base_url, "/")
    for preview_match in re.finditer(
        r"""<a\b[^>]*href=["'][^"']*/catalogs/(\d+)/(?:thumbnail|preview)\.jpg["'][^>]*\btitle=["']([^"']+)["'][^>]*>""",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        article_id = preview_match.group(1)
        title = clean_text(html.unescape(preview_match.group(2)))
        if not normalized_year_range(title):
            continue
        rows.append(
            {
                "url": urljoin(parsed_base, f"/cgi/viewcontent.cgi?article={article_id}&context=catalogs"),
                "text": title,
                "evidence_text": title,
                "evidence_source": "bepress_slideshow_context",
            }
        )
    for block_match in re.finditer(
        r"<li>\s*<div class=\"content_block\">(.*?)</div>\s*</li>",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        block = block_match.group(1)
        title_match = re.search(r"<h2>\s*<a\b[^>]*>(.*?)</a>\s*</h2>", block, flags=re.IGNORECASE | re.DOTALL)
        asset_match = re.search(r"/catalogs/(\d+)/(?:thumbnail|preview)\.jpg", block, flags=re.IGNORECASE)
        if not title_match or not asset_match:
            continue
        title = visible_fragment_text(title_match.group(1))
        if not normalized_year_range(title):
            continue
        article_id = asset_match.group(1)
        rows.append(
            {
                "url": urljoin(parsed_base, f"/cgi/viewcontent.cgi?article={article_id}&context=catalogs"),
                "text": title,
                "evidence_text": title,
                "evidence_source": "bepress_gallery_context",
            }
        )
    return rows


def visible_fragment_text(fragment: str) -> str:
    cleaned = re.sub(r"<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", html.unescape(cleaned)).strip()


def dedupe_context_records(records: list[dict[str, str]]) -> list[dict[str, str]]:
    seen = set()
    out = []
    for record in records:
        key = (record.get("url", ""), record.get("evidence_text", ""))
        if not record.get("url") or key in seen:
            continue
        seen.add(key)
        out.append(record)
    return out


def build_year_coverage(
    batch: pd.DataFrame,
    targets: pd.DataFrame,
    decisions: pd.DataFrame,
    candidates: pd.DataFrame,
    archive_pages: pd.DataFrame,
    observed_bounds: pd.DataFrame | None = None,
) -> pd.DataFrame:
    status = targets.loc[targets["unitid"].isin(set(batch["unitid"].astype(int)))].rename(columns={"year": "target_year"}).copy()
    status = status.merge(batch[["unitid", "batch3_rank", "pilot_rank", "pilot_case_types"]], on="unitid", how="left")
    status = status.merge(
        decisions[["unitid", "decision_status", "preferred_source_root_url", "preferred_source_root_type"]],
        on="unitid",
        how="left",
    )
    if not candidates.empty:
        chosen = (
            candidates.sort_values(["unitid", "target_year", "candidate_priority", "candidate_url"])
            .groupby(["unitid", "target_year"], as_index=False)
            .first()
        )
        status = status.merge(
            chosen[
                [
                    "unitid",
                    "target_year",
                    "candidate_url",
                    "candidate_link_text",
                    "archive_url",
                    "catalog_year_start",
                    "catalog_year_end",
                    "candidate_priority",
                ]
            ],
            on=["unitid", "target_year"],
            how="left",
        )
    for col in ["candidate_url", "candidate_link_text", "archive_url", "catalog_year_start", "catalog_year_end", "candidate_priority"]:
        if col not in status.columns:
            status[col] = ""
    status = add_archive_bounds(status, candidates, archive_pages, observed_bounds)
    status["candidate_status"] = status["candidate_url"].fillna("").astype(str).str.strip().map(
        lambda value: "explicit_year_candidate_found" if value else "no_explicit_year_candidate_from_root"
    )
    status.loc[status["decision_status"].fillna("").ne("preferred_source_root_identified"), "candidate_status"] = "source_root_not_found"
    return status.sort_values(["batch3_rank", "unitid", "target_year"])


def add_archive_bounds(
    status: pd.DataFrame,
    candidates: pd.DataFrame,
    archive_pages: pd.DataFrame,
    observed_bounds: pd.DataFrame | None = None,
) -> pd.DataFrame:
    status = status.copy()
    bounds = pd.DataFrame(columns=["unitid", "observed_candidate_start_year", "observed_candidate_end_year"])
    if observed_bounds is not None and not observed_bounds.empty:
        bounds = observed_bounds.copy()
    elif not candidates.empty:
        bounds = (
            candidates.groupby("unitid", as_index=False)
            .agg(
                observed_candidate_start_year=("target_year", "min"),
                observed_candidate_end_year=("target_year", "max"),
            )
        )
    status = status.merge(bounds, on="unitid", how="left")
    status["archive_bound_inferred"] = False
    status["archive_bound_note"] = ""
    status["interior_archive_gap_inferred"] = False
    status["interior_archive_gap_note"] = ""
    candidate_years_by_unitid: dict[int, set[int]] = {}
    if not candidates.empty:
        candidate_years_by_unitid = {
            int(unitid): set(group["target_year"].dropna().astype(int))
            for unitid, group in candidates.groupby("unitid", dropna=False)
            if not pd.isna(unitid)
        }
    for unitid, group in status.groupby("unitid", dropna=False):
        start_values = group["observed_candidate_start_year"].dropna()
        end_values = group["observed_candidate_end_year"].dropna()
        if start_values.empty or end_values.empty:
            continue
        start_year = int(start_values.iloc[0])
        end_year = int(end_values.iloc[0])
        early_missing = group["target_year"].astype(int).lt(start_year)
        if early_missing.sum() > ARCHIVE_BOUND_GRACE_YEARS:
            mask = status["unitid"].eq(unitid) & status["target_year"].astype(int).lt(start_year)
            status.loc[mask, "archive_bound_inferred"] = True
            status.loc[mask, "archive_bound_note"] = f"Preferred root/archive produced explicit candidates starting at AY {start_year}."
        observed_years = candidate_years_by_unitid.get(int(unitid), set()) if not pd.isna(unitid) else set()
        if not observed_years:
            continue
        missing_inside_span = (
            status["unitid"].eq(unitid)
            & status["target_year"].astype(int).between(start_year, end_year)
            & status["candidate_url"].fillna("").astype(str).str.strip().eq("")
        )
        status.loc[missing_inside_span, "interior_archive_gap_inferred"] = True
        status.loc[missing_inside_span, "interior_archive_gap_note"] = (
            f"Target AY falls inside observed archive candidate span AY {start_year}-{end_year}, "
            "but no explicit candidate was extracted; run targeted archive-gap search before treating as absent."
        )
    return status


def build_observed_candidate_bounds(
    archive_pages: pd.DataFrame,
    result_by_url: dict[str, dict[str, object]],
) -> pd.DataFrame:
    rows = []
    for _, page in archive_pages.iterrows():
        if page["retrieval_status"] not in RETRIEVED_STATUSES:
            continue
        result = result_by_url.get(page["archive_url"], {})
        for record in contextual_link_records(result, page):
            if not is_relevant_catalog_link(record):
                continue
            year_range = normalized_year_range(clean_text(record.get("evidence_text", record.get("text", ""))))
            if year_range:
                start, end = year_range
                rows.append(
                    {
                        "unitid": int(page["unitid"]),
                        "observed_candidate_start_year": start,
                        "observed_candidate_end_year": end - 1,
                    }
                )
    if not rows:
        return pd.DataFrame()
    return (
        pd.DataFrame(rows)
        .groupby("unitid", as_index=False)
        .agg(
            observed_candidate_start_year=("observed_candidate_start_year", "min"),
            observed_candidate_end_year=("observed_candidate_end_year", "max"),
        )
    )


def build_legacy_gap_candidates(year_coverage: pd.DataFrame, legacy_leads: pd.DataFrame) -> pd.DataFrame:
    """Use legacy URLs only for institution-years without preferred-root candidates."""
    if legacy_leads.empty:
        return pd.DataFrame()
    gap_years = year_coverage.loc[
        year_coverage["candidate_url"].fillna("").astype(str).str.strip().eq(""),
        ["batch3_rank", "unitid", "institution_name", "target_year"],
    ].copy()
    if gap_years.empty:
        return pd.DataFrame()
    leads = legacy_leads.loc[legacy_leads["legacy_url"].fillna("").astype(str).str.strip().ne("")].copy()
    if leads.empty:
        return pd.DataFrame()
    candidates = gap_years.merge(
        leads,
        on=["batch3_rank", "unitid", "institution_name", "target_year"],
        how="inner",
        suffixes=("", "_legacy"),
    )
    if candidates.empty:
        return pd.DataFrame()
    candidates["candidate_url"] = candidates["legacy_url"].map(clean_text)
    candidates["candidate_link_text"] = "legacy workbook URL"
    candidates["archive_url"] = candidates["legacy_url_parent"].map(clean_text)
    candidates["catalog_year_start"] = candidates["target_year"]
    candidates["catalog_year_end"] = candidates["target_year"].astype(int) + 1
    candidates["candidate_source_method"] = "legacy_prior_gap_fill"
    candidates.loc[candidates["candidate_url"].map(is_policy_page_lead), "candidate_source_method"] = (
        "legacy_policy_page_deferred"
    )
    candidates["candidate_scope"] = "legacy_catalog_lead"
    candidates.loc[candidates["candidate_source_method"].eq("legacy_policy_page_deferred"), "candidate_scope"] = (
        "legacy_policy_page_lead"
    )
    candidates["validation_status"] = candidates["candidate_source_method"].map(
        {
            "legacy_prior_gap_fill": "legacy_url_gap_fill_candidate",
            "legacy_policy_page_deferred": "legacy_policy_page_deferred",
        }
    )
    candidates["created_at"] = utc_now()
    return candidates[
        [
            "batch3_rank",
            "unitid",
            "institution_name",
            "target_year",
            "candidate_url",
            "candidate_link_text",
            "archive_url",
            "catalog_year_start",
            "catalog_year_end",
            "candidate_source_method",
            "candidate_scope",
            "validation_status",
            "legacy_link_id",
            "selected_as_prior_evidence",
            "legacy_needs_review",
            "legacy_review_reasons",
            "created_at",
        ]
    ].sort_values(["batch3_rank", "unitid", "target_year", "legacy_link_id"])


def is_policy_page_lead(url: str) -> bool:
    lowered = clean_text(url).lower()
    if not lowered:
        return False
    policy_terms = ("policy", "policies", "repeat", "forgiveness")
    source_terms = ("bulletin", ".pdf")
    return any(term in lowered for term in policy_terms) and not any(term in lowered for term in source_terms)


def add_legacy_gap_status(year_coverage: pd.DataFrame, legacy_gap_candidates: pd.DataFrame) -> pd.DataFrame:
    if legacy_gap_candidates.empty:
        return year_coverage
    policy_leads = legacy_gap_candidates.loc[
        legacy_gap_candidates["candidate_source_method"].eq("legacy_policy_page_deferred")
    ].copy()
    if policy_leads.empty:
        return year_coverage
    policy_leads = (
        policy_leads.sort_values(["unitid", "target_year", "candidate_url"])
        .groupby(["unitid", "target_year"], as_index=False)
        .first()
    )
    return year_coverage.merge(
        policy_leads[["unitid", "target_year", "candidate_url"]].rename(
            columns={"candidate_url": "legacy_policy_page_url"}
        ),
        on=["unitid", "target_year"],
        how="left",
    )


def build_inventory(
    year_coverage: pd.DataFrame,
    legacy_gap_candidates: pd.DataFrame | None = None,
    *,
    source_prefix: str = "batch3",
) -> pd.DataFrame:
    rows = []
    source_counter = 1
    for _, row in year_coverage.loc[year_coverage["candidate_url"].fillna("").astype(str).str.strip().ne("")].iterrows():
        rows.append(
            {
                "source_id": f"{source_prefix}-{source_counter:05d}",
                "pilot_rank": int(row["batch3_rank"]),
                "batch3_rank": int(row["batch3_rank"]),
                "unitid": int(row["unitid"]),
                "institution_name": row["institution_name"],
                "target_year": int(row["target_year"]),
                "candidate_url": row["candidate_url"],
                "candidate_source_method": "preferred_root_archive",
                "candidate_link_text": clean_text(row.get("candidate_link_text", "")),
                "archive_url": clean_text(row.get("archive_url", "")),
                "catalog_year_start": row.get("catalog_year_start", ""),
                "catalog_year_end": row.get("catalog_year_end", ""),
                "retrieval_status": "not_attempted",
                "text_extract_status": "not_attempted",
                "needs_human_review": False,
                "review_reason": "",
                "legacy_workbook": "",
                "legacy_sheet_name": "",
                "legacy_excel_row": "",
                "legacy_link_id": "",
                "legacy_selected_as_prior_evidence": "",
                "legacy_needs_review": "",
                "legacy_review_reasons": "",
                "created_at": utc_now(),
                "updated_at": utc_now(),
            }
        )
        source_counter += 1
    if legacy_gap_candidates is not None and not legacy_gap_candidates.empty:
        legacy_retrieval_candidates = legacy_gap_candidates.loc[
            legacy_gap_candidates["candidate_source_method"].eq("legacy_prior_gap_fill")
        ]
        for _, row in legacy_retrieval_candidates.iterrows():
            rows.append(
                {
                    "source_id": f"{source_prefix}-{source_counter:05d}",
                    "pilot_rank": int(row["batch3_rank"]),
                    "batch3_rank": int(row["batch3_rank"]),
                    "unitid": int(row["unitid"]),
                    "institution_name": row["institution_name"],
                    "target_year": int(row["target_year"]),
                    "candidate_url": row["candidate_url"],
                    "candidate_source_method": "legacy_prior_gap_fill",
                    "candidate_link_text": row["candidate_link_text"],
                    "archive_url": row["archive_url"],
                    "catalog_year_start": row["catalog_year_start"],
                    "catalog_year_end": row["catalog_year_end"],
                    "retrieval_status": "not_attempted",
                    "text_extract_status": "not_attempted",
                    "needs_human_review": False,
                    "review_reason": "",
                    "legacy_workbook": "public",
                    "legacy_sheet_name": "",
                    "legacy_excel_row": "",
                    "legacy_link_id": row.get("legacy_link_id", ""),
                    "legacy_selected_as_prior_evidence": row.get("selected_as_prior_evidence", ""),
                    "legacy_needs_review": row.get("legacy_needs_review", ""),
                    "legacy_review_reasons": row.get("legacy_review_reasons", ""),
                    "created_at": utc_now(),
                    "updated_at": utc_now(),
                }
            )
            source_counter += 1
    return pd.DataFrame(rows)


def build_stage_status(year_coverage: pd.DataFrame, retrieval_coverage: pd.DataFrame) -> pd.DataFrame:
    best = pd.DataFrame()
    if not retrieval_coverage.empty:
        retrieval_coverage = retrieval_coverage.copy()
        for col in ["candidate_url", "candidate_source_method", "candidate_link_text", "archive_url"]:
            if col not in retrieval_coverage.columns:
                retrieval_coverage[col] = ""
        best = (
            retrieval_coverage.sort_values(["unitid", "target_year", "source_id"])
            .groupby(["unitid", "target_year"], as_index=False)
            .first()
        )
    rows = year_coverage.copy()
    if not best.empty:
        rows = rows.merge(
            best[
                [
                    "unitid",
                    "target_year",
                    "source_id",
                    "candidate_url",
                    "candidate_source_method",
                    "candidate_link_text",
                    "archive_url",
                    "source_retrieved",
                    "best_retrieval_status",
                    "best_attempt_method",
                    "best_content_type",
                    "local_source_path",
                    "covers_target_year",
                ]
            ],
            on=["unitid", "target_year"],
            how="left",
            suffixes=("", "_retrieved"),
        )
    for col in [
        "source_id",
        "source_retrieved",
        "best_retrieval_status",
        "best_attempt_method",
        "best_content_type",
        "local_source_path",
        "covers_target_year",
    ]:
        if col not in rows.columns:
            rows[col] = ""
    status_rows = []
    for _, row in rows.iterrows():
        stage, stop_reason, next_action, explanation = stage_for_row(row)
        status_rows.append(
            {
                "batch3_rank": int(row["batch3_rank"]),
                "unitid": int(row["unitid"]),
                "institution_name": row["institution_name"],
                "target_year": int(row["target_year"]),
                "pipeline_stage": stage,
                "stop_reason": stop_reason,
                "next_batch_action": next_action,
                "human_decision_needed": False,
                "stage_explanation": explanation,
                "decision_status": clean_text(row.get("decision_status", "")),
                "preferred_source_root_url": clean_text(row.get("preferred_source_root_url", "")),
                "candidate_url": clean_text(row.get("candidate_url", "")),
                "candidate_link_text": clean_text(row.get("candidate_link_text", "")),
                "archive_url": clean_text(row.get("archive_url", "")),
                "retrieved_candidate_url": clean_text(row.get("candidate_url_retrieved", "")),
                "retrieved_candidate_method": clean_text(row.get("candidate_source_method", "")),
                "retrieved_candidate_link_text": clean_text(row.get("candidate_link_text_retrieved", "")),
                "retrieved_archive_url": clean_text(row.get("archive_url_retrieved", "")),
                "legacy_policy_page_url": clean_text(row.get("legacy_policy_page_url", "")),
                "retrieved_source_id": clean_text(row.get("source_id", "")),
                "source_retrieved": to_bool(row.get("source_retrieved", False)),
                "retrieval_status": clean_text(row.get("best_retrieval_status", "")),
                "retrieval_method": clean_text(row.get("best_attempt_method", "")),
                "retrieved_content_type": clean_text(row.get("best_content_type", "")),
                "covers_target_year": to_bool(row.get("covers_target_year", False)),
                "local_source_path": clean_text(row.get("local_source_path", "")),
                "archive_bound_inferred": to_bool(row.get("archive_bound_inferred", False)),
                "archive_bound_note": clean_text(row.get("archive_bound_note", "")),
                "interior_archive_gap_inferred": to_bool(row.get("interior_archive_gap_inferred", False)),
                "interior_archive_gap_note": clean_text(row.get("interior_archive_gap_note", "")),
                "created_at": utc_now(),
            }
        )
    return pd.DataFrame(status_rows).sort_values(["batch3_rank", "unitid", "target_year"])


def to_bool(value: object) -> bool:
    if pd.isna(value):
        return False
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def stage_for_row(row: pd.Series) -> tuple[str, str, str, str]:
    if to_bool(row.get("source_retrieved", False)):
        return (
            "source_retrieved",
            "policy_terms_not_searched",
            "policy_term_search",
            "Catalog source body was retrieved and saved; policy-term search has not run yet.",
        )
    retrieved_candidate_url = clean_text(row.get("retrieved_candidate_url", "")) or clean_text(
        row.get("candidate_url_retrieved", "")
    )
    if retrieved_candidate_url:
        return (
            "candidate_identified",
            "source_not_retrieved",
            "retrieval_recovery",
            "A year-level fallback candidate exists, but direct retrieval/recovery did not retrieve a source body.",
        )
    if clean_text(row.get("legacy_policy_page_url", "")):
        return (
            "root_identified",
            "policy_dating_needed",
            "policy_dating_workflow",
            "Legacy evidence provides a policy-page lead, but historical dating is needed before it can support panel years.",
        )
    if clean_text(row.get("decision_status", "")) != "preferred_source_root_identified":
        return (
            "no_source_path",
            "no_root_found",
            "source_root_discovery",
            "No likely official catalog root was identified by the bounded generated-root and legacy-lead pass.",
        )
    if clean_text(row.get("candidate_url", "")):
        return (
            "candidate_identified",
            "source_not_retrieved",
            "retrieval_recovery",
            "A year-level catalog candidate exists, but direct retrieval/recovery did not retrieve a source body.",
        )
    if to_bool(row.get("archive_bound_inferred", False)):
        return (
            "root_identified",
            "archive_bound",
            "defer_archive_bound",
            clean_text(row.get("archive_bound_note", "")),
        )
    if to_bool(row.get("interior_archive_gap_inferred", False)):
        return (
            "root_identified",
            "interior_archive_gap",
            "targeted_archive_gap_search",
            clean_text(row.get("interior_archive_gap_note", "")),
        )
    return (
        "root_identified",
        "no_candidate_found",
        "source_root_discovery",
        "Preferred root was identified, but no explicit year-level catalog candidate was found for this institution-year.",
    )


def write_summary(path: Path, stage_status: pd.DataFrame, outputs: Batch3Outputs) -> None:
    lines = [
        "# Phase 3 Batch 3 Catalog Discovery",
        "",
        f"Generated at: {utc_now()}",
        "",
        "Scope: generalized 10-institution catalog-discovery expansion; no policy extraction or classification.",
        "",
        "## Pipeline Stages",
        "",
    ]
    for stage, count in stage_status["pipeline_stage"].value_counts(dropna=False).items():
        lines.append(f"- {stage}: {count}")
    lines.extend(["", "## Next Batch Actions", ""])
    for action, count in stage_status["next_batch_action"].value_counts(dropna=False).items():
        lines.append(f"- {action}: {count}")
    lines.extend(["", "## Institutions", ""])
    for (unitid, name), group in stage_status.groupby(["unitid", "institution_name"], dropna=False):
        action_counts = ", ".join(f"{action}={count}" for action, count in group["next_batch_action"].value_counts().items())
        stages = ", ".join(f"{stage}={count}" for stage, count in group["pipeline_stage"].value_counts().items())
        lines.append(f"- {name} ({int(unitid)}): {action_counts}; stages: {stages}")
    lines.extend(["", "## Outputs", ""])
    for label, output_path in outputs.__dict__.items():
        if label != "summary_report":
            lines.append(f"- {label}: `{output_path}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_batch3_discovery(
    repo_root: Path,
    *,
    batch_size: int = BATCH_SIZE,
    timeout_seconds: int = 15,
) -> Batch3Outputs:
    repo_root = repo_root.resolve()
    pilot, links, targets, batch2 = read_inputs(repo_root)
    batch = select_batch3_institutions(pilot, batch2, batch_size=batch_size)
    legacy_leads = build_legacy_leads(batch, links)
    tasks = source_root_tasks(batch, legacy_leads)
    root_candidates = build_root_candidates(repo_root, legacy_leads, tasks, timeout_seconds=timeout_seconds)
    decisions = build_source_root_decisions(root_candidates, tasks)
    archive_pages, result_by_url = build_archive_pages(repo_root, decisions, timeout_seconds=timeout_seconds)
    year_candidates = build_year_candidates(archive_pages, result_by_url)
    observed_bounds = build_observed_candidate_bounds(archive_pages, result_by_url)
    year_coverage = build_year_coverage(batch, targets, decisions, year_candidates, archive_pages, observed_bounds)
    legacy_gap_candidates = build_legacy_gap_candidates(year_coverage, legacy_leads)
    year_coverage = add_legacy_gap_status(year_coverage, legacy_gap_candidates)
    inventory = build_inventory(year_coverage, legacy_gap_candidates)
    retrieval_attempts = build_retrieval_attempts(repo_root, inventory, timeout_seconds=timeout_seconds) if not inventory.empty else pd.DataFrame()
    retrieval_coverage = build_coverage(inventory, retrieval_attempts) if not inventory.empty else pd.DataFrame()
    if not retrieval_coverage.empty:
        retrieval_coverage = retrieval_coverage.merge(
            inventory[["source_id", "candidate_source_method", "candidate_link_text", "archive_url"]],
            on="source_id",
            how="left",
        )
    stage_status = build_stage_status(year_coverage, retrieval_coverage)

    outputs = Batch3Outputs(
        institutions=(repo_root / BATCH3_INSTITUTIONS_OUTPUT).resolve(),
        legacy_leads=(repo_root / BATCH3_LEGACY_LEADS_OUTPUT).resolve(),
        root_candidates=(repo_root / BATCH3_ROOT_CANDIDATES_OUTPUT).resolve(),
        source_root_decisions=(repo_root / BATCH3_SOURCE_ROOT_DECISIONS_OUTPUT).resolve(),
        archive_pages=(repo_root / BATCH3_ARCHIVE_PAGES_OUTPUT).resolve(),
        year_candidates=(repo_root / BATCH3_YEAR_CANDIDATES_OUTPUT).resolve(),
        year_coverage=(repo_root / BATCH3_YEAR_COVERAGE_OUTPUT).resolve(),
        legacy_gap_candidates=(repo_root / BATCH3_LEGACY_GAP_CANDIDATES_OUTPUT).resolve(),
        combined_inventory=(repo_root / BATCH3_COMBINED_INVENTORY_OUTPUT).resolve(),
        retrieval_attempts=(repo_root / BATCH3_RETRIEVAL_ATTEMPTS_OUTPUT).resolve(),
        retrieval_coverage=(repo_root / BATCH3_RETRIEVAL_COVERAGE_OUTPUT).resolve(),
        stage_status=(repo_root / BATCH3_STAGE_STATUS_OUTPUT).resolve(),
        summary_report=(repo_root / BATCH3_SUMMARY_OUTPUT).resolve(),
    )
    for output_path in outputs.__dict__.values():
        output_path.parent.mkdir(parents=True, exist_ok=True)
    batch.to_csv(outputs.institutions, index=False)
    legacy_leads.to_csv(outputs.legacy_leads, index=False)
    root_candidates.to_csv(outputs.root_candidates, index=False)
    decisions.to_csv(outputs.source_root_decisions, index=False)
    archive_pages.to_csv(outputs.archive_pages, index=False)
    year_candidates.to_csv(outputs.year_candidates, index=False)
    year_coverage.to_csv(outputs.year_coverage, index=False)
    legacy_gap_candidates.to_csv(outputs.legacy_gap_candidates, index=False)
    inventory.to_csv(outputs.combined_inventory, index=False)
    retrieval_attempts.to_csv(outputs.retrieval_attempts, index=False)
    retrieval_coverage.to_csv(outputs.retrieval_coverage, index=False)
    stage_status.to_csv(outputs.stage_status, index=False)
    write_summary(outputs.summary_report, stage_status, outputs)
    return outputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a generalized Phase 3 batch-3 catalog-discovery expansion.")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    parser.add_argument("--timeout-seconds", type=int, default=15)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve() if args.root else repo_root_from_cwd()
    outputs = run_batch3_discovery(root, batch_size=args.batch_size, timeout_seconds=args.timeout_seconds)
    for label, output_path in outputs.__dict__.items():
        print(f"{label}: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
