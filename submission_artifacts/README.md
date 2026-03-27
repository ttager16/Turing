# Submission Artifacts

Purpose: frozen copies of the canonical deliverable outputs, preserved so the shipped state survives even if the live pipeline is rerun.

The live pipeline writes to `outputs/`. This folder preserves the same deliverables as a frozen snapshot.

## Open These First

- `dataset_analysis.xlsx` OR `dataset_analysis.json`
- `workbook_field_guide.xlsx`
- `RUN_MANIFEST.json`

## What The Main Files Are

- `dataset_analysis.xlsx`
  - the main human-readable combined Stage 1 to Stage 3 workbook
- `dataset_analysis.json`
  - the same combined content in machine-readable form
- `workbook_field_guide.xlsx`
  - companion guide explaining workbook fields, labels, decision logic, prompts, and code locations
- `RUN_MANIFEST.json`
  - provenance for the authoritative run and frozen outputs

## Why There Are Also Stage Subfolders

The root of this folder is the quick reviewer surface.

The stage subfolders preserve the stage-local frozen outputs and manifests that sit behind those top-level files:

- `sample_requirements_analysis/`
  - frozen Stage 1 workbook
- `sample_efficacy_analysis/`
  - frozen Stage 2 CSV outputs and manifest
- `dataset_analysis/`
  - frozen stage-local Stage 3 outputs and manifest
- `manual_audit/`
  - frozen Stage 4 workflow artifacts

This is why some files appear twice. For example, the combined Stage 3 workbook and JSON are available both at the root of this folder and inside `dataset_analysis/`.

## Manual Audit Note

`manual_audit/human_review.csv` is the reviewer-authored file.

If no human review was completed, it remains an empty scaffold rather than a finished adjudication artifact.
