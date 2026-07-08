# Stage-Based Requirements Checklist For The Policy Data Build

Created: 2026-06-23

Authority: BINDING CHECKLIST. This is the primary pass/fail checklist for
stage completion and journal-release readiness. Supporting rules can add detail
but cannot weaken these requirements.

This checklist breaks journal replication and LLM-use requirements into the
actual stages of the course repetition policy data build. The goal is to make
each stage auditable before moving to the next one.

Status-claim rule: generated artifacts can supply evidence, but they cannot
authorize pass/fail language. A run may be described as `pass`, `production
ready`, `ready to scale`, or `journal standard` only when a review-stream process review
crosswalks the generated evidence to the relevant binding checklist/run-contract
criteria and reaches that same decision. If the review is missing, conflicting,
or partial, front-door status files must use `under review`, `partial pass`, or
`fail`. Those labels do not complete the active Step 1 URL-stage test-batch
goal; Codex should continue fixing, rerunning, packaging, and reviewing until
the required process review passes Gate 1 and Gate 2, unless a precise external
blocker prevents further progress.

## Current Stage: URL Discovery And Validation

Use this section for the work currently underway: finding candidate catalog or
policy URLs, deciding whether they are valid institution-year sources, and
building the reviewed URL panel that will later feed text extraction.

### 1. Define The URL-Discovery Target Panel

- [ ] Freeze the target universe for URL discovery.
  - Done when: The target file lists `unitid`, institution name, sector, year,
    IPEDS inclusion rule, and whether the row is in the estimation window.
  - Required audit output: `target_panel.csv`.
  - Current project hook:
    `policy_scraper/artifacts/AUDIT_TRAILS/url_discovery_step1_full_audit/outputs/target_panel.csv`.

- [ ] State the denominator used for URL-discovery success rates.
  - Done when: The README says whether rates are computed over all target
    panel-years, rows with graduation outcomes, active legacy benchmark rows,
    or another denominator.
  - Required audit output: denominator table by sector and year.
  - Current project hook:
    `policy_scraper/artifacts/AUDIT_TRAILS/url_discovery_step1_full_audit/README.md`,
    `policy_scraper/artifacts/AUDIT_TRAILS/url_discovery_step1_full_audit/outputs/stage_rates.csv`.

- [ ] Keep excluded rows visible.
  - Done when: Rows excluded from discovery have a reason such as out of sector,
    outside year window, missing outcome, already hand-collected, or duplicate.
  - Required audit output: exclusion or stop-log table.

- [ ] Use explicit production inputs for production runs.
  - Done when: A production Step 1 command starts from production inputs such as
    `target_panel.csv`, `candidate_url_ledger.csv`, `source_review_log.csv`,
    source-evidence cache/manifest files where applicable, and an optional
    benchmark key used only after discovery/review. Future production commands
    do not require `pilot_batch_*` outputs, `artifacts/PILOTS/`, or old pilot
    audit folders as runtime inputs.
  - Required audit output: production input manifest.
  - Fail condition: A run that requires `--prior-batch-slug`, `pilot_batch_*`, or
    old pilot output files as the normal production input contract is
    transitional/migration evidence, not the clean production runner.
  - Fail condition: A command that mainly wraps, rewrites, or transforms old run
    folders instead of rebuilding from explicit production inputs is
    transitional/migration evidence, even if its output folder is named
    `production_chunk_*`.

### 2. Record Candidate URL Generation

- [ ] Log every candidate URL before review.
  - Done when: Each candidate has `unitid`, institution, target year, candidate
    URL, discovery method, source query/root, timestamp or run ID, and candidate
    rank if applicable.
  - Required audit output: candidate ledger.
  - Current project hook: `url_candidate_audit.csv`,
    `step3_suggestion_candidate_ledger.csv`.

- [ ] Separate candidate-generation methods.
  - Done when: Candidate rows distinguish human legacy URL, deterministic
    programmatic search, archive/root expansion, gap-fill inference,
    LLM-suggested URL, Claude-suggested URL, and manual entry.
  - Required audit output: `candidate_source_type` or equivalent field.
  - Replication reason: A journal reviewer should be able to see where LLMs
    affected search coverage versus where deterministic code did the work.

- [ ] Treat LLM/Claude URL suggestions only as candidates.
  - Done when: No LLM-suggested URL enters `production_best_url` unless it
    passes the same retrieval, institution, source-type, and year validation as
    non-LLM candidates.
  - Required audit output: reviewed decision row for every accepted
    LLM-suggested URL.
  - Current project hook: archived suggestion ledgers are retained under
    `policy_scraper/artifacts/OLD_OUTPUT_ARCHIVES/`; current Step 1 run and
    strict source-review outputs exclude LLM/Claude suggestion files as
    production URL evidence.

- [ ] Preserve enough prompt/model information for LLM-generated candidates.
  - Done when: For any LLM URL-suggestion batch, the package records model/tool,
    run date, prompt or task instruction, input institution list, output file,
    and whether the output was manually reviewed.
  - Required audit output: LLM candidate-generation provenance note or log.
  - Important limit: The LLM output is not source evidence. The valid catalog
    page is the evidence.

- [ ] Record API/web rescue provenance when rescue is part of the URL process.
  - Done when: If deterministic URL discovery leaves unresolved target years,
    the package either runs the configured API/web rescue or replays matching
    cached API rescue outputs. For every API-assisted ready row, the output
    records call ID, prompt version, prompt path, raw response path, parsed
    response path, triage file, and source-review file.
  - Required audit output: API triage logs, raw/parsed response logs, and
    ready-row `url_discovery_ai_*` provenance fields.
  - Fail condition: A deterministic-only run cannot pass as a full
    production-path URL test unless it documents that API/web rescue was not
    eligible or not needed.

### 3. Validate Candidate URLs

- [ ] Enforce the highest-standard URL/source review gate.
  - Done when: Programmatic URLs enter production only after row-level source
    evidence and institution-level panel review. HTTP status, filename
    patterns, cached labels, or LLM suggestions alone are not sufficient.
  - Required audit output: accepted review record for every production
    programmatic URL and institution-level panel review evidence for every
    programmatic institution.
  - Current project hook:
    `policy_scraper/docs/replication_standards/url_source_review_standard.md`,
    `policy_scraper/artifacts/AUDIT_TRAILS/url_stage_strict_source_review/manual_url_review_log.csv`,
    `policy_scraper/artifacts/AUDIT_TRAILS/url_stage_strict_source_review/bucket_reconciliation.csv`.
  - Fail condition: A scripted deterministic quality gate is not a substitute
    for evidence-backed source review under `url_source_review_standard.md`.
    Codex may assist the review, but final acceptance requires recorded source
    evidence and institution-panel checks.

- [ ] Check that each accepted URL resolves or is otherwise retrievable.
  - Done when: Accepted rows record HTTP status, redirect target if any,
    retrieval method, retrieval date/run ID, and failure reason for rejected
    rows.
  - Required audit output: URL validation audit.
  - Current project hook: `url_validation_audit.csv`.

- [ ] Check that the URL belongs to the correct institution.
  - Done when: Review fields show institution match, domain/root match, or a
    documented reason why a third-party catalog host is valid.
  - Required audit output: source-decision audit.
  - Current project hook: `source_decision_audit.csv`.

- [ ] Check that the URL is the right source type.
  - Done when: Accepted URLs are classified as catalog PDF, catalog HTML,
    registrar policy page, academic policy page, archived catalog index, or
    other accepted source type.
  - Required audit output: `source_type` or equivalent decision field.

- [ ] Check that the URL supports the target year.
  - Done when: Each accepted row records explicit catalog year, inferred year
    span, archive year, or documented gap-fill rule.
  - Required audit output: year-span fields and gap-fill audit.
  - Current project hook: `gap_fill_audit.csv`,
    `package_pattern_gap_fill_audit.csv`.

- [ ] Reject weak URLs with visible reasons.
  - Done when: Non-accepted candidates have reasons such as wrong institution,
    wrong year, homepage only, dead URL, search-results page, insufficient
    policy source, duplicate lower-ranked URL, or unresolved after bounded
    recovery.
  - Required audit output: stop-log or candidate-decision field.
  - Current project hook: `url_review_stop_log.csv`.

### 4. Build The Reviewed URL Panel

- [ ] Select one production URL per institution-year.
  - Done when: The reviewed URL panel has one row per target institution-year
    and one `production_best_url` or an explicit no-URL status.
  - Required audit output: `reviewed_url_panel.csv`.
  - Historical project hook, not the clean production input contract:
    `policy_scraper/artifacts/PILOTS/url_discovery/pipeline_outputs/pilot_batch_001/OUTPUT_urls_for_text_extraction.csv`,
    with detailed panels under
    `policy_scraper/artifacts/AUDIT_TRAILS/url_discovery_step1_full_audit/outputs/reviewed_url_panel.csv`
    and
    `policy_scraper/artifacts/AUDIT_TRAILS/url_stage_strict_source_review/reviewed_url_panel.csv`.

- [ ] Preserve source hierarchy.
  - Done when: The panel records whether the final URL came from active human
    legacy evidence, reviewed programmatic discovery, reviewed LLM suggestion,
    reviewed Claude suggestion, manual recovery, or gap-fill inference.
  - Required audit output: `production_url_source` or equivalent.

- [ ] Do not classify policy in the URL stage.
  - Done when: The URL-stage code and README state that this stage does not
    extract policy text, classify grade forgiveness/averaging, or call policy
    classification APIs.
  - Required audit output: stage README and run summary.
  - Current project hook: Step 1 README already states this rule.

- [ ] Keep no-URL rows in the panel.
  - Done when: Missing URL rows remain in the reviewed panel or stop log with
    reason fields, instead of being dropped.
  - Required audit output: reviewed panel plus stop log.

### 5. Benchmark URL Discovery

- [ ] Use hidden legacy URLs as a benchmark, not as search input.
  - Done when: The package documents that human legacy URLs are hidden during
    discovery scoring and used afterward as the answer key.
  - Required audit output: hidden legacy benchmark file and score file.
  - Current project hook: `legacy_holdout_truth.csv`,
    `legacy_validation_scores.csv`.

- [ ] Report URL recovery rates by sector.
  - Done when: Public, private, and combined URL recovery are reported against
    the benchmark denominator and the full target panel denominator.
  - Required audit output: `stage_rates.csv`.

- [ ] Investigate benchmark failures.
  - Done when: Missed active legacy URLs have failure categories such as search
    miss, archive miss, year-span miss, retrieval failure, validation rejection,
    or duplicate resolution issue.
  - Required audit output: loss bucket or validation-score failure table.

- [ ] Decide whether the URL stage is ready to hand off.
  - Done when: The production source ledger has closure for the target rows:
    each row has an accepted reviewed source, valid prior evidence recovered
    and reviewed, a newly discovered reviewed source, or an explicit
    unresolved/unrecoverable status. For production chunks with prior
    benchmark evidence, every valid human legacy benchmark row must also be
    recovered, promoted into the ledger with human-legacy provenance, or
    row-invalidated. Prior-programmatic benchmark rows must be recovered by the
    current run or row-invalidated; old programmatic evidence cannot promote a
    row into the source ledger by itself.
  - Benchmark target: At least 90 percent recovery on active held-out legacy
    URL rows, by sector and combined, when the goal is clean no-legacy
    benchmarking.
  - Production target: 100 percent ledger closure. Prior programmatic
    discoveries may be used as diagnostics or examples for general code/rule
    repairs, but they are not valid source-ledger provenance and must not count
    as recovery evidence unless recovered and reviewed by the current run.
  - Required production audit output: `BENCHMARK_RECOVERY.csv` and
    `BENCHMARK_MISSES.csv`. A production chunk does not pass the
    prior-programmatic benchmark check if `BENCHMARK_MISSES.csv` contains
    current-run prior-programmatic misses. The file must distinguish misses
    already source-ledger-resolved by valid human legacy evidence from misses
    that still lack a production source.

### 6. URL-Stage Release Artifacts

- [ ] Package the URL-stage code snapshot or stable runner.
  - Done when: The package identifies the exact script(s) used to build the
    reviewed URL panel and how to rerun them.
  - Required audit output: code path and run command.
  - Historical project hook, not the clean production runner:
    `policy_scraper/src/course_policy/step1_pilot_url_discovery.py` for the
    historical pilot/development command path and
    `policy_scraper/artifacts/AUDIT_TRAILS/url_discovery_step1_full_audit/code/run_step1_url_discovery.py`
    for the full-audit snapshot.
  - Clean-runner requirement: future production release packages should identify
    the explicit production runner and package-local command, not a pilot-era
    command path.

- [ ] Prove the URL-stage release does not depend on pilot runtime inputs.
  - Done when: The release manifest and rebuild command can be run from
    package-local production inputs and cached evidence, and the required input
    manifest contains no `artifacts/PILOTS/`, `pilot_batch_*`, or old pilot audit
    folder paths except under an explicitly labeled migration/test mode.
  - Required audit output: production input manifest and release manifest.
  - Fail condition: A journal-facing Step 1 release cannot require old pilot
    output folders to regenerate the reviewed URL handoff or source ledger.

- [ ] Create a URL-stage file manifest.
  - Done when: Every URL-stage input/output has row counts, column counts,
    file size, modification time, and SHA-256 hash.
  - Required audit output: `file_manifest.csv`.

- [ ] Write a URL-stage handoff note for text extraction.
  - Done when: The note says which file is the handoff file, which rows are
    ready for text extraction, and which rows stop before text extraction.
  - Required audit output: README section or separate handoff markdown.

## Next Stage: Text Retrieval And Text Readiness

This stage starts only after the reviewed URL panel is frozen.

- [ ] Build a text-retrieval queue from accepted URL rows.
  - Done when: Each queued row has `unitid`, year, source URL, URL source, and
    source type.
  - Current project hook:
    `policy_scraper/artifacts/AUDIT_TRAILS/text_readiness_step2_full_audit/outputs/year_source_queue.csv`.

- [ ] Retrieve source text using documented, non-LLM code.
  - Done when: Retrieval status, method, content type, error reason, and text
    length are logged for every unique source.
  - Current project hook: `source_text_audit.csv`.

- [ ] Keep API calls out of text readiness.
  - Done when: The text-readiness README and code state that the stage does not
    call policy-classification APIs.
  - Current project hook: Step 2 README already states this rule.

- [ ] Report retrieval, readable-text, and text-ready rates.
  - Done when: Rates are reported by sector and combined sample, with loss
    buckets for every failed row.
  - Current project hook: `stage_rates.csv`, `loss_buckets.csv`.

## Next Stage: Policy Excerpt Extraction

This stage locates repeat-policy language in retrieved catalog text.

- [ ] Search for course-repeat and GPA-treatment language with documented
  deterministic rules.
  - Done when: Search terms, regexes, windows, and exclusion rules are versioned.

- [ ] Preserve source-backed excerpts.
  - Done when: Every extracted policy excerpt has source URL, year, text span or
    page context where available, and extraction rule.

- [ ] Keep no-policy-term rows visible.
  - Done when: Rows with readable text but no policy terms remain in the trace
    with a no-policy-term stop reason.

## Next Stage: Policy Classification

This is the first stage where LLM/API-assisted classification can be acceptable
as part of the research method.

- [ ] Publish the policy codebook before final classification.
  - Done when: Definitions cover grade forgiveness, grade averaging,
    thresholds, unknown, no policy, SAP-only language, transcript-retention
    language, department-only policy, and ambiguous repeated-course language.

- [ ] Use model/API classification only from retrieved source text or excerpts.
  - Done when: The model input is source text already retrieved by the pipeline,
    not unaudited model memory or web browsing.

- [ ] Archive prompt, schema, model, parameters, raw output, and parsed output.
  - Done when: Every API-assisted row can be replayed from cached artifacts
    without a live API call.
  - Current project hook: `ai_config.py`, cached API classification CSVs.

- [ ] Require supporting evidence for final classifications.
  - Done when: Final coded rows include a supporting quote or deterministic
    rule trace.

- [ ] Flag model uncertainty for human review.
  - Done when: Rows with unsupported quotes, parse failures, ambiguous policy,
    or treatment-timing implications are marked `needs_human_review` or
    equivalent.

## Next Stage: Human Review And Adjudication

- [ ] Maintain a human review queue.
  - Done when: Ambiguous, model-flagged, and treatment-changing rows are
    assigned to a review file with reason codes.

- [ ] Preserve adjudication decisions.
  - Done when: Each adjudicated row records original model/rule output, human
    decision, reason, supporting quote, reviewer/date if available, and final
    coding.

- [ ] Audit model-human and legacy-new disagreements.
  - Done when: Disagreements are grouped by error type and reported in the
    validation summary.
  - Current project hook: mismatch audit, second-pass audit, adjudication queue.

## Next Stage: Final Panel Construction

- [ ] Merge final policy coding into the analysis panel with no silent drops.
  - Done when: Merge rates and unmatched rows are reported by sector and year.

- [ ] Preserve treatment timing traceability.
  - Done when: First adoption years, threshold changes, and policy transitions
    can be traced to the underlying coded institution-year rows.

- [ ] Produce analysis-ready data and a variable codebook.
  - Done when: Every final policy variable and status/audit field has a
    plain-English definition and allowed values.

## Final Stage: Journal Replication Release

- [ ] Name the release as a frozen `production_release_*` package.
  - Done when: The release has a unique `production_release_*` name, release
    date, version/commit identifier, and explicit status. Production chunks are
    working construction units; they are not journal-ready releases by
    themselves.
  - Required release output: release README status block.

- [ ] Use precise go/no-go language.
  - Done when: Reports distinguish `ready for next production chunk`,
    `source-review/benchmark complete`, `not yet journal release ready`, and
    `journal release ready after frozen release-package rebuild`. No chunk report
    says simply "ready" without naming the next permitted use.

- [ ] Freeze code state, not only working-tree status.
  - Done when: The release identifies the exact code snapshot used to build the
    data, including commit hash or archived source bundle, and records whether
    any release code differs from the public repository snapshot. A raw
    `git_dirty: true` flag is not sufficient.
  - Required release output: code manifest or archived source bundle manifest.

- [ ] Provide one master README, exact command, and run order.
  - Done when: A replicator can rebuild all release outputs or replay cached
    restricted/live artifacts from the release root without undocumented steps.
    Commands must use package-local relative paths, not local Dropbox or other
    machine-specific absolute paths.
  - Required release output: master README with runnable command block.

- [ ] Record the computational environment.
  - Done when: Python version, package versions or lock file, operating-system
    assumptions, and any Stata/R versions used later are recorded. Random seeds,
    runtime expectations, memory expectations, and optional container details are
    included where applicable.
  - Required release output: environment manifest such as `environment.yml`,
    `requirements.txt`/lock file, `sessionInfo`, or equivalent.

- [ ] Hash all release inputs, outputs, caches, and code artifacts.
  - Done when: Every package-local input, output, cache, source-evidence file,
    model-output file, adjudication file, and code archive has file size,
    modification time, SHA-256 hash, and row/column counts where tabular.
  - Required release output: release manifest and checksum file.

- [ ] Exclude pilot-era runtime dependencies from the journal release.
  - Done when: Historical `pilot_batch_*` outputs may appear only as cited
    development evidence, benchmark-design context, or test fixtures. They are
    not required inputs for the release rebuild, and they do not appear in the
    release input manifest as normal runtime files.
  - Required release output: release input manifest with no pilot runtime paths,
    or a clearly labeled migration-only exception that is not called journal
    release ready.

- [ ] Include a Data Availability Statement.
  - Done when: IPEDS, catalog URLs, extracted text, LLM/API outputs, human
    review files, and final derived data are each listed as public, restricted,
    cached, omitted, or regenerable.

- [ ] Make source evidence portable.
  - Done when: Cached PDFs, HTML/text extracts, source snapshots, source-review
    records, and source-ledger hashes are included when redistribution is
    permitted. If source artifacts are omitted for copyright, terms, or access
    reasons, the Data Availability Statement names the omission and the release
    provides URLs, retrieval metadata, hashes or stable identifiers where
    possible, and optional live-retrieval code. Required rebuilds must not depend
    on live web retrieval unless the omission is explicitly documented as
    unavoidable and replayed from cached derived evidence.
  - Required release output: source evidence manifest.

- [ ] Include an AI Use Statement.
  - Done when: The statement names AI tools/models, tasks, dates or versions,
    human oversight, validation procedures, privacy/IP safeguards, and author
    responsibility.

- [ ] Include an AI/model-output manifest for pipeline artifacts.
  - Done when: Every API/model-assisted row that affects source discovery,
    extraction, classification, or review links to task type, provider/model,
    run date/time, prompt version, schema version, parameters, input hash, raw
    response path, parsed response path, output hash, validation status, and any
    adjudication record. Live API calls are optional diagnostics, not required
    rebuild steps.
  - Required release output: AI/model-output manifest.

- [ ] Freeze the final source ledger.
  - Done when: Accepted institution-year sources are stored as release data
    with hashes/manifests, source-review evidence, and provenance fields. Row-
    specific source decisions are not hidden in scraper code.

- [ ] Freeze stage boundaries and adjudication records.
  - Done when: The release separates URL/source validation, text retrieval,
    excerpt search, policy classification, human adjudication, final panel
    construction, and analysis outputs. Each stage has a handoff file or stop log
    and downstream stages cannot silently alter upstream decisions.

- [ ] Keep live Codex out of the required rebuild path.
  - Done when: The replication run regenerates the final dataset from frozen
    ledgers, archived/cached source artifacts, code, and cached model outputs
    where applicable. Codex coding/debugging assistance is disclosed as research
    assistance, not required as a runtime dependency.

- [ ] Run a clean release-package rebuild check.
  - Done when: The release is tested from a clean release directory using the
    documented command. The check verifies that expected output hashes, row
    counts, and key summary tables match the frozen release record or reports
    documented acceptable differences.
  - Required release output: rebuild check log or verification summary.

- [ ] Deposit in a trusted repository.
  - Done when: The final replication package is in a journal-acceptable archive
    such as AEA Data and Code Repository, Dataverse, Zenodo, or another approved
    repository.
