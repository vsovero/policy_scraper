import pandas as pd

from course_policy.batch2_secondary_archive import (
    build_year_summary,
    extract_candidate_rows,
    is_undergraduate_or_combined_catalog,
    parse_catalog_year_range,
)


def test_parse_catalog_year_range():
    assert parse_catalog_year_range("2004-2005 - University catalog") == (2004, 2005)
    assert parse_catalog_year_range("2010_2011 Undergraduate Catalog") == (2010, 2011)


def test_is_undergraduate_or_combined_catalog():
    assert is_undergraduate_or_combined_catalog("2000-2001 - undergraduate and graduate catalog")
    assert is_undergraduate_or_combined_catalog("2010-2011 - undergraduate catalog")
    assert not is_undergraduate_or_combined_catalog("2010-2011 - graduate catalog")
    assert not is_undergraduate_or_combined_catalog("2017-2018 - spring catalog addendum")


def test_extract_candidate_rows_from_oai_metadata():
    xml = b'''<?xml version="1.0"?>
    <OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">
      <ListRecords>
        <record>
          <header><identifier>oai:digarch.unco.edu:node-49720</identifier><setSpec>node:11204</setSpec></header>
          <metadata>
            <mdRecord xmlns="http://dplava.lib.virginia.edu">
              <title>2000-2001 - University of Northern Colorado undergraduate and graduate catalog</title>
              <identifier>https://digarch.unco.edu/node/49720</identifier>
            </mdRecord>
          </metadata>
        </record>
      </ListRecords>
    </OAI-PMH>'''

    rows = extract_candidate_rows("node:11204", "Catalogs 2000-2009", [xml])

    assert len(rows) == 1
    assert rows[0]["target_year"] == 2000
    assert rows[0]["catalog_year_evidence_type"] == "oai_metadata_title"


def test_build_year_summary_fills_prior_missing_year():
    existing = pd.DataFrame(
        [
            {
                "unitid": 127741,
                "institution_name": "University of Northern Colorado",
                "target_year": 2000,
                "batch2_year_status": "missing_after_root_and_legacy",
                "has_root_archive_candidate": False,
                "has_legacy_gap_fill_candidate": False,
            },
            {
                "unitid": 127741,
                "institution_name": "University of Northern Colorado",
                "target_year": 2011,
                "batch2_year_status": "root_candidate",
                "has_root_archive_candidate": True,
                "has_legacy_gap_fill_candidate": False,
            },
        ]
    )
    candidates = pd.DataFrame([{"target_year": 2000}])

    summary = build_year_summary(existing, candidates)

    assert summary.loc[summary["target_year"].eq(2000), "post_secondary_archive_status"].iloc[0] == (
        "secondary_institutional_archive_candidate"
    )
    assert summary.loc[summary["target_year"].eq(2011), "post_secondary_archive_status"].iloc[0] == (
        "preferred_root_candidate"
    )
