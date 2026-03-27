# Sample Requirements Analysis

Status: implemented

Open first if you want:
- the Stage 1 workbook: `outputs/sample_requirements_analysis/guideline_audit.xlsx`
- the workbook field guide: `outputs/workbook_field_guide.xlsx`

This stage performs artifact-centric checks on each sample against the annotation guideline. It preserves the original section-based evaluator layout, including the existing `Section 1` through `Section 7` folder structure that currently powers the audit.

Expected inputs:
- `artifacts/provided/Samples.jsonl`
- stage-local evaluator code in this directory
- optional LLM access configured centrally in `src/turing_takehome/llm.py`

Expected outputs:
- workbook under `outputs/sample_requirements_analysis/`
- optional single-column markdown reports
- rendered sample PDFs under `outputs/sample_requirements_analysis/rendered_samples/`
- centralized prompt-template copies under `artifacts/audit/stage1/` after running `python scripts/build_audit_bundle.py`

Notes:
- The current implementation is the migrated legacy codebase with conservative path fixes only.
- Section numbering intentionally reflects the existing evaluator coverage and remains unchanged.
- LLM access is configured centrally in `src/turing_takehome/llm.py`.
- Stage 1 does not preserve full per-call runtime traces in canonical outputs; the audit bundle instead centralizes exact prompt templates and evaluator source references.
- The workbook is the main human-readable review surface for Stage 1.
