"""Run bounded fresh catalog discovery for public institutions without public legacy URLs."""

from __future__ import annotations

import argparse
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

from .ai_config import repo_root_from_cwd
from .batch2_pilot import clean_text
from .batch2_root_check import candidate_urls_for_task, likely_catalog_root, link_score, root_priority
from .batch2_year_candidates import add_candidate_selection_rank_columns, candidate_archive_urls, candidate_selection_sort_columns
from .batch3_discovery import (
    ROOT_RETRIEVAL_BYTES,
    RETRIEVED_STATUSES,
    build_source_root_decisions,
    build_year_candidates,
    prioritized_root_candidates,
)
from .catalog_retrieval import retrieve_url, save_source_body
from .institution_universe import TARGET_END_YEAR, TARGET_START_YEAR


DATA_DIR = Path("artifacts/policy_data_internal")
INTERIM_DIR = DATA_DIR / "interim"
REVIEW_DIR = DATA_DIR / "review"
LOG_DIR = DATA_DIR / "logs"
DELIVERY_DIR = Path("../policy_data")

PUBLIC_NO_LEGACY_QUEUE_CLEAN = DELIVERY_DIR / "public_no_legacy_fresh_discovery_queue.csv"
INSTITUTION_YEAR_TARGETS_INPUT = INTERIM_DIR / "institution_year_targets.csv"
RETRYABLE_RETRIEVAL_STATUSES = {"url_error", "timeout", "network_error", "error"}
RETRYABLE_HTTP_STATUSES = {408, 425, 429, 500, 502, 503, 504}
DEFAULT_RETRIEVAL_ATTEMPTS = 3


@dataclass(frozen=True)
class PublicFreshDiscoveryOutputs:
    institutions_csv: Path
    root_candidates_csv: Path
    source_root_decisions_csv: Path
    archive_pages_csv: Path
    year_candidates_csv: Path
    year_panel_csv: Path
    institution_status_csv: Path
    workbook: Path
    summary_md: Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def suffixed_path(path: Path, suffix: str) -> Path:
    if not suffix:
        return path
    clean_suffix = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in suffix.strip())
    return path.with_name(f"{path.stem}_{clean_suffix}{path.suffix}")


def read_public_no_legacy_queue(repo_root: Path) -> pd.DataFrame:
    path = (repo_root / PUBLIC_NO_LEGACY_QUEUE_CLEAN).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Missing public no-legacy queue: {path}")
    return pd.read_csv(path, low_memory=False)


def select_public_fresh_institutions(
    queue: pd.DataFrame,
    *,
    limit: int | None,
    rank_start: int,
    include_branch_campuses: bool,
) -> pd.DataFrame:
    selected = queue.copy()
    selected["institution_name"] = selected["institution_name"].map(clean_text)
    selected["webaddr"] = selected["webaddr"].map(clean_text)
    selected = selected.loc[selected["public_phase3_coverage_status"].eq("no_public_legacy_url_needs_fresh_discovery")]
    if not include_branch_campuses:
        branch_terms = (
            "campus",
            "center",
            "digital immersion",
            "extension",
            "law school",
            "state university-",
            "system eversity",
        )
        lowered = selected["institution_name"].str.lower()
        selected = selected.loc[~lowered.apply(lambda value: any(term in value for term in branch_terms))]
    selected = selected.sort_values(["state", "institution_name", "unitid"]).reset_index(drop=True)
    selected.insert(0, "fresh_rank", range(1, len(selected) + 1))
    selected = selected.loc[selected["fresh_rank"].ge(rank_start)].copy()
    if limit is not None:
        selected = selected.head(limit).copy()
    selected["batch3_rank"] = range(1, len(selected) + 1)
    selected["created_at"] = utc_now()
    columns = [
        "fresh_rank",
        "batch3_rank",
        "unitid",
        "institution_name",
        "state",
        "webaddr",
        "public_phase3_coverage_status",
        "public_legacy_url_count",
        "public_legacy_year_count",
        "public_legacy_rows",
        "created_at",
    ]
    for column in columns:
        if column not in selected.columns:
            selected[column] = ""
    return selected[columns]


def empty_legacy_leads() -> pd.DataFrame:
    return pd.DataFrame(columns=["unitid", "legacy_url", "legacy_url_parent"])


def retryable_http_status(value: object) -> bool:
    try:
        return int(float(str(value))) in RETRYABLE_HTTP_STATUSES
    except (TypeError, ValueError):
        return False


def should_retry_retrieval(result: dict[str, object]) -> bool:
    status = clean_text(result.get("retrieval_status"))
    if status in RETRYABLE_RETRIEVAL_STATUSES:
        return True
    if status == "http_error" and retryable_http_status(result.get("http_status")):
        return True
    return False


def retrieve_url_with_retries(
    url: str,
    *,
    timeout_seconds: int,
    max_bytes: int,
    attempts: int = DEFAULT_RETRIEVAL_ATTEMPTS,
) -> dict[str, object]:
    """Retry transient URL failures so a flaky lookup does not drop a panel."""
    last_result: dict[str, object] = {}
    attempt_count = max(1, attempts)
    for attempt in range(1, attempt_count + 1):
        last_result = retrieve_url(url, timeout_seconds=timeout_seconds, max_bytes=max_bytes)
        last_result["retrieval_attempt_count"] = attempt
        if not should_retry_retrieval(last_result):
            return last_result
        if attempt < attempt_count:
            time.sleep(min(0.25 * attempt, 1.0))
    return last_result


def build_root_candidates_concurrent(
    repo_root: Path,
    legacy_leads: pd.DataFrame,
    tasks: pd.DataFrame,
    *,
    timeout_seconds: int,
    max_candidates_per_institution: int,
    max_workers: int,
    source_slug: str = "public-fresh",
) -> pd.DataFrame:
    jobs: list[tuple[pd.Series, int, dict[str, str]]] = []
    for _, task in tasks.sort_values(["batch3_rank", "unitid"]).iterrows():
        candidates = prioritized_root_candidates(candidate_urls_for_task(task, legacy_leads))[:max_candidates_per_institution]
        for idx, candidate in enumerate(candidates, 1):
            jobs.append((task.copy(), idx, candidate))
    if not jobs:
        return pd.DataFrame()

    def fetch(job: tuple[pd.Series, int, dict[str, str]]) -> tuple[pd.Series, int, dict[str, str], dict[str, object]]:
        task, idx, candidate = job
        result = retrieve_url_with_retries(
            candidate["candidate_url"],
            timeout_seconds=timeout_seconds,
            max_bytes=ROOT_RETRIEVAL_BYTES,
        )
        return task, idx, candidate, result

    rows: list[dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(fetch, job) for job in jobs]
        for future in as_completed(futures):
            task, idx, candidate, result = future.result()
            local_source_path = ""
            if result["retrieval_status"] in RETRIEVED_STATUSES:
                local_source_path = str(
                    save_source_body(
                        repo_root,
                        f"{source_slug}-root-{int(task['unitid'])}-{idx:02d}",
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
                    "root_candidate_id": f"{source_slug}-root-{int(task['batch3_rank']):03d}-{idx:02d}",
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
                    "error_type": result.get("error_type", ""),
                    "error_message": result.get("error_message", ""),
                    "retrieval_attempt_count": result.get("retrieval_attempt_count", 1),
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


def build_archive_pages_concurrent(
    repo_root: Path,
    decisions: pd.DataFrame,
    *,
    timeout_seconds: int,
    max_archive_pages_per_institution: int,
    max_workers: int,
    source_slug: str = "public-fresh",
) -> tuple[pd.DataFrame, dict[str, dict[str, object]]]:
    usable = decisions.loc[decisions["decision_status"].eq("preferred_source_root_identified")].copy()
    if usable.empty:
        return pd.DataFrame(), {}

    def error_result(exc: BaseException) -> dict[str, object]:
        return {
            "retrieval_status": "error",
            "http_status": "",
            "final_url": "",
            "content_type": "",
            "page_title": "",
            "year_hints": "",
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "retrieval_attempt_count": 1,
            "link_records": [],
            "body": b"",
        }

    root_results: dict[str, dict[str, object]] = {}
    print(f"[archive-pages] {source_slug} root fetches={len(usable)}", flush=True)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {
            executor.submit(
                retrieve_url_with_retries,
                clean_text(decision["preferred_source_root_url"]),
                timeout_seconds=timeout_seconds,
                max_bytes=ROOT_RETRIEVAL_BYTES,
            ): clean_text(decision["preferred_source_root_url"])
            for _, decision in usable.iterrows()
        }
        for completed, future in enumerate(as_completed(future_to_url), 1):
            url = future_to_url[future]
            try:
                root_results[url] = future.result()
            except Exception as exc:  # pragma: no cover - network failures vary.
                root_results[url] = error_result(exc)
            if completed == len(future_to_url) or completed % 25 == 0:
                print(f"[archive-pages] {source_slug} roots {completed}/{len(future_to_url)}", flush=True)

    archive_jobs: list[tuple[pd.Series, int, dict[str, str]]] = []
    seen: set[tuple[int, str]] = set()
    for _, decision in usable.sort_values(["batch3_rank", "unitid"]).iterrows():
        root_url = clean_text(decision["preferred_source_root_url"])
        archives = candidate_archive_urls(root_results.get(root_url, {}), root_url)[:max_archive_pages_per_institution]
        for idx, archive in enumerate(archives, 1):
            key = (int(decision["unitid"]), archive["archive_url"])
            if key in seen:
                continue
            seen.add(key)
            archive_jobs.append((decision.copy(), idx, archive))

    result_by_url = dict(root_results)
    rows: list[dict[str, object]] = []

    def fetch_archive(job: tuple[pd.Series, int, dict[str, str]]) -> tuple[pd.Series, int, dict[str, str], dict[str, object]]:
        decision, idx, archive = job
        archive_url = archive["archive_url"]
        if archive_url in root_results:
            result = root_results[archive_url]
        else:
            result = retrieve_url_with_retries(
                archive_url,
                timeout_seconds=timeout_seconds,
                max_bytes=ROOT_RETRIEVAL_BYTES,
            )
        return decision, idx, archive, result

    print(f"[archive-pages] {source_slug} archive fetches={len(archive_jobs)}", flush=True)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_job = {executor.submit(fetch_archive, job): job for job in archive_jobs}
        for completed, future in enumerate(as_completed(future_to_job), 1):
            try:
                decision, idx, archive, result = future.result()
            except Exception as exc:  # pragma: no cover - network failures vary.
                decision, idx, archive = future_to_job[future]
                result = error_result(exc)
            archive_url = archive["archive_url"]
            result_by_url[archive_url] = result
            local_source_path = ""
            if result["retrieval_status"] in RETRIEVED_STATUSES:
                local_source_path = str(
                    save_source_body(
                        repo_root,
                        f"{source_slug}-archive-{int(decision['unitid'])}-{idx:02d}",
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
                    "preferred_source_root_url": clean_text(decision["preferred_source_root_url"]),
                    "archive_url": archive_url,
                    "archive_source": archive["archive_source"],
                    "archive_link_text": archive["archive_link_text"],
                    "retrieval_status": result["retrieval_status"],
                    "http_status": result["http_status"],
                    "final_url": result["final_url"],
                    "content_type": result["content_type"],
                    "page_title": result["page_title"],
                    "year_hints": result["year_hints"],
                    "error_type": result.get("error_type", ""),
                    "error_message": result.get("error_message", ""),
                    "retrieval_attempt_count": result.get("retrieval_attempt_count", 1),
                    "link_count": len(result.get("link_records", [])),
                    "local_source_path": local_source_path,
                    "created_at": utc_now(),
                }
            )
            if completed == len(future_to_job) or completed % 25 == 0:
                print(f"[archive-pages] {source_slug} archives {completed}/{len(future_to_job)}", flush=True)
    nested_archive_sources = {
        "contentdm_collection_api",
        "contentdm_collection_year_api",
        "root_contentdm_collection_link",
        "root_archive_link",
        "root_catalog_collection_link",
        "archive_pagination_link",
    }
    frontier_rows = list(rows)
    for nested_depth in range(1, 3):
        nested_count_by_unitid: dict[int, int] = {}
        nested_jobs: list[tuple[pd.Series, int, dict[str, str]]] = []
        for row in frontier_rows:
            unitid = int(row["unitid"])
            remaining = max_archive_pages_per_institution - nested_count_by_unitid.get(unitid, 0)
            if remaining <= 0:
                continue
            archive_url = clean_text(row["archive_url"])
            result = result_by_url.get(archive_url, {})
            nested_archives = [
                archive
                for archive in candidate_archive_urls(result, archive_url)
                if archive["archive_source"] in nested_archive_sources
            ]
            for archive in nested_archives:
                if remaining <= 0:
                    break
                key = (unitid, archive["archive_url"])
                if key in seen:
                    continue
                seen.add(key)
                remaining -= 1
                nested_count_by_unitid[unitid] = nested_count_by_unitid.get(unitid, 0) + 1
                nested_archive = dict(archive)
                nested_archive["archive_source"] = f"nested{nested_depth}_{archive['archive_source']}"
                child_text = clean_text(nested_archive.get("archive_link_text", ""))
                nested_archive["archive_link_text"] = child_text or clean_text(row.get("archive_link_text", ""))
                idx = len(rows) + nested_count_by_unitid[unitid]
                decision = pd.Series(
                    {
                        "batch3_rank": row["batch3_rank"],
                        "unitid": row["unitid"],
                        "institution_name": row["institution_name"],
                        "preferred_source_root_url": row["preferred_source_root_url"],
                    }
                )
                nested_jobs.append((decision, idx, nested_archive))

        print(f"[archive-pages] {source_slug} nested depth {nested_depth} archive fetches={len(nested_jobs)}", flush=True)
        if not nested_jobs:
            frontier_rows = []
            continue
        new_rows: list[dict[str, object]] = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_job = {executor.submit(fetch_archive, job): job for job in nested_jobs}
            for completed, future in enumerate(as_completed(future_to_job), 1):
                try:
                    decision, idx, archive, result = future.result()
                except Exception as exc:  # pragma: no cover - network failures vary.
                    decision, idx, archive = future_to_job[future]
                    result = error_result(exc)
                archive_url = archive["archive_url"]
                result_by_url[archive_url] = result
                local_source_path = ""
                if result["retrieval_status"] in RETRIEVED_STATUSES:
                    local_source_path = str(
                        save_source_body(
                            repo_root,
                            f"{source_slug}-archive-{int(decision['unitid'])}-{idx:02d}",
                            "archive_page",
                            archive_url,
                            str(result["content_type"]),
                            result["body"],
                        )
                    )
                row = {
                    "batch3_rank": int(decision["batch3_rank"]),
                    "unitid": int(decision["unitid"]),
                    "institution_name": decision["institution_name"],
                    "preferred_source_root_url": clean_text(decision["preferred_source_root_url"]),
                    "archive_url": archive_url,
                    "archive_source": archive["archive_source"],
                    "archive_link_text": archive["archive_link_text"],
                    "retrieval_status": result["retrieval_status"],
                    "http_status": result["http_status"],
                    "final_url": result["final_url"],
                    "content_type": result["content_type"],
                    "page_title": result["page_title"],
                    "year_hints": result["year_hints"],
                    "error_type": result.get("error_type", ""),
                    "error_message": result.get("error_message", ""),
                    "retrieval_attempt_count": result.get("retrieval_attempt_count", 1),
                    "link_count": len(result.get("link_records", [])),
                    "local_source_path": local_source_path,
                    "created_at": utc_now(),
                }
                rows.append(row)
                new_rows.append(row)
                if completed == len(future_to_job) or completed % 25 == 0:
                    print(
                        f"[archive-pages] {source_slug} nested depth {nested_depth} archives {completed}/{len(future_to_job)}",
                        flush=True,
                    )
        frontier_rows = new_rows
    if not rows:
        return pd.DataFrame(), result_by_url
    return pd.DataFrame(rows).sort_values(["batch3_rank", "unitid", "archive_url"]), result_by_url


def build_year_panel(repo_root: Path, institutions: pd.DataFrame, year_candidates: pd.DataFrame) -> pd.DataFrame:
    targets = pd.read_csv(repo_root / INSTITUTION_YEAR_TARGETS_INPUT, low_memory=False)
    targets = targets.loc[
        targets["unitid"].isin(set(institutions["unitid"].astype(int)))
        & targets["year"].between(TARGET_START_YEAR, TARGET_END_YEAR)
    ].copy()
    targets = targets.rename(columns={"year": "target_year"})
    targets = targets.merge(
        institutions[["unitid", "fresh_rank", "institution_name", "state", "webaddr"]],
        on=["unitid", "institution_name"],
        how="left",
    )
    if year_candidates.empty:
        targets["best_url"] = ""
        targets["best_url_source"] = ""
        targets["catalog_year_start"] = ""
        targets["catalog_year_end"] = ""
        targets["candidate_link_text"] = ""
        targets["archive_url"] = ""
        return targets.sort_values(["fresh_rank", "unitid", "target_year"])

    candidates = year_candidates.copy()
    candidates = add_candidate_selection_rank_columns(candidates)
    chosen = (
        candidates.sort_values(candidate_selection_sort_columns(["unitid", "target_year"]))
        .drop_duplicates(["unitid", "target_year"], keep="first")
        .rename(columns={"candidate_url": "best_url"})
    )
    keep = [
        "unitid",
        "target_year",
        "best_url",
        "catalog_year_start",
        "catalog_year_end",
        "candidate_link_text",
        "candidate_evidence_source",
        "archive_url",
    ]
    for column in keep:
        if column not in chosen.columns:
            chosen[column] = ""
    panel = targets.merge(chosen[keep], on=["unitid", "target_year"], how="left")
    panel["best_url"] = panel["best_url"].fillna("").map(clean_text)
    panel["best_url_source"] = panel["candidate_evidence_source"].fillna("").map(clean_text)
    for column in ["catalog_year_start", "catalog_year_end", "candidate_link_text", "archive_url"]:
        panel[column] = panel[column].fillna("")
    return panel.sort_values(["fresh_rank", "unitid", "target_year"])


def root_signal_counts(root_candidates: pd.DataFrame) -> pd.DataFrame:
    if root_candidates.empty:
        return pd.DataFrame(columns=["unitid", "retrieved_root_count", "likely_root_count", "root_catalog_link_count", "root_archive_link_count"])
    roots = root_candidates.copy()
    roots["retrieved_root"] = roots["retrieval_status"].isin(RETRIEVED_STATUSES)
    return (
        roots.groupby("unitid", as_index=False)
        .agg(
            retrieved_root_count=("retrieved_root", "sum"),
            likely_root_count=("likely_catalog_root", "sum"),
            root_catalog_link_count=("catalog_link_count", "max"),
            root_archive_link_count=("archive_link_count", "max"),
        )
    )


def classify_institution_status(
    institutions: pd.DataFrame,
    root_candidates: pd.DataFrame,
    decisions: pd.DataFrame,
    archive_pages: pd.DataFrame,
    year_candidates: pd.DataFrame,
    year_panel: pd.DataFrame,
) -> pd.DataFrame:
    roots = root_signal_counts(root_candidates)
    decision_cols = ["unitid", "decision_status", "preferred_source_root_url", "preferred_source_root_type", "preferred_source_root_title"]
    decisions_compact = decisions[decision_cols].copy() if not decisions.empty else pd.DataFrame(columns=decision_cols)

    archive_summary = (
        archive_pages.groupby("unitid", as_index=False)
        .agg(
            archive_page_count=("archive_url", "nunique"),
            retrieved_archive_page_count=("retrieval_status", lambda values: int(pd.Series(values).isin(RETRIEVED_STATUSES).sum())),
            archive_min_year_hint=("year_hints", lambda values: first_year_hint(values, minimum=True)),
            archive_max_year_hint=("year_hints", lambda values: first_year_hint(values, minimum=False)),
        )
        if not archive_pages.empty
        else pd.DataFrame(columns=["unitid", "archive_page_count", "retrieved_archive_page_count", "archive_min_year_hint", "archive_max_year_hint"])
    )
    candidate_summary = (
        year_candidates.groupby("unitid", as_index=False)
        .agg(
            explicit_year_candidate_count=("candidate_url", "nunique"),
            min_candidate_year=("target_year", "min"),
            max_candidate_year=("target_year", "max"),
        )
        if not year_candidates.empty
        else pd.DataFrame(columns=["unitid", "explicit_year_candidate_count", "min_candidate_year", "max_candidate_year"])
    )
    panel_summary = (
        year_panel.groupby("unitid", as_index=False)
        .agg(
            panel_years_with_best_url=("best_url", lambda values: int(pd.Series(values).fillna("").astype(str).str.strip().ne("").sum())),
            panel_first_year_with_best_url=("target_year", lambda values: ""),
        )
        if not year_panel.empty
        else pd.DataFrame(columns=["unitid", "panel_years_with_best_url", "panel_first_year_with_best_url"])
    )
    if not year_panel.empty:
        first_last = (
            year_panel.loc[year_panel["best_url"].fillna("").astype(str).str.strip().ne("")]
            .groupby("unitid", as_index=False)
            .agg(panel_first_year_with_best_url=("target_year", "min"), panel_last_year_with_best_url=("target_year", "max"))
        )
        panel_summary = panel_summary.drop(columns=["panel_first_year_with_best_url"], errors="ignore").merge(
            first_last, on="unitid", how="left"
        )

    status = institutions.merge(roots, on="unitid", how="left")
    status = status.merge(decisions_compact, on="unitid", how="left")
    status = status.merge(archive_summary, on="unitid", how="left")
    status = status.merge(candidate_summary, on="unitid", how="left")
    status = status.merge(panel_summary, on="unitid", how="left")
    for column in [
        "retrieved_root_count",
        "likely_root_count",
        "root_catalog_link_count",
        "root_archive_link_count",
        "archive_page_count",
        "retrieved_archive_page_count",
        "explicit_year_candidate_count",
        "panel_years_with_best_url",
    ]:
        status[column] = pd.to_numeric(status[column], errors="coerce").fillna(0).astype(int)
    for column in [
        "decision_status",
        "preferred_source_root_url",
        "preferred_source_root_type",
        "preferred_source_root_title",
        "archive_min_year_hint",
        "archive_max_year_hint",
        "min_candidate_year",
        "max_candidate_year",
        "panel_first_year_with_best_url",
        "panel_last_year_with_best_url",
    ]:
        if column not in status.columns:
            status[column] = ""
        status[column] = status[column].fillna("")

    status["fresh_discovery_status"] = status.apply(fresh_status_for_row, axis=1)
    status["next_pipeline_action"] = status["fresh_discovery_status"].map(
        {
            "year_candidates_found": "retrieve_and_validate_candidate_catalogs",
            "source_root_found_no_explicit_years": "ai_or_search_expand_root",
            "root_candidates_retrieved_but_not_catalog": "ai_or_search_find_better_root",
            "source_root_not_found": "ai_or_search_fresh_discovery",
        }
    )
    status["created_at"] = utc_now()
    return status.sort_values(["fresh_rank", "unitid"])


def first_year_hint(values: pd.Series, *, minimum: bool) -> str:
    years: list[int] = []
    for value in values.dropna().astype(str):
        for piece in value.replace(",", ";").split(";"):
            piece = piece.strip()
            if piece.isdigit():
                year = int(piece)
                if TARGET_START_YEAR <= year <= 2035:
                    years.append(year)
    if not years:
        return ""
    return str(min(years) if minimum else max(years))


def fresh_status_for_row(row: pd.Series) -> str:
    if int(row.get("explicit_year_candidate_count", 0) or 0) > 0:
        return "year_candidates_found"
    if clean_text(row.get("decision_status")) == "preferred_source_root_identified":
        return "source_root_found_no_explicit_years"
    if int(row.get("retrieved_root_count", 0) or 0) > 0:
        return "root_candidates_retrieved_but_not_catalog"
    return "source_root_not_found"


def remove_excel_illegal_characters(value: object) -> object:
    if not isinstance(value, str):
        return value
    return ILLEGAL_CHARACTERS_RE.sub("", value)


def excel_safe_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    out = frame.copy()
    for column in out.select_dtypes(include=["object"]).columns:
        out[column] = out[column].map(remove_excel_illegal_characters)
    return out


def write_workbook(path: Path, sheets: dict[str, pd.DataFrame]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for name, frame in sheets.items():
            excel_safe_frame(frame).to_excel(writer, sheet_name=name[:31], index=False)


def write_summary(path: Path, *, suffix: str, status: pd.DataFrame, outputs: PublicFreshDiscoveryOutputs) -> None:
    counts = status["fresh_discovery_status"].value_counts().to_dict() if not status.empty else {}
    lines = [
        "# Public Fresh Discovery Run",
        "",
        f"Generated at: {utc_now()}",
        f"Run suffix: `{suffix}`",
        "",
        "Scope: public institutions with no public legacy URL. This run does bounded official-site root probing and archive/year-candidate extraction only; broad search and AI suggestions are deferred.",
        "",
        "## Bottom Line",
        "",
        f"- Institutions processed: {status['unitid'].nunique() if not status.empty else 0}",
        f"- Institutions with explicit year candidates: {int(counts.get('year_candidates_found', 0))}",
        f"- Institutions with source root but no explicit years: {int(counts.get('source_root_found_no_explicit_years', 0))}",
        f"- Institutions with retrieved non-catalog roots only: {int(counts.get('root_candidates_retrieved_but_not_catalog', 0))}",
        f"- Institutions with no retrieved source root: {int(counts.get('source_root_not_found', 0))}",
        "",
        "## Outputs",
        "",
    ]
    for label, output_path in outputs.__dict__.items():
        lines.append(f"- {label}: `{output_path}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_delivery_summary(path: Path, *, suffix: str, status: pd.DataFrame) -> None:
    counts = status["fresh_discovery_status"].value_counts().to_dict() if not status.empty else {}
    lines = [
        "# Public Fresh Discovery Run",
        "",
        f"Generated at: {utc_now()}",
        f"Run suffix: `{suffix}`",
        "",
        "Scope: public institutions with no public legacy URL. This run does bounded official-site root probing and archive/year-candidate extraction only; broad search and AI suggestions are deferred.",
        "",
        "## Bottom Line",
        "",
        f"- Institutions processed: {status['unitid'].nunique() if not status.empty else 0}",
        f"- Institutions with explicit year candidates: {int(counts.get('year_candidates_found', 0))}",
        f"- Institutions with source root but no explicit years: {int(counts.get('source_root_found_no_explicit_years', 0))}",
        f"- Institutions with retrieved non-catalog roots only: {int(counts.get('root_candidates_retrieved_but_not_catalog', 0))}",
        f"- Institutions with no retrieved source root: {int(counts.get('source_root_not_found', 0))}",
        "",
        "## Clean Review Files",
        "",
        f"- Workbook: `public_fresh_discovery_{suffix}.xlsx`",
        f"- Institution status: `public_fresh_discovery_status_{suffix}.csv`",
        f"- Year panel: `public_fresh_year_panel_{suffix}.csv`",
        f"- Year candidates: `public_fresh_year_candidates_{suffix}.csv`",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def copy_delivery(repo_root: Path, outputs: PublicFreshDiscoveryOutputs, suffix: str, status: pd.DataFrame) -> None:
    delivery = (repo_root / DELIVERY_DIR).resolve()
    delivery.mkdir(parents=True, exist_ok=True)
    for source, stem in [
        (outputs.workbook, "public_fresh_discovery"),
        (outputs.institution_status_csv, "public_fresh_discovery_status"),
        (outputs.year_panel_csv, "public_fresh_year_panel"),
        (outputs.year_candidates_csv, "public_fresh_year_candidates"),
    ]:
        target = delivery / f"{stem}_{suffix}{source.suffix}"
        target.write_bytes(source.read_bytes())
    write_delivery_summary(delivery / f"public_fresh_discovery_summary_{suffix}.md", suffix=suffix, status=status)


def run(
    repo_root: Path,
    *,
    suffix: str,
    limit: int | None,
    rank_start: int = 1,
    include_branch_campuses: bool = True,
    timeout_seconds: int = 4,
    max_root_candidates_per_institution: int = 24,
    max_archive_pages_per_institution: int = 12,
    max_workers: int = 16,
) -> PublicFreshDiscoveryOutputs:
    repo_root = repo_root.resolve()
    queue = read_public_no_legacy_queue(repo_root)
    institutions = select_public_fresh_institutions(
        queue,
        limit=limit,
        rank_start=rank_start,
        include_branch_campuses=include_branch_campuses,
    )
    legacy_leads = empty_legacy_leads()
    tasks = institutions.rename(columns={"fresh_rank": "public_fresh_rank"}).copy()
    root_candidates = build_root_candidates_concurrent(
        repo_root,
        legacy_leads,
        tasks,
        timeout_seconds=timeout_seconds,
        max_candidates_per_institution=max_root_candidates_per_institution,
        max_workers=max_workers,
    )
    decisions = build_source_root_decisions(root_candidates, tasks)
    archive_pages, result_by_url = build_archive_pages_concurrent(
        repo_root,
        decisions,
        timeout_seconds=timeout_seconds,
        max_archive_pages_per_institution=max_archive_pages_per_institution,
        max_workers=max_workers,
    )
    year_candidates = build_year_candidates(archive_pages, result_by_url)
    year_panel = build_year_panel(repo_root, institutions, year_candidates)
    status = classify_institution_status(institutions, root_candidates, decisions, archive_pages, year_candidates, year_panel)

    outputs = PublicFreshDiscoveryOutputs(
        institutions_csv=suffixed_path((repo_root / INTERIM_DIR / "public_fresh_discovery_institutions.csv").resolve(), suffix),
        root_candidates_csv=suffixed_path((repo_root / INTERIM_DIR / "public_fresh_discovery_root_candidates.csv").resolve(), suffix),
        source_root_decisions_csv=suffixed_path((repo_root / INTERIM_DIR / "public_fresh_discovery_source_root_decisions.csv").resolve(), suffix),
        archive_pages_csv=suffixed_path((repo_root / INTERIM_DIR / "public_fresh_discovery_archive_pages.csv").resolve(), suffix),
        year_candidates_csv=suffixed_path((repo_root / INTERIM_DIR / "public_fresh_discovery_year_candidates.csv").resolve(), suffix),
        year_panel_csv=suffixed_path((repo_root / REVIEW_DIR / "public_fresh_discovery_year_panel.csv").resolve(), suffix),
        institution_status_csv=suffixed_path((repo_root / REVIEW_DIR / "public_fresh_discovery_status.csv").resolve(), suffix),
        workbook=suffixed_path((repo_root / REVIEW_DIR / "public_fresh_discovery.xlsx").resolve(), suffix),
        summary_md=suffixed_path((repo_root / LOG_DIR / "public_fresh_discovery_summary.md").resolve(), suffix),
    )
    for output_path in outputs.__dict__.values():
        output_path.parent.mkdir(parents=True, exist_ok=True)
    institutions.to_csv(outputs.institutions_csv, index=False)
    root_candidates.to_csv(outputs.root_candidates_csv, index=False)
    decisions.to_csv(outputs.source_root_decisions_csv, index=False)
    archive_pages.to_csv(outputs.archive_pages_csv, index=False)
    year_candidates.to_csv(outputs.year_candidates_csv, index=False)
    year_panel.to_csv(outputs.year_panel_csv, index=False)
    status.to_csv(outputs.institution_status_csv, index=False)
    write_workbook(
        outputs.workbook,
        {
            "start_here": status,
            "year_panel": year_panel,
            "year_candidates": year_candidates,
            "source_root_decisions": decisions,
            "root_candidates": root_candidates,
            "archive_pages": archive_pages,
        },
    )
    write_summary(outputs.summary_md, suffix=suffix, status=status, outputs=outputs)
    copy_delivery(repo_root, outputs, suffix, status)
    return outputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--suffix", required=True)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--rank-start", type=int, default=1)
    parser.add_argument("--exclude-branch-campuses", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=4)
    parser.add_argument("--max-root-candidates-per-institution", type=int, default=24)
    parser.add_argument("--max-archive-pages-per-institution", type=int, default=12)
    parser.add_argument("--max-workers", type=int, default=16)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = args.root.resolve() if args.root else repo_root_from_cwd()
    outputs = run(
        repo_root,
        suffix=args.suffix,
        limit=args.limit,
        rank_start=args.rank_start,
        include_branch_campuses=not args.exclude_branch_campuses,
        timeout_seconds=args.timeout_seconds,
        max_root_candidates_per_institution=args.max_root_candidates_per_institution,
        max_archive_pages_per_institution=args.max_archive_pages_per_institution,
        max_workers=args.max_workers,
    )
    for label, output_path in outputs.__dict__.items():
        print(f"{label}: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
