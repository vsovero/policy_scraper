import pandas as pd

from course_policy.strict_pilot import (
    build_strict_year_coverage,
    classify_year_evidence,
    parse_explicit_catalog_year,
)


def test_parse_explicit_catalog_year_requires_catalog_context():
    assert parse_explicit_catalog_year("SFSU Bulletin 2013-2014") == (
        2013,
        2014,
        "SFSU Bulletin 2013-2014",
    )
    assert parse_explicit_catalog_year("bpbootstrap-20160726.pack.js") is None


def test_classify_year_evidence_does_not_accept_filename_without_review():
    row = pd.Series(
        {
            "source_retrieved": True,
            "local_source_path": "",
            "best_page_title": "",
            "best_final_url": "https://example.edu/catalog-2004-2006.pdf",
            "candidate_url": "https://example.edu/catalog-2004-2006.pdf",
            "target_year": 2004,
        }
    )

    evidence = classify_year_evidence(row)

    assert evidence["catalog_year_evidence_type"] == "filename_pattern_requires_review"
    assert evidence["strict_covers_target_year"] is False


def test_classify_year_evidence_does_not_accept_pdf_title_without_text():
    row = pd.Series(
        {
            "source_retrieved": True,
            "best_content_type": "application/pdf",
            "local_source_path": "/tmp/does-not-exist.pdf",
            "best_page_title": "2003 2005 Undergraduate Catalog.pdf",
            "best_final_url": "https://example.edu/download?id=123",
            "candidate_url": "https://example.edu/download?id=123",
            "target_year": 2003,
        }
    )

    evidence = classify_year_evidence(row)

    assert evidence["catalog_year_evidence_type"] == "pdf_text_unavailable_or_inconclusive"
    assert evidence["strict_covers_target_year"] is False


def test_build_strict_year_coverage_expands_only_strict_covered_sources():
    institutions = pd.DataFrame(
        [
            {"unitid": 1, "strict_pilot_rank": 1, "strict_pilot_reason": "test"},
        ]
    )
    targets = pd.DataFrame([target_row(1, 2004), target_row(1, 2005), target_row(1, 2006)])
    strict_retrieval = pd.DataFrame(
        [
            {
                "unitid": 1,
                "source_id": "s1",
                "candidate_url": "https://example.edu/catalog.html",
                "strict_covers_target_year": True,
                "catalog_year_start": 2004,
                "catalog_year_end": 2006,
                "catalog_year_evidence_type": "html_title_or_heading",
                "catalog_year_evidence_text": "Catalog 2004-2006",
                "best_attempt_method": "direct",
                "local_source_path": "/tmp/catalog.html",
            }
        ]
    )

    coverage = build_strict_year_coverage(institutions, targets, strict_retrieval)

    assert coverage["has_strict_catalog_source"].tolist() == [True, True, False]


def target_row(unitid, year):
    return {
        "unitid": unitid,
        "institution_name": "Example U",
        "sector": "public_4_year",
        "control": "public",
        "state": "AA",
        "year": year,
        "prior_evidence_status": "missing",
        "source_discovery_priority": "high",
    }
