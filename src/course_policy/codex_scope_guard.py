from __future__ import annotations

import argparse
import csv
import fnmatch
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_REL_PATH = "docs/replication_standards/protected_artifact_docs_manifest.csv"

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
    "src/course_policy/step1_production_runner.py",
    "src/course_policy/step1_production_input_builder.py",
    "src/course_policy/step1_proof_to_scale_url_production.py",
    "src/course_policy/step1_attrition_audit.py",
    "src/course_policy/production_release_url_stage.py",
    "src/course_policy/production_quality_gate.py",
    "src/course_policy/production_namespace.py",
    "src/course_policy/production_streams.py",
    "tests/test_step1_*.py",
    "tests/test_production_*.py",
]

INTEGRATION_OUTPUT_PATTERNS = [
    "artifacts/PIPELINE_OUTPUTS/01_url_discovery/reports/step1_attrition_audit_001_040/*.csv",
    "artifacts/PIPELINE_OUTPUTS/01_url_discovery/reports/step1_attrition_audit_001_040/*.json",
    "artifacts/PIPELINE_OUTPUTS/01_url_discovery/reports/step1_attrition_audit_001_040/STEP1_ATTRITION_AUDIT_REPORT.md",
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


def _run_git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout


def _matches_any(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def _sha256(rel_path: str) -> str | None:
    path = REPO_ROOT / rel_path
    if not path.exists() or not path.is_file():
        return None

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_status_paths() -> set[str]:
    output = _run_git("status", "--porcelain=v1", "--untracked-files=all")
    paths: set[str] = set()
    for line in output.splitlines():
        if not line:
            continue
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", maxsplit=1)[1]
        paths.add(path)
    return paths


def _read_manifest() -> dict[str, str]:
    manifest = REPO_ROOT / MANIFEST_REL_PATH
    if not manifest.exists():
        return {}
    with manifest.open(newline="") as handle:
        return {row["path"]: row["sha256"] for row in csv.DictReader(handle)}


def _snapshot() -> dict[str, Any]:
    status_paths = sorted(_git_status_paths() | {MANIFEST_REL_PATH})
    protected_docs = _read_manifest()
    return {
        "status_hashes": {path: _sha256(path) for path in status_paths},
        "protected_doc_hashes": {
            path: _sha256(path) for path in sorted(protected_docs)
        },
        "manifest_rows": protected_docs,
    }


def _changed_hash_paths(before: dict[str, str | None], after: dict[str, str | None]) -> list[str]:
    return sorted(
        path
        for path in set(before) | set(after)
        if before.get(path) != after.get(path)
    )


def _current_status_hashes(baseline: dict[str, Any]) -> dict[str, str | None]:
    paths = set(baseline["status_hashes"]) | _git_status_paths() | {MANIFEST_REL_PATH}
    return {path: _sha256(path) for path in sorted(paths)}


def _current_protected_hashes(baseline: dict[str, Any]) -> dict[str, str | None]:
    paths = set(baseline["protected_doc_hashes"]) | set(_read_manifest())
    return {path: _sha256(path) for path in sorted(paths)}


def _manifest_row_changes(baseline: dict[str, Any]) -> list[str]:
    before = baseline["manifest_rows"]
    after = _read_manifest()
    return sorted(
        path
        for path in set(before) | set(after)
        if before.get(path) != after.get(path)
    )


def _allowed_for_scope(scope: str, path: str) -> bool:
    if scope == "testing":
        return _matches_any(path, ALLOWED_TEST_OUTPUT_PATTERNS)
    if scope == "review":
        return path == MANIFEST_REL_PATH or _matches_any(path, REVIEW_DOC_PATTERNS)
    if scope == "build":
        return _matches_any(path, BUILD_CODE_PATTERNS) or _matches_any(
            path, BUILD_OUTPUT_PATTERNS
        )
    if scope == "integration":
        return _matches_any(path, INTEGRATION_CODE_PATTERNS) or _matches_any(
            path, INTEGRATION_OUTPUT_PATTERNS
        )
    if scope == "project_management":
        return path == MANIFEST_REL_PATH or _matches_any(
            path, PROJECT_MANAGEMENT_DOC_PATTERNS
        )
    raise ValueError(f"Unknown scope: {scope}")


def _allowed_manifest_row_for_scope(scope: str, path: str) -> bool:
    if scope == "testing":
        return False
    if scope == "review":
        return _matches_any(path, REVIEW_DOC_PATTERNS)
    if scope == "build":
        return False
    if scope == "integration":
        return False
    if scope == "project_management":
        return _matches_any(path, PROJECT_MANAGEMENT_ARTIFACT_DOC_PATTERNS)
    raise ValueError(f"Unknown scope: {scope}")


def _scope_message(scope: str) -> str:
    if scope == "testing":
        return (
            "Testing streams may edit only run-local generated output. "
            "They must not edit current status, README/START_HERE, standards, "
            "process reviews, or the protected-doc manifest."
        )
    if scope == "review":
        return (
            "Review streams may edit only the relevant process-review file and "
            "the manifest row for that review file."
        )
    if scope == "build":
        return (
            "Build streams may edit Step 1 URL-discovery source/tests and "
            "run-local generated output only. They must not edit status, "
            "reviews, standards docs, front-door docs, or the protected-doc "
            "manifest."
        )
    if scope == "integration":
        return (
            "Integration streams may edit only the Step 1 production-runner/"
            "release-packager/audit source files, matching tests, and explicitly "
            "approved audit outputs. They must not edit status, reviews, "
            "standards docs, arbitrary generated outputs, or unrelated "
            "discovery/classification modules."
        )
    if scope == "project_management":
        return (
            "Project-management streams may edit planning/status/front-door docs "
            "and their manifest rows, but not generated test output or process "
            "reviews."
        )
    raise ValueError(f"Unknown scope: {scope}")


def _repo_relative(path: Path) -> str | None:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return None


def init_baseline(scope: str, baseline_path: Path) -> None:
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "scope": scope,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(REPO_ROOT),
        **_snapshot(),
    }
    baseline_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {scope} scope baseline: {baseline_path}")


def check_baseline(scope: str, baseline_path: Path) -> int:
    baseline = json.loads(baseline_path.read_text())
    if baseline["scope"] != scope:
        print(
            f"Baseline scope is {baseline['scope']!r}, but check scope is {scope!r}.",
            file=sys.stderr,
        )
        return 2

    current_status = _current_status_hashes(baseline)
    changed_paths = _changed_hash_paths(baseline["status_hashes"], current_status)
    protected_changes = _changed_hash_paths(
        baseline["protected_doc_hashes"], _current_protected_hashes(baseline)
    )
    manifest_row_changes = _manifest_row_changes(baseline)

    violations: list[str] = []
    for path in changed_paths:
        if path == _repo_relative(baseline_path):
            continue
        if not _allowed_for_scope(scope, path):
            violations.append(f"{path} changed outside {scope} scope")

    for path in protected_changes:
        if not _allowed_for_scope(scope, path):
            violations.append(f"{path} protected-doc hash changed outside {scope} scope")

    for path in manifest_row_changes:
        if not _allowed_manifest_row_for_scope(scope, path):
            violations.append(f"{MANIFEST_REL_PATH} changed forbidden row {path}")

    if violations:
        print(_scope_message(scope), file=sys.stderr)
        print("Scope violations:", file=sys.stderr)
        for violation in violations:
            print(f"- {violation}", file=sys.stderr)
        return 1

    print(f"{scope} scope check passed for baseline: {baseline_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["init", "check"])
    parser.add_argument(
        "--scope",
        choices=["testing", "review", "build", "integration", "project_management"],
        required=True,
    )
    parser.add_argument("--baseline", required=True, type=Path)
    args = parser.parse_args(argv)

    baseline = args.baseline
    if not baseline.is_absolute():
        baseline = REPO_ROOT / baseline

    if args.command == "init":
        init_baseline(args.scope, baseline)
        return 0
    return check_baseline(args.scope, baseline)


if __name__ == "__main__":
    raise SystemExit(main())
