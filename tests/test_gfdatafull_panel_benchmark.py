from pathlib import Path

import pandas as pd

from course_policy.gfdatafull_panel_benchmark import (
    build_attrition,
    build_classification_flags,
    build_policy_spell_priority_queue,
    read_csv_many,
    summarize_attrition,
    source_id_for_url,
)


def old_panel() -> pd.DataFrame:
    rows = [
        {
            "unitid": 1,
            "target_year": 2010,
            "instnm": "Survives",
            "has_grad_outcome": True,
            "in_current_target_window_2000_2020": True,
        },
        {
            "unitid": 2,
            "target_year": 2011,
            "instnm": "No URL",
            "has_grad_outcome": True,
            "in_current_target_window_2000_2020": True,
        },
        {
            "unitid": 3,
            "target_year": 2012,
            "instnm": "Missing Current Panel",
            "has_grad_outcome": False,
            "in_current_target_window_2000_2020": True,
        },
        {
            "unitid": 4,
            "target_year": 2021,
            "instnm": "Outside Scope",
            "has_grad_outcome": False,
            "in_current_target_window_2000_2020": False,
        },
        {
            "unitid": 5,
            "target_year": 2013,
            "instnm": "No Classification",
            "has_grad_outcome": False,
            "in_current_target_window_2000_2020": True,
        },
        {
            "unitid": 6,
            "target_year": 2014,
            "instnm": "Not Strict Usable",
            "has_grad_outcome": False,
            "in_current_target_window_2000_2020": True,
        },
    ]
    return pd.DataFrame(rows)


def test_build_attrition_uses_old_gfdatafull_panel_as_denominator() -> None:
    current_year_panel = pd.DataFrame(
        [
            {"unitid": 1, "start_year": 2010, "best_url": "https://example.edu/2010.pdf"},
            {"unitid": 2, "start_year": 2011, "best_url": ""},
            {"unitid": 5, "start_year": 2013, "best_url": "https://example.edu/2013.pdf"},
            {"unitid": 6, "start_year": 2014, "best_url": "https://example.edu/2014.pdf"},
        ]
    )
    catalog_db = pd.DataFrame(
        [
            {
                "source_stream": "public_legacy_url",
                "unitid": 1,
                "target_year": 2010,
                "best_url": "https://example.edu/2010.pdf",
                "policy_extraction_ready": True,
            },
            {
                "source_stream": "public_legacy_url",
                "unitid": 2,
                "target_year": 2011,
                "best_url": "",
                "policy_extraction_ready": False,
            },
            {
                "source_stream": "public_legacy_url",
                "unitid": 5,
                "target_year": 2013,
                "best_url": "https://example.edu/2013.pdf",
                "policy_extraction_ready": True,
            },
            {
                "source_stream": "public_legacy_url",
                "unitid": 6,
                "target_year": 2014,
                "best_url": "https://example.edu/2014.pdf",
                "policy_extraction_ready": True,
            },
        ]
    )
    classification = pd.DataFrame(
        [
            {"unitid": 1, "target_year": 2010, "api_status": "parsed", "api_policy_class": "grade_forgiveness"},
            {"unitid": 6, "target_year": 2014, "api_status": "parsed", "api_policy_class": "unknown"},
        ]
    )
    loss_audit = pd.DataFrame(
        [
            {"unitid": 1, "target_year": 2010, "is_informative_gf_ga_both": True, "has_classification_row": True},
            {"unitid": 6, "target_year": 2014, "is_informative_gf_ga_both": False, "has_classification_row": True},
        ]
    )
    public_audit = pd.DataFrame(
        [
            {
                "unitid": 1,
                "parsed_start_year": 2010,
                "missing_start_year": False,
                "start_year_outside_2000_2020": False,
                "missing_bulletin_url": False,
            }
        ]
    )
    legacy_links = pd.DataFrame(
        [
            {
                "unitid": 1,
                "target_year": 2010,
                "legacy_workbook": "public",
                "legacy_url": "https://example.edu/2010.pdf",
                "selected_as_prior_evidence": True,
            }
        ]
    )

    attrition = build_attrition(
        old_panel(),
        raw_public_audit=public_audit,
        legacy_links=legacy_links,
        current_year_panel=current_year_panel,
        catalog_db=catalog_db,
        classification=classification,
        loss_audit=loss_audit,
    )

    stages = dict(zip(attrition["unitid"], attrition["attrition_stage"]))
    assert stages[1] == "07_strict_usable_gf_ga"
    assert stages[2] == "02_current_panel_year_but_no_best_url"
    assert stages[3] == "01_missing_from_current_legacy_panel"
    assert stages[4] == "00_outside_current_2000_2020_scope"
    assert stages[5] == "04_extraction_or_policy_search_did_not_make_classification_row"
    assert stages[6] == "06_classified_but_not_strict_usable_gf_ga"
    assert bool(attrition.loc[attrition["unitid"].eq(1), "in_raw_legacy_change_log_exact_year"].iloc[0])
    assert bool(attrition.loc[attrition["unitid"].eq(1), "in_legacy_evidence_bridge_exact_year"].iloc[0])


def test_summarize_attrition_reports_main_and_outcome_valid_denominators() -> None:
    attrition = build_attrition(
        old_panel(),
        current_year_panel=pd.DataFrame(
            [
                {"unitid": 1, "start_year": 2010, "best_url": "https://example.edu/2010.pdf"},
                {"unitid": 2, "start_year": 2011, "best_url": ""},
            ]
        ),
        catalog_db=pd.DataFrame(
            [
                {
                    "source_stream": "public_legacy_url",
                    "unitid": 1,
                    "target_year": 2010,
                    "best_url": "https://example.edu/2010.pdf",
                    "policy_extraction_ready": True,
                }
            ]
        ),
        classification=pd.DataFrame(
            [{"unitid": 1, "target_year": 2010, "api_status": "parsed", "api_policy_class": "grade_forgiveness"}]
        ),
        loss_audit=pd.DataFrame(
            [{"unitid": 1, "target_year": 2010, "is_informative_gf_ga_both": True, "has_classification_row": True}]
        ),
    )

    summary = summarize_attrition(attrition)
    keyed = {
        (row["denominator"], row["metric"]): row["count"]
        for _, row in summary.iterrows()
    }

    assert keyed[("old_gfdatafull_public_valid_policy_2000_2020", "denominator")] == 5
    assert keyed[("old_gfdatafull_public_valid_policy_2000_2020", "current_panel_row_present")] == 2
    assert keyed[("old_gfdatafull_public_valid_policy_2000_2020", "strict_usable_gf_ga")] == 1
    assert keyed[("old_gfdatafull_public_valid_policy_2000_2020_with_grad_outcome", "denominator")] == 2
    assert keyed[("old_gfdatafull_public_valid_policy_2000_2020_with_grad_outcome", "strict_usable_gf_ga")] == 1


def test_private_benchmark_falls_back_to_informative_api_class_without_loss_audit() -> None:
    attrition = build_attrition(
        old_panel().loc[lambda frame: frame["unitid"].eq(1)],
        workbook_label="private",
        stream_id="private_human_legacy_url",
        current_year_panel=pd.DataFrame(
            [{"unitid": 1, "start_year": 2010, "best_url": "https://private.example/catalog-2010.pdf"}]
        ),
        catalog_db=pd.DataFrame(
            [
                {
                    "source_stream": "private_human_legacy_url",
                    "unitid": 1,
                    "target_year": 2010,
                    "best_url": "https://private.example/catalog-2010.pdf",
                    "policy_extraction_ready": True,
                }
            ]
        ),
        classification=pd.DataFrame(
            [{"unitid": 1, "target_year": 2010, "api_status": "parsed", "api_policy_class": "grade_averaging"}]
        ),
        loss_audit=pd.DataFrame(),
    )

    assert attrition["strict_usable_gf_ga"].iloc[0]
    assert attrition["attrition_stage"].iloc[0] == "07_strict_usable_gf_ga"


def test_local_coded_policy_class_counts_as_informative_coverage() -> None:
    attrition = build_attrition(
        old_panel().loc[lambda frame: frame["unitid"].eq(1)],
        current_year_panel=pd.DataFrame(
            [{"unitid": 1, "start_year": 2010, "best_url": "https://example.edu/catalog-2010.pdf"}]
        ),
        catalog_db=pd.DataFrame(
            [
                {
                    "source_stream": "public_legacy_url",
                    "unitid": 1,
                    "target_year": 2010,
                    "best_url": "https://example.edu/catalog-2010.pdf",
                    "policy_extraction_ready": True,
                }
            ]
        ),
        classification=pd.DataFrame(
            [
                {
                    "unitid": 1,
                    "target_year": 2010,
                    "api_status": "not_needed",
                    "coded_policy_class": "grade_averaging",
                }
            ]
        ),
        loss_audit=pd.DataFrame(
            [{"unitid": 1, "target_year": 2010, "is_informative_gf_ga_both": False, "has_classification_row": False}]
        ),
    )

    row = attrition.iloc[0]
    assert row["classification_has_informative_class"]
    assert row["strict_usable_gf_ga"]
    assert row["policy_spell_has_classification_informative_class"]
    assert row["attrition_stage"] == "07_strict_usable_gf_ga"


def test_informative_local_class_survives_api_unknown_on_same_row() -> None:
    flags = build_classification_flags(
        pd.DataFrame(
            [
                {
                    "unitid": 1,
                    "target_year": 2010,
                    "api_status": "parsed",
                    "api_policy_class": "unknown",
                    "coded_policy_class": "grade_forgiveness",
                }
            ]
        )
    )

    assert flags["classification_has_informative_class"].iloc[0]
    assert flags["classification_policy_class_clean"].iloc[0] == "grade_forgiveness"


def test_api_most_generous_legacy_policy_class_takes_priority() -> None:
    flags = build_classification_flags(
        pd.DataFrame(
            [
                {
                    "unitid": 1,
                    "target_year": 2010,
                    "api_status": "parsed",
                    "api_policy_class": "both_or_ambiguous",
                    "api_most_generous_legacy_policy_class": "grade_forgiveness",
                    "coded_policy_class": "both_or_ambiguous",
                }
            ]
        )
    )

    assert flags["classification_has_informative_class"].iloc[0]
    assert flags["classification_policy_class_clean"].iloc[0] == "grade_forgiveness"


def test_combined_classification_files_prefer_informative_priority_row(tmp_path: Path) -> None:
    default_path = tmp_path / "policy_classification_production_excerpt_public_legacy_url_001_002_api_live.csv"
    priority_path = tmp_path / "policy_classification_production_excerpt_public_legacy_url_priority_001_001_api_skip.csv"
    pd.DataFrame(
        [{"unitid": 1, "target_year": 2010, "api_status": "parsed", "api_policy_class": "unknown"}]
    ).to_csv(default_path, index=False)
    pd.DataFrame(
        [{"unitid": 1, "target_year": 2010, "api_status": "not_needed", "coded_policy_class": "grade_forgiveness"}]
    ).to_csv(priority_path, index=False)

    combined = read_csv_many([default_path, priority_path])
    flags = build_classification_flags(combined)

    assert len(flags) == 1
    assert flags["classification_has_informative_class"].iloc[0]
    assert flags["classification_policy_class_clean"].iloc[0] == "grade_forgiveness"


def test_summarize_attrition_uses_requested_sector_label() -> None:
    attrition = build_attrition(
        old_panel().loc[lambda frame: frame["unitid"].eq(1)],
        current_year_panel=pd.DataFrame(
            [{"unitid": 1, "start_year": 2010, "best_url": "https://private.example/catalog-2010.pdf"}]
        ),
        catalog_db=pd.DataFrame(
            [
                {
                    "source_stream": "public_legacy_url",
                    "unitid": 1,
                    "target_year": 2010,
                    "best_url": "https://private.example/catalog-2010.pdf",
                    "policy_extraction_ready": True,
                }
            ]
        ),
        classification=pd.DataFrame(
            [{"unitid": 1, "target_year": 2010, "api_status": "parsed", "api_policy_class": "grade_forgiveness"}]
        ),
        loss_audit=pd.DataFrame(
            [{"unitid": 1, "target_year": 2010, "is_informative_gf_ga_both": True, "has_classification_row": True}]
        ),
    )

    summary = summarize_attrition(attrition, sector="private")

    assert "old_gfdatafull_private_valid_policy_2000_2020" in set(summary["denominator"])


def test_policy_spell_priority_selects_same_spell_alternate_when_representative_failed() -> None:
    bad_shell = "https://www.yumpu.com/en/document/read/123/catalog-shell"
    good_pdf = "https://catalog.example.edu/archives/catalog-2011.pdf"
    panel = pd.DataFrame(
        [
            {
                "unitid": 7,
                "target_year": 2010,
                "instnm": "Alternate College",
                "avg": 0,
                "gradeavg": "",
                "forgive": 1,
                "gradeforgive": "Any",
                "has_grad_outcome": True,
                "in_current_target_window_2000_2020": True,
            },
            {
                "unitid": 7,
                "target_year": 2011,
                "instnm": "Alternate College",
                "avg": 0,
                "gradeavg": "",
                "forgive": 1,
                "gradeforgive": "Any",
                "has_grad_outcome": True,
                "in_current_target_window_2000_2020": True,
            },
        ]
    )
    current_year_panel = pd.DataFrame(
        [
            {"unitid": 7, "start_year": 2010, "best_url": bad_shell},
            {"unitid": 7, "start_year": 2011, "best_url": good_pdf},
        ]
    )
    catalog = pd.DataFrame(
        [
            {
                "source_stream": "private_human_legacy_url",
                "unitid": 7,
                "target_year": 2010,
                "best_url": bad_shell,
                "policy_extraction_ready": True,
            },
            {
                "source_stream": "private_human_legacy_url",
                "unitid": 7,
                "target_year": 2011,
                "best_url": good_pdf,
                "policy_extraction_ready": True,
            },
        ]
    )
    attrition = build_attrition(
        panel,
        workbook_label="private",
        stream_id="private_human_legacy_url",
        current_year_panel=current_year_panel,
        catalog_db=catalog,
    )
    source_cache = pd.DataFrame(
        [
            {
                "policy_source_id": source_id_for_url(bad_shell),
                "retrieval_status": "retrieved",
                "text_extract_status": "html_text_extracted",
                "text_char_count": 29,
                "policy_excerpt_count": 0,
            }
        ]
    )

    queue = build_policy_spell_priority_queue(attrition, source_audit_cache=source_cache)

    assert len(queue) == 1
    row = queue.iloc[0]
    assert row["representative_target_year"] == 2010
    assert row["selected_target_year"] == 2011
    assert row["selected_best_url"] == good_pdf
    assert row["same_spell_alternate_selected"]


def test_policy_spell_priority_treats_unquoted_space_url_error_as_stale() -> None:
    shell = "https://catalog.example.edu/current"
    pdf_with_space = "https://catalog.example.edu/-/media/2003-2005 Undergraduate Catalog.pdf"
    panel = pd.DataFrame(
        [
            {
                "unitid": 8,
                "target_year": 2003,
                "instnm": "Space URL College",
                "avg": 0,
                "gradeavg": "",
                "forgive": 1,
                "gradeforgive": "Any",
                "has_grad_outcome": True,
                "in_current_target_window_2000_2020": True,
            },
            {
                "unitid": 8,
                "target_year": 2004,
                "instnm": "Space URL College",
                "avg": 0,
                "gradeavg": "",
                "forgive": 1,
                "gradeforgive": "Any",
                "has_grad_outcome": True,
                "in_current_target_window_2000_2020": True,
            },
        ]
    )
    current_year_panel = pd.DataFrame(
        [
            {"unitid": 8, "start_year": 2003, "best_url": shell},
            {"unitid": 8, "start_year": 2004, "best_url": pdf_with_space},
        ]
    )
    catalog = pd.DataFrame(
        [
            {
                "source_stream": "public_legacy_url",
                "unitid": 8,
                "target_year": 2003,
                "best_url": shell,
                "policy_extraction_ready": True,
            },
            {
                "source_stream": "public_legacy_url",
                "unitid": 8,
                "target_year": 2004,
                "best_url": pdf_with_space,
                "policy_extraction_ready": True,
            },
        ]
    )
    attrition = build_attrition(
        panel,
        workbook_label="public",
        stream_id="public_legacy_url",
        current_year_panel=current_year_panel,
        catalog_db=catalog,
    )
    source_cache = pd.DataFrame(
        [
            {
                "policy_source_id": source_id_for_url(shell),
                "retrieval_status": "retrieved",
                "text_extract_status": "html_text_extracted",
                "text_char_count": 100,
                "policy_excerpt_count": 0,
            },
            {
                "policy_source_id": source_id_for_url(pdf_with_space),
                "retrieval_status": "error",
                "text_extract_status": "empty_body",
                "text_char_count": 0,
                "policy_excerpt_count": 0,
            },
        ]
    )

    queue = build_policy_spell_priority_queue(attrition, source_audit_cache=source_cache)

    assert queue.iloc[0]["selected_target_year"] == 2004
    assert queue.iloc[0]["selected_best_url"] == pdf_with_space
