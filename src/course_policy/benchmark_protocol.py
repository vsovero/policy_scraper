"""Benchmark protocol labels and guardrails.

The project has two different objectives that must stay separate:

1. Rebuild the existing policy dataset. This may use human legacy URLs and
   other legacy evidence as assists.
2. Validate the no-legacy pipeline. This may not use human legacy URLs or
   legacy-derived source hints as benchmark evidence.

This module gives those objectives explicit names so reports and tests do not
collapse them into one ambiguous "coverage" number.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import pandas as pd


LEGACY_ASSISTED_REBUILD = "legacy_assisted_rebuild"
KNOWN_URL_EXECUTION_DIAGNOSTIC = "known_url_execution_diagnostic"
CLEAN_NO_LEGACY_BENCHMARK = "clean_no_legacy_benchmark"
REVIEW_GATED_LEAD = "review_gated_lead"
COMBINED_DELIVERY = "combined_delivery"
UNKNOWN_PROTOCOL = "unknown_protocol"

HUMAN_LEGACY_STREAMS = {"public_legacy_url", "private_human_legacy_url"}
CLEAN_NO_LEGACY_STREAMS = {
    "public_fresh_discovery",
    "private_fresh_discovery",
    "public_clean_no_legacy_holdout",
    "private_clean_no_legacy_holdout",
}
REVIEW_GATED_LEAD_STREAMS = {"private_new_legacy_url"}

LEGACY_HINT_COLUMNS = (
    "legacy_url",
    "legacy_excerpt",
    "legacy_policy_class",
    "legacy_link_id",
)
LEGACY_HINT_SOURCE_VALUES = {
    "human_legacy_prior",
    "public_workbook_human_legacy_url",
    "private_workbook_human_legacy_url",
}


@dataclass(frozen=True)
class BenchmarkProtocol:
    name: str
    label: str
    counts_as_clean_no_legacy: bool
    may_use_human_legacy_url_for_rebuild: bool
    may_use_human_legacy_url_for_benchmark: bool
    target_rate: float | None
    notes: str


PROTOCOLS: dict[str, BenchmarkProtocol] = {
    LEGACY_ASSISTED_REBUILD: BenchmarkProtocol(
        name=LEGACY_ASSISTED_REBUILD,
        label="Legacy-assisted rebuild",
        counts_as_clean_no_legacy=False,
        may_use_human_legacy_url_for_rebuild=True,
        may_use_human_legacy_url_for_benchmark=False,
        target_rate=None,
        notes=(
            "Production rebuild may use human legacy URLs, corrected legacy URLs, "
            "legacy excerpts, archives, and manual leads. This does not prove "
            "the no-legacy discovery pipeline works."
        ),
    ),
    KNOWN_URL_EXECUTION_DIAGNOSTIC: BenchmarkProtocol(
        name=KNOWN_URL_EXECUTION_DIAGNOSTIC,
        label="Known-URL execution diagnostic",
        counts_as_clean_no_legacy=False,
        may_use_human_legacy_url_for_rebuild=True,
        may_use_human_legacy_url_for_benchmark=True,
        target_rate=0.90,
        notes=(
            "Given a valid human URL, the system should retrieve, extract, "
            "find policy text, classify, and match. This diagnoses execution, "
            "not independent discovery."
        ),
    ),
    CLEAN_NO_LEGACY_BENCHMARK: BenchmarkProtocol(
        name=CLEAN_NO_LEGACY_BENCHMARK,
        label="Clean no-legacy benchmark",
        counts_as_clean_no_legacy=True,
        may_use_human_legacy_url_for_rebuild=False,
        may_use_human_legacy_url_for_benchmark=False,
        target_rate=0.90,
        notes=(
            "The system starts without human legacy URLs or legacy-derived "
            "source hints. It must independently find, retrieve, extract, and "
            "classify the source on a manually validated sample."
        ),
    ),
    REVIEW_GATED_LEAD: BenchmarkProtocol(
        name=REVIEW_GATED_LEAD,
        label="Review-gated lead",
        counts_as_clean_no_legacy=False,
        may_use_human_legacy_url_for_rebuild=False,
        may_use_human_legacy_url_for_benchmark=False,
        target_rate=None,
        notes="Automated or LLM-suggested leads require source review before final use.",
    ),
    COMBINED_DELIVERY: BenchmarkProtocol(
        name=COMBINED_DELIVERY,
        label="Combined delivery",
        counts_as_clean_no_legacy=False,
        may_use_human_legacy_url_for_rebuild=True,
        may_use_human_legacy_url_for_benchmark=False,
        target_rate=None,
        notes="Merged output object; benchmark it through its component streams.",
    ),
    UNKNOWN_PROTOCOL: BenchmarkProtocol(
        name=UNKNOWN_PROTOCOL,
        label="Unknown protocol",
        counts_as_clean_no_legacy=False,
        may_use_human_legacy_url_for_rebuild=False,
        may_use_human_legacy_url_for_benchmark=False,
        target_rate=None,
        notes="Unrecognized stream; do not use as a benchmark without classification.",
    ),
}


def protocol_name_for_stream(source_stream: str) -> str:
    stream = str(source_stream or "").strip()
    if stream in HUMAN_LEGACY_STREAMS:
        return KNOWN_URL_EXECUTION_DIAGNOSTIC
    if stream in CLEAN_NO_LEGACY_STREAMS:
        return CLEAN_NO_LEGACY_BENCHMARK
    if stream in REVIEW_GATED_LEAD_STREAMS:
        return REVIEW_GATED_LEAD
    if stream == "combined_catalog_url_database":
        return COMBINED_DELIVERY
    return UNKNOWN_PROTOCOL


def protocol_for_stream(source_stream: str) -> BenchmarkProtocol:
    return PROTOCOLS[protocol_name_for_stream(source_stream)]


def clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def row_has_legacy_hint(row: Mapping[str, object]) -> bool:
    for column in LEGACY_HINT_COLUMNS:
        if clean_text(row.get(column)):
            return True
    source_trust = clean_text(row.get("source_trust_level"))
    if source_trust in LEGACY_HINT_SOURCE_VALUES:
        return True
    source_seed_types = clean_text(row.get("source_seed_types")).lower()
    if "legacy" in source_seed_types:
        return True
    best_url_source = clean_text(row.get("best_url_source")).lower()
    if "legacy" in best_url_source:
        return True
    return False


def clean_no_legacy_row_eligible(row: Mapping[str, object]) -> bool:
    protocol = protocol_for_stream(clean_text(row.get("source_stream")))
    return protocol.counts_as_clean_no_legacy and not row_has_legacy_hint(row)


def assert_clean_no_legacy_frame(frame: pd.DataFrame) -> None:
    """Raise if a clean benchmark frame contains legacy-assisted rows."""
    if frame.empty:
        return
    offenders = []
    for idx, row in frame.iterrows():
        if not clean_no_legacy_row_eligible(row):
            offenders.append(idx)
    if offenders:
        preview = ", ".join(str(i) for i in offenders[:10])
        raise ValueError(
            "Clean no-legacy benchmark contains legacy-assisted or non-clean rows "
            f"at index positions: {preview}"
        )
