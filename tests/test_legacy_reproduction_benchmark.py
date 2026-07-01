import pandas as pd

from course_policy.legacy_reproduction_benchmark import (
    between_legacy_gap_denominator,
    read_final_panel,
    normalized_url,
)


def test_normalized_url_ignores_fragment_and_trailing_slash_but_keeps_query():
    assert normalized_url("HTTPS://Example.EDU/catalog/?a=1#section") == "https://example.edu/catalog?a=1"


def test_between_legacy_gap_denominator_counts_only_bracketed_missing_years():
    legacy = pd.DataFrame(
        [
            {"unitid": 1, "target_year": 2000, "legacy_url": "https://example.edu/2000.pdf"},
            {"unitid": 1, "target_year": 2003, "legacy_url": "https://example.edu/2003.pdf"},
            {"unitid": 2, "target_year": 2012, "legacy_url": "https://other.edu/2012.pdf"},
        ]
    )

    assert between_legacy_gap_denominator(legacy) == (1, 2)


def test_read_final_panel_uses_full_mockup_and_overlays_ai_subset(tmp_path):
    review = tmp_path / "artifacts/policy_data_internal/review"
    review.mkdir(parents=True)
    pd.DataFrame(
        [
            {"unitid": 1, "start_year": 2000, "best_url": "https://legacy.edu/2000.pdf", "best_url_source": "legacy"},
            {"unitid": 2, "start_year": 2000, "best_url": "https://other.edu/2000.pdf", "best_url_source": "legacy"},
        ]
    ).to_csv(review / "catalog_url_spotcheck_mockup_sample.csv", index=False)
    pd.DataFrame(
        [
            {
                "unitid": 2,
                "start_year": 2000,
                "post_ai_best_url": "https://other.edu/ai-2000.pdf",
                "post_ai_best_url_source": "ai",
            }
        ]
    ).to_csv(review / "catalog_ai_root_year_coverage_comparison_sample_updated.csv", index=False)

    panel = read_final_panel(tmp_path, suffix="sample", comparison_suffix="sample_updated")

    assert len(panel) == 2
    assert panel.loc[panel["unitid"].eq(1), "post_ai_best_url"].iloc[0] == "https://legacy.edu/2000.pdf"
    assert panel.loc[panel["unitid"].eq(2), "post_ai_best_url"].iloc[0] == "https://other.edu/ai-2000.pdf"


def test_read_final_panel_without_comparison_suffix_does_not_overlay_unsuffixed_file(tmp_path):
    review = tmp_path / "artifacts/policy_data_internal/review"
    review.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [{"unitid": 1, "start_year": 2000, "best_url": "https://legacy.edu/2000.pdf", "best_url_source": "legacy"}]
    ).to_csv(review / "catalog_url_spotcheck_mockup_sample.csv", index=False)
    pd.DataFrame(
        [{"unitid": 1, "start_year": 2000, "post_ai_best_url": "https://wrong-overlay.edu/2000.pdf"}]
    ).to_csv(review / "catalog_ai_root_year_coverage_comparison.csv", index=False)

    panel = read_final_panel(tmp_path, suffix="sample", comparison_suffix="")

    assert panel["post_ai_best_url"].iloc[0] == "https://legacy.edu/2000.pdf"
