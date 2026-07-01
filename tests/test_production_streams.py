from pathlib import Path

from course_policy.production_streams import (
    ensure_stream_workspace,
    get_stream,
    stream_frame,
    stream_ids,
    stream_workspace_dirs,
)


def test_registry_includes_current_and_planned_streams() -> None:
    ids = stream_ids()

    assert ids == [
        "public_legacy_url",
        "private_human_legacy_url",
        "public_fresh_discovery",
        "private_new_legacy_url",
        "private_fresh_discovery",
        "public_clean_no_legacy_holdout",
        "private_clean_no_legacy_holdout",
        "combined_catalog_url_database",
    ]


def test_private_new_legacy_stream_is_review_gated_and_not_final() -> None:
    stream = get_stream("private_new_legacy_url")

    assert stream.status == "review_gated_workspace_not_final"
    assert stream.sector == "private_nonprofit_4_year"
    assert stream.source_family == "unverified_legacy_like_url"
    assert "private_workbook_automated_missing_private_url" in stream.source_seed_types
    assert stream.review_gate == "verify_official_scope_catalog_year_and_source_type"


def test_stream_frame_flattens_source_seed_types() -> None:
    frame = stream_frame()
    row = frame.loc[frame["stream_id"].eq("private_new_legacy_url")].iloc[0]

    assert "private_llm_suggested_url_from_legacy_workbook" in row["source_seed_types"]
    assert row["output_namespace"] == "streams/private_new_legacy_url/current"


def test_stream_frame_labels_benchmark_protocols() -> None:
    frame = stream_frame().set_index("stream_id")

    assert frame.loc["public_legacy_url", "benchmark_protocol"] == "known_url_execution_diagnostic"
    assert frame.loc["private_human_legacy_url", "benchmark_protocol"] == "known_url_execution_diagnostic"
    assert frame.loc["public_fresh_discovery", "benchmark_protocol"] == "clean_no_legacy_benchmark"
    assert frame.loc["private_fresh_discovery", "benchmark_protocol"] == "clean_no_legacy_benchmark"
    assert frame.loc["public_clean_no_legacy_holdout", "benchmark_protocol"] == "clean_no_legacy_benchmark"
    assert frame.loc["private_clean_no_legacy_holdout", "benchmark_protocol"] == "clean_no_legacy_benchmark"
    assert not bool(frame.loc["public_legacy_url", "counts_as_clean_no_legacy_benchmark"])
    assert bool(frame.loc["public_fresh_discovery", "counts_as_clean_no_legacy_benchmark"])
    assert bool(frame.loc["private_clean_no_legacy_holdout", "counts_as_clean_no_legacy_benchmark"])


def test_workspace_dirs_are_stream_scoped(tmp_path: Path) -> None:
    dirs = stream_workspace_dirs(tmp_path, "private_new_legacy_url")

    assert len(dirs) == 10
    assert all("private_new_legacy_url" in str(path) for path in dirs)
    assert any("interim/streams/private_new_legacy_url/current" in str(path) for path in dirs)
    assert any("logs/streams/private_new_legacy_url/archive" in str(path) for path in dirs)


def test_ensure_stream_workspace_creates_gitkeep_files(tmp_path: Path) -> None:
    created = ensure_stream_workspace(tmp_path, ["private_new_legacy_url"])

    assert len(created) == 10
    assert all(path.exists() for path in created)
    assert all((path / ".gitkeep").exists() for path in created)
