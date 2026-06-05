# catalog_discovery_v0

Schema version: course_policy_ai_v0

Purpose: suggest candidate official catalog sources only after deterministic discovery methods have not resolved a source.

Inputs:

- institution name
- unitid
- target year or target year range
- known legacy URLs
- institution homepage/catalog archive candidates
- search or archive snippets already collected by code

Output requirements:

- return structured JSON only;
- include candidate URLs with catalog coverage years when supported;
- explain why each candidate appears official and year-appropriate;
- mark uncertain cases as needing human review;
- do not classify course repetition policy.

Validation gate:

- suggested sources are candidate leads only;
- code must verify official status, retrieval status, year coverage, and text extraction before source selection.
