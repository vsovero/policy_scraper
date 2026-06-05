import pandas as pd

from course_policy.ocr_visual_review import (
    exclude_existing_candidates,
    merge_confirmation_tables,
    original_url_from_wayback,
    read_candidates,
    status_from_ai,
)


def test_status_from_ai_confirms_only_matching_visible_years():
    source = pd.Series({"catalog_year_start": 2000, "catalog_year_end": 2002})
    parsed = {
        "visual_confirmation_status": "confirmed",
        "catalog_year_start": 2000,
        "catalog_year_end": 2002,
        "evidence_text": "2000-2002 CATALOG",
        "confidence": "high",
        "notes": "",
    }

    status, confirmed, evidence, confidence, _notes = status_from_ai(source, parsed)

    assert status == "visual_ai_confirmed"
    assert confirmed
    assert evidence == "2000-2002 CATALOG"
    assert confidence == "high"


def test_status_from_ai_rejects_mismatched_years():
    source = pd.Series({"catalog_year_start": 2000, "catalog_year_end": 2002})
    parsed = {
        "visual_confirmation_status": "confirmed",
        "catalog_year_start": 2001,
        "catalog_year_end": 2003,
        "evidence_text": "2001-2003 CATALOG",
    }

    status, confirmed, _evidence, _confidence, _notes = status_from_ai(source, parsed)

    assert status == "visual_ai_evidence_insufficient"
    assert not confirmed


def test_status_from_ai_rejects_evidence_missing_end_year():
    source = pd.Series({"catalog_year_start": 2002, "catalog_year_end": 2004})
    parsed = {
        "visual_confirmation_status": "confirmed",
        "catalog_year_start": 2002,
        "catalog_year_end": 2004,
        "evidence_text": "August 1, 2002",
    }

    status, confirmed, _evidence, _confidence, _notes = status_from_ai(source, parsed)

    assert status == "visual_ai_evidence_insufficient"
    assert not confirmed


def test_read_candidates_filters_scanned_pdf_status(tmp_path):
    root = tmp_path
    interim = root / "../data_policy_pipeline/interim"
    interim.mkdir(parents=True)
    pd.DataFrame(
        [
            {"source_id": "a", "source_status": "scanned_pdf_needs_ocr_or_visual_review"},
            {"source_id": "b", "source_status": "ready_for_retrieval"},
        ]
    ).to_csv(interim / "catalog_panel_candidates_strict_pilot.csv", index=False)

    candidates = read_candidates(root)

    assert candidates["source_id"].tolist() == ["a"]


def test_exclude_existing_candidates_skips_completed_source_ids():
    candidates = pd.DataFrame([{"source_id": "a"}, {"source_id": "b"}])
    existing = pd.DataFrame([{"source_id": "a"}])

    remaining = exclude_existing_candidates(candidates, existing)

    assert remaining["source_id"].tolist() == ["b"]


def test_merge_confirmation_tables_prefers_new_rows():
    existing = pd.DataFrame(
        [{"source_id": "a", "unitid": 1, "catalog_year_start": 2000, "confirmation_status": "old"}]
    )
    new = pd.DataFrame(
        [
            {"source_id": "a", "unitid": 1, "catalog_year_start": 2000, "confirmation_status": "new"},
            {"source_id": "b", "unitid": 1, "catalog_year_start": 2001, "confirmation_status": "new"},
        ]
    )

    merged = merge_confirmation_tables(existing, new)

    assert merged["source_id"].tolist() == ["a", "b"]
    assert merged.loc[merged["source_id"].eq("a"), "confirmation_status"].iloc[0] == "new"


def test_original_url_from_wayback_extracts_replay_target():
    url = "https://web.archive.org/web/20230401072525id_/https://tools.abac.edu/Registrar/Catalogs/Archive/2000-2002.pdf"

    assert original_url_from_wayback(url) == "https://tools.abac.edu/Registrar/Catalogs/Archive/2000-2002.pdf"
