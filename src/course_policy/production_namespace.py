"""Organize generated catalog outputs into stream-specific production folders."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .ai_config import repo_root_from_cwd


INTERNAL_DATA_DIR = Path("artifacts/policy_data_internal")
DELIVERY_DATA_DIR = Path("../policy_data")
INTERIM_DIR = INTERNAL_DATA_DIR / "interim"
REVIEW_DIR = INTERNAL_DATA_DIR / "review"
LOG_DIR = INTERNAL_DATA_DIR / "logs"

PUBLIC_SUFFIX = "public_legacy_focused_resolution_v1"
PRIVATE_SMOKE_SUFFIX = "private_step0_smoke"
PRIVATE_DIRECT_SUFFIX = "private_human_all_v1"
PRIVATE_ROLLUP_SUFFIX = "private_human_legacy_rollup_v1"


@dataclass(frozen=True)
class ProductionNamespaceOutputs:
    public_manifest_csv: Path
    public_manifest_md: Path
    private_status_md: Path
    archive_manifest_csv: Path


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("run_%Y%m%d_%H%M%S")


def clean_run_id(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in value.strip())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_generated_source(preferred: Path) -> Path:
    if preferred.exists():
        return preferred
    archive_dir = preferred.parent / "archive"
    matches = sorted(archive_dir.glob(f"pre_namespace_*/{preferred.name}"))
    if matches:
        return matches[-1]
    raise FileNotFoundError(f"Missing generated source file: {preferred}")


def git_commit(repo_root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def git_dirty(repo_root: Path) -> str:
    try:
        status = subprocess.check_output(
            ["git", "status", "--short"],
            cwd=repo_root,
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""
    return "true" if status.strip() else "false"


def ensure_stream_dirs(repo_root: Path) -> None:
    for base in [INTERIM_DIR, REVIEW_DIR, LOG_DIR]:
        archive_path = repo_root / base / "archive"
        archive_path.mkdir(parents=True, exist_ok=True)
        keep = archive_path / ".gitkeep"
        if not keep.exists():
            keep.write_text("", encoding="utf-8")
        for stream in ["public", "private", "combined"]:
            for tier in ["current", "archive"]:
                path = repo_root / base / stream / tier
                path.mkdir(parents=True, exist_ok=True)
                keep = path / ".gitkeep"
                if not keep.exists():
                    keep.write_text("", encoding="utf-8")


def public_current_mappings(repo_root: Path) -> list[tuple[Path, Path, str]]:
    review = repo_root / REVIEW_DIR
    logs = repo_root / LOG_DIR
    return [
        (
            review / f"catalog_public_legacy_production_rollup_{PUBLIC_SUFFIX}.xlsx",
            review / "public/current/public_catalog_rollup.xlsx",
            "user_facing_workbook",
        ),
        (
            review / f"catalog_public_legacy_START_HERE_{PUBLIC_SUFFIX}.csv",
            review / "public/current/public_start_here.csv",
            "summary_metrics",
        ),
        (
            review / f"catalog_public_legacy_year_panel_{PUBLIC_SUFFIX}.csv",
            review / "public/current/public_year_panel.csv",
            "year_panel",
        ),
        (
            review / f"catalog_public_legacy_institution_qc_{PUBLIC_SUFFIX}.csv",
            review / "public/current/public_institution_qc.csv",
            "institution_qc",
        ),
        (
            review / f"catalog_public_legacy_public_status_{PUBLIC_SUFFIX}.csv",
            review / "public/current/public_status.csv",
            "public_status",
        ),
        (
            review / f"catalog_public_no_legacy_fresh_discovery_queue_{PUBLIC_SUFFIX}.csv",
            review / "public/current/public_no_legacy_fresh_discovery_queue.csv",
            "fresh_discovery_queue",
        ),
        (
            review / f"catalog_public_legacy_prior_seed_or_pilot_{PUBLIC_SUFFIX}.csv",
            review / "public/current/public_prior_seed_or_pilot.csv",
            "prior_seed_or_pilot",
        ),
        (
            review / f"catalog_public_legacy_gap_benchmark_{PUBLIC_SUFFIX}.csv",
            review / "public/current/public_legacy_gap_benchmark.csv",
            "legacy_gap_benchmark",
        ),
        (
            review / f"catalog_public_legacy_legacy_reproduction_{PUBLIC_SUFFIX}.csv",
            review / "public/current/public_legacy_reproduction.csv",
            "legacy_reproduction",
        ),
        (
            review / f"catalog_public_legacy_outside_legacy_bounds_{PUBLIC_SUFFIX}.csv",
            review / "public/current/public_outside_legacy_bounds.csv",
            "outside_legacy_bounds",
        ),
        (
            review / f"catalog_public_legacy_resolution_actions_{PUBLIC_SUFFIX}.csv",
            review / "public/current/public_resolution_actions.csv",
            "resolution_actions",
        ),
        (
            logs / f"catalog_public_legacy_production_rollup_{PUBLIC_SUFFIX}.md",
            logs / "public/current/public_catalog_rollup_summary.md",
            "summary_log",
        ),
        (
            logs / f"phase3_public_legacy_resolution_pass_{PUBLIC_SUFFIX}.md",
            logs / "public/current/public_resolution_pass_summary.md",
            "resolution_log",
        ),
    ]


def copy_public_current(repo_root: Path, *, run_id: str) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    commit = git_commit(repo_root)
    dirty = git_dirty(repo_root)
    for source, target, role in public_current_mappings(repo_root):
        source = resolve_generated_source(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        rows.append(
            {
                "run_id": run_id,
                "stream": "public",
                "role": role,
                "stable_output_path": str(target.resolve()),
                "source_output_path": str(source.resolve()),
                "sha256": sha256_file(target),
                "source_sha256": sha256_file(source),
                "byte_size": target.stat().st_size,
                "source_byte_size": source.stat().st_size,
                "git_commit": commit,
                "git_dirty": dirty,
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        )
    return pd.DataFrame(rows)


def write_public_manifest(repo_root: Path, manifest: pd.DataFrame) -> tuple[Path, Path]:
    csv_path = repo_root / REVIEW_DIR / "public/current/public_run_manifest.csv"
    md_path = repo_root / LOG_DIR / "public/current/public_run_manifest.md"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    manifest.to_csv(csv_path, index=False)
    mismatches = manifest.loc[
        (manifest["sha256"] != manifest["source_sha256"])
        | (manifest["byte_size"] != manifest["source_byte_size"])
    ]
    lines = [
        "# Public Production Run Manifest",
        "",
        f"Run id: `{manifest['run_id'].iloc[0] if not manifest.empty else ''}`",
        f"Git commit: `{manifest['git_commit'].iloc[0] if not manifest.empty else ''}`",
        f"Git dirty: `{manifest['git_dirty'].iloc[0] if not manifest.empty else ''}`",
        "",
        "## Verification",
        "",
        f"- Stable files copied: {len(manifest)}",
        f"- SHA/size mismatches: {len(mismatches)}",
        "",
        "## Current Public Files",
        "",
    ]
    for _, row in manifest.sort_values("role").iterrows():
        lines.append(f"- {row['role']}: `{row['stable_output_path']}`")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return csv_path.resolve(), md_path.resolve()


def private_direct_mappings(repo_root: Path) -> list[tuple[Path, Path, str]]:
    review = repo_root / REVIEW_DIR
    logs = repo_root / LOG_DIR
    return [
        (
            review / f"private_legacy_direct_review_{PRIVATE_DIRECT_SUFFIX}.xlsx",
            review / "private/current/private_legacy_direct_review.xlsx",
            "private_direct_workbook",
        ),
        (
            review / f"private_legacy_direct_url_status_{PRIVATE_DIRECT_SUFFIX}.csv",
            review / "private/current/private_legacy_direct_url_status.csv",
            "private_direct_url_status",
        ),
        (
            review / f"private_legacy_direct_institution_status_{PRIVATE_DIRECT_SUFFIX}.csv",
            review / "private/current/private_legacy_direct_institution_status.csv",
            "private_direct_institution_status",
        ),
        (
            logs / f"private_legacy_direct_summary_{PRIVATE_DIRECT_SUFFIX}.md",
            logs / "private/current/private_legacy_direct_summary.md",
            "private_direct_summary",
        ),
    ]


def private_rollup_mappings(repo_root: Path) -> list[tuple[Path, Path, str]]:
    review = repo_root / REVIEW_DIR
    logs = repo_root / LOG_DIR
    return [
        (
            review / f"catalog_private_human_legacy_rollup_{PRIVATE_ROLLUP_SUFFIX}.xlsx",
            review / "private/current/private_catalog_rollup.xlsx",
            "private_user_facing_workbook",
        ),
        (
            review / f"catalog_private_human_legacy_START_HERE_{PRIVATE_ROLLUP_SUFFIX}.csv",
            review / "private/current/private_start_here.csv",
            "private_summary_metrics",
        ),
        (
            review / f"catalog_private_human_legacy_year_panel_{PRIVATE_ROLLUP_SUFFIX}.csv",
            review / "private/current/private_year_panel.csv",
            "private_year_panel",
        ),
        (
            review / f"catalog_private_human_legacy_institution_qc_{PRIVATE_ROLLUP_SUFFIX}.csv",
            review / "private/current/private_institution_qc.csv",
            "private_institution_qc",
        ),
        (
            review / f"catalog_private_human_legacy_private_status_{PRIVATE_ROLLUP_SUFFIX}.csv",
            review / "private/current/private_status.csv",
            "private_status",
        ),
        (
            review / f"catalog_private_no_human_legacy_fresh_discovery_queue_{PRIVATE_ROLLUP_SUFFIX}.csv",
            review / "private/current/private_no_human_legacy_fresh_discovery_queue.csv",
            "private_fresh_discovery_queue",
        ),
        (
            logs / f"catalog_private_human_legacy_rollup_{PRIVATE_ROLLUP_SUFFIX}.md",
            logs / "private/current/private_human_legacy_rollup_summary.md",
            "private_rollup_summary",
        ),
    ]


def copy_private_current(repo_root: Path, *, run_id: str) -> None:
    archive_interim = repo_root / INTERIM_DIR / "private/archive" / PRIVATE_SMOKE_SUFFIX
    archive_logs = repo_root / LOG_DIR / "private/archive" / PRIVATE_SMOKE_SUFFIX
    archive_interim.mkdir(parents=True, exist_ok=True)
    archive_logs.mkdir(parents=True, exist_ok=True)
    smoke_sources = list((repo_root / INTERIM_DIR).glob(f"catalog_private_*_{PRIVATE_SMOKE_SUFFIX}.csv"))
    if not smoke_sources:
        smoke_sources = list((repo_root / INTERIM_DIR / "archive").glob(f"pre_namespace_*/catalog_private_*_{PRIVATE_SMOKE_SUFFIX}.csv"))
    for source in smoke_sources:
        shutil.copy2(source, archive_interim / source.name)
    smoke_log = repo_root / LOG_DIR / f"phase_private_discovery_summary_{PRIVATE_SMOKE_SUFFIX}.md"
    if not smoke_log.exists():
        matches = sorted((repo_root / LOG_DIR / "archive").glob(f"pre_namespace_*/phase_private_discovery_summary_{PRIVATE_SMOKE_SUFFIX}.md"))
        if matches:
            smoke_log = matches[-1]
    if smoke_log.exists():
        shutil.copy2(smoke_log, archive_logs / smoke_log.name)

    copied_private: list[tuple[str, Path]] = []
    for source, target, role in private_rollup_mappings(repo_root) + private_direct_mappings(repo_root):
        if source.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            copied_private.append((role, target))

    status_path = repo_root / REVIEW_DIR / "private/current/private_stream_status.md"
    status_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Private Stream Status", "", f"Run id: `{run_id}`", ""]
    if copied_private:
        lines.extend(
            [
                "The human-entered private legacy URLs have been advanced to the same catalog-URL rollup stage as the public stream.",
                "",
                "This is not yet policy extraction/classification. It is the trusted human-private catalog URL panel, with inactive legacy URLs queued for retrieval recovery and non-legacy years queued for fresh discovery.",
                "",
                "## Current Private Files",
                "",
            ]
        )
        for role, target in copied_private:
            lines.append(f"- {role}: `{target.resolve()}`")
        lines.extend(
            [
                "",
                "Step 0 automated/LLM-suggested private URLs remain review-gated and are not included in this trusted human-private direct benchmark.",
            ]
        )
    else:
        lines.extend(
            [
                "The private stream is namespaced but not yet in production.",
                "",
                "The existing `private_step0_smoke` outputs were copied into the private archive as a prototype only.",
                "They should not be treated as final private catalog evidence.",
            ]
        )
    lines.extend(["", f"Prototype archive: `{archive_interim.resolve()}`"])
    status_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def should_archive_top_level(path: Path) -> bool:
    if not path.is_file():
        return False
    if path.name in {".gitkeep", ".DS_Store"}:
        return False
    return True


def archive_top_level_outputs(repo_root: Path, *, run_id: str) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for base in [INTERIM_DIR, REVIEW_DIR, LOG_DIR]:
        source_dir = repo_root / base
        target_dir = source_dir / "archive" / f"pre_namespace_{run_id}"
        target_dir.mkdir(parents=True, exist_ok=True)
        for source in sorted(source_dir.iterdir()):
            if not should_archive_top_level(source):
                continue
            target = target_dir / source.name
            if target.exists():
                raise FileExistsError(f"Archive target already exists: {target}")
            shutil.move(str(source), str(target))
            rows.append(
                {
                    "run_id": run_id,
                    "folder": base.name,
                    "original_path": str(source.resolve()),
                    "archived_path": str(target.resolve()),
                    "byte_size": target.stat().st_size,
                    "sha256": sha256_file(target),
                }
            )
    return pd.DataFrame(rows)


def write_archive_note(repo_root: Path, *, run_id: str, archive_manifest: pd.DataFrame) -> Path:
    note = repo_root / LOG_DIR / "archive" / "README.md"
    manifest_path = repo_root / LOG_DIR / "archive" / f"pre_namespace_{run_id}_manifest.csv"
    note.parent.mkdir(parents=True, exist_ok=True)
    archive_manifest.to_csv(manifest_path, index=False)
    note.write_text(
        "\n".join(
            [
                "# Generated Output Archive",
                "",
                "This folder stores superseded generated outputs that were moved out of the top-level",
                "`interim`, `review`, and `logs` folders during the production namespace migration.",
                "",
                f"Latest namespace migration run: `{run_id}`",
                f"Latest archive manifest: `{manifest_path.resolve()}`",
                "",
                "No original Excel, Stata, or R files are stored here.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest_path.resolve()


def write_review_navigation(repo_root: Path, *, run_id: str, archive_manifest_csv: Path) -> Path:
    path = repo_root / REVIEW_DIR / "START_HERE.md"
    path.write_text(
        "\n".join(
            [
                "# Catalog URL Production Outputs",
                "",
                f"Current namespace run: `{run_id}`",
                "",
                "## Public Current",
                "",
                "- Workbook: `public/current/public_catalog_rollup.xlsx`",
                "- Year panel: `public/current/public_year_panel.csv`",
                "- Institution QC: `public/current/public_institution_qc.csv`",
                "- Public status: `public/current/public_status.csv`",
                "- Run manifest: `public/current/public_run_manifest.csv`",
                "",
                "## Private Current",
                "",
                "- Status note: `private/current/private_stream_status.md`",
                "- The private stream is namespaced, but the existing private Step 0 files remain prototype/smoke-test outputs.",
                "",
                "## Combined Current",
                "",
                "- No combined public/private production output has been validated yet.",
                "",
                "## Archive",
                "",
                "- Superseded loose generated files were moved into `interim/archive/`, `review/archive/`, and `logs/archive/`.",
                f"- Archive manifest: `{archive_manifest_csv}`",
                "",
                "Stable `current/` filenames are intentionally not versioned. The run manifest records source files, checksums, git commit, and run id.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path.resolve()


def current_front_door_mappings(repo_root: Path) -> list[tuple[Path, Path]]:
    review = repo_root / REVIEW_DIR
    delivery = repo_root / DELIVERY_DATA_DIR
    return [
        (review / "public/current/public_catalog_rollup.xlsx", delivery / "public_catalog_rollup.xlsx"),
        (review / "public/current/public_start_here.csv", delivery / "public_start_here.csv"),
        (review / "public/current/public_year_panel.csv", delivery / "public_year_panel.csv"),
        (review / "public/current/public_institution_qc.csv", delivery / "public_institution_qc.csv"),
        (review / "public/current/public_status.csv", delivery / "public_status.csv"),
        (
            review / "public/current/public_no_legacy_fresh_discovery_queue.csv",
            delivery / "public_no_legacy_fresh_discovery_queue.csv",
        ),
        (review / "public/current/public_resolution_actions.csv", delivery / "public_resolution_actions.csv"),
        (review / "public/current/public_run_manifest.csv", delivery / "public_run_manifest.csv"),
        (review / "private/current/private_stream_status.md", delivery / "private_stream_status.md"),
        (review / "private/current/private_catalog_rollup.xlsx", delivery / "private_catalog_rollup.xlsx"),
        (review / "private/current/private_start_here.csv", delivery / "private_start_here.csv"),
        (review / "private/current/private_year_panel.csv", delivery / "private_year_panel.csv"),
        (review / "private/current/private_institution_qc.csv", delivery / "private_institution_qc.csv"),
        (review / "private/current/private_status.csv", delivery / "private_status.csv"),
        (
            review / "private/current/private_no_human_legacy_fresh_discovery_queue.csv",
            delivery / "private_no_human_legacy_fresh_discovery_queue.csv",
        ),
        (
            repo_root / LOG_DIR / "private/current/private_human_legacy_rollup_summary.md",
            delivery / "private_human_legacy_rollup_summary.md",
        ),
    ]


def metric_value(metrics: pd.DataFrame, metric: str) -> str:
    if not {"metric", "value"}.issubset(metrics.columns):
        return ""
    matches = metrics.loc[metrics["metric"] == metric, "value"]
    if matches.empty:
        return ""
    return str(matches.iloc[0])


def write_delivery_summaries(repo_root: Path, *, run_id: str) -> None:
    delivery = repo_root / DELIVERY_DATA_DIR
    start_csv = delivery / "public_start_here.csv"
    actions_csv = delivery / "public_resolution_actions.csv"
    manifest_csv = delivery / "public_run_manifest.csv"

    metrics = pd.read_csv(start_csv) if start_csv.exists() else pd.DataFrame(columns=["metric", "value"])
    manifest = pd.read_csv(manifest_csv) if manifest_csv.exists() else pd.DataFrame()
    mismatches = 0
    if not manifest.empty:
        mismatches = int(
            (
                (manifest["sha256"] != manifest["source_sha256"])
                | (manifest["byte_size"] != manifest["source_byte_size"])
            ).sum()
        )

    summary_lines = [
        "# Public Catalog URL Run Summary",
        "",
        f"Delivery run id: `{run_id}`",
        "",
        "## Scope",
        "",
        f"- Public institutions in Phase 2 universe: {metric_value(metrics, 'Public institutions in Phase 2 universe')}",
        f"- Public institutions with at least one public legacy URL: {metric_value(metrics, 'Public institutions with at least one public legacy URL')}",
        f"- Processed in this production legacy-backed run: {metric_value(metrics, 'Processed in this production legacy-backed run')}",
        f"- Public institutions with no public legacy URL; fresh discovery needed: {metric_value(metrics, 'Public institutions with no public legacy URL; fresh discovery needed')}",
        "",
        "## Coverage",
        "",
        f"- Institution-year rows in combined mockup: {metric_value(metrics, 'Institution-year rows in combined mockup')}",
        f"- Institution-year rows with best_url: {metric_value(metrics, 'Institution-year rows with best_url')}",
        f"- Institution-year best_url coverage %: {metric_value(metrics, 'Institution-year best_url coverage %')}",
        f"- Active legacy URLs reproduced: {metric_value(metrics, 'Active legacy URLs reproduced')}",
        f"- Active legacy URL reproduction %: {metric_value(metrics, 'Active legacy URL reproduction %')}",
        f"- Net bracketed gap years added after AI: {metric_value(metrics, 'Net bracketed gap years added after AI')}",
        "",
        "## Provenance",
        "",
        f"- Manifest rows: {len(manifest)}",
        f"- SHA/size mismatches in copied internal current files: {mismatches}",
        "- Detailed source paths and checksums: `public_run_manifest.csv`",
        "- Internal reproducibility files: `policy_scraper/artifacts/policy_data_internal/`",
    ]
    (delivery / "public_run_summary.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    actions = pd.read_csv(actions_csv) if actions_csv.exists() else pd.DataFrame()
    resolution_lines = [
        "# Public Resolution Summary",
        "",
        f"Delivery run id: `{run_id}`",
        "",
        "This file summarizes cleanup and deferred-follow-up actions used to produce the current public catalog URL rollup.",
        "",
    ]
    if actions.empty or not {"resolution_bucket", "unitid", "affected_rows"}.issubset(actions.columns):
        resolution_lines.append("No resolution actions are recorded in `public_resolution_actions.csv`.")
    else:
        resolution_lines.extend(["## Resolution Buckets", ""])
        grouped = (
            actions.groupby("resolution_bucket", dropna=False)
            .agg(institutions=("unitid", "nunique"), affected_rows=("affected_rows", "sum"))
            .reset_index()
            .sort_values("resolution_bucket")
        )
        for _, row in grouped.iterrows():
            resolution_lines.append(
                f"- {row['resolution_bucket']}: {int(row['institutions'])} institutions; {int(row['affected_rows'])} affected rows"
            )
        resolution_lines.extend(
            [
                "",
                "Detailed row-level actions are in `public_resolution_actions.csv`.",
            ]
        )
    (delivery / "public_resolution_summary.md").write_text(
        "\n".join(resolution_lines) + "\n", encoding="utf-8"
    )

    private_start_csv = delivery / "private_start_here.csv"
    private_metrics = (
        pd.read_csv(private_start_csv) if private_start_csv.exists() else pd.DataFrame(columns=["metric", "value"])
    )
    if not private_metrics.empty:
        private_rollup_lines = [
            "# Private Human Legacy Catalog URL Rollup",
            "",
            f"Delivery run id: `{run_id}`",
            "",
            "## Scope",
            "",
            f"- Private institutions in Phase 2 universe: {metric_value(private_metrics, 'Private institutions in Phase 2 universe')}",
            f"- Private institutions with at least one human private legacy URL: {metric_value(private_metrics, 'Private institutions with at least one human private legacy URL')}",
            f"- Processed in this private human-legacy rollup: {metric_value(private_metrics, 'Processed in this private human-legacy rollup')}",
            f"- Private institutions with no human private legacy URL; fresh discovery needed: {metric_value(private_metrics, 'Private institutions with no human private legacy URL; fresh discovery needed')}",
            "",
            "## Coverage",
            "",
            f"- Institution-year rows in private year panel: {metric_value(private_metrics, 'Institution-year rows in private year panel')}",
            f"- Institution-year rows with best_url: {metric_value(private_metrics, 'Institution-year rows with best_url')}",
            f"- Institution-year best_url coverage %: {metric_value(private_metrics, 'Institution-year best_url coverage %')}",
            f"- Human private legacy URL year rows in panel: {metric_value(private_metrics, 'Human private legacy URL year rows in panel')}",
            f"- Direct active human private URL row rate %: {metric_value(private_metrics, 'Direct active human private URL row rate %')}",
            f"- Step 0/LLM suggested URLs included: {metric_value(private_metrics, 'Step 0/LLM suggested URLs included')}",
            "",
            "## QC Status Counts",
            "",
        ]
        for metric, value in private_metrics.loc[
            private_metrics["metric"].astype(str).str.startswith("QC status:")
        ].itertuples(index=False):
            private_rollup_lines.append(f"- {str(metric).replace('QC status: ', '')}: {value}")
        private_rollup_lines.extend(
            [
                "",
                "Detailed year-level rows are in `private_year_panel.csv`.",
                "Institution-level QC is in `private_institution_qc.csv`.",
            ]
        )
        (delivery / "private_human_legacy_rollup_summary.md").write_text(
            "\n".join(private_rollup_lines) + "\n",
            encoding="utf-8",
        )

    if not private_metrics.empty:
        status_lines = [
            "# Private Stream Status",
            "",
            f"Delivery run id: `{run_id}`",
            "",
            "The human-entered private legacy URLs are now at the same catalog-URL rollup stage as the public stream.",
            "",
            "This is not yet policy extraction/classification. It is the trusted human-private catalog URL panel, with inactive legacy URLs queued for retrieval recovery and non-legacy years queued for fresh discovery.",
            "",
            "Open `private_catalog_rollup.xlsx` first.",
            "",
            "Step 0 automated/LLM-suggested private URLs remain review-gated and are not included in this trusted human-private rollup.",
        ]
        (delivery / "private_stream_status.md").write_text(
            "\n".join(status_lines) + "\n",
            encoding="utf-8",
        )


def write_review_current_front_door(repo_root: Path, *, run_id: str) -> Path:
    current_dir = repo_root / DELIVERY_DATA_DIR
    current_dir.mkdir(parents=True, exist_ok=True)
    for source, target in current_front_door_mappings(repo_root):
        if source.exists():
            shutil.copy2(source, target)
    write_delivery_summaries(repo_root, run_id=run_id)
    start_here = current_dir / "START_HERE.md"
    start_here.write_text(
        "\n".join(
            [
                "# Current Review Files",
                "",
                f"Current namespace run: `{run_id}`",
                "",
                "Open this folder for day-to-day review. It contains only the leading data files and short run notes.",
                "",
                "Background outputs needed for reproducibility are stored in `policy_scraper/artifacts/policy_data_internal/`.",
                "That artifacts folder is intentionally ignored by Git.",
                "",
                "## Public",
                "",
                "- `public_catalog_rollup.xlsx`: main public review workbook.",
                "- `public_year_panel.csv`: current public catalog URL panel.",
                "- `public_institution_qc.csv`: institution-level public QC.",
                "- `public_start_here.csv`: public production metrics.",
                "- `public_resolution_actions.csv`: cleanup/deferred follow-up actions.",
                "- `public_run_manifest.csv`: provenance and checksum manifest.",
                "- `public_run_summary.md`: summary of the run that created the rollup.",
                "- `public_resolution_summary.md`: summary of resolution/pass cleanup.",
                "",
                "## Private",
                "",
                "- `private_stream_status.md`: current private-stream status.",
                "- `private_catalog_rollup.xlsx`: main private human-legacy review workbook.",
                "- `private_year_panel.csv`: current private human-legacy catalog URL panel.",
                "- `private_institution_qc.csv`: institution-level private QC.",
                "- `private_start_here.csv`: private production metrics.",
                "- `private_no_human_legacy_fresh_discovery_queue.csv`: private institutions needing fresh discovery because they have no human-private legacy URLs.",
                "- `private_human_legacy_rollup_summary.md`: private human-legacy rollup summary.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return start_here.resolve()


def write_project_start_here(repo_root: Path, *, run_id: str) -> Path:
    project_root = repo_root.parent
    path = project_root / "START_HERE.md"
    path.write_text(
        "\n".join(
            [
                "# Course Repetition IPEDS Project",
                "",
                "Open this first.",
                "",
                "## What To Open",
                "",
                "For review/data work:",
                "",
                "- `policy_data/START_HERE.md`",
                "- `policy_data/public_catalog_rollup.xlsx`",
                "- `policy_data/private_catalog_rollup.xlsx`",
                "",
                "For code:",
                "",
                "- `policy_scraper/README.md`",
                "- `policy_scraper/src/course_policy/`",
                "",
                "## Folder Meaning",
                "",
                "- `policy_scraper/`: code, tests, prompts, and documentation. This is the GitHub-backed repo.",
                "- `policy_data/`: clean delivery packet with the leading review files and run summaries.",
                "- `policy_scraper/artifacts/policy_data_internal/`: ignored local reproducibility artifacts, logs, archives, and source downloads.",
                "",
                f"Current namespace run: `{run_id}`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path.resolve()


def latest_archive_manifest(repo_root: Path) -> Path:
    manifests = sorted((repo_root / LOG_DIR / "archive").glob("pre_namespace_*_manifest.csv"))
    if manifests:
        return manifests[-1].resolve()
    return (repo_root / LOG_DIR / "archive" / "no_archive_manifest_available.csv").resolve()


def run(repo_root: Path, *, run_id: str | None = None, archive_top_level: bool = False) -> ProductionNamespaceOutputs:
    repo_root = repo_root.resolve()
    run_id = clean_run_id(run_id or utc_run_id())
    ensure_stream_dirs(repo_root)
    manifest = copy_public_current(repo_root, run_id=run_id)
    public_manifest_csv, public_manifest_md = write_public_manifest(repo_root, manifest)
    copy_private_current(repo_root, run_id=run_id)
    private_status = (repo_root / REVIEW_DIR / "private/current/private_stream_status.md").resolve()
    archive_manifest_csv = latest_archive_manifest(repo_root)
    if archive_top_level:
        archive_manifest = archive_top_level_outputs(repo_root, run_id=run_id)
        archive_manifest_csv = write_archive_note(repo_root, run_id=run_id, archive_manifest=archive_manifest)
    write_review_navigation(repo_root, run_id=run_id, archive_manifest_csv=archive_manifest_csv)
    write_review_current_front_door(repo_root, run_id=run_id)
    write_project_start_here(repo_root, run_id=run_id)
    return ProductionNamespaceOutputs(
        public_manifest_csv=public_manifest_csv,
        public_manifest_md=public_manifest_md,
        private_status_md=private_status,
        archive_manifest_csv=archive_manifest_csv,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--archive-top-level", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = args.root.resolve() if args.root else repo_root_from_cwd()
    outputs = run(repo_root, run_id=args.run_id, archive_top_level=args.archive_top_level)
    for label, path in outputs.__dict__.items():
        print(f"{label}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
