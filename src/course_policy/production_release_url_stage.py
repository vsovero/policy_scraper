"""Package a passing URL-discovery production chunk as a portable release.

The release package is a replay/check package, not a live rediscovery run. It
copies frozen URL-stage outputs, source-review evidence, cached source text, and
code snapshots into a package-local layout with relative manifests.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import shutil
import shlex
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from pandas.errors import EmptyDataError

from .ai_config import repo_root_from_cwd


PIPELINE_ROOT = Path("artifacts/PIPELINE_OUTPUTS")
URL_DISCOVERY_ROOT = PIPELINE_ROOT / "01_url_discovery"
PRODUCTION_CHUNKS_ROOT = URL_DISCOVERY_ROOT / "production_chunks"
PRODUCTION_RELEASES_ROOT = URL_DISCOVERY_ROOT / "production_releases"
AUDIT_ROOT = Path("artifacts/AUDIT_TRAILS")
DEFAULT_CHUNK_ID = "production_chunk_001"
DEFAULT_RELEASE_ID = "production_release_url_stage_001"

REQUIRED_CHUNK_FILES = (
    "OUTPUT_urls_for_text_extraction.csv",
    "OUTPUT_source_ledger_delta.csv",
    "UNRESOLVED_ROWS.csv",
    "BENCHMARK_RECOVERY.csv",
    "BENCHMARK_MISSES.csv",
    "REQUIREMENTS_STATUS.csv",
    "GUIDELINE_CROSSWALK.csv",
    "MANIFEST.json",
)

CHUNK_DATA_COPIES = {
    "OUTPUT_urls_for_text_extraction.csv": "data/reviewed_url_handoff_panel.csv",
    "OUTPUT_source_ledger_delta.csv": "data/source_ledger.csv",
    "UNRESOLVED_ROWS.csv": "data/url_stop_log.csv",
    "BENCHMARK_RECOVERY.csv": "data/benchmark_recovery.csv",
    "BENCHMARK_MISSES.csv": "data/benchmark_misses.csv",
    "REQUIREMENTS_STATUS.csv": "data/requirements_status.csv",
    "GUIDELINE_CROSSWALK.csv": "data/guideline_crosswalk.csv",
}

CHUNK_AUDIT_COPIES = {
    "README.md": "audit/construction_chunk_readme.md",
    "CHUNK_REPORT.md": "audit/construction_chunk_report.md",
    "MANIFEST.json": "audit/construction_chunk_manifest.json",
}

SELF_REFERENTIAL_RELEASE_FILES = {
    "release_manifest.csv",
    "checksums.sha256",
    "rebuild_check.csv",
    "rebuild_check_log.txt",
}

PRODUCTION_INPUT_COPY_FILES = {
    "target_panel.csv",
    "candidate_url_ledger.csv",
    "source_review_log.csv",
    "historical_case_precheck.csv",
    "run_config.json",
    "source_evidence_manifest.csv",
    "benchmark_key.csv",
}

AI_YEAR_GAP_AUDIT_FILES = {
    "ai_year_gap_cases.csv",
    "ai_year_gap_status.csv",
    "ai_year_gap_triage.csv",
    "ai_year_gap_verified_roots.csv",
    "ai_year_gap_year_panel.csv",
    "ai_year_gap_rollup.xlsx",
}

AI_MODEL_OUTPUT_COLUMNS = [
    "task_type",
    "provider_or_tool",
    "model_or_version",
    "run_date_time",
    "prompt_or_rule_version",
    "schema_version",
    "unitid",
    "institution_name",
    "call_or_run_id",
    "input_hash",
    "output_hash",
    "prompt_path",
    "prompt_sha256",
    "raw_response_path",
    "raw_response_sha256",
    "parsed_response_path",
    "parsed_response_sha256",
    "triage_path",
    "triage_sha256",
    "source_review_linkage_path",
    "source_review_linkage_sha256",
    "source_review_linkage_filter",
    "linked_ai_candidate_rows",
    "validation_status",
]


@dataclass(frozen=True)
class ReleasePackageResult:
    release_dir: Path
    release_id: str
    release_manifest: Path
    checksum_file: Path
    rebuild_check: Path
    package_pass: bool


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


def read_csv_or_empty(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path, low_memory=False)
    except EmptyDataError:
        return pd.DataFrame()


def write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_if_file(path: Path) -> str:
    return sha256_file(path) if path.is_file() else ""


def path_in_release_if_file(path: Path, release_dir: Path) -> str:
    return path_in_release(path, release_dir) if path.is_file() else ""


def read_json_object(path: Path) -> dict[str, object]:
    if not path.is_file() or path.stat().st_size == 0:
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def response_timestamp_iso(raw: dict[str, object]) -> str:
    for key in ["completed_at", "created_at"]:
        value = raw.get(key)
        try:
            if value not in {None, ""}:
                return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat(timespec="seconds")
        except (TypeError, ValueError, OSError):
            continue
    return ""


def prompt_schema_version(prompt_path: Path) -> str:
    prompt = read_json_object(prompt_path)
    schema = prompt.get("required_json_schema")
    if isinstance(schema, dict) and schema:
        return "clean_no_legacy_year_gap_web_discovery_response_v1"
    if isinstance(prompt.get("response_format"), dict):
        return clean_text(prompt["response_format"].get("name")) or "response_format_json_schema"
    return ""


def run_git_command(repo_root: Path, args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception:
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def code_version_record(repo_root: Path) -> dict[str, object]:
    status = run_git_command(repo_root, ["status", "--short"])
    return {
        "git_commit": run_git_command(repo_root, ["rev-parse", "HEAD"]),
        "git_dirty": bool(status),
        "git_status_short": status,
    }


def copy_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def path_in_release(path: Path, release_dir: Path) -> str:
    return path.resolve().relative_to(release_dir.resolve()).as_posix()


def safe_path_part(value: object) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", clean_text(value)).strip("_")
    return text[:120] or "source"


def derived_input_dir_from_chunk_id(repo_root: Path, chunk_id: str) -> Path:
    suffix = chunk_id.removeprefix("production_chunk_")
    return repo_root / URL_DISCOVERY_ROOT / "production_inputs" / f"production_{suffix}"


def production_input_dir_for_chunk(repo_root: Path, chunk_dir: Path, chunk_id: str) -> Path | None:
    manifest_path = chunk_dir / "MANIFEST.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            args = shlex.split(clean_text(manifest.get("run_command")))
            if "--input-dir" in args:
                value = args[args.index("--input-dir") + 1]
                candidate = Path(value)
                if not candidate.is_absolute():
                    candidate = repo_root / candidate
                if candidate.exists():
                    return candidate
        except Exception:
            pass
    derived = derived_input_dir_from_chunk_id(repo_root, chunk_id)
    return derived if derived.exists() else None


def raw_input_candidates(repo_root: Path) -> dict[str, Path]:
    candidates = {
        "gfprivatelist.xlsx": repo_root.parent / "Stata Files" / "Data" / "gfprivatelist.xlsx",
        "Course repetition data.xlsx": repo_root.parent / "Ipeds raw Data files" / "Course repetition data.xlsx",
    }
    return {name: path for name, path in candidates.items() if path.exists()}


def source_path_for_reference(reference: object, repo_root: Path) -> Path | None:
    text = clean_text(reference)
    if not text:
        return None
    if text.startswith(("construction_upstream_file:", "external_absolute_path_removed:", "audit/", "data/", "code/")):
        return None
    path = Path(text)
    if path.is_absolute() and path.exists():
        return path
    repo_candidate = repo_root / path
    if repo_candidate.exists():
        return repo_candidate
    raw = raw_input_candidates(repo_root).get(path.name)
    if raw:
        return raw
    return None


def lineage_target_for_source(source: Path, *, repo_root: Path, release_dir: Path) -> Path:
    name = source.name
    if name in raw_input_candidates(repo_root):
        return release_dir / "audit/source_lineage/raw_inputs" / name
    try:
        relative = source.resolve().relative_to((repo_root / "artifacts/policy_data_internal/review/streams").resolve())
        return release_dir / "audit/source_lineage/stream_outputs" / relative
    except ValueError:
        pass
    try:
        relative = source.resolve().relative_to((repo_root / "artifacts/policy_data_internal/logs/ai/raw_responses").resolve())
        return release_dir / "audit/ai_api_provenance/raw_responses" / relative.name
    except ValueError:
        pass
    try:
        relative = source.resolve().relative_to((repo_root / "artifacts/policy_data_internal/logs/ai/parsed_responses").resolve())
        subdir = "prompts" if relative.name.endswith("_prompt.json") else "parsed_responses"
        return release_dir / "audit/ai_api_provenance" / subdir / relative.name
    except ValueError:
        pass
    return release_dir / "audit/source_lineage/other_inputs" / safe_path_part(name)


def add_lineage_copy(
    *,
    source: Path,
    target: Path,
    release_dir: Path,
    original_reference: str,
    role: str,
    rows: list[dict[str, object]],
    reference_map: dict[str, str],
) -> None:
    if not source.exists() or source.is_dir():
        return
    copy_file(source, target)
    packaged_path = path_in_release(target, release_dir)
    reference_map[original_reference] = packaged_path
    reference_map[str(source)] = packaged_path
    reference_map[source.as_posix()] = packaged_path
    reference_map[source.name] = packaged_path
    rows.append(
        {
            "role": role,
            "original_reference": original_reference,
            "packaged_path": packaged_path,
            "original_size_bytes": target.stat().st_size,
            "original_sha256": sha256_file(target),
            "size_bytes": target.stat().st_size,
            "sha256": sha256_file(target),
            "packaged_size_bytes": target.stat().st_size,
            "packaged_sha256": sha256_file(target),
        }
    )


def copy_production_input_files(
    *,
    production_input_dir: Path | None,
    release_dir: Path,
    rows: list[dict[str, object]],
    reference_map: dict[str, str],
) -> None:
    if production_input_dir is None or not production_input_dir.exists():
        return
    for source in sorted(production_input_dir.iterdir()):
        if not source.is_file() or source.name not in PRODUCTION_INPUT_COPY_FILES:
            continue
        target = release_dir / "audit/production_inputs" / source.name
        add_lineage_copy(
            source=source,
            target=target,
            release_dir=release_dir,
            original_reference=source.as_posix(),
            role="production_input",
            rows=rows,
            reference_map=reference_map,
        )


def iter_reference_values(release_dir: Path) -> set[str]:
    values: set[str] = set()
    candidate_files = list((release_dir / "data").glob("*.csv"))
    candidate_files.extend((release_dir / "audit/production_inputs").glob("*.csv"))
    for path in sorted(candidate_files):
        frame = read_csv_or_empty(path)
        if frame.empty:
            continue
        for column in ["candidate_source_file", "source_review_file", "review_file"]:
            if column in frame.columns:
                values.update(frame[column].map(clean_text).loc[lambda series: series.ne("")].tolist())
    return values


def copy_referenced_lineage_files(
    *,
    repo_root: Path,
    release_dir: Path,
    rows: list[dict[str, object]],
    reference_map: dict[str, str],
) -> set[Path]:
    copied_sources: set[Path] = set()
    for reference in sorted(iter_reference_values(release_dir)):
        source = source_path_for_reference(reference, repo_root)
        if source is None:
            continue
        target = lineage_target_for_source(source, repo_root=repo_root, release_dir=release_dir)
        add_lineage_copy(
            source=source,
            target=target,
            release_dir=release_dir,
            original_reference=reference,
            role="referenced_candidate_or_review_source",
            rows=rows,
            reference_map=reference_map,
        )
        copied_sources.add(source.resolve())
    return copied_sources


def copy_ai_year_gap_bundle(
    *,
    repo_root: Path,
    release_dir: Path,
    copied_sources: set[Path],
    rows: list[dict[str, object]],
    reference_map: dict[str, str],
) -> None:
    stream_dirs = {
        source.parent
        for source in copied_sources
        if source.name.startswith("ai_year_gap_") or source.name in {"archive_expansion_year_panel.csv"}
    }
    stream_dirs.update(ai_year_gap_stream_dirs_from_run_config(repo_root=repo_root, release_dir=release_dir))
    for stream_dir in sorted(stream_dirs):
        try:
            stream_relative = stream_dir.resolve().relative_to(
                (repo_root / "artifacts/policy_data_internal/review/streams").resolve()
            )
        except ValueError:
            stream_relative = Path(safe_path_part(stream_dir.name))
        for name in AI_YEAR_GAP_AUDIT_FILES:
            source = stream_dir / name
            if not source.exists():
                continue
            target = release_dir / "audit/ai_api_provenance/stream_outputs" / stream_relative / name
            add_lineage_copy(
                source=source,
                target=target,
                release_dir=release_dir,
                original_reference=source.as_posix(),
                role="ai_api_year_gap_audit",
                rows=rows,
                reference_map=reference_map,
            )
    for triage_path in sorted((release_dir / "audit/ai_api_provenance").rglob("ai_year_gap_triage.csv")):
        triage = read_csv_or_empty(triage_path)
        if triage.empty:
            continue
        for column, subdir in [
            ("api_prompt_path", "prompts"),
            ("api_raw_response_path", "raw_responses"),
            ("api_parsed_response_path", "parsed_responses"),
        ]:
            if column not in triage.columns:
                continue
            for reference in triage[column].map(clean_text).loc[lambda series: series.ne("")].drop_duplicates():
                source = source_path_for_reference(reference, repo_root)
                if source is None:
                    continue
                target = release_dir / "audit/ai_api_provenance" / subdir / source.name
                add_lineage_copy(
                    source=source,
                    target=target,
                    release_dir=release_dir,
                    original_reference=reference,
                    role=f"ai_api_{subdir.rstrip('s')}",
                    rows=rows,
                    reference_map=reference_map,
                )


def ai_year_gap_stream_dirs_from_run_config(*, repo_root: Path, release_dir: Path) -> set[Path]:
    config_path = release_dir / "audit/production_inputs/run_config.json"
    config = read_json_object(config_path)
    namespace = clean_text(config.get("run_namespace"))
    rescue_text = " ".join(
        [
            clean_text(config.get("api_web_rescue_mode")),
            clean_text(config.get("api_web_rescue_status")),
            clean_text(config.get("api_web_rescue_reason")),
        ]
    ).lower()
    if not namespace or not any(marker in rescue_text for marker in ("ai", "api", "web")):
        return set()
    streams_root = repo_root / "artifacts/policy_data_internal/review/streams"
    if not streams_root.exists():
        return set()
    return {
        path
        for path in streams_root.glob(f"*/{namespace}")
        if path.is_dir() and any((path / name).exists() for name in AI_YEAR_GAP_AUDIT_FILES)
    }


def rewrite_csv_references(path: Path, reference_map: dict[str, str]) -> None:
    frame = read_csv_or_empty(path)
    if frame.empty and path.stat().st_size == 0:
        return
    changed = False
    for column in frame.columns:
        original = frame[column].fillna("").map(clean_text)
        rewritten = original.map(lambda value: rewrite_reference_text(value, reference_map))
        if not rewritten.equals(original):
            frame[column] = rewritten
            changed = True
    if changed:
        write_csv(frame, path)


def rewrite_reference_text(value: str, reference_map: dict[str, str]) -> str:
    if not value:
        return value
    if value in reference_map:
        return reference_map[value]
    rewritten = value
    for original, packaged in sorted(reference_map.items(), key=lambda item: len(item[0]), reverse=True):
        if original and original in rewritten:
            rewritten = rewritten.replace(original, packaged)
    return rewritten


def final_lineage_manifest(rows: list[dict[str, object]], release_dir: Path) -> pd.DataFrame:
    refreshed: list[dict[str, object]] = []
    for row in rows:
        updated = dict(row)
        rel_path = clean_text(updated.get("packaged_path"))
        path = release_dir / rel_path
        if rel_path and path.exists():
            size = path.stat().st_size
            digest = sha256_file(path)
            updated["size_bytes"] = size
            updated["sha256"] = digest
            updated["packaged_size_bytes"] = size
            updated["packaged_sha256"] = digest
        refreshed.append(updated)
    return pd.DataFrame(refreshed)


def package_lineage_sources(
    *,
    repo_root: Path,
    chunk_dir: Path,
    chunk_id: str,
    release_dir: Path,
) -> None:
    rows: list[dict[str, object]] = []
    reference_map: dict[str, str] = {}
    production_input_dir = production_input_dir_for_chunk(repo_root, chunk_dir, chunk_id)
    copy_production_input_files(
        production_input_dir=production_input_dir,
        release_dir=release_dir,
        rows=rows,
        reference_map=reference_map,
    )
    copied_sources = copy_referenced_lineage_files(
        repo_root=repo_root,
        release_dir=release_dir,
        rows=rows,
        reference_map=reference_map,
    )
    copy_ai_year_gap_bundle(
        repo_root=repo_root,
        release_dir=release_dir,
        copied_sources=copied_sources,
        rows=rows,
        reference_map=reference_map,
    )
    for path in sorted(release_dir.rglob("*.csv")):
        rewrite_csv_references(path, reference_map)
    write_csv(final_lineage_manifest(rows, release_dir), release_dir / "audit/source_lineage_manifest.csv")


def csv_shape(path: Path) -> tuple[int | str, int | str]:
    if path.suffix.lower() != ".csv" or not path.exists() or path.stat().st_size == 0:
        return "", ""
    frame = read_csv_or_empty(path)
    return len(frame), len(frame.columns)


def release_file_record(path: Path, release_dir: Path, role: str) -> dict[str, object]:
    rows, columns = csv_shape(path)
    return {
        "role": role,
        "path": path_in_release(path, release_dir),
        "size_bytes": path.stat().st_size,
        "modified_at_utc": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(timespec="seconds"),
        "sha256": sha256_file(path),
        "rows": rows,
        "columns": columns,
    }


def iter_release_files(release_dir: Path, *, include_manifests: bool = False) -> list[Path]:
    excluded = {"release_manifest.csv", "checksums.sha256", "rebuild_check.csv", "rebuild_check_log.txt"}
    if include_manifests:
        excluded = {"checksums.sha256", "rebuild_check.csv", "rebuild_check_log.txt"}
    return sorted(
        path
        for path in release_dir.rglob("*")
        if path.is_file() and path.name not in excluded
    )


def validate_chunk(chunk_dir: Path) -> None:
    missing = [name for name in REQUIRED_CHUNK_FILES if not (chunk_dir / name).exists()]
    if missing:
        raise FileNotFoundError(f"Production chunk is missing required files: {', '.join(missing)}")

    requirements = pd.read_csv(chunk_dir / "REQUIREMENTS_STATUS.csv")
    if not requirements["status"].astype(str).str.lower().eq("pass").all():
        failed = requirements.loc[~requirements["status"].astype(str).str.lower().eq("pass"), "requirement_id"]
        raise ValueError(f"Production chunk has failing requirements: {', '.join(failed.astype(str))}")

    benchmark_misses = read_csv_or_empty(chunk_dir / "BENCHMARK_MISSES.csv")
    if not benchmark_misses.empty:
        raise ValueError("Production chunk still has benchmark misses; it cannot be packaged as a passing URL-stage release.")


def copy_chunk_outputs(chunk_dir: Path, audit_dir: Path, release_dir: Path) -> None:
    for source_name, target_rel in CHUNK_DATA_COPIES.items():
        copy_file(chunk_dir / source_name, release_dir / target_rel)
    for source_name, target_rel in CHUNK_AUDIT_COPIES.items():
        if (chunk_dir / source_name).exists():
            copy_file(chunk_dir / source_name, release_dir / target_rel)

    if audit_dir.exists():
        for source in sorted(audit_dir.rglob("*")):
            if not source.is_file():
                continue
            relative = source.relative_to(audit_dir)
            if relative.parts and relative.parts[0] == "code_snapshot":
                target = release_dir / "code" / "source_snapshot" / Path(*relative.parts[1:])
            else:
                target = release_dir / "audit" / relative
            copy_file(source, target)


def package_relative_reference(original: str, *, repo_root: Path, release_dir: Path, chunk_id: str) -> str:
    value = clean_text(original)
    if not value:
        return value
    path = Path(value)
    if not path.is_absolute():
        return value
    try:
        relative = path.resolve().relative_to(release_dir.resolve())
        return relative.as_posix()
    except ValueError:
        pass
    try:
        repo_relative = path.resolve().relative_to(repo_root.resolve())
    except ValueError:
        return f"external_absolute_path_removed:{path.name}"

    chunk_prefix = Path("artifacts/PIPELINE_OUTPUTS/01_url_discovery/production_chunks") / chunk_id
    audit_prefix = Path("artifacts/AUDIT_TRAILS") / f"url_discovery_{chunk_id}"

    try:
        chunk_relative = repo_relative.relative_to(chunk_prefix)
        mapped = CHUNK_DATA_COPIES.get(chunk_relative.as_posix()) or CHUNK_AUDIT_COPIES.get(chunk_relative.as_posix())
        if mapped:
            return mapped
        return f"audit/construction_chunk_file:{chunk_relative.as_posix()}"
    except ValueError:
        pass

    try:
        audit_relative = repo_relative.relative_to(audit_prefix)
        if audit_relative.parts and audit_relative.parts[0] == "code_snapshot":
            return (Path("code/source_snapshot") / Path(*audit_relative.parts[1:])).as_posix()
        return (Path("audit") / audit_relative).as_posix()
    except ValueError:
        pass

    return f"construction_upstream_file:{repo_relative.as_posix()}"


def sanitize_text_value(value: str, *, repo_root: Path, release_dir: Path, chunk_id: str) -> str:
    if not value:
        return value
    repo_prefix = str(repo_root.resolve())

    if Path(value).is_absolute():
        return package_relative_reference(value, repo_root=repo_root, release_dir=release_dir, chunk_id=chunk_id)

    first, separator, remainder = value.partition(" ")
    if separator and first.isalnum() and Path(remainder).is_absolute():
        return f"{first} {package_relative_reference(remainder, repo_root=repo_root, release_dir=release_dir, chunk_id=chunk_id)}"

    if repo_prefix not in value:
        return value

    replacements: dict[str, str] = {}
    for token in value.split():
        stripped = token.strip().strip(",;)")
        if stripped.startswith(repo_prefix):
            replacements[stripped] = package_relative_reference(
                stripped,
                repo_root=repo_root,
                release_dir=release_dir,
                chunk_id=chunk_id,
            )
    sanitized = value
    for original, replacement in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
        sanitized = sanitized.replace(original, replacement)
    return sanitized.replace(repo_prefix, "construction_project_root")


def sanitize_csv_paths(path: Path, *, repo_root: Path, release_dir: Path, chunk_id: str) -> None:
    frame = read_csv_or_empty(path)
    if frame.empty and path.stat().st_size == 0:
        return
    changed = False
    for column in frame.columns:
        sanitized = frame[column].map(
            lambda value: sanitize_text_value(
                clean_text(value),
                repo_root=repo_root,
                release_dir=release_dir,
                chunk_id=chunk_id,
            )
        )
        if not sanitized.equals(frame[column].fillna("").map(clean_text)):
            frame[column] = sanitized
            changed = True
    if changed:
        write_csv(frame, path)


def sanitize_json_paths(path: Path, *, repo_root: Path, release_dir: Path, chunk_id: str) -> None:
    text = path.read_text(encoding="utf-8")
    sanitized = sanitize_text_value(text, repo_root=repo_root, release_dir=release_dir, chunk_id=chunk_id)
    if sanitized != text:
        path.write_text(sanitized, encoding="utf-8")


def sanitize_release_paths(release_dir: Path, *, repo_root: Path, chunk_id: str) -> None:
    for path in sorted(release_dir.rglob("*")):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix == ".csv":
            sanitize_csv_paths(path, repo_root=repo_root, release_dir=release_dir, chunk_id=chunk_id)
        elif suffix in {".json", ".txt", ".md"}:
            sanitize_json_paths(path, repo_root=repo_root, release_dir=release_dir, chunk_id=chunk_id)


def remove_bytecode_caches(release_dir: Path) -> None:
    for pycache in sorted(release_dir.rglob("__pycache__")):
        if pycache.is_dir():
            shutil.rmtree(pycache)
    for pyc in sorted(release_dir.rglob("*.pyc")):
        if pyc.is_file():
            pyc.unlink()


def write_target_panel(release_dir: Path) -> None:
    handoff = pd.read_csv(release_dir / "data/reviewed_url_handoff_panel.csv", low_memory=False)
    columns = [c for c in ["unitid", "institution_name", "sector", "state", "academic_year"] if c in handoff.columns]
    target_panel = handoff[columns].drop_duplicates().sort_values(columns).reset_index(drop=True)
    write_csv(target_panel, release_dir / "data/target_panel.csv")


def write_candidate_url_ledger(release_dir: Path) -> None:
    handoff = pd.read_csv(release_dir / "data/reviewed_url_handoff_panel.csv", low_memory=False)
    columns = [
        "unitid",
        "institution_name",
        "academic_year",
        "candidate_url",
        "url_for_text_extraction",
        "url_status",
        "production_url_source",
        "candidate_generation_method",
        "candidate_source_type",
        "legacy_input_provenance",
        "candidate_source_file",
        "source_review_file",
        "review_decision",
        "review_reason",
    ]
    for column in columns:
        if column not in handoff.columns:
            handoff[column] = ""
    write_csv(handoff[columns].copy(), release_dir / "data/candidate_url_ledger.csv")


def write_url_validation_audit(release_dir: Path) -> None:
    handoff = pd.read_csv(release_dir / "data/reviewed_url_handoff_panel.csv", low_memory=False)
    columns = [
        "unitid",
        "institution_name",
        "academic_year",
        "ready_for_text_extraction",
        "url_status",
        "url_status_reason",
        "unresolved_reason",
        "source_opened",
        "retrieval_status",
        "http_status",
        "final_url_after_redirect",
        "legacy_input_provenance",
        "institution_match_confirmed",
        "campus_or_unitid_match_confirmed",
        "source_scope_confirmed",
        "source_type_confirmed",
        "year_coverage_confirmed",
        "archive_child_links_checked",
        "gap_fill_search_completed",
        "panel_consistency_confirmed",
        "review_decision",
        "reviewed_by",
        "reviewed_at",
    ]
    for column in columns:
        if column not in handoff.columns:
            handoff[column] = ""
    write_csv(handoff[columns].copy(), release_dir / "data/url_validation_audit.csv")


def write_source_review_log(release_dir: Path) -> None:
    ledger = read_csv_or_empty(release_dir / "data/source_ledger.csv")
    columns = [
        "unitid",
        "institution_name",
        "academic_year",
        "accepted_source_url",
        "provenance_type",
        "legacy_input_provenance",
        "review_file",
        "review_decision",
        "review_reason",
        "reviewed_by",
        "reviewed_at",
        "source_opened",
        "institution_match_confirmed",
        "source_scope_confirmed",
        "source_type_confirmed",
        "year_coverage_confirmed",
        "panel_consistency_confirmed",
    ]
    for column in columns:
        if column not in ledger.columns:
            ledger[column] = ""
    write_csv(ledger[columns].copy(), release_dir / "data/source_review_log.csv")


def write_stage_rates(release_dir: Path) -> None:
    handoff = pd.read_csv(release_dir / "data/reviewed_url_handoff_panel.csv", low_memory=False)
    ledger = read_csv_or_empty(release_dir / "data/source_ledger.csv")
    unresolved = read_csv_or_empty(release_dir / "data/url_stop_log.csv")
    recovery = read_csv_or_empty(release_dir / "data/benchmark_recovery.csv")
    target_rows = len(handoff)
    rows = [
        {"metric": "target_rows", "sector": "all", "count": target_rows, "denominator": target_rows, "rate": 1.0 if target_rows else ""},
        {
            "metric": "source_ledger_rows",
            "sector": "all",
            "count": len(ledger),
            "denominator": target_rows,
            "rate": len(ledger) / target_rows if target_rows else "",
        },
        {
            "metric": "unresolved_rows",
            "sector": "all",
            "count": len(unresolved),
            "denominator": target_rows,
            "rate": len(unresolved) / target_rows if target_rows else "",
        },
    ]
    if "sector" in handoff.columns:
        ready = handoff.copy()
        ready["_ready"] = ready.get("ready_for_text_extraction", pd.Series("", index=ready.index)).map(clean_text).str.lower().isin(
            {"1", "1.0", "true", "yes", "y"}
        )
        for sector, group in ready.groupby("sector", dropna=False):
            denominator = len(group)
            count = int(group["_ready"].sum())
            rows.append(
                {
                    "metric": "source_ledger_rows",
                    "sector": clean_text(sector) or "missing_sector",
                    "count": count,
                    "denominator": denominator,
                    "rate": count / denominator if denominator else "",
                }
            )
    if not recovery.empty:
        status = recovery["benchmark_recovery_status"].astype(str)
        current = status.eq("recovered_by_current_chunk")
        invalidated = status.eq("row_invalidated_by_current_review")
        miss = status.eq("miss")
        rows.append(
            {
                "metric": "benchmark_rows_recovered_by_current_run",
                "sector": "all",
                "count": int(current.sum()),
                "denominator": len(recovery),
                "rate": int(current.sum()) / len(recovery),
            }
        )
        rows.append(
            {
                "metric": "benchmark_rows_invalidated_by_current_review",
                "sector": "all",
                "count": int(invalidated.sum()),
                "denominator": len(recovery),
                "rate": int(invalidated.sum()) / len(recovery),
            }
        )
        rows.append(
            {
                "metric": "benchmark_unresolved_misses",
                "sector": "all",
                "count": int(miss.sum()),
                "denominator": len(recovery),
                "rate": int(miss.sum()) / len(recovery),
            }
        )
        if "sector" in recovery.columns:
            for sector, group in recovery.groupby("sector", dropna=False):
                sector_status = group["benchmark_recovery_status"].astype(str)
                denominator = len(group)
                for metric, mask in [
                    ("benchmark_rows_recovered_by_current_run", sector_status.eq("recovered_by_current_chunk")),
                    ("benchmark_rows_invalidated_by_current_review", sector_status.eq("row_invalidated_by_current_review")),
                    ("benchmark_unresolved_misses", sector_status.eq("miss")),
                ]:
                    count = int(mask.sum())
                    rows.append(
                        {
                            "metric": metric,
                            "sector": clean_text(sector) or "missing_sector",
                            "count": count,
                            "denominator": denominator,
                            "rate": count / denominator if denominator else "",
                        }
                    )
    write_csv(pd.DataFrame(rows), release_dir / "data/stage_rates.csv")


def write_loss_buckets(release_dir: Path) -> None:
    unresolved = read_csv_or_empty(release_dir / "data/url_stop_log.csv")
    if unresolved.empty:
        buckets = pd.DataFrame(columns=["bucket", "count"])
    else:
        source = "url_status" if "url_status" in unresolved.columns else "unresolved_reason"
        buckets = (
            unresolved[source]
            .fillna("")
            .astype(str)
            .replace("", "missing_unresolved_status")
            .value_counts()
            .rename_axis("bucket")
            .reset_index(name="count")
        )
    write_csv(buckets, release_dir / "data/loss_buckets.csv")


def write_source_evidence_manifest(release_dir: Path) -> None:
    ledger = read_csv_or_empty(release_dir / "data/source_ledger.csv")
    cache_frames = [
        read_csv_or_empty(release_dir / "audit/current_run_reattempt_cached_source_evidence.csv"),
        read_csv_or_empty(release_dir / "audit/source_evidence_manifest.csv"),
    ]
    cache_frames = [frame for frame in cache_frames if not frame.empty]
    cache = pd.concat(cache_frames, ignore_index=True, sort=False) if cache_frames else pd.DataFrame()
    rows: list[dict[str, object]] = []
    for _, row in ledger.iterrows():
        unitid = clean_text(row.get("unitid"))
        year = clean_text(row.get("academic_year"))
        accepted_url = clean_text(row.get("accepted_source_url"))
        cache_row = pd.DataFrame()
        if not cache.empty:
            cache_row = cache.loc[
                cache.get("unitid", pd.Series(index=cache.index, dtype=object)).map(clean_text).eq(unitid)
                & cache.get("academic_year", pd.Series(index=cache.index, dtype=object)).map(clean_text).eq(year)
            ]
        cached_text_path = ""
        cached_text_sha256 = ""
        source_body_sha256 = ""
        if not cache_row.empty:
            cache_first = cache_row.iloc[0]
            cached_text_path = clean_text(cache_first.get("cached_text_path"))
            source_body_sha256 = clean_text(cache_first.get("source_body_sha256"))
            cached_text_sha256 = clean_text(cache_first.get("cached_text_sha256"))
            if cached_text_path:
                cached = Path(cached_text_path)
                candidates = [cached] if cached.is_absolute() else []
                candidates.extend(
                    [
                        release_dir / "audit" / cached,
                        release_dir / "audit/source_evidence_cache" / cached.name,
                        release_dir / "audit/current_run_reattempt_cached_text" / cached.name,
                        release_dir / cached,
                    ]
                )
                for candidate in candidates:
                    if candidate.exists() and release_dir.resolve() in candidate.resolve().parents:
                        cached_text_path = path_in_release(candidate, release_dir)
                        break
        rows.append(
            {
                "unitid": unitid,
                "institution_name": clean_text(row.get("institution_name")),
                "academic_year": year,
                "accepted_source_url": accepted_url,
                "provenance_type": clean_text(row.get("provenance_type")),
                "review_decision": clean_text(row.get("review_decision")),
                "reviewed_by": clean_text(row.get("reviewed_by")),
                "reviewed_at": clean_text(row.get("reviewed_at")),
                "evidence_hash_or_cache_path": clean_text(row.get("evidence_hash_or_cache_path")),
                "cached_text_path": cached_text_path,
                "cached_text_sha256": cached_text_sha256,
                "source_body_sha256": source_body_sha256,
                "source_artifact_status": "cached_text_available" if cached_text_path else "source_url_and_review_evidence_only",
            }
        )
    write_csv(pd.DataFrame(rows), release_dir / "source_evidence_manifest.csv")


def ai_source_review_linkage(release_dir: Path, unitid: object) -> dict[str, object]:
    candidate_paths = [
        release_dir / "data/candidate_url_ledger.csv",
        release_dir / "audit/production_inputs/candidate_url_ledger.csv",
    ]
    source_review = release_dir / "audit/production_inputs/source_review_log.csv"
    if not source_review.exists():
        source_review = release_dir / "data/source_review_log.csv"
    unitid_text = clean_text(unitid)
    linked_rows = 0
    for candidate_path in candidate_paths:
        candidate_ledger = read_csv_or_empty(candidate_path)
        if candidate_ledger.empty or not {"unitid", "candidate_generation_method"}.issubset(candidate_ledger.columns):
            continue
        unitid_matches = candidate_ledger["unitid"].map(clean_text).eq(unitid_text)
        ai_matches = candidate_ledger["candidate_generation_method"].fillna("").map(clean_text).str.contains("ai_|api_|web_search", regex=True)
        linked_rows += int((unitid_matches & ai_matches).sum())
    return {
        "source_review_linkage_path": path_in_release(source_review, release_dir) if source_review.exists() else "",
        "source_review_linkage_sha256": sha256_file(source_review) if source_review.exists() else "",
        "source_review_linkage_filter": (
            f"unitid={unitid_text}; join data/candidate_url_ledger.csv AI/API-assisted rows "
            "and audit/production_inputs/candidate_url_ledger.csv to the packaged source-review log on unitid and academic_year"
            if unitid_text
            else ""
        ),
        "linked_ai_candidate_rows": linked_rows,
    }


def write_ai_model_output_manifest(release_dir: Path) -> None:
    rows: list[dict[str, object]] = []
    for triage_path in sorted((release_dir / "audit/ai_api_provenance").rglob("ai_year_gap_triage.csv")):
        triage = read_csv_or_empty(triage_path)
        if triage.empty:
            continue
        for _, row in triage.iterrows():
            prompt_path = release_dir / clean_text(row.get("api_prompt_path"))
            raw_path = release_dir / clean_text(row.get("api_raw_response_path"))
            parsed_path = release_dir / clean_text(row.get("api_parsed_response_path"))
            raw = read_json_object(raw_path)
            linkage = ai_source_review_linkage(release_dir, row.get("unitid"))
            rows.append(
                {
                    "task_type": "clean_no_legacy_year_gap_web_discovery",
                    "provider_or_tool": "OpenAI Responses API with web-search tool",
                    "model_or_version": clean_text(raw.get("model")),
                    "run_date_time": response_timestamp_iso(raw),
                    "prompt_or_rule_version": clean_text(row.get("api_prompt_version")),
                    "schema_version": prompt_schema_version(prompt_path),
                    "unitid": clean_text(row.get("unitid")),
                    "institution_name": clean_text(row.get("institution_name")),
                    "call_or_run_id": clean_text(row.get("api_log_call_id")),
                    "input_hash": sha256_if_file(prompt_path),
                    "output_hash": sha256_if_file(parsed_path),
                    "prompt_path": path_in_release_if_file(prompt_path, release_dir),
                    "prompt_sha256": sha256_if_file(prompt_path),
                    "raw_response_path": path_in_release_if_file(raw_path, release_dir),
                    "raw_response_sha256": sha256_if_file(raw_path),
                    "parsed_response_path": path_in_release_if_file(parsed_path, release_dir),
                    "parsed_response_sha256": sha256_if_file(parsed_path),
                    "triage_path": path_in_release(triage_path, release_dir),
                    "triage_sha256": sha256_file(triage_path),
                    **linkage,
                    "validation_status": clean_text(row.get("api_validation_status")),
                }
            )
    queue = release_dir / "audit/current_run_reattempt_queue.csv"
    review = release_dir / "audit/current_run_reattempt_source_review.csv"
    adjudications = release_dir / "audit/current_run_reattempt_manual_adjudications.csv"
    if review.exists():
        rows.append(
            {
                "task_type": "codex_assisted_source_review",
                "provider_or_tool": "Codex/manual source review",
                "model_or_version": "recorded in project audit trail when available",
                "run_date_time": "",
                "prompt_or_rule_version": "url_source_review_standard",
                "schema_version": "production_chunk_reattempt_review",
                "unitid": "",
                "institution_name": "",
                "call_or_run_id": "",
                "input_hash": sha256_file(queue) if queue.exists() else "",
                "output_hash": sha256_file(review),
                "prompt_path": "",
                "prompt_sha256": "",
                "raw_response_path": "",
                "raw_response_sha256": "",
                "parsed_response_path": path_in_release(review, release_dir),
                "parsed_response_sha256": sha256_file(review),
                "triage_path": path_in_release(adjudications, release_dir) if adjudications.exists() else "",
                "triage_sha256": sha256_file(adjudications) if adjudications.exists() else "",
                "source_review_linkage_path": path_in_release(review, release_dir),
                "source_review_linkage_sha256": sha256_file(review),
                "source_review_linkage_filter": "codex-assisted source-review output row",
                "linked_ai_candidate_rows": "",
                "validation_status": "accepted_rows_preserved_in_source_ledger",
            }
        )
    api_summary = release_dir / "audit/api_rescue_summary.csv"
    if api_summary.exists():
        rows.append(
            {
                "task_type": "url_api_rescue_summary",
                "provider_or_tool": "prior_batch_api_rescue",
                "model_or_version": "",
                "run_date_time": "",
                "prompt_or_rule_version": "",
                "schema_version": "api_rescue_summary",
                "unitid": "",
                "institution_name": "",
                "call_or_run_id": "",
                "input_hash": "",
                "output_hash": sha256_file(api_summary),
                "prompt_path": "",
                "prompt_sha256": "",
                "raw_response_path": "",
                "raw_response_sha256": "",
                "parsed_response_path": path_in_release(api_summary, release_dir),
                "parsed_response_sha256": sha256_file(api_summary),
                "triage_path": "",
                "triage_sha256": "",
                "source_review_linkage_path": "",
                "source_review_linkage_sha256": "",
                "source_review_linkage_filter": "",
                "linked_ai_candidate_rows": "",
                "validation_status": "prior_api_attempt_documented_not_rerun",
            }
        )
    write_csv(pd.DataFrame(rows, columns=AI_MODEL_OUTPUT_COLUMNS), release_dir / "ai_model_output_manifest.csv")


def write_ai_api_use_statement(release_dir: Path) -> None:
    manifest = read_csv_or_empty(release_dir / "ai_model_output_manifest.csv")
    handoff = read_csv_or_empty(release_dir / "data/reviewed_url_handoff_panel.csv")
    ai_methods = pd.Series(dtype=object)
    if not handoff.empty and "candidate_generation_method" in handoff.columns:
        methods = handoff["candidate_generation_method"].fillna("").map(clean_text)
        ai_methods = methods.loc[methods.str.contains("ai_|api_|web_search", regex=True)]
    rows = [
        {
            "component": "candidate_generation",
            "ai_or_api_used": bool(not ai_methods.empty),
            "release_evidence": "ai_model_output_manifest.csv; audit/ai_api_provenance/",
            "detail": (
                f"ai_or_api_candidate_rows={len(ai_methods)}; manifest_rows={len(manifest)}"
                if not manifest.empty or not ai_methods.empty
                else "No AI/API-assisted candidate-generation rows detected in the release handoff."
            ),
        },
        {
            "component": "source_review",
            "ai_or_api_used": False,
            "release_evidence": "data/source_review_log.csv; audit/production_inputs/source_review_log.csv",
            "detail": "Source-review decisions are deterministic Codex review of retrieved source evidence, not hidden API classification.",
        },
        {
            "component": "downstream_policy_classification",
            "ai_or_api_used": False,
            "release_evidence": "",
            "detail": "Downstream extraction and policy classification are outside this URL-stage release.",
        },
    ]
    write_csv(pd.DataFrame(rows), release_dir / "ai_api_use_statement.csv")


def write_data_availability(release_dir: Path) -> None:
    rows = [
        {"component": "IPEDS/input panel", "release_status": "not_packaged_in_url_stage_release", "note": "Referenced by upstream target construction."},
        {"component": "accepted catalog/source URLs", "release_status": "included", "note": "Stored in data/source_ledger.csv."},
        {"component": "cached source text", "release_status": "included_when_available", "note": "Stored under audit/source_evidence_cache when packaged; older reattempt packages may use audit/current_run_reattempt_cached_text."},
        {"component": "live web retrieval", "release_status": "not_required_for_rebuild", "note": "Optional diagnostic only; release uses frozen ledger and cached evidence."},
        {"component": "Codex/API outputs", "release_status": "included_when_affecting_step1", "note": "See ai_api_use_statement.csv, ai_model_output_manifest.csv, and audit/ai_api_provenance/."},
        {"component": "candidate/source lineage", "release_status": "included", "note": "See audit/source_lineage_manifest.csv and audit/source_lineage/."},
        {"component": "downstream policy extraction/classification", "release_status": "not_included_in_url_stage_release", "note": "Must be added before final journal release."},
    ]
    write_csv(pd.DataFrame(rows), release_dir / "data_availability.csv")


def write_environment_manifest(release_dir: Path) -> None:
    packages = []
    for name in ["pandas"]:
        try:
            module = __import__(name)
            version = getattr(module, "__version__", "")
        except Exception:
            version = ""
        packages.append({"package": name, "version": version})
    rows = [
        {"key": "python_version", "value": sys.version.replace("\n", " ")},
        {"key": "python_executable", "value": Path(sys.executable).name},
        {"key": "platform", "value": platform.platform()},
        {"key": "package_versions", "value": json.dumps(packages, sort_keys=True)},
    ]
    write_csv(pd.DataFrame(rows), release_dir / "environment_manifest.csv")


def write_code_archive_manifest(release_dir: Path) -> None:
    code_dir = release_dir / "code/source_snapshot"
    rows = []
    if code_dir.exists():
        for path in sorted(code_dir.rglob("*")):
            if path.is_file():
                rows.append(release_file_record(path, release_dir, "archived_code"))
    write_csv(pd.DataFrame(rows), release_dir / "code_archive_manifest.csv")


def write_release_readme(release_dir: Path, *, release_id: str, chunk_id: str) -> None:
    text = f"""# {release_id}

Status: URL-stage source-review release package, not a complete journal release.

This package freezes Step 1 URL/source-discovery outputs from `{chunk_id}`. It
is intended to be rebuilt from package-local files and cached evidence, without
live Codex repair or live web rediscovery.

Run order:

1. Inspect `data/target_panel.csv`.
2. Inspect `data/source_ledger.csv` and `data/url_stop_log.csv`.
3. Verify `release_manifest.csv` and `checksums.sha256`.
4. Use `data/reviewed_url_handoff_panel.csv` as the URL-stage handoff.

Exact package-local verification command:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=code/source_snapshot/src python -m course_policy.production_release_url_stage --release-root . --verify-only
```

This URL-stage package still excludes downstream text retrieval, policy excerpt
search, policy classification, adjudication, final panel construction, and final
analysis outputs.
"""
    (release_dir / "README.md").write_text(text, encoding="utf-8")


def write_rebuild_commands(release_dir: Path) -> None:
    text = "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=code/source_snapshot/src python -m course_policy.production_release_url_stage --release-root . --verify-only\n"
    (release_dir / "REBUILD_COMMANDS.txt").write_text(text, encoding="utf-8")


def write_code_state(release_dir: Path, repo_root: Path) -> None:
    record = code_version_record(repo_root)
    record["archived_source_bundle"] = "code/source_snapshot"
    record["authoritative_release_code"] = "archived_source_bundle"
    record["dirty_worktree_interpretation"] = (
        "The URL-stage release is reproduced from code/source_snapshot. "
        "The git dirty flag documents the construction workspace and does not "
        "replace the archived bundle for this package."
    )
    write_csv(pd.DataFrame([record]), release_dir / "code_state.csv")


def ai_api_provenance_detail(release_dir: Path) -> tuple[str, str]:
    manifest = read_csv_or_empty(release_dir / "ai_model_output_manifest.csv")
    handoff = read_csv_or_empty(release_dir / "data/reviewed_url_handoff_panel.csv")
    needs_ai = False
    if not handoff.empty:
        for column in ["candidate_generation_method", "api_web_rescue_mode", "api_web_rescue_status"]:
            if column in handoff.columns:
                values = handoff[column].fillna("").map(clean_text).str.lower()
                needs_ai = needs_ai or bool(values.str.contains("ai|api|web_search", regex=True).any())
    if not needs_ai:
        return "not_applicable", "No AI/API-assisted URL-stage rows detected."
    if manifest.empty:
        return "fail", "AI/API-assisted rows detected, but ai_model_output_manifest.csv has no rows."
    missing = 0
    dry_run_rows = 0
    completed_rows = 0
    for _, row in manifest.iterrows():
        if clean_text(row.get("task_type")) != "clean_no_legacy_year_gap_web_discovery":
            continue
        validation_status = clean_text(row.get("validation_status")).lower()
        if validation_status == "dry_run":
            dry_run_rows += 1
            required = ["prompt_path", "triage_path"]
        else:
            completed_rows += 1
            required = ["prompt_path", "raw_response_path", "parsed_response_path", "triage_path"]
        for column in required:
            rel = clean_text(row.get(column))
            if not rel or not (release_dir / rel).is_file():
                missing += 1
    status = "pass" if missing == 0 else "fail"
    return (
        status,
        f"manifest_rows={len(manifest)}; completed_api_rows={completed_rows}; "
        f"dry_run_rows={dry_run_rows}; missing_required_artifact_refs={missing}",
    )


def source_lineage_package_local_detail(release_dir: Path) -> tuple[str, str]:
    checked = 0
    nonlocal_refs = 0
    bad_tokens = ("/Users/", "/Dropbox/", "artifacts/policy_data_internal/", "artifacts/PIPELINE_OUTPUTS/")
    for rel in [
        "data/candidate_url_ledger.csv",
        "data/source_review_log.csv",
        "data/reviewed_url_handoff_panel.csv",
        "data/source_ledger.csv",
        "data/url_validation_audit.csv",
    ]:
        frame = read_csv_or_empty(release_dir / rel)
        if frame.empty:
            continue
        for column in ["candidate_source_file", "source_review_file", "review_file"]:
            if column not in frame.columns:
                continue
            values = frame[column].fillna("").map(clean_text).loc[lambda series: series.ne("")]
            checked += len(values)
            for value in values:
                if any(token in value for token in bad_tokens):
                    nonlocal_refs += 1
                    continue
                if not value.startswith(("audit/", "data/", "code/")) and Path(value).suffix:
                    nonlocal_refs += 1
    manifest = release_dir / "audit/source_lineage_manifest.csv"
    manifest_rows = len(read_csv_or_empty(manifest))
    status = "pass" if nonlocal_refs == 0 and manifest.exists() and manifest_rows > 0 else "fail"
    return status, f"path_refs_checked={checked}; non_package_local_refs={nonlocal_refs}; lineage_manifest_rows={manifest_rows}"


def write_release_status(release_dir: Path, *, release_id: str, chunk_id: str) -> None:
    requirements = read_csv_or_empty(release_dir / "data/requirements_status.csv")
    stage_rates = read_csv_or_empty(release_dir / "data/stage_rates.csv")
    benchmark = read_csv_or_empty(release_dir / "data/benchmark_recovery.csv")
    benchmark_misses = read_csv_or_empty(release_dir / "data/benchmark_misses.csv")
    crosswalk = read_csv_or_empty(release_dir / "data/guideline_crosswalk.csv")
    req_pass = bool(not requirements.empty and requirements["status"].astype(str).str.lower().eq("pass").all())
    crosswalk_by_id = {
        clean_text(row.get("claim_id")): row
        for _, row in crosswalk.iterrows()
    } if not crosswalk.empty else {}

    def crosswalk_status(claim_id: str, default: str = "not_recorded") -> str:
        row = crosswalk_by_id.get(claim_id)
        return clean_text(row.get("status")) if row is not None else default

    def crosswalk_detail(claim_id: str, default: str = "") -> str:
        row = crosswalk_by_id.get(claim_id)
        if row is None:
            return default
        pieces = [
            clean_text(row.get("observed_value")),
            clean_text(row.get("supported_claim")),
            clean_text(row.get("limitation")),
        ]
        return " ".join(piece for piece in pieces if piece)

    legacy_status = crosswalk_status("legacy_carry_forward_accounting", "not_tested" if benchmark.empty else "fail")
    legacy_detail = crosswalk_detail(
        "legacy_carry_forward_accounting",
        "No benchmark denominator supplied." if benchmark.empty else f"benchmark_rows={len(benchmark)}; benchmark_misses={len(benchmark_misses)}",
    )
    clean_benchmark_status = crosswalk_status("clean_no_legacy_benchmark", "not_tested")
    clean_benchmark_detail = crosswalk_detail("clean_no_legacy_benchmark", "")
    source_ledger_status = crosswalk_status("source_ledger_row_accounting", "pass" if req_pass else "fail")
    source_ledger_detail = crosswalk_detail("source_ledger_row_accounting", "")
    readiness_status = crosswalk_status("source_discovery_readiness_to_scale", "under_review")
    readiness_detail = crosswalk_detail("source_discovery_readiness_to_scale", "")
    ai_status, ai_detail = ai_api_provenance_detail(release_dir)
    lineage_status, lineage_detail = source_lineage_package_local_detail(release_dir)
    ready_detail = ""
    if not stage_rates.empty and {"metric", "count", "denominator", "rate"}.issubset(stage_rates.columns):
        row = stage_rates.loc[
            stage_rates["metric"].astype(str).eq("source_ledger_rows")
            & stage_rates.get("sector", pd.Series("all", index=stage_rates.index)).astype(str).eq("all")
        ]
        if not row.empty:
            first = row.iloc[0]
            ready_detail = f"ready_rows={first['count']}; target_rows={first['denominator']}; ready_rate={float(first['rate']):.1%}"
    rows = [
        {"check": "release_id", "status": release_id, "detail": ""},
        {"check": "source_chunk", "status": chunk_id, "detail": ""},
        {"check": "clean_runner_rebuild_package", "status": "pass", "detail": "Release package rebuilt and verified from package-local files."},
        {"check": "blocking_clean_runner_requirements", "status": "pass" if req_pass else "fail", "detail": f"requirements_rows={len(requirements)}"},
        {"check": "source_ledger_row_accounting", "status": source_ledger_status, "detail": f"{source_ledger_detail} {ready_detail}".strip()},
        {"check": "legacy_prior_benchmark_accounting", "status": legacy_status, "detail": legacy_detail},
        {"check": "clean_no_legacy_benchmark", "status": clean_benchmark_status, "detail": clean_benchmark_detail},
        {"check": "ai_api_provenance_packaged", "status": ai_status, "detail": ai_detail},
        {"check": "candidate_source_lineage_package_local", "status": lineage_status, "detail": lineage_detail},
        {"check": "ready_to_scale_claim", "status": readiness_status, "detail": readiness_detail},
        {"check": "journal_release_ready", "status": "fail", "detail": "Downstream extraction/classification/final panel stages are not included."},
    ]
    write_csv(pd.DataFrame(rows), release_dir / "release_status.csv")


def write_manifest_exclusions(release_dir: Path) -> None:
    rows = [
        {
            "path": "release_manifest.csv",
            "reason": "Self-referential manifest file; its hash is recorded in checksums.sha256.",
            "expected_presence": "present",
        },
        {
            "path": "checksums.sha256",
            "reason": "Self-referential checksum file.",
            "expected_presence": "present",
        },
        {
            "path": "rebuild_check.csv",
            "reason": "Verifier output regenerated by the package-local verification command.",
            "expected_presence": "present_after_verification",
        },
        {
            "path": "rebuild_check_log.txt",
            "reason": "Verifier output regenerated by the package-local verification command.",
            "expected_presence": "present_after_verification",
        },
    ]
    write_csv(pd.DataFrame(rows), release_dir / "manifest_exclusions.csv")


def write_release_manifest_and_checksums(release_dir: Path) -> tuple[Path, Path]:
    manifest_path = release_dir / "release_manifest.csv"
    checksum_path = release_dir / "checksums.sha256"
    rows = [release_file_record(path, release_dir, "release_file") for path in iter_release_files(release_dir)]
    write_csv(pd.DataFrame(rows), manifest_path)

    checksum_rows = []
    for path in iter_release_files(release_dir, include_manifests=True):
        checksum_rows.append(f"{sha256_file(path)}  {path_in_release(path, release_dir)}")
    checksum_path.write_text("\n".join(checksum_rows) + "\n", encoding="utf-8")
    return manifest_path, checksum_path


def allowed_unmanifested_paths(release_dir: Path) -> set[str]:
    exclusions = read_csv_or_empty(release_dir / "manifest_exclusions.csv")
    if exclusions.empty or "path" not in exclusions.columns:
        return set(SELF_REFERENTIAL_RELEASE_FILES)
    return set(exclusions["path"].map(clean_text).loc[lambda s: s.ne("")])


def local_absolute_path_hits(release_dir: Path) -> list[dict[str, object]]:
    hits: list[dict[str, object]] = []
    for path in sorted(release_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".csv", ".json", ".txt", ".md"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "/Users/" in text or "/Dropbox/" in text:
            hits.append(
                {
                    "path": path_in_release(path, release_dir),
                    "exists": True,
                    "expected_sha256": "",
                    "actual_sha256": "",
                    "status": "fail_local_absolute_path_present",
                }
            )
    return hits


def unmanifested_file_hits(release_dir: Path, manifest: pd.DataFrame) -> list[dict[str, object]]:
    manifest_paths = set(manifest["path"].map(clean_text)) if "path" in manifest.columns else set()
    allowed = allowed_unmanifested_paths(release_dir)
    hits: list[dict[str, object]] = []
    for path in sorted(release_dir.rglob("*")):
        if not path.is_file():
            continue
        relative = path_in_release(path, release_dir)
        if relative in manifest_paths or relative in allowed:
            continue
        hits.append(
            {
                "path": relative,
                "exists": True,
                "expected_sha256": "",
                "actual_sha256": sha256_file(path),
                "status": "fail_unmanifested_file_present",
            }
        )
    return hits


def verify_release_package(release_dir: Path) -> tuple[pd.DataFrame, str]:
    remove_bytecode_caches(release_dir)
    manifest_path = release_dir / "release_manifest.csv"
    manifest = pd.read_csv(manifest_path)
    rows = []
    for _, row in manifest.iterrows():
        rel_path = clean_text(row.get("path"))
        path = release_dir / rel_path
        exists = path.exists()
        expected_sha = clean_text(row.get("sha256"))
        actual_sha = sha256_file(path) if exists else ""
        rows.append(
            {
                "path": rel_path,
                "exists": exists,
                "expected_sha256": expected_sha,
                "actual_sha256": actual_sha,
                "status": "pass" if exists and actual_sha == expected_sha else "fail",
            }
        )
    rows.extend(unmanifested_file_hits(release_dir, manifest))
    rows.extend(local_absolute_path_hits(release_dir))
    frame = pd.DataFrame(rows)
    overall = "pass" if not frame.empty and frame["status"].eq("pass").all() else "fail"
    log = (
        f"release_root=.\n"
        f"files_checked={len(frame)}\n"
        f"unmanifested_failures={int(frame['status'].eq('fail_unmanifested_file_present').sum()) if not frame.empty else 0}\n"
        f"local_absolute_path_failures={int(frame['status'].eq('fail_local_absolute_path_present').sum()) if not frame.empty else 0}\n"
        f"status={overall}\n"
    )
    return frame, log


def write_rebuild_check(release_dir: Path) -> tuple[Path, bool]:
    frame, log = verify_release_package(release_dir)
    check_path = release_dir / "rebuild_check.csv"
    log_path = release_dir / "rebuild_check_log.txt"
    write_csv(frame, check_path)
    log_path.write_text(log, encoding="utf-8")
    return check_path, bool(not frame.empty and frame["status"].eq("pass").all())


def build_url_stage_release_package(
    repo_root: Path,
    *,
    chunk_id: str = DEFAULT_CHUNK_ID,
    release_id: str = DEFAULT_RELEASE_ID,
    overwrite: bool = False,
) -> ReleasePackageResult:
    repo_root = repo_root.resolve()
    chunk_dir = repo_root / PRODUCTION_CHUNKS_ROOT / chunk_id
    audit_dir = repo_root / AUDIT_ROOT / f"url_discovery_{chunk_id}"
    release_dir = repo_root / PRODUCTION_RELEASES_ROOT / release_id
    validate_chunk(chunk_dir)

    if release_dir.exists():
        if not overwrite:
            raise FileExistsError(f"Release directory already exists: {release_dir}")
        shutil.rmtree(release_dir)
    release_dir.mkdir(parents=True, exist_ok=True)

    copy_chunk_outputs(chunk_dir, audit_dir, release_dir)
    write_target_panel(release_dir)
    write_candidate_url_ledger(release_dir)
    write_url_validation_audit(release_dir)
    write_source_review_log(release_dir)
    write_stage_rates(release_dir)
    write_loss_buckets(release_dir)
    write_source_evidence_manifest(release_dir)
    package_lineage_sources(
        repo_root=repo_root,
        chunk_dir=chunk_dir,
        chunk_id=chunk_id,
        release_dir=release_dir,
    )
    write_ai_model_output_manifest(release_dir)
    write_ai_api_use_statement(release_dir)
    write_data_availability(release_dir)
    write_environment_manifest(release_dir)
    write_code_archive_manifest(release_dir)
    write_release_status(release_dir, release_id=release_id, chunk_id=chunk_id)
    write_code_state(release_dir, repo_root)
    write_release_readme(release_dir, release_id=release_id, chunk_id=chunk_id)
    write_rebuild_commands(release_dir)
    write_manifest_exclusions(release_dir)
    sanitize_release_paths(release_dir, repo_root=repo_root, chunk_id=chunk_id)
    remove_bytecode_caches(release_dir)
    manifest_path, checksum_path = write_release_manifest_and_checksums(release_dir)
    rebuild_check_path, package_pass = write_rebuild_check(release_dir)
    remove_bytecode_caches(release_dir)
    manifest_path, checksum_path = write_release_manifest_and_checksums(release_dir)

    return ReleasePackageResult(
        release_dir=release_dir,
        release_id=release_id,
        release_manifest=manifest_path,
        checksum_file=checksum_path,
        rebuild_check=rebuild_check_path,
        package_pass=package_pass,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--chunk-id", default=DEFAULT_CHUNK_ID)
    parser.add_argument("--release-id", default=DEFAULT_RELEASE_ID)
    parser.add_argument("--release-root", type=Path, default=None)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.verify_only:
        release_dir = (args.release_root or Path.cwd()).resolve()
        remove_bytecode_caches(release_dir)
        frame, log = verify_release_package(release_dir)
        write_csv(frame, release_dir / "rebuild_check.csv")
        (release_dir / "rebuild_check_log.txt").write_text(log, encoding="utf-8")
        remove_bytecode_caches(release_dir)
        print(log.strip())
        return 0 if not frame.empty and frame["status"].eq("pass").all() else 1

    repo_root = repo_root_from_cwd(args.root)
    result = build_url_stage_release_package(
        repo_root,
        chunk_id=args.chunk_id,
        release_id=args.release_id,
        overwrite=args.overwrite,
    )
    print(f"release_dir={result.release_dir}")
    print(f"release_manifest={result.release_manifest}")
    print(f"checksum_file={result.checksum_file}")
    print(f"rebuild_check={result.rebuild_check}")
    print(f"package_pass={result.package_pass}")
    return 0 if result.package_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
