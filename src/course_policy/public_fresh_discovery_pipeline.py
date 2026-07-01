"""Run the full public no-legacy fresh-discovery process."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pandas as pd
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from pandas.errors import EmptyDataError

from .ai_config import AIConfig, load_ai_config, repo_root_from_cwd
from .batch2_pilot import clean_text
from .batch2_year_candidates import (
    academic_years_from_range,
    add_candidate_selection_rank_columns,
    candidate_priority,
    candidate_selection_sort_columns,
    catalog_year_range,
)
from .batch3_discovery import build_year_candidates, is_policy_page_lead, is_wrong_scope_catalog_url
from .catalog_retrieval import retrieve_url
from .institution_universe import TARGET_END_YEAR, TARGET_START_YEAR
from .public_fresh_discovery import (
    PublicFreshDiscoveryOutputs,
    build_archive_pages_concurrent,
    classify_institution_status,
    copy_delivery as copy_first_pass_delivery,
    run as run_first_pass,
    suffixed_path,
)


DATA_DIR = Path("artifacts/policy_data_internal")
REVIEW_DIR = DATA_DIR / "review"
INTERIM_DIR = DATA_DIR / "interim"
LOG_DIR = DATA_DIR / "logs"
DELIVERY_DIR = Path("../policy_data")

TASK_TYPE = "public_fresh_root_web_discovery"
PROMPT_VERSION = "public_fresh_root_web_discovery_v0"
UNRESOLVED_STATUSES = {
    "source_root_not_found",
    "root_candidates_retrieved_but_not_catalog",
    "source_root_found_no_explicit_years",
}


@dataclass(frozen=True)
class PublicFreshPipelineOutputs:
    first_pass_workbook: Path
    first_pass_status_csv: Path
    ai_cases_csv: Path
    ai_triage_csv: Path
    ai_verified_roots_csv: Path
    ai_archive_pages_csv: Path
    ai_year_candidates_csv: Path
    final_year_panel_csv: Path
    final_status_csv: Path
    workbook: Path
    summary_md: Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def safe_error_message(message: str, config: AIConfig) -> str:
    key = os.environ.get(config.openai.api_key_env, "")
    if key:
        message = message.replace(key, "[redacted]")
    return re.sub(r"sk-[A-Za-z0-9*_-]+", "[redacted-api-key]", message)


def read_csv_if_exists(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size <= 1:
        return pd.DataFrame()
    try:
        return pd.read_csv(path, low_memory=False)
    except EmptyDataError:
        return pd.DataFrame()


def first_pass_outputs_for_suffix(repo_root: Path, suffix: str) -> PublicFreshDiscoveryOutputs:
    return PublicFreshDiscoveryOutputs(
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


def first_pass_outputs_exist(outputs: PublicFreshDiscoveryOutputs) -> bool:
    required = [
        outputs.root_candidates_csv,
        outputs.year_candidates_csv,
        outputs.year_panel_csv,
        outputs.institution_status_csv,
        outputs.workbook,
    ]
    return all(path.exists() for path in required)


def select_ai_cases(status: pd.DataFrame, *, max_cases: int | None) -> pd.DataFrame:
    cases = status.loc[status["fresh_discovery_status"].isin(UNRESOLVED_STATUSES)].copy()
    cases["status_priority"] = cases["fresh_discovery_status"].map(
        {
            "source_root_found_no_explicit_years": 0,
            "root_candidates_retrieved_but_not_catalog": 1,
            "source_root_not_found": 2,
        }
    ).fillna(9)
    cases = cases.sort_values(["status_priority", "fresh_rank", "institution_name", "unitid"]).drop(columns=["status_priority"])
    if max_cases is not None:
        cases = cases.head(max_cases).copy()
    return cases


def build_case_prompt(case: pd.Series, root_candidates: pd.DataFrame) -> str:
    unitid = int(case["unitid"])
    tried = root_candidates.loc[root_candidates["unitid"].astype(int).eq(unitid)].copy()
    tried = tried.sort_values(["retrieval_status", "candidate_url"]).head(18)
    tried_rows = [
        {
            "candidate_url": clean_text(row.get("candidate_url")),
            "retrieval_status": clean_text(row.get("retrieval_status")),
            "http_status": clean_text(row.get("http_status")),
            "page_title": clean_text(row.get("page_title")),
            "catalog_link_count": int(row.get("catalog_link_count", 0) or 0),
            "archive_link_count": int(row.get("archive_link_count", 0) or 0),
        }
        for _, row in tried.iterrows()
    ]
    payload = {
        "role": "You are helping an auditable catalog-discovery pipeline find official university catalog archives.",
        "task": "Find likely official catalog archive roots for a public institution that has no human legacy URL.",
        "institution": {
            "unitid": unitid,
            "name": clean_text(case.get("institution_name")),
            "state": clean_text(case.get("state")),
            "webaddr": clean_text(case.get("webaddr")),
            "first_pass_status": clean_text(case.get("fresh_discovery_status")),
            "preferred_source_root_url": clean_text(case.get("preferred_source_root_url")),
        },
        "already_tried": tried_rows,
        "rules": [
            "Use web search only for official university catalog, bulletin, registrar catalog, academic catalog archive, or institutional repository catalog collection roots.",
            "Prefer university-wide undergraduate/general catalog archives over graduate, law, medical, school-specific, policy-only, or handbook-only pages.",
            "Do not invent URLs. Return only URLs you found or URLs that are directly supported by an official page you found.",
            "If a current catalog page points to an archive page, return the archive page.",
            "Return compact JSON only.",
        ],
        "required_json_schema": {
            "root_candidates": [
                {
                    "url": "official root/archive/repository URL",
                    "root_type": "catalog_archive|current_catalog_with_archive_links|registrar_catalog_page|institutional_repository_collection|direct_catalog_pdf|other",
                    "confidence": "low|medium|high",
                    "evidence": "short explanation of why this URL is relevant",
                }
            ],
            "direct_catalog_urls": [
                {
                    "url": "direct catalog PDF or HTML URL if found",
                    "catalog_year_text": "catalog year/range shown on page or URL",
                    "evidence": "short explanation",
                }
            ],
            "search_queries_used": ["queries"],
            "stop_reason_if_no_root": "short explanation or empty string",
        },
    }
    return json.dumps(payload, indent=2, sort_keys=True)


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
        raise ValueError("Expected JSON object")
    return parsed


def call_openai(config: AIConfig, prompt: str, call_id: str) -> tuple[dict[str, Any], Path, Path]:
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("The openai package is required for live API calls.") from exc
    client = OpenAI(
        api_key=os.environ[config.openai.api_key_env],
        timeout=config.openai.timeout_seconds,
        max_retries=config.openai.max_retries,
    )
    response = client.responses.create(
        model=config.openai.model,
        tools=[{"type": "web_search_preview"}],
        input=[
            {
                "role": "user",
                "content": (
                    "Return JSON only. Use web search to find likely official catalog archive roots "
                    "for this institution, following the supplied schema.\n\n"
                    + prompt
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


def run_ai_triage(
    repo_root: Path,
    *,
    config: AIConfig,
    status: pd.DataFrame,
    root_candidates: pd.DataFrame,
    max_cases: int | None,
    suffix: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    cases = select_ai_cases(status, max_cases=max_cases)
    if config.live_enabled and len(cases) > config.workflow.max_requests_per_run:
        raise ValueError(
            f"selected AI cases={len(cases)} exceeds workflow.max_requests_per_run={config.workflow.max_requests_per_run}"
        )
    config.workflow.log_dir.mkdir(parents=True, exist_ok=True)
    config.workflow.raw_response_dir.mkdir(parents=True, exist_ok=True)
    config.workflow.parsed_response_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    created_at = utc_now()
    for _, case in cases.iterrows():
        call_id = f"{TASK_TYPE}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"
        prompt = build_case_prompt(case, root_candidates)
        prompt_path = config.workflow.parsed_response_dir / f"{call_id}_prompt.json"
        prompt_path.write_text(prompt, encoding="utf-8")
        parsed: dict[str, Any] = {}
        raw_path = parsed_path = None
        validation_status = "dry_run"
        error_message = ""
        if config.live_enabled:
            validation_status = "not_attempted"
            try:
                parsed, raw_path, parsed_path = call_openai(config, prompt, call_id)
                validation_status = "parsed"
            except Exception as exc:  # pragma: no cover - remote failures vary.
                validation_status = "api_error"
                error_message = type(exc).__name__ + ": " + safe_error_message(str(exc), config)
                raw_path = config.workflow.raw_response_dir / f"{call_id}.json"
                raw_path.write_text(json.dumps({"error_message": error_message}, indent=2), encoding="utf-8")
        log_record = {
            "call_id": call_id,
            "task_type": TASK_TYPE,
            "unitid": int(case["unitid"]),
            "institution_name": clean_text(case["institution_name"]),
            "model": config.openai.model,
            "prompt_version": PROMPT_VERSION,
            "schema_version": config.prompts.schema_version,
            "input_hash": sha256_text(prompt),
            "output_hash": sha256_text(json.dumps(parsed, sort_keys=True)) if parsed else "",
            "prompt_path": str(prompt_path),
            "raw_response_path": str(raw_path) if raw_path else "",
            "parsed_response_path": str(parsed_path) if parsed_path else "",
            "validation_status": validation_status,
            "error_message": error_message,
            "created_at": created_at,
        }
        with (config.workflow.log_dir / "api_call_log.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(log_record, sort_keys=True) + "\n")
        rows.append(flatten_ai_result(case, parsed, log_record))
    return cases, pd.DataFrame(rows)


def flatten_ai_result(case: pd.Series, parsed: dict[str, Any], log_record: dict[str, Any]) -> dict[str, Any]:
    roots = parsed.get("root_candidates", []) if isinstance(parsed.get("root_candidates", []), list) else []
    direct = parsed.get("direct_catalog_urls", []) if isinstance(parsed.get("direct_catalog_urls", []), list) else []
    return {
        "unitid": int(case["unitid"]),
        "institution_name": clean_text(case["institution_name"]),
        "fresh_rank": int(case["fresh_rank"]),
        "first_pass_status": clean_text(case["fresh_discovery_status"]),
        "api_validation_status": log_record["validation_status"],
        "api_root_candidate_count": len(roots),
        "api_direct_catalog_url_count": len(direct),
        "api_root_candidates_json": json.dumps(roots, sort_keys=True),
        "api_direct_catalog_urls_json": json.dumps(direct, sort_keys=True),
        "api_search_queries_used": json.dumps(parsed.get("search_queries_used", []), sort_keys=True),
        "api_stop_reason_if_no_root": clean_text(parsed.get("stop_reason_if_no_root", "")),
        "api_log_call_id": log_record["call_id"],
        "api_prompt_path": log_record["prompt_path"],
        "api_raw_response_path": log_record["raw_response_path"],
        "api_parsed_response_path": log_record["parsed_response_path"],
        "api_error_message": log_record["error_message"],
    }


def parse_json_list(value: object) -> list[dict[str, Any]]:
    text = clean_text(value)
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return []
    return [item for item in parsed if isinstance(item, dict)] if isinstance(parsed, list) else []


def verify_ai_roots(ai_triage: pd.DataFrame, *, timeout_seconds: int) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for _, triage in ai_triage.iterrows():
        for idx, root in enumerate(parse_json_list(triage.get("api_root_candidates_json")), 1):
            url = clean_text(root.get("url"))
            if not url:
                continue
            result = retrieve_url(url, timeout_seconds=timeout_seconds, max_bytes=200_000)
            rows.append(
                {
                    "ai_root_rank": idx,
                    "unitid": int(triage["unitid"]),
                    "institution_name": clean_text(triage["institution_name"]),
                    "first_pass_status": clean_text(triage["first_pass_status"]),
                    "root_url": url,
                    "root_type": clean_text(root.get("root_type")),
                    "ai_confidence": clean_text(root.get("confidence")),
                    "ai_evidence": clean_text(root.get("evidence")),
                    "retrieval_status": result["retrieval_status"],
                    "http_status": result["http_status"],
                    "final_url": result["final_url"],
                    "content_type": result["content_type"],
                    "page_title": result["page_title"],
                    "year_hints": result["year_hints"],
                    "link_count": len(result.get("link_records", [])),
                    "verified_as_expandable_root": is_expandable_ai_root(url, result),
                    "created_at": utc_now(),
                }
            )
    return pd.DataFrame(rows)


def is_expandable_ai_root(url: str, result: dict[str, object]) -> bool:
    if result["retrieval_status"] not in {"retrieved", "retrieved_truncated"}:
        return False
    if is_policy_page_lead(url) or is_wrong_scope_catalog_url(url):
        return False
    parsed = urlparse(url)
    path_parts = [part.lower() for part in parsed.path.split("/") if part]
    body = result.get("body", b"")
    body_text = body[:20_000].decode("utf-8", errors="replace").lower() if isinstance(body, bytes) else ""
    if (
        len(path_parts) >= 3
        and path_parts[0] == "digital"
        and path_parts[1] == "collection"
    ) or (
        len(path_parts) >= 4
        and path_parts[0] == "cdm"
        and path_parts[1] == "search"
        and path_parts[2] == "collection"
    ):
        return True
    if parsed.path.lower().endswith("index.php") and ("acalog" in body_text or "catalog list" in body_text):
        return True
    if parsed.path.lower().endswith(".pdf"):
        return False
    content = clean_text(result.get("content_type")).lower()
    evidence = f"{url} {result.get('page_title', '')}".lower()
    if "html" not in content and "catalog" not in evidence and "archive" not in evidence and "bulletin" not in evidence:
        return False
    return any(term in evidence for term in ["catalog", "archive", "bulletin", "registrar"])


def decisions_from_ai_roots(ai_roots: pd.DataFrame) -> pd.DataFrame:
    roots = ai_roots.loc[ai_roots.get("verified_as_expandable_root", pd.Series(dtype=bool)).fillna(False)].copy()
    if roots.empty:
        return pd.DataFrame()
    rows = []
    for _, root in roots.sort_values(["unitid", "ai_root_rank", "root_url"]).iterrows():
        rows.append(
            {
                "batch3_rank": int(root["ai_root_rank"]),
                "unitid": int(root["unitid"]),
                "institution_name": clean_text(root["institution_name"]),
                "decision_status": "preferred_source_root_identified",
                "preferred_source_root_url": clean_text(root["root_url"]),
                "preferred_source_root_type": f"ai_{clean_text(root.get('root_type'))}",
                "preferred_source_root_title": clean_text(root.get("page_title")),
                "created_at": utc_now(),
            }
        )
    return pd.DataFrame(rows)


def direct_catalog_candidates(ai_triage: pd.DataFrame, *, timeout_seconds: int) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for _, triage in ai_triage.iterrows():
        for item in parse_json_list(triage.get("api_direct_catalog_urls_json")):
            url = clean_text(item.get("url"))
            evidence = f"{item.get('catalog_year_text', '')} {url} {item.get('evidence', '')}"
            year_range = catalog_year_range(evidence)
            if not url or not year_range:
                continue
            if is_wrong_scope_catalog_url(evidence) and "undergrad" not in evidence.lower():
                continue
            result = retrieve_url(url, timeout_seconds=timeout_seconds, max_bytes=200_000)
            if result["retrieval_status"] not in {"retrieved", "retrieved_truncated"}:
                continue
            start, end = year_range
            for target_year in academic_years_from_range(start, end):
                if not (TARGET_START_YEAR <= target_year <= TARGET_END_YEAR):
                    continue
                rows.append(
                    {
                        "batch3_rank": 0,
                        "unitid": int(triage["unitid"]),
                        "institution_name": clean_text(triage["institution_name"]),
                        "target_year": target_year,
                        "catalog_year_start": start,
                        "catalog_year_end": end,
                        "academic_year_rule": "AY is the catalog start year; multi-year catalogs cover each start year through end-1.",
                        "candidate_url": url,
                        "candidate_link_text": clean_text(item.get("catalog_year_text")) or "AI-discovered direct catalog URL",
                        "candidate_evidence_text": clean_text(item.get("evidence")),
                        "candidate_evidence_source": "ai_web_direct_catalog_url",
                        "archive_url": "",
                        "archive_page_title": "",
                        "candidate_scope": "undergraduate_or_university_catalog",
                        "validation_status": "ai_web_direct_catalog_year",
                        "candidate_priority": candidate_priority(evidence),
                        "candidate_source_method": "ai_web_direct_catalog_url",
                        "candidate_retrieval_status": result["retrieval_status"],
                        "candidate_http_status": result["http_status"],
                        "candidate_page_title": result["page_title"],
                        "created_at": utc_now(),
                    }
                )
    return pd.DataFrame(rows)


def filter_candidate_rows(candidates: pd.DataFrame) -> pd.DataFrame:
    if candidates.empty:
        return candidates
    out = candidates.copy()
    for column in ["candidate_url", "candidate_link_text", "candidate_evidence_text", "candidate_source_method"]:
        if column not in out.columns:
            out[column] = ""
        out[column] = out[column].fillna("").map(clean_text)
    evidence = (
        out["candidate_link_text"]
        + " "
        + out["candidate_evidence_text"]
        + " "
        + out["candidate_url"]
    ).str.lower()
    url = out["candidate_url"].str.lower()
    generic_search = url.str.contains(r"/search\?|[?&]q=", regex=True, na=False)
    vague_prior_link = evidence.str.contains(
        r"\b(?:prior to|before|older than|older catalogs|previous catalogs)\b",
        regex=True,
        na=False,
    )
    no_url_year_range = out["candidate_url"].map(lambda value: catalog_year_range(value) is None)
    direct_catalog = out["candidate_source_method"].eq("ai_web_direct_catalog_url")
    if "candidate_retrieval_status" not in out.columns:
        out["candidate_retrieval_status"] = ""
    retrieved_direct = out["candidate_retrieval_status"].isin({"retrieved", "retrieved_truncated"})
    host = out["candidate_url"].map(lambda value: urlparse(value).netloc.lower())
    unofficial_blog_host = host.str.contains("blog", na=False)
    catalogish_evidence = evidence.str.contains(r"\b(?:catalog|catalogue|bulletin)\b", regex=True, na=False)
    non_catalog_publication = evidence.str.contains(r"\bmicro-credential\b", regex=True, na=False)
    non_catalog_publication |= (
        evidence.str.contains(r"\b(?:academic calendar|course descriptions?)\b", regex=True, na=False)
        & ~catalogish_evidence
    )
    wrong_catalog_publication = (
        evidence.str.contains(
            r"(?:academic calendar|academic-calendar|calendar\.pdf|interim catalog|interim%20catalog)",
            regex=True,
            na=False,
        )
        & ~catalogish_evidence
    )
    campus_subdomain_wrong_scope = out.apply(candidate_uses_unmatched_campus_subdomain, axis=1)
    keep = ~(generic_search & vague_prior_link & no_url_year_range)
    keep &= ~(direct_catalog & ~retrieved_direct)
    keep &= ~non_catalog_publication
    keep &= ~wrong_catalog_publication
    keep &= ~campus_subdomain_wrong_scope
    keep &= ~unofficial_blog_host
    return out.loc[keep].copy()


def candidate_uses_unmatched_campus_subdomain(row: pd.Series) -> bool:
    institution = clean_text(row.get("institution_name")).lower()
    url = clean_text(row.get("candidate_url"))
    host = urlparse(url).netloc.lower()
    campus_terms = {"asia", "europe"}
    first_label = host.split(".", 1)[0]
    if first_label not in campus_terms:
        return False
    return first_label not in institution


def candidate_span_years(row: pd.Series) -> list[int]:
    target_value = pd.to_numeric(pd.Series([row.get("target_year")]), errors="coerce").iloc[0]
    if pd.isna(target_value):
        return []
    target_year = int(target_value)
    start_value = pd.to_numeric(pd.Series([row.get("catalog_year_start")]), errors="coerce").iloc[0]
    end_value = pd.to_numeric(pd.Series([row.get("catalog_year_end")]), errors="coerce").iloc[0]
    if not pd.isna(start_value) and not pd.isna(end_value):
        start, end = int(start_value), int(end_value)
    else:
        evidence = " ".join(
            clean_text(row.get(column))
            for column in ["candidate_url", "candidate_link_text", "candidate_evidence_text"]
        )
        parsed = catalog_year_range(evidence)
        if not parsed:
            return [target_year]
        start, end = parsed
    years = academic_years_from_range(start, end)
    if target_year not in years:
        return [target_year]
    return years or [target_year]


def expand_candidate_spans(all_candidates: pd.DataFrame) -> pd.DataFrame:
    if all_candidates.empty or "target_year" not in all_candidates.columns:
        return all_candidates
    rows: list[dict[str, object]] = []
    for _, row in all_candidates.iterrows():
        for target_year in candidate_span_years(row):
            out = row.to_dict()
            out["target_year"] = target_year
            rows.append(out)
    if not rows:
        return all_candidates
    expanded = add_candidate_selection_rank_columns(pd.DataFrame(rows))
    expanded = expanded.sort_values(candidate_selection_sort_columns(["unitid", "target_year", "candidate_url"]))
    return expanded.drop_duplicates(["unitid", "target_year", "candidate_url"], keep="first")


def risky_catalogarchive_root_url(value: object) -> bool:
    parsed = urlparse(clean_text(value).lower())
    if not parsed.netloc.startswith("catalogarchive."):
        return False
    return not parsed.path.lower().endswith(".pdf")


def direct_pdf_candidate_url(value: object) -> bool:
    parsed = urlparse(clean_text(value).lower())
    return bool(parsed.netloc) and parsed.path.lower().endswith(".pdf")


RETRIEVED_CANDIDATE_SOURCE_METHODS = {
    "ai_verified_root_archive",
    "clean_archive_expansion",
    "clean_wayback_cdx_content_dating",
}

GENERATED_YEAR_PROBE_SOURCES = {
    "inferred_year_url_pattern",
}


def weak_generated_year_probe_source(value: object) -> bool:
    return clean_text(value).lower() in GENERATED_YEAR_PROBE_SOURCES


def retrieved_candidate_can_replace_generated_probe(row: pd.Series) -> bool:
    method = clean_text(row.get("candidate_source_method")).lower()
    evidence_source = clean_text(row.get("ai_candidate_evidence_source")).lower()
    if evidence_source in GENERATED_YEAR_PROBE_SOURCES:
        return False
    return method in RETRIEVED_CANDIDATE_SOURCE_METHODS


def merge_final_panel(base_panel: pd.DataFrame, all_candidates: pd.DataFrame) -> pd.DataFrame:
    panel = base_panel.copy()
    panel["best_url"] = panel["best_url"].fillna("").map(clean_text)
    if all_candidates.empty:
        panel["final_best_url"] = panel["best_url"]
        panel["final_best_url_source"] = panel.get("best_url_source", "")
        panel["final_status"] = panel["final_best_url"].map(lambda value: "candidate_found" if clean_text(value) else "still_missing")
        return panel
    candidates = add_candidate_selection_rank_columns(expand_candidate_spans(all_candidates))
    chosen = (
        candidates.sort_values(candidate_selection_sort_columns(["unitid", "target_year"]))
        .drop_duplicates(["unitid", "target_year"], keep="first")
        .copy()
    )
    if "candidate_source_method" not in chosen.columns:
        chosen["candidate_source_method"] = ""
    chosen["candidate_source_method"] = chosen["candidate_source_method"].fillna("")
    if "candidate_evidence_source" in chosen.columns:
        chosen.loc[chosen["candidate_source_method"].eq(""), "candidate_source_method"] = chosen.loc[
            chosen["candidate_source_method"].eq(""),
            "candidate_evidence_source",
        ]
    if "candidate_evidence_source" not in chosen.columns:
        chosen["candidate_evidence_source"] = ""
    chosen = chosen.rename(
        columns={
            "candidate_url": "ai_candidate_url",
            "candidate_evidence_source": "ai_candidate_evidence_source",
        }
    )
    keep = [
        "unitid",
        "target_year",
        "ai_candidate_url",
        "candidate_source_method",
        "ai_candidate_evidence_source",
        "candidate_link_text",
        "candidate_evidence_text",
        "archive_url",
    ]
    for column in keep:
        if column not in chosen.columns:
            chosen[column] = ""
    panel = panel.merge(chosen[keep], on=["unitid", "target_year"], how="left")
    ai_has = panel["ai_candidate_url"].fillna("").map(clean_text).ne("")
    base_has = panel["best_url"].map(clean_text).ne("")
    replace_risky_base = (
        base_has
        & ai_has
        & panel["best_url"].map(risky_catalogarchive_root_url)
        & panel["ai_candidate_url"].map(direct_pdf_candidate_url)
    )
    replace_generated_probe = (
        base_has
        & ai_has
        & panel.get("best_url_source", pd.Series("", index=panel.index)).map(weak_generated_year_probe_source)
        & panel.apply(retrieved_candidate_can_replace_generated_probe, axis=1)
    )
    panel["final_best_url"] = panel["best_url"]
    panel.loc[~base_has & ai_has, "final_best_url"] = panel.loc[~base_has & ai_has, "ai_candidate_url"]
    panel.loc[replace_risky_base, "final_best_url"] = panel.loc[replace_risky_base, "ai_candidate_url"]
    panel.loc[replace_generated_probe, "final_best_url"] = panel.loc[replace_generated_probe, "ai_candidate_url"]
    panel["final_best_url_source"] = panel.get("best_url_source", "")
    panel.loc[~base_has & ai_has, "final_best_url_source"] = panel.loc[~base_has & ai_has, "candidate_source_method"]
    panel.loc[replace_risky_base, "final_best_url_source"] = panel.loc[replace_risky_base, "candidate_source_method"]
    panel.loc[replace_generated_probe, "final_best_url_source"] = panel.loc[replace_generated_probe, "candidate_source_method"]
    panel["final_status"] = "still_missing"
    panel.loc[base_has, "final_status"] = "first_pass_candidate_found"
    panel.loc[~base_has & ai_has, "final_status"] = "ai_candidate_added"
    panel.loc[replace_risky_base, "final_status"] = "candidate_replaced_risky_catalogarchive"
    panel.loc[replace_generated_probe, "final_status"] = "candidate_replaced_generated_probe"
    return panel.sort_values(["fresh_rank", "unitid", "target_year"])


def build_final_status(first_status: pd.DataFrame, final_panel: pd.DataFrame, ai_triage: pd.DataFrame, ai_roots: pd.DataFrame) -> pd.DataFrame:
    counts = (
        final_panel.groupby("unitid", as_index=False)
        .agg(
            first_pass_years=("best_url", lambda values: int(pd.Series(values).fillna("").astype(str).str.strip().ne("").sum())),
            ai_added_years=("final_status", lambda values: int(pd.Series(values).eq("ai_candidate_added").sum())),
            final_years_with_url=("final_best_url", lambda values: int(pd.Series(values).fillna("").astype(str).str.strip().ne("").sum())),
        )
    )
    triage = ai_triage[["unitid", "api_validation_status", "api_root_candidate_count", "api_direct_catalog_url_count", "api_stop_reason_if_no_root", "api_error_message"]].copy() if not ai_triage.empty else pd.DataFrame(columns=["unitid"])
    roots = (
        ai_roots.groupby("unitid", as_index=False)
        .agg(ai_verified_root_count=("verified_as_expandable_root", "sum"), ai_root_checked_count=("root_url", "count"))
        if not ai_roots.empty
        else pd.DataFrame(columns=["unitid", "ai_verified_root_count", "ai_root_checked_count"])
    )
    status = first_status.merge(counts, on="unitid", how="left")
    status = status.merge(triage, on="unitid", how="left")
    status = status.merge(roots, on="unitid", how="left")
    for column in [
        "first_pass_years",
        "ai_added_years",
        "final_years_with_url",
        "api_root_candidate_count",
        "api_direct_catalog_url_count",
        "ai_verified_root_count",
        "ai_root_checked_count",
    ]:
        if column not in status.columns:
            status[column] = 0
        status[column] = pd.to_numeric(status[column], errors="coerce").fillna(0).astype(int)
    for column in ["api_validation_status", "api_stop_reason_if_no_root", "api_error_message"]:
        if column not in status.columns:
            status[column] = ""
        status[column] = status[column].fillna("")
    status["final_discovery_status"] = status.apply(final_status_for_row, axis=1)
    status["final_next_action"] = status["final_discovery_status"].map(
        {
            "candidate_years_found": "retrieve_and_validate_candidate_catalogs",
            "ai_added_candidate_years": "retrieve_and_validate_candidate_catalogs",
            "ai_root_found_no_years": "expand_ai_root_or_wayback",
            "ai_no_root_found": "defer_or_lower_priority_manual_search",
            "ai_not_run": "run_ai_web_discovery_if_priority",
        }
    )
    return status.sort_values(["fresh_rank", "unitid"])


def final_status_for_row(row: pd.Series) -> str:
    if int(row.get("ai_added_years", 0) or 0) > 0:
        return "ai_added_candidate_years"
    if int(row.get("first_pass_years", 0) or 0) > 0:
        return "candidate_years_found"
    if clean_text(row.get("api_validation_status")) == "":
        return "ai_not_run"
    if int(row.get("ai_verified_root_count", 0) or 0) > 0:
        return "ai_root_found_no_years"
    return "ai_no_root_found"


def write_workbook(path: Path, sheets: dict[str, pd.DataFrame]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for name, frame in sheets.items():
            excel_safe_frame(frame).to_excel(writer, sheet_name=name[:31], index=False)


def excel_safe_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    out = frame.copy()
    object_columns = out.select_dtypes(include=["object"]).columns
    for column in object_columns:
        out[column] = out[column].map(remove_excel_illegal_characters)
    return out


def remove_excel_illegal_characters(value: object) -> object:
    if not isinstance(value, str):
        return value
    return ILLEGAL_CHARACTERS_RE.sub("", value)


def write_summary(path: Path, *, suffix: str, final_status: pd.DataFrame, outputs: PublicFreshPipelineOutputs) -> None:
    counts = final_status["final_discovery_status"].value_counts().to_dict() if not final_status.empty else {}
    lines = [
        "# Public Fresh Discovery Full Process",
        "",
        f"Generated at: {utc_now()}",
        f"Run suffix: `{suffix}`",
        "",
        "Scope: public institutions with no public legacy URL. Runs bounded official-site discovery, AI web-search root discovery for unresolved cases, deterministic expansion of verified roots, and final panel/status assembly.",
        "",
        "## Bottom Line",
        "",
        f"- Institutions processed: {final_status['unitid'].nunique() if not final_status.empty else 0}",
        f"- Candidate years found in first pass: {int(final_status['first_pass_years'].sum()) if not final_status.empty else 0}",
        f"- Candidate years added after AI/search: {int(final_status['ai_added_years'].sum()) if not final_status.empty else 0}",
        f"- Final candidate years with URL: {int(final_status['final_years_with_url'].sum()) if not final_status.empty else 0}",
        "",
        "## Final Status Counts",
        "",
    ]
    if counts:
        for status, count in sorted(counts.items()):
            lines.append(f"- {status}: {int(count)}")
    else:
        lines.append("- none")
    lines.extend(["", "## Outputs", ""])
    for label, output_path in outputs.__dict__.items():
        lines.append(f"- {label}: `{output_path}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def copy_delivery(repo_root: Path, outputs: PublicFreshPipelineOutputs, suffix: str, final_status: pd.DataFrame) -> None:
    delivery = (repo_root / DELIVERY_DIR).resolve()
    delivery.mkdir(parents=True, exist_ok=True)
    for source, stem in [
        (outputs.workbook, "public_fresh_full_process"),
        (outputs.final_status_csv, "public_fresh_full_status"),
        (outputs.final_year_panel_csv, "public_fresh_full_year_panel"),
        (outputs.ai_cases_csv, "public_fresh_ai_cases"),
        (outputs.ai_triage_csv, "public_fresh_ai_triage"),
        (outputs.ai_verified_roots_csv, "public_fresh_ai_verified_roots"),
        (outputs.ai_archive_pages_csv, "public_fresh_ai_archive_pages"),
        (outputs.ai_year_candidates_csv, "public_fresh_ai_year_candidates"),
    ]:
        (delivery / f"{stem}_{suffix}{source.suffix}").write_bytes(source.read_bytes())
    summary_path = delivery / f"public_fresh_full_process_summary_{suffix}.md"
    write_summary(summary_path, suffix=suffix, final_status=final_status, outputs=delivery_outputs(delivery, suffix))


def delivery_outputs(delivery: Path, suffix: str) -> PublicFreshPipelineOutputs:
    return PublicFreshPipelineOutputs(
        first_pass_workbook=delivery / f"public_fresh_discovery_{suffix}.xlsx",
        first_pass_status_csv=delivery / f"public_fresh_discovery_status_{suffix}.csv",
        ai_cases_csv=delivery / f"public_fresh_ai_cases_{suffix}.csv",
        ai_triage_csv=delivery / f"public_fresh_ai_triage_{suffix}.csv",
        ai_verified_roots_csv=delivery / f"public_fresh_ai_verified_roots_{suffix}.csv",
        ai_archive_pages_csv=delivery / f"public_fresh_ai_archive_pages_{suffix}.csv",
        ai_year_candidates_csv=delivery / f"public_fresh_ai_year_candidates_{suffix}.csv",
        final_year_panel_csv=delivery / f"public_fresh_full_year_panel_{suffix}.csv",
        final_status_csv=delivery / f"public_fresh_full_status_{suffix}.csv",
        workbook=delivery / f"public_fresh_full_process_{suffix}.xlsx",
        summary_md=delivery / f"public_fresh_full_process_summary_{suffix}.md",
    )


def run(
    repo_root: Path,
    *,
    suffix: str,
    limit: int | None,
    rank_start: int = 1,
    config_path: Path | None = None,
    max_api_cases: int | None = None,
    timeout_seconds: int = 3,
    max_root_candidates_per_institution: int = 24,
    max_archive_pages_per_institution: int = 4,
    max_workers: int = 16,
    reuse_first_pass: bool = False,
    reuse_ai_triage: bool = False,
    reuse_ai_expansion: bool = False,
) -> PublicFreshPipelineOutputs:
    repo_root = repo_root.resolve()
    config = load_ai_config(config_path, root=repo_root)
    if max_api_cases is None:
        max_api_cases = config.workflow.max_requests_per_run if config.live_enabled else 0

    cached_first_outputs = first_pass_outputs_for_suffix(repo_root, suffix)
    if reuse_first_pass and first_pass_outputs_exist(cached_first_outputs):
        first_outputs = cached_first_outputs
    else:
        first_outputs = run_first_pass(
            repo_root,
            suffix=suffix,
            limit=limit,
            rank_start=rank_start,
            include_branch_campuses=True,
            timeout_seconds=timeout_seconds,
            max_root_candidates_per_institution=max_root_candidates_per_institution,
            max_archive_pages_per_institution=max_archive_pages_per_institution,
            max_workers=max_workers,
        )
    first_status = read_csv_if_exists(first_outputs.institution_status_csv)
    first_panel = read_csv_if_exists(first_outputs.year_panel_csv)
    first_candidates = read_csv_if_exists(first_outputs.year_candidates_csv)
    root_candidates = read_csv_if_exists(first_outputs.root_candidates_csv)

    ai_cases_path = suffixed_path((repo_root / REVIEW_DIR / "public_fresh_ai_cases.csv").resolve(), suffix)
    ai_triage_path = suffixed_path((repo_root / REVIEW_DIR / "public_fresh_ai_triage.csv").resolve(), suffix)
    if reuse_ai_triage and ai_triage_path.exists():
        ai_cases = read_csv_if_exists(ai_cases_path)
        ai_triage = read_csv_if_exists(ai_triage_path)
    else:
        ai_cases, ai_triage = run_ai_triage(
            repo_root,
            config=config,
            status=first_status,
            root_candidates=root_candidates,
            max_cases=max_api_cases,
            suffix=suffix,
        )
    ai_roots_path = suffixed_path((repo_root / REVIEW_DIR / "public_fresh_ai_verified_roots.csv").resolve(), suffix)
    ai_archive_pages_path = suffixed_path((repo_root / INTERIM_DIR / "public_fresh_ai_archive_pages.csv").resolve(), suffix)
    ai_year_candidates_path = suffixed_path((repo_root / INTERIM_DIR / "public_fresh_ai_year_candidates.csv").resolve(), suffix)
    if reuse_ai_expansion and ai_roots_path.exists() and ai_year_candidates_path.exists():
        ai_roots = read_csv_if_exists(ai_roots_path)
        ai_archive_pages = read_csv_if_exists(ai_archive_pages_path)
        ai_year_candidates = read_csv_if_exists(ai_year_candidates_path)
        ai_direct_candidates = pd.DataFrame()
    else:
        ai_roots = verify_ai_roots(ai_triage, timeout_seconds=timeout_seconds) if not ai_triage.empty else pd.DataFrame()
        ai_decisions = decisions_from_ai_roots(ai_roots)
        ai_archive_pages, ai_result_by_url = build_archive_pages_concurrent(
            repo_root,
            ai_decisions,
            timeout_seconds=timeout_seconds,
            max_archive_pages_per_institution=max_archive_pages_per_institution,
            max_workers=max_workers,
        ) if not ai_decisions.empty else (pd.DataFrame(), {})
        ai_year_candidates = build_year_candidates(ai_archive_pages, ai_result_by_url) if not ai_archive_pages.empty else pd.DataFrame()
        if not ai_year_candidates.empty:
            ai_year_candidates["candidate_source_method"] = "ai_verified_root_archive"
        ai_direct_candidates = direct_catalog_candidates(ai_triage, timeout_seconds=timeout_seconds)
    all_candidates = pd.concat(
        [frame for frame in [first_candidates, ai_year_candidates, ai_direct_candidates] if not frame.empty],
        ignore_index=True,
        sort=False,
    ) if any(not frame.empty for frame in [first_candidates, ai_year_candidates, ai_direct_candidates]) else pd.DataFrame()
    all_candidates = filter_candidate_rows(all_candidates)
    final_panel = merge_final_panel(first_panel, all_candidates)
    final_status = build_final_status(first_status, final_panel, ai_triage, ai_roots)

    outputs = PublicFreshPipelineOutputs(
        first_pass_workbook=first_outputs.workbook,
        first_pass_status_csv=first_outputs.institution_status_csv,
        ai_cases_csv=ai_cases_path,
        ai_triage_csv=ai_triage_path,
        ai_verified_roots_csv=ai_roots_path,
        ai_archive_pages_csv=ai_archive_pages_path,
        ai_year_candidates_csv=ai_year_candidates_path,
        final_year_panel_csv=suffixed_path((repo_root / REVIEW_DIR / "public_fresh_full_year_panel.csv").resolve(), suffix),
        final_status_csv=suffixed_path((repo_root / REVIEW_DIR / "public_fresh_full_status.csv").resolve(), suffix),
        workbook=suffixed_path((repo_root / REVIEW_DIR / "public_fresh_full_process.xlsx").resolve(), suffix),
        summary_md=suffixed_path((repo_root / LOG_DIR / "public_fresh_full_process_summary.md").resolve(), suffix),
    )
    for path in outputs.__dict__.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    ai_cases.to_csv(outputs.ai_cases_csv, index=False)
    ai_triage.to_csv(outputs.ai_triage_csv, index=False)
    ai_roots.to_csv(outputs.ai_verified_roots_csv, index=False)
    ai_archive_pages.to_csv(outputs.ai_archive_pages_csv, index=False)
    pd.concat([ai_year_candidates, ai_direct_candidates], ignore_index=True, sort=False).to_csv(
        outputs.ai_year_candidates_csv,
        index=False,
    )
    final_panel.to_csv(outputs.final_year_panel_csv, index=False)
    final_status.to_csv(outputs.final_status_csv, index=False)
    write_workbook(
        outputs.workbook,
        {
            "start_here": final_status,
            "final_year_panel": final_panel,
            "ai_triage": ai_triage,
            "ai_verified_roots": ai_roots,
            "ai_year_candidates": pd.concat([ai_year_candidates, ai_direct_candidates], ignore_index=True, sort=False),
            "first_pass_status": first_status,
        },
    )
    write_summary(outputs.summary_md, suffix=suffix, final_status=final_status, outputs=outputs)
    copy_first_pass_delivery(repo_root, first_outputs, suffix, first_status)
    copy_delivery(repo_root, outputs, suffix, final_status)
    return outputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--suffix", required=True)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--rank-start", type=int, default=1)
    parser.add_argument("--max-api-cases", type=int, default=None)
    parser.add_argument("--timeout-seconds", type=int, default=3)
    parser.add_argument("--max-root-candidates-per-institution", type=int, default=24)
    parser.add_argument("--max-archive-pages-per-institution", type=int, default=4)
    parser.add_argument("--max-workers", type=int, default=16)
    parser.add_argument("--reuse-first-pass", action="store_true")
    parser.add_argument("--reuse-ai-triage", action="store_true")
    parser.add_argument("--reuse-ai-expansion", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = args.root.resolve() if args.root else repo_root_from_cwd()
    outputs = run(
        repo_root,
        suffix=args.suffix,
        limit=args.limit,
        rank_start=args.rank_start,
        config_path=args.config,
        max_api_cases=args.max_api_cases,
        timeout_seconds=args.timeout_seconds,
        max_root_candidates_per_institution=args.max_root_candidates_per_institution,
        max_archive_pages_per_institution=args.max_archive_pages_per_institution,
        max_workers=args.max_workers,
        reuse_first_pass=args.reuse_first_pass,
        reuse_ai_triage=args.reuse_ai_triage,
        reuse_ai_expansion=args.reuse_ai_expansion,
    )
    for label, output_path in outputs.__dict__.items():
        print(f"{label}: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
