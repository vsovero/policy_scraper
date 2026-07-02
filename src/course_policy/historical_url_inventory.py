"""Build a historical URL-discovery inventory from prior project artifacts.

The inventory is a planning and benchmark-preservation lane. It scans old
artifact folders, normalizes URL attempts and reviewed discoveries, and writes
audit outputs plus a concise human-facing summary. It is deliberately separate
from the clean Step 1 production runner.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
from pandas.errors import EmptyDataError, ParserError

from .ai_config import repo_root_from_cwd


PIPELINE_HISTORICAL_DIR = Path("artifacts/PIPELINE_OUTPUTS/01_url_discovery/historical_inventory")
AUDIT_HISTORICAL_DIR = Path("artifacts/AUDIT_TRAILS/url_discovery_historical_inventory")

SCAN_ROOTS = (
    Path("artifacts/PILOTS/url_discovery"),
    Path("artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_chunks"),
    Path("artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_inputs"),
    Path("artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases"),
    Path("artifacts/OLD_OUTPUT_ARCHIVES"),
    Path("artifacts/AUDIT_TRAILS"),
    Path("artifacts/policy_data_internal/interim"),
)

SCAN_SUFFIXES = {".csv", ".md", ".json", ".txt"}
EXCLUDED_DIR_NAMES = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    "code_snapshot",
    "source_snapshot",
    "source_evidence_cache",
    "current_run_reattempt_cached_text",
    "url_discovery_historical_inventory",
    "historical_inventory",
}

ACCEPTED_DECISION_PREFIXES = ("accept_",)
ACCEPTED_DECISIONS = {
    "accept_current_run_source_review",
    "accept_exact_year_catalog",
    "accept_multi_year_catalog",
    "accept_official_policy_source",
    "accept_cached_external_evidence_replay",
}

PRIORITY_ORDER = {
    "valid_human_legacy": 1,
    "prior_programmatic_accepted_needs_current_reverification": 2,
    "unreviewed_prior_programmatic_candidate_lead": 3,
    "imported_llm_candidate_lead_overlay": 4,
    "unreviewed_human_legacy_candidate_lead": 5,
    "programmatic_attempt_no_valid_discovery": 6,
    "no_historical_programmatic_attempt_found": 7,
}

UNREVIEWED_LEAD_CLASSES = (
    "unreviewed_prior_programmatic_candidate_lead",
    "imported_llm_candidate_lead_overlay",
    "unreviewed_human_legacy_candidate_lead",
)


ATTEMPT_COLUMNS = [
    "inventory_row_id",
    "source_file_path",
    "source_file_sha256",
    "run_family",
    "file_role",
    "evidence_class",
    "unitid",
    "institution_name",
    "sector",
    "state",
    "academic_year",
    "url",
    "candidate_url",
    "final_url",
    "attempt_stage",
    "retrieval_status",
    "http_status",
    "ready_for_text_extraction",
    "source_opened",
    "review_decision",
    "review_reason",
    "classification_reason",
]

DISCOVERY_COLUMNS = [
    "inventory_discovery_id",
    "source_file_path",
    "source_file_sha256",
    "run_family",
    "file_role",
    "evidence_class",
    "unitid",
    "institution_name",
    "sector",
    "state",
    "academic_year",
    "url",
    "url_role",
    "source_type",
    "source_year_coverage",
    "provenance_type",
    "review_decision",
    "review_reason",
    "reviewed_by",
    "reviewed_at",
    "classification_reason",
]

TARGET_COLUMNS = ["unitid", "institution_name", "sector", "state", "academic_year", "source_file_path"]


@dataclass(frozen=True)
class HistoricalInventoryResult:
    audit_dir: Path
    summary_dir: Path
    source_file_manifest: Path
    file_level_classification: Path
    attempts: Path
    discoveries: Path
    institution_priority_buckets: Path
    source_family_summary: Path
    parse_exceptions: Path
    run_manifest: Path
    summary: Path
    files_scanned: int
    attempt_rows: int
    discovery_rows: int
    target_rows: int
    institution_rows: int


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def clean_text(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except TypeError:
        pass
    return str(value).strip()


def truthy(value: object) -> bool:
    return clean_text(value).lower() in {"1", "1.0", "true", "yes", "y"}


def read_csv_or_empty(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path, low_memory=False)
    except EmptyDataError:
        return pd.DataFrame()


def write_csv(frame: pd.DataFrame, path: Path, columns: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = frame.copy()
    if columns is not None:
        for column in columns:
            if column not in out.columns:
                out[column] = ""
        out = out[columns]
    out.to_csv(path, index=False)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative_path(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(path)


def normalize_path_reference(value: object, repo_root: Path) -> str:
    text = clean_text(value)
    if not text:
        return ""
    repo = repo_root.resolve().as_posix()
    return text.replace(repo + "/", "")


def first_value(row: pd.Series, names: list[str]) -> str:
    for name in names:
        if name in row.index:
            value = clean_text(row.get(name))
            if value:
                return value
    return ""


def row_year(row: pd.Series) -> str:
    return first_value(row, ["academic_year", "target_year", "year", "source_year_start", "target_years"])


def accepted_decision(value: object) -> bool:
    text = clean_text(value)
    return text in ACCEPTED_DECISIONS or text.startswith(ACCEPTED_DECISION_PREFIXES)


def url_host(value: object) -> str:
    text = clean_text(value)
    if not text:
        return ""
    parsed = urlparse(text if "://" in text else "https://" + text)
    return parsed.netloc.lower()


def infer_run_family(path: Path) -> str:
    for part in path.parts:
        if part.startswith(("pilot_batch_", "production_chunk_", "production_release_", "production_", "url_discovery_")):
            return part
        if part in {"mini_full_production_test_001", "clean_runner_tests"}:
            return part
    return ""


def classify_file_role(path: Path) -> tuple[str, str]:
    name = path.name
    lower = name.lower()
    if lower == "step4_suggestion_source_review.csv":
        return "suggestion_source_review", "review status for Claude/LLM suggestion pool"
    if (
        lower in {"public_claude_coverage_grid.csv", "private_llm_suggestions.csv"}
        or lower.startswith("private_step0_llm_suggestions_")
        or lower.startswith("public_fresh_ai_year_candidates_")
        or lower.startswith("public_fresh_ai_verified_roots_")
        or lower.startswith("public_fresh_ai_archive_pages_")
        or lower.startswith("public_fresh_ai_cases_")
        or lower.startswith("public_fresh_ai_triage_")
        or lower.startswith("step1_suggestion_")
        or lower.startswith("step3_suggestion_")
        or lower.startswith("suggestion_url_validation_")
    ):
        return "llm_suggestion_candidate", "Claude/LLM suggestion-pool candidate lead"
    if lower in {"output_urls_for_text_extraction.csv", "reviewed_url_handoff_panel.csv"}:
        return "url_handoff", "row-level URL handoff"
    if lower in {"output_source_ledger_delta.csv", "source_ledger.csv"}:
        return "source_ledger", "accepted source-ledger rows"
    if lower in {"unresolved_rows.csv", "url_stop_log.csv"}:
        return "unresolved_rows", "explicit unresolved rows"
    if lower == "benchmark_recovery.csv":
        return "benchmark_recovery", "benchmark recovery rows"
    if lower == "benchmark_misses.csv":
        return "benchmark_misses", "benchmark miss rows"
    if lower in {
        "source_review_log.csv",
        "current_run_reattempt_source_review.csv",
        "current_run_reattempt_source_review_auto.csv",
    }:
        return "source_review", "source-review rows"
    if lower in {
        "retrieved_candidate_url_evidence.csv",
        "candidate_retrieval_evidence.csv",
        "legacy_url_retrieval_evidence.csv",
        "current_run_reattempt_retrieved_evidence.csv",
    }:
        return "retrieval_evidence", "retrieval evidence rows"
    if lower == "candidate_url_ledger.csv":
        return "candidate_url_ledger", "production candidate ledger"
    if lower in {"legacy_evidence_links.csv", "preferred_legacy_links.csv"}:
        return "human_legacy_links", "human legacy evidence links"
    if lower == "benchmark_against_old_audit.csv":
        return "old_audit_benchmark", "old audit benchmark comparison"
    if lower == "target_panel.csv":
        return "target_panel", "target panel rows"
    if lower in {"input_manifest.csv", "output_manifest.csv", "release_manifest.csv", "source_evidence_manifest.csv"}:
        return "manifest", "manifest or evidence manifest"
    if lower.endswith(".md"):
        return "report_markdown", "human-facing report"
    if lower.endswith(".json"):
        return "json_metadata", "run metadata"
    if lower.endswith(".txt"):
        return "text_metadata", "run command or log"
    return "excluded_non_url_or_duplicate_artifact", "unrecognized artifact shape"


def should_skip_path(path: Path) -> bool:
    if path.name.startswith("."):
        return True
    return any(part in EXCLUDED_DIR_NAMES for part in path.parts)


def discover_source_files(repo_root: Path, scan_roots: tuple[Path, ...] = SCAN_ROOTS) -> list[Path]:
    files: list[Path] = []
    seen: set[Path] = set()
    for root in scan_roots:
        base = repo_root / root
        if not base.exists():
            continue
        if base.is_file():
            candidates = [base]
        else:
            candidates = [path for path in base.rglob("*") if path.is_file()]
        for path in candidates:
            if path.suffix.lower() not in SCAN_SUFFIXES:
                continue
            try:
                relative = path.resolve().relative_to(repo_root.resolve())
            except ValueError:
                relative = path
            if should_skip_path(relative):
                continue
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            files.append(path)
    return sorted(files, key=lambda value: relative_path(value, repo_root))


def file_manifest_record(path: Path, repo_root: Path) -> dict[str, object]:
    file_role, role_reason = classify_file_role(path)
    record: dict[str, object] = {
        "source_file_path": relative_path(path, repo_root),
        "file_name": path.name,
        "file_role": file_role,
        "role_reason": role_reason,
        "run_family": infer_run_family(path),
        "suffix": path.suffix.lower(),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "rows": "",
        "columns": "",
    }
    if path.suffix.lower() == ".csv":
        try:
            frame = read_csv_or_empty(path)
            record["rows"] = len(frame)
            record["columns"] = len(frame.columns)
        except (OSError, ParserError, UnicodeDecodeError):
            record["rows"] = ""
            record["columns"] = ""
    return record


def base_context(path: Path, repo_root: Path, file_role: str, file_sha: str) -> dict[str, object]:
    return {
        "source_file_path": relative_path(path, repo_root),
        "source_file_sha256": file_sha,
        "run_family": infer_run_family(path),
        "file_role": file_role,
    }


def base_row_fields(row: pd.Series) -> dict[str, object]:
    return {
        "unitid": first_value(row, ["unitid"]),
        "institution_name": first_value(row, ["institution_name", "instnm", "name"]),
        "sector": first_value(row, ["sector", "sector_group", "sector_stream"]),
        "state": first_value(row, ["state", "stabbr"]),
        "academic_year": row_year(row),
    }


def attempt_from_row(
    row: pd.Series,
    *,
    context: dict[str, object],
    evidence_class: str,
    url: str,
    candidate_url: str = "",
    final_url: str = "",
    attempt_stage: str = "",
    classification_reason: str = "",
) -> dict[str, object]:
    out = {
        **context,
        **base_row_fields(row),
        "evidence_class": evidence_class,
        "url": url,
        "candidate_url": candidate_url,
        "final_url": final_url,
        "attempt_stage": attempt_stage,
        "retrieval_status": first_value(
            row,
            ["retrieval_status", "candidate_retrieval_status", "live_retrieval_status", "cached_retrieval_status"],
        ),
        "http_status": first_value(row, ["http_status", "candidate_http_status", "live_http_status"]),
        "ready_for_text_extraction": first_value(
            row,
            ["ready_for_text_extraction", "current_ready", "final_ready_row_count"],
        ),
        "source_opened": first_value(row, ["source_opened"]),
        "review_decision": first_value(
            row,
            ["review_decision", "current_review_decision", "source_review_status", "manual_source_decision"],
        ),
        "review_reason": first_value(
            row,
            [
                "review_reason",
                "current_review_reason",
                "known_url_review_bucket",
                "live_validation_status",
                "validation_status",
                "stop_reason",
            ],
        ),
        "classification_reason": classification_reason,
    }
    return out


def discovery_from_row(
    row: pd.Series,
    *,
    context: dict[str, object],
    evidence_class: str,
    url: str,
    url_role: str,
    classification_reason: str,
) -> dict[str, object]:
    return {
        **context,
        **base_row_fields(row),
        "evidence_class": evidence_class,
        "url": url,
        "url_role": url_role,
        "source_type": first_value(row, ["source_type", "candidate_source_type", "candidate_scope", "root_type", "live_scope_type", "scope"]),
        "source_year_coverage": first_value(row, ["source_year_coverage", "source_year_coverage_note"]),
        "provenance_type": first_value(row, ["provenance_type", "source_ledger_provenance_type", "production_url_source", "stream"]),
        "review_decision": first_value(
            row,
            ["review_decision", "current_review_decision", "source_review_status", "manual_source_decision"],
        ),
        "review_reason": first_value(
            row,
            ["review_reason", "current_review_reason", "known_url_review_bucket", "live_validation_status", "validation_status"],
        ),
        "reviewed_by": first_value(row, ["reviewed_by"]),
        "reviewed_at": first_value(row, ["reviewed_at"]),
        "classification_reason": classification_reason,
    }


def classify_retrieval(row: pd.Series) -> tuple[str, str]:
    status = first_value(row, ["retrieval_status"]).lower()
    if status.startswith("retrieved"):
        return "unreviewed_prior_programmatic_candidate_lead", "retrieved candidate needs source-review confirmation"
    if status:
        return "programmatic_attempt_no_valid_discovery", f"retrieval did not produce usable evidence: {status}"
    return "unreviewed_prior_programmatic_candidate_lead", "candidate row without source-review decision"


def parse_human_legacy_links(frame: pd.DataFrame, context: dict[str, object]) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    attempts: list[dict[str, object]] = []
    discoveries: list[dict[str, object]] = []
    targets: list[dict[str, object]] = []
    for _, row in frame.iterrows():
        url = first_value(row, ["legacy_url"])
        if not first_value(row, ["unitid"]) or not row_year(row):
            continue
        targets.append({**base_row_fields(row), "source_file_path": context["source_file_path"]})
        if not url:
            attempts.append(
                attempt_from_row(
                    row,
                    context=context,
                    evidence_class="programmatic_attempt_no_valid_discovery",
                    url="",
                    attempt_stage="human_legacy_missing_url",
                    classification_reason="legacy evidence row has no URL",
                )
            )
            continue
        selected = truthy(row.get("source_can_be_prior_evidence")) or truthy(row.get("selected_as_prior_evidence"))
        evidence_class = "valid_human_legacy" if selected else "unreviewed_human_legacy_candidate_lead"
        reason = "human legacy evidence selected as usable prior evidence" if selected else "legacy URL needs review before use"
        attempts.append(
            attempt_from_row(
                row,
                context=context,
                evidence_class=evidence_class,
                url=url,
                candidate_url=url,
                attempt_stage="human_legacy_link",
                classification_reason=reason,
            )
        )
        if selected:
            discoveries.append(
                discovery_from_row(
                    row,
                    context=context,
                    evidence_class="valid_human_legacy",
                    url=url,
                    url_role="legacy_url",
                    classification_reason=reason,
                )
            )
    return attempts, discoveries, targets


def parse_url_handoff(frame: pd.DataFrame, context: dict[str, object]) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    attempts: list[dict[str, object]] = []
    discoveries: list[dict[str, object]] = []
    targets: list[dict[str, object]] = []
    for _, row in frame.iterrows():
        if not first_value(row, ["unitid"]) or not row_year(row):
            continue
        targets.append({**base_row_fields(row), "source_file_path": context["source_file_path"]})
        ready = truthy(row.get("ready_for_text_extraction")) or clean_text(row.get("url_status")) == "source_review_ready"
        accepted_url = first_value(row, ["url_for_text_extraction", "accepted_source_url"])
        candidate = first_value(row, ["candidate_url"])
        if ready and accepted_url:
            provenance = first_value(row, ["url_source_bucket", "production_url_source", "provenance_type"]).lower()
            if "human" in provenance or truthy(row.get("human_legacy_url_used")):
                evidence_class = "valid_human_legacy"
                reason = "ready handoff row uses human legacy provenance"
            else:
                evidence_class = "prior_programmatic_accepted_needs_current_reverification"
                reason = "historical ready handoff row requires current-run re-verification before production use"
            discoveries.append(
                discovery_from_row(
                    row,
                    context=context,
                    evidence_class=evidence_class,
                    url=accepted_url,
                    url_role="url_for_text_extraction",
                    classification_reason=reason,
                )
            )
            attempts.append(
                attempt_from_row(
                    row,
                    context=context,
                    evidence_class=evidence_class,
                    url=accepted_url,
                    candidate_url=candidate,
                    final_url=first_value(row, ["final_url_after_redirect"]),
                    attempt_stage="accepted_handoff",
                    classification_reason=reason,
                )
            )
        else:
            evidence_class = "unreviewed_prior_programmatic_candidate_lead" if candidate else "programmatic_attempt_no_valid_discovery"
            reason = "candidate exists but row was not accepted" if candidate else "no accepted candidate in historical handoff"
            attempts.append(
                attempt_from_row(
                    row,
                    context=context,
                    evidence_class=evidence_class,
                    url=accepted_url or candidate,
                    candidate_url=candidate,
                    final_url=first_value(row, ["final_url_after_redirect"]),
                    attempt_stage=first_value(row, ["url_status", "attrition_stage"]) or "not_ready_handoff",
                    classification_reason=reason,
                )
            )
    return attempts, discoveries, targets


def parse_source_ledger(frame: pd.DataFrame, context: dict[str, object]) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    attempts: list[dict[str, object]] = []
    discoveries: list[dict[str, object]] = []
    targets: list[dict[str, object]] = []
    for _, row in frame.iterrows():
        url = first_value(row, ["accepted_source_url", "url_for_text_extraction"])
        if not first_value(row, ["unitid"]) or not row_year(row):
            continue
        targets.append({**base_row_fields(row), "source_file_path": context["source_file_path"]})
        if not url:
            continue
        provenance = first_value(row, ["provenance_type", "source_ledger_provenance_type"]).lower()
        evidence_class = (
            "valid_human_legacy"
            if "human" in provenance
            else "prior_programmatic_accepted_needs_current_reverification"
        )
        reason = (
            "source ledger row records prior human provenance"
            if evidence_class == "valid_human_legacy"
            else "historical source-ledger row requires current-run re-verification before production use"
        )
        discoveries.append(
            discovery_from_row(
                row,
                context=context,
                evidence_class=evidence_class,
                url=url,
                url_role="accepted_source_url",
                classification_reason=reason,
            )
        )
        attempts.append(
            attempt_from_row(
                row,
                context=context,
                evidence_class=evidence_class,
                url=url,
                candidate_url=first_value(row, ["candidate_url"]),
                final_url=first_value(row, ["final_url_after_redirect"]),
                attempt_stage="accepted_source_ledger",
                classification_reason=reason,
            )
        )
    return attempts, discoveries, targets


def parse_source_review(frame: pd.DataFrame, context: dict[str, object]) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    attempts: list[dict[str, object]] = []
    discoveries: list[dict[str, object]] = []
    targets: list[dict[str, object]] = []
    for _, row in frame.iterrows():
        candidate = first_value(row, ["candidate_url"])
        final_url = first_value(row, ["final_url_after_redirect", "final_url"])
        decision = first_value(row, ["review_decision"])
        if not first_value(row, ["unitid"]) or not row_year(row):
            continue
        targets.append({**base_row_fields(row), "source_file_path": context["source_file_path"]})
        if accepted_decision(decision):
            evidence_class = "prior_programmatic_accepted_needs_current_reverification"
            reason = "accepted historical source-review row requires current-run re-verification before production use"
            discoveries.append(
                discovery_from_row(
                    row,
                    context=context,
                    evidence_class=evidence_class,
                    url=final_url or candidate,
                    url_role="source_review_accepted_url",
                    classification_reason=reason,
                )
            )
        elif candidate:
            evidence_class = "programmatic_attempt_no_valid_discovery" if decision.startswith("reject_") else "unreviewed_prior_programmatic_candidate_lead"
            reason = "source review rejected candidate" if decision.startswith("reject_") else "candidate has no accepted review decision"
        else:
            evidence_class = "programmatic_attempt_no_valid_discovery"
            reason = "source-review row has no candidate URL"
        attempts.append(
            attempt_from_row(
                row,
                context=context,
                evidence_class=evidence_class,
                url=final_url or candidate,
                candidate_url=candidate,
                final_url=final_url,
                attempt_stage="source_review",
                classification_reason=reason,
            )
        )
    return attempts, discoveries, targets


def parse_retrieval_evidence(frame: pd.DataFrame, context: dict[str, object]) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    attempts: list[dict[str, object]] = []
    targets: list[dict[str, object]] = []
    for _, row in frame.iterrows():
        candidate = first_value(row, ["candidate_url", "legacy_url"])
        final_url = first_value(row, ["final_url", "final_url_after_redirect"])
        if not candidate and not final_url:
            continue
        if first_value(row, ["unitid"]) and row_year(row):
            targets.append({**base_row_fields(row), "source_file_path": context["source_file_path"]})
        evidence_class, reason = classify_retrieval(row)
        attempts.append(
            attempt_from_row(
                row,
                context=context,
                evidence_class=evidence_class,
                url=final_url or candidate,
                candidate_url=candidate,
                final_url=final_url,
                attempt_stage="retrieval_evidence",
                classification_reason=reason,
            )
        )
    return attempts, [], targets


def parse_candidate_ledger(frame: pd.DataFrame, context: dict[str, object]) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    attempts: list[dict[str, object]] = []
    targets: list[dict[str, object]] = []
    for _, row in frame.iterrows():
        candidate = first_value(row, ["candidate_url"])
        if not first_value(row, ["unitid"]) or not row_year(row):
            continue
        targets.append({**base_row_fields(row), "source_file_path": context["source_file_path"]})
        if not candidate:
            continue
        source_type = first_value(row, ["candidate_source_type", "candidate_generation_method"]).lower()
        evidence_class = "valid_human_legacy" if "human_legacy" in source_type else "unreviewed_prior_programmatic_candidate_lead"
        reason = "raw human legacy candidate in production input" if evidence_class == "valid_human_legacy" else "candidate ledger row needs review"
        attempts.append(
            attempt_from_row(
                row,
                context=context,
                evidence_class=evidence_class,
                url=candidate,
                candidate_url=candidate,
                attempt_stage="candidate_url_ledger",
                classification_reason=reason,
            )
        )
    return attempts, [], targets


def suggestion_candidate_url(row: pd.Series) -> str:
    return first_value(row, ["candidate_url", "url", "root_url", "archive_url", "live_final_url", "final_url"])


def suggestion_failure_reason(row: pd.Series) -> str:
    status_text = " ".join(
        first_value(row, [name]).lower()
        for name in [
            "source_review_status",
            "manual_source_decision",
            "live_validation_status",
            "known_url_review_bucket",
            "known_url_outcome",
            "validation_status",
            "status",
            "scope",
            "candidate_scope",
            "live_scope_type",
            "stop_reason",
        ]
        if first_value(row, [name])
    )
    if not status_text:
        return ""
    failure_terms = [
        "wrong_institution",
        "graduate_only",
        "school_specific",
        "inactive_url",
        "no_candidate_url",
        "manual_rejected",
        "bad_scope",
        "not_catalog",
    ]
    return next((term for term in failure_terms if term in status_text), "")


def parse_llm_suggestion_candidates(frame: pd.DataFrame, context: dict[str, object]) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    attempts: list[dict[str, object]] = []
    targets: list[dict[str, object]] = []
    for _, row in frame.iterrows():
        if not first_value(row, ["unitid"]):
            continue
        if row_year(row):
            targets.append({**base_row_fields(row), "source_file_path": context["source_file_path"]})
        candidate = suggestion_candidate_url(row)
        if not candidate:
            attempts.append(
                attempt_from_row(
                    row,
                    context=context,
                    evidence_class="programmatic_attempt_no_valid_discovery",
                    url="",
                    attempt_stage="llm_suggestion_no_candidate_url",
                    classification_reason="Claude/LLM suggestion row had no URL or source root candidate",
                )
            )
            continue
        failure = suggestion_failure_reason(row)
        if failure:
            evidence_class = "programmatic_attempt_no_valid_discovery"
            reason = f"Claude/LLM suggestion was historically flagged as unusable: {failure}"
        else:
            evidence_class = "imported_llm_candidate_lead_overlay"
            reason = "Claude/LLM suggestion-pool URL/root lead requires current-run recovery and source review"
        attempts.append(
            attempt_from_row(
                row,
                context=context,
                evidence_class=evidence_class,
                url=candidate,
                candidate_url=first_value(row, ["candidate_url", "url"]) or candidate,
                final_url=first_value(row, ["live_final_url", "final_url"]),
                attempt_stage=first_value(row, ["candidate_source_method", "stage", "validation_status", "live_validation_status"])
                or "llm_suggestion_candidate",
                classification_reason=reason,
            )
        )
    return attempts, [], targets


def parse_suggestion_source_review(frame: pd.DataFrame, context: dict[str, object]) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    attempts: list[dict[str, object]] = []
    discoveries: list[dict[str, object]] = []
    targets: list[dict[str, object]] = []
    for _, row in frame.iterrows():
        if not first_value(row, ["unitid"]):
            continue
        if row_year(row):
            targets.append({**base_row_fields(row), "source_file_path": context["source_file_path"]})
        candidate = suggestion_candidate_url(row)
        status = first_value(row, ["source_review_status", "manual_source_decision", "row_status", "panel_routing_status"]).lower()
        if "already_final_ready" in status or "manual_accept" in status or status in {"accept", "accepted"}:
            evidence_class = "prior_programmatic_accepted_needs_current_reverification"
            reason = "Claude/LLM suggestion stream had historical accepted/final-ready source review; current-run recovery and review still required"
        elif "manual_rejected" in status or "wrong_institution" in status or "no_valid" in status or "no_candidate" in status:
            evidence_class = "programmatic_attempt_no_valid_discovery"
            reason = f"Claude/LLM suggestion source-review status was not usable: {status}"
        elif candidate:
            evidence_class = "imported_llm_candidate_lead_overlay"
            reason = "Claude/LLM suggestion source-review row still needs source review"
        else:
            evidence_class = "programmatic_attempt_no_valid_discovery"
            reason = "Claude/LLM suggestion source-review row had no URL candidate"
        attempts.append(
            attempt_from_row(
                row,
                context=context,
                evidence_class=evidence_class,
                url=candidate,
                candidate_url=first_value(row, ["candidate_url", "url"]) or candidate,
                final_url=first_value(row, ["live_final_url", "final_url"]),
                attempt_stage=status or "suggestion_source_review",
                classification_reason=reason,
            )
        )
        if evidence_class == "prior_programmatic_accepted_needs_current_reverification" and candidate:
            discoveries.append(
                discovery_from_row(
                    row,
                    context=context,
                    evidence_class=evidence_class,
                    url=candidate,
                    url_role="suggestion_review_accepted_url",
                    classification_reason=reason,
                )
            )
    return attempts, discoveries, targets


def parse_unresolved_rows(frame: pd.DataFrame, context: dict[str, object]) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    attempts: list[dict[str, object]] = []
    targets: list[dict[str, object]] = []
    for _, row in frame.iterrows():
        if not first_value(row, ["unitid"]) or not row_year(row):
            continue
        targets.append({**base_row_fields(row), "source_file_path": context["source_file_path"]})
        candidate = first_value(row, ["candidate_url"])
        attempts.append(
            attempt_from_row(
                row,
                context=context,
                evidence_class="programmatic_attempt_no_valid_discovery",
                url=candidate,
                candidate_url=candidate,
                attempt_stage=first_value(row, ["url_status"]) or "unresolved_row",
                classification_reason=first_value(row, ["unresolved_reason", "stop_reason"]) or "row unresolved in historical artifact",
            )
        )
    return attempts, [], targets


def parse_benchmark_recovery(frame: pd.DataFrame, context: dict[str, object]) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    attempts: list[dict[str, object]] = []
    discoveries: list[dict[str, object]] = []
    targets: list[dict[str, object]] = []
    for _, row in frame.iterrows():
        benchmark_url = first_value(row, ["benchmark_url", "old_production_best_url"])
        accepted_url = first_value(row, ["accepted_source_url", "current_url_for_text_extraction"])
        if not first_value(row, ["unitid"]) or not row_year(row):
            continue
        targets.append({**base_row_fields(row), "source_file_path": context["source_file_path"]})
        group = first_value(row, ["benchmark_group"]).lower()
        invalidated = truthy(row.get("row_invalidated_by_current_review"))
        current_recovered = (
            truthy(row.get("current_run_recovered"))
            or truthy(row.get("current_ready_for_text_extraction"))
            or truthy(row.get("old_ready_for_text_extraction"))
        )
        if invalidated:
            evidence_class = "programmatic_attempt_no_valid_discovery"
            reason = "benchmark row was invalidated by current review"
        elif "human" in group and benchmark_url:
            evidence_class = "valid_human_legacy"
            reason = "benchmark row preserves human legacy URL evidence"
        elif current_recovered and (accepted_url or benchmark_url):
            evidence_class = "prior_programmatic_accepted_needs_current_reverification"
            reason = "benchmark row was recovered in a historical run"
        else:
            evidence_class = "programmatic_attempt_no_valid_discovery"
            reason = "benchmark row was not recovered by the historical run"
        attempts.append(
            attempt_from_row(
                row,
                context=context,
                evidence_class=evidence_class,
                url=accepted_url or benchmark_url,
                candidate_url=benchmark_url,
                attempt_stage="benchmark_recovery",
                classification_reason=reason,
            )
        )
        if evidence_class in {"valid_human_legacy", "prior_programmatic_accepted_needs_current_reverification"}:
            discoveries.append(
                discovery_from_row(
                    row,
                    context=context,
                    evidence_class=evidence_class,
                    url=accepted_url or benchmark_url,
                    url_role="benchmark_url",
                    classification_reason=reason,
                )
            )
    return attempts, discoveries, targets


def parse_target_panel(frame: pd.DataFrame, context: dict[str, object]) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    targets: list[dict[str, object]] = []
    for _, row in frame.iterrows():
        if first_value(row, ["unitid"]) and row_year(row):
            targets.append({**base_row_fields(row), "source_file_path": context["source_file_path"]})
    return [], [], targets


def parse_known_csv(path: Path, repo_root: Path, file_role: str, file_sha: str) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    frame = read_csv_or_empty(path)
    context = base_context(path, repo_root, file_role, file_sha)
    if file_role == "human_legacy_links":
        return parse_human_legacy_links(frame, context)
    if file_role == "url_handoff":
        return parse_url_handoff(frame, context)
    if file_role == "source_ledger":
        return parse_source_ledger(frame, context)
    if file_role == "source_review":
        return parse_source_review(frame, context)
    if file_role == "retrieval_evidence":
        return parse_retrieval_evidence(frame, context)
    if file_role == "candidate_url_ledger":
        return parse_candidate_ledger(frame, context)
    if file_role == "llm_suggestion_candidate":
        return parse_llm_suggestion_candidates(frame, context)
    if file_role == "suggestion_source_review":
        return parse_suggestion_source_review(frame, context)
    if file_role in {"unresolved_rows", "benchmark_misses"}:
        return parse_unresolved_rows(frame, context)
    if file_role in {"benchmark_recovery", "old_audit_benchmark"}:
        return parse_benchmark_recovery(frame, context)
    if file_role == "target_panel":
        return parse_target_panel(frame, context)
    return [], [], []


def with_inventory_ids(rows: list[dict[str, object]], id_name: str) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame.insert(0, id_name, range(1, len(frame) + 1))
    return frame


def clean_normalized_frame(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = frame.copy()
    for column in columns:
        if column not in out.columns:
            out[column] = ""
    out = out[columns].copy()
    for column in ["unitid", "academic_year"]:
        if column in out.columns:
            out[column] = pd.to_numeric(out[column], errors="coerce").astype("Int64")
    return out


def target_frame_from_rows(rows: list[dict[str, object]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    if frame.empty:
        return pd.DataFrame(columns=TARGET_COLUMNS)
    for column in TARGET_COLUMNS:
        if column not in frame.columns:
            frame[column] = ""
    frame["unitid"] = pd.to_numeric(frame["unitid"], errors="coerce").astype("Int64")
    frame["academic_year"] = pd.to_numeric(frame["academic_year"], errors="coerce").astype("Int64")
    frame = frame.loc[frame["unitid"].notna() & frame["academic_year"].notna()].copy()
    return frame[TARGET_COLUMNS].drop_duplicates(["unitid", "academic_year", "source_file_path"])


def build_priority_buckets(targets: pd.DataFrame, attempts: pd.DataFrame, discoveries: pd.DataFrame) -> pd.DataFrame:
    if targets.empty and attempts.empty and discoveries.empty:
        return pd.DataFrame(
            columns=[
                "unitid",
                "institution_name",
                "sector",
                "state",
                "priority_bucket",
                "priority_rank",
                "target_year_rows",
                "valid_human_legacy_rows",
                "prior_programmatic_accepted_rows",
                "unreviewed_prior_programmatic_lead_rows",
                "imported_llm_candidate_lead_rows",
                "unreviewed_human_legacy_candidate_lead_rows",
                "unreviewed_candidate_lead_rows",
                "failed_attempt_rows",
                "no_historical_attempt_rows",
                "years_observed",
                "source_files",
                "recommended_next_step",
            ]
        )
    row_frames = []
    for frame in [targets, attempts, discoveries]:
        if not frame.empty:
            row_frames.append(frame[[column for column in ["unitid", "institution_name", "sector", "state", "academic_year", "source_file_path"] if column in frame.columns]].copy())
    universe = pd.concat(row_frames, ignore_index=True).copy()
    universe["unitid"] = pd.to_numeric(universe["unitid"], errors="coerce").astype("Int64")
    universe["academic_year"] = pd.to_numeric(universe["academic_year"], errors="coerce").astype("Int64")
    universe = universe.loc[universe["unitid"].notna()].copy()
    keys = universe[["unitid", "academic_year"]].drop_duplicates()

    def key_counts(frame: pd.DataFrame, evidence_classes: str | tuple[str, ...], output_column: str | None = None) -> pd.DataFrame:
        classes = (evidence_classes,) if isinstance(evidence_classes, str) else evidence_classes
        count_column = output_column or f"{classes[0]}_rows"
        if frame.empty:
            return pd.DataFrame(columns=["unitid", count_column])
        subset = frame.loc[frame["evidence_class"].isin(classes), ["unitid", "academic_year"]].drop_duplicates()
        if subset.empty:
            return pd.DataFrame(columns=["unitid", count_column])
        return subset.groupby("unitid", as_index=False).size().rename(columns={"size": count_column})

    attempts_keyed = attempts[["unitid", "academic_year"]].drop_duplicates() if not attempts.empty else pd.DataFrame(columns=["unitid", "academic_year"])
    no_attempt = keys.merge(attempts_keyed.assign(has_attempt=True), on=["unitid", "academic_year"], how="left")
    no_attempt = no_attempt.loc[no_attempt["has_attempt"].isna(), ["unitid", "academic_year"]]
    no_attempt_counts = no_attempt.groupby("unitid", as_index=False).size().rename(columns={"size": "no_historical_attempt_rows"})

    base = (
        universe.sort_values(["unitid", "academic_year"])
        .groupby("unitid", as_index=False)
        .agg(
            institution_name=("institution_name", lambda values: next((clean_text(v) for v in values if clean_text(v)), "")),
            sector=("sector", lambda values: next((clean_text(v) for v in values if clean_text(v)), "")),
            state=("state", lambda values: next((clean_text(v) for v in values if clean_text(v)), "")),
            target_year_rows=("academic_year", lambda values: len({int(v) for v in values.dropna()})),
            years_observed=("academic_year", lambda values: "; ".join(str(int(v)) for v in sorted(set(values.dropna())))),
            source_files=("source_file_path", lambda values: "; ".join(sorted({clean_text(v) for v in values if clean_text(v)})[:12])),
        )
    )
    metrics = [
        key_counts(discoveries, "valid_human_legacy", "valid_human_legacy_rows"),
        key_counts(
            discoveries,
            "prior_programmatic_accepted_needs_current_reverification",
            "prior_programmatic_accepted_rows",
        ),
        key_counts(
            attempts,
            "unreviewed_prior_programmatic_candidate_lead",
            "unreviewed_prior_programmatic_lead_rows",
        ),
        key_counts(attempts, "imported_llm_candidate_lead_overlay", "imported_llm_candidate_lead_rows"),
        key_counts(
            attempts,
            "unreviewed_human_legacy_candidate_lead",
            "unreviewed_human_legacy_candidate_lead_rows",
        ),
        key_counts(attempts, UNREVIEWED_LEAD_CLASSES, "unreviewed_candidate_lead_rows"),
        key_counts(attempts, "programmatic_attempt_no_valid_discovery", "failed_attempt_rows"),
        no_attempt_counts,
    ]
    out = base.copy()
    for metric in metrics:
        out = out.merge(metric, on="unitid", how="left")
    count_cols = [
        "valid_human_legacy_rows",
        "prior_programmatic_accepted_rows",
        "unreviewed_prior_programmatic_lead_rows",
        "imported_llm_candidate_lead_rows",
        "unreviewed_human_legacy_candidate_lead_rows",
        "unreviewed_candidate_lead_rows",
        "failed_attempt_rows",
        "no_historical_attempt_rows",
    ]
    for column in count_cols:
        out[column] = pd.to_numeric(out[column], errors="coerce").fillna(0).astype(int)

    def choose_bucket(row: pd.Series) -> str:
        if row["valid_human_legacy_rows"] > 0:
            return "valid_human_legacy"
        if row["prior_programmatic_accepted_rows"] > 0:
            return "prior_programmatic_accepted_needs_current_reverification"
        if row["unreviewed_prior_programmatic_lead_rows"] > 0:
            return "unreviewed_prior_programmatic_candidate_lead"
        if row["imported_llm_candidate_lead_rows"] > 0:
            return "imported_llm_candidate_lead_overlay"
        if row["unreviewed_human_legacy_candidate_lead_rows"] > 0:
            return "unreviewed_human_legacy_candidate_lead"
        if row["failed_attempt_rows"] > 0:
            return "programmatic_attempt_no_valid_discovery"
        return "no_historical_programmatic_attempt_found"

    next_steps = {
        "valid_human_legacy": "Start early: review human legacy evidence as transparent provenance and recover/review sources in current production lane.",
        "prior_programmatic_accepted_needs_current_reverification": "Use as source-family lead and benchmark memory; require current-run recovery and source review before ledger acceptance.",
        "unreviewed_prior_programmatic_candidate_lead": "Triage prior programmatic leads before spending time on fresh broad search.",
        "imported_llm_candidate_lead_overlay": "Use imported Claude/LLM leads as search hints only; require current-run recovery and source review.",
        "unreviewed_human_legacy_candidate_lead": "Review unselected human legacy URLs as candidate leads before treating them as evidence.",
        "programmatic_attempt_no_valid_discovery": "Use failed-attempt reasons to target source-family fixes or manual search.",
        "no_historical_programmatic_attempt_found": "Schedule after higher-yield buckets unless needed for sample balance.",
    }
    out["priority_bucket"] = out.apply(choose_bucket, axis=1)
    out["priority_rank"] = out["priority_bucket"].map(PRIORITY_ORDER).astype(int)
    out["recommended_next_step"] = out["priority_bucket"].map(next_steps)
    return out.sort_values(["priority_rank", "unitid"]).reset_index(drop=True)


def build_source_family_summary(discoveries: pd.DataFrame) -> pd.DataFrame:
    if discoveries.empty:
        return pd.DataFrame(columns=["evidence_class", "url_host", "source_type", "rows", "institutions", "years"])
    out = discoveries.copy()
    out["url_host"] = out["url"].map(url_host)
    grouped = (
        out.groupby(["evidence_class", "url_host", "source_type"], dropna=False)
        .agg(
            rows=("url", "size"),
            institutions=("unitid", lambda values: len(set(values.dropna()))),
            years=("academic_year", lambda values: len(set(values.dropna()))),
        )
        .reset_index()
    )
    return grouped.sort_values(["evidence_class", "rows"], ascending=[True, False])


def write_summary(
    path: Path,
    *,
    manifest: pd.DataFrame,
    file_classification: pd.DataFrame,
    attempts: pd.DataFrame,
    discoveries: pd.DataFrame,
    priority: pd.DataFrame,
    parse_exceptions: pd.DataFrame,
    run_started_at: str,
) -> None:
    bucket_counts = (
        priority["priority_bucket"].value_counts().rename_axis("priority_bucket").reset_index(name="institutions")
        if not priority.empty
        else pd.DataFrame(columns=["priority_bucket", "institutions"])
    )
    if not bucket_counts.empty:
        bucket_counts["priority_rank"] = bucket_counts["priority_bucket"].map(PRIORITY_ORDER)
        bucket_counts = bucket_counts.sort_values(["priority_rank", "priority_bucket"]).drop(columns=["priority_rank"])
    file_role_counts = (
        file_classification["file_role"].value_counts().rename_axis("file_role").reset_index(name="files")
        if not file_classification.empty
        else pd.DataFrame(columns=["file_role", "files"])
    )
    discovery_counts = (
        discoveries["evidence_class"].value_counts().rename_axis("evidence_class").reset_index(name="rows")
        if not discoveries.empty
        else pd.DataFrame(columns=["evidence_class", "rows"])
    )

    def md_table(frame: pd.DataFrame) -> list[str]:
        if frame.empty:
            return ["_No rows._"]
        values = frame.fillna("").astype(str)
        headers = list(values.columns)
        lines = [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join(["---"] * len(headers)) + " |",
        ]
        for _, row in values.iterrows():
            lines.append("| " + " | ".join(clean_text(row[column]).replace("|", "\\|") for column in headers) + " |")
        return lines

    lines = [
        "# Historical Inventory Summary",
        "",
        f"Status: inventory run completed at `{utc_now()}`.",
        f"Run started at: `{run_started_at}`.",
        "",
        "## Purpose",
        "",
        "This inventory maps historical Step 1 URL-discovery attempts, candidate leads, reviewed discoveries, failures, and benchmark evidence so future Step 1 production chunks can be ordered intelligently.",
        "",
        "This is planning evidence only. It is not a production chunk, source-ledger promotion step, clean no-legacy benchmark, or journal release.",
        "",
        "## Guardrail",
        "",
        "Prior programmatic evidence found here cannot promote a row into the source ledger by itself. A production row still needs current-run recovery and source review under the binding Step 1 standards.",
        "",
        "Hard gate:",
        "",
        "```text",
        "../.venv/bin/python -m pytest tests/test_step1_production_runner.py::test_clean_runner_rejects_historical_inventory_runtime_inputs",
        "```",
        "",
        "## Inventory Counts",
        "",
        f"- Files scanned: {len(manifest)}",
        f"- Files parsed into URL evidence: {int(file_classification['parse_status'].eq('parsed').sum()) if not file_classification.empty else 0}",
        f"- Files excluded or informational only: {int(file_classification['parse_status'].eq('excluded').sum()) if not file_classification.empty else 0}",
        f"- Parse exceptions: {len(parse_exceptions)}",
        f"- Normalized URL attempts: {len(attempts)}",
        f"- Normalized discoveries: {len(discoveries)}",
        f"- Institution priority rows: {len(priority)}",
        "",
        "## Priority Buckets",
        "",
        *md_table(bucket_counts),
        "",
        "## Discovery Evidence Classes",
        "",
        *md_table(discovery_counts),
        "",
        "## File Roles Scanned",
        "",
        *md_table(file_role_counts),
        "",
        "## Outputs",
        "",
        "Detailed audit outputs:",
        "",
        "```text",
        "artifacts/AUDIT_TRAILS/url_discovery_historical_inventory/source_file_manifest.csv",
        "artifacts/AUDIT_TRAILS/url_discovery_historical_inventory/file_level_classification.csv",
        "artifacts/AUDIT_TRAILS/url_discovery_historical_inventory/normalized_historical_url_attempts.csv",
        "artifacts/AUDIT_TRAILS/url_discovery_historical_inventory/normalized_historical_discoveries.csv",
        "artifacts/AUDIT_TRAILS/url_discovery_historical_inventory/institution_priority_buckets.csv",
        "artifacts/AUDIT_TRAILS/url_discovery_historical_inventory/source_family_summary.csv",
        "artifacts/AUDIT_TRAILS/url_discovery_historical_inventory/parse_exceptions.csv",
        "artifacts/AUDIT_TRAILS/url_discovery_historical_inventory/inventory_run_manifest.json",
        "```",
        "",
        "Human-facing copies:",
        "",
        "```text",
        "artifacts/PIPELINE_OUTPUTS/01_url_discovery/historical_inventory/HISTORICAL_INVENTORY_SUMMARY.md",
        "artifacts/PIPELINE_OUTPUTS/01_url_discovery/historical_inventory/institution_priority_buckets.csv",
        "artifacts/PIPELINE_OUTPUTS/01_url_discovery/historical_inventory/source_family_summary.csv",
        "```",
        "",
        "## Known Limitations",
        "",
        "- The target denominator is inferred from scanned target, handoff, ledger, benchmark, and legacy rows; it is not a final full production universe claim.",
        "- Unknown file shapes are recorded in the file-level classification rather than interpreted as evidence.",
        "- Claude/imported LLM suggestion-pool URLs and roots are counted as imported lead overlays, not prior programmatic discoveries, unless a later source-review artifact accepted or rejected them.",
        "- Historical accepted programmatic rows are source-family leads and benchmark memory, not production evidence.",
        "- Local absolute paths embedded inside old historical artifacts may appear as historical source references; inventory output paths created by this command are repo-relative.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_historical_inventory(
    repo_root: Path | str | None = None,
    *,
    audit_dir: Path | str | None = None,
    summary_dir: Path | str | None = None,
    scan_roots: tuple[Path, ...] = SCAN_ROOTS,
) -> HistoricalInventoryResult:
    root = Path(repo_root).resolve() if repo_root is not None else repo_root_from_cwd()
    audit = (Path(audit_dir) if audit_dir is not None else root / AUDIT_HISTORICAL_DIR).resolve()
    summary = (Path(summary_dir) if summary_dir is not None else root / PIPELINE_HISTORICAL_DIR).resolve()
    audit.mkdir(parents=True, exist_ok=True)
    summary.mkdir(parents=True, exist_ok=True)
    run_started_at = utc_now()

    files = discover_source_files(root, scan_roots)
    manifest_rows = [file_manifest_record(path, root) for path in files]
    manifest = pd.DataFrame(manifest_rows)
    attempts_rows: list[dict[str, object]] = []
    discovery_rows: list[dict[str, object]] = []
    target_rows: list[dict[str, object]] = []
    file_class_rows: list[dict[str, object]] = []
    exception_rows: list[dict[str, object]] = []

    for path, manifest_row in zip(files, manifest_rows):
        file_role = clean_text(manifest_row["file_role"])
        parse_status = "excluded"
        extracted_attempts = 0
        extracted_discoveries = 0
        exclusion_reason = ""
        try:
            if path.suffix.lower() == ".csv" and file_role not in {
                "manifest",
                "excluded_non_url_or_duplicate_artifact",
            }:
                file_sha = clean_text(manifest_row["sha256"])
                attempts, discoveries, targets = parse_known_csv(path, root, file_role, file_sha)
                attempts_rows.extend(attempts)
                discovery_rows.extend(discoveries)
                target_rows.extend(targets)
                extracted_attempts = len(attempts)
                extracted_discoveries = len(discoveries)
                parse_status = "parsed" if attempts or discoveries or targets else "excluded"
                if parse_status == "excluded":
                    exclusion_reason = "recognized CSV shape but no URL evidence rows found"
            else:
                exclusion_reason = "informational, manifest, or unrecognized artifact shape"
        except (OSError, ParserError, UnicodeDecodeError, ValueError) as exc:
            parse_status = "parse_exception"
            exclusion_reason = f"{type(exc).__name__}: {exc}"
            exception_rows.append(
                {
                    "source_file_path": relative_path(path, root),
                    "file_role": file_role,
                    "exception_type": type(exc).__name__,
                    "exception_message": str(exc),
                }
            )
        file_class_rows.append(
            {
                **manifest_row,
                "parse_status": parse_status,
                "extracted_attempt_rows": extracted_attempts,
                "extracted_discovery_rows": extracted_discoveries,
                "exclusion_reason": exclusion_reason,
            }
        )

    attempts = clean_normalized_frame(with_inventory_ids(attempts_rows, "inventory_row_id"), ATTEMPT_COLUMNS)
    discoveries = clean_normalized_frame(with_inventory_ids(discovery_rows, "inventory_discovery_id"), DISCOVERY_COLUMNS)
    targets = target_frame_from_rows(target_rows)
    priority = build_priority_buckets(targets, attempts, discoveries)
    family_summary = build_source_family_summary(discoveries)
    file_classification = pd.DataFrame(file_class_rows)
    parse_exceptions = pd.DataFrame(exception_rows)

    source_manifest_path = audit / "source_file_manifest.csv"
    file_class_path = audit / "file_level_classification.csv"
    attempts_path = audit / "normalized_historical_url_attempts.csv"
    discoveries_path = audit / "normalized_historical_discoveries.csv"
    priority_path = audit / "institution_priority_buckets.csv"
    family_path = audit / "source_family_summary.csv"
    exceptions_path = audit / "parse_exceptions.csv"
    run_manifest_path = audit / "inventory_run_manifest.json"
    summary_path = summary / "HISTORICAL_INVENTORY_SUMMARY.md"

    write_csv(manifest, source_manifest_path)
    write_csv(file_classification, file_class_path)
    write_csv(attempts, attempts_path, ATTEMPT_COLUMNS)
    write_csv(discoveries, discoveries_path, DISCOVERY_COLUMNS)
    write_csv(priority, priority_path)
    write_csv(family_summary, family_path)
    write_csv(parse_exceptions, exceptions_path)

    summary_priority_path = summary / "institution_priority_buckets.csv"
    summary_family_path = summary / "source_family_summary.csv"
    write_csv(priority, summary_priority_path)
    write_csv(family_summary, summary_family_path)

    run_manifest = {
        "created_at_utc": utc_now(),
        "run_started_at_utc": run_started_at,
        "builder": "course_policy.historical_url_inventory",
        "repo_root": str(root),
        "scan_roots": [path.as_posix() for path in scan_roots],
        "audit_outputs": {
            "source_file_manifest": relative_path(source_manifest_path, root),
            "file_level_classification": relative_path(file_class_path, root),
            "normalized_historical_url_attempts": relative_path(attempts_path, root),
            "normalized_historical_discoveries": relative_path(discoveries_path, root),
            "institution_priority_buckets": relative_path(priority_path, root),
            "source_family_summary": relative_path(family_path, root),
            "parse_exceptions": relative_path(exceptions_path, root),
        },
        "summary_outputs": {
            "summary": relative_path(summary_path, root),
            "institution_priority_buckets": relative_path(summary_priority_path, root),
            "source_family_summary": relative_path(summary_family_path, root),
        },
        "guardrail": (
            "Historical inventory is planning evidence only; clean Step 1 production runner "
            "must reject it as a runtime input."
        ),
        "counts": {
            "files_scanned": len(manifest),
            "attempt_rows": len(attempts),
            "discovery_rows": len(discoveries),
            "target_rows": len(targets.drop_duplicates(["unitid", "academic_year"])) if not targets.empty else 0,
            "institution_priority_rows": len(priority),
            "parse_exceptions": len(parse_exceptions),
        },
    }
    run_manifest_path.write_text(json.dumps(run_manifest, indent=2, sort_keys=True), encoding="utf-8")

    write_summary(
        summary_path,
        manifest=manifest,
        file_classification=file_classification,
        attempts=attempts,
        discoveries=discoveries,
        priority=priority,
        parse_exceptions=parse_exceptions,
        run_started_at=run_started_at,
    )

    return HistoricalInventoryResult(
        audit_dir=audit,
        summary_dir=summary,
        source_file_manifest=source_manifest_path,
        file_level_classification=file_class_path,
        attempts=attempts_path,
        discoveries=discoveries_path,
        institution_priority_buckets=priority_path,
        source_family_summary=family_path,
        parse_exceptions=exceptions_path,
        run_manifest=run_manifest_path,
        summary=summary_path,
        files_scanned=len(manifest),
        attempt_rows=len(attempts),
        discovery_rows=len(discoveries),
        target_rows=len(targets.drop_duplicates(["unitid", "academic_year"])) if not targets.empty else 0,
        institution_rows=len(priority),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=None, help="Repository root. Defaults to discovery from cwd.")
    parser.add_argument("--audit-dir", type=Path, default=None, help="Override audit output directory.")
    parser.add_argument("--summary-dir", type=Path, default=None, help="Override human-facing summary directory.")
    parser.add_argument(
        "--scan-root",
        type=Path,
        action="append",
        default=None,
        help=(
            "Artifact root to scan. May be repo-relative or absolute. Repeat to "
            "scan multiple parked legacy locations without moving them into the repo."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = build_historical_inventory(
        args.repo_root,
        audit_dir=args.audit_dir,
        summary_dir=args.summary_dir,
        scan_roots=tuple(args.scan_root) if args.scan_root else SCAN_ROOTS,
    )
    print(f"files_scanned={result.files_scanned}")
    print(f"attempt_rows={result.attempt_rows}")
    print(f"discovery_rows={result.discovery_rows}")
    print(f"target_rows={result.target_rows}")
    print(f"institution_priority_rows={result.institution_rows}")
    print(f"summary={result.summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
