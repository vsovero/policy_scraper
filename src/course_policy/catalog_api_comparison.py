"""Compare deterministic catalog URL scraping with AI-assisted source assessment."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import pandas as pd

from .ai_config import AIConfig, load_ai_config, repo_root_from_cwd


DATA_DIR = Path("../data_policy_pipeline")
INTERIM_DIR = DATA_DIR / "interim"
LOG_DIR = DATA_DIR / "logs"
CATALOG_INVENTORY_INPUT = INTERIM_DIR / "catalog_inventory_pilot.csv"
COMPARISON_OUTPUT = INTERIM_DIR / "catalog_api_comparison_sample.csv"
SUMMARY_OUTPUT = LOG_DIR / "phase3_catalog_api_comparison_summary.md"

TASK_TYPE = "catalog_source_assessment_sample"
PROMPT_VERSION = "catalog_source_assessment_v0"
MAX_FETCH_BYTES = 200_000
SNIPPET_CHARS = 4_000


@dataclass(frozen=True)
class ComparisonOutputs:
    comparison_table: Path
    summary_report: Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def select_sample(inventory: pd.DataFrame, sample_size: int, source_ids: list[str] | None = None) -> pd.DataFrame:
    candidates = inventory[inventory["candidate_url"].fillna("").astype(str).str.strip().ne("")].copy()
    if source_ids:
        selected = candidates[candidates["source_id"].isin(source_ids)].copy()
        missing = sorted(set(source_ids) - set(selected["source_id"]))
        if missing:
            raise ValueError(f"source_id values not found or missing candidate URLs: {missing}")
        return selected.sort_values(["source_id"])
    candidates["review_sort"] = candidates["needs_human_review"].astype(str).str.lower().isin({"true", "1"})
    return (
        candidates.sort_values(
            ["review_sort", "pilot_rank", "unitid", "target_year", "source_id"],
            ascending=[False, True, True, True, True],
        )
        .head(sample_size)
        .drop(columns=["review_sort"])
    )


def scrape_candidate_url(url: str, timeout_seconds: int = 20) -> dict[str, Any]:
    result: dict[str, Any] = {
        "scrape_status": "not_attempted",
        "http_status": "",
        "final_url": "",
        "content_type": "",
        "content_length_bytes": "",
        "page_title": "",
        "year_hints": "",
        "snippet": "",
        "error_type": "",
        "error_message": "",
    }
    request = Request(url, headers={"User-Agent": "course-policy-pipeline/0.1"})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            body = response.read(MAX_FETCH_BYTES)
            content_type = response.headers.get("content-type", "")
            final_url = response.geturl()
            result.update(
                {
                    "scrape_status": "retrieved",
                    "http_status": getattr(response, "status", ""),
                    "final_url": final_url,
                    "content_type": content_type,
                    "content_length_bytes": len(body),
                }
            )
            text = decode_body(body, content_type)
            result["page_title"] = extract_title(text) or title_from_url(final_url)
            result["year_hints"] = "; ".join(str(year) for year in infer_years(f"{url} {final_url} {text[:5000]}"))
            result["snippet"] = clean_snippet(text)
    except HTTPError as exc:
        result.update(
            {
                "scrape_status": "http_error",
                "http_status": exc.code,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            }
        )
    except URLError as exc:
        result.update(
            {
                "scrape_status": "url_error",
                "error_type": type(exc).__name__,
                "error_message": str(exc.reason),
            }
        )
    except Exception as exc:  # pragma: no cover - defensive around remote servers.
        result.update({"scrape_status": "error", "error_type": type(exc).__name__, "error_message": str(exc)})
    return result


def decode_body(body: bytes, content_type: str) -> str:
    if "pdf" in content_type.lower() or body.startswith(b"%PDF"):
        return title_from_pdf_bytes(body)
    for encoding in ["utf-8", "latin-1"]:
        try:
            return body.decode(encoding, errors="replace")
        except Exception:
            continue
    return ""


def title_from_pdf_bytes(body: bytes) -> str:
    text = body[:5000].decode("latin-1", errors="ignore")
    match = re.search(r"/Title\s*\(([^)]{1,200})\)", text)
    return match.group(1).strip() if match else "PDF source; text extraction not attempted in Phase 3 comparison"


def extract_title(text: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    title = re.sub(r"\s+", " ", html.unescape(match.group(1))).strip()
    return title[:300]


def title_from_url(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    return path.rsplit("/", 1)[-1].replace("-", " ").replace("_", " ")[:300]


def infer_years(text: str) -> list[int]:
    years = sorted({int(match.group(0)) for match in re.finditer(r"(?:19|20)\d{2}", text)})
    return [year for year in years if 1990 <= year <= 2030]


def clean_snippet(text: str) -> str:
    text = re.sub(r"<script.*?</script>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:SNIPPET_CHARS]


def build_assessment_prompt(row: pd.Series, scrape: dict[str, Any]) -> str:
    payload = {
        "task": "Assess a candidate source for a course repetition policy catalog pipeline.",
        "institution_name": row["institution_name"],
        "unitid": int(row["unitid"]),
        "target_year": int(row["target_year"]),
        "candidate_url": row["candidate_url"],
        "legacy_context": {
            "legacy_workbook": row.get("legacy_workbook", ""),
            "legacy_sheet_name": row.get("legacy_sheet_name", ""),
            "legacy_review_reasons": row.get("legacy_review_reasons", ""),
            "pilot_case_types": row.get("pilot_case_types", ""),
        },
        "deterministic_scrape": {
            "scrape_status": scrape["scrape_status"],
            "http_status": scrape["http_status"],
            "final_url": scrape["final_url"],
            "content_type": scrape["content_type"],
            "page_title": scrape["page_title"],
            "year_hints": scrape["year_hints"],
            "snippet": scrape["snippet"],
        },
        "instructions": [
            "Use only the provided URL, title, year hints, and snippet.",
            "Do not browse, guess from memory, or classify course repetition policy.",
            "Return JSON only with the requested fields.",
        ],
        "required_json_fields": [
            "likely_official_source",
            "likely_catalog_source",
            "source_kind",
            "catalog_year_start",
            "catalog_year_end",
            "confidence",
            "ai_added_value",
            "suggested_next_action",
            "needs_human_review",
            "review_reason",
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def call_openai_assessment(config: AIConfig, prompt: str, call_id: str) -> tuple[dict[str, Any], Path, Path]:
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover - environment dependency.
        raise RuntimeError("The openai package is required for live API calls.") from exc

    client = OpenAI(
        timeout=config.openai.timeout_seconds,
        max_retries=config.openai.max_retries,
    )
    response = client.responses.create(
        model=config.openai.model,
        input=[
            {
                "role": "user",
                "content": (
                    "Return compact JSON only. Assess whether this candidate URL looks like "
                    "an official catalog source for the target institution-year.\n\n"
                    f"{prompt}"
                ),
            }
        ],
    )
    raw_path = config.workflow.raw_response_dir / f"{call_id}.json"
    parsed_path = config.workflow.parsed_response_dir / f"{call_id}.json"
    raw = response.model_dump(mode="json") if hasattr(response, "model_dump") else {"repr": repr(response)}
    raw_path.write_text(json.dumps(raw, indent=2, sort_keys=True), encoding="utf-8")
    parsed = extract_json_object(str(getattr(response, "output_text", "")))
    parsed_path.write_text(json.dumps(parsed, indent=2, sort_keys=True), encoding="utf-8")
    return parsed, raw_path, parsed_path


def extract_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("Expected JSON object from API response")
    return parsed


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")


def run_catalog_api_comparison(
    repo_root: Path,
    *,
    config_path: Path | None = None,
    sample_size: int = 1,
    source_ids: list[str] | None = None,
) -> ComparisonOutputs:
    repo_root = repo_root.resolve()
    config = load_ai_config(config_path, root=repo_root)
    if not config.live_enabled:
        raise ValueError("catalog API comparison requires workflow.mode = 'live'")
    if sample_size > config.workflow.max_requests_per_run:
        raise ValueError(
            f"sample_size={sample_size} exceeds workflow.max_requests_per_run={config.workflow.max_requests_per_run}"
        )

    config.workflow.log_dir.mkdir(parents=True, exist_ok=True)
    config.workflow.raw_response_dir.mkdir(parents=True, exist_ok=True)
    config.workflow.parsed_response_dir.mkdir(parents=True, exist_ok=True)

    inventory = pd.read_csv(repo_root / CATALOG_INVENTORY_INPUT, low_memory=False)
    sample = select_sample(inventory, sample_size, source_ids=source_ids)
    created_at = utc_now()
    rows: list[dict[str, Any]] = []

    for _, row in sample.iterrows():
        call_id = f"{TASK_TYPE}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"
        scrape = scrape_candidate_url(str(row["candidate_url"]), timeout_seconds=config.openai.timeout_seconds)
        prompt = build_assessment_prompt(row, scrape)
        raw_path = parsed_path = None
        validation_status = "not_attempted"
        api_error = ""
        ai: dict[str, Any] = {}
        try:
            ai, raw_path, parsed_path = call_openai_assessment(config, prompt, call_id)
            validation_status = "parsed"
        except Exception as exc:  # pragma: no cover - exact remote/API failures vary.
            validation_status = "api_error"
            api_error = type(exc).__name__ + ": " + str(exc)

        log_record = {
            "call_id": call_id,
            "task_type": TASK_TYPE,
            "unitid": int(row["unitid"]),
            "institution_name": row["institution_name"],
            "target_year": int(row["target_year"]),
            "source_id": row["source_id"],
            "model": config.openai.model,
            "prompt_version": PROMPT_VERSION,
            "schema_version": config.prompts.schema_version,
            "input_hash": sha256_text(prompt),
            "output_hash": sha256_text(json.dumps(ai, sort_keys=True)) if ai else "",
            "raw_response_path": str(raw_path) if raw_path else "",
            "parsed_response_path": str(parsed_path) if parsed_path else "",
            "validation_status": validation_status,
            "error_message": api_error,
            "created_at": created_at,
        }
        append_jsonl(config.workflow.log_dir / "api_call_log.jsonl", log_record)

        rows.append(flatten_result(row, scrape, ai, log_record))

    output_path = (repo_root / COMPARISON_OUTPUT).resolve()
    summary_path = (repo_root / SUMMARY_OUTPUT).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    comparison = pd.DataFrame(rows)
    comparison.to_csv(output_path, index=False)
    write_summary(summary_path, comparison, config, output_path)
    return ComparisonOutputs(comparison_table=output_path, summary_report=summary_path)


def flatten_result(
    row: pd.Series,
    scrape: dict[str, Any],
    ai: dict[str, Any],
    log_record: dict[str, Any],
) -> dict[str, Any]:
    return {
        "source_id": row["source_id"],
        "unitid": int(row["unitid"]),
        "institution_name": row["institution_name"],
        "target_year": int(row["target_year"]),
        "candidate_url": row["candidate_url"],
        "legacy_review_reasons": row.get("legacy_review_reasons", ""),
        "web_scrape_status": scrape["scrape_status"],
        "web_http_status": scrape["http_status"],
        "web_final_url": scrape["final_url"],
        "web_content_type": scrape["content_type"],
        "web_page_title": scrape["page_title"],
        "web_year_hints": scrape["year_hints"],
        "web_snippet": scrape["snippet"],
        "api_validation_status": log_record["validation_status"],
        "api_likely_official_source": ai.get("likely_official_source", ""),
        "api_likely_catalog_source": ai.get("likely_catalog_source", ""),
        "api_source_kind": ai.get("source_kind", ""),
        "api_catalog_year_start": ai.get("catalog_year_start", ""),
        "api_catalog_year_end": ai.get("catalog_year_end", ""),
        "api_confidence": ai.get("confidence", ""),
        "api_added_value": ai.get("ai_added_value", ""),
        "api_suggested_next_action": ai.get("suggested_next_action", ""),
        "api_needs_human_review": ai.get("needs_human_review", ""),
        "api_review_reason": ai.get("review_reason", ""),
        "api_log_call_id": log_record["call_id"],
        "api_raw_response_path": log_record["raw_response_path"],
        "api_parsed_response_path": log_record["parsed_response_path"],
        "api_error_message": log_record["error_message"],
    }


def write_summary(summary_path: Path, comparison: pd.DataFrame, config: AIConfig, output_path: Path) -> None:
    lines = [
        "# Phase 3 Catalog API Comparison Sample",
        "",
        f"Generated at: {utc_now()}",
        "",
        "## Purpose",
        "",
        "- Compare deterministic URL scrape fields with AI-assisted source assessment fields.",
        "- This does not classify course repetition policy and does not select final sources.",
        "",
        "## Run",
        "",
        f"- Rows assessed: {len(comparison)}",
        f"- Model: `{config.openai.model}`",
        f"- Prompt version: `{PROMPT_VERSION}`",
        f"- Output table: `{output_path}`",
        "",
        "## Status Counts",
        "",
    ]
    for status, count in comparison["api_validation_status"].value_counts(dropna=False).items():
        lines.append(f"- API {status}: {count}")
    for status, count in comparison["web_scrape_status"].value_counts(dropna=False).items():
        lines.append(f"- Web scrape {status}: {count}")
    lines.append("")
    summary_path.write_text("\n".join(lines), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a small web-scrape vs API source-assessment comparison.")
    parser.add_argument("--root", type=Path, default=None, help="Repository root. Defaults to auto-detection.")
    parser.add_argument("--config", type=Path, default=None, help="AI config path.")
    parser.add_argument("--sample-size", type=int, default=1)
    parser.add_argument("--source-id", action="append", default=None, help="Specific catalog inventory source_id to assess.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve() if args.root else repo_root_from_cwd()
    outputs = run_catalog_api_comparison(
        root,
        config_path=args.config,
        sample_size=args.sample_size,
        source_ids=args.source_id,
    )
    for label, path in outputs.__dict__.items():
        print(f"{label}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
