# Sample Efficacy Analysis

Status: implemented

Open first if you want:
- the per-sample Stage 2 results: `outputs/sample_efficacy_analysis/sample_results.csv`
- the per-model Stage 2 results: `outputs/sample_efficacy_analysis/sample_model_results.csv`
- the workbook field guide: `outputs/workbook_field_guide.xlsx`

This stage runs model-centric executable evaluation for each sample, including prompt construction, multi-attempt code generation, code extraction, isolated execution, generated edge-case tests, sample-level comparison, and efficacy labeling.

Expected inputs:
- curated samples and metadata from `artifacts/provided/`
- centralized LLM configuration in `src/turing_takehome/llm.py`
- runtime limits supplied via the Stage 2 CLI

Expected outputs:
- per-sample comparison results in CSV and JSONL
- per-model results in CSV and JSONL
- attempt-level results in JSONL
- per-test results in JSONL
- a run manifest describing the evaluated subset and model configuration
- execution traces under `outputs/sample_efficacy_analysis/traces/`
- a lightweight summary report
- a centralized audit mirror under `artifacts/audit/stage2/` after running `python scripts/build_audit_bundle.py`

Notes:
- The current implementation supports both development slices and canonical full-dataset runs.
- The default canonical configuration is single-model Stage 2 with `openai-gpt-5-mini`.
- Additional model targets can still be supplied explicitly through the CLI when comparison runs are useful.
- It preserves traces and distinguishes generation, execution, logical, and benchmark-suspicion failures.
- The CSV outputs are the main review surface here; the trace folders provide the underlying prompt, candidate, and execution evidence when deeper inspection is needed.
