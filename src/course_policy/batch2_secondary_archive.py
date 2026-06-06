"""Test bounded secondary institutional archive expansion for batch 2."""

from __future__ import annotations

import argparse
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .ai_config import repo_root_from_cwd
from .batch2_runthrough import BATCH2_RUNTHROUGH_YEAR_SUMMARY_OUTPUT
from .catalog_retrieval import retrieve_url, save_source_body
from .institution_universe import TARGET_END_YEAR, TARGET_START_YEAR


DATA_DIR = Path("../data_policy_pipeline")
INTERIM_DIR = DATA_DIR / "interim"
LOG_DIR = DATA_DIR / "logs"

BATCH2_SECONDARY_ARCHIVE_CANDIDATES_OUTPUT = INTERIM_DIR / "catalog_batch2_secondary_archive_candidates.csv"
BATCH2_SECONDARY_ARCHIVE_YEAR_SUMMARY_OUTPUT = INTERIM_DIR / "catalog_batch2_secondary_archive_year_summary.csv"
BATCH2_SECONDARY_ARCHIVE_SUMMARY_OUTPUT = LOG_DIR / "phase3_batch2_secondary_archive_summary.md"

UNC_UNITID = 127741
UNC_NAME = "University of Northern Colorado"
UNC_PREFERRED_ROOT_START = 2011
UNC_OAI_BASE_URL = "https://digarch.unco.edu/oai/request"
UNC_DIGITAL_ARCHIVE_SETS = {
    "node:11204": "Catalogs 2000-2009",
    "node:11650": "Catalogs 2010-2019",
}
OAI_NS = {"o": "http://www.openarchives.org/OAI/2.0/"}


@dataclass(frozen=True)
class Batch2SecondaryArchiveOutputs:
    candidates: Path
    year_summary: Path
    summary_report: Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_year_summary(repo_root: Path) -> pd.DataFrame:
    return pd.read_csv(repo_root / BATCH2_RUNTHROUGH_YEAR_SUMMARY_OUTPUT, low_memory=False)


def fetch_url(url: str, timeout_seconds: int = 30) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return response.read()


def list_oai_records(set_spec: str) -> list[bytes]:
    records = []
    url = (
        UNC_OAI_BASE_URL
        + "?verb=ListRecords&metadataPrefix=mdRecord&set="
        + urllib.parse.quote(set_spec)
    )
    while url:
        data = fetch_url(url)
        records.append(data)
        root = ET.fromstring(data)
        token = root.findtext(".//o:resumptionToken", namespaces=OAI_NS)
        url = (
            UNC_OAI_BASE_URL + "?verb=ListRecords&resumptionToken=" + urllib.parse.quote(token)
            if token
            else ""
        )
    return records


def record_texts(record: ET.Element) -> list[str]:
    return [elem.text.strip() for elem in record.iter() if elem.text and elem.text.strip()]


def parse_catalog_year_range(text: str) -> tuple[int, int] | None:
    match = re.search(r"((?:19|20)\d{2})\s*[-–—_/]\s*((?:19|20)?\d{2})", text)
    if not match:
        return None
    start = int(match.group(1))
    end_text = match.group(2)
    end = int(end_text) if len(end_text) == 4 else int(str(start)[:2] + end_text)
    if not (TARGET_START_YEAR <= start <= TARGET_END_YEAR and start < end <= TARGET_END_YEAR + 2):
        return None
    return start, end


def is_undergraduate_or_combined_catalog(title: str) -> bool:
    lowered = title.lower()
    if "catalog" not in lowered:
        return False
    if "addendum" in lowered or "supplemental" in lowered:
        return False
    if "undergraduate and graduate catalog" in lowered:
        return True
    graduate_check = lowered.replace("undergraduate", "")
    return "undergraduate" in lowered and "graduate catalog" not in graduate_check


def node_url_from_texts(texts: list[str]) -> str:
    for text in texts:
        if text.startswith("https://digarch.unco.edu/node/"):
            return text
    return ""


def object_id_from_identifier(identifier: str) -> str:
    match = re.search(r"node-(\d+)$", identifier)
    return match.group(1) if match else ""


def extract_candidate_rows(set_spec: str, set_name: str, xml_pages: list[bytes]) -> list[dict[str, object]]:
    rows = []
    for page in xml_pages:
        root = ET.fromstring(page)
        for record in root.findall(".//o:record", OAI_NS):
            identifier = record.findtext("o:header/o:identifier", namespaces=OAI_NS) or ""
            texts = record_texts(record)
            title = ""
            for text in texts:
                if parse_catalog_year_range(text) and "catalog" in text.lower():
                    title = text
            if not title:
                continue
            range_match = parse_catalog_year_range(title)
            if not range_match:
                continue
            start, end = range_match
            if not title:
                continue
            if not is_undergraduate_or_combined_catalog(title):
                continue
            node_url = node_url_from_texts(texts)
            object_id = object_id_from_identifier(identifier)
            for target_year in range(start, end):
                if not (TARGET_START_YEAR <= target_year < UNC_PREFERRED_ROOT_START):
                    continue
                rows.append(
                    {
                        "unitid": UNC_UNITID,
                        "institution_name": UNC_NAME,
                        "target_year": target_year,
                        "catalog_year_start": start,
                        "catalog_year_end": end,
                        "candidate_url": node_url,
                        "candidate_title": title,
                        "secondary_source_root_url": UNC_OAI_BASE_URL,
                        "secondary_source_root_name": set_name,
                        "secondary_source_set_spec": set_spec,
                        "oai_identifier": identifier,
                        "digital_object_id": object_id,
                        "candidate_method": "institutional_digital_archive_gap_fill",
                        "source_root_role": "secondary_institutional_digital_archive",
                        "catalog_year_evidence_type": "oai_metadata_title",
                        "catalog_body_access_status": "not_tested",
                        "catalog_body_retrieval_status": "",
                        "catalog_body_http_status": "",
                        "catalog_body_content_type": "",
                        "created_at": utc_now(),
                    }
                )
    if not rows:
        return rows
    deduped: dict[tuple[int, str], dict[str, object]] = {}
    for row in rows:
        deduped[(int(row["target_year"]), str(row["candidate_url"]))] = row
    return list(deduped.values())


def test_catalog_body_access(candidates: pd.DataFrame) -> pd.DataFrame:
    out = candidates.copy()
    access_rows = []
    for _, row in out.drop_duplicates("candidate_url").iterrows():
        result = retrieve_url(str(row["candidate_url"]), max_bytes=250_000)
        access_rows.append(
            {
                "candidate_url": row["candidate_url"],
                "catalog_body_access_status": (
                    "catalog_body_retrieved"
                    if result["retrieval_status"] in {"retrieved", "retrieved_truncated"}
                    and "verify that you're not a robot" not in result["body"].decode("utf-8", errors="ignore").lower()
                    else "blocked_or_challenge_page"
                ),
                "catalog_body_retrieval_status": result["retrieval_status"],
                "catalog_body_http_status": result["http_status"],
                "catalog_body_content_type": result["content_type"],
            }
        )
    access = pd.DataFrame(access_rows)
    return out.drop(
        columns=[
            "catalog_body_access_status",
            "catalog_body_retrieval_status",
            "catalog_body_http_status",
            "catalog_body_content_type",
        ],
        errors="ignore",
    ).merge(access, on="candidate_url", how="left")


def build_year_summary(existing_year_summary: pd.DataFrame, secondary_candidates: pd.DataFrame) -> pd.DataFrame:
    unc = existing_year_summary.loc[existing_year_summary["unitid"].eq(UNC_UNITID)].copy()
    candidate_years = set(secondary_candidates["target_year"].astype(int)) if not secondary_candidates.empty else set()
    rows = []
    for _, row in unc.iterrows():
        target_year = int(row["target_year"])
        current_status = row["batch2_year_status"]
        has_secondary = target_year in candidate_years
        rows.append(
            {
                "unitid": UNC_UNITID,
                "institution_name": UNC_NAME,
                "target_year": target_year,
                "prior_batch2_year_status": current_status,
                "has_preferred_root_candidate": bool(row["has_root_archive_candidate"]),
                "has_legacy_gap_fill_candidate": bool(row["has_legacy_gap_fill_candidate"]),
                "has_secondary_archive_candidate": has_secondary,
                "post_secondary_archive_status": (
                    "preferred_root_candidate"
                    if bool(row["has_root_archive_candidate"])
                    else "secondary_institutional_archive_candidate"
                    if has_secondary
                    else "secondary_archive_gap_unfilled"
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(["unitid", "target_year"])


def write_summary(path: Path, candidates: pd.DataFrame, year_summary: pd.DataFrame) -> None:
    lines = [
        "# Phase 3 Batch 2 Secondary Archive Test",
        "",
        f"Generated at: {utc_now()}",
        "",
        "Scope: bounded UNC Digital Archive OAI expansion from institutional catalog sets only.",
        "",
        "## Source Roots",
        "",
    ]
    for set_spec, set_name in UNC_DIGITAL_ARCHIVE_SETS.items():
        lines.append(f"- {set_spec}: {set_name}")
    lines.extend(["", "## Candidate Coverage", ""])
    candidate_years = sorted(candidates["target_year"].astype(int).unique()) if not candidates.empty else []
    lines.append(f"- Secondary archive candidate years: {candidate_years or 'none'}")
    filled = year_summary.loc[
        year_summary["post_secondary_archive_status"].eq("secondary_institutional_archive_candidate"),
        "target_year",
    ].astype(int).tolist()
    still_missing = year_summary.loc[
        year_summary["post_secondary_archive_status"].eq("secondary_archive_gap_unfilled"),
        "target_year",
    ].astype(int).tolist()
    preferred = year_summary.loc[
        year_summary["post_secondary_archive_status"].eq("preferred_root_candidate"),
        "target_year",
    ].astype(int).tolist()
    lines.append(f"- Preferred root years retained: {preferred or 'none'}")
    lines.append(f"- Years newly filled by secondary archive candidates: {filled or 'none'}")
    lines.append(f"- Years still unfilled after secondary archive expansion: {still_missing or 'none'}")
    lines.extend(["", "## Body Access", ""])
    if candidates.empty:
        lines.append("- none")
    else:
        for status, count in candidates["catalog_body_access_status"].value_counts(dropna=False).items():
            lines.append(f"- {status}: {count}")
    lines.extend(["", "## Notes", ""])
    lines.append("- OAI metadata gives explicit catalog-year evidence and bounded set provenance.")
    lines.append("- Direct catalog body URLs are WAF/challenge-blocked from the current pipeline environment, so text extraction still needs a browser/manual/approved access path.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_batch2_secondary_archive(repo_root: Path) -> Batch2SecondaryArchiveOutputs:
    repo_root = repo_root.resolve()
    xml_pages_by_set = {set_spec: list_oai_records(set_spec) for set_spec in UNC_DIGITAL_ARCHIVE_SETS}
    for set_spec, pages in xml_pages_by_set.items():
        for index, page in enumerate(pages, 1):
            save_source_body(
                repo_root,
                f"batch2-secondary-unco-{set_spec.replace(':', '-')}-{index}",
                "oai_records",
                UNC_OAI_BASE_URL,
                "application/xml",
                page,
            )
    rows = []
    for set_spec, pages in xml_pages_by_set.items():
        rows.extend(extract_candidate_rows(set_spec, UNC_DIGITAL_ARCHIVE_SETS[set_spec], pages))
    candidates = pd.DataFrame(rows)
    if not candidates.empty:
        candidates = test_catalog_body_access(candidates).sort_values(["unitid", "target_year", "candidate_url"])
    year_summary = build_year_summary(read_year_summary(repo_root), candidates)

    outputs = Batch2SecondaryArchiveOutputs(
        candidates=(repo_root / BATCH2_SECONDARY_ARCHIVE_CANDIDATES_OUTPUT).resolve(),
        year_summary=(repo_root / BATCH2_SECONDARY_ARCHIVE_YEAR_SUMMARY_OUTPUT).resolve(),
        summary_report=(repo_root / BATCH2_SECONDARY_ARCHIVE_SUMMARY_OUTPUT).resolve(),
    )
    for output_path in outputs.__dict__.values():
        output_path.parent.mkdir(parents=True, exist_ok=True)
    candidates.to_csv(outputs.candidates, index=False)
    year_summary.to_csv(outputs.year_summary, index=False)
    write_summary(outputs.summary_report, candidates, year_summary)
    return outputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run batch-2 bounded secondary institutional archive test.")
    parser.add_argument("--root", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve() if args.root else repo_root_from_cwd()
    outputs = run_batch2_secondary_archive(root)
    for label, output_path in outputs.__dict__.items():
        print(f"{label}: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
