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
    parser.add_argument("--scope", choices=["testing", "review", "project_management"], required=True)
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
