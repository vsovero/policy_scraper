# Policy Classification Rules

This document defines the working rules for classifying course repetition policy excerpts after catalog URLs have been found and source text has been extracted.

These rules are intentionally separate from catalog discovery. A source URL can be valid for catalog coverage while still failing policy classification if the relevant excerpt is missing, graduate-only, program-specific, or ambiguous.

## Classification Object

The target policy is the institution-wide or broadly undergraduate policy governing what happens when an undergraduate student repeats a course.

The central coding question is:

> When a course is repeated, how are the original and repeated grades treated in GPA calculation?

Do not classify based only on the presence of words such as `repeat`, `retake`, or `repeatable for credit`. The excerpt must say enough about GPA, grade points, grade replacement, grade exclusion, or all-attempts counting to support the classification.

Repeat eligibility is a separate coding signal from GPA treatment. A policy can say that a student may repeat a course, must repeat an `F`, or may repeat courses below a certain grade without saying whether the original grade is forgiven, replaced, excluded, averaged, or included in grade points. In that case, preserve the repeat-eligibility threshold if useful, but do not infer `grade_forgiveness` or `grade_averaging`.

When GPA treatment is missing, code the GPA-treatment class as `unknown` and flag `insufficient_gpa_treatment_evidence`. This is an acceptable result, not a failure. Do not assume a universal default that an `F` may be repeated, and do not assume default grade averaging unless the source explicitly says both/all attempts count in GPA, grade points, QPA, CGPA, AGPA, cumulative average, or an equivalent GPA-calculation field.

## Scope Gate

Before classification, decide whether the evidence applies to the target population.

Accept as primary evidence:

- undergraduate catalog or undergraduate bulletin policy;
- institution-wide academic policy that clearly includes undergraduates;
- general student handbook policy when it clearly applies to undergraduate students broadly.

Reject or quarantine as non-primary evidence:

- graduate-only catalog or graduate student policy;
- professional-school-only policy, such as law, medicine, pharmacy, or nursing, unless it clearly governs the institution-wide undergraduate population;
- department, major, or program-specific repeat rules;
- individual course repeatability notes unless they are part of the general repeat policy.

If source scope is plausible but not explicit, flag it for source-context review rather than accepting silently.

## Primary Policy Classes

### Grade Forgiveness

Code `grade_forgiveness` when the repeated course grade replaces, excludes, removes, forgives, or otherwise prevents the original grade from being included in GPA calculation.

Supporting language includes:

- only the repeated, latest, final, or highest grade counts in GPA;
- the original grade is excluded from GPA;
- the previous grade is forgiven, replaced, removed, or not calculated;
- a repeated course triggers GPA recalculation or grade replacement.

Transcript caveats do not negate forgiveness. Many forgiveness policies say both grades remain on the transcript while only one grade counts in GPA.

Forgiveness can operate through different mechanisms. Preserve the mechanism when the text supports it:

```text
forgiveness_mechanism
```

Suggested `forgiveness_mechanism` values:

```text
higher_grade
most_recent_grade
last_attempt_grade
repeated_grade
first_grade_excluded
lowest_grade_excluded
student_option_or_petition
unknown_mechanism
```

For example, a policy where only the higher of the two grades counts is different from a policy where the most recent grade counts even if it is lower. Both are grade forgiveness, but they should not be collapsed when the source distinguishes them.

### Grade Averaging

Code `grade_averaging` when the original and repeated attempts both count in GPA, all attempts are included, or grades are averaged.

Supporting language includes:

- both the initial and repeated grades count in GPA;
- all attempts are included in GPA or quality points;
- all attempts are included in QPA, CGPA, AGPA, cumulative average, cumulative index, or equivalent grade-point calculations;
- repeated grades are averaged;
- the original and repeated grades both remain in GPA calculation.

Credit-counting caveats should be recorded separately. A policy may say credit is earned only once while both grades still count in GPA.

Do not code `grade_averaging` merely because credit is limited to one attempt or because the student is allowed to repeat a failed course. The source must describe GPA, grade-point, or equivalent cumulative-average treatment.

### Neither

Code `neither` only when the source clearly describes repeated courses but the policy does not fit forgiveness or averaging.

Do not use `neither` when the excerpt is merely incomplete. If the repeat passage does not state GPA treatment, search the source for GPA calculation, academic records, grade replacement, or grade forgiveness sections before assigning a final class.

### Both Or Ambiguous

Code `both_or_ambiguous` when the policy contains different GPA-treatment branches or the excerpt is not clear enough to assign a single class.

Common branching rules include:

- course level or course number, such as lower-division versus upper-division courses;
- attempt count, such as first repeat versus later repeats;
- grade threshold, such as D/F repeats receiving forgiveness while other repeats count in GPA;
- course repeatability, such as ordinary courses versus courses approved as repeatable for credit;
- major or program relationship, such as major courses versus non-major/elective courses;
- approval status, such as automatic repeat treatment versus petition-only, dean approval, advisor approval, or registrar request.

For branching policies, record the branch restriction rather than flattening the policy into a single class.

Recommended fields:

```text
branching_rule_present
branching_rule_type
branching_rule_notes
```

Suggested `branching_rule_type` values:

```text
course_level
attempt_count
grade_threshold
course_repeatability
major_requirement
approval_requirement
mixed_or_other
```

## Structured Branch Coding

Historically, some review work selected the most generous policy version available for an institution-year. That can be useful for a particular treatment definition, but it should be treated as a downstream derived measure rather than the only stored coding.

When a policy contains multiple rules in the same year, code each branch systematically. The goal is to preserve enough detail so later analysis can define treatment in different ways, such as:

- any grade-forgiveness option available;
- forgiveness available for D/F courses only;
- forgiveness available for lower-division courses only;
- forgiveness available only for a limited number of attempts or credits;
- most generous branch available to a typical undergraduate;
- branch available only by petition or student option.

Recommended branch-level fields:

```text
policy_branch_id
branch_policy_class
branch_forgiveness_mechanism
branch_applies_to_course_level
branch_applies_to_class_standing
branch_applies_to_original_grade_threshold
branch_applies_to_attempt_number
branch_applies_to_credit_limit
branch_applies_to_course_repeatability
branch_applies_to_major_requirement
branch_requires_petition_or_approval
branch_approval_type
branch_same_institution_required
branch_notes
```

Suggested values for `branch_applies_to_course_level`:

```text
lower_division
upper_division
freshman_level
undergraduate_all
course_specific
unknown
not_applicable
```

Suggested values for `branch_applies_to_class_standing`:

```text
freshman
sophomore
junior
senior
lower_division_student
upper_division_student
all_undergraduates
unknown
not_applicable
```

Course level and class standing are distinct. A policy may apply to freshman-level courses regardless of student standing, or it may apply to students at a particular class standing.

Suggested values for `branch_applies_to_major_requirement`:

```text
major_courses
non_major_courses
general_education_courses
elective_courses
all_courses
unknown
not_applicable
```

Suggested values for `branch_approval_type`:

```text
automatic
student_request
registrar_request
advisor_approval
instructor_approval
department_approval
dean_approval
committee_approval
petition_or_exception
unknown
not_applicable
```

Approval requirements should be coded separately from the underlying GPA treatment. A policy may offer grade forgiveness in principle but only after a student request, petition, or administrative approval. That is different from automatic forgiveness and may matter for treatment definitions downstream.

Derived treatment fields can then be created from branch-level data. For example:

```text
derived_any_grade_forgiveness_available
derived_most_generous_policy_class
derived_most_generous_threshold
derived_forgiveness_for_df_courses
derived_forgiveness_for_lower_division_courses
derived_forgiveness_for_major_courses
derived_automatic_forgiveness_available
```

These derived fields should be documented separately from the source-coded branch fields.

## Threshold Rules

The threshold is the highest original grade that makes a student eligible for the relevant repeat policy.

Use explicit letter thresholds when the text directly supports them:

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

Use `Unknown` when a policy is present but the excerpt does not identify the threshold.

Do not convert `Unknown` to `Any`. The absence of an explicit restriction is not enough to code `Any`.

Keep repeat-eligibility thresholds separate from grade-forgiveness thresholds. For example, "students may repeat courses in which they earned below C" identifies a repeat-eligibility threshold. It is not a grade-forgiveness threshold unless the source also says the earlier grade is replaced, excluded, forgiven, removed from GPA, or otherwise not counted in the GPA calculation.

### Implied Thresholds

Some policies imply a threshold through success-condition language.

Example rule:

- If the policy says a student may repeat until receiving a grade of `C` or higher, code the threshold as `C-` or below.

Use implied thresholds only when the text clearly defines the success condition. If the implication is unclear, keep the threshold as `Unknown` and flag for review.

### Threshold Non-Conflicts

Some threshold differences should not be escalated as substantive conflicts:

- `Any` versus `Unknown` is a precision difference when students were not asked to distinguish explicit-any language from no explicit cutoff;
- `Unknown` versus a letter threshold is usually a missingness/precision issue unless the source text explicitly supports a competing threshold;
- adjacent C-boundary interpretations, such as `D+` versus `C-`, should be treated cautiously when the policy says `C or higher`, `below C`, or `grade of C` because the wording may not distinguish C-, C, and C+ cleanly.

These rows may still matter for later branch-level coding, but they are not high-priority treatment conflicts unless grade-forgiveness availability or a clearly supported threshold changes.

## Source Search Rules During Extraction

The relevant policy may live in more than one place. Search for course-repeat language, but also search for standalone policy sections.

Primary search targets:

- course repetition;
- repeated courses;
- repeating a course;
- retaking a course;
- repeat policy;
- credit for repeated courses.

Secondary search targets:

- grade forgiveness;
- grade replacement;
- grade exclusion;
- GPA recalculation;
- grade point average;
- academic records;
- academic standing;
- transcript policy.

If a repeat passage says students may repeat courses but does not explain GPA treatment, do not stop there. Search nearby and elsewhere in the same source for GPA calculation or grade forgiveness language.

## Source Context And Legacy Evidence

The legacy/student excerpt remains evidence in its own right. Retrieved source context is allowed to add missing policy language, but it should not erase an explicit legacy excerpt merely because the retrieved context came from a different current URL, a later catalog, or a broader catalog page.

Use this order:

- if the legacy excerpt itself explicitly states GPA treatment, classify that excerpt and preserve its source URL;
- if retrieved source context is verified as the same source/catalog year, use it to add missed context or resolve missing details;
- if retrieved source context is a different source, later catalog, current catalog PDF, graduate/professional artifact, or otherwise unverified, ignore it for production classification unless it is being used only as a search lead;
- if the legacy excerpt only states repeat eligibility without GPA treatment, do not retain grade forgiveness or grade averaging from the student code unless another verified source supplies explicit GPA-treatment language.

This rule prevents two errors: current-source context overwriting the historical excerpt, and student-coded grade forgiveness being retained when the copied excerpt does not actually support GPA treatment.

## Academic Renewal Caution

Academic renewal, academic amnesty, fresh start, or readmission forgiveness language can resemble grade forgiveness but may describe a broader record-clearing policy rather than ordinary course repetition.

Set an academic-renewal flag when this language appears.

Do not code academic renewal as course-repeat grade forgiveness unless the passage explicitly ties the GPA exclusion/replacement to repeating a course.

Recommended fields:

```text
academic_renewal_flag
academic_renewal_notes
```

## Lookalikes And False Positives

Do not classify from these alone:

- course descriptions saying a course may be repeated for credit;
- special topics, music, studio, thesis, internship, independent study, or variable-topic repeatability notes;
- financial aid or satisfactory academic progress repeated-course rules;
- transcript-only language without GPA-treatment language;
- student-written notes or summaries without source text.

These may still be useful search leads, but they are not sufficient classification evidence.

## Evidence Requirements

Each classification should preserve:

- source URL;
- target academic year;
- source scope decision;
- candidate excerpt;
- supporting quote or sentence;
- policy class;
- threshold and threshold type;
- forgiveness mechanism, if applicable;
- branch rule notes, if any;
- branch-level restrictions, if multiple rules apply;
- review flag and reason, if uncertain.

The excerpt should include enough context to determine GPA treatment and threshold if present.

## Legacy Benchmark Audit Gate

Legacy/student entries are an audit benchmark, not production truth. They should
be used to learn where the automated source-selection, extraction, or
classification process is failing.

Before moving from legacy/student-backed testing to full classification of
institution-years with no student evidence, the benchmark audit must be stable:

- every student entry selected for benchmark testing should be compared against
  the computer-selected source and computer classification;
- no conflict should remain unexplained;
- virtually every conflict should have a clear resolution: computer correct,
  student correct, source unavailable/unverifiable, or genuinely insufficient
  evidence;
- if the student is correct and the computer is not, the process must be fixed;
- if the failure is caused by wrong or missing source selection, fix the catalog
  URL production process and rerun extraction/classification from the corrected
  source;
- do not patch a source-selection failure by forcing a classification override
  downstream;
- if the failure is caused by missing policy context, fix extraction/search
  before accepting the classification;
- if the failure is caused by interpretation, update the classification rules
  and tests;
- only genuinely ambiguous or source-unverifiable cases should remain unclear,
  and those should be few and explicitly labeled.

The production pipeline should not depend on student excerpts. The production
flow is:

```text
selected best URL -> extracted source text -> policy excerpts -> structured classification
```

The legacy benchmark flow is separate:

```text
student URL/excerpt/code -> compare against computer source/excerpt/code -> diagnose process gaps
```

If the benchmark reveals that a student URL was the appropriate best source, the
correct action is to update the best-URL selection stage, then rerun extraction
and classification. The audit should not silently write production
classification values.

## Longitudinal Continuity And Change Detection

Policy changes should be coded conservatively. Do not create a policy-change event merely because wording, formatting, OCR quality, section title, URL structure, or catalog platform changes.

Before declaring a change within an institution, compare the current year to nearby catalog years and ask whether any substantive policy dimension changed:

- GPA treatment mechanism;
- grade threshold;
- forgiveness mechanism, such as higher grade versus most recent grade;
- branch restrictions, such as course level, attempt count, major requirement, or approval requirement;
- credit or unit limits;
- same-institution or transfer-repeat rules;
- undergraduate/general scope;
- source authority.

If the same rule is expressed with minor wording differences, carry the same structured coding and mark the language as stable or substantively equivalent.

### Passage-Set Comparison

Do not compare only the single best course-repeat paragraph across years. The relevant policy may appear as a set of passages. A real change can occur when:

- a standalone `Grade Forgiveness`, `Grade Replacement`, or `Grade Exclusion` section is added or removed;
- a GPA-calculation paragraph is added while the course-repeat paragraph stays the same;
- an academic-renewal paragraph appears or disappears;
- an exception, petition, approval, or upper/lower-division branch is added;
- a major/program caveat is added;
- a graduate/professional-school limitation appears, changing source scope.

Recommended longitudinal review fields:

```text
prior_year
current_year
excerpt_similarity_to_prior
passage_set_change_status
preliminary_change_status
substantive_change_dimensions
added_passage_types
removed_passage_types
same_policy_carry_forward_flag
change_review_notes
```

Suggested `preliminary_change_status` values:

```text
same_policy_language
minor_wording_change_same_policy
added_or_removed_passage_needs_review
substantive_policy_change
scope_or_source_context_change
unclear_needs_review
```

This continuity check is intended to prevent two errors:

- false positives, where stable policy language is coded differently across years;
- false negatives, where the main repeat paragraph stays the same but another policy passage changes the actual rule.

## Manual Review Triggers

Flag for manual review when:

- source scope is not clearly undergraduate/general;
- excerpt mentions repeat policy but not GPA treatment;
- GPA recalculation is mentioned but the mechanism is unclear;
- policy has multiple branches;
- threshold is implied rather than explicit;
- threshold is `Any`;
- threshold is `Unknown` for an otherwise important policy;
- academic renewal/amnesty language appears;
- classification conflicts with legacy coding;
- adjacent catalog years have unexpectedly different coding;
- a new or removed standalone policy passage may change the rule;
- source text is OCR-garbled or truncated.

## Lessons From Initial Manual Batch

The first ten-row manual review confirmed:

- clean forgiveness and averaging cases are usually straightforward when GPA-treatment language is explicit;
- `C or higher` success-condition language can support an implied `C-` threshold;
- forgiveness mechanisms should be preserved when possible, especially `higher_grade` versus `most_recent_grade`;
- branching policies need separate branch notes and branch-level structured fields, especially course-number, lower-division, grade-threshold, attempt-count, or approval restrictions;
- unclear repeat passages should trigger a second search for GPA calculation or grade forgiveness sections;
- handbooks can be policy-relevant but must be flagged when source authority or undergraduate scope is not explicit.
