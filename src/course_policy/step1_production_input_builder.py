"""Build explicit inputs for the clean Step 1 production runner.

The builder converts a row-level seed file into the required Step 1 front-door
inputs. It does not read historical pilot folders or old run outputs.
"""

from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .ai_config import repo_root_from_cwd
from .step1_production_runner import (
    HISTORICAL_CASE_PRECHECK_REQUIRED_COLUMNS,
    assert_historical_case_precheck_is_not_source_input,
    contains_forbidden_runtime_reference,
    file_record,
    sha256_file,
    utc_now,
    write_csv,
)


REQUIRED_SEED_COLUMNS = {
    "unitid",
    "institution_name",
    "sector",
    "state",
    "academic_year",
    "target_inclusion_reason",
    "estimation_sample_flag",
    "panel_fill_flag",
    "candidate_url",
    "candidate_generation_method",
    "candidate_rank",
    "review_decision",
    "review_reason",
    "reviewed_by",
    "reviewed_at",
    *HISTORICAL_CASE_PRECHECK_REQUIRED_COLUMNS,
}

TARGET_COLUMNS = [
    "unitid",
    "institution_name",
    "sector",
    "state",
    "academic_year",
    "target_inclusion_reason",
    "estimation_sample_flag",
    "panel_fill_flag",
]

CANDIDATE_COLUMNS = [
    "unitid",
    "institution_name",
    "sector",
    "state",
    "academic_year",
    "candidate_url",
    "candidate_rank",
    "candidate_generation_method",
    "candidate_source_file",
    "candidate_source_type",
    "source_query_or_root",
    "candidate_generated_at",
]

SOURCE_REVIEW_COLUMNS = [
    "unitid",
    "institution_name",
    "sector",
    "state",
    "academic_year",
    "candidate_url",
    "final_url_after_redirect",
    "retrieval_status",
    "http_status",
    "content_type",
    "source_page_title",
    "source_opened",
    "institution_match_confirmed",
    "campus_or_unitid_match_confirmed",
    "source_scope_confirmed",
    "source_type_confirmed",
    "year_coverage_confirmed",
    "archive_child_links_checked",
    "gap_fill_search_completed",
    "panel_consistency_confirmed",
    "source_type",
    "source_year_start",
    "source_year_end",
    "source_year_coverage_note",
    "url_source_bucket",
    "review_decision",
    "review_reason",
    "reviewed_by",
    "reviewed_at",
    "deterministic_search_completed",
    "archive_expansion_completed",
    "api_web_rescue_mode",
    "api_web_rescue_status",
    "api_web_rescue_reason",
    "source_evidence_note",
]

HISTORICAL_CASE_PRECHECK_COLUMNS = [
    "unitid",
    "institution_name",
    "historical_priority_bucket",
    "valid_human_legacy_rows",
    "prior_programmatic_accepted_rows",
    "unreviewed_candidate_lead_rows",
    "failed_attempt_rows",
    "known_source_family_summary",
    "known_failure_pattern_summary",
    "historical_precheck_completed",
    "runtime_input_guardrail_confirmed",
    "precheck_created_by",
    "precheck_created_at",
]


@dataclass(frozen=True)
class ProductionInputBuildResult:
    input_dir: Path
    manifest_path: Path
    target_rows: int
    candidate_rows: int
    review_rows: int
    precheck_rows: int
    evidence_rows: int
    benchmark_rows: int


def clean_text(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except TypeError:
        pass
    return str(value).strip()


def require_seed_columns(seed: pd.DataFrame) -> None:
    missing = sorted(REQUIRED_SEED_COLUMNS.difference(seed.columns))
    if missing:
        raise ValueError(f"Seed file missing required columns: {', '.join(missing)}")


def assert_no_forbidden_seed_values(seed: pd.DataFrame) -> None:
    offenders: list[str] = []
    for column in seed.columns:
        mask = seed[column].map(contains_forbidden_runtime_reference)
        if mask.any():
            offenders.append(column)
    if offenders:
        raise ValueError(
            "Production input seed contains forbidden pilot runtime references: "
            + ", ".join(sorted(set(offenders)))
        )


def with_default_columns(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = frame.copy()
    for column in columns:
        if column not in out.columns:
            out[column] = ""
    return out[columns].copy()


def target_panel_from_seed(seed: pd.DataFrame) -> pd.DataFrame:
    return (
        with_default_columns(seed, TARGET_COLUMNS)
        .sort_values(["unitid", "academic_year"])
        .drop_duplicates(["unitid", "academic_year"], keep="first")
    )


def candidate_ledger_from_seed(seed: pd.DataFrame) -> pd.DataFrame:
    candidates = seed.loc[seed["candidate_url"].map(clean_text).ne("")].copy()
    if candidates.empty:
        return pd.DataFrame(columns=CANDIDATE_COLUMNS)
    return with_default_columns(candidates, CANDIDATE_COLUMNS).sort_values(
        ["unitid", "academic_year", "candidate_rank"]
    )


def source_review_log_from_seed(seed: pd.DataFrame) -> pd.DataFrame:
    return with_default_columns(seed, SOURCE_REVIEW_COLUMNS).sort_values(["unitid", "academic_year"])


def historical_case_precheck_from_seed(seed: pd.DataFrame) -> pd.DataFrame:
    precheck = (
        with_default_columns(seed, HISTORICAL_CASE_PRECHECK_COLUMNS)
        .sort_values(["unitid", "institution_name"])
        .drop_duplicates(["unitid"], keep="first")
    )
    assert_historical_case_precheck_is_not_source_input(precheck)
    return precheck


def write_evidence_cache(seed: pd.DataFrame, input_dir: Path) -> pd.DataFrame:
    cache_dir = input_dir / "source_evidence_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    for _, row in seed.iterrows():
        excerpt = clean_text(row.get("evidence_excerpt"))
        candidate_url = clean_text(row.get("candidate_url"))
        if not excerpt or not candidate_url:
            continue
        unitid = int(row["unitid"])
        year = int(row["academic_year"])
        cache_path = cache_dir / f"{unitid}_{year}_source_evidence.txt"
        cache_path.write_text(excerpt + "\n", encoding="utf-8")
        rows.append(
            {
                "unitid": unitid,
                "academic_year": year,
                "candidate_url": candidate_url,
                "cached_text_path": cache_path.relative_to(input_dir).as_posix(),
                "cached_text_sha256": sha256_file(cache_path),
                "source_body_sha256": sha256_file(cache_path),
            }
        )
    return pd.DataFrame(
        rows,
        columns=[
            "unitid",
            "academic_year",
            "candidate_url",
            "cached_text_path",
            "cached_text_sha256",
            "source_body_sha256",
        ],
    )


def benchmark_key_from_seed(seed: pd.DataFrame) -> pd.DataFrame:
    if "benchmark_url" not in seed.columns:
        return pd.DataFrame(columns=["benchmark_group", "unitid", "institution_name", "academic_year", "benchmark_url"])
    key = seed.loc[seed["benchmark_url"].map(clean_text).ne("")].copy()
    if key.empty:
        return pd.DataFrame(columns=["benchmark_group", "unitid", "institution_name", "academic_year", "benchmark_url"])
    if "benchmark_group" not in key.columns:
        key["benchmark_group"] = "explicit_seed_benchmark"
    return with_default_columns(
        key,
        ["benchmark_group", "unitid", "institution_name", "academic_year", "benchmark_url"],
    ).sort_values(["unitid", "academic_year"])


def write_run_config(
    input_dir: Path,
    *,
    chunk_id: str,
    release_id: str | None,
    sector_scope: str,
    year_scope: str,
    api_web_mode: str,
    seed_source: str,
) -> None:
    config = {
        "chunk_id": chunk_id,
        "release_id": release_id or "",
        "sector_scope": sector_scope,
        "year_scope": year_scope,
        "api_web_mode": api_web_mode,
        "seed_source": seed_source,
        "created_at": utc_now(),
        "builder": "course_policy.step1_production_input_builder",
    }
    (input_dir / "run_config.json").write_text(json.dumps(config, indent=2, sort_keys=True), encoding="utf-8")


def build_manifest(repo_root: Path, input_dir: Path, seed_csv: Path) -> pd.DataFrame:
    input_files = [
        seed_csv,
        input_dir / "run_config.json",
        input_dir / "target_panel.csv",
        input_dir / "candidate_url_ledger.csv",
        input_dir / "source_review_log.csv",
        input_dir / "historical_case_precheck.csv",
        input_dir / "source_evidence_manifest.csv",
        input_dir / "benchmark_key.csv",
    ]
    records = [
        file_record(path, repo_root=repo_root, role="production_input_builder_input" if path == seed_csv else "production_input")
        for path in input_files
        if path.exists()
    ]
    manifest = pd.DataFrame(records)
    write_csv(manifest, input_dir / "production_input_builder_manifest.csv")
    return manifest


def build_production_inputs_from_seed(
    repo_root: Path,
    *,
    seed_csv: Path,
    input_dir: Path,
    chunk_id: str,
    release_id: str | None = None,
    sector_scope: str = "both",
    year_scope: str = "2002-2016",
    api_web_mode: str = "cached",
    overwrite: bool = False,
) -> ProductionInputBuildResult:
    repo_root = repo_root.resolve()
    seed_csv = seed_csv if seed_csv.is_absolute() else repo_root / seed_csv
    input_dir = input_dir if input_dir.is_absolute() else repo_root / input_dir
    if contains_forbidden_runtime_reference(seed_csv):
        raise ValueError(f"Seed path is not allowed for clean production inputs: {seed_csv}")
    if input_dir.exists():
        if not overwrite:
            raise FileExistsError(f"Input directory already exists: {input_dir}")
        shutil.rmtree(input_dir)
    input_dir.mkdir(parents=True, exist_ok=True)

    seed = pd.read_csv(seed_csv, low_memory=False)
    require_seed_columns(seed)
    assert_no_forbidden_seed_values(seed)

    target_panel = target_panel_from_seed(seed)
    candidate_ledger = candidate_ledger_from_seed(seed)
    source_review = source_review_log_from_seed(seed)
    historical_case_precheck = historical_case_precheck_from_seed(seed)
    evidence = write_evidence_cache(seed, input_dir)
    benchmark_key = benchmark_key_from_seed(seed)

    write_run_config(
        input_dir,
        chunk_id=chunk_id,
        release_id=release_id,
        sector_scope=sector_scope,
        year_scope=year_scope,
        api_web_mode=api_web_mode,
        seed_source=seed_csv.relative_to(repo_root).as_posix() if repo_root in seed_csv.parents else seed_csv.name,
    )
    write_csv(target_panel, input_dir / "target_panel.csv")
    write_csv(candidate_ledger, input_dir / "candidate_url_ledger.csv")
    write_csv(source_review, input_dir / "source_review_log.csv")
    write_csv(historical_case_precheck, input_dir / "historical_case_precheck.csv")
    write_csv(evidence, input_dir / "source_evidence_manifest.csv")
    write_csv(benchmark_key, input_dir / "benchmark_key.csv")
    manifest = build_manifest(repo_root, input_dir, seed_csv)

    return ProductionInputBuildResult(
        input_dir=input_dir,
        manifest_path=input_dir / "production_input_builder_manifest.csv",
        target_rows=len(target_panel),
        candidate_rows=len(candidate_ledger),
        review_rows=len(source_review),
        precheck_rows=len(historical_case_precheck),
        evidence_rows=len(evidence),
        benchmark_rows=len(benchmark_key),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--seed-csv", type=Path, required=True)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--chunk-id", required=True)
    parser.add_argument("--release-id", default=None)
    parser.add_argument("--sector-scope", default="both")
    parser.add_argument("--year-scope", default="2002-2016")
    parser.add_argument("--api-web-mode", default="cached", choices=["cached", "live", "off", "not_eligible"])
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = repo_root_from_cwd(args.root)
    result = build_production_inputs_from_seed(
        repo_root,
        seed_csv=args.seed_csv,
        input_dir=args.input_dir,
        chunk_id=args.chunk_id,
        release_id=args.release_id,
        sector_scope=args.sector_scope,
        year_scope=args.year_scope,
        api_web_mode=args.api_web_mode,
        overwrite=args.overwrite,
    )
    print(
        "built_production_inputs "
        f"input_dir={result.input_dir} "
        f"target_rows={result.target_rows} "
        f"candidate_rows={result.candidate_rows} "
        f"review_rows={result.review_rows} "
        f"evidence_rows={result.evidence_rows} "
        f"benchmark_rows={result.benchmark_rows}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
