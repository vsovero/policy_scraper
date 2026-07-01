from pathlib import Path

import pandas as pd

from course_policy.production_namespace import PUBLIC_SUFFIX, run


def write_file(path: Path, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_production_namespace_copies_public_current_and_writes_manifest(tmp_path: Path):
    repo = tmp_path / "repo"
    review = repo / "artifacts/policy_data_internal/review"
    logs = repo / "artifacts/policy_data_internal/logs"
    interim = repo / "artifacts/policy_data_internal/interim"
    repo.mkdir()

    sources = [
        review / f"catalog_public_legacy_production_rollup_{PUBLIC_SUFFIX}.xlsx",
        review / f"catalog_public_legacy_START_HERE_{PUBLIC_SUFFIX}.csv",
        review / f"catalog_public_legacy_year_panel_{PUBLIC_SUFFIX}.csv",
        review / f"catalog_public_legacy_institution_qc_{PUBLIC_SUFFIX}.csv",
        review / f"catalog_public_legacy_public_status_{PUBLIC_SUFFIX}.csv",
        review / f"catalog_public_no_legacy_fresh_discovery_queue_{PUBLIC_SUFFIX}.csv",
        review / f"catalog_public_legacy_prior_seed_or_pilot_{PUBLIC_SUFFIX}.csv",
        review / f"catalog_public_legacy_gap_benchmark_{PUBLIC_SUFFIX}.csv",
        review / f"catalog_public_legacy_legacy_reproduction_{PUBLIC_SUFFIX}.csv",
        review / f"catalog_public_legacy_outside_legacy_bounds_{PUBLIC_SUFFIX}.csv",
        review / f"catalog_public_legacy_resolution_actions_{PUBLIC_SUFFIX}.csv",
        logs / f"catalog_public_legacy_production_rollup_{PUBLIC_SUFFIX}.md",
        logs / f"phase3_public_legacy_resolution_pass_{PUBLIC_SUFFIX}.md",
    ]
    for index, path in enumerate(sources):
        write_file(path, f"source-{index}")
    write_file(interim / "catalog_private_institutions_private_step0_smoke.csv", "private-smoke")
    write_file(logs / "phase_private_discovery_summary_private_step0_smoke.md", "private-log")

    outputs = run(repo, run_id="run_test", archive_top_level=False)

    manifest = pd.read_csv(outputs.public_manifest_csv)
    assert len(manifest) == len(sources)
    assert set(manifest["stream"]) == {"public"}
    assert (manifest["sha256"] == manifest["source_sha256"]).all()
    assert (review / "public/current/public_catalog_rollup.xlsx").read_text(encoding="utf-8") == "source-0"
    assert (repo / "../policy_data/public_catalog_rollup.xlsx").read_text(encoding="utf-8") == "source-0"
    assert (repo / "../policy_data/START_HERE.md").exists()
    assert (review / "START_HERE.md").exists()
    assert outputs.private_status_md.exists()
    assert (interim / "private/archive/private_step0_smoke/catalog_private_institutions_private_step0_smoke.csv").exists()


def test_production_namespace_archives_top_level_generated_files(tmp_path: Path):
    repo = tmp_path / "repo"
    review = repo / "artifacts/policy_data_internal/review"
    logs = repo / "artifacts/policy_data_internal/logs"
    interim = repo / "artifacts/policy_data_internal/interim"
    repo.mkdir()

    for path in [
        review / f"catalog_public_legacy_production_rollup_{PUBLIC_SUFFIX}.xlsx",
        review / f"catalog_public_legacy_START_HERE_{PUBLIC_SUFFIX}.csv",
        review / f"catalog_public_legacy_year_panel_{PUBLIC_SUFFIX}.csv",
        review / f"catalog_public_legacy_institution_qc_{PUBLIC_SUFFIX}.csv",
        review / f"catalog_public_legacy_public_status_{PUBLIC_SUFFIX}.csv",
        review / f"catalog_public_no_legacy_fresh_discovery_queue_{PUBLIC_SUFFIX}.csv",
        review / f"catalog_public_legacy_prior_seed_or_pilot_{PUBLIC_SUFFIX}.csv",
        review / f"catalog_public_legacy_gap_benchmark_{PUBLIC_SUFFIX}.csv",
        review / f"catalog_public_legacy_legacy_reproduction_{PUBLIC_SUFFIX}.csv",
        review / f"catalog_public_legacy_outside_legacy_bounds_{PUBLIC_SUFFIX}.csv",
        review / f"catalog_public_legacy_resolution_actions_{PUBLIC_SUFFIX}.csv",
        logs / f"catalog_public_legacy_production_rollup_{PUBLIC_SUFFIX}.md",
        logs / f"phase3_public_legacy_resolution_pass_{PUBLIC_SUFFIX}.md",
    ]:
        write_file(path, "source")
    write_file(review / "old_pilot.csv", "old")
    write_file(review / ".gitkeep", "")

    outputs = run(repo, run_id="run_archive", archive_top_level=True)

    assert (review / "public/current/public_year_panel.csv").exists()
    assert not (review / "old_pilot.csv").exists()
    archived = review / "archive/pre_namespace_run_archive/old_pilot.csv"
    assert archived.read_text(encoding="utf-8") == "old"
    assert outputs.archive_manifest_csv.exists()
    assert (review / ".gitkeep").exists()
