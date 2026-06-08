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
    SupplementalCatalogCandidate(
        145600,
        2015,
        "https://catalog.uic.edu/ucat/archive-links/2015-17-UIC-undergraduate-catalog.pdf",
        "2015-17 UIC Undergraduate Catalog",
        "Reviewed UIC official archive PDF; root extraction saw the PDF but did not preserve both AY years.",
    ),
    SupplementalCatalogCandidate(
        145600,
        2016,
        "https://catalog.uic.edu/ucat/archive-links/2015-17-UIC-undergraduate-catalog.pdf",
        "2015-17 UIC Undergraduate Catalog",
        "Reviewed UIC official archive PDF; root extraction saw the PDF but did not preserve both AY years.",
    ),
    SupplementalCatalogCandidate(
        141981,
        2013,
        "https://westoahu.hawaii.edu/wp-content/uploads/docs/catalog/UHWO_Catalog_2013-2014.pdf",
        "2013-2014 UH West Oahu General Catalog",
        "Verified official UH West Oahu catalog PDF URL from the general catalog page/media path.",
    ),
    SupplementalCatalogCandidate(
        141981,
        2014,
        "https://westoahu.hawaii.edu/wp-content/uploads/docs/catalog/UHWO_Catalog_2014-2015.pdf",
        "2014-2015 UH West Oahu General Catalog",
        "Verified official UH West Oahu catalog PDF URL from the general catalog page/media path.",
    ),
    SupplementalCatalogCandidate(
        141981,
        2016,
        "https://westoahu.hawaii.edu/wp-content/uploads/docs/catalog/UHWO_Catalog_2016-2017.pdf",
        "2016-2017 UH West Oahu General Catalog",
        "Verified official UH West Oahu catalog PDF URL from the general catalog page/media path.",
    ),
    SupplementalCatalogCandidate(
        141981,
        2017,
        "https://westoahu.hawaii.edu/wp-content/uploads/docs/catalog/UHWO_Catalog_2017-2018.pdf",
        "2017-2018 UH West Oahu General Catalog",
        "Verified official UH West Oahu catalog PDF URL from the general catalog page/media path.",
    ),
    SupplementalCatalogCandidate(
        159382,
        2007,
        "https://www.lsua.edu/content/documents/general-catalog-(2007)_Original_283a4dc8-1f11-4bd9-aa88-b8bd591ef948.pdf",
        "LSUA General Catalog 2007",
        "Verified official LSUA catalog PDF listed on the Registrar catalog page with generic Open PDF link text.",
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
    + [
        AcceptedSourceGap(
            131399,
            2011,
            "verified_source_gap",
            "defer_verified_source_gap",
            "UDC official catalog page jumps from the 2008-2011 catalog span to 2012-2013; by the AY start-year rule, AY 2011 is not covered by the 2008-2011 catalog.",
        )
    ]
    + [
        AcceptedSourceGap(
            161244,
            2009,
            "verified_source_gap",
            "defer_verified_source_gap",
            "UMaine Machias official catalog page jumps from 2007-2009 to 2010-2012; by the AY start-year rule, AY 2009 is not covered by the 2007-2009 catalog.",
        )
    ]
    + [
        AcceptedSourceGap(
            131399,
            year,
            "verified_source_gap",
            "defer_verified_source_gap",
            "UDC official catalog page has a visible catalog-span jump at this AY under the start-year coverage rule.",
        )
        for year in [2013, 2016, 2019]
    ]
    + [
        AcceptedSourceGap(
            163286,
            year,
            "verified_source_gap",
            "defer_verified_source_gap",
            "UMD official legacy PDF archive runs through 2017-2018; this AY falls in the transition to the newer current catalog site and no stable archived catalog URL was found in this pass.",
        )
        for year in [2018, 2019]
    ]
    + [
        AcceptedSourceGap(
            133951,
            year,
            "secondary_archive_access_blocked",
            "retrieval_recovery_or_browser_access",
            "FIU Digital Commons catalog collection root returned a 202/empty index from the pipeline environment; keep the institution in access-recovery rather than treating these rows as unexplained failures.",
        )
        for year in [
            2001,
            2002,
            2003,
            2004,
            2005,
            2006,
            2007,
            2008,
            2010,
            2011,
            2012,
            2013,
            2014,
            2015,
            2016,
            2017,
            2018,
            2019,
            2020,
        ]
    ]
)
