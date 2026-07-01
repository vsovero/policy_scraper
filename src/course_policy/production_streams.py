"""Canonical stream registry for catalog URL production.

This module does not run discovery. It names the production streams, records
their trust gates, and creates the internal workspace folders where stream
outputs should live.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from .ai_config import repo_root_from_cwd
from .benchmark_protocol import protocol_for_stream


INTERNAL_DATA_DIR = Path("artifacts/policy_data_internal")
STREAM_BASE_DIRS = (
    INTERNAL_DATA_DIR / "interim" / "streams",
    INTERNAL_DATA_DIR / "review" / "streams",
    INTERNAL_DATA_DIR / "logs" / "streams",
    INTERNAL_DATA_DIR / "catalog_sources" / "streams",
    INTERNAL_DATA_DIR / "extracted_text" / "streams",
)
STREAM_SUMMARY_PATH = INTERNAL_DATA_DIR / "logs" / "production_streams_current.md"


@dataclass(frozen=True)
class ProductionStream:
    stream_id: str
    label: str
    sector: str
    source_family: str
    source_seed_types: tuple[str, ...]
    status: str
    current_role: str
    output_namespace: str
    review_gate: str
    run_order: int
    planned_next_action: str
    notes: str


PRODUCTION_STREAMS: tuple[ProductionStream, ...] = (
    ProductionStream(
        stream_id="public_legacy_url",
        label="Public human legacy URLs",
        sector="public_4_year",
        source_family="legacy_url",
        source_seed_types=("public_workbook_human_legacy_url",),
        status="current_catalog_url_component",
        current_role="Reproduce and extend public student/legacy URL evidence before fresh discovery.",
        output_namespace="public/current plus streams/public_legacy_url/current",
        review_gate="catalog_qc_passes_or_defined_stop",
        run_order=10,
        planned_next_action="wrap_existing_public_legacy_modules_in_shared_catalog_pipeline",
        notes=(
            "Legacy URLs are prior evidence and strong leads. They should be "
            "used to recover active sources and gap-fill within documented "
            "bounds, but they do not override a better coherent catalog root."
        ),
    ),
    ProductionStream(
        stream_id="private_human_legacy_url",
        label="Private human legacy URLs",
        sector="private_nonprofit_4_year",
        source_family="legacy_url",
        source_seed_types=("private_workbook_human_legacy_url",),
        status="current_catalog_url_component",
        current_role="Bring private human-entered legacy URLs to the same stage as public legacy URLs.",
        output_namespace="private/current plus streams/private_human_legacy_url/current",
        review_gate="catalog_qc_passes_or_defined_stop",
        run_order=20,
        planned_next_action="wrap_existing_private_legacy_modules_in_shared_catalog_pipeline",
        notes=(
            "This stream excludes automated missing-private suggestions. It is "
            "the trusted private analogue to the public human legacy URL stream."
        ),
    ),
    ProductionStream(
        stream_id="public_fresh_discovery",
        label="Public fresh discovery",
        sector="public_4_year",
        source_family="fresh_discovery",
        source_seed_types=("institution_homepage", "official_catalog_root_search", "ai_assisted_hard_case_triage"),
        status="current_catalog_url_component",
        current_role="Search public institutions or years not resolved by public legacy URLs.",
        output_namespace="public/current plus streams/public_fresh_discovery/current",
        review_gate="source_scope_and_catalog_year_verified",
        run_order=30,
        planned_next_action="standardize_existing_public_fresh_discovery_pipeline_outputs",
        notes=(
            "This is the first true no-legacy route. It should keep AI leads as "
            "suggestions until source scope and catalog-year evidence are verified."
        ),
    ),
    ProductionStream(
        stream_id="private_new_legacy_url",
        label="Private automated/new legacy URL leads",
        sector="private_nonprofit_4_year",
        source_family="unverified_legacy_like_url",
        source_seed_types=(
            "private_workbook_automated_missing_private_url",
            "private_llm_suggested_url_from_legacy_workbook",
        ),
        status="review_gated_workspace_not_final",
        current_role=(
            "Reserved/staging space for private workbook automated/LLM URL leads "
            "that are not approved as final catalog evidence."
        ),
        output_namespace="streams/private_new_legacy_url/current",
        review_gate="verify_official_scope_catalog_year_and_source_type",
        run_order=40,
        planned_next_action="build_and_test_private_new_legacy_url_stream_after_human_private_legacy_is_stable",
        notes=(
            "These URLs may be useful, but they are not human-entered legacy "
            "evidence. They must stay review-gated and cannot become final "
            "catalog evidence until official institution-wide undergraduate "
            "scope and academic-year coverage are confirmed."
        ),
    ),
    ProductionStream(
        stream_id="private_fresh_discovery",
        label="Private fresh discovery",
        sector="private_nonprofit_4_year",
        source_family="fresh_discovery",
        source_seed_types=("institution_homepage", "official_catalog_root_search"),
        status="current_catalog_url_component",
        current_role="Search private institutions with no human-entered private legacy URL using bounded official-site catalog discovery.",
        output_namespace="streams/private_fresh_discovery/current",
        review_gate="source_scope_and_catalog_year_verified",
        run_order=50,
        planned_next_action="run_full_no_human_legacy_private_queue_then_rebuild_combined_catalog_database",
        notes=(
            "This is the private analogue to public_fresh_discovery. It uses "
            "deterministic official-site root/archive probing first; AI rescue "
            "and broad web discovery remain separate follow-up steps."
        ),
    ),
    ProductionStream(
        stream_id="public_clean_no_legacy_holdout",
        label="Public clean no-legacy holdout",
        sector="public_4_year",
        source_family="benchmark_holdout",
        source_seed_types=("institution_homepage", "official_catalog_root_search"),
        status="benchmark_workspace",
        current_role=(
            "Withhold public human legacy URLs and test whether the no-legacy "
            "pipeline can independently find and classify the original truth rows."
        ),
        output_namespace="streams/public_clean_no_legacy_holdout/current",
        review_gate="legacy_truth_withheld_until_scoring",
        run_order=61,
        planned_next_action="run_clean_holdout_until_row_score_reaches_90_percent",
        notes=(
            "This is not a production recovery stream. It exists only to score "
            "the clean no-legacy process against withheld public legacy truth."
        ),
    ),
    ProductionStream(
        stream_id="private_clean_no_legacy_holdout",
        label="Private clean no-legacy holdout",
        sector="private_nonprofit_4_year",
        source_family="benchmark_holdout",
        source_seed_types=("institution_homepage", "official_catalog_root_search"),
        status="benchmark_workspace",
        current_role=(
            "Withhold private human legacy URLs and test whether the no-legacy "
            "pipeline can independently find and classify the original truth rows."
        ),
        output_namespace="streams/private_clean_no_legacy_holdout/current",
        review_gate="legacy_truth_withheld_until_scoring",
        run_order=62,
        planned_next_action="run_clean_holdout_until_row_score_reaches_90_percent",
        notes=(
            "This is the clean private benchmark. Human private legacy URLs are "
            "truth labels for scoring only and must not enter discovery inputs."
        ),
    ),
    ProductionStream(
        stream_id="combined_catalog_url_database",
        label="Combined catalog URL database",
        sector="public_and_private",
        source_family="harmonized_output",
        source_seed_types=(
            "public_legacy_url",
            "private_human_legacy_url",
            "public_fresh_discovery",
            "private_new_legacy_url",
            "private_fresh_discovery",
        ),
        status="current_front_facing_output",
        current_role="Merge validated stream outputs into the flat user-facing catalog URL database.",
        output_namespace="../policy_data plus streams/combined_catalog_url_database/current",
        review_gate="all_included_streams_pass_catalog_qc_or_have_defined_stops",
        run_order=90,
        planned_next_action="regenerate_after_each_stream_stabilizes",
        notes=(
            "This is the delivery object. Audit, benchmark, and student "
            "comparison files should inform upstream fixes, not patch this "
            "database directly."
        ),
    ),
)


def stream_ids() -> list[str]:
    return [stream.stream_id for stream in sorted(PRODUCTION_STREAMS, key=lambda item: item.run_order)]


def get_stream(stream_id: str) -> ProductionStream:
    for stream in PRODUCTION_STREAMS:
        if stream.stream_id == stream_id:
            return stream
    valid = ", ".join(stream_ids())
    raise KeyError(f"Unknown production stream '{stream_id}'. Valid streams: {valid}")


def stream_frame(streams: Iterable[ProductionStream] = PRODUCTION_STREAMS) -> pd.DataFrame:
    rows = []
    for stream in sorted(streams, key=lambda item: item.run_order):
        row = asdict(stream)
        row["source_seed_types"] = "; ".join(stream.source_seed_types)
        protocol = protocol_for_stream(stream.stream_id)
        row["benchmark_protocol"] = protocol.name
        row["counts_as_clean_no_legacy_benchmark"] = protocol.counts_as_clean_no_legacy
        row["benchmark_target_rate"] = "" if protocol.target_rate is None else protocol.target_rate
        rows.append(row)
    return pd.DataFrame(rows)


def stream_workspace_dirs(repo_root: Path, stream_id: str) -> list[Path]:
    get_stream(stream_id)
    dirs = []
    for base in STREAM_BASE_DIRS:
        for tier in ("current", "archive"):
            dirs.append(repo_root / base / stream_id / tier)
    return dirs


def ensure_stream_workspace(repo_root: Path, stream_ids_to_create: Iterable[str] | None = None) -> list[Path]:
    selected = list(stream_ids_to_create or stream_ids())
    created: list[Path] = []
    for stream_id in selected:
        for path in stream_workspace_dirs(repo_root, stream_id):
            path.mkdir(parents=True, exist_ok=True)
            keep = path / ".gitkeep"
            if not keep.exists():
                keep.write_text("", encoding="utf-8")
            created.append(path)
    return created


def write_stream_summary(repo_root: Path) -> Path:
    frame = stream_frame()
    lines = [
        "# Production Stream Registry",
        "",
        "This file is generated from `course_policy.production_streams`.",
        "",
        "The stream registry separates current production work from audit, pilot, and rescue scripts.",
        "A stream is included in final production only after its review gate is satisfied or every gap has a defined stop.",
        "Benchmark roles are separate from production use: human legacy streams can rebuild data and diagnose execution, but they do not count as clean no-legacy discovery benchmarks.",
        "",
        "## Streams",
        "",
        "| Order | Stream | Status | Benchmark role | Clean no-legacy? | Role | Review gate |",
        "|---:|---|---|---|---:|---|---|",
    ]
    for _, row in frame.iterrows():
        lines.append(
            f"| {row['run_order']} | `{row['stream_id']}` | {row['status']} | "
            f"`{row['benchmark_protocol']}` | {row['counts_as_clean_no_legacy_benchmark']} | "
            f"{row['current_role']} | `{row['review_gate']}` |"
        )
    lines.extend(
        [
            "",
            "## Benchmark Rule",
            "",
            "- `legacy_assisted_rebuild`: may use human legacy URLs to rebuild the existing dataset; not a clean benchmark.",
            "- `known_url_execution_diagnostic`: may use valid human URLs to test retrieval/extraction/classification; not a discovery benchmark.",
            "- `clean_no_legacy_benchmark`: must withhold human legacy URLs and legacy-derived source hints; target 90% on a manually validated sample.",
            "",
        ]
    )
    lines.extend(
        [
            "## Private New Legacy URL Space",
            "",
            "`private_new_legacy_url` is intentionally present but marked `review_gated_workspace_not_final`.",
            "It is for automated or LLM-suggested private workbook URL leads, not human-entered legacy URLs.",
            "Rows in that stream must preserve workbook provenance and remain review-gated until source scope and catalog-year evidence are confirmed.",
            "",
            "## Internal Workspace",
            "",
            "For each stream, the pipeline may write `current/` and `archive/` folders under:",
            "",
            "- `artifacts/policy_data_internal/interim/streams/`",
            "- `artifacts/policy_data_internal/review/streams/`",
            "- `artifacts/policy_data_internal/logs/streams/`",
            "- `artifacts/policy_data_internal/catalog_sources/streams/`",
            "- `artifacts/policy_data_internal/extracted_text/streams/`",
            "",
        ]
    )
    path = repo_root / STREAM_SUMMARY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path.resolve()


def main() -> None:
    parser = argparse.ArgumentParser(description="Show or create catalog production stream workspaces.")
    parser.add_argument("--list", action="store_true", help="Print the stream registry as CSV.")
    parser.add_argument("--ensure-workspace", action="store_true", help="Create current/archive folders for streams.")
    parser.add_argument("--write-summary", action="store_true", help="Write a markdown stream summary into logs.")
    parser.add_argument(
        "--stream-id",
        action="append",
        dest="selected_stream_ids",
        help="Limit workspace creation to one stream. Can be passed more than once.",
    )
    args = parser.parse_args()

    repo_root = repo_root_from_cwd(Path.cwd())
    if args.list or (not args.ensure_workspace and not args.write_summary):
        print(stream_frame().to_csv(index=False))
    if args.ensure_workspace:
        created = ensure_stream_workspace(repo_root, args.selected_stream_ids)
        print(f"workspace_dirs_ready: {len(created)}")
    if args.write_summary:
        print(f"summary_path: {write_stream_summary(repo_root)}")


if __name__ == "__main__":
    main()
