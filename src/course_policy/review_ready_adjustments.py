"""Reviewed Phase 3 pilot adjustments that preserve explicit provenance.

These rows are not silent overrides. They are small, reviewed pilot additions
for source roots that were found during the audit but are not yet handled by a
general parser, plus source gaps that were checked and should not be counted as
parser failures in the review workbook.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SupplementalCatalogCandidate:
    unitid: int
    target_year: int
    candidate_url: str
    candidate_link_text: str
    source_note: str


@dataclass(frozen=True)
class AcceptedSourceGap:
    unitid: int
    target_year: int
    stop_reason: str
    next_batch_action: str
    review_note: str


SUPPLEMENTAL_CATALOG_CANDIDATES: tuple[SupplementalCatalogCandidate, ...] = (
    SupplementalCatalogCandidate(
        139940,
        2000,
        "https://dlg.usg.edu/record/gsu_catalogs_26343",
        "Undergraduate Catalog, Georgia State University, 2000-2001",
        "Digital Library of Georgia record; GSU CONTENTdm endpoint is blocked from current retrieval environment.",
    ),
    SupplementalCatalogCandidate(
        139940,
        2001,
        "https://dlg.usg.edu/record/gsu_catalogs_24620",
        "Undergraduate Catalog, Georgia State University, 2001-2002",
        "Digital Library of Georgia record; GSU CONTENTdm endpoint is blocked from current retrieval environment.",
    ),
    SupplementalCatalogCandidate(
        139940,
        2002,
        "https://dlg.usg.edu/record/gsu_catalogs_25025",
        "Undergraduate Catalog, Georgia State University, 2002-2003",
        "Digital Library of Georgia record; GSU CONTENTdm endpoint is blocked from current retrieval environment.",
    ),
    SupplementalCatalogCandidate(
        101480,
        2000,
        "https://digitalcommons.jsu.edu/lib_ac_bul_bulletin/201/",
        "Catalog | 2000-2001 (June)",
        "Jacksonville State Digital Commons undergraduate bulletins/catalogs sibling record.",
    ),
    SupplementalCatalogCandidate(
        101480,
        2001,
        "https://digitalcommons.jsu.edu/lib_ac_bul_bulletin/202/",
        "Catalog | 2001-2002 (June)",
        "Jacksonville State Digital Commons undergraduate bulletins/catalogs sibling record.",
    ),
    SupplementalCatalogCandidate(
        101480,
        2002,
        "https://digitalcommons.jsu.edu/lib_ac_bul_bulletin/203/",
        "Catalog | 2002-2003 (June)",
        "Jacksonville State Digital Commons undergraduate bulletins/catalogs sibling record.",
    ),
    SupplementalCatalogCandidate(
        101480,
        2003,
        "https://digitalcommons.jsu.edu/lib_ac_bul_bulletin/204/",
        "Catalog | 2003-2004 (June)",
        "Jacksonville State Digital Commons undergraduate bulletins/catalogs sibling record.",
    ),
    SupplementalCatalogCandidate(
        185828,
        2000,
        "https://digitalcommons.njit.edu/coursecatalogs/10/",
        "Undergraduate Catalog, Fall 2000, New Jersey Institute of Technology",
        "NJIT Digital Commons course catalog record linked from the official archive page.",
    ),
    SupplementalCatalogCandidate(
        110495,
        2001,
        "https://catalog.csustan.edu/mime/media/32/966/Catalog-01-03.pdf",
        "CSU Stanislaus Catalog 2001-2003",
        "Reviewed official catalog.csustan.edu media PDF pattern for pre-Acalog catalog years.",
    ),
    SupplementalCatalogCandidate(
        110495,
        2002,
        "https://catalog.csustan.edu/mime/media/32/966/Catalog-01-03.pdf",
        "CSU Stanislaus Catalog 2001-2003",
        "Reviewed official catalog.csustan.edu media PDF pattern for pre-Acalog catalog years.",
    ),
    SupplementalCatalogCandidate(
        110495,
        2003,
        "https://catalog.csustan.edu/mime/media/32/966/Catalog-03-05.pdf",
        "CSU Stanislaus Catalog 2003-2005",
        "Reviewed official catalog.csustan.edu media PDF pattern for pre-Acalog catalog years.",
    ),
    SupplementalCatalogCandidate(
        110495,
        2004,
        "https://catalog.csustan.edu/mime/media/32/966/Catalog-03-05.pdf",
        "CSU Stanislaus Catalog 2003-2005",
        "Reviewed official catalog.csustan.edu media PDF pattern for pre-Acalog catalog years.",
    ),
    SupplementalCatalogCandidate(
        110495,
        2005,
        "https://catalog.csustan.edu/mime/media/32/966/Catalog-05-06.pdf",
        "CSU Stanislaus Catalog 2005-2006",
        "Reviewed official catalog.csustan.edu media PDF pattern for pre-Acalog catalog years.",
    ),
    SupplementalCatalogCandidate(
        110495,
        2006,
        "https://catalog.csustan.edu/mime/media/32/966/Catalog-06-07.pdf",
        "CSU Stanislaus Catalog 2006-2007",
        "Reviewed official catalog.csustan.edu media PDF pattern for pre-Acalog catalog years.",
    ),
    SupplementalCatalogCandidate(
        110495,
        2007,
        "https://catalog.csustan.edu/mime/media/32/966/Catalog-07-08.pdf",
        "CSU Stanislaus Catalog 2007-2008",
        "Reviewed official catalog.csustan.edu media PDF pattern for pre-Acalog catalog years.",
    ),
)


ACCEPTED_SOURCE_GAPS: tuple[AcceptedSourceGap, ...] = tuple(
    [
        AcceptedSourceGap(
            100724,
            year,
            "official_archive_lower_bound_reached",
            "record_official_coverage_limit",
            "Alabama State reviewed undergraduate catalog archive starts at 2008-2010; earlier AY rows are outside the observed archive bound.",
        )
        for year in range(2000, 2008)
    ]
    + [
        AcceptedSourceGap(
            100724,
            year,
            "verified_source_gap",
            "defer_verified_source_gap",
            "Alabama State reviewed archive visibly jumps over this AY after the bounded archive check.",
        )
        for year in (2010, 2014)
    ]
    + [
        AcceptedSourceGap(
            100706,
            2009,
            "verified_source_gap",
            "defer_verified_source_gap",
            "UAH LOUIS catalog collection jumps from 2007-2009 to 2010-2011; no 2009-2010 undergraduate catalog is visible in the bounded collection check.",
        )
    ]
    + [
        AcceptedSourceGap(
            213349,
            year,
            "direct_pdf_pattern_unresolved",
            "defer_direct_pdf_pattern_gap",
            "Kutztown has only partial direct PDF legacy evidence in this pass; no browsable archive directory was retrievable.",
        )
        for year in [2000, 2001, 2004, 2005, 2006, 2009, *range(2011, 2021)]
    ]
    + [
        AcceptedSourceGap(
            185828,
            year,
            "verified_source_gap",
            "defer_verified_source_gap",
            "NJIT official archive and linked Digital Commons records do not expose an undergraduate catalog for this AY in the bounded check.",
        )
        for year in [2001, 2002, 2005, 2008, 2010, 2013]
    ]
    + [
        AcceptedSourceGap(
            127741,
            year,
            "secondary_archive_access_blocked",
            "retrieval_recovery_or_browser_access",
            "UNCO early-year Digital UNC source is institution-specific but WAF/challenge-blocked from the pipeline environment; keep as access-recovery queue.",
        )
        for year in [2001, 2003, 2004, 2005, 2006, 2007, 2009, 2010]
    ]
)
