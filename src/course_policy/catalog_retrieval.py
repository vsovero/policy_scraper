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
from urllib.parse import quote, urlparse, urlunparse
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
SUMMARY_OUTPUT = LOG_DIR / "phase3_catalog_retrieval_pilot_summary.md"

MAX_SOURCE_BYTES = 25 * 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 25
WAYBACK_AVAILABLE_URL = "https://archive.org/wayback/available?url={url}&timestamp={timestamp}"


@dataclass(frozen=True)
class RetrievalOutputs:
    retrieval_attempts: Path
    retrieval_coverage: Path
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
    attempts = [("direct", url)]
    parsed = urlparse(url)
    if parsed.scheme == "http":
        attempts.append(("https_variant", urlunparse(parsed._replace(scheme="https"))))
    elif parsed.scheme == "https":
        attempts.append(("http_variant", urlunparse(parsed._replace(scheme="http"))))
    attempts.append(("wayback_available", wayback_available_url(url, target_year)))
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


def parse_wayback_snapshot(body: bytes) -> str:
    try:
        data = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        return ""
    closest = data.get("archived_snapshots", {}).get("closest", {})
    if closest.get("available") and closest.get("url"):
        return str(closest["url"])
    return ""


def should_try_recovery(result: dict[str, Any]) -> bool:
    return result["retrieval_status"] not in {"retrieved", "retrieved_truncated"}


def build_retrieval_attempts(
    repo_root: Path,
    inventory: pd.DataFrame,
    *,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    created_at = utc_now()
    leads = inventory[inventory["candidate_url"].fillna("").astype(str).str.strip().ne("")].copy()
    for _, source in leads.sort_values(["pilot_rank", "unitid", "target_year", "source_id"]).iterrows():
        prior_failed = True
        for sequence, (method, attempt_url) in enumerate(
            candidate_attempt_urls(str(source["candidate_url"]), int(source["target_year"])),
            start=1,
        ):
            if not prior_failed:
                break
            result = retrieve_url(attempt_url, timeout_seconds=timeout_seconds)
            local_path = ""
            recovered_url = ""
            if result["retrieval_status"] in {"retrieved", "retrieved_truncated"}:
                if method == "wayback_available":
                    recovered_url = parse_wayback_snapshot(result["body"])
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
                        rows.append(
                            attempt_row(
                                source,
                                len(rows) + 1,
                                sequence + 0.1,
                                "wayback_snapshot",
                                recovered_url,
                                snapshot,
                                snapshot_path,
                                created_at,
                                recovered_from=attempt_url,
                            )
                        )
                else:
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
            prior_failed = should_try_recovery(result)
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
        & ~attempts["attempt_method"].eq("wayback_available")
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
                    "source_id",
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
            on="source_id",
            how="left",
        )
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


def write_summary(summary_path: Path, inventory: pd.DataFrame, attempts: pd.DataFrame, coverage: pd.DataFrame) -> None:
    lines = [
        "# Phase 3 Catalog Retrieval Pilot",
        "",
        f"Generated at: {utc_now()}",
        "",
        "## Scope",
        "",
        f"- Candidate source leads with URLs: {len(coverage)}",
        f"- Retrieval attempts: {len(attempts)}",
        "- Legacy URLs are still treated as candidate leads until source/year verification is complete.",
        "",
        "## Coverage",
        "",
        f"- Retrieved source leads: {int(coverage['source_retrieved'].sum())}",
        f"- Not retrieved source leads: {int((~coverage['source_retrieved']).sum())}",
        f"- Retrieved leads with target year in hints: {int((coverage['source_retrieved'] & coverage['target_year_in_hints']).sum())}",
        "",
        "## Best Retrieval Status",
        "",
    ]
    for status, count in coverage["best_retrieval_status"].value_counts(dropna=False).items():
        lines.append(f"- {status}: {count}")
    lines.extend(["", "## Attempt Status", ""])
    for status, count in attempts["retrieval_status"].value_counts(dropna=False).items():
        lines.append(f"- {status}: {count}")
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
            f"- Coverage: `{(summary_path.parents[1] / 'interim' / RETRIEVAL_COVERAGE_OUTPUT.name).resolve()}`",
            "",
        ]
    )
    summary_path.write_text("\n".join(lines), encoding="utf-8")


def run_phase3_retrieval_pilot(repo_root: Path, *, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> RetrievalOutputs:
    repo_root = repo_root.resolve()
    inventory = pd.read_csv(repo_root / CATALOG_INVENTORY_INPUT, low_memory=False)
    attempts = build_retrieval_attempts(repo_root, inventory, timeout_seconds=timeout_seconds)
    coverage = build_coverage(inventory, attempts)

    attempts_path = (repo_root / RETRIEVAL_ATTEMPTS_OUTPUT).resolve()
    coverage_path = (repo_root / RETRIEVAL_COVERAGE_OUTPUT).resolve()
    summary_path = (repo_root / SUMMARY_OUTPUT).resolve()
    attempts_path.parent.mkdir(parents=True, exist_ok=True)
    coverage_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    attempts.to_csv(attempts_path, index=False)
    coverage.to_csv(coverage_path, index=False)
    write_summary(summary_path, inventory, attempts, coverage)
    return RetrievalOutputs(retrieval_attempts=attempts_path, retrieval_coverage=coverage_path, summary_report=summary_path)


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
