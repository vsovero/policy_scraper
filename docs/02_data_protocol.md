# Data Protocol

## Scope

The target sample is U.S. public and private 4-year institutions from 2000 through 2020. The primary policy object is the undergraduate course repetition policy in effect for each institution-year.

The policy panel should be keyed by:

```text
unitid
year
```

`year` is the academic year start. For example, a `2013-2014` catalog is academic year `2013`.
Multi-year catalogs must be represented explicitly with coverage start and end years.

## Source Hierarchy

Preferred source order:

1. official undergraduate catalog or bulletin for the target academic year;
2. official archived undergraduate catalog or bulletin covering the target year;
3. official registrar, academic policy, or catalog archive page for the target year;
4. archived official source via the Internet Archive;
5. other institution-hosted document with clear year and undergraduate policy coverage;
6. manual review.

Do not use unaffiliated summaries as final evidence unless no official source exists and the case is explicitly flagged for review.

## Legacy Workbook Evidence

Legacy public and private workbook rows are historical evidence and discovery aids, not final source-backed classifications by themselves.

When legacy rows are merged into the pipeline:

- preserve the originating workbook, sheet name, and Excel row number;
- preserve audit flags such as missing URL, missing evidence text, likely student note, malformed threshold/code, duplicate institution-year, conflicting duplicate, missing start year, and start year outside 2000-2020;
- treat legacy URLs as candidate source leads until verified by code;
- treat legacy notes/excerpts as prior evidence only when they appear to contain catalog language;
- route rows with student-note-like text, malformed values, missing source details, or duplicate conflicts to review rather than silently cleaning them.

For the private workbook, sheet-level precedence must be explicit before rows are used as prior evidence. Training, example, automated, and main private sheets may overlap and conflict. Conflicting rows should be retained in the audit trail and routed to review unless a later human-adjudicated source clearly resolves the conflict.

Private workbook example/training rows are not public-institution source evidence. They may be useful for training or documentation, but should be excluded from public catalog-discovery pilots unless a later reviewed protocol explicitly says otherwise.

## Source Preservation

For each source used, the pipeline should store:

- original URL;
- archived URL, if applicable;
- retrieval timestamp;
- local file path or text snapshot path;
- file type;
- catalog coverage years;
- extraction status;
- evidence excerpt.

The final policy classification must be traceable to a saved source and a verbatim excerpt whenever possible.

## Multi-Year Catalogs

If a catalog covers multiple academic years, for example `2004-2006`, record:

```text
catalog_year_start = 2004
catalog_year_end = 2006
```

Then apply the same source only to academic years from `catalog_year_start` through the year before `catalog_year_end`.
For example, a `2004-2006` catalog covers AY `2004` and AY `2005`, not AY `2006`.

For a two-year catalog such as `2013-2014`, `catalog_year_start = 2013` and `catalog_year_end = 2014`; the catalog is the direct source for AY `2013`.

If the catalog title or metadata is ambiguous, flag for review.

## Policy Categories

### Grade Forgiveness

Grade forgiveness is present when the repeated course grade replaces, excludes, removes, forgives, or otherwise prevents the original attempt from being included in the GPA calculation.

Examples of supporting language may include:

- original grade is excluded from GPA;
- only the repeated grade is used in GPA;
- previous grade is forgiven;
- grade replacement policy;
- academic renewal/repeat policy removes prior grade from GPA.

### Grade Averaging

Grade averaging is present when the original and repeated attempts are both included in GPA calculation, averaged, or otherwise both count toward GPA.

Examples of supporting language may include:

- both grades count in GPA;
- all attempts are included in GPA;
- repeated grades are averaged;
- both the original and repeated attempts remain in the GPA.

### Neither

Neither is appropriate when the catalog clearly describes course repetition rules but neither grade forgiveness nor grade averaging applies, or when repeated coursework does not alter GPA treatment in a way that fits the two main categories.

### Both or Ambiguous

Both/ambiguous should be used when a policy seems to include both grade averaging and grade forgiveness under different conditions, or when the excerpt is not clear enough to assign a single category.

Both/ambiguous cases should generally be routed to human review.

## Threshold Coding

The threshold is the highest original grade that allows a student to repeat the course under the relevant policy.

Allowed explicit thresholds:

```text
F
D-
D
D+
C-
C
C+
B-
B
B+
A-
A
A+
```

Use `Any` only when the source explicitly states that any grade, any course, any previous grade, or no grade restriction applies.

Use `Unknown` only when a policy is identified but the threshold cannot be determined from the available evidence.

Use missing/null only when the field is structurally not applicable, such as no grade forgiveness threshold when there is no grade forgiveness policy.

Important rule: `Unknown` and `Any` are different. Do not convert `Unknown` to `Any`.

Malformed threshold values, including typo variants of `Unknown`, should be flagged rather than automatically normalized into valid values. A later reviewed correction may record the corrected value, but the raw legacy value should remain available for audit.

## Attempt, Credit, and Course Limits

If the policy includes limits, store them separately from the main policy class:

- maximum attempts per course;
- maximum forgiven credits;
- maximum number of repeated courses;
- whether repeated course must be taken at the same institution;
- whether both grades remain on transcript;
- whether approval is required.

These details may matter for future robustness checks but should not be collapsed into the main policy category.

## Evidence Excerpts

Each classification should have a verbatim excerpt whenever possible.

A good excerpt should:

- contain the relevant policy language;
- include enough surrounding text to determine GPA treatment;
- include threshold language if present;
- avoid being only a student-written summary;
- be tied to a source URL and, when possible, page or section.

Student notes can be preserved as legacy notes but should not replace a policy excerpt.

## Carrying Policies Across Years

Do not silently fill missing years.

Every institution-year should have a source/evidence status:

- `direct_catalog_observed`: catalog for that year observed directly;
- `multi_year_catalog_applied`: catalog covers a range including that year;
- `carried_forward`: policy carried forward from prior source under explicit protocol;
- `backfilled`: policy inferred backward under explicit protocol;
- `legacy_only`: only legacy spreadsheet evidence available;
- `missing`: no usable evidence;
- `ambiguous`: evidence exists but cannot be coded confidently.

Carry-forward or backfill rules should be conservative and easy to audit.

## Human Review Triggers

Flag for human review when:

- no source is found;
- source cannot be retrieved;
- extracted text is empty;
- no policy excerpt is found;
- policy excerpt is student-written rather than catalog text;
- legacy row has malformed policy or threshold values;
- legacy row is duplicated or conflicts with another row for the same institution-year;
- AI confidence is below threshold;
- AI classification conflicts with legacy data;
- policy changes unexpectedly from one year to the next;
- threshold is `Any` but quote does not clearly support no restriction;
- threshold is `Unknown` and the policy is otherwise important;
- both grade forgiveness and grade averaging are coded as present;
- source year coverage is unclear.
