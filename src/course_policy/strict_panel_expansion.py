"""Expand strict pilot candidate catalog sources across the 2000-2020 panel."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import pandas as pd

from .ai_config import repo_root_from_cwd
from .catalog_retrieval import retrieve_url
from .institution_universe import TARGET_END_YEAR, TARGET_START_YEAR
from .strict_pilot import STRICT_PILOT_UNITIDS


DATA_DIR = Path("../data_policy_pipeline")
INTERIM_DIR = DATA_DIR / "interim"
LOG_DIR = DATA_DIR / "logs"

INSTITUTION_YEAR_TARGETS_INPUT = INTERIM_DIR / "institution_year_targets.csv"
STRICT_INSTITUTIONS_INPUT = INTERIM_DIR / "catalog_pilot_institutions_strict.csv"
STRICT_YEAR_COVERAGE_INPUT = INTERIM_DIR / "catalog_year_coverage_strict_pilot.csv"

PANEL_CANDIDATES_OUTPUT = INTERIM_DIR / "catalog_panel_candidates_strict_pilot.csv"
PANEL_YEAR_STATUS_OUTPUT = INTERIM_DIR / "catalog_panel_year_status_strict_pilot.csv"
PANEL_SUMMARY_OUTPUT = LOG_DIR / "phase3_strict_panel_expansion_summary.md"


SFSU_ARCHIVE_URL = "https://bulletin.sfsu.edu/past-bulletin-archive/"
SIU_ARCHIVE_URL = "https://opensiuc.lib.siu.edu/ua_bcc/"
ABAC_ARCHIVE_URL = "https://web.archive.org/web/20230401072525id_/https://tools.abac.edu/Registrar/Catalogs/Archive/"

UNC_CHARLOTTE_PROVOST_NODES = {
    2003: "https://provost.charlotte.edu/node/171/",
    2005: "https://provost.charlotte.edu/node/173/",
    2007: "https://provost.charlotte.edu/node/177/",
    2009: "https://provost.charlotte.edu/node/179/",
    2010: "https://provost.charlotte.edu/node/181/",
    2011: "https://provost.charlotte.edu/node/183/",
}

FIRST_PASS_ARCHIVE_BOUNDS = {
    149222: {
        "label": "SIU repository archive page",
        "archive_url": SIU_ARCHIVE_URL,
        "first_ay": 2000,
        "last_ay": 2016,
    },
    199139: {
        "label": "UNC Charlotte Provost catalog archive nodes",
        "archive_url": "https://provost.charlotte.edu/",
        "first_ay": 2003,
        "last_ay": 2011,
    },
}


@dataclass(frozen=True)
class PanelExpansionOutputs:
    candidates: Path
    year_status: Path
    summary_report: Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_inputs(repo_root: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    return (
        pd.read_csv(repo_root / STRICT_INSTITUTIONS_INPUT, low_memory=False),
        pd.read_csv(repo_root / INSTITUTION_YEAR_TARGETS_INPUT, low_memory=False),
        pd.read_csv(repo_root / STRICT_YEAR_COVERAGE_INPUT, low_memory=False),
    )


def parse_catalog_year_range(text: str) -> tuple[int, int] | None:
    match = re.search(r"((?:19|20|22)\d{2})\s*(?:-|–|—|/|\s+to\s+)\s*((?:19|20)?\d{2})", text)
    if not match:
        return None
    start = int(match.group(1))
    end_text = match.group(2)
    end = int(end_text) if len(end_text) == 4 else int(str(start)[:2] + end_text)
    if start > 2030 and 1990 <= end <= 2035:
        start = end - 1
    if 1990 <= start <= 2030 and start < end <= 2035:
        return start, end
    return None


def candidate_row(
    source_id: str,
    unitid: int,
    institution_name: str,
    candidate_url: str,
    source_title: str,
    catalog_year_start: int,
    catalog_year_end: int,
    discovery_method: str,
    source_kind: str,
    source_status: str,
    archive_page_url: str,
    review_reason: str = "",
) -> dict[str, object]:
    return {
        "source_id": source_id,
        "unitid": unitid,
        "institution_name": institution_name,
        "candidate_url": candidate_url,
        "source_title": source_title,
        "catalog_year_start": catalog_year_start,
        "catalog_year_end": catalog_year_end,
        "discovery_method": discovery_method,
        "source_kind": source_kind,
        "source_status": source_status,
        "archive_page_url": archive_page_url,
        "needs_human_review": bool(review_reason),
        "review_reason": review_reason,
        "created_at": utc_now(),
    }


def normalize_wayback_url(url: str) -> str:
    return url.replace("https:/tools.", "https://tools.").replace("http:/tools.", "http://tools.")


def discover_sfsu() -> list[dict[str, object]]:
    result = retrieve_url(SFSU_ARCHIVE_URL)
    rows = []
    for record in result.get("link_records", []):
        text = record.get("text", "")
        if "SF State" not in text or "Bulletin" not in text:
            continue
        coverage = parse_catalog_year_range(text)
        if not coverage:
            continue
        start, end = coverage
        if end <= TARGET_START_YEAR or start > TARGET_END_YEAR:
            continue
        rows.append(
            candidate_row(
                f"panel-sfsu-{start:04d}-{end:04d}",
                122597,
                "San Francisco State University",
                record["url"],
                text,
                start,
                end,
                "institution_archive_page",
                "undergraduate_bulletin_page",
                "ready_for_retrieval",
                SFSU_ARCHIVE_URL,
            )
        )
    return rows


def discover_siu() -> list[dict[str, object]]:
    result = retrieve_url(SIU_ARCHIVE_URL)
    rows = []
    for record in result.get("link_records", []):
        text = record.get("text", "")
        if "Undergraduate" not in text or "Catalog" not in text and "Bulletin" not in text:
            continue
        coverage = parse_catalog_year_range(text)
        if not coverage:
            continue
        start, end = coverage
        if end <= TARGET_START_YEAR or start > TARGET_END_YEAR:
            continue
        review_reason = "Archive title appears to contain a year typo; verify before using." if "2208-2009" in text else ""
        rows.append(
            candidate_row(
                f"panel-siu-{start:04d}-{end:04d}",
                149222,
                "Southern Illinois University-Carbondale",
                record["url"],
                text,
                start,
                end,
                "institution_repository_archive",
                "undergraduate_catalog_repository_item",
                "ready_for_retrieval" if not review_reason else "review_before_retrieval",
                SIU_ARCHIVE_URL,
                review_reason,
            )
        )
    return rows


def discover_abac() -> list[dict[str, object]]:
    result = retrieve_url(ABAC_ARCHIVE_URL)
    rows = []
    for record in result.get("link_records", []):
        text = record.get("text", "")
        if not text.lower().endswith(".pdf"):
            continue
        coverage = parse_catalog_year_range(text)
        if not coverage:
            continue
        start, end = coverage
        if end <= TARGET_START_YEAR or start > TARGET_END_YEAR:
            continue
        rows.append(
            candidate_row(
                f"panel-abac-{start:04d}-{end:04d}",
                138558,
                "Abraham Baldwin Agricultural College",
                normalize_wayback_url(record["url"]),
                text,
                start,
                end,
                "wayback_archive_index",
                "undergraduate_catalog_pdf",
                "scanned_pdf_needs_ocr_or_visual_review",
                ABAC_ARCHIVE_URL,
                "ABAC archive PDFs may be scanned/image-only; require OCR or visual catalog-year confirmation.",
            )
        )
    return rows


def discover_unc_charlotte() -> list[dict[str, object]]:
    rows = []
    for start, url in UNC_CHARLOTTE_PROVOST_NODES.items():
        result = retrieve_url(url)
        title = result.get("page_title", "")
        coverage = parse_catalog_year_range(title)
        if not coverage:
            continue
        start, end = coverage
        rows.append(
            candidate_row(
                f"panel-uncc-{start:04d}-{end:04d}",
                199139,
                "University of North Carolina at Charlotte",
                url,
                title,
                start,
                end,
                "provost_catalog_archive_page",
                "undergraduate_catalog_archive_page",
                "ready_for_retrieval",
                "https://provost.charlotte.edu/",
            )
        )
    return rows


def discover_ohsu(institutions: pd.DataFrame) -> list[dict[str, object]]:
    name = institutions.loc[institutions["unitid"].eq(209490), "institution_name"].iloc[0]
    return [
        candidate_row(
            f"panel-ohsu-missing-{year}",
            209490,
            name,
            "",
            f"No institution-wide undergraduate catalog lead found for AY {year}",
            year,
            year + 1,
            "fresh_discovery_needed",
            "missing_institution_wide_undergraduate_catalog",
            "fresh_discovery_needed",
            "",
            "Legacy lead is missing or wrong-scope; search must start from institution-wide undergraduate catalog/bulletin or official undergraduate academic policy source.",
        )
        for year in range(TARGET_START_YEAR, TARGET_END_YEAR + 1)
    ]


def build_candidates(institutions: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    rows.extend(discover_sfsu())
    rows.extend(discover_siu())
    rows.extend(discover_abac())
    rows.extend(discover_unc_charlotte())
    rows.extend(discover_ohsu(institutions))
    candidates = pd.DataFrame(rows)
    if candidates.empty:
        return candidates
    candidates = candidates.drop_duplicates(subset=["unitid", "candidate_url", "catalog_year_start", "catalog_year_end"])
    return candidates.sort_values(["unitid", "catalog_year_start", "catalog_year_end", "candidate_url"])


def build_year_status(
    institutions: pd.DataFrame,
    targets: pd.DataFrame,
    strict_year_coverage: pd.DataFrame,
    candidates: pd.DataFrame,
) -> pd.DataFrame:
    panel = targets[targets["unitid"].isin(STRICT_PILOT_UNITIDS)].rename(columns={"year": "target_year"}).copy()
    panel = panel.merge(
        institutions[["unitid", "strict_pilot_rank", "strict_pilot_reason"]],
        on="unitid",
        how="left",
    )
    strict = strict_year_coverage[["unitid", "target_year", "has_strict_catalog_source", "source_id"]].rename(
        columns={"source_id": "current_strict_source_id"}
    )
    panel = panel.merge(strict, on=["unitid", "target_year"], how="left")
    panel["has_strict_catalog_source"] = panel["has_strict_catalog_source"].fillna(False)

    expanded = []
    for _, source in candidates.iterrows():
        for year in range(int(source["catalog_year_start"]), int(source["catalog_year_end"])):
            if TARGET_START_YEAR <= year <= TARGET_END_YEAR:
                expanded.append(
                    {
                        "unitid": source["unitid"],
                        "target_year": year,
                        "candidate_source_id": source["source_id"],
                        "candidate_url": source["candidate_url"],
                        "candidate_title": source["source_title"],
                        "candidate_status": source["source_status"],
                        "candidate_review_reason": source["review_reason"],
                    }
                )
    candidate_years = pd.DataFrame(expanded)
    if candidate_years.empty:
        panel["candidate_source_id"] = ""
    else:
        candidate_years = candidate_years.sort_values(["unitid", "target_year", "candidate_status", "candidate_source_id"])
        candidate_years = candidate_years.groupby(["unitid", "target_year"], as_index=False).first()
        panel = panel.merge(candidate_years, on=["unitid", "target_year"], how="left")
    panel["candidate_status"] = panel["candidate_status"].fillna("no_candidate_found")
    panel = apply_first_pass_archive_guardrails(panel)
    panel.loc[panel["has_strict_catalog_source"], "candidate_status"] = "already_strict_covered"
    panel.loc[panel["has_strict_catalog_source"], "candidate_review_reason"] = ""
    return panel.sort_values(["strict_pilot_rank", "unitid", "target_year"])


def apply_first_pass_archive_guardrails(panel: pd.DataFrame) -> pd.DataFrame:
    out = panel.copy()
    if "candidate_review_reason" not in out.columns:
        out["candidate_review_reason"] = ""
    out["candidate_review_reason"] = out["candidate_review_reason"].fillna("")
    for unitid, bounds in FIRST_PASS_ARCHIVE_BOUNDS.items():
        before_archive = (
            out["unitid"].eq(unitid)
            & out["candidate_status"].eq("no_candidate_found")
            & out["target_year"].lt(int(bounds["first_ay"]))
        )
        after_archive = (
            out["unitid"].eq(unitid)
            & out["candidate_status"].eq("no_candidate_found")
            & out["target_year"].gt(int(bounds["last_ay"]))
        )
        before_reason = (
            f"First-pass hard stop: {bounds['label']} starts at AY {bounds['first_ay']}; "
            f"target year is earlier than the first catalog candidate found from this source. "
            f"Do not spend deeper-search resources on this earlier-year gap until the archive-limit queue is revisited. "
            f"Archive/source checked: {bounds['archive_url']}"
        )
        after_reason = (
            f"First-pass hard stop: {bounds['label']} ends at AY {bounds['last_ay']}; "
            f"target year is later than the last catalog candidate found from this source. "
            f"Do not spend deeper-search resources on this later-year gap until the archive-limit queue is revisited. "
            f"Archive/source checked: {bounds['archive_url']}"
        )
        out.loc[before_archive, "candidate_status"] = "official_archive_lower_bound_reached"
        out.loc[before_archive, "candidate_review_reason"] = before_reason
        out.loc[after_archive, "candidate_status"] = "official_archive_upper_bound_reached"
        out.loc[after_archive, "candidate_review_reason"] = after_reason
    return out


def write_summary(path: Path, candidates: pd.DataFrame, year_status: pd.DataFrame) -> None:
    lines = [
        "# Phase 3 Strict Panel Expansion",
        "",
        f"Generated at: {utc_now()}",
        "",
        "Scope: expand candidate catalog coverage across AY 2000-2020 for the 5 strict-pilot institutions only. This step records candidates and review status; it does not retrieve every candidate source or classify policies.",
        "",
        "Status definitions:",
        "",
        "- already_strict_covered: existing strict pilot source already covers the institution-year.",
        "- ready_for_retrieval: candidate source has explicit catalog-year context from an archive/index page and can be retrieved next.",
        "- scanned_pdf_needs_ocr_or_visual_review: candidate appears to cover the year, but text extraction is not sufficient for strict automated confirmation.",
        "- review_before_retrieval: candidate has a known ambiguity, such as a catalog-year typo, that should be checked before use.",
        "- fresh_discovery_needed: existing leads are missing or wrong-scope, so discovery should restart from an institution-wide undergraduate source.",
        "- official_archive_lower_bound_reached: first-pass official archive/index source starts after the target year; stop earlier-year search for now and revisit later only if needed.",
        "- official_archive_upper_bound_reached: first-pass official archive/index source ends before the target year; stop later-year search for now and revisit later only if needed.",
        "- no_candidate_found: deterministic archive expansion did not identify a candidate for that year.",
        "",
        "## Candidate Sources",
        "",
    ]
    for status, count in candidates["source_status"].value_counts(dropna=False).items():
        lines.append(f"- {status}: {count}")
    lines.extend(["", "## Institution-Year Status", ""])
    for status, count in year_status["candidate_status"].value_counts(dropna=False).items():
        lines.append(f"- {status}: {count}")
    lines.extend(["", "## Institution Summary", ""])
    grouped = year_status.groupby(["unitid", "institution_name"])
    for (unitid, name), group in grouped:
        covered = int(group["has_strict_catalog_source"].sum())
        ready = int(group["candidate_status"].eq("ready_for_retrieval").sum())
        review = int(group["candidate_status"].str.contains("review|ocr|fresh", case=False, na=False).sum())
        archive_limited = int(group["candidate_status"].str.contains("archive_.*_bound", regex=True, na=False).sum())
        lines.append(
            f"- {name} ({unitid}): strict covered {covered}/21; ready candidates {ready}; "
            f"review/fresh discovery {review}; archive-limit hard stops {archive_limited}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_strict_panel_expansion(repo_root: Path) -> PanelExpansionOutputs:
    repo_root = repo_root.resolve()
    institutions, targets, strict_year_coverage = read_inputs(repo_root)
    candidates = build_candidates(institutions)
    year_status = build_year_status(institutions, targets, strict_year_coverage, candidates)

    outputs = PanelExpansionOutputs(
        candidates=(repo_root / PANEL_CANDIDATES_OUTPUT).resolve(),
        year_status=(repo_root / PANEL_YEAR_STATUS_OUTPUT).resolve(),
        summary_report=(repo_root / PANEL_SUMMARY_OUTPUT).resolve(),
    )
    for path in outputs.__dict__.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    candidates.to_csv(outputs.candidates, index=False)
    year_status.to_csv(outputs.year_status, index=False)
    write_summary(outputs.summary_report, candidates, year_status)
    return outputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Expand strict pilot catalog candidates across the 2000-2020 panel.")
    parser.add_argument("--root", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve() if args.root else repo_root_from_cwd()
    outputs = run_strict_panel_expansion(root)
    for label, path in outputs.__dict__.items():
        print(f"{label}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
