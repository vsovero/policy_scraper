import pandas as pd
import pytest

from course_policy.benchmark_protocol import (
    CLEAN_NO_LEGACY_BENCHMARK,
    KNOWN_URL_EXECUTION_DIAGNOSTIC,
    assert_clean_no_legacy_frame,
    clean_no_legacy_row_eligible,
    protocol_for_stream,
)


def test_human_legacy_stream_is_known_url_diagnostic_not_clean_benchmark():
    protocol = protocol_for_stream("private_human_legacy_url")

    assert protocol.name == KNOWN_URL_EXECUTION_DIAGNOSTIC
    assert protocol.may_use_human_legacy_url_for_rebuild is True
    assert protocol.may_use_human_legacy_url_for_benchmark is True
    assert protocol.counts_as_clean_no_legacy is False
    assert protocol.target_rate == 0.90


def test_fresh_discovery_stream_is_clean_no_legacy_benchmark():
    protocol = protocol_for_stream("public_fresh_discovery")

    assert protocol.name == CLEAN_NO_LEGACY_BENCHMARK
    assert protocol.may_use_human_legacy_url_for_rebuild is False
    assert protocol.may_use_human_legacy_url_for_benchmark is False
    assert protocol.counts_as_clean_no_legacy is True
    assert protocol.target_rate == 0.90


def test_clean_holdout_stream_is_clean_no_legacy_benchmark():
    protocol = protocol_for_stream("private_clean_no_legacy_holdout")

    assert protocol.name == CLEAN_NO_LEGACY_BENCHMARK
    assert protocol.may_use_human_legacy_url_for_benchmark is False
    assert protocol.counts_as_clean_no_legacy is True


def test_clean_no_legacy_row_rejects_legacy_hints():
    clean_row = {
        "source_stream": "private_fresh_discovery",
        "best_url": "https://example.edu/catalog/2019",
        "best_url_source": "official_homepage_catalog_archive",
        "legacy_url": "",
        "source_trust_level": "pipeline_discovered",
        "source_seed_types": "institution_homepage",
    }
    cheated_row = {
        **clean_row,
        "legacy_url": "https://example.edu/legacy-human-url.pdf",
    }

    assert clean_no_legacy_row_eligible(clean_row) is True
    assert clean_no_legacy_row_eligible(cheated_row) is False


def test_clean_no_legacy_frame_guard_raises_on_human_legacy_source():
    frame = pd.DataFrame(
        [
            {
                "source_stream": "public_fresh_discovery",
                "best_url_source": "official_homepage_catalog_archive",
                "legacy_url": "",
                "source_trust_level": "pipeline_discovered",
                "source_seed_types": "institution_homepage",
            },
            {
                "source_stream": "public_legacy_url",
                "best_url_source": "public_human_legacy_url",
                "legacy_url": "https://example.edu/catalog.pdf",
                "source_trust_level": "human_legacy_prior",
                "source_seed_types": "public_workbook_human_legacy_url",
            },
        ]
    )

    with pytest.raises(ValueError, match="Clean no-legacy benchmark contains"):
        assert_clean_no_legacy_frame(frame)
