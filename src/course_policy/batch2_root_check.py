"""Check batch-2 legacy leads and candidate official catalog roots."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pandas as pd

from .ai_config import repo_root_from_cwd
from .batch2_pilot import (
    BATCH2_LEGACY_LEADS_OUTPUT,
    BATCH2_SOURCE_ROOT_TASKS_OUTPUT,
    BATCH2_STATUS_SUMMARY_OUTPUT,
    clean_text,
    parent_url,
)
from .catalog_retrieval import retrieve_url, save_source_body


DATA_DIR = Path("../data_policy_pipeline")
INTERIM_DIR = DATA_DIR / "interim"
LOG_DIR = DATA_DIR / "logs"

BATCH2_ROOT_CANDIDATES_OUTPUT = INTERIM_DIR / "catalog_batch2_root_candidates.csv"
BATCH2_SOURCE_ROOT_DECISIONS_OUTPUT = INTERIM_DIR / "catalog_batch2_source_root_decisions.csv"
BATCH2_ROOT_CHECK_SUMMARY_OUTPUT = LOG_DIR / "phase3_batch2_root_check_summary.md"


@dataclass(frozen=True)
class Batch2RootCheckOutputs:
    root_candidates: Path
    source_root_decisions: Path
    source_root_tasks: Path
    status_summary: Path
    summary_report: Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_inputs(repo_root: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    return (
        pd.read_csv(repo_root / BATCH2_LEGACY_LEADS_OUTPUT, low_memory=False),
        pd.read_csv(repo_root / BATCH2_SOURCE_ROOT_TASKS_OUTPUT, low_memory=False),
        pd.read_csv(repo_root / BATCH2_STATUS_SUMMARY_OUTPUT, low_memory=False),
    )


def normalized_url(url: str) -> str:
    url = clean_text(url)
    if not url or url.lower() in {"nan", "none", "null"}:
        return ""
    parsed = urlparse(url if "://" in url else f"https://{url}")
    path = parsed.path or "/"
    return parsed._replace(path=path, params="", query="", fragment="").geturl()


def registrable_domain(hostname: str) -> str:
    parts = hostname.lower().split(".")
    if len(parts) <= 2:
        return hostname.lower()
    return ".".join(parts[-2:])


def catalog_archive_path_candidates(domain: str, web_host: str = "") -> list[dict[str, str]]:
    hosts = [domain]
    if web_host and web_host.lower() not in {"", domain}:
        hosts.append(web_host.lower())
    if f"www.{domain}" not in hosts:
        hosts.append(f"www.{domain}")

    paths = [
        "catalogarchive/",
        "catalogarchives/",
        "catalog-archive/",
        "catalog-archives/",
        "catalog/archive/",
        "catalog/archives/",
        "catalogs/archive/",
        "catalogs/archives/",
        "archives/catalogs/",
        "academic-catalog/",
        "academic-catalogs/",
        "registrar/catalog/",
        "registrar/catalogs/",
        "academics/catalog/",
        "academics/catalogs/",
    ]
    rows = []
    for host in hosts:
        for path in paths:
            rows.append(
                {
                    "candidate_url": f"https://{host}/{path}",
                    "candidate_source_type": "generated_catalog_archive_path",
                }
            )
    return rows


def legacy_derived_collection_roots(url: str) -> list[dict[str, str]]:
    raw_url = clean_text(url)
    if not raw_url:
        return []
    parsed = urlparse(raw_url if "://" in raw_url else f"https://{raw_url}")
    rows: list[dict[str, str]] = []
    base = f"{parsed.scheme}://{parsed.netloc}"
    path_parts = [part for part in parsed.path.split("/") if part]
    query = parse_qs(parsed.query)

    context = query.get("context", [""])[0]
    if parsed.path == "/cgi/viewcontent.cgi" and context:
        rows.append(
            {
                "candidate_url": f"{base}/{context.strip('/')}/",
                "candidate_source_type": "legacy_derived_repository_collection",
            }
        )

    if len(path_parts) >= 3 and path_parts[0] == "digital" and path_parts[1] == "collection":
        rows.append(
            {
                "candidate_url": f"{base}/digital/collection/{path_parts[2]}/",
                "candidate_source_type": "legacy_derived_repository_collection",
            }
        )

    lowered_parts = [part.lower() for part in path_parts]
    for idx, part in enumerate(lowered_parts):
        if "catalogarchive" in part or (("catalog" in part or "bulletin" in part) and "archive" in part):
            rows.append(
                {
                    "candidate_url": f"{base}/{'/'.join(path_parts[: idx + 1])}/",
                    "candidate_source_type": "legacy_derived_archive_root",
                }
            )

    for idx, part in enumerate(lowered_parts):
        if part in {"catalog", "catalogs", "bulletin", "bulletins"}:
            rows.append(
                {
                    "candidate_url": f"{base}/{'/'.join(path_parts[: idx + 1])}/",
                    "candidate_source_type": "legacy_derived_archive_root",
                }
            )

    return rows


def candidate_urls_for_task(task: pd.Series, legacy_leads: pd.DataFrame) -> list[dict[str, str]]:
    webaddr = normalized_url(str(task.get("webaddr", "")))
    parsed = urlparse(webaddr)
    domain = registrable_domain(parsed.netloc)
    urls: list[dict[str, str]] = []

    urls.extend(catalog_archive_path_candidates(domain, parsed.netloc))
    for template, source_type in [
        (f"https://catalog.{domain}/", "generated_catalog_subdomain"),
        (f"https://catalogs.{domain}/", "generated_catalogs_subdomain"),
        (f"https://{domain}/catalog/", "generated_catalog_path"),
        (f"https://{domain}/catalogs/", "generated_catalogs_path"),
        (f"https://{domain}/registrar/catalogs/", "generated_registrar_catalogs_path"),
        (f"https://{domain}/academics/catalog/", "generated_academics_catalog_path"),
    ]:
        urls.append({"candidate_url": template, "candidate_source_type": source_type})

    rows = legacy_leads.loc[legacy_leads["unitid"].eq(task["unitid"])]
    for _, lead in rows.iterrows():
        raw_legacy_url = clean_text(lead.get("legacy_url", ""))
        urls.extend(legacy_derived_collection_roots(raw_legacy_url))
        legacy_url = normalized_url(raw_legacy_url)
        legacy_parent = normalized_url(str(lead.get("legacy_url_parent", "")))
        if legacy_url and not legacy_parent:
            legacy_parent = normalized_url(parent_url(legacy_url))
        if legacy_parent:
            urls.append({"candidate_url": legacy_parent, "candidate_source_type": "legacy_parent_url"})
        if legacy_url:
            urls.append({"candidate_url": legacy_url, "candidate_source_type": "legacy_url"})

    seen = set()
    deduped = []
    for row in urls:
        url = row["candidate_url"]
        key = (url, row["candidate_source_type"])
        if not url or key in seen:
            continue
        deduped.append(row)
        seen.add(key)
    return deduped


def link_score(result: dict[str, object]) -> tuple[int, int]:
    records = result.get("link_records", [])
    catalog_links = 0
    archive_links = 0
    for record in records:
        text = f"{record.get('text', '')} {record.get('url', '')}".lower()
        if "catalog" in text or "bulletin" in text:
            catalog_links += 1
        if "archive" in text or "past" in text or "pdf" in text:
            archive_links += 1
    return catalog_links, archive_links


def likely_catalog_root(result: dict[str, object], candidate_url: str, source_type: str) -> bool:
    if result["retrieval_status"] not in {"retrieved", "retrieved_truncated"}:
        return False
    title = str(result.get("page_title", "")).lower()
    host = urlparse(candidate_url).netloc.lower()
    path = urlparse(candidate_url).path.lower()
    catalog_links, archive_links = link_score(result)
    return (
        "catalog" in title
        or "bulletin" in title
        or host.startswith(("catalog.", "catalogs."))
        or source_type == "legacy_derived_repository_collection"
        or source_type in {"legacy_derived_archive_root", "legacy_derived_repository_collection"}
        and ("catalog" in path or "bulletin" in path)
        and (catalog_links >= 1 or archive_links >= 1 or "catalog" in title or "bulletin" in title)
        or catalog_links >= 3
        or (source_type == "legacy_parent_url" and archive_links >= 1)
    )


def root_priority(source_type: str, result: dict[str, object], candidate_url: str) -> int:
    host = urlparse(candidate_url).netloc.lower()
    path = urlparse(candidate_url).path.lower()
    if source_type in {"legacy_derived_archive_root", "legacy_derived_repository_collection"}:
        return 5
    if source_type == "generated_catalog_archive_path" and likely_catalog_root(result, candidate_url, source_type):
        return 8
    if "archive" in path and likely_catalog_root(result, candidate_url, source_type):
        return 8
    if source_type.startswith("generated") and host.startswith(("catalog.", "catalogs.")):
        return 10
    if source_type == "legacy_parent_url" and likely_catalog_root(result, candidate_url, source_type):
        return 20
    if source_type.startswith("generated"):
        return 30
    if source_type == "legacy_url":
        return 80
    return 90


def build_root_candidates(
    repo_root: Path,
    legacy_leads: pd.DataFrame,
    source_root_tasks: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    for _, task in source_root_tasks.sort_values(["batch2_rank", "unitid"]).iterrows():
        for idx, candidate in enumerate(candidate_urls_for_task(task, legacy_leads), 1):
            result = retrieve_url(candidate["candidate_url"])
            local_source_path = ""
            if result["retrieval_status"] in {"retrieved", "retrieved_truncated"}:
                local_source_path = str(
                    save_source_body(
                        repo_root,
                        f"batch2-root-{int(task['unitid'])}-{idx:02d}",
                        "root_check",
                        candidate["candidate_url"],
                        str(result["content_type"]),
                        result["body"],
                    )
                )
            catalog_links, archive_links = link_score(result)
            is_likely_root = likely_catalog_root(
                result,
                candidate["candidate_url"],
                candidate["candidate_source_type"],
            )
            rows.append(
                {
                    "root_candidate_id": f"batch2-root-{int(task['batch2_rank']):02d}-{idx:02d}",
                    "batch2_rank": int(task["batch2_rank"]),
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
                    "likely_catalog_root": is_likely_root,
                    "root_priority": root_priority(candidate["candidate_source_type"], result, candidate["candidate_url"]),
                    "local_source_path": local_source_path,
                    "created_at": utc_now(),
                }
            )
    return pd.DataFrame(rows).sort_values(["batch2_rank", "root_priority", "candidate_url"])


def build_source_root_decisions(root_candidates: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (rank, unitid, name), group in root_candidates.groupby(
        ["batch2_rank", "unitid", "institution_name"], dropna=False
    ):
        usable = group.loc[group["likely_catalog_root"].fillna(False)].copy()
        if usable.empty:
            rows.append(
                {
                    "batch2_rank": rank,
                    "unitid": unitid,
                    "institution_name": name,
                    "decision_status": "source_root_not_found",
                    "preferred_source_root_url": "",
                    "preferred_source_root_type": "",
                    "preferred_source_root_title": "",
                    "recommended_next_step": "Use targeted official-site search or Wayback on legacy URLs; do not count coverage yet.",
                    "created_at": utc_now(),
                }
            )
            continue
        preferred = usable.sort_values(["root_priority", "candidate_source_type", "candidate_url"]).iloc[0]
        rows.append(
            {
                "batch2_rank": rank,
                "unitid": unitid,
                "institution_name": name,
                "decision_status": "preferred_source_root_identified",
                "preferred_source_root_url": preferred["candidate_url"],
                "preferred_source_root_type": preferred["candidate_source_type"],
                "preferred_source_root_title": preferred["page_title"],
                "recommended_next_step": "Expand catalog-year candidates from this root, then retrieve and validate explicit catalog-year evidence.",
                "created_at": utc_now(),
            }
        )
    return pd.DataFrame(rows).sort_values(["batch2_rank", "unitid"])


def update_source_root_tasks(tasks: pd.DataFrame, decisions: pd.DataFrame) -> pd.DataFrame:
    out = tasks.drop(
        columns=[
            "task_status",
            "decision_status",
            "preferred_source_root_name",
            "preferred_source_root_url",
            "preferred_source_root_type",
            "preferred_source_root_title",
            "recommended_next_step",
        ],
        errors="ignore",
    ).merge(
        decisions[
            [
                "unitid",
                "decision_status",
                "preferred_source_root_url",
                "preferred_source_root_type",
                "preferred_source_root_title",
                "recommended_next_step",
            ]
        ],
        on="unitid",
        how="left",
    )
    out["task_status"] = out["decision_status"].fillna("source_root_discovery_needed")
    out["preferred_source_root_name"] = out["preferred_source_root_title"].fillna("")
    return out.sort_values(["batch2_rank", "unitid"])


def update_status_summary(summary: pd.DataFrame, decisions: pd.DataFrame) -> pd.DataFrame:
    out = summary.drop(
        columns=["overall_status", "task_status", "decision_status", "recommended_next_step"],
        errors="ignore",
    ).merge(
        decisions[["unitid", "decision_status", "recommended_next_step"]],
        on="unitid",
        how="left",
    )
    out["overall_status"] = out["decision_status"].fillna("source_root_discovery_needed")
    out["task_status"] = out["overall_status"]
    return out.sort_values(["batch2_rank", "unitid"])


def write_summary(path: Path, decisions: pd.DataFrame, candidates: pd.DataFrame) -> None:
    lines = [
        "# Phase 3 Batch 2 Root Check",
        "",
        f"Generated at: {utc_now()}",
        "",
        "Scope: bounded legacy URL and official catalog-root check for the 5-institution batch-2 pilot.",
        "",
        "## Decision Counts",
        "",
    ]
    for status, count in decisions["decision_status"].value_counts(dropna=False).items():
        lines.append(f"- {status}: {count}")
    lines.extend(["", "## Preferred Roots", ""])
    for _, row in decisions.iterrows():
        lines.append(
            f"- {row['institution_name']}: {row['decision_status']}; {row['preferred_source_root_url'] or 'none'}"
        )
    lines.extend(["", "## Candidate Retrieval Status", ""])
    for status, count in candidates["retrieval_status"].value_counts(dropna=False).items():
        lines.append(f"- {status}: {count}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_batch2_root_check(repo_root: Path) -> Batch2RootCheckOutputs:
    repo_root = repo_root.resolve()
    legacy_leads, tasks, summary = read_inputs(repo_root)
    root_candidates = build_root_candidates(repo_root, legacy_leads, tasks)
    decisions = build_source_root_decisions(root_candidates)
    updated_tasks = update_source_root_tasks(tasks, decisions)
    updated_summary = update_status_summary(summary, decisions)

    outputs = Batch2RootCheckOutputs(
        root_candidates=(repo_root / BATCH2_ROOT_CANDIDATES_OUTPUT).resolve(),
        source_root_decisions=(repo_root / BATCH2_SOURCE_ROOT_DECISIONS_OUTPUT).resolve(),
        source_root_tasks=(repo_root / BATCH2_SOURCE_ROOT_TASKS_OUTPUT).resolve(),
        status_summary=(repo_root / BATCH2_STATUS_SUMMARY_OUTPUT).resolve(),
        summary_report=(repo_root / BATCH2_ROOT_CHECK_SUMMARY_OUTPUT).resolve(),
    )
    for output_path in outputs.__dict__.values():
        output_path.parent.mkdir(parents=True, exist_ok=True)
    root_candidates.to_csv(outputs.root_candidates, index=False)
    decisions.to_csv(outputs.source_root_decisions, index=False)
    updated_tasks.to_csv(outputs.source_root_tasks, index=False)
    updated_summary.to_csv(outputs.status_summary, index=False)
    write_summary(outputs.summary_report, decisions, root_candidates)
    return outputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Phase 3 batch-2 legacy/root URL check.")
    parser.add_argument("--root", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve() if args.root else repo_root_from_cwd()
    outputs = run_batch2_root_check(root)
    for label, output_path in outputs.__dict__.items():
        print(f"{label}: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
