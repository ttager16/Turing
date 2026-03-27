# Dataset Analysis

Status: implemented

Open first if you want:
- the combined workbook: `outputs/dataset_analysis.xlsx`
- the combined JSON: `outputs/dataset_analysis.json`
- the workbook field guide: `outputs/workbook_field_guide.xlsx`

Stage 3 is the benchmark-auditing layer for the take-home. It treats the dataset as a dataset, not just a bag of individually scored samples.

Inputs:
- `artifacts/provided/Samples.jsonl`
- `outputs/sample_requirements_analysis/guideline_audit.xlsx`
- `outputs/sample_efficacy_analysis/`

Outputs:
- `outputs/dataset_analysis/dataset_analysis.json`
- `outputs/dataset_analysis/dataset_summary.json`
- `outputs/dataset_analysis/detailed_rows.csv`
- `outputs/dataset_analysis/enriched_samples.csv`
- `outputs/dataset_analysis/enriched_samples.jsonl`
- `outputs/dataset_analysis/duplicate_pairs.csv`
- `outputs/dataset_analysis/audit_queues.json`
- `outputs/dataset_analysis/relationship_analysis.json`
- `outputs/dataset_analysis/summary.md`
- `outputs/dataset_analysis/dataset_analysis.xlsx`
- `outputs/dataset_analysis/run_manifest.json`
- `outputs/dataset_analysis/detailed_test_notes.json`
- `outputs/dataset_analysis/stage3_auditor_traces/`
- `outputs/dataset_analysis/embedding_traces/`
- `outputs/dataset_analysis/embedding_cache.json`
- stable combined workbook + JSON at `outputs/dataset_analysis.xlsx` and `outputs/dataset_analysis.json`
- timestamped historical combined workbook + JSON under `outputs/reports/`
- centralized audit copies under `artifacts/audit/stage3/` after running `python scripts/build_audit_bundle.py`

Implemented analyses:
- Dataset profile: length, test-count, Stage 1 score, and Stage 2 pass-rate distributions.
- Efficacy distribution: label counts, benchmark-quality counts, and failure-category counts.
- Redundancy analysis: lexical, structural, and embedding-based prompt similarity, closest-neighbor redundancy score, and redundancy clusters.
- Attempt variance: repeated-attempt spread, execution stability, and volatility flags.
- Model disagreement: either cross-model Stage 2 disagreement when multiple Stage 2 targets were run, or a lightweight Stage 3 dual-auditor disagreement pass (`gpt-5-mini` plus local `qwen`) when Stage 2 is single-model. This is an audit-layer signal, not a second full Stage 2 benchmark run.
- Threshold sensitivity: near-boundary checks around the main heuristic pass-rate cutoffs used by the current Stage 2/3 interpretation.
- Stage 1 to Stage 2 linkage: relationship tables over failing checks and section-level scores, filtered so very small-support signals do not dominate the ranking.
- Outlier flags: prompt/test/pass-rate outliers using IQR heuristics.
- Audit queues: suspicious benchmark defects, redundancy candidates, contradictions, trivial items, and exemplar candidates.
- Detailed reporting: Stage 3 detailed rows focus on Stage 3 checks plus `Notes-X` columns for flagged checks.
- Workbook naming: the stage-local workbook uses `Summary` and `Detailed`; the combined report uses `Stage3_Summary` and `Stage3_Detailed`.
- Stage 3 now supports `batch-run` and `aggregate-batches`; the aggregate step reruns canonical Stage 3 over the union of completed batch indices so global redundancy and relationship analysis stay exact.

Design notes:
- Stage 3 joins existing Stage 1 and Stage 2 outputs; it does not re-run their logic.
- The redundancy analysis remains intentionally interpretable for the take-home, but it now combines lexical, structural, and semantic signals rather than relying only on surface overlap.
- Stage-local note caches are content-addressed, so notes regenerate automatically when the prompt or note evidence changes.
- Embeddings are fetched through the shared LLM gateway in `src/turing_takehome/llm.py` using the local OpenAI-compatible endpoint and cached by content hash.
- If richer metadata arrives later, the same enriched table can support category-balance analysis without changing the core pipeline shape.
- The workbook and JSON exports carry the same combined Stage 1 to Stage 3 content in different wrappers; the workbook is the clearest audit surface for human review.
