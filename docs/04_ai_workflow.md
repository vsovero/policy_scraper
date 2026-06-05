# AI Workflow

AI should be used in controlled, auditable stages. The pipeline should never treat an AI response as final data unless it passes validation and can be traced to source evidence.

## AI Touchpoint 1: Catalog Discovery

### Purpose

Help identify likely catalog sources when deterministic methods fail or produce ambiguous candidates.

### When to Call AI

Call AI for discovery only after lower-cost deterministic methods have been attempted:

1. legacy workbook URLs;
2. known institution catalog archives;
3. URL pattern checks;
4. search engine results;
5. Internet Archive CDX queries.

### Input

The discovery prompt should include:

- institution name;
- unitid;
- target year or year range;
- known candidate URLs;
- snippets from search results or archive pages;
- prior successful URL patterns for that institution, if any.

### Output

The AI response should be structured JSON:

```json
{
  "candidates": [
    {
      "url": "https://example.edu/catalogs/2008-undergraduate.pdf",
      "archived_url": null,
      "catalog_year_start": 2008,
      "catalog_year_end": 2009,
      "source_kind": "undergraduate_catalog_pdf",
      "reason": "The page title indicates this is the 2008-2009 undergraduate catalog.",
      "confidence": 0.82
    }
  ],
  "needs_human_review": false,
  "review_reason": null
}
```

### Verification Gate

AI-discovered sources must be verified by code:

- URL can be fetched or archived version exists;
- source appears institution-official;
- source year coverage is plausible;
- text can be extracted or source can be routed to review.

No AI-discovered URL should enter the selected source table without this verification.

## AI Touchpoint 2: Policy Classification

### Purpose

Classify a course repetition policy from a bounded excerpt of catalog text.

### When to Call AI

Call AI after the pipeline has:

1. downloaded or snapshotted a catalog source;
2. extracted text;
3. found candidate course repetition excerpts;
4. selected the best excerpt or excerpt set for classification.

### Input

The classification prompt should include:

- institution name;
- unitid;
- catalog year;
- source URL;
- candidate excerpt;
- coding definitions;
- allowed output categories;
- instruction to quote exact supporting language.

### Output

The AI response should be structured JSON:

```json
{
  "policy_class": "grade_forgiveness",
  "grade_averaging": 0,
  "grade_avg_threshold": null,
  "grade_forgiveness": 1,
  "grade_forgive_threshold": "C-",
  "threshold_type": "explicit_letter",
  "attempt_limit": null,
  "credit_limit": null,
  "same_institution_required": true,
  "both_grades_on_transcript": true,
  "supporting_quote": "A student may repeat courses in which a grade of C- or lower was earned...",
  "confidence": 0.91,
  "needs_human_review": false,
  "review_reason": null
}
```

### Required Model Behavior

The prompt should require the model to:

- distinguish `Any` from `Unknown`;
- avoid inferring thresholds without textual support;
- return `needs_human_review = true` when evidence is unclear;
- include a supporting quote;
- avoid using student notes as catalog evidence unless explicitly labeled as legacy-only;
- classify from the excerpt, not from memory.

## API Logging

Every AI call should be logged with:

```text
request_id
task_type
unitid
institution_name
target_year
source_id
excerpt_id
model
prompt_version
schema_version
input_hash
output_hash
raw_response_path
parsed_response_path
validation_status
created_at
```

This allows the project to rerun or audit classifications later.

## Cost Control

Use AI selectively:

- deterministic methods first;
- AI discovery only for hard cases;
- classification only on candidate excerpts, not full catalogs;
- cheaper model for routine classifications;
- stronger model only for ambiguous cases;
- batch processing for large stable runs;
- monthly API budget limits.

## Validation Rules Around AI

Deterministic validation should flag:

- missing supporting quote;
- quote not found in excerpt;
- `Any` threshold without clear no-restriction language;
- `Unknown` used where no policy was actually identified;
- both grade averaging and grade forgiveness present without explanation;
- policy class inconsistent with binary indicators;
- malformed threshold value;
- confidence below threshold;
- disagreement with human-reviewed legacy examples.

## Prompt Versioning

Prompt templates should live in `policy_pipeline/prompts/`.

Each prompt should have:

- a version number;
- a schema version;
- a short changelog;
- sample inputs and outputs;
- notes on known failure modes.

Do not silently change prompts during a full-scale run. If a prompt changes, rerun affected records or record the prompt version difference.

