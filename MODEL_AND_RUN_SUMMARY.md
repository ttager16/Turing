# Model And Run Summary

Purpose: concise factual summary of the authoritative run, the models used by each stage, and the main reproducibility caveats.

## Authoritative Run

- Authoritative run scope: final full-dataset Stage 1 to Stage 3 run over all 155 samples
- Authoritative timestamp: `2026-03-26T09:29:15Z`
- Authoritative entrypoint: `python main.py`
- Canonical combined outputs:
  - [outputs/dataset_analysis.xlsx](outputs/dataset_analysis.xlsx)
  - [outputs/dataset_analysis.json](outputs/dataset_analysis.json)
- Frozen submission copies:
  - [submission_artifacts/](submission_artifacts/)

Why this run is authoritative:
- it is the final full-dataset Stage 1 to Stage 3 run reflected by the stable root-level outputs
- those outputs are the ones linked from the public reviewer docs
- the frozen submission copies were taken from this state so reruns do not destroy the shipped artifacts

## Stage-by-Stage Models

### Stage 1

- Primary mechanism: mixed deterministic checks plus LLM-assisted judgment for the more subjective artifact-quality checks
- LLM target: same primary OpenAI-backed target family used elsewhere in the repo
- Canonical output:
  - [outputs/sample_requirements_analysis/guideline_audit.xlsx](outputs/sample_requirements_analysis/guideline_audit.xlsx)

### Stage 2

- Solver target: `openai-gpt-5-mini`
- Model label in outputs: `openai:gpt-5-mini`
- Attempts per sample: `2`
- Generated tests per sample: `3`
- Generated-test authoring target: `openai-gpt-5-mini`
- Canonical outputs:
  - [outputs/sample_efficacy_analysis/sample_results.csv](outputs/sample_efficacy_analysis/sample_results.csv)
  - [outputs/sample_efficacy_analysis/sample_model_results.csv](outputs/sample_efficacy_analysis/sample_model_results.csv)

### Stage 3

- Core analysis: deterministic aggregation and heuristic synthesis over Stage 1 and Stage 2 outputs
- Embedding model: `text-embedding-nomic-embed-text-v1.5`
- Embedding source: local OpenAI-compatible endpoint via LM Studio
- LM Studio install target: `nomic-ai/nomic-embed-text-v1.5-GGUF`, quantization `Q4_K_M`
- Optional lightweight auditor: a small LLM-backed disagreement helper used only for a narrow Stage 3 disagreement signal
- Canonical outputs:
  - [outputs/dataset_analysis/dataset_analysis.xlsx](outputs/dataset_analysis/dataset_analysis.xlsx)
  - [outputs/dataset_analysis/dataset_analysis.json](outputs/dataset_analysis/dataset_analysis.json)

### Stage 4

- Stage 4 is human-in-the-loop, not part of the authoritative automated run
- Current human-review artifact:
  - [outputs/manual_audit/human_review.csv](outputs/manual_audit/human_review.csv)
- Stage 4 artifacts are reviewer-authored and separate from the authoritative automated Stage 1 to Stage 3 run

## Included Vs Excluded Work

Included in authoritative claims:
- final Stage 1 workbook
- final Stage 2 sample and model result CSVs
- final Stage 3 workbook and JSON
- stable combined root-level workbook and JSON

Exploratory or secondary only:
- proxy audit under `outputs/proxy_audit/`
- intermediate batch outputs under `artifacts/tmp/`
- Stage 4 reviewer-authored artifacts under `outputs/manual_audit/`

## Environment Summary

- OS used for the authoritative run: `Windows-11-10.0.26200-SP0`
- Python used for manifest refresh and artifact inspection: `3.14.3`
- Dependency install path expected by the repo:
  - `python -m pip install -r requirements.txt`
- External service requirements:
  - OpenAI API key for `gpt-5-mini`
  - local LM Studio embedding endpoint serving `text-embedding-nomic-embed-text-v1.5`

## Reproducibility Caveats

- LLM-backed stages are nondeterministic across reruns even when code and inputs are unchanged.
- Stage 2 and Stage 3 labels are heuristic, so exact labels can shift if upstream LLM behavior shifts.
- Stage 4 is intentionally separate from the authoritative automated run because it is a human-authored adjudication layer.
- The root-level manifest with exact output paths and file metadata is:
  - [RUN_MANIFEST.json](RUN_MANIFEST.json)
