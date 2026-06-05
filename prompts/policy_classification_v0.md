# policy_classification_v0

Schema version: course_policy_ai_v0

Purpose: classify course repetition policy from a bounded, source-backed catalog excerpt.

Inputs:

- institution name
- unitid
- target year
- source URL and local source id
- bounded excerpt text
- coding definitions for grade forgiveness, grade averaging, neither, both/ambiguous, and unknown
- allowed threshold values

Output requirements:

- return structured JSON only;
- classify from the provided excerpt, not from memory;
- preserve the difference between `Any` and `Unknown`;
- include a supporting quote that appears in the excerpt;
- mark unclear, conflicting, or low-confidence cases as needing human review.

Validation gate:

- code must verify that the supporting quote appears in the excerpt;
- code must validate policy indicators, threshold values, confidence, and review flags before accepting parsed output.
