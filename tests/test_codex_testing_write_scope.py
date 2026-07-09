from __future__ import annotations

import csv
import fnmatch
import hashlib
import os
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_REL_PATH = "docs/replication_standards/protected_artifact_docs_manifest.csv"
PROTECTED_ARTIFACT_DOC_MANIFEST = (
    REPO_ROOT / MANIFEST_REL_PATH
)

PROTECTED_PATTERNS = [
    "README.md",
    "docs/**",
    "artifacts/PIPELINE_OUTPUTS/CURRENT_STATUS_AND_NEXT_STEPS.md",
    "artifacts/PIPELINE_OUTPUTS/START_HERE.md",
    "artifacts/PIPELINE_OUTPUTS/**/README.md",
    "artifacts/PIPELINE_OUTPUTS/**/process_reviews/**",
    "artifacts/AUDIT_TRAILS/START_HERE.md",
    "artifacts/PILOTS/**/README.md",
]

ALLOWED_TEST_REPORT_PATTERNS = [
    "artifacts/PILOTS/**/CHUNK_REPORT.md",
    "artifacts/PILOTS/**/RUN_REPORT.md",
    "artifacts/PILOTS/**/TEST_REPORT.md",
    "artifacts/PILOTS/**/RELEASE_REPORT.md",
    "artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_chunks/*/CHUNK_REPORT.md",
    "artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/*/RELEASE_REPORT.md",
]

ALLOWED_TEST_OUTPUT_PATTERNS = [
    "artifacts/PILOTS/*.csv",
    "artifacts/PILOTS/*.json",
    "artifacts/PILOTS/*.txt",
    "artifacts/PILOTS/**/*.csv",
    "artifacts/PILOTS/**/*.json",
    "artifacts/PILOTS/**/*.txt",
    "artifacts/PILOTS/**/CHUNK_REPORT.md",
    "artifacts/PILOTS/**/RUN_REPORT.md",
    "artifacts/PILOTS/**/TEST_REPORT.md",
    "artifacts/PILOTS/**/RELEASE_REPORT.md",
    "artifacts/PILOTS/**/source_evidence_cache/**",
    "artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_chunks/*/*.csv",
    "artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_chunks/*/*.json",
    "artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_chunks/*/*.txt",
    "artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_chunks/*/**/*.csv",
    "artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_chunks/*/**/*.json",
    "artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_chunks/*/**/*.txt",
    "artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_chunks/*/CHUNK_REPORT.md",
    "artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_chunks/*/RUN_REPORT.md",
    "artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_chunks/*/TEST_REPORT.md",
    "artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_chunks/*/**/CHUNK_REPORT.md",
    "artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_chunks/*/**/RUN_REPORT.md",
    "artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_chunks/*/**/TEST_REPORT.md",
    "artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_chunks/*/**/source_evidence_cache/**",
    "artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/*/*.csv",
    "artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/*/*.json",
    "artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/*/*.txt",
    "artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/*/**/*.csv",
    "artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/*/**/*.json",
    "artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/*/**/*.txt",
    "artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/*/RELEASE_REPORT.md",
    "artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/*/**/RELEASE_REPORT.md",
    "artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_releases/*/**/source_evidence_cache/**",
]

REVIEW_DOC_PATTERNS = [
    "artifacts/PIPELINE_OUTPUTS/**/process_reviews/**",
]

INTEGRATION_CODE_PATTERNS = [
    "src/course_policy/codex_scope_guard.py",
    "src/course_policy/step1_production_runner.py",
    "src/course_policy/step1_production_input_builder.py",
    "src/course_policy/step1_proof_to_scale_url_production.py",
    "src/course_policy/step1_attrition_audit.py",
    "src/course_policy/step1_post_repair_closure_audit.py",
    "src/course_policy/production_release_url_stage.py",
    "src/course_policy/production_quality_gate.py",
    "src/course_policy/production_namespace.py",
    "src/course_policy/production_streams.py",
    "tests/test_codex_testing_write_scope.py",
    "tests/test_step1_*.py",
    "tests/test_production_*.py",
]

INTEGRATION_OUTPUT_PATTERNS = [
    "artifacts/PIPELINE_OUTPUTS/01_url_discovery/reports/step1_attrition_audit_001_040/*.csv",
    "artifacts/PIPELINE_OUTPUTS/01_url_discovery/reports/step1_attrition_audit_001_040/*.json",
    "artifacts/PIPELINE_OUTPUTS/01_url_discovery/reports/step1_attrition_audit_001_040/STEP1_ATTRITION_AUDIT_REPORT.md",
    "artifacts/PIPELINE_OUTPUTS/01_url_discovery/reports/step1_post_repair_closure_audit_001/*.csv",
    "artifacts/PIPELINE_OUTPUTS/01_url_discovery/reports/step1_post_repair_closure_audit_001/*.json",
    "artifacts/PIPELINE_OUTPUTS/01_url_discovery/reports/step1_post_repair_closure_audit_001/STEP1_POST_REPAIR_CLOSURE_AUDIT_REPORT.md",
]

BUILD_CODE_PATTERNS = [
    "src/course_policy/audit_legacy.py",
    "src/course_policy/benchmark_protocol.py",
    "src/course_policy/batch2_*.py",
    "src/course_policy/batch3_discovery.py",
    "src/course_policy/batch4_discovery.py",
    "src/course_policy/catalog_*.py",
    "src/course_policy/clean_no_legacy_benchmark.py",
    "src/course_policy/current_process_trace.py",
    "src/course_policy/fresh_discovery.py",
    "src/course_policy/gfdatafull_panel_benchmark.py",
    "src/course_policy/institution_universe.py",
    "src/course_policy/legacy_*.py",
    "src/course_policy/manual_catalog_search_audit.py",
    "src/course_policy/ocr_visual_review.py",
    "src/course_policy/phase3_review_packet.py",
    "src/course_policy/pilot_status_summary.py",
    "src/course_policy/production_*.py",
    "src/course_policy/public_fresh_discovery*.py",
    "src/course_policy/review_ready_adjustments.py",
    "src/course_policy/reviewed_root_expansion.py",
    "src/course_policy/source_root_plan.py",
    "src/course_policy/spotcheck_workbook.py",
    "src/course_policy/step1_*.py",
    "src/course_policy/strict_*.py",
    "tests/test_audit_legacy.py",
    "tests/test_benchmark_protocol.py",
    "tests/test_batch2_*.py",
    "tests/test_batch3_discovery.py",
    "tests/test_batch4_discovery.py",
    "tests/test_catalog_*.py",
    "tests/test_clean_no_legacy_benchmark.py",
    "tests/test_current_process_trace.py",
    "tests/test_fresh_discovery.py",
    "tests/test_gfdatafull_panel_benchmark.py",
    "tests/test_institution_universe.py",
    "tests/test_legacy_*.py",
    "tests/test_manual_catalog_search_audit.py",
    "tests/test_ocr_visual_review.py",
    "tests/test_phase3_review_packet.py",
    "tests/test_pilot_status_summary.py",
    "tests/test_production_*.py",
    "tests/test_public_fresh_discovery*.py",
    "tests/test_review_ready_adjustments.py",
    "tests/test_reviewed_root_expansion.py",
    "tests/test_source_root_plan.py",
    "tests/test_spotcheck_workbook.py",
    "tests/test_step1_*.py",
    "tests/test_strict_*.py",
]

BUILD_OUTPUT_PATTERNS = [
    *ALLOWED_TEST_OUTPUT_PATTERNS,
    "artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_chunks/*/BUILD_LOG.md",
    "artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_chunks/*/SUPERVISOR_RUN_REPORT.md",
    "artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_chunks/*/**/BUILD_LOG.md",
    "artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_chunks/*/**/SUPERVISOR_RUN_REPORT.md",
]

PROJECT_MANAGEMENT_DOC_PATTERNS = [
    "README.md",
    "docs/**",
    "artifacts/PIPELINE_OUTPUTS/CURRENT_STATUS_AND_NEXT_STEPS.md",
    "artifacts/PIPELINE_OUTPUTS/START_HERE.md",
    "artifacts/PIPELINE_OUTPUTS/**/README.md",
    "artifacts/AUDIT_TRAILS/START_HERE.md",
    "artifacts/PILOTS/**/README.md",
]

PROJECT_MANAGEMENT_ARTIFACT_DOC_PATTERNS = [
    "artifacts/PIPELINE_OUTPUTS/CURRENT_STATUS_AND_NEXT_STEPS.md",
    "artifacts/PIPELINE_OUTPUTS/START_HERE.md",
    "artifacts/PIPELINE_OUTPUTS/**/README.md",
    "artifacts/AUDIT_TRAILS/START_HERE.md",
    "artifacts/PILOTS/**/README.md",
]


def _git_lines(*args: str) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def _changed_paths() -> set[str]:
    tracked = _git_lines("diff", "--name-only", "--diff-filter=ACMRTUXB", "HEAD")
    untracked = _git_lines("ls-files", "--others", "--exclude-standard")
    return set(tracked + untracked)


def _git_show(path: str) -> str | None:
    result = subprocess.run(
        ["git", "show", f"HEAD:{path}"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_manifest_text(text: str) -> dict[str, str]:
    rows = csv.DictReader(text.splitlines())
    return {row["path"]: row["sha256"] for row in rows}


def _read_working_manifest() -> dict[str, str]:
    with PROTECTED_ARTIFACT_DOC_MANIFEST.open(newline="") as handle:
        return {row["path"]: row["sha256"] for row in csv.DictReader(handle)}


def _manifest_row_changes() -> list[str]:
    head_text = _git_show(MANIFEST_REL_PATH)
    if head_text is None:
        return []

    head_manifest = _read_manifest_text(head_text)
    working_manifest = _read_working_manifest()
    return sorted(
        path
        for path in set(head_manifest) | set(working_manifest)
        if head_manifest.get(path) != working_manifest.get(path)
    )


def _protected_artifact_doc_mismatches() -> list[str]:
    rows = _read_working_manifest()

    mismatches: list[str] = []
    for rel_path, expected in rows.items():
        path = REPO_ROOT / rel_path
        if not path.exists():
            mismatches.append(f"{rel_path} is missing; expected sha256 {expected}")
            continue
        actual = _sha256(path)
        if actual != expected:
            mismatches.append(
                f"{rel_path} sha256 changed: expected {expected}, found {actual}"
            )
    return mismatches


def _matches_any(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def _scope_path_violations(allowed_patterns: list[str]) -> list[str]:
    return [
        path
        for path in sorted(_changed_paths())
        if not _matches_any(path, allowed_patterns)
    ]


def _manifest_row_violations(allowed_patterns: list[str]) -> list[str]:
    return [
        f"{MANIFEST_REL_PATH} changed protected row {path}"
        for path in _manifest_row_changes()
        if not _matches_any(path, allowed_patterns)
    ]


def test_write_scope_patterns_protect_status_and_allow_run_local_reports() -> None:
    assert _matches_any(
        "artifacts/PIPELINE_OUTPUTS/CURRENT_STATUS_AND_NEXT_STEPS.md",
        PROTECTED_PATTERNS,
    )
    assert _matches_any(
        "artifacts/PIPELINE_OUTPUTS/01_url_discovery/process_reviews/review.md",
        PROTECTED_PATTERNS,
    )
    assert _matches_any(
        "artifacts/PILOTS/url_discovery/example/CHUNK_REPORT.md",
        ALLOWED_TEST_REPORT_PATTERNS,
    )
    assert not _matches_any(
        "artifacts/PILOTS/url_discovery/README.md",
        ALLOWED_TEST_REPORT_PATTERNS,
    )
    assert _matches_any(
        "artifacts/PIPELINE_OUTPUTS/01_url_discovery/process_reviews/review.md",
        REVIEW_DOC_PATTERNS,
    )
    assert _matches_any(
        "artifacts/PIPELINE_OUTPUTS/CURRENT_STATUS_AND_NEXT_STEPS.md",
        PROJECT_MANAGEMENT_ARTIFACT_DOC_PATTERNS,
    )
    assert not _matches_any(
        "artifacts/PIPELINE_OUTPUTS/01_url_discovery/process_reviews/review.md",
        PROJECT_MANAGEMENT_ARTIFACT_DOC_PATTERNS,
    )
    assert _matches_any(
        "src/course_policy/step1_production_runner.py",
        INTEGRATION_CODE_PATTERNS,
    )
    assert _matches_any(
        "src/course_policy/step1_attrition_audit.py",
        INTEGRATION_CODE_PATTERNS,
    )
    assert _matches_any(
        "src/course_policy/step1_post_repair_closure_audit.py",
        INTEGRATION_CODE_PATTERNS,
    )
    assert _matches_any(
        "src/course_policy/codex_scope_guard.py",
        INTEGRATION_CODE_PATTERNS,
    )
    assert _matches_any(
        "tests/test_codex_testing_write_scope.py",
        INTEGRATION_CODE_PATTERNS,
    )
    assert _matches_any(
        "tests/test_production_release_url_stage.py",
        INTEGRATION_CODE_PATTERNS,
    )
    assert _matches_any(
        "artifacts/PIPELINE_OUTPUTS/01_url_discovery/reports/step1_attrition_audit_001_040/institution_attrition_ledger.csv",
        INTEGRATION_OUTPUT_PATTERNS,
    )
    assert _matches_any(
        "artifacts/PIPELINE_OUTPUTS/01_url_discovery/reports/step1_post_repair_closure_audit_001/institution_closure_ledger.csv",
        INTEGRATION_OUTPUT_PATTERNS,
    )
    assert _matches_any(
        "artifacts/PIPELINE_OUTPUTS/01_url_discovery/reports/step1_post_repair_closure_audit_001/STEP1_POST_REPAIR_CLOSURE_AUDIT_REPORT.md",
        INTEGRATION_OUTPUT_PATTERNS,
    )
    assert not _matches_any(
        "artifacts/PIPELINE_OUTPUTS/01_url_discovery/reports/some_other_audit/report.csv",
        INTEGRATION_OUTPUT_PATTERNS,
    )
    assert not _matches_any(
        "artifacts/PIPELINE_OUTPUTS/CURRENT_STATUS_AND_NEXT_STEPS.md",
        INTEGRATION_CODE_PATTERNS,
    )
    assert _matches_any(
        "src/course_policy/public_fresh_discovery.py",
        BUILD_CODE_PATTERNS,
    )
    assert _matches_any(
        "tests/test_public_fresh_discovery.py",
        BUILD_CODE_PATTERNS,
    )
    assert not _matches_any(
        "src/course_policy/policy_classification_batch.py",
        BUILD_CODE_PATTERNS,
    )
    assert not _matches_any(
        "src/course_policy/ai_config.py",
        BUILD_CODE_PATTERNS,
    )
    assert not _matches_any(
        "src/course_policy/codex_scope_guard.py",
        BUILD_CODE_PATTERNS,
    )
    assert _matches_any(
        "artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_chunks/example/BUILD_LOG.md",
        BUILD_OUTPUT_PATTERNS,
    )


def test_protected_ignored_artifact_docs_match_manifest() -> None:
    mismatches = _protected_artifact_doc_mismatches()

    assert not mismatches, (
        "Protected artifact docs are ignored by Git, so they are locked by "
        "docs/replication_standards/protected_artifact_docs_manifest.csv. "
        "Testing streams must not edit these files. Review streams may update "
        "only process-review files plus their manifest rows. "
        "Project-management streams may update only front-door/status docs plus "
        "their manifest rows. Mismatches:\n"
        + "\n".join(f"- {mismatch}" for mismatch in mismatches)
    )


def test_codex_stream_scope_limits_changed_files() -> None:
    scope = os.environ.get("CODEX_STREAM_SCOPE")
    if scope is None:
        pytest.skip(
            "Set CODEX_STREAM_SCOPE=testing, review, build, integration, or project_management "
            "to enforce stream write scope."
        )

    if scope == "testing":
        violations = _scope_path_violations(ALLOWED_TEST_OUTPUT_PATTERNS)
        violations.extend(_protected_artifact_doc_mismatches())
        message = (
            "Testing/drill/smoke/mini-batch streams may edit only run-local "
            "test output. Put requested doc or review changes in the run-local "
            "report and ask for a separate review or project-management edit."
        )
    elif scope == "review":
        allowed = [*REVIEW_DOC_PATTERNS, MANIFEST_REL_PATH]
        violations = _scope_path_violations(allowed)
        violations.extend(_protected_artifact_doc_mismatches())
        violations.extend(_manifest_row_violations(REVIEW_DOC_PATTERNS))
        message = (
            "Review streams may edit only the relevant process-review file and "
            "the manifest row for that review file. They may not update current "
            "status, front-door docs, standards, or generated test output."
        )
    elif scope == "build":
        allowed = [*BUILD_CODE_PATTERNS, *BUILD_OUTPUT_PATTERNS]
        violations = _scope_path_violations(allowed)
        violations.extend(_protected_artifact_doc_mismatches())
        violations.extend(_manifest_row_violations([]))
        message = (
            "Build streams may edit Step 1 URL-discovery source/tests and "
            "run-local generated output only. They may not edit status, "
            "reviews, standards, front-door docs, or downstream classification files."
        )
    elif scope == "integration":
        allowed = [*INTEGRATION_CODE_PATTERNS, *INTEGRATION_OUTPUT_PATTERNS]
        violations = _scope_path_violations(allowed)
        violations.extend(_protected_artifact_doc_mismatches())
        violations.extend(_manifest_row_violations([]))
        message = (
            "Integration streams may edit only the Step 1 production-runner/"
            "release-packager/audit source files, matching tests, and explicitly "
            "approved audit outputs. They may not edit status, reviews, standards, "
            "arbitrary generated output, or unrelated discovery/classification "
            "modules."
        )
    elif scope == "project_management":
        allowed = [*PROJECT_MANAGEMENT_DOC_PATTERNS, MANIFEST_REL_PATH]
        violations = _scope_path_violations(allowed)
        violations.extend(_protected_artifact_doc_mismatches())
        violations.extend(
            _manifest_row_violations(PROJECT_MANAGEMENT_ARTIFACT_DOC_PATTERNS)
        )
        message = (
            "Project-management streams may update planning/status/front-door "
            "docs, but not generated test output or process-review files."
        )
    else:
        raise AssertionError(
            "CODEX_STREAM_SCOPE must be testing, review, build, integration, or project_management; "
            f"got {scope!r}."
        )

    assert not violations, (
        message
        + " Violations:\n"
        + "\n".join(f"- {path}" for path in violations)
    )
