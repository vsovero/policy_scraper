"""Retrieve and recover candidate catalog sources for the Phase 3 pilot."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import mimetypes
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen

import pandas as pd

from .ai_config import repo_root_from_cwd


DATA_DIR = Path("../data_policy_pipeline")
INTERIM_DIR = DATA_DIR / "interim"
LOG_DIR = DATA_DIR / "logs"
CATALOG_SOURCE_DIR = DATA_DIR / "catalog_sources" / "pilot"

CATALOG_INVENTORY_INPUT = INTERIM_DIR / "catalog_inventory_pilot.csv"
RETRIEVAL_ATTEMPTS_OUTPUT = INTERIM_DIR / "catalog_retrieval_attempts_pilot.csv"
RETRIEVAL_COVERAGE_OUTPUT = INTERIM_DIR / "catalog_retrieval_coverage_pilot.csv"
RETRIEVAL_DEDUPED_COVERAGE_OUTPUT = INTERIM_DIR / "catalog_retrieval_coverage_pilot_deduped.csv"
SUMMARY_OUTPUT = LOG_DIR / "phase3_catalog_retrieval_pilot_summary.md"

MAX_SOURCE_BYTES = 25 * 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 25
WAYBACK_AVAILABLE_URL = "https://archive.org/wayback/available?url={url}&timestamp={timestamp}"
WAYBACK_CDX_URL = (
    "https://web.archive.org/cdx?url={url}&output=json&filter=statuscode:200"
    "&collapse=digest&fl=timestamp,original,mimetype,statuscode,digest&limit=10"
)


@dataclass(frozen=True)
class RetrievalOutputs:
    retrieval_attempts: Path
    retrieval_coverage: Path
    retrieval_coverage_deduped: Path
    summary_report: Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def retrieve_url(
    url: str,
    *,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    max_bytes: int = MAX_SOURCE_BYTES,
) -> dict[str, Any]:
    """Fetch a URL and return metadata plus response body when successful."""
    result: dict[str, Any] = {
        "retrieval_status": "not_attempted",
        "http_status": "",
        "final_url": "",
        "content_type": "",
        "content_length_bytes": "",
        "page_title": "",
        "year_hints": "",
        "sha256": "",
        "error_type": "",
        "error_message": "",
        "body": b"",
        "links": [],
    }
    try:
        request = Request(url, headers=browser_headers())
        with urlopen(request, timeout=timeout_seconds) as response:
            body = response.read(max_bytes + 1)
            if len(body) > max_bytes:
                body = body[:max_bytes]
                result["retrieval_status"] = "retrieved_truncated"
            else:
                result["retrieval_status"] = "retrieved"
            final_url = response.geturl()
            content_type = response.headers.get("content-type", "")
            text = decode_body(body, content_type)
            result.update(
                {
                    "http_status": getattr(response, "status", ""),
                    "final_url": final_url,
                    "content_type": content_type,
                    "content_length_bytes": len(body),
                    "page_title": extract_title(text, final_url, content_type),
                    "year_hints": "; ".join(str(year) for year in infer_years(f"{url} {final_url} {text[:8000]}")),
                    "sha256": sha256_bytes(body),
                    "body": body,
                    "links": extract_links(text, final_url, content_type),
                }
            )
    except HTTPError as exc:
        result.update(
            {
                "retrieval_status": "http_error",
                "http_status": exc.code,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            }
        )
    except URLError as exc:
        result.update(
            {
                "retrieval_status": "url_error",
                "error_type": type(exc).__name__,
                "error_message": str(exc.reason),
            }
        )
    except Exception as exc:  # pragma: no cover - remote failures vary.
        result.update({"retrieval_status": "error", "error_type": type(exc).__name__, "error_message": str(exc)})
    return result


def browser_headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept": "text/html,application/pdf,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }


def decode_body(body: bytes, content_type: str) -> str:
    if body.startswith(b"%PDF") or "pdf" in content_type.lower():
        return pdf_metadata_text(body)
    for encoding in ["utf-8", "latin-1"]:
        try:
            return body.decode(encoding, errors="replace")
        except Exception:
            continue
    return ""


def pdf_metadata_text(body: bytes) -> str:
    text = body[:12000].decode("latin-1", errors="ignore")
    pieces = []
    for key in ["Title", "Author", "Subject"]:
        match = re.search(rf"/{key}\s*\(([^)]{{1,300}})\)", text)
        if match:
            pieces.append(match.group(1))
    return " ".join(pieces)


def extract_title(text: str, url: str, content_type: str) -> str:
    if "pdf" in content_type.lower():
        return text.strip()[:300] or title_from_url(url)
    match = re.search(r"<title[^>]*>(.*?)</title>", text, flags=re.IGNORECASE | re.DOTALL)
    if match:
        return re.sub(r"\s+", " ", html.unescape(match.group(1))).strip()[:300]
    return title_from_url(url)


def extract_links(text: str, base_url: str, content_type: str) -> list[str]:
    if "html" not in content_type.lower() and "<a" not in text.lower():
        return []
    links: list[str] = []
    for match in re.finditer(r"""href=["']([^"']+)["']""", text, flags=re.IGNORECASE):
        href = html.unescape(match.group(1)).strip()
        if href and not href.startswith(("#", "mailto:", "tel:", "javascript:")):
            links.append(urljoin(base_url, href))
    return sorted(set(links))


def title_from_url(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    return path.rsplit("/", 1)[-1].replace("-", " ").replace("_", " ")[:300]


def infer_years(text: str) -> list[int]:
    years = sorted({int(match.group(0)) for match in re.finditer(r"(?:19|20)\d{2}", text)})
    return [year for year in years if 1990 <= year <= 2030]


def sha256_bytes(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def source_extension(url: str, content_type: str) -> str:
    parsed_ext = Path(urlparse(url).path).suffix.lower()
    if parsed_ext in {".pdf", ".html", ".htm", ".txt", ".xml"}:
        return parsed_ext
    guessed = mimetypes.guess_extension(content_type.split(";")[0].strip()) if content_type else None
    if guessed in {".pdf", ".html", ".htm", ".txt", ".xml"}:
        return guessed
    if "pdf" in content_type.lower():
        return ".pdf"
    if "html" in content_type.lower():
        return ".html"
    return ".bin"


def save_source_body(
    root: Path,
    source_id: str,
    attempt_method: str,
    url: str,
    content_type: str,
    body: bytes,
) -> Path:
    source_dir = (root / CATALOG_SOURCE_DIR / source_id).resolve()
    source_dir.mkdir(parents=True, exist_ok=True)
    ext = source_extension(url, content_type)
    path = source_dir / f"{attempt_method}{ext}"
    path.write_bytes(body)
    return path


def candidate_attempt_urls(url: str, target_year: int) -> list[tuple[str, str]]:
    attempts = direct_attempt_urls(url)
    attempts.append(("wayback_available", wayback_available_url(url, target_year)))
    return dedupe_attempts(attempts)


def direct_attempt_urls(url: str) -> list[tuple[str, str]]:
    attempts = [("direct", url)]
    parsed = urlparse(url)
    if parsed.scheme == "http":
        attempts.append(("https_variant", urlunparse(parsed._replace(scheme="https"))))
    elif parsed.scheme == "https":
        attempts.append(("http_variant", urlunparse(parsed._replace(scheme="http"))))
    return dedupe_attempts(attempts)


def dedupe_attempts(attempts: list[tuple[str, str]]) -> list[tuple[str, str]]:
    seen = set()
    out = []
    for method, url in attempts:
        if url and url not in seen:
            out.append((method, url))
            seen.add(url)
    return out


def wayback_available_url(url: str, target_year: int) -> str:
    timestamp = f"{target_year}0701"
    return WAYBACK_AVAILABLE_URL.format(url=quote(url, safe=""), timestamp=timestamp)


def wayback_available_latest_url(url: str) -> str:
    return "https://archive.org/wayback/available?url=" + quote(url, safe="")


def wayback_cdx_url(url: str) -> str:
    return WAYBACK_CDX_URL.format(url=quote(url, safe=""))


def parse_wayback_snapshot(body: bytes) -> str:
    try:
        data = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        return ""
    closest = data.get("archived_snapshots", {}).get("closest", {})
    if closest.get("available") and closest.get("url"):
        return str(closest["url"])
    return ""


def parse_cdx_snapshots(body: bytes, target_year: int) -> list[str]:
    try:
        rows = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        return []
    if not isinstance(rows, list) or len(rows) < 2:
        return []
    snapshots: list[tuple[int, str]] = []
    for row in rows[1:]:
        if not isinstance(row, list) or not row:
            continue
        timestamp = str(row[0])
        if not timestamp.isdigit():
            continue
        distance = abs(int(timestamp[:4]) - target_year)
        snapshots.append((distance, f"https://web.archive.org/web/{timestamp}/{row[1] if len(row) > 1 else ''}"))
    return [url for _, url in sorted(snapshots, key=lambda item: item[0])]


def parent_urls(url: str, max_depth: int = 3) -> list[str]:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    urls: list[str] = []
    for depth in range(1, min(max_depth, len(parts)) + 1):
        parent_path = "/" + "/".join(parts[:-depth]) + "/"
        if parent_path == "//":
            parent_path = "/"
        urls.append(urlunparse(parsed._replace(path=parent_path, query="", fragment="")))
    return dedupe_urls(urls)


def dedupe_urls(urls: list[str]) -> list[str]:
    seen = set()
    out = []
    for url in urls:
        if url and url not in seen:
            out.append(url)
            seen.add(url)
    return out


def candidate_links_from_parent(parent_result: dict[str, Any], original_url: str, target_year: int) -> list[str]:
    original_name = Path(urlparse(original_url).path).name.lower()
    candidates: list[tuple[int, str]] = []
    for link in parent_result.get("links", []):
        link_lower = link.lower()
        score = 0
        if original_name and Path(urlparse(link).path).name.lower() == original_name:
            score += 50
        if str(target_year) in link_lower or str(target_year + 1) in link_lower or str(target_year - 1) in link_lower:
            score += 20
        if any(keyword in link_lower for keyword in ["catalog", "bulletin", "undergrad", "policy", "archive"]):
            score += 10
        if link_lower.endswith((".pdf", ".html", ".htm")):
            score += 5
        if score > 0:
            candidates.append((score, link))
    return [url for _, url in sorted(candidates, key=lambda item: item[0], reverse=True)[:5]]


def should_try_recovery(result: dict[str, Any]) -> bool:
    return result["retrieval_status"] not in {"retrieved", "retrieved_truncated"}


def result_has_target_year(result: dict[str, Any], target_year: int) -> bool:
    haystack = f"{result.get('final_url', '')} {result.get('page_title', '')} {result.get('year_hints', '')}"
    return str(target_year) in haystack


METADATA_ATTEMPT_METHODS = {"wayback_available", "wayback_available_latest", "wayback_cdx_lookup", "parent_page"}


def build_retrieval_attempts(
    repo_root: Path,
    inventory: pd.DataFrame,
    *,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    created_at = utc_now()
    leads = inventory[inventory["candidate_url"].fillna("").astype(str).str.strip().ne("")].copy()
    leads = leads.drop_duplicates(subset=["candidate_url"]).copy()
    for _, source in leads.sort_values(["pilot_rank", "unitid", "target_year", "source_id"]).iterrows():
        sequence = 1.0
        source_retrieved = False
        original_url = str(source["candidate_url"])
        target_year = int(source["target_year"])

        for method, attempt_url in direct_attempt_urls(original_url):
            if source_retrieved:
                break
            result = retrieve_url(attempt_url, timeout_seconds=timeout_seconds)
            local_path = ""
            if result["retrieval_status"] in {"retrieved", "retrieved_truncated"}:
                local_path = str(
                    save_source_body(
                        repo_root,
                        str(source["source_id"]),
                        method,
                        attempt_url,
                        str(result["content_type"]),
                        result["body"],
                    )
                )
                source_retrieved = True
            rows.append(
                attempt_row(
                    source,
                    len(rows) + 1,
                    sequence,
                    method,
                    attempt_url,
                    result,
                    local_path,
                    created_at,
                    recovered_from="",
                )
            )
            sequence += 1.0

        if not source_retrieved:
            for parent_url in parent_urls(original_url):
                if source_retrieved:
                    break
                parent_result = retrieve_url(parent_url, timeout_seconds=timeout_seconds)
                rows.append(
                    attempt_row(
                        source,
                        len(rows) + 1,
                        sequence,
                        "parent_page",
                        parent_url,
                        parent_result,
                        "",
                        created_at,
                        recovered_from=original_url,
                    )
                )
                sequence += 1.0
                if parent_result["retrieval_status"] not in {"retrieved", "retrieved_truncated"}:
                    continue
                for link_url in candidate_links_from_parent(parent_result, original_url, target_year):
                    if source_retrieved:
                        break
                    link_result = retrieve_url(link_url, timeout_seconds=timeout_seconds)
                    link_path = ""
                    if link_result["retrieval_status"] in {"retrieved", "retrieved_truncated"}:
                        link_path = str(
                            save_source_body(
                                repo_root,
                                str(source["source_id"]),
                                "parent_link",
                                link_url,
                                str(link_result["content_type"]),
                                link_result["body"],
                            )
                        )
                        source_retrieved = result_has_target_year(link_result, target_year)
                    rows.append(
                        attempt_row(
                            source,
                            len(rows) + 1,
                            sequence,
                            "parent_link",
                            link_url,
                            link_result,
                            link_path,
                            created_at,
                            recovered_from=parent_url,
                        )
                    )
                    sequence += 1.0

        if not source_retrieved:
            wayback_lookup_url = wayback_available_url(original_url, target_year)
            wayback_result = retrieve_url(wayback_lookup_url, timeout_seconds=timeout_seconds)
            rows.append(
                attempt_row(
                    source,
                    len(rows) + 1,
                    sequence,
                    "wayback_available",
                    wayback_lookup_url,
                    wayback_result,
                    "",
                    created_at,
                    recovered_from="",
                )
            )
            sequence += 1.0
            recovered_url = ""
            recovered_from_url = wayback_lookup_url
            if wayback_result["retrieval_status"] in {"retrieved", "retrieved_truncated"}:
                recovered_url = parse_wayback_snapshot(wayback_result["body"])
            if not recovered_url:
                wayback_lookup_url = wayback_available_latest_url(original_url)
                recovered_from_url = wayback_lookup_url
                wayback_result = retrieve_url(wayback_lookup_url, timeout_seconds=timeout_seconds)
                rows.append(
                    attempt_row(
                        source,
                        len(rows) + 1,
                        sequence,
                        "wayback_available_latest",
                        wayback_lookup_url,
                        wayback_result,
                        "",
                        created_at,
                        recovered_from="",
                    )
                )
                sequence += 1.0
                if wayback_result["retrieval_status"] in {"retrieved", "retrieved_truncated"}:
                    recovered_url = parse_wayback_snapshot(wayback_result["body"])
            if recovered_url:
                snapshot = retrieve_url(recovered_url, timeout_seconds=timeout_seconds)
                snapshot_path = ""
                if snapshot["retrieval_status"] in {"retrieved", "retrieved_truncated"}:
                    snapshot_path = str(
                        save_source_body(
                            repo_root,
                            str(source["source_id"]),
                            "wayback_snapshot",
                            recovered_url,
                            str(snapshot["content_type"]),
                            snapshot["body"],
                        )
                    )
                    source_retrieved = True
                rows.append(
                    attempt_row(
                        source,
                        len(rows) + 1,
                        sequence,
                        "wayback_snapshot",
                        recovered_url,
                        snapshot,
                        snapshot_path,
                        created_at,
                        recovered_from=recovered_from_url,
                    )
                )
                sequence += 1.0

        if not source_retrieved:
            cdx_result = retrieve_url(wayback_cdx_url(original_url), timeout_seconds=timeout_seconds)
            rows.append(
                attempt_row(
                    source,
                    len(rows) + 1,
                    sequence,
                    "wayback_cdx_lookup",
                    wayback_cdx_url(original_url),
                    cdx_result,
                    "",
                    created_at,
                    recovered_from="",
                )
            )
            sequence += 1.0
            if cdx_result["retrieval_status"] in {"retrieved", "retrieved_truncated"}:
                for snapshot_url in parse_cdx_snapshots(cdx_result["body"], target_year)[:3]:
                    if source_retrieved:
                        break
                    snapshot = retrieve_url(snapshot_url, timeout_seconds=timeout_seconds)
                    snapshot_path = ""
                    if snapshot["retrieval_status"] in {"retrieved", "retrieved_truncated"}:
                        snapshot_path = str(
                            save_source_body(
                                repo_root,
                                str(source["source_id"]),
                                "wayback_cdx_snapshot",
                                snapshot_url,
                                str(snapshot["content_type"]),
                                snapshot["body"],
                            )
                        )
                        source_retrieved = True
                    rows.append(
                        attempt_row(
                            source,
                            len(rows) + 1,
                            sequence,
                            "wayback_cdx_snapshot",
                            snapshot_url,
                            snapshot,
                            snapshot_path,
                            created_at,
                            recovered_from=wayback_cdx_url(original_url),
                        )
                    )
                    sequence += 1.0
    return pd.DataFrame(rows).sort_values(["source_id", "attempt_sequence", "attempt_method"])


def attempt_row(
    source: pd.Series,
    attempt_id: int,
    attempt_sequence: float,
    method: str,
    attempt_url: str,
    result: dict[str, Any],
    local_path: str,
    created_at: str,
    *,
    recovered_from: str,
) -> dict[str, Any]:
    return {
        "retrieval_attempt_id": attempt_id,
        "source_id": source["source_id"],
        "unitid": int(source["unitid"]),
        "institution_name": source["institution_name"],
        "target_year": int(source["target_year"]),
        "original_candidate_url": source["candidate_url"],
        "attempt_sequence": attempt_sequence,
        "attempt_method": method,
        "attempt_url": attempt_url,
        "recovered_from": recovered_from,
        "retrieval_status": result["retrieval_status"],
        "http_status": result["http_status"],
        "final_url": result["final_url"],
        "content_type": result["content_type"],
        "content_length_bytes": result["content_length_bytes"],
        "page_title": result["page_title"],
        "year_hints": result["year_hints"],
        "sha256": result["sha256"],
        "local_source_path": local_path,
        "error_type": result["error_type"],
        "error_message": result["error_message"],
        "legacy_workbook": source.get("legacy_workbook", ""),
        "legacy_sheet_name": source.get("legacy_sheet_name", ""),
        "legacy_excel_row": source.get("legacy_excel_row", ""),
        "legacy_link_id": source.get("legacy_link_id", ""),
        "legacy_selected_as_prior_evidence": source.get("legacy_selected_as_prior_evidence", ""),
        "legacy_needs_review": source.get("legacy_needs_review", ""),
        "legacy_review_reasons": source.get("legacy_review_reasons", ""),
        "created_at": created_at,
    }


def build_coverage(inventory: pd.DataFrame, attempts: pd.DataFrame) -> pd.DataFrame:
    leads = inventory[inventory["candidate_url"].fillna("").astype(str).str.strip().ne("")].copy()
    success = attempts[
        attempts["retrieval_status"].isin(["retrieved", "retrieved_truncated"])
        & ~attempts["attempt_method"].isin(METADATA_ATTEMPT_METHODS)
    ].copy()
    if success.empty:
        leads["best_retrieval_status"] = "not_retrieved"
        leads["best_attempt_method"] = ""
        leads["best_final_url"] = ""
        leads["best_content_type"] = ""
        leads["best_page_title"] = ""
        leads["best_year_hints"] = ""
        leads["local_source_path"] = ""
        leads["sha256"] = ""
    else:
        success["method_rank"] = success["attempt_method"].map(
            {"direct": 1, "https_variant": 2, "http_variant": 3, "wayback_snapshot": 4, "wayback_available": 9}
        ).fillna(8)
        best = (
            success.sort_values(["source_id", "method_rank", "attempt_sequence"])
            .groupby("source_id", as_index=False)
            .first()
        )
        best = best.rename(
            columns={
                "retrieval_status": "best_retrieval_status",
                "attempt_method": "best_attempt_method",
                "final_url": "best_final_url",
                "content_type": "best_content_type",
                "page_title": "best_page_title",
                "year_hints": "best_year_hints",
                "local_source_path": "best_local_source_path",
                "sha256": "best_sha256",
            }
        )
        leads = leads.merge(
            best[
                [
                    "original_candidate_url",
                    "best_retrieval_status",
                    "best_attempt_method",
                    "best_final_url",
                    "best_content_type",
                    "best_page_title",
                    "best_year_hints",
                    "best_local_source_path",
                    "best_sha256",
                ]
            ],
            left_on="candidate_url",
            right_on="original_candidate_url",
            how="left",
        )
        leads = leads.drop(columns=["original_candidate_url"], errors="ignore")
        leads["best_retrieval_status"] = leads["best_retrieval_status"].fillna("not_retrieved")
        leads["best_attempt_method"] = leads["best_attempt_method"].fillna("")
        leads["best_final_url"] = leads["best_final_url"].fillna("")
        leads["best_content_type"] = leads["best_content_type"].fillna("")
        leads["best_page_title"] = leads["best_page_title"].fillna("")
        leads["best_year_hints"] = leads["best_year_hints"].fillna("")
        leads["local_source_path"] = leads["best_local_source_path"].fillna("")
        leads["sha256"] = leads["best_sha256"].fillna("")

    leads["source_retrieved"] = leads["best_retrieval_status"].isin(["retrieved", "retrieved_truncated"])
    leads["target_year_in_hints"] = leads.apply(
        lambda row: str(int(row["target_year"])) in str(row.get("best_year_hints", "")),
        axis=1,
    )
    return leads[
        [
            "source_id",
            "pilot_rank",
            "unitid",
            "institution_name",
            "target_year",
            "candidate_url",
            "source_retrieved",
            "best_retrieval_status",
            "best_attempt_method",
            "best_final_url",
            "best_content_type",
            "best_page_title",
            "best_year_hints",
            "target_year_in_hints",
            "local_source_path",
            "sha256",
            "needs_human_review",
            "review_reason",
            "legacy_workbook",
            "legacy_sheet_name",
            "legacy_excel_row",
            "legacy_link_id",
            "legacy_selected_as_prior_evidence",
            "legacy_needs_review",
            "legacy_review_reasons",
        ]
    ].sort_values(["pilot_rank", "unitid", "target_year", "source_id"])


def build_deduped_coverage(coverage: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        coverage.groupby(["unitid", "target_year", "candidate_url"], dropna=False)
        .agg(
            institution_name=("institution_name", "first"),
            source_ids=("source_id", unique_join),
            source_id_count=("source_id", "nunique"),
            pilot_rank=("pilot_rank", "min"),
            source_retrieved=("source_retrieved", "max"),
            best_retrieval_status=("best_retrieval_status", "first"),
            best_attempt_method=("best_attempt_method", "first"),
            best_final_url=("best_final_url", "first"),
            best_content_type=("best_content_type", "first"),
            best_page_title=("best_page_title", "first"),
            best_year_hints=("best_year_hints", "first"),
            target_year_in_hints=("target_year_in_hints", "max"),
            local_source_path=("local_source_path", "first"),
            sha256=("sha256", "first"),
            needs_human_review=("needs_human_review", "max"),
            review_reason=("review_reason", unique_join),
            legacy_workbooks=("legacy_workbook", unique_join),
            legacy_sheet_names=("legacy_sheet_name", unique_join),
            legacy_excel_rows=("legacy_excel_row", unique_join),
            legacy_link_ids=("legacy_link_id", unique_join),
            legacy_selected_prior_count=("legacy_selected_as_prior_evidence", "sum"),
            legacy_needs_review=("legacy_needs_review", "max"),
            legacy_review_reasons=("legacy_review_reasons", unique_join),
        )
        .reset_index()
    )
    return grouped.sort_values(["pilot_rank", "unitid", "target_year", "candidate_url"])


def unique_join(values: pd.Series) -> str:
    nonempty = values.dropna().astype(str).str.strip()
    nonempty = nonempty[nonempty.ne("")]
    return "; ".join(sorted(nonempty.unique()))


def write_summary(
    summary_path: Path,
    inventory: pd.DataFrame,
    attempts: pd.DataFrame,
    coverage: pd.DataFrame,
    deduped_coverage: pd.DataFrame,
) -> None:
    lines = [
        "# Phase 3 Catalog Retrieval Pilot",
        "",
        f"Generated at: {utc_now()}",
        "",
        "## Scope",
        "",
        f"- Candidate source provenance rows with URLs: {len(coverage)}",
        f"- Unique candidate URL leads: {len(deduped_coverage)}",
        f"- Retrieval attempts: {len(attempts)}",
        "- Legacy URLs are still treated as candidate leads until source/year verification is complete.",
        "",
        "## Coverage",
        "",
        f"- Retrieved provenance rows: {int(coverage['source_retrieved'].sum())}",
        f"- Retrieved unique URL leads: {int(deduped_coverage['source_retrieved'].sum())}",
        f"- Not retrieved unique URL leads: {int((~deduped_coverage['source_retrieved']).sum())}",
        f"- Retrieved unique URL leads with target year in hints: {int((deduped_coverage['source_retrieved'] & deduped_coverage['target_year_in_hints']).sum())}",
        "",
        "## Best Retrieval Status",
        "",
    ]
    for status, count in deduped_coverage["best_retrieval_status"].value_counts(dropna=False).items():
        lines.append(f"- {status}: {count}")
    lines.extend(["", "## Attempt Status", ""])
    for status, count in attempts["retrieval_status"].value_counts(dropna=False).items():
        lines.append(f"- {status}: {count}")
    lines.extend(["", "## Best Method Attribution", ""])
    method_counts = deduped_coverage["best_attempt_method"].fillna("").replace("", "none").value_counts()
    for method, count in method_counts.items():
        method_rows = deduped_coverage[deduped_coverage["best_attempt_method"].fillna("").replace("", "none").eq(method)]
        target_hint_count = int(method_rows["target_year_in_hints"].sum()) if not method_rows.empty else 0
        lines.append(f"- {method}: {count} unique URL leads ({target_hint_count} with target year in hints)")
    lines.extend(
        [
            "",
            "## Method Counts",
            "",
        ]
    )
    for method, count in attempts["attempt_method"].value_counts(dropna=False).items():
        lines.append(f"- {method}: {count}")
    lines.extend(
        [
            "",
            "## Outputs",
            "",
            f"- Attempts: `{(summary_path.parents[1] / 'interim' / RETRIEVAL_ATTEMPTS_OUTPUT.name).resolve()}`",
            f"- Provenance-row coverage: `{(summary_path.parents[1] / 'interim' / RETRIEVAL_COVERAGE_OUTPUT.name).resolve()}`",
            f"- Deduplicated URL coverage: `{(summary_path.parents[1] / 'interim' / RETRIEVAL_DEDUPED_COVERAGE_OUTPUT.name).resolve()}`",
            "",
        ]
    )
    summary_path.write_text("\n".join(lines), encoding="utf-8")


def run_phase3_retrieval_pilot(repo_root: Path, *, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> RetrievalOutputs:
    repo_root = repo_root.resolve()
    inventory = pd.read_csv(repo_root / CATALOG_INVENTORY_INPUT, low_memory=False)
    attempts = build_retrieval_attempts(repo_root, inventory, timeout_seconds=timeout_seconds)
    coverage = build_coverage(inventory, attempts)
    deduped_coverage = build_deduped_coverage(coverage)

    attempts_path = (repo_root / RETRIEVAL_ATTEMPTS_OUTPUT).resolve()
    coverage_path = (repo_root / RETRIEVAL_COVERAGE_OUTPUT).resolve()
    deduped_coverage_path = (repo_root / RETRIEVAL_DEDUPED_COVERAGE_OUTPUT).resolve()
    summary_path = (repo_root / SUMMARY_OUTPUT).resolve()
    attempts_path.parent.mkdir(parents=True, exist_ok=True)
    coverage_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    attempts.to_csv(attempts_path, index=False)
    coverage.to_csv(coverage_path, index=False)
    deduped_coverage.to_csv(deduped_coverage_path, index=False)
    write_summary(summary_path, inventory, attempts, coverage, deduped_coverage)
    return RetrievalOutputs(
        retrieval_attempts=attempts_path,
        retrieval_coverage=coverage_path,
        retrieval_coverage_deduped=deduped_coverage_path,
        summary_report=summary_path,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Phase 3 pilot catalog source retrieval and recovery.")
    parser.add_argument("--root", type=Path, default=None, help="Repository root. Defaults to auto-detection.")
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve() if args.root else repo_root_from_cwd()
    outputs = run_phase3_retrieval_pilot(root, timeout_seconds=args.timeout_seconds)
    for label, path in outputs.__dict__.items():
        print(f"{label}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
