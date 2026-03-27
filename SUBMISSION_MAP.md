# Submission Map

Purpose: map the assignment asks to the concrete artifacts in this repository.

## If You Only Open Six Things

1. [README.md](README.md)
2. [final_report.docx](final_report.docx)
3. [METHODOLOGY.md](METHODOLOGY.md)
4. [AUDIT_REPORT.md](AUDIT_REPORT.md)
5. [MODEL_AND_RUN_SUMMARY.md](MODEL_AND_RUN_SUMMARY.md)
6. [EXEMPLAR_SET.md](EXEMPLAR_SET.md)

Then inspect the stable combined outputs:

- [outputs/dataset_analysis.xlsx](outputs/dataset_analysis.xlsx)
- [outputs/dataset_analysis.json](outputs/dataset_analysis.json)
- [outputs/workbook_field_guide.xlsx](outputs/workbook_field_guide.xlsx)

The workbook and JSON carry the same combined Stage 1 to Stage 3 content in different wrappers. Open the workbook first if you want the clearest review surface.

## Assignment Ask -> Artifact

Process / workflow used to validate data quality:

- [README.md](README.md)
- [METHODOLOGY.md](METHODOLOGY.md)
- [MODEL_AND_RUN_SUMMARY.md](MODEL_AND_RUN_SUMMARY.md)
- [docs/workflow.md](docs/workflow.md)
- [docs/architecture.md](docs/architecture.md)

Artifacts built, including scripts, prompts, and traces:

- [main.py](main.py)
- [scripts/setup_repo.py](scripts/setup_repo.py)
- [scripts/check_setup.py](scripts/check_setup.py)
- [artifacts/audit/README.md](artifacts/audit/README.md)

Quality issues found in the dataset, guideline, or data format:

- [AUDIT_REPORT.md](AUDIT_REPORT.md)
- [EXEMPLAR_SET.md](EXEMPLAR_SET.md)
- [outputs/dataset_analysis.xlsx](outputs/dataset_analysis.xlsx)
- [outputs/dataset_analysis.json](outputs/dataset_analysis.json)
- [outputs/workbook_field_guide.xlsx](outputs/workbook_field_guide.xlsx)

Reproducible outputs:

- [outputs/sample_requirements_analysis/](outputs/sample_requirements_analysis/)
- [outputs/sample_efficacy_analysis/](outputs/sample_efficacy_analysis/)
- [outputs/dataset_analysis/](outputs/dataset_analysis/)
- [outputs/manual_audit/](outputs/manual_audit/)
- [RUN_MANIFEST.json](RUN_MANIFEST.json)

Manual review workflow:

- [HUMAN_EVAL_WORKFLOW.md](HUMAN_EVAL_WORKFLOW.md)
- [EXEMPLAR_SET.md](EXEMPLAR_SET.md)
- `python main.py --manual-audit`

Optional post-analysis tightening workflow:

- `python main.py --proxy-audit`
  - writes secondary companion artifacts under `outputs/proxy_audit/`
  - `proxy_bug_hunt.csv` is the main reviewer-facing output
  - this workflow is intentionally separate from the canonical Stage 1 to Stage 4 deliverables

What I would do with more time:

- [docs/limitations_and_next_steps.md](docs/limitations_and_next_steps.md)
