"""OCR/visual catalog-year confirmation pilot for scanned catalog PDFs."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pandas as pd

from .ai_config import AIConfig, load_ai_config, repo_root_from_cwd
from .catalog_retrieval import (
    DEFAULT_TIMEOUT_SECONDS,
    parse_wayback_snapshot,
    raw_wayback_snapshot_url,
    retrieve_url,
    save_source_body,
    wayback_available_latest_url,
    wayback_available_url,
)


DATA_DIR = Path("../data_policy_pipeline")
INTERIM_DIR = DATA_DIR / "interim"
LOG_DIR = DATA_DIR / "logs"
REVIEW_DIR = DATA_DIR / "review"

PANEL_CANDIDATES_INPUT = INTERIM_DIR / "catalog_panel_candidates_strict_pilot.csv"
OCR_OUTPUT = INTERIM_DIR / "catalog_ocr_visual_confirmation_strict_pilot.csv"
OCR_SUMMARY_OUTPUT = LOG_DIR / "phase3_ocr_visual_confirmation_summary.md"
PAGE_IMAGE_DIR = REVIEW_DIR / "ocr_page_images" / "strict_pilot_abac"

TASK_TYPE = "catalog_year_visual_ocr"
PROMPT_VERSION = "catalog_year_visual_ocr_v0"
BUNDLED_BIN_DIR = Path("/Users/verosovero/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin")
PDFTOPPM = BUNDLED_BIN_DIR / "pdftoppm"


@dataclass(frozen=True)
class OCRVisualOutputs:
    confirmation_table: Path
    summary_report: Path
    page_image_dir: Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_candidates(repo_root: Path) -> pd.DataFrame:
    candidates = pd.read_csv(repo_root / PANEL_CANDIDATES_INPUT, low_memory=False)
    return candidates[candidates["source_status"].eq("scanned_pdf_needs_ocr_or_visual_review")].copy()


def read_existing_confirmation(repo_root: Path) -> pd.DataFrame:
    path = repo_root / OCR_OUTPUT
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, low_memory=False)


def exclude_existing_candidates(candidates: pd.DataFrame, existing: pd.DataFrame) -> pd.DataFrame:
    if existing.empty or "source_id" not in existing.columns:
        return candidates
    completed_ids = set(existing["source_id"].dropna().astype(str))
    return candidates.loc[~candidates["source_id"].astype(str).isin(completed_ids)].copy()


def merge_confirmation_tables(existing: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    if existing.empty:
        return new
    if new.empty:
        return existing
    merged = pd.concat([existing, new], ignore_index=True, sort=False)
    merged["_row_order"] = range(len(merged))
    merged = merged.sort_values(["source_id", "_row_order"]).drop_duplicates("source_id", keep="last")
    return merged.drop(columns=["_row_order"]).sort_values(["unitid", "catalog_year_start", "source_id"])


def original_url_from_wayback(url: str) -> str:
    parsed = urlparse(url)
    if parsed.netloc.lower() != "web.archive.org":
        return url
    marker = "/http"
    marker_index = parsed.path.find(marker)
    if marker_index == -1:
        return url
    return parsed.path[marker_index + 1 :]


def candidate_pdf_attempt_urls(source: pd.Series) -> list[tuple[str, str]]:
    candidate_url = str(source["candidate_url"])
    original_url = original_url_from_wayback(candidate_url)
    attempts = [("candidate_url", candidate_url)]
    for method, lookup_url in [
        ("wayback_latest_snapshot", wayback_available_latest_url(original_url)),
        ("wayback_year_snapshot", wayback_available_url(original_url, int(source["catalog_year_start"]))),
    ]:
        lookup = retrieve_url(lookup_url, timeout_seconds=DEFAULT_TIMEOUT_SECONDS)
        if lookup["retrieval_status"] not in {"retrieved", "retrieved_truncated"}:
            continue
        snapshot_url = parse_wayback_snapshot(lookup["body"])
        if snapshot_url:
            attempts.append((method, raw_wayback_snapshot_url(snapshot_url)))
    seen = set()
    out = []
    for method, url in attempts:
        if url not in seen:
            out.append((method, url))
            seen.add(url)
    return out


def retrieve_candidate_pdf(
    repo_root: Path,
    source: pd.Series,
    timeout_seconds: int,
    *,
    attempt_method: str,
    attempt_url: str,
) -> tuple[str, dict[str, Any]]:
    result = retrieve_url(attempt_url, timeout_seconds=timeout_seconds)
    local_path = ""
    if result["retrieval_status"] in {"retrieved", "retrieved_truncated"}:
        local_path = str(
            save_source_body(
                repo_root,
                str(source["source_id"]),
                attempt_method,
                attempt_url,
                str(result["content_type"]),
                result["body"],
            )
        )
    return local_path, result


def render_first_page(repo_root: Path, pdf_path: str, source_id: str) -> tuple[str, str]:
    if not pdf_path:
        return "", "missing_pdf"
    if not PDFTOPPM.exists():
        return "", "pdftoppm_unavailable"
    output_dir = (repo_root / PAGE_IMAGE_DIR / source_id).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_prefix = output_dir / "page"
    cmd = [
        str(PDFTOPPM),
        "-png",
        "-singlefile",
        "-f",
        "1",
        "-l",
        "1",
        "-r",
        "180",
        pdf_path,
        str(output_prefix),
    ]
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    image_path = output_dir / "page.png"
    if result.returncode != 0 or not image_path.exists():
        return "", f"render_error:{result.stderr.strip()[:300]}"
    return str(image_path), "rendered_first_page"


def call_openai_visual_ocr(
    config: AIConfig,
    source: pd.Series,
    image_path: str,
) -> tuple[dict[str, Any], str, str, str]:
    call_id = f"{TASK_TYPE}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"
    raw_path = config.workflow.raw_response_dir / f"{call_id}.json"
    parsed_path = config.workflow.parsed_response_dir / f"{call_id}.json"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    parsed_path.parent.mkdir(parents=True, exist_ok=True)

    prompt = build_visual_prompt(source)
    error_type = ""
    error_message = ""
    parsed: dict[str, Any] = {}
    raw: dict[str, Any] = {}
    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=os.environ[config.openai.api_key_env],
            timeout=config.openai.timeout_seconds,
            max_retries=config.openai.max_retries,
        )
        response = client.responses.create(
            model=config.openai.model,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {"type": "input_image", "image_url": image_data_url(image_path)},
                    ],
                }
            ],
        )
        raw = response.model_dump(mode="json") if hasattr(response, "model_dump") else {"repr": repr(response)}
        parsed = extract_json_object(str(getattr(response, "output_text", "")))
    except Exception as exc:  # pragma: no cover - exact API failures vary.
        error_type = type(exc).__name__
        error_message = safe_error_message(str(exc))
        raw = {"error_type": error_type, "error_message": error_message}
        parsed = {}

    raw_path.write_text(json.dumps(raw, indent=2, sort_keys=True), encoding="utf-8")
    parsed_path.write_text(json.dumps(parsed, indent=2, sort_keys=True), encoding="utf-8")
    metadata = {
        "call_id": call_id,
        "task_type": TASK_TYPE,
        "prompt_version": PROMPT_VERSION,
        "model": config.openai.model,
        "source_id": source["source_id"],
        "input_hash": sha256_text(prompt + image_sha256(image_path)),
        "raw_response_path": str(raw_path),
        "parsed_response_path": str(parsed_path),
        "validation_status": "api_error" if error_type else "parsed",
        "error_type": error_type,
        "error_message": error_message,
        "created_at": utc_now(),
    }
    append_jsonl(config.workflow.log_dir / "api_call_log.jsonl", metadata)
    return parsed, call_id, str(raw_path), str(parsed_path)


def build_visual_prompt(source: pd.Series) -> str:
    payload = {
        "task": "Read the first page image of a college catalog PDF and identify explicit catalog-year evidence.",
        "institution_name": source["institution_name"],
        "candidate_url": source["candidate_url"],
        "source_title_from_archive": source["source_title"],
        "expected_catalog_year_start": int(source["catalog_year_start"]),
        "expected_catalog_year_end": int(source["catalog_year_end"]),
        "instructions": [
            "Use only visible text in the image.",
            "Do not infer the catalog year from URL or filename.",
            "If the year range is not visible, return visual_confirmation_status='not_confirmed'.",
            "Return compact JSON only.",
        ],
        "required_json_fields": [
            "visual_confirmation_status",
            "catalog_year_start",
            "catalog_year_end",
            "evidence_text",
            "confidence",
            "notes",
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def image_data_url(image_path: str) -> str:
    data = Path(image_path).read_bytes()
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def image_sha256(image_path: str) -> str:
    return hashlib.sha256(Path(image_path).read_bytes()).hexdigest()


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


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")


def safe_error_message(message: str) -> str:
    exact_key = os.environ.get("OPENAI_API_KEY", "")
    if exact_key:
        message = message.replace(exact_key, "[redacted]")
    return re.sub(r"sk-[A-Za-z0-9*_-]+", "[redacted-api-key]", message)


def status_from_ai(source: pd.Series, parsed: dict[str, Any]) -> tuple[str, bool, str, str, str]:
    status = str(parsed.get("visual_confirmation_status", "")).strip() or "not_attempted"
    evidence = str(parsed.get("evidence_text", "")).strip()
    confidence = str(parsed.get("confidence", "")).strip()
    notes = str(parsed.get("notes", "")).strip()
    confirmed = False
    try:
        start = int(parsed.get("catalog_year_start", ""))
        end = int(parsed.get("catalog_year_end", ""))
        confirmed = (
            status == "confirmed"
            and start == int(source["catalog_year_start"])
            and end == int(source["catalog_year_end"])
            and bool(evidence)
            and evidence_contains_year_range(evidence, start, end)
        )
    except (TypeError, ValueError):
        confirmed = False
    if confirmed:
        confirmation_status = "visual_ai_confirmed"
    elif status == "confirmed":
        confirmation_status = "visual_ai_evidence_insufficient"
    else:
        confirmation_status = f"visual_ai_{status}"
    return confirmation_status, confirmed, evidence, confidence, notes


def evidence_contains_year_range(evidence: str, start: int, end: int) -> bool:
    compact = re.sub(r"\s+", " ", evidence)
    return str(start) in compact and str(end) in compact


def build_confirmation_table(
    repo_root: Path,
    candidates: pd.DataFrame,
    *,
    config: AIConfig | None,
    use_api: bool,
    max_api_requests: int,
    timeout_seconds: int,
    max_sources: int | None,
) -> pd.DataFrame:
    rows = []
    api_calls = 0
    selected = candidates.sort_values(["unitid", "catalog_year_start", "source_id"])
    if max_sources is not None:
        selected = selected.head(max_sources)
    for _, source in selected.iterrows():
        pdf_path = ""
        image_path = ""
        render_status = "not_attempted"
        retrieval: dict[str, Any] = {"retrieval_status": "not_attempted", "http_status": "", "content_type": ""}
        pdf_recovery_method = ""
        pdf_attempt_url = ""
        attempted_urls = []
        for attempt_method, attempt_url in candidate_pdf_attempt_urls(source):
            attempted_urls.append(f"{attempt_method}:{attempt_url}")
            candidate_pdf_path, candidate_retrieval = retrieve_candidate_pdf(
                repo_root,
                source,
                timeout_seconds,
                attempt_method=attempt_method,
                attempt_url=attempt_url,
            )
            candidate_image_path, candidate_render_status = render_first_page(
                repo_root, candidate_pdf_path, str(source["source_id"])
            )
            retrieval = candidate_retrieval
            pdf_path = candidate_pdf_path
            image_path = candidate_image_path
            render_status = candidate_render_status
            pdf_recovery_method = attempt_method
            pdf_attempt_url = attempt_url
            if image_path:
                break
        api_status = "not_attempted"
        confirmed = False
        evidence_text = ""
        confidence = ""
        notes = ""
        call_id = ""
        raw_response_path = ""
        parsed_response_path = ""

        if use_api and config and config.live_enabled and image_path and api_calls < max_api_requests:
            parsed, call_id, raw_response_path, parsed_response_path = call_openai_visual_ocr(config, source, image_path)
            api_calls += 1
            api_status, confirmed, evidence_text, confidence, notes = status_from_ai(source, parsed)
        elif image_path:
            api_status = "rendered_for_human_visual_review"
        elif retrieval["retrieval_status"] not in {"retrieved", "retrieved_truncated"}:
            api_status = "pdf_not_retrieved"
        else:
            api_status = render_status

        rows.append(
            {
                "source_id": source["source_id"],
                "unitid": int(source["unitid"]),
                "institution_name": source["institution_name"],
                "candidate_url": source["candidate_url"],
                "source_title": source["source_title"],
                "catalog_year_start": int(source["catalog_year_start"]),
                "catalog_year_end": int(source["catalog_year_end"]),
                "retrieval_status": retrieval["retrieval_status"],
                "http_status": retrieval["http_status"],
                "content_type": retrieval["content_type"],
                "pdf_recovery_method": pdf_recovery_method,
                "pdf_attempt_url": pdf_attempt_url,
                "pdf_attempted_urls": " | ".join(attempted_urls),
                "local_pdf_path": pdf_path,
                "page_image_path": image_path,
                "render_status": render_status,
                "ocr_mode": "openai_visual" if use_api and config and config.live_enabled else "render_only",
                "confirmation_status": api_status,
                "confirmed_catalog_year": confirmed,
                "visual_evidence_text": evidence_text,
                "visual_confidence": confidence,
                "visual_notes": notes,
                "api_call_id": call_id,
                "raw_response_path": raw_response_path,
                "parsed_response_path": parsed_response_path,
                "created_at": utc_now(),
            }
        )
    return pd.DataFrame(rows)


def write_summary(path: Path, table: pd.DataFrame) -> None:
    lines = [
        "# Phase 3 OCR / Visual Catalog-Year Confirmation",
        "",
        f"Generated at: {utc_now()}",
        "",
        "Scope: ABAC scanned catalog PDF candidates only. Confirmation requires visible catalog-year evidence from rendered page image/API visual OCR, not URL or filename patterns.",
        "",
        "## Counts",
        "",
        f"- Candidate sources: {len(table)}",
        f"- Confirmed catalog-year sources: {int(table['confirmed_catalog_year'].sum()) if not table.empty else 0}",
        "",
        "## Confirmation Status",
        "",
    ]
    if table.empty:
        lines.append("- none")
    else:
        for status, count in table["confirmation_status"].value_counts(dropna=False).items():
            lines.append(f"- {status}: {count}")
    lines.extend(["", "## Retrieval Status", ""])
    if table.empty:
        lines.append("- none")
    else:
        for status, count in table["retrieval_status"].value_counts(dropna=False).items():
            lines.append(f"- {status}: {count}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_ocr_visual_review(
    repo_root: Path,
    *,
    config_path: Path | None = None,
    use_api: bool = False,
    max_api_requests: int | None = None,
    max_sources: int | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> OCRVisualOutputs:
    repo_root = repo_root.resolve()
    candidates = read_candidates(repo_root)
    existing = read_existing_confirmation(repo_root)
    candidates = exclude_existing_candidates(candidates, existing)
    config = load_ai_config(config_path, root=repo_root) if use_api else None
    api_limit = 0
    if use_api and config:
        api_limit = config.workflow.max_requests_per_run if max_api_requests is None else max_api_requests
        api_limit = min(api_limit, config.workflow.max_requests_per_run)
    new_table = build_confirmation_table(
        repo_root,
        candidates,
        config=config,
        use_api=use_api,
        max_api_requests=api_limit,
        timeout_seconds=timeout_seconds,
        max_sources=max_sources,
    )
    table = merge_confirmation_tables(existing, new_table)

    outputs = OCRVisualOutputs(
        confirmation_table=(repo_root / OCR_OUTPUT).resolve(),
        summary_report=(repo_root / OCR_SUMMARY_OUTPUT).resolve(),
        page_image_dir=(repo_root / PAGE_IMAGE_DIR).resolve(),
    )
    outputs.confirmation_table.parent.mkdir(parents=True, exist_ok=True)
    outputs.summary_report.parent.mkdir(parents=True, exist_ok=True)
    outputs.page_image_dir.mkdir(parents=True, exist_ok=True)
    table.to_csv(outputs.confirmation_table, index=False)
    write_summary(outputs.summary_report, table)
    return outputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run OCR/visual catalog-year confirmation for scanned PDF candidates.")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--use-api", action="store_true")
    parser.add_argument("--max-api-requests", type=int, default=None)
    parser.add_argument("--max-sources", type=int, default=None)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve() if args.root else repo_root_from_cwd()
    outputs = run_ocr_visual_review(
        root,
        config_path=args.config,
        use_api=args.use_api,
        max_api_requests=args.max_api_requests,
        max_sources=args.max_sources,
        timeout_seconds=args.timeout_seconds,
    )
    for label, output_path in outputs.__dict__.items():
        print(f"{label}: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
