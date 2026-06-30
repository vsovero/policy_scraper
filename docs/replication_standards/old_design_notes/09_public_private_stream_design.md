# Public/Private Discovery Stream Design

## Purpose

The public and private catalog workflows should use the same source-discovery, retrieval, extraction, classification, validation, and review logic wherever possible. The private workflow should differ only in its configured source seeds and review gates.

The current private implementation proves the idea, but it is still shaped as a private wrapper around public batch code. Before scaling private institutions, refactor toward a shared stream-based runner so public and private do not drift apart as public-process updates continue.

## Recommended Architecture

Use one shared discovery engine:

```text
run_catalog_discovery(stream_config)
```

Then define stream configurations through the production stream registry:

```text
src/course_policy/production_streams.py
```

The current stream map is documented in `docs/11_production_streams.md`.

The public legacy stream should configure:

- sector: public 4-year;
- legacy workbook: public;
- seed sources: human-entered public legacy URLs;
- output namespace: `public_legacy_url`.

The private human legacy stream should configure:

- sector: private nonprofit 4-year;
- legacy workbook: private;
- seed sources: human-entered private sheet URLs;
- output namespace: `private_human_legacy_url`.

The private new-legacy URL stream should configure:

- sector: private nonprofit 4-year;
- workbook: private;
- seed sources: automated or LLM-suggested URL leads from the private workbook workflow;
- output namespace: `private_new_legacy_url`;
- default trust level: unverified suggestion;
- default review gate: verify official source scope, source type, and catalog-year evidence.

The private fresh-discovery stream should run only after the yield from
`private_new_legacy_url` has been measured.

## Source Seed Trust

Avoid hard-coding special downstream behavior for "private Step 0." Instead, make seed trust explicit in common fields:

```text
source_seed_type
source_trust_level
requires_source_review
review_gate
```

Suggested values:

```text
source_seed_type = human_legacy_url
source_trust_level = legacy_human_entered
requires_source_review = false/true depending on audit flags
review_gate = ""
```

```text
source_seed_type = llm_suggested_url
source_trust_level = unverified_suggestion
requires_source_review = true
review_gate = verify_official_scope_and_catalog_year
```

This lets later retrieval, policy search, and classification code stay shared. The downstream rule becomes generic: a source with an unresolved review gate cannot become final evidence, regardless of whether it came from public or private.

## Output Layout

Use separate internal output namespaces to prevent accidental overwrites:

```text
policy_scraper/artifacts/policy_data_internal/interim/public/current/
policy_scraper/artifacts/policy_data_internal/interim/private/current/
policy_scraper/artifacts/policy_data_internal/logs/public/current/
policy_scraper/artifacts/policy_data_internal/logs/private/current/
policy_scraper/artifacts/policy_data_internal/review/public/current/
policy_scraper/artifacts/policy_data_internal/review/private/current/
```

Shared combined outputs can still live under the internal combined namespace once public/private stream outputs are validated and merged.

For production-facing files, copy only the leading files into the flat delivery folder:

```text
policy_data/START_HERE.md
public_catalog_rollup.xlsx
public_year_panel.csv
public_institution_qc.csv
public_run_manifest.csv
```

GitHub versions the code. The generated-data audit trail is preserved by run manifests, archived source paths, checksums, run ids, logs, and the git commit recorded in the manifest.

Superseded generated files should be moved into stream or top-level archive folders inside the ignored internal artifacts:

```text
policy_scraper/artifacts/policy_data_internal/interim/archive/
policy_scraper/artifacts/policy_data_internal/review/archive/
policy_scraper/artifacts/policy_data_internal/logs/archive/
```

Do not put archive folders in the user-facing `policy_data/` delivery packet.

## Preferred Code Shape

Target shape:

```text
course_policy/catalog_discovery.py      # shared engine
course_policy/discovery_streams.py      # public/private stream configs
course_policy/run_public_discovery.py   # small CLI wrapper
course_policy/run_private_discovery.py  # small CLI wrapper
```

Avoid maintaining large separate public and private runners. Public/private differences should be configuration, not forked logic.

## Private New-Legacy URL Rule

The private-only new-legacy URL stream should add automated or LLM-suggested URLs as early source candidates, but never as trusted final evidence.

For every automated missing-private URL:

- preserve workbook row, `Parent_URL`, `Page_Number`, `Score`, URL, and excerpt;
- mark the source as `source_seed_type = llm_suggested_url`;
- mark `source_trust_level = unverified_suggestion`;
- mark `requires_source_review = true`;
- set `review_gate = verify_official_scope_and_catalog_year`;
- allow retrieval and policy search to proceed;
- block final evidence selection until the review gate is resolved.

Human-coded private-sheet URLs should outrank automated suggestions for the same institution-year.

## Migration Plan

1. Keep the current private Step 0 prototype only as a proof of concept.
2. Extract shared discovery behavior from public batch modules into a stream-neutral engine.
3. Move public output writing into the `public/` namespace.
4. Move private output writing into the `private/` namespace.
5. Replace private-specific downstream checks with generic trust/review-gate checks.
6. Add tests that run the same engine with public and private configs.
7. Only then scale private retrieval and classification.

## Bottom Line

Public and private should not become two separate pipelines. They should be two configured streams flowing through the same pipeline, with private Step 0 represented as unverified source-seed metadata and review gates.
