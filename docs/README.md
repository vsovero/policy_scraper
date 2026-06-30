# Policy Scraper Docs

Use this folder for replication-standard documentation only. The pipeline
outputs themselves live in:

```text
policy_scraper/artifacts/PIPELINE_OUTPUTS/
```

## Open First

Current work is the transition from Step 1 URL-discovery pilots to Step 1
production source-ledger construction. Open these first:

```text
replication_standards/README.md
replication_standards/codex_goals/step_1_url_discovery_run_contract.md
```

Historical pilot/regression outputs live in:

```text
policy_scraper/artifacts/PIPELINE_OUTPUTS/01_url_discovery/
```

Current status, cross-stage next steps, and production-readiness notes live in:

```text
policy_scraper/artifacts/PIPELINE_OUTPUTS/CURRENT_STATUS_AND_NEXT_STEPS.md
```

The active plan for the self-contained computer-versus-human validation rebuild
lives in:

```text
policy_scraper/artifacts/PIPELINE_OUTPUTS/CLEAN_REBUILD_VALIDATION_PLAN.md
```

Current reproducibility rule:

```text
Codex may assist code development, debugging, and source-review triage, but the
required replication package should not ask Codex to fix code or rediscover
sources. General discoveries become general code/rules. Row-specific accepted
sources become rows in a frozen source ledger. The final dataset rebuilds from
that ledger and archived/cached artifacts.
```

Human-written process reviews and go/no-go notes live in:

```text
policy_scraper/artifacts/PIPELINE_OUTPUTS/01_url_discovery/process_reviews/
```

The detailed audit evidence lives in:

```text
policy_scraper/artifacts/AUDIT_TRAILS/START_HERE.md
```

## Folder Meaning

Everything current is organized under:

```text
replication_standards/
```

Start with:

```text
replication_standards/requirements_checklist.md
replication_standards/url_source_review_standard.md
```

```text
replication_standards/
  Publication, replication-package, and LLM/AI-use requirements. The current
  Step 1 run contract, supporting rules, and old design notes live inside this
  folder so there is one standard.
```

## Current Rule

The active Step 1 process should be documented stage-by-stage in
`policy_scraper/artifacts/PIPELINE_OUTPUTS/`. This docs folder defines the
standards and goals; it should not become a second output folder.

New production work should be labeled `production_chunk_*`, not
`pilot_batch_*`. A production chunk is complete only when every target
institution-year is represented in the source ledger or in an unresolved-row
table with an explicit reason.
