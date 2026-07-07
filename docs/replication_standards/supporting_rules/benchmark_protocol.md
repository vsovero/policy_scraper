# Benchmark Protocol

Authority: BINDING STAGE RULE. This file governs benchmark labels, benchmark
claims, and the difference between construction evidence and clean validation.
It cannot be weakened by run reports or submission prose.

## Benchmark Lanes And Replication Path

The project has benchmark lanes and a final replication path. They must be
reported separately.

Clean no-legacy URL discovery tests whether unaided automation can find sources
from ordinary institution metadata. If it fails out of sample, the project
should report that failure and should not claim that URL discovery is a general
autonomous scraper.

The final journal replication path is different. It should rebuild the final
dataset from a frozen source ledger, archived/cached source artifacts,
extraction/classification code, and cached model outputs where applicable. It
should not require live Codex, live code repair, or live web rediscovery.
Its URL-stage completion target is ledger closure, not 90 percent recall:
every target institution-year must have an accepted reviewed source, a valid
prior source recovered and reviewed, a newly discovered reviewed source, or an
explicit unresolved/unrecoverable status.

For production chunks that use earlier pilot or audit evidence, ledger closure
is not enough by itself. Every valid human legacy row in the chunk must be
shown in `BENCHMARK_RECOVERY.csv` as recovered by the current chunk, promoted
into the source ledger with visible human-legacy provenance, or row-invalidated
with a documented reason. Every prior-programmatic row must be recovered by the
current run or row-invalidated; old programmatic evidence must not promote a row
into the source ledger by itself. `BENCHMARK_MISSES.csv` must be empty for the
chunk to pass.
When it is not empty, the miss file must label whether each current-run
benchmark miss is already source-ledger-resolved by valid human legacy evidence
or is still a programmatic-only source hole.

Codex may be used during development as a coding assistant, debugging assistant,
and source-review triage aid. That use belongs in AI-use disclosure and, when it
affects source construction, the construction audit trail. Codex findings should
not be hidden in scraper conditionals. Generalizable fixes become general code
or source-family rules; row-specific accepted sources become transparent source
ledger rows.

For production construction, Codex and the developer may inspect prior valid
human or programmatic answers while writing general source-family rules. That
invalidates the chunk as a clean out-of-sample discovery benchmark, but it is
allowed for exhaustive source-ledger construction.

This permission is about development and review evidence, not the production
runtime contract. Old pilot outputs can teach the code, supply regression tests,
and define benchmark answers. They should not be required input files for the
normal journal-facing production runner.

## Source Taxonomy In Benchmark Reports

Benchmark and production reports must not collapse historical leads into legacy
evidence. The following roles are distinct:

- `validated_human_legacy`: reviewed human/curated legacy source evidence.
- `prior_programmatic`: a previously accepted programmatic discovery that must
  be recovered and reviewed by the current run before source-ledger acceptance.
- `imported_llm_candidate_lead`: imported LLM, Claude, automated workbook,
  training-set, suggestion-pool, or AI/API lead. This is a search hint only.
- `failed_programmatic_attempt`: prior attempt evidence that no valid source was
  found by the old process.

Private automated missing-sheet URLs, private LLM training-set URLs, public
Claude/LLM suggestion outputs, public fresh-AI archive pages, and similar lead
artifacts are not human legacy evidence. They must not be counted as
`validated_human_legacy`, must not satisfy legacy coverage, and must not enter a
legacy benchmark denominator. They may be selected in a historical-lead
construction lane and may enter the source ledger only after current-run
recovery and source review.

## 1. Rebuild The Existing Dataset

This is a production recovery task.

Allowed evidence:

- human legacy URLs;
- corrected legacy URLs;
- archived versions of legacy URLs;
- previous valid programmatic discoveries as diagnostics or rule-development
  aids, not as automatic source-ledger promotions;
- imported LLM/programmatic leads as search hints only, not as legacy evidence;
- legacy excerpts and classifications as debugging aids;
- manual leads;
- API or browser rescue;
- Codex-assisted coding/debugging or source-review triage, if disclosed and
  traceable.

This output should be labeled `legacy_assisted_rebuild` or
`source_ledger_replication_build`, depending on whether it is an intermediate
recovery task or the final deterministic rebuild. It can be useful and
necessary, but it is not a clean test of whether the pipeline can work when no
human or prior programmatic answer exists.

If this lane reads `pilot_batch_*` outputs or old pilot audit folders at runtime,
it is a legacy-assisted or migration run. It should not be described as the clean
Step 1 production runner, even if its outputs are later used to write general
code/rule fixes.

## 2. Prove The No-Legacy Pipeline Works

This is the clean benchmark.

The pipeline cannot be given human legacy URLs, legacy excerpts, legacy policy
classes, or legacy-derived source hints. It starts from institution/year inputs
and ordinary institutional metadata only. It must independently:

1. find the source;
2. retrieve the source;
3. extract readable text;
4. find course-repetition policy text;
5. classify the policy;
6. match a manually validated answer.

The target for this clean benchmark is 90 percent on a manually validated sample
where the source exists and is reasonably discoverable. This target is a
benchmark of unaided discovery, not the production completion standard.

## 3. Reproduce The Final Dataset

This is the required journal replication path.

Allowed evidence:

- frozen source ledger;
- cached or archived source artifacts;
- valid prior human/programmatic source evidence only after it has been reviewed
  under the applicable production rules and stored in the frozen source ledger;
- retrieval/extraction outputs where redistribution is permitted;
- prompt templates and cached model/API outputs where applicable;
- source-review and adjudication logs;
- deterministic build scripts.

The replication package should not require a live Codex step that fixes code or
fills remaining holes. It may include Codex-assisted source-review logs as
provenance, and it may include optional live demonstrations, but the required
rebuild should run from frozen artifacts. It also should not require
`pilot_batch_*` outputs or old pilot audit folders as normal runtime inputs.
Those files may be cited as development evidence, benchmark-design context, or
test fixtures, but not as the runtime spine of a journal release.

## Required Benchmark Lanes

| Lane | Human legacy URLs allowed? | Counts as clean no-legacy benchmark? | Required for final rebuild? | Target |
|---|---:|---:|---:|---:|
| `legacy_assisted_rebuild` | yes | no | no | maximize recovered usable panel |
| `historical_lead_source_reconstruction` | no, except separately labeled rows | no | no | recover/review useful public and private historical leads |
| `known_url_execution_diagnostic` | yes | no | no | 90-100 percent among valid URLs |
| `clean_no_legacy_benchmark` | no | yes | no | 90 percent diagnostic target |
| `source_ledger_replication_build` | yes, if frozen in ledger | no | yes | 100 percent ledger closure, then regenerate final dataset |

## Known-URL Diagnostic

The known-URL diagnostic exists only to test execution after the source has
already been identified. It answers:

If a human supplied a valid URL, can the system retrieve it, extract text, find
the policy, classify it, and reproduce the human coding?

For public rows, dead or unreachable legacy URLs are allowable slippage in the
all-row recovery number. Among valid/retrievable human URLs, the expected rate
is still 90-100 percent. Private should be close to the same standard because
its human URLs should mostly be valid.

This diagnostic does not prove no-legacy discovery works.

## Clean No-Legacy Benchmark

The clean benchmark must use withheld/manual validation rows where the pipeline
does not receive the human URL. A row is disqualified from the clean benchmark
if it uses any of the following as input evidence:

- `legacy_url`;
- `legacy_excerpt`;
- `legacy_policy_class`;
- legacy workbook row IDs or link IDs as source hints;
- `source_trust_level = human_legacy_prior`;
- `best_url_source` or `source_seed_types` that indicate a legacy URL source.

Fresh-discovery streams may still use institution homepages, official catalog
root search, platform enumeration, Wayback, browser/API rescue, and manual
validation of the benchmark answer after the pipeline has made its attempt.

Codex-assisted code changes made after seeing a failed clean benchmark convert
that batch into development/regression evidence. The repaired batch can show
that the general code now handles the failure class, but it no longer counts as
untouched out-of-sample validation.

## Process Rule

All streams should eventually use the same retrieval, extraction, policy search,
classification, and audit engine. They differ only in admission rules:

- human legacy streams enter the execution diagnostic through valid human URLs;
- historical-lead streams may use imported LLM/programmatic leads as search
  hints, but they are neither human legacy evidence nor clean no-legacy inputs;
- no-legacy streams enter only after independent source discovery and source
  validation;
- legacy-assisted rebuild and source-ledger replication can use all frozen,
  documented evidence, but must not be counted as clean benchmark success;
- final replication reads source decisions from the ledger, not from hidden
  institution-specific code branches.

## Code Guardrail

The code-level labels live in:

`src/course_policy/benchmark_protocol.py`

The harmonized catalog URL database includes:

- `benchmark_protocol`;
- `counts_as_clean_no_legacy_benchmark`.

These fields are labels, not final evidence. A clean benchmark report must still
run the no-legacy validation guard and exclude any row with legacy hints.
