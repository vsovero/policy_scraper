# Sources Reviewed

Reviewed on 2026-06-23.

## Economics Data And Code Standards

1. American Economic Association, "Data and Code Availability Policy"
   - URL: https://www.aeaweb.org/journals/data/data-code-policy
   - Project relevance: Requires data, code, and computational details
     sufficient to permit replication; requires data availability statements,
     raw and analysis data where possible, transformation and analysis code,
     metadata, README documentation, trusted repository deposit, licensing,
     and clear documentation of omissions.

2. Data and Code Availability Standard v1.0
   - URL: https://datacodestandard.org/
   - Project relevance: Defines a compact standard for data availability
     statements, raw data, analysis data, metadata, citations, transformation
     code, analysis code, supporting materials, README documentation, archive
     location, license, and omissions.

3. AEA Data Editor, "Step by step guidance"
   - URL: https://aeadataeditor.github.io/aea-de-guidance/
   - Project relevance: Provides practical workflow guidance for preparing,
     uploading, and submitting replication packages for AEA-style verification.

4. AEA, "Data and Code Availability Policy: Frequently Asked Questions"
   - URL: https://www.aeaweb.org/journals/data/faq
   - Project relevance: Clarifies that AEA runs code within reasonable resource
     limits, assesses software/data/code availability and clarity, and requires
     trusted archives rather than ordinary cloud storage.

5. Quarterly Journal of Economics, "Data Policy"
   - URL: https://academic.oup.com/qje/pages/Data_Policy
   - Project relevance: Adopts the American Economic Review data availability
     standard and requires data, programs, and computation details sufficient
     for replication. It also requires README documentation and details for
     proprietary or otherwise restricted data.

6. Review of Economic Studies Data Editor, "Data Availability Policy"
   - URL: https://restud.dataeditor.group/before/
   - Project relevance: Endorses DCAS and requires code/data sufficient to
     reproduce work, README documentation, software versions, run order, random
     seeds, archive posting, and early disclosure of exemptions.

7. Econometric Society Data Editor, "Reproduce and Replicate"
   - URL: https://www.econometricsociety.org/publications/es-data-editor-website/reproduce-and-replicate
   - Project relevance: States that Econometrica, Quantitative Economics, and
     Theoretical Economics require reproducibility checks for empirical,
     experimental, and simulation results, with replication packages made
     publicly available through Zenodo.

## Generative AI And LLM Use Standards

8. Elsevier, "Generative AI policies for journals"
   - URL: https://www.elsevier.com/about/policies-and-standards/generative-ai-policies-for-journals
   - Project relevance: Requires disclosure of AI use in manuscript preparation,
     detailed methods reporting when AI is part of the research process,
     human oversight, accountability, checking for hallucinated sources, privacy
     and IP safeguards, and reproducible description of AI tools used for code,
     data analysis, or research methods.

9. Nature Portfolio, "Artificial Intelligence (AI)"
   - URL: https://www.nature.com/nature-portfolio/editorial-policies/ai
   - Project relevance: States that LLMs do not satisfy authorship criteria,
     LLM use should be documented in Methods or a suitable alternative section,
     AI-assisted copy editing does not need declaration, and authors retain
     responsibility for the final work.

## LLM/Text Replication Package Examples

These are not binding standards. They are examples to cite when explaining how
the course-repetition package handles source retrieval, text search, cached LLM
outputs, classification validation, and benchmark analysis.

10. Griswold, Max, Michael Robbins, and Michael Pollard. 2025. "Replication
    Data for: Stay Tuned - Improving Sentiment Analysis and Stance Detection
    Using Large Language Models."
    - Repository: https://doi.org/10.7910/DVN/OOSYCN
    - Related estimates repository: https://doi.org/10.7910/DVN/QPU9GL
    - Code: https://github.com/maxgriswold/Stay-Tuned---Improving-Sentiment-Analysis-and-Stance-Detection-Using-Large-Language-Models
    - Project relevance: Best structural example for this project. It
      separates public code, deposited inputs/outputs, a Docker environment,
      staged scripts, optional costly OpenAI reruns, and archived model outputs
      that allow replication without forcing every replicator to rerun live API
      calls.

11. Gunes, Erkan, and Christoffer Florczak. 2023. "Replacing or Enhancing the
    Human Coder? Multiclass Classification of Policy Documents with Large
    Language Models."
    - Repository: https://doi.org/10.7910/DVN/SGIDYO
    - Project relevance: Closest topical match for GPT-assisted policy
      document classification. It deposits raw GPT classification files,
      parsing code, results code, and supplementary materials. This project
      should copy the raw-output and parsing transparency, while adding stricter
      source-retrieval and source-review provenance.

12. Gilardi, Fabrizio, Meysam Alizadeh, and Mael Kubli. 2023. "Replication Data
    for: ChatGPT outperforms crowd-workers for text-annotation tasks."
    - Repository: https://doi.org/10.7910/DVN/PQYF6M
    - Project relevance: Useful benchmark example for comparing LLM annotation
      with human or crowd labels across multiple text-classification tasks. It
      motivates separate reporting of model-label accuracy, human agreement,
      cost/runtime, and validation samples.

13. Dahl, Matthew, Varun Magesh, Mirac Suzgun, and Daniel E. Ho. 2024. "Large
    Legal Fictions: Profiling Legal Hallucinations in Large Language Models."
    - Repository: https://doi.org/10.7910/DVN/V4ON8H
    - Project relevance: Useful legal/source-based example because it archives
      many task/model output files with model and temperature metadata. It also
      reinforces this project's rule that model outputs cannot replace
      source-backed evidence.

14. Le Mens, Gael, and Aina Gallego. 2024. "Replication Data for: Positioning
    Political Texts with Large Language Models by Asking and Averaging."
    - Repository: https://doi.org/10.7910/DVN/YFM0BW
    - Related article: Political Analysis 33(3), 2025.
    - Project relevance: Useful example for repeated LLM prompting, averaging,
      and validation against external benchmarks. Less directly useful for
      catalog retrieval, but helpful for documenting validation and cautionary
      limits.

## Project Files Reviewed For Fit

15. `policy_url_discovery_step1/README.md`
    - Project relevance: Documents URL discovery, URL review, hidden legacy
      benchmark scoring, stage rates, manifests, and the rule that Step 1 does
      not run text extraction or policy classification.

16. `policy_text_readiness_step2/README.md`
    - Project relevance: Documents retrieval and text-readiness assessment,
      cached source-text audits, loss buckets, stage rates, and the rule that
      Step 2 does not call the API or classify policy.

17. `policy_human_replication_gold_standard/README.md`
    - Project relevance: Documents known-source reproduction, broad extraction
      queue coverage, policy classification rows, API-assisted review where
      used, mismatch audits, and the separation between programmatic, API, and
      Codex/manual review steps.

18. `policy_human_replication_gold_standard/code_snapshot/course_policy/ai_config.py`
    - Project relevance: Shows a configurable AI workflow with live/off modes,
      model configuration, budget/request caps, prompt/schema versions, and
      raw/parsed response directories.
