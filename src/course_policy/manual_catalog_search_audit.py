"""Record manual catalog source searches for the Phase 3 test set.

This file is intentionally a small curated audit artifact: it captures the
source roots found by manual web searches so the automated discovery code can
be updated against concrete misses rather than vague follow-up flags.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .ai_config import repo_root_from_cwd


DATA_DIR = Path("../data_policy_pipeline")
INTERIM_DIR = DATA_DIR / "interim"
REVIEW_DIR = DATA_DIR / "review"
LOG_DIR = DATA_DIR / "logs"

ROOT_SEARCH_AUDIT_INPUT = REVIEW_DIR / "catalog_root_search_audit.xlsx"
LEGACY_EVIDENCE_LINKS_INPUT = INTERIM_DIR / "legacy_evidence_links.csv"

MANUAL_AUDIT_OUTPUT = REVIEW_DIR / "manual_catalog_search_audit.csv"
MANUAL_SUMMARY_OUTPUT = LOG_DIR / "manual_catalog_search_audit_summary.md"


MANUAL_FINDINGS = [
    {
        "unitid": 194152,
        "manual_status": "partial_current_only",
        "manual_best_root_url": "https://www.alfred.edu/academics/undergrad-majors-minors/catalog.cfm",
        "manual_root_type": "official_current_catalog_page",
        "manual_coverage_start_year": 2021,
        "manual_coverage_end_year": 2026,
        "manual_search_evidence": "Current Alfred catalog page links PDF catalogs back to 2021-2022 and says older versions require registrar contact.",
        "programmatic_fix_needed": "Treat current catalog pages with explicit older-catalog contact language as hard-stop partial coverage, not a search failure.",
        "next_pipeline_action": "defer_or_contact_registrar",
    },
    {
        "unitid": 200697,
        "manual_status": "scope_dead_end",
        "manual_best_root_url": "https://www.airuniversity.af.edu/Portals/10/Registrar/catalogs/2000-2001_AU_catalog.pdf",
        "manual_root_type": "system_catalog_pdf_wrong_scope",
        "manual_coverage_start_year": 2000,
        "manual_coverage_end_year": 2001,
        "manual_search_evidence": "Air University catalog exists, but AFIT is a graduate/professional institution and does not appear to be an undergraduate catalog target.",
        "programmatic_fix_needed": "Add scope review for graduate-only institutions before spending retrieval effort.",
        "next_pipeline_action": "scope_review",
    },
    {
        "unitid": 100724,
        "manual_status": "partial_current_or_selected_pdfs",
        "manual_best_root_url": "https://www.alasu.edu/_qa/academiccatalog.php",
        "manual_root_type": "official_catalog_page_selected_pdfs",
        "manual_coverage_start_year": 0,
        "manual_coverage_end_year": 0,
        "manual_search_evidence": "Search found current/selected Alabama State undergraduate catalog PDFs, but no full 2000-2020 archive root yet.",
        "programmatic_fix_needed": "Escalate to broader site and digital archive query when official catalog page has selected PDFs but no archive list.",
        "next_pipeline_action": "digital_archive_search",
    },
    {
        "unitid": 150136,
        "manual_status": "found_by_automation",
        "manual_best_root_url": "https://dmr.bsu.edu/digital/collection/BSUCoursCat/",
        "manual_root_type": "institutional_digital_archive_contentdm",
        "manual_coverage_start_year": 2000,
        "manual_coverage_end_year": 2014,
        "manual_search_evidence": "Legacy-derived CONTENTdm collection exposes Ball State course catalogs.",
        "programmatic_fix_needed": "Keep CONTENTdm collection API parser.",
        "next_pipeline_action": "retrieve_panel_candidates",
    },
    {
        "unitid": 142115,
        "manual_status": "found_with_repository_pagination",
        "manual_best_root_url": "https://scholarworks.boisestate.edu/catalogs/",
        "manual_root_type": "institutional_repository_bepress",
        "manual_coverage_start_year": 2000,
        "manual_coverage_end_year": 2020,
        "manual_search_evidence": "Boise ScholarWorks catalog collection uses paginated index pages; older catalogs are on index.2.html and index.3.html.",
        "programmatic_fix_needed": "Follow BePress/Digital Commons pagination links before declaring repository coverage partial.",
        "next_pipeline_action": "rerun_with_pagination",
    },
    {
        "unitid": 441937,
        "manual_status": "found_by_automation",
        "manual_best_root_url": "https://www.csuci.edu/academics/catalog-and-schedule/catalog/",
        "manual_root_type": "official_catalog_archive",
        "manual_coverage_start_year": 2002,
        "manual_coverage_end_year": 2020,
        "manual_search_evidence": "Official CSUCI catalog page exposes archive years from the early 2000s.",
        "programmatic_fix_needed": "No immediate change.",
        "next_pipeline_action": "retrieve_panel_candidates",
    },
    {
        "unitid": 110608,
        "manual_status": "found_official_archive",
        "manual_best_root_url": "https://catalog.csun.edu/resources/catalog-archives/",
        "manual_root_type": "official_catalog_archive",
        "manual_coverage_start_year": 1998,
        "manual_coverage_end_year": 2026,
        "manual_search_evidence": "CSUN archive page lists official website/ePub links for recent years and CollegeSource links for 1998-2014.",
        "programmatic_fix_needed": "When a current catalog root has a Resources page, crawl resource/archive pages before treating the root as empty.",
        "next_pipeline_action": "add_resource_archive_pass",
    },
    {
        "unitid": 126775,
        "manual_status": "found_official_archive",
        "manual_best_root_url": "https://www.mines.edu/registrar/bulletins/",
        "manual_root_type": "official_bulletin_archive",
        "manual_coverage_start_year": 1999,
        "manual_coverage_end_year": 2020,
        "manual_search_evidence": "Colorado School of Mines Registrar page lists undergraduate bulletins/course catalogs including 2000-2001.",
        "programmatic_fix_needed": "Search registrar bulletin/catalog archive paths, not only catalog subdomains.",
        "next_pipeline_action": "add_registrar_bulletin_archive_pass",
    },
    {
        "unitid": 220075,
        "manual_status": "partial_official_archive",
        "manual_best_root_url": "https://catalog.etsu.edu/",
        "manual_root_type": "official_catalog_archive",
        "manual_coverage_start_year": 2010,
        "manual_coverage_end_year": 2020,
        "manual_search_evidence": "Automated archive extraction found 2010-2020; no older official archive root confirmed in this pass.",
        "programmatic_fix_needed": "Apply hard stop when official archive begins in 2010 unless legacy evidence suggests older online catalogs.",
        "next_pipeline_action": "record_official_coverage_limit",
    },
    {
        "unitid": 134097,
        "manual_status": "found_official_archive_and_digital_archive",
        "manual_best_root_url": "https://registrar.fsu.edu/archive",
        "manual_root_type": "official_bulletin_archive",
        "manual_coverage_start_year": 2002,
        "manual_coverage_end_year": 2020,
        "manual_search_evidence": "FSU Registrar archive lists undergraduate bulletins from 2002-2003 forward and points pre-listed items to DigiNole.",
        "programmatic_fix_needed": "Follow 'Archive of Previous Editions' links and record digital archive referrals for earlier years.",
        "next_pipeline_action": "retrieve_official_then_digital_archive_gap_search",
    },
    {
        "unitid": 232186,
        "manual_status": "found_by_automation",
        "manual_best_root_url": "https://catalog.gmu.edu/",
        "manual_root_type": "official_catalog_archive",
        "manual_coverage_start_year": 2000,
        "manual_coverage_end_year": 2020,
        "manual_search_evidence": "GMU catalog root exposes archive coverage across the panel.",
        "programmatic_fix_needed": "No immediate change.",
        "next_pipeline_action": "retrieve_panel_candidates",
    },
    {
        "unitid": 139940,
        "manual_status": "found_digital_archive",
        "manual_best_root_url": "https://digitalcollections.library.gsu.edu/digital/collection/catalogs",
        "manual_root_type": "institutional_digital_archive_contentdm",
        "manual_coverage_start_year": 2000,
        "manual_coverage_end_year": 2020,
        "manual_search_evidence": "Georgia State University Catalogs collection includes undergraduate catalogs; Digital Library of Georgia record confirms 2000-2001.",
        "programmatic_fix_needed": "If official catalog archive path fails, search institution/library digital collections for catalog collections.",
        "next_pipeline_action": "add_digital_archive_search",
    },
    {
        "unitid": 101480,
        "manual_status": "found_official_and_repository_archive",
        "manual_best_root_url": "https://www.jsu.edu/catalogarchive/",
        "manual_root_type": "official_catalog_archive",
        "manual_coverage_start_year": 2000,
        "manual_coverage_end_year": 2020,
        "manual_search_evidence": "Official JSU catalog archive exists; Digital Commons also has older catalog records including 2000-2001.",
        "programmatic_fix_needed": "Prefer official archive, but use repository collection for years outside official coverage.",
        "next_pipeline_action": "retrieve_official_then_repository_gaps",
    },
    {
        "unitid": 213349,
        "manual_status": "found_direct_pdf_archive_pattern",
        "manual_best_root_url": "https://www.kutztown.edu/Departments-Offices/A-F/Catalog/Documents/archive/",
        "manual_root_type": "official_direct_pdf_archive_directory",
        "manual_coverage_start_year": 1998,
        "manual_coverage_end_year": 2022,
        "manual_search_evidence": "Search finds Kutztown undergraduate catalog PDFs in the official Documents/archive path, even though current page says older catalogs require registrar contact.",
        "programmatic_fix_needed": "Use legacy URL directory patterns and direct-PDF search results to seed archive directories.",
        "next_pipeline_action": "direct_pdf_pattern_search",
    },
    {
        "unitid": 185828,
        "manual_status": "found_official_and_digital_archive",
        "manual_best_root_url": "https://archive.catalog.njit.edu/",
        "manual_root_type": "official_catalog_archive_plus_repository",
        "manual_coverage_start_year": 2000,
        "manual_coverage_end_year": 2020,
        "manual_search_evidence": "NJIT archive covers 2000 onward and directs pre-2000 catalogs to Digital Commons coursecatalogs.",
        "programmatic_fix_needed": "Promote archive.catalog subdomains and parse links to institutional repositories.",
        "next_pipeline_action": "retrieve_panel_candidates",
    },
    {
        "unitid": 199102,
        "manual_status": "partial_official_archive",
        "manual_best_root_url": "https://ncat.edu/provost/academic-affairs/bulletins/index.php",
        "manual_root_type": "official_bulletin_archive",
        "manual_coverage_start_year": 2014,
        "manual_coverage_end_year": 2020,
        "manual_search_evidence": "Official North Carolina A&T Undergraduate Bulletins page lists 2014-2015 forward.",
        "programmatic_fix_needed": "After official archive coverage limit, run digital archive search only if legacy evidence or high-priority gap requires it.",
        "next_pipeline_action": "record_official_coverage_limit",
    },
    {
        "unitid": 147776,
        "manual_status": "found_by_automation",
        "manual_best_root_url": "https://neiu.edu/academic-catalog/",
        "manual_root_type": "official_catalog_archive",
        "manual_coverage_start_year": 2000,
        "manual_coverage_end_year": 2020,
        "manual_search_evidence": "NEIU official academic catalog page exposes panel coverage.",
        "programmatic_fix_needed": "No immediate change.",
        "next_pipeline_action": "retrieve_panel_candidates",
    },
    {
        "unitid": 229027,
        "manual_status": "found_by_automation",
        "manual_best_root_url": "https://catalog.utsa.edu/",
        "manual_root_type": "official_catalog_archive",
        "manual_coverage_start_year": 2000,
        "manual_coverage_end_year": 2020,
        "manual_search_evidence": "UTSA catalog root exposes panel coverage.",
        "programmatic_fix_needed": "No immediate change.",
        "next_pipeline_action": "retrieve_panel_candidates",
    },
    {
        "unitid": 100663,
        "manual_status": "found_official_archive",
        "manual_best_root_url": "https://www.uab.edu/students/academics/catalogs/undergraduate-archive",
        "manual_root_type": "official_catalog_archive",
        "manual_coverage_start_year": 2004,
        "manual_coverage_end_year": 2020,
        "manual_search_evidence": "UAB undergraduate archive lists previous catalogs from 2004-2006 through 2019-2020 and says prior catalogs require registrar contact.",
        "programmatic_fix_needed": "Follow sibling catalog archive links when legacy URL points to an images/PDF directory.",
        "next_pipeline_action": "retrieve_official_then_record_gap_limit",
    },
    {
        "unitid": 100706,
        "manual_status": "found_repository_archive_with_gap",
        "manual_best_root_url": "https://louis.uah.edu/catalogs/",
        "manual_root_type": "institutional_repository_bepress",
        "manual_coverage_start_year": 2000,
        "manual_coverage_end_year": 2020,
        "manual_search_evidence": "UAH LOUIS catalog repository covers the panel in paginated repository pages; prior spot check left 2009 unresolved.",
        "programmatic_fix_needed": "Follow repository pagination and treat isolated missing years inside a span as suspicious until rechecked.",
        "next_pipeline_action": "rerun_with_pagination_and_gap_check",
    },
    {
        "unitid": 141574,
        "manual_status": "found_official_archive",
        "manual_best_root_url": "https://manoa.hawaii.edu/catalog-2020-21/about-uh/about-catalog/previous/",
        "manual_root_type": "official_catalog_archive",
        "manual_coverage_start_year": 1999,
        "manual_coverage_end_year": 2020,
        "manual_search_evidence": "UH Manoa previous catalogs page links each year from 1999-2000 through 2020-2021.",
        "programmatic_fix_needed": "Follow previous-catalog links from current catalog pages and alternate yearly catalog hosts.",
        "next_pipeline_action": "add_previous_catalog_page_pass",
    },
    {
        "unitid": 127741,
        "manual_status": "found_digital_archive_for_gaps",
        "manual_best_root_url": "https://digarch.unco.edu/",
        "manual_root_type": "university_digital_archive",
        "manual_coverage_start_year": 2000,
        "manual_coverage_end_year": 2020,
        "manual_search_evidence": "UNCO current catalog archive covers later years; university digital archive contains earlier catalog records.",
        "programmatic_fix_needed": "When official archive starts late, run a targeted institution digital archive query for catalog gaps.",
        "next_pipeline_action": "official_then_digital_archive_gap_search",
    },
    {
        "unitid": 102094,
        "manual_status": "found_official_archive",
        "manual_best_root_url": "https://www.southalabama.edu/departments/registrar/bulletin_archives.html",
        "manual_root_type": "official_bulletin_archive",
        "manual_coverage_start_year": 2005,
        "manual_coverage_end_year": 2020,
        "manual_search_evidence": "South Alabama Registrar bulletin archives list bulletins back to 2005-2006.",
        "programmatic_fix_needed": "Search registrar bulletin archive pages when a legacy bulletin directory exists.",
        "next_pipeline_action": "retrieve_official_then_record_gap_limit",
    },
    {
        "unitid": 122597,
        "manual_status": "found_official_archive",
        "manual_best_root_url": "https://bulletin.sfsu.edu/past-bulletin-archive/",
        "manual_root_type": "official_bulletin_archive",
        "manual_coverage_start_year": 2000,
        "manual_coverage_end_year": 2020,
        "manual_search_evidence": "SFSU past bulletin archive links official bulletin pages across the panel.",
        "programmatic_fix_needed": "Use visible archive links and retrieved strict-pilot catalog-year evidence.",
        "next_pipeline_action": "retrieve_panel_candidates",
    },
    {
        "unitid": 149222,
        "manual_status": "partial_repository_archive",
        "manual_best_root_url": "https://opensiuc.lib.siu.edu/ua_bcc/",
        "manual_root_type": "institutional_repository_bepress",
        "manual_coverage_start_year": 2000,
        "manual_coverage_end_year": 2016,
        "manual_search_evidence": "OpenSIUC Undergraduate Catalog/Bulletin collection provides catalog PDFs through AY 2016; later years are outside observed repository bounds.",
        "programmatic_fix_needed": "Follow repository collection pages and preserve official archive bound stops.",
        "next_pipeline_action": "retrieve_official_then_record_gap_limit",
    },
    {
        "unitid": 138558,
        "manual_status": "ocr_or_visual_review",
        "manual_best_root_url": "https://web.archive.org/web/20230401072525id_/https://tools.abac.edu/Registrar/Catalogs/Archive/",
        "manual_root_type": "wayback_catalog_archive",
        "manual_coverage_start_year": 2000,
        "manual_coverage_end_year": 2020,
        "manual_search_evidence": "ABAC archived catalog index exposes candidate PDFs, but files are scanned or Wayback-fragile and require OCR/visual confirmation.",
        "programmatic_fix_needed": "Do not count URL-pattern candidates as strict coverage until OCR or visual catalog-year confirmation succeeds.",
        "next_pipeline_action": "ocr_batch",
    },
    {
        "unitid": 199139,
        "manual_status": "found_official_archive_with_bounds",
        "manual_best_root_url": "https://provost.charlotte.edu/",
        "manual_root_type": "official_catalog_archive_pages",
        "manual_coverage_start_year": 2003,
        "manual_coverage_end_year": 2011,
        "manual_search_evidence": "UNC Charlotte official Provost catalog nodes cover AY 2003-2011; legacy and DigitalNC leads provide separate evidence outside that span.",
        "programmatic_fix_needed": "Keep official archive first; use legacy/digital archive leads only for documented gap years outside the official span.",
        "next_pipeline_action": "official_then_legacy_or_digital_gap_search",
    },
    {
        "unitid": 209490,
        "manual_status": "catalog_dead_end_wrong_scope",
        "manual_best_root_url": "https://www.ohsu.edu/education/academic-policy",
        "manual_root_type": "institution_wide_policy_not_catalog",
        "manual_coverage_start_year": 0,
        "manual_coverage_end_year": 0,
        "manual_search_evidence": "Controlled OHSU fresh discovery found institution-wide policy pages and school-specific catalogs, but no institution-wide undergraduate catalog root.",
        "programmatic_fix_needed": "Stop catalog-first discovery for OHSU in this pilot; preserve policy leads for later dated policy extraction.",
        "next_pipeline_action": "catalog_dead_end",
    },
    {
        "unitid": 230728,
        "manual_status": "found_by_automation",
        "manual_best_root_url": "https://catalog.usu.edu/",
        "manual_root_type": "official_catalog_archive",
        "manual_coverage_start_year": 2000,
        "manual_coverage_end_year": 2020,
        "manual_search_evidence": "USU catalog root exposes panel coverage.",
        "programmatic_fix_needed": "No immediate change.",
        "next_pipeline_action": "retrieve_panel_candidates",
    },
    {
        "unitid": 130776,
        "manual_status": "partial_official_archive",
        "manual_best_root_url": "https://catalogs.wcsu.edu/ugrad2122/",
        "manual_root_type": "official_catalog_archive",
        "manual_coverage_start_year": 2010,
        "manual_coverage_end_year": 2020,
        "manual_search_evidence": "WCSU undergraduate catalog pages expose an Archived Catalogs menu from 2010-2012 forward.",
        "programmatic_fix_needed": "Do not stop at catalogs.wcsu.edu root; crawl current undergraduate catalog pages and side-menu archive links.",
        "next_pipeline_action": "add_current_catalog_archive_menu_pass",
    },
    {
        "unitid": 102368,
        "manual_status": "partial_official_archive",
        "manual_best_root_url": "https://www.troy.edu/academics/catalogs/",
        "manual_root_type": "official_catalog_archive",
        "manual_coverage_start_year": 2005,
        "manual_coverage_end_year": 2020,
        "manual_search_evidence": "Troy academic catalog page exposes undergraduate and graduate catalogs from 2005-2006 forward and says earlier catalogs must be requested from the Registrar.",
        "programmatic_fix_needed": "Treat explicit pre-online catalog contact language as an archive lower-bound stop for early AY rows.",
        "next_pipeline_action": "retrieve_official_then_record_gap_limit",
    },
    {
        "unitid": 110422,
        "manual_status": "found_official_and_repository_archive",
        "manual_best_root_url": "https://previouscatalogs.calpoly.edu/Home",
        "manual_root_type": "official_catalog_archive_plus_repository",
        "manual_coverage_start_year": 2000,
        "manual_coverage_end_year": 2020,
        "manual_search_evidence": "Cal Poly previous-catalog page links recent official catalogs and points earlier catalogs to the Cal Poly Digital Commons catalog collection.",
        "programmatic_fix_needed": "Follow official archive referrals to institutional repository collections before declaring early years missing.",
        "next_pipeline_action": "retrieve_official_then_repository_gaps",
    },
    {
        "unitid": 110495,
        "manual_status": "found_official_archive_and_direct_pdfs",
        "manual_best_root_url": "https://catalog.csustan.edu/",
        "manual_root_type": "official_catalog_archive_plus_direct_pdf_pattern",
        "manual_coverage_start_year": 2001,
        "manual_coverage_end_year": 2020,
        "manual_search_evidence": "CSU Stanislaus Acalog archive covers 2008 forward; early 2001-2008 catalog PDFs are available through official catalog.csustan.edu media URLs.",
        "programmatic_fix_needed": "Use direct PDF patterns from official catalog hosts to fill pre-Acalog gaps when legacy/catalog search finds the pattern.",
        "next_pipeline_action": "retrieve_official_then_direct_pdf_pattern_gaps",
    },
    {
        "unitid": 110510,
        "manual_status": "found_repository_archive",
        "manual_best_root_url": "https://scholarworks.lib.csusb.edu/csusb-catalog/",
        "manual_root_type": "institutional_repository_bepress",
        "manual_coverage_start_year": 2000,
        "manual_coverage_end_year": 2020,
        "manual_search_evidence": "CSUSB ScholarWorks course catalog collection says catalogs date back to 1965 and exposes 2000-2020 catalog items in the repository gallery.",
        "programmatic_fix_needed": "Parse BePress gallery titles for repository collections whose path is not literally /catalogs/.",
        "next_pipeline_action": "retrieve_panel_candidates",
    },
    {
        "unitid": 110565,
        "manual_status": "found_official_archive",
        "manual_best_root_url": "http://catalog.fullerton.edu/",
        "manual_root_type": "official_catalog_archive",
        "manual_coverage_start_year": 2003,
        "manual_coverage_end_year": 2020,
        "manual_search_evidence": "CSUF catalog subdomain exposes archived Acalog entries for 2013 forward and links the older official Fullerton catalog archive for 2003-2015.",
        "programmatic_fix_needed": "Follow current catalog roots that point back to official archived-catalog pages.",
        "next_pipeline_action": "retrieve_official_then_record_gap_limit",
    },
    {
        "unitid": 104151,
        "manual_status": "found_official_archive",
        "manual_best_root_url": "https://catalog.asu.edu/catalog_archives",
        "manual_root_type": "official_catalog_archive",
        "manual_coverage_start_year": 2000,
        "manual_coverage_end_year": 2020,
        "manual_search_evidence": "ASU catalog archives page lists university academic catalogs since 1994, including General Catalog and General and Graduate Catalog rows across the panel.",
        "programmatic_fix_needed": "Allow university-wide General and Graduate Catalog links while continuing to reject graduate-only catalog links.",
        "next_pipeline_action": "retrieve_panel_candidates",
    },
    {
        "unitid": 110617,
        "manual_status": "found_official_archive",
        "manual_best_root_url": "https://catalog.csus.edu/",
        "manual_root_type": "official_catalog_archive",
        "manual_coverage_start_year": 2000,
        "manual_coverage_end_year": 2020,
        "manual_search_evidence": "Sacramento State catalog root and oldcatalog archive expose previous catalog links across the panel.",
        "programmatic_fix_needed": "Use current catalog root plus linked previous-catalog archive pages.",
        "next_pipeline_action": "retrieve_panel_candidates",
    },
    {
        "unitid": 110714,
        "manual_status": "found_official_archive_with_bounds",
        "manual_best_root_url": "https://registrar.ucsc.edu/catalog/",
        "manual_root_type": "official_catalog_archive",
        "manual_coverage_start_year": 2003,
        "manual_coverage_end_year": 2020,
        "manual_search_evidence": "UCSC Registrar catalog page lists archived General Catalog PDFs from 2003-2004 forward and states that catalogs from 1965-2002 require Special Collections contact.",
        "programmatic_fix_needed": "Treat explicit pre-online archive contact language as a lower-bound stop.",
        "next_pipeline_action": "retrieve_official_then_record_gap_limit",
    },
    {
        "unitid": 115755,
        "manual_status": "partial_official_archive",
        "manual_best_root_url": "https://catalog.humboldt.edu/",
        "manual_root_type": "official_catalog_archive",
        "manual_coverage_start_year": 2005,
        "manual_coverage_end_year": 2020,
        "manual_search_evidence": "Cal Poly Humboldt catalog root and archived catalogs page expose catalog entries from 2005-2006 forward in this pass.",
        "programmatic_fix_needed": "Record official archive lower bound when no earlier root is found in the bounded pass.",
        "next_pipeline_action": "retrieve_official_then_record_gap_limit",
    },
    {
        "unitid": 123572,
        "manual_status": "found_official_archive",
        "manual_best_root_url": "https://catalog.sonoma.edu/",
        "manual_root_type": "official_catalog_archive",
        "manual_coverage_start_year": 2000,
        "manual_coverage_end_year": 2020,
        "manual_search_evidence": "Sonoma State catalog root exposes archived catalog candidates covering the full panel.",
        "programmatic_fix_needed": "No immediate change.",
        "next_pipeline_action": "retrieve_panel_candidates",
    },
    {
        "unitid": 126562,
        "manual_status": "partial_official_archive",
        "manual_best_root_url": "https://www.ucdenver.edu/registrar/catalogs/archived",
        "manual_root_type": "official_catalog_archive",
        "manual_coverage_start_year": 2007,
        "manual_coverage_end_year": 2020,
        "manual_search_evidence": "CU Denver Registrar archive lists PDF catalogs from 2007-2008 forward and states catalogs prior to 2007 are in Auraria Library Digital Collections.",
        "programmatic_fix_needed": "Record the official archive lower bound and preserve the library referral for a later secondary-archive pass.",
        "next_pipeline_action": "retrieve_official_then_record_gap_limit",
    },
    {
        "unitid": 128771,
        "manual_status": "found_official_archive",
        "manual_best_root_url": "https://ccsu.smartcatalogiq.com/",
        "manual_root_type": "official_catalog_archive",
        "manual_coverage_start_year": 2000,
        "manual_coverage_end_year": 2020,
        "manual_search_evidence": "Central Connecticut SmartCatalog root exposes archived undergraduate/graduate catalog entries across the panel.",
        "programmatic_fix_needed": "No immediate change.",
        "next_pipeline_action": "retrieve_panel_candidates",
    },
    {
        "unitid": 129020,
        "manual_status": "found_official_archive",
        "manual_best_root_url": "https://catalog.uconn.edu/",
        "manual_root_type": "official_catalog_archive",
        "manual_coverage_start_year": 2000,
        "manual_coverage_end_year": 2020,
        "manual_search_evidence": "UConn catalog root links archive pages with catalog entries across the panel.",
        "programmatic_fix_needed": "No immediate change.",
        "next_pipeline_action": "retrieve_panel_candidates",
    },
    {
        "unitid": 130493,
        "manual_status": "partial_official_archive",
        "manual_best_root_url": "https://catalog.southernct.edu/archives/",
        "manual_root_type": "official_catalog_archive",
        "manual_coverage_start_year": 2006,
        "manual_coverage_end_year": 2020,
        "manual_search_evidence": "Southern Connecticut catalog archive lists undergraduate catalog PDFs from 2006 forward in the bounded pass.",
        "programmatic_fix_needed": "Record official archive lower bound when no earlier root is found in the bounded pass.",
        "next_pipeline_action": "retrieve_official_then_record_gap_limit",
    },
    {
        "unitid": 130943,
        "manual_status": "partial_official_archive",
        "manual_best_root_url": "https://catalog.udel.edu/",
        "manual_root_type": "official_catalog_archive",
        "manual_coverage_start_year": 2017,
        "manual_coverage_end_year": 2020,
        "manual_search_evidence": "University of Delaware catalog root exposes archived undergraduate catalogs from 2017-2018 forward in this pass.",
        "programmatic_fix_needed": "Record official archive lower bound unless a secondary archive is later found.",
        "next_pipeline_action": "retrieve_official_then_record_gap_limit",
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def legacy_summary(repo_root: Path) -> pd.DataFrame:
    legacy = pd.read_csv(repo_root / LEGACY_EVIDENCE_LINKS_INPUT, low_memory=False)
    legacy = legacy.loc[legacy["unitid"].isin([row["unitid"] for row in MANUAL_FINDINGS])].copy()
    if legacy.empty:
        return pd.DataFrame(columns=["unitid", "legacy_url_count", "legacy_urls_sample"])
    legacy["legacy_url"] = legacy["legacy_url"].fillna("").astype(str).str.strip()
    legacy_with_urls = legacy.loc[legacy["legacy_url"].ne("")]
    return (
        legacy_with_urls.groupby("unitid", as_index=False)
        .agg(
            legacy_url_count=("legacy_url", "count"),
            legacy_urls_sample=("legacy_url", lambda values: " | ".join(list(dict.fromkeys(values))[:3])),
        )
    )


def load_root_audit(repo_root: Path) -> pd.DataFrame:
    root_path = repo_root / ROOT_SEARCH_AUDIT_INPUT
    if not root_path.exists():
        return pd.DataFrame(columns=["unitid"])
    cols = [
        "unitid",
        "institution_name",
        "root_search_status",
        "preferred_source_root_url",
        "candidate_year_count",
        "candidate_start_year",
        "candidate_end_year",
        "recommended_next_step",
    ]
    audit = pd.read_excel(root_path)
    return audit[[col for col in cols if col in audit.columns]]


def build_manual_audit(repo_root: Path) -> pd.DataFrame:
    manual = pd.DataFrame(MANUAL_FINDINGS)
    root_audit = load_root_audit(repo_root)
    legacy = legacy_summary(repo_root)
    output = manual.merge(root_audit, on="unitid", how="left").merge(legacy, on="unitid", how="left")
    output["legacy_url_count"] = output["legacy_url_count"].fillna(0).astype(int)
    output["legacy_urls_sample"] = output["legacy_urls_sample"].fillna("")
    output["created_at"] = utc_now()
    ordered_cols = [
        "unitid",
        "institution_name",
        "root_search_status",
        "preferred_source_root_url",
        "candidate_year_count",
        "candidate_start_year",
        "candidate_end_year",
        "manual_status",
        "manual_best_root_url",
        "manual_root_type",
        "manual_coverage_start_year",
        "manual_coverage_end_year",
        "legacy_url_count",
        "legacy_urls_sample",
        "manual_search_evidence",
        "programmatic_fix_needed",
        "next_pipeline_action",
        "recommended_next_step",
        "created_at",
    ]
    return output[ordered_cols].sort_values(["manual_status", "institution_name"])


def write_summary(audit: pd.DataFrame, output_path: Path) -> None:
    status_counts = audit["manual_status"].value_counts().sort_index()
    type_counts = audit["manual_root_type"].value_counts().sort_index()
    recovered = audit.loc[
        audit["root_search_status"].isin(["needs_followup", "root_not_found"])
        & audit["manual_status"].str.startswith("found")
    ]
    legacy_recovered = recovered.loc[recovered["legacy_url_count"].gt(0)]

    lines = [
        "# Manual Catalog Search Audit",
        "",
        f"Created: {utc_now()}",
        "",
        "## Purpose",
        "",
        "Manual source-finding pass over the current Phase 3 test set, with emphasis on rows where the automated root search left holes despite legacy evidence.",
        "",
        "## Status Counts",
        "",
    ]
    for status, count in status_counts.items():
        lines.append(f"- {status}: {count}")
    lines.extend(["", "## Root Types", ""])
    for root_type, count in type_counts.items():
        lines.append(f"- {root_type}: {count}")
    lines.extend(
        [
            "",
            "## Key Result",
            "",
            f"- Manual search found usable source roots for {len(recovered)} institutions that automation had marked `needs_followup` or `root_not_found`.",
            f"- Of those, {len(legacy_recovered)} had legacy URLs, meaning the old student evidence was not the problem; our root-finding rules were too narrow.",
            "",
            "## Immediate Rule Updates",
            "",
            "- Crawl resource/archive/previous-catalog pages linked from current catalog roots.",
            "- Follow BePress/Digital Commons pagination before calling repository coverage partial.",
            "- Include institutional digital archives as a second-stage search when official catalog archives fail or start late.",
            "- Use legacy URL directory patterns to seed official PDF archive directories.",
            "- Treat isolated missing years inside an otherwise continuous repository span as suspicious and recheck before marking missing.",
        ]
    )
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(repo_root: Path) -> tuple[Path, Path]:
    audit = build_manual_audit(repo_root)
    output_csv = repo_root / MANUAL_AUDIT_OUTPUT
    summary_md = repo_root / MANUAL_SUMMARY_OUTPUT
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    summary_md.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(output_csv, index=False)
    write_summary(audit, summary_md)
    return output_csv, summary_md


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    repo_root = repo_root_from_cwd()
    output_csv, summary_md = run(repo_root)
    print(f"manual_audit: {output_csv}")
    print(f"summary: {summary_md}")


if __name__ == "__main__":
    main()
