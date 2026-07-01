from __future__ import annotations

import pandas as pd

from course_policy.production_quality_gate import evaluate_quality_gate, read_csv_if_exists


def year_rows(count: int, *, terms: int, short_no_terms: int = 0) -> pd.DataFrame:
    rows = []
    for index in range(count):
        has_terms = index < terms
        rows.append(
            {
                "unitid": 100000 + index,
                "target_year": 2010,
                "policy_source_id": f"policy-src-{index}",
                "policy_search_status": "policy_terms_found" if has_terms else "no_policy_terms_found",
                "_short_no_terms": index >= terms and index < terms + short_no_terms,
            }
        )
    return pd.DataFrame(rows)


def source_rows(year_review: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for row in year_review.to_dict("records"):
        short = bool(row.get("_short_no_terms"))
        rows.append(
            {
                "policy_source_id": row["policy_source_id"],
                "retrieval_status": "retrieved",
                "text_char_count": 1200 if short else 250000,
                "policy_excerpt_count": 1 if row["policy_search_status"] == "policy_terms_found" else 0,
            }
        )
    return pd.DataFrame(rows)


def combined_rows(count: int, *, informative: int, weak: int = 0) -> pd.DataFrame:
    rows = []
    for index in range(count):
        if index < informative:
            policy_class = "grade_forgiveness"
        elif index < informative + weak:
            policy_class = "unknown"
        else:
            policy_class = "no_relevant_policy"
        rows.append(
            {
                "unitid": 100000 + index,
                "target_year": 2010,
                "api_status": "parsed",
                "api_policy_class": policy_class,
            }
        )
    return pd.DataFrame(rows)


def test_quality_gate_passes_healthy_block() -> None:
    year_review = year_rows(30, terms=26)
    result = evaluate_quality_gate(
        year_reviews=[year_review],
        source_audits=[source_rows(year_review)],
        combined=combined_rows(26, informative=22, weak=2),
    )

    assert result.status == "PASS"
    assert result.metrics["policy_term_rate"] > 0.8
    assert result.metrics["informative_reviewed_rate"] > 0.7


def test_quality_gate_fails_low_yield_short_text_block() -> None:
    year_review = year_rows(30, terms=8, short_no_terms=18)
    result = evaluate_quality_gate(
        year_reviews=[year_review],
        source_audits=[source_rows(year_review)],
        combined=combined_rows(8, informative=4, weak=4),
    )

    assert result.status == "FAIL"
    failed_checks = {check["check"] for check in result.checks if check["status"] == "FAIL"}
    assert "policy_term_rate" in failed_checks
    assert "informative_reviewed_rate" in failed_checks
    assert "short_text_no_terms_rate" in failed_checks


def test_read_csv_if_exists_treats_empty_file_as_empty_frame(tmp_path) -> None:
    empty = tmp_path / "empty.csv"
    empty.write_text("")

    assert read_csv_if_exists(empty).empty
