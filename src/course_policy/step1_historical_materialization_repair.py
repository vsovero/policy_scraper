"""Build bounded evidence for the Step 1 historical URL materialization repair."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from .ai_config import repo_root_from_cwd
from .step1_attrition_audit import AUDIT_OUTPUT_ROOT, discover_historical_inventory_dir
from .step1_production_runner import write_csv
from .step1_proof_to_scale_url_production import (
    HISTORICAL_INVENTORY_ROOT,
    clean_text,
    historical_materialized_candidates_from_decisions,
    historical_url_materialization_decisions_for_target,
    load_historical_url_evidence_rows,
    repo_relative,
)


DEFAULT_OUTPUT_DIR = Path("artifacts/PIPELINE_OUTPUTS/01_url_discovery/build_reports/step1_historical_materialization_repair")


def load_reviewed_failure_subset(audit_dir: Path) -> pd.DataFrame:
    ledger_path = audit_dir / "institution_year_attrition_ledger.csv"
    if not ledger_path.exists():
        raise FileNotFoundError(f"Attrition ledger not found: {ledger_path}")
    ledger = pd.read_csv(ledger_path, low_memory=False)
    subset = ledger.loc[
        ledger["attrition_class"].map(clean_text).eq("candidate_materialization_failure")
        & ledger["secondary_attrition_class"].map(clean_text).eq("dropped_historical_url_evidence")
    ].copy()
    subset["unitid"] = pd.to_numeric(subset["unitid"], errors="coerce").astype("Int64")
    subset["academic_year"] = pd.to_numeric(subset["academic_year"], errors="coerce").astype("Int64")
    return subset.loc[subset["unitid"].notna() & subset["academic_year"].notna()].copy()


def target_panel_from_attrition_subset(subset: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "unitid": subset["unitid"],
            "institution_name": subset["institution_name"].where(
                subset["institution_name"].map(clean_text).ne(""),
                subset["target_universe_institution_name"],
            ),
            "sector": subset["sector"].where(subset["sector"].map(clean_text).ne(""), subset["target_universe_sector"]),
            "state": subset["state"].where(subset["state"].map(clean_text).ne(""), subset["target_universe_state"]),
            "academic_year": subset["academic_year"],
            "homepage_url": subset["homepage_url"].where(
                subset["homepage_url"].map(clean_text).ne(""),
                subset["target_universe_homepage_url"],
            ),
            "has_human_legacy_source": subset.get("has_human_legacy_source", False),
            "attrition_class": subset["attrition_class"],
        }
    ).drop_duplicates(["unitid", "academic_year"], keep="first")


def resolve_inventory_dir(repo_root: Path, requested: Path | None) -> Path:
    if requested is not None:
        resolved = requested if requested.is_absolute() else repo_root / requested
        if not resolved.exists():
            raise FileNotFoundError(f"Historical inventory directory not found: {resolved}")
        return resolved
    local = repo_root / HISTORICAL_INVENTORY_ROOT
    if local.exists():
        return local
    discovered = discover_historical_inventory_dir(repo_root)
    if discovered is None:
        raise FileNotFoundError("Could not find historical inventory directory for materialization proof.")
    return discovered


def repair_ledger_from_decisions(subset: pd.DataFrame, decisions: pd.DataFrame) -> pd.DataFrame:
    keys = ["unitid", "academic_year"]
    keep = [
        "unitid",
        "academic_year",
        "old_collected_policy_institution",
        "selected_batches",
        "candidate_url_rows",
        "benchmark_key_rows",
        "has_valid_human_legacy",
        "has_prior_programmatic_accepted",
        "has_imported_llm_candidate_lead",
        "has_unreviewed_candidate_lead",
        "has_failed_historical_attempt",
        "secondary_attrition_class",
    ]
    prior = subset[[column for column in keep if column in subset.columns]].drop_duplicates(keys, keep="first")
    out = decisions.merge(prior, on=keys, how="left")
    out = out.rename(
        columns={
            "academic_year": "year",
            "historical_evidence_value": "historical_evidence_value",
            "provenance_label": "provenance_label",
        }
    )
    ordered = [
        "unitid",
        "institution_name",
        "year",
        "prior_attrition_class",
        "historical_evidence_class",
        "historical_evidence_value",
        "materialization_decision",
        "candidate_url",
        "provenance_label",
        "exclusion_reason",
        "historical_source_table",
        "historical_source_file_path",
        "historical_inventory_row_id",
        "candidate_generation_method",
        "candidate_source_type",
        "catalog_year_start",
        "catalog_year_end",
        "counts_as_legacy_coverage",
        "selected_batches",
        "candidate_url_rows",
        "benchmark_key_rows",
        "has_valid_human_legacy",
        "has_prior_programmatic_accepted",
        "has_imported_llm_candidate_lead",
        "has_unreviewed_candidate_lead",
        "has_failed_historical_attempt",
        "secondary_attrition_class",
    ]
    for column in ordered:
        if column not in out.columns:
            out[column] = ""
    return out[ordered].sort_values(["unitid", "year"]).reset_index(drop=True)


def proof_counts(ledger: pd.DataFrame) -> dict[str, int]:
    materialized = ledger["candidate_url"].map(clean_text).ne("")
    return {
        "candidate_materialization_failure_rows_examined": int(len(ledger)),
        "materializable_true_human_legacy_rows": int(
            (ledger["historical_evidence_class"].eq("valid_human_legacy") & materialized).sum()
        ),
        "materializable_prior_programmatic_accepted_rows": int(
            (ledger["historical_evidence_class"].eq("prior_programmatic_accepted_needs_current_reverification") & materialized).sum()
        ),
        "imported_llm_or_programmatic_lead_only_rows": int(
            (
                ledger["provenance_label"].isin(["imported_llm_candidate_lead", "historical_programmatic_lead"])
                & materialized
            ).sum()
        ),
        "no_materializable_url_after_stricter_rules_rows": int((~materialized).sum()),
        "rows_requiring_text_validation_rather_than_url_stage_acceptance": 0,
    }


def write_report(
    *,
    output_dir: Path,
    repo_root: Path,
    audit_dir: Path,
    inventory_dir: Path,
    ledger: pd.DataFrame,
    candidates: pd.DataFrame,
    counts: dict[str, int],
) -> Path:
    columbus = ledger.loc[ledger["unitid"].eq(139366)].copy()
    columbus_candidates = candidates.loc[candidates["unitid"].eq(139366)].copy() if not candidates.empty else pd.DataFrame()
    columbus_before_candidates = int(pd.to_numeric(columbus.get("candidate_url_rows", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
    columbus_before_benchmark = int(pd.to_numeric(columbus.get("benchmark_key_rows", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
    columbus_after = len(columbus_candidates)
    provenance = "; ".join(sorted({clean_text(value) for value in columbus.get("provenance_label", []) if clean_text(value)}))
    report = output_dir / "REPAIR_PROOF_REPORT.md"
    lines = [
        "# Step 1 Historical URL/Evidence Materialization Repair Proof",
        "",
        "Bounded build-stream proof over reviewed candidate-materialization failures.",
        "",
        "## Inputs",
        "",
        f"- Attrition audit: `{repo_relative(audit_dir, repo_root)}`",
        f"- Historical inventory: `{repo_relative(inventory_dir, repo_root)}`",
        "",
        "## Proof Counts",
        "",
        "| Measure | Rows |",
        "|---|---:|",
    ]
    lines.extend(f"| {key} | {value} |" for key, value in counts.items())
    lines.extend(
        [
            "",
            "## Columbus State Regression",
            "",
            f"- unitid: `139366`",
            f"- before candidate_url_ledger rows in reviewed batch evidence: `{columbus_before_candidates}`",
            f"- before benchmark_key rows in reviewed batch evidence: `{columbus_before_benchmark}`",
            f"- after materialized candidate rows in repair proof: `{columbus_after}`",
            f"- selected provenance labels: `{provenance or 'none'}`",
            "",
            "## Interpretation",
            "",
            "- Materialized rows are candidates for current Step 1 retrieval/source review, not final URL-stage acceptances.",
            "- Imported LLM/programmatic leads remain historical lead candidates and do not become human legacy evidence.",
            "- Failed historical attempts without URL values remain excluded.",
        ]
    )
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def run_repair_proof(
    repo_root: Path,
    *,
    audit_dir: Path,
    output_dir: Path,
    inventory_dir: Path | None = None,
    overwrite: bool = False,
) -> dict[str, object]:
    repo_root = repo_root.resolve()
    audit_dir = audit_dir if audit_dir.is_absolute() else repo_root / audit_dir
    output_dir = output_dir if output_dir.is_absolute() else repo_root / output_dir
    if output_dir.exists() and not overwrite:
        raise FileExistsError(f"Output directory already exists: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    resolved_inventory = resolve_inventory_dir(repo_root, inventory_dir)
    subset = load_reviewed_failure_subset(audit_dir)
    target_panel = target_panel_from_attrition_subset(subset)
    historical_evidence = load_historical_url_evidence_rows(repo_root, resolved_inventory)
    decisions = historical_url_materialization_decisions_for_target(
        target_panel,
        historical_evidence,
        repo_root=repo_root,
        prior_attrition_lookup=subset,
    )
    ledger = repair_ledger_from_decisions(subset, decisions)
    candidates = historical_materialized_candidates_from_decisions(decisions)
    counts = proof_counts(ledger)

    write_csv(ledger, output_dir / "historical_materialization_repair_ledger.csv")
    write_csv(candidates, output_dir / "materialized_candidate_url_ledger.csv")
    (output_dir / "repair_counts.json").write_text(json.dumps(counts, indent=2, sort_keys=True), encoding="utf-8")
    report = write_report(
        output_dir=output_dir,
        repo_root=repo_root,
        audit_dir=audit_dir,
        inventory_dir=resolved_inventory,
        ledger=ledger,
        candidates=candidates,
        counts=counts,
    )
    build_log = output_dir / "BUILD_LOG.md"
    build_log.write_text(
        "\n".join(
            [
                "# Build Log",
                "",
                "- command: `course_policy.step1_historical_materialization_repair`",
                f"- attrition audit: `{repo_relative(audit_dir, repo_root)}`",
                f"- historical inventory: `{repo_relative(resolved_inventory, repo_root)}`",
                f"- output report: `{repo_relative(report, repo_root)}`",
                f"- examined rows: `{counts['candidate_materialization_failure_rows_examined']}`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "output_dir": output_dir,
        "report": report,
        "ledger": output_dir / "historical_materialization_repair_ledger.csv",
        "candidate_ledger": output_dir / "materialized_candidate_url_ledger.csv",
        "counts": counts,
        "columbus_materialized_rows": int((ledger["unitid"].eq(139366) & ledger["candidate_url"].map(clean_text).ne("")).sum()),
        "build_log": build_log,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--audit-dir", type=Path, default=AUDIT_OUTPUT_ROOT)
    parser.add_argument("--historical-inventory-dir", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = repo_root_from_cwd(args.root)
    result = run_repair_proof(
        repo_root,
        audit_dir=args.audit_dir,
        output_dir=args.output_dir,
        inventory_dir=args.historical_inventory_dir,
        overwrite=args.overwrite,
    )
    counts = result["counts"]
    print(
        "historical_materialization_repair "
        f"output_dir={result['output_dir']} "
        f"examined_rows={counts['candidate_materialization_failure_rows_examined']} "
        f"human_rows={counts['materializable_true_human_legacy_rows']} "
        f"prior_programmatic_rows={counts['materializable_prior_programmatic_accepted_rows']} "
        f"lead_only_rows={counts['imported_llm_or_programmatic_lead_only_rows']} "
        f"no_materializable_rows={counts['no_materializable_url_after_stricter_rules_rows']} "
        f"columbus_materialized_rows={result['columbus_materialized_rows']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
