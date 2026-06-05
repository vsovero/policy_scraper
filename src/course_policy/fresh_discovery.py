"""Controlled fresh-discovery pilot for institutions without a catalog root."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .ai_config import repo_root_from_cwd
from .catalog_retrieval import DEFAULT_TIMEOUT_SECONDS, retrieve_url, save_source_body
from .strict_pilot import extract_pdf_text


DATA_DIR = Path("../data_policy_pipeline")
INTERIM_DIR = DATA_DIR / "interim"
LOG_DIR = DATA_DIR / "logs"

STRICT_INSTITUTIONS_INPUT = INTERIM_DIR / "catalog_pilot_institutions_strict.csv"
FRESH_DISCOVERY_OUTPUT = INTERIM_DIR / "catalog_fresh_discovery_ohsu_strict_pilot.csv"
FRESH_DISCOVERY_SUMMARY_OUTPUT = LOG_DIR / "phase3_fresh_discovery_ohsu_summary.md"

OHSU_UNITID = 209490

OHSU_SEED_ROOTS = [
    {
        "source_root_name": "OHSU Academic Policy",
        "source_root_url": "https://www.ohsu.edu/education/academic-policy",
        "fresh_discovery_method": "official_site_search",
        "root_scope": "institution_wide_academic_policy",
        "source_root_type": "academic_policy_landing_page",
        "first_pass_decision": "possible_policy_root_not_catalog",
        "recommended_next_step": "Use as an institution-wide policy root only if catalog/handbook roots cannot support source coverage.",
    },
    {
        "source_root_name": "OHSU Office of the Registrar",
        "source_root_url": "https://www.ohsu.edu/education/office-registrar",
        "fresh_discovery_method": "official_site_search",
        "root_scope": "institution_wide_registrar",
        "source_root_type": "registrar_landing_page",
        "first_pass_decision": "possible_policy_root_not_catalog",
        "recommended_next_step": "Use to locate dates, deadlines, registration, transfer credit, and university records policies.",
    },
    {
        "source_root_name": "OHSU Policy Manual",
        "source_root_url": "https://www.ohsu.edu/about/policies",
        "fresh_discovery_method": "official_site_search",
        "root_scope": "institution_wide_policy_manual",
        "source_root_type": "policy_manual",
        "first_pass_decision": "possible_policy_root_not_catalog",
        "recommended_next_step": "Evaluate if university-wide grading/repeat policies can substitute for catalog evidence under an exception protocol.",
    },
    {
        "source_root_name": "OHSU University Grading Policy 02-70-020",
        "source_root_url": "https://ohsu.ellucid.com/documents/view/20897/?security=851390364c24e4d64d30c543ebc2e928ba06da2e",
        "fresh_discovery_method": "official_policy_manual_link_followed",
        "root_scope": "institution_wide_grading_policy",
        "source_root_type": "policy_manager_document",
        "first_pass_decision": "use_as_policy_evidence_root",
        "recommended_next_step": "Use as a current institution-wide policy evidence root for repeated/remediated course treatment; historical coverage still needs Wayback or policy revision history.",
    },
    {
        "source_root_name": "OHSU School of Nursing Catalog and Student Handbook",
        "source_root_url": "https://www.ohsu.edu/sites/default/files/2025-09/SoN-Catalog-2025-26.pdf",
        "fresh_discovery_method": "official_site_search",
        "root_scope": "school_specific_undergraduate_catalog",
        "source_root_type": "school_catalog_pdf",
        "first_pass_decision": "wrong_scope_exception_review",
        "recommended_next_step": "Review whether school-specific undergraduate catalogs are acceptable for OHSU because the university appears to organize student handbooks by school/program.",
    },
    {
        "source_root_name": "OHSU Undergraduate Transfer Procedure",
        "source_root_url": "https://www.ohsu.edu/sites/default/files/2021-08/Procedure%2002-70-005%20Undergraduate%20Transfer.pdf",
        "fresh_discovery_method": "official_site_search",
        "root_scope": "institution_wide_undergraduate_policy",
        "source_root_type": "policy_pdf",
        "first_pass_decision": "policy_page_only",
        "recommended_next_step": "Retain as evidence that institution-wide undergraduate policies exist, but do not treat as a catalog root.",
    },
    {
        "source_root_name": "OHSU Education Landing Page",
        "source_root_url": "https://www.ohsu.edu/education/",
        "fresh_discovery_method": "official_site_search",
        "root_scope": "institution_wide_education_landing_page",
        "source_root_type": "education_landing_page",
        "first_pass_decision": "program_structure_context",
        "recommended_next_step": "Use for program/school structure context; not a catalog root.",
    },
]


@dataclass(frozen=True)
class FreshDiscoveryOutputs:
    discovery_table: Path
    summary_report: Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_institutions(repo_root: Path) -> pd.DataFrame:
    return pd.read_csv(repo_root / STRICT_INSTITUTIONS_INPUT, low_memory=False)


def find_ohsu_name(institutions: pd.DataFrame) -> str:
    match = institutions.loc[institutions["unitid"].eq(OHSU_UNITID)]
    if match.empty:
        return "Oregon Health & Science University"
    return str(match.iloc[0]["institution_name"])


def evidence_snippet(result: dict[str, object]) -> str:
    title = str(result.get("page_title", "") or "")
    year_hints = str(result.get("year_hints", "") or "")
    return f"title={title}; year_hints={year_hints}".strip()


def direct_pdf_url(result: dict[str, object]) -> str:
    for record in result.get("link_records", []):
        if record.get("text", "").strip().lower() == "open pdf directly":
            return record.get("url", "")
    return ""


def policy_evidence_from_pdf(repo_root: Path, source_root_name: str, result: dict[str, object]) -> tuple[str, str, str]:
    url = direct_pdf_url(result)
    if not url:
        return "", "", ""
    pdf_result = retrieve_url(url, timeout_seconds=DEFAULT_TIMEOUT_SECONDS)
    if pdf_result["retrieval_status"] not in {"retrieved", "retrieved_truncated"}:
        return url, "", ""
    source_id = source_root_name.lower().replace(" ", "-").replace("/", "-")
    local_path = save_source_body(repo_root, source_id, "fresh_discovery_policy_pdf", url, str(pdf_result["content_type"]), pdf_result["body"])
    text, text_status = extract_pdf_text(local_path, max_pages=10)
    excerpt = repeated_course_excerpt(text)
    return url, str(local_path), f"{text_status}: {excerpt}" if excerpt else text_status


def repeated_course_excerpt(text: str) -> str:
    lower = text.lower()
    positions = [lower.find(term) for term in ["repeated courses", "repeating the course", "remediated courses", "repeat"]]
    positions = [pos for pos in positions if pos >= 0]
    if not positions:
        return ""
    start = max(0, min(positions) - 500)
    end = min(len(text), min(positions) + 1800)
    return " ".join(text[start:end].split())


def build_fresh_discovery_table(
    institutions: pd.DataFrame,
    repo_root: Path,
    *,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> pd.DataFrame:
    institution_name = find_ohsu_name(institutions)
    rows = []
    for idx, seed in enumerate(OHSU_SEED_ROOTS, 1):
        result = retrieve_url(seed["source_root_url"], timeout_seconds=timeout_seconds)
        direct_policy_pdf_url = ""
        local_policy_pdf_path = ""
        policy_evidence_excerpt = ""
        if seed["first_pass_decision"] == "use_as_policy_evidence_root":
            direct_policy_pdf_url, local_policy_pdf_path, policy_evidence_excerpt = policy_evidence_from_pdf(
                repo_root, seed["source_root_name"], result
            )
        rows.append(
            {
                "fresh_discovery_id": f"ohsu-fresh-{idx:02d}",
                "unitid": OHSU_UNITID,
                "institution_name": institution_name,
                "source_root_name": seed["source_root_name"],
                "source_root_url": seed["source_root_url"],
                "fresh_discovery_method": seed["fresh_discovery_method"],
                "root_scope": seed["root_scope"],
                "source_root_type": seed["source_root_type"],
                "first_pass_decision": seed["first_pass_decision"],
                "recommended_next_step": seed["recommended_next_step"],
                "acceptable_policy_evidence_root": seed["first_pass_decision"] == "use_as_policy_evidence_root",
                "retrieval_status": result["retrieval_status"],
                "http_status": result["http_status"],
                "content_type": result["content_type"],
                "page_title": result["page_title"],
                "year_hints": result["year_hints"],
                "link_count": len(result.get("link_records", [])),
                "evidence_snippet": evidence_snippet(result),
                "direct_policy_pdf_url": direct_policy_pdf_url,
                "local_policy_pdf_path": local_policy_pdf_path,
                "policy_evidence_excerpt": policy_evidence_excerpt,
                "acceptable_first_pass_catalog_root": seed["first_pass_decision"] == "use_for_first_pass",
                "needs_exception_review": seed["first_pass_decision"] == "wrong_scope_exception_review",
                "created_at": utc_now(),
            }
        )
    return pd.DataFrame(rows)


def overall_fresh_discovery_status(discovery: pd.DataFrame) -> str:
    if discovery["acceptable_first_pass_catalog_root"].any():
        return "acceptable_catalog_root_found"
    if discovery["acceptable_policy_evidence_root"].any():
        return "acceptable_policy_evidence_root_found"
    if discovery["needs_exception_review"].any():
        return "exception_review_needed"
    if discovery["first_pass_decision"].str.contains("policy", case=False, na=False).any():
        return "policy_roots_found_no_catalog_root"
    return "fresh_discovery_no_root_found"


def write_summary(path: Path, discovery: pd.DataFrame) -> None:
    status = overall_fresh_discovery_status(discovery)
    lines = [
        "# Phase 3 OHSU Fresh Discovery Pilot",
        "",
        f"Generated at: {utc_now()}",
        "",
        "Scope: controlled fresh discovery for OHSU using official OHSU pages and PDFs found through targeted official-site search.",
        "",
        f"- Overall status: {status}",
        f"- Candidate roots reviewed: {len(discovery)}",
        f"- Acceptable first-pass catalog roots: {int(discovery['acceptable_first_pass_catalog_root'].sum())}",
        f"- Acceptable policy evidence roots: {int(discovery['acceptable_policy_evidence_root'].sum())}",
        f"- Roots needing exception review: {int(discovery['needs_exception_review'].sum())}",
        "",
        "## First-Pass Decisions",
        "",
    ]
    for decision, count in discovery["first_pass_decision"].value_counts(dropna=False).items():
        lines.append(f"- {decision}: {count}")
    lines.extend(["", "## Source Roots", ""])
    for _, row in discovery.iterrows():
        lines.append(
            f"- {row['source_root_name']}: {row['first_pass_decision']} "
            f"({row['root_scope']}); {row['source_root_url']}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_fresh_discovery(
    repo_root: Path,
    *,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> FreshDiscoveryOutputs:
    repo_root = repo_root.resolve()
    institutions = read_institutions(repo_root)
    discovery = build_fresh_discovery_table(institutions, repo_root, timeout_seconds=timeout_seconds)
    outputs = FreshDiscoveryOutputs(
        discovery_table=(repo_root / FRESH_DISCOVERY_OUTPUT).resolve(),
        summary_report=(repo_root / FRESH_DISCOVERY_SUMMARY_OUTPUT).resolve(),
    )
    for output_path in outputs.__dict__.values():
        output_path.parent.mkdir(parents=True, exist_ok=True)
    discovery.to_csv(outputs.discovery_table, index=False)
    write_summary(outputs.summary_report, discovery)
    return outputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run controlled OHSU fresh-discovery pilot.")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve() if args.root else repo_root_from_cwd()
    outputs = run_fresh_discovery(root, timeout_seconds=args.timeout_seconds)
    for label, output_path in outputs.__dict__.items():
        print(f"{label}: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
