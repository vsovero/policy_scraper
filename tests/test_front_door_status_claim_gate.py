from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

FRONT_DOOR_FILES = [
    REPO_ROOT / "artifacts/PIPELINE_OUTPUTS/CURRENT_STATUS_AND_NEXT_STEPS.md",
    REPO_ROOT / "artifacts/PIPELINE_OUTPUTS/01_url_discovery/README.md",
]

PROCESS_REVIEW_DIR = REPO_ROOT / "artifacts/PIPELINE_OUTPUTS/01_url_discovery/process_reviews"
STEP1_RUN_CONTRACT = (
    REPO_ROOT
    / "docs/replication_standards/codex_goals/step_1_url_discovery_run_contract.md"
)

CHUNK_ID_RE = re.compile(r"\bproduction_chunk_[A-Za-z0-9_]+\b")

PASS_CLAIM_PATTERNS = [
    re.compile(r"\b(?:passes|passed)\b", re.IGNORECASE),
    re.compile(r":\s*(?:pass|partial pass)\b", re.IGNORECASE),
    re.compile(r"\b\d+\s*/\s*\d+\s+(?:pass|passed)\b", re.IGNORECASE),
    re.compile(r"\brequirements?\s+(?:pass|passed)\b", re.IGNORECASE),
    re.compile(r"\bverifier\s*:\s*pass\b", re.IGNORECASE),
]

EXPLICIT_REVIEW_FAIL_PATTERNS = [
    re.compile(r"current-stage decision[^:\n]*:\s*\*\*\s*fail", re.IGNORECASE),
    re.compile(r"\bFAIL\s+for\b", re.IGNORECASE),
    re.compile(r"review decision is that[^.\n]*not ready", re.IGNORECASE),
]

EXPLICIT_REVIEW_PASS_PATTERNS = [
    re.compile(r"current-stage decision[^:\n]*:\s*\*\*\s*pass", re.IGNORECASE),
    re.compile(r"\bPASS\s+for\b", re.IGNORECASE),
    re.compile(r"\bpassed\s+Gate\s+1\s+and\s+Gate\s+2\b", re.IGNORECASE),
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _process_review_text() -> str:
    chunks: list[str] = []
    for path in sorted(PROCESS_REVIEW_DIR.glob("*.md")):
        chunks.append(_read(path))
    return "\n\n".join(chunks)


def _section_containing(text: str, needle: str) -> str:
    start = text.find(needle)
    if start == -1:
        return ""
    section_start = text.rfind("\n## ", 0, start)
    if section_start == -1:
        section_start = 0
    else:
        section_start += 1
    section_end = text.find("\n## ", start)
    if section_end == -1:
        section_end = len(text)
    return text[section_start:section_end]


def _pass_claim_hits(text: str) -> list[str]:
    hits: list[str] = []
    for pattern in PASS_CLAIM_PATTERNS:
        for match in pattern.finditer(text):
            line_start = text.rfind("\n", 0, match.start()) + 1
            line_end = text.find("\n", match.end())
            if line_end == -1:
                line_end = len(text)
            hits.append(text[line_start:line_end].strip())
    return hits


def _review_section_for_chunk(review_text: str, chunk_id: str) -> str:
    return _section_containing(review_text, chunk_id)


def _has_explicit_review_fail(review_section: str) -> bool:
    return any(pattern.search(review_section) for pattern in EXPLICIT_REVIEW_FAIL_PATTERNS)


def _has_explicit_review_pass(review_section: str) -> bool:
    return any(pattern.search(review_section) for pattern in EXPLICIT_REVIEW_PASS_PATTERNS)


def test_front_door_pass_claims_require_matching_process_review() -> None:
    review_text = _process_review_text()
    failures: list[str] = []

    for front_door in FRONT_DOOR_FILES:
        if not front_door.exists():
            continue
        text = _read(front_door)
        for chunk_id in sorted(set(CHUNK_ID_RE.findall(text))):
            section = _section_containing(text, chunk_id)
            hits = _pass_claim_hits(section)
            if not hits:
                continue

            rel_path = front_door.relative_to(REPO_ROOT)
            formatted_hits = "\n      ".join(hits)
            review_section = _review_section_for_chunk(review_text, chunk_id)
            if not review_section:
                failures.append(
                    f"{rel_path} makes pass-like claims for {chunk_id}, but no process review mentions it:\n"
                    f"      {formatted_hits}"
                )
                continue

            if _has_explicit_review_fail(review_section):
                failures.append(
                    f"{rel_path} makes pass-like claims for {chunk_id}, but its process-review section "
                    f"contains an explicit fail decision. Use under-review, fail, or positive-evidence wording instead:\n"
                    f"      {formatted_hits}"
                )
            elif not _has_explicit_review_pass(review_section):
                failures.append(
                    f"{rel_path} makes pass-like claims for {chunk_id}, but its process-review section "
                    f"does not explicitly pass it:\n"
                    f"      {formatted_hits}"
                )

    assert not failures, (
        "Front-door status files may not promote generated pass claims before a matching "
        "process review exists.\n\n" + "\n\n".join(failures)
    )


def test_step1_goal_contract_does_not_treat_under_review_as_completion() -> None:
    text = re.sub(r"\s+", " ", _read(STEP1_RUN_CONTRACT).lower())

    required_phrases = [
        "journal-ready step 1 successful test batch goal",
        "not acceptable stopping points",
        "keep fixing, rerunning, packaging, and reviewing",
        "gate 1 and gate 2 process review passes",
        "only for a real external blocker",
    ]

    missing = [phrase for phrase in required_phrases if phrase not in text]

    assert not missing, (
        "The Step 1 run contract must make clear that under-review/partial/fail "
        "status is not completion for the active successful-test-batch goal. "
        "Missing phrases: " + ", ".join(missing)
    )


def test_step1_contract_separates_human_legacy_from_prior_programmatic() -> None:
    text = re.sub(r"\s+", " ", _read(STEP1_RUN_CONTRACT).lower())

    forbidden_phrases = [
        "legacy/human/prior-programmatic evidence is reported as provenance",
        "prior-programmatic evidence is reported as provenance",
    ]
    forbidden_hits = [phrase for phrase in forbidden_phrases if phrase in text]

    required_phrases = [
        "valid human legacy evidence is reported as provenance when used",
        "prior-programmatic evidence is reported only as diagnostics or benchmark evidence",
        "unless the current run recovers and reviews the source",
    ]
    missing = [phrase for phrase in required_phrases if phrase not in text]

    assert not forbidden_hits, (
        "Prior-programmatic output cannot be treated as source-ledger provenance "
        "unless the current run recovers and reviews it. Forbidden phrases: "
        + ", ".join(forbidden_hits)
    )
    assert not missing, (
        "The Step 1 contract must distinguish human legacy provenance from "
        "prior-programmatic diagnostics. Missing phrases: " + ", ".join(missing)
    )


def test_step1_contract_requires_historical_inventory_runtime_gate() -> None:
    text = re.sub(r"\s+", " ", _read(STEP1_RUN_CONTRACT).lower())

    required_phrases = [
        "historical url discovery inventory contract",
        "cannot feed hidden urls into the production runner",
        "hard gate: the clean step 1 production runner must reject runtime inputs",
        "historical_inventory/",
        "url_discovery_historical_inventory/",
        "institution_priority_buckets",
        "prior programmatic rows into the source ledger by itself",
    ]
    missing = [phrase for phrase in required_phrases if phrase not in text]

    assert not missing, (
        "The Step 1 contract must make historical inventory a planning lane with "
        "a hard runtime-input gate, not a production shortcut. Missing phrases: "
        + ", ".join(missing)
    )


def test_step1_contract_requires_historical_case_precheck_gate() -> None:
    text = re.sub(r"\s+", " ", _read(STEP1_RUN_CONTRACT).lower())

    required_phrases = [
        "historical case precheck gate",
        "historical_case_precheck.csv",
        "one completed precheck row for every target institution",
        "runtime_input_guardrail_confirmed",
        "must reject the precheck if it contains direct urls",
        "the historical case precheck is not source evidence",
    ]
    missing = [phrase for phrase in required_phrases if phrase not in text]

    assert not missing, (
        "The Step 1 contract must require URL-free historical case prechecks "
        "as a hard coding gate before completion claims. Missing phrases: "
        + ", ".join(missing)
    )
