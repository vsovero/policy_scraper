"""Build a first-pass source-root plan for Phase 3 catalog discovery."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .ai_config import repo_root_from_cwd


DATA_DIR = Path("../data_policy_pipeline")
INTERIM_DIR = DATA_DIR / "interim"
LOG_DIR = DATA_DIR / "logs"

STRICT_INSTITUTIONS_INPUT = INTERIM_DIR / "catalog_pilot_institutions_strict.csv"
SOURCE_ROOT_PLAN_OUTPUT = INTERIM_DIR / "catalog_source_root_plan_strict_pilot.csv"
ESCALATION_QUEUE_OUTPUT = INTERIM_DIR / "catalog_first_pass_escalation_queue_strict_pilot.csv"
SOURCE_ROOT_SUMMARY_OUTPUT = LOG_DIR / "phase3_source_root_plan_summary.md"

SOURCE_ROOT_COLUMNS = [
    "unitid",
    "institution_name",
    "strict_pilot_rank",
    "source_root_role",
    "source_root_name",
    "source_root_url",
    "source_root_type",
    "root_scope",
    "first_pass_decision",
    "first_ay_observed",
    "last_ay_observed",
    "archive_bound_basis",
    "fallback_order",
    "notes",
    "created_at",
]


@dataclass(frozen=True)
class SourceRootPlanOutputs:
    source_root_plan: Path
    escalation_queue: Path
    summary_report: Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_inputs(repo_root: Path) -> pd.DataFrame:
    return pd.read_csv(repo_root / STRICT_INSTITUTIONS_INPUT, low_memory=False)


def plan_row(
    institutions: pd.DataFrame,
    unitid: int,
    role: str,
    name: str,
    url: str,
    root_type: str,
    scope: str,
    decision: str,
    first_ay: int | str,
    last_ay: int | str,
    bound_basis: str,
    fallback_order: int | str,
    notes: str,
) -> dict[str, object]:
    inst = institutions.loc[institutions["unitid"].eq(unitid)].iloc[0]
    return {
        "unitid": unitid,
        "institution_name": inst["institution_name"],
        "strict_pilot_rank": int(inst["strict_pilot_rank"]),
        "source_root_role": role,
        "source_root_name": name,
        "source_root_url": url,
        "source_root_type": root_type,
        "root_scope": scope,
        "first_pass_decision": decision,
        "first_ay_observed": first_ay,
        "last_ay_observed": last_ay,
        "archive_bound_basis": bound_basis,
        "fallback_order": fallback_order,
        "notes": notes,
        "created_at": utc_now(),
    }


def build_source_root_plan(institutions: pd.DataFrame) -> pd.DataFrame:
    rows = [
        plan_row(
            institutions,
            122597,
            "preferred_first_pass",
            "SFSU Past Bulletin Archive",
            "https://bulletin.sfsu.edu/past-bulletin-archive/",
            "official_catalog_archive",
            "institution_wide_undergraduate_catalog",
            "use_for_first_pass",
            2000,
            2020,
            "observed_archive_link_text",
            1,
            "Clean official archive; direct retrieval covered AY 2000-2020.",
        ),
        plan_row(
            institutions,
            149222,
            "preferred_first_pass",
            "OpenSIUC Undergraduate Catalog/Bulletin Repository Collection",
            "https://opensiuc.lib.siu.edu/ua_bcc/",
            "institution_repository_collection",
            "institution_wide_undergraduate_catalog",
            "use_for_first_pass_with_archive_bounds",
            2000,
            2016,
            "observed_repository_item_titles",
            1,
            "Direct retrieval works with PDF headers. AY 2008 title has a visible typo and remains review-before-retrieval.",
        ),
        plan_row(
            institutions,
            138558,
            "preferred_first_pass",
            "ABAC Catalog Archive via Wayback",
            "https://web.archive.org/web/20230401072525id_/https://tools.abac.edu/Registrar/Catalogs/Archive/",
            "archived_catalog_index",
            "institution_wide_undergraduate_catalog",
            "route_to_ocr_or_visual_review",
            2000,
            2020,
            "observed_archive_link_text",
            1,
            "Catalog candidates exist, but PDFs appear scanned/image-only and need OCR or visual confirmation.",
        ),
        plan_row(
            institutions,
            199139,
            "preferred_first_pass_candidate",
            "DigitalNC UNC Charlotte Catalog Records",
            "https://lib.digitalnc.org/",
            "state_library_digital_archive_collection",
            "institution_wide_undergraduate_catalog",
            "review_as_preferred_root_before_next_retrieval",
            1999,
            2009,
            "observed_search_result_metadata",
            1,
            "DigitalNC appears to provide a coherent UNC Charlotte catalog collection. Automated scraping is blocked by AWS WAF, but record pages and metadata are indexed.",
        ),
        plan_row(
            institutions,
            199139,
            "legacy_prior",
            "Legacy Catalog PDFs",
            "https://catalog.charlotte.edu/",
            "legacy_url_pattern",
            "institution_wide_undergraduate_catalog",
            "use_as_prior_or_corroborating_evidence",
            2001,
            2008,
            "legacy_public_workbook_links",
            2,
            "Legacy links currently provide strict PDF evidence for AY 2001-2004 and AY 2007-2008.",
        ),
        plan_row(
            institutions,
            199139,
            "fallback_official",
            "UNC Charlotte Provost Catalog Nodes",
            "https://provost.charlotte.edu/",
            "official_catalog_archive_pages",
            "institution_wide_undergraduate_catalog",
            "fallback_after_root_review",
            2003,
            2011,
            "observed_page_titles",
            3,
            "Provost nodes fill some gaps but should not silently mix with DigitalNC/legacy roots.",
        ),
        plan_row(
            institutions,
            209490,
            "deferred_policy_lead",
            "OHSU University Grading Policy 02-70-020",
            "https://ohsu.ellucid.com/documents/view/20897/?security=851390364c24e4d64d30c543ebc2e928ba06da2e",
            "policy_manager_document",
            "institution_wide_grading_policy",
            "defer_policy_lead_catalog_first",
            "",
            "",
            "fresh_discovery_official_policy_manual",
            1,
            "Fresh discovery found an OHSU-wide University Grading policy with repeated/remediated course language, but current policy pages are deferred for Phase 3 because historical coverage would require Wayback or revision-history work.",
        ),
        plan_row(
            institutions,
            209490,
            "rejected_wrong_scope",
            "OHSU School of Nursing Lead",
            "",
            "school_specific_lead",
            "school_specific_or_program_specific",
            "wrong_scope_exception_review",
            "",
            "",
            "scope_review",
            2,
            "School-specific catalog/handbook lead remains wrong-scope by default, but may become exception evidence if OHSU does not publish institution-wide catalogs.",
        ),
    ]
    return pd.DataFrame(rows, columns=SOURCE_ROOT_COLUMNS).sort_values(
        ["strict_pilot_rank", "fallback_order", "source_root_role"], na_position="last"
    )


def build_escalation_queue(source_root_plan: pd.DataFrame) -> pd.DataFrame:
    escalation_map = {
        "route_to_ocr_or_visual_review": "ocr_or_visual_review",
        "review_as_preferred_root_before_next_retrieval": "source_root_review",
        "wrong_scope_exception_review": "wrong_scope_exception_review",
    }
    rows = []
    for _, row in source_root_plan.iterrows():
        bucket = escalation_map.get(str(row["first_pass_decision"]), "")
        if not bucket:
            continue
        rows.append(
            {
                "unitid": row["unitid"],
                "institution_name": row["institution_name"],
                "strict_pilot_rank": row["strict_pilot_rank"],
                "escalation_bucket": bucket,
                "source_root_name": row["source_root_name"],
                "source_root_url": row["source_root_url"],
                "reason": row["notes"],
                "recommended_next_step": recommended_next_step(bucket),
                "created_at": utc_now(),
            }
        )
    return pd.DataFrame(rows).sort_values(["strict_pilot_rank", "escalation_bucket"])


def recommended_next_step(bucket: str) -> str:
    steps = {
        "ocr_or_visual_review": "Test OCR or rendered-page catalog-year confirmation before counting strict coverage.",
        "source_root_review": "Decide whether this root replaces mixed legacy/official roots for first-pass discovery.",
        "wrong_scope_exception_review": "Decide whether school-specific catalog/handbook sources are acceptable fallback evidence.",
    }
    return steps[bucket]


def write_summary(path: Path, source_root_plan: pd.DataFrame, escalation_queue: pd.DataFrame) -> None:
    lines = [
        "# Phase 3 Source-Root Plan",
        "",
        f"Generated at: {utc_now()}",
        "",
        "Purpose: convert strict-pilot institution-specific lessons into reusable source-root roles, stop rules, and escalation buckets.",
        "",
        "## Source Root Roles",
        "",
    ]
    for role, count in source_root_plan["source_root_role"].value_counts(dropna=False).items():
        lines.append(f"- {role}: {count}")
    lines.extend(["", "## First-Pass Decisions", ""])
    for decision, count in source_root_plan["first_pass_decision"].value_counts(dropna=False).items():
        lines.append(f"- {decision}: {count}")
    lines.extend(["", "## Escalation Queue", ""])
    if escalation_queue.empty:
        lines.append("- none")
    else:
        for bucket, count in escalation_queue["escalation_bucket"].value_counts(dropna=False).items():
            lines.append(f"- {bucket}: {count}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_source_root_plan(repo_root: Path) -> SourceRootPlanOutputs:
    repo_root = repo_root.resolve()
    institutions = read_inputs(repo_root)
    source_root_plan = build_source_root_plan(institutions)
    escalation_queue = build_escalation_queue(source_root_plan)

    outputs = SourceRootPlanOutputs(
        source_root_plan=(repo_root / SOURCE_ROOT_PLAN_OUTPUT).resolve(),
        escalation_queue=(repo_root / ESCALATION_QUEUE_OUTPUT).resolve(),
        summary_report=(repo_root / SOURCE_ROOT_SUMMARY_OUTPUT).resolve(),
    )
    for output_path in outputs.__dict__.values():
        output_path.parent.mkdir(parents=True, exist_ok=True)
    source_root_plan.to_csv(outputs.source_root_plan, index=False)
    escalation_queue.to_csv(outputs.escalation_queue, index=False)
    write_summary(outputs.summary_report, source_root_plan, escalation_queue)
    return outputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build strict-pilot source-root plan and escalation queue.")
    parser.add_argument("--root", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve() if args.root else repo_root_from_cwd()
    outputs = run_source_root_plan(root)
    for label, output_path in outputs.__dict__.items():
        print(f"{label}: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
