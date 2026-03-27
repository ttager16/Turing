# Audit Artifact Index

Purpose: central index for the preserved prompts, traces, and manifests that support the benchmark audit.

This folder is the centralized reviewer-facing prompt, trace, and manifest surface.

## Open These First

- [README.md](../../README.md)
- [SUBMISSION_MAP.md](../../SUBMISSION_MAP.md)
- [METHODOLOGY.md](../../METHODOLOGY.md)
- [AUDIT_REPORT.md](../../AUDIT_REPORT.md)
- [RUN_MANIFEST.json](../../RUN_MANIFEST.json)
- [workbook_field_guide.xlsx](../../outputs/workbook_field_guide.xlsx)
- [bundle_manifest.json](bundle_manifest.json)

## Folder Layout

- `stage1/`
  - extracted Stage 1 prompt templates
  - Stage 1 trace note
- `stage2/`
  - copied runtime prompts and traces from the canonical Stage 2 run
- `stage3/`
  - copied Stage 3 auditor traces, embedding traces, and key analysis artifacts
- `stage4/`
  - copied review packet, review template, and current human-review artifacts
- `run_manifests/`
  - root and stage-local run manifests

## Assignment Mapping

The assignment asks for workflow artifacts, scripts, LLM prompts, and traces.

This bundle centralizes:

- exact Stage 1 prompt templates
- full Stage 2 runtime request and response traces
- Stage 3 auditor and embedding traces
- Stage 4 review packet artifacts
- current Stage 4 reviewer-save artifact when present
- the manifests needed to understand what was run

Runtime entrypoint:

- `python main.py`

Human review UI:

- `python main.py --manual-audit`

Optional proxy audit:

- `python main.py --proxy-audit`

Bootstrap helper:

- `python scripts/setup_repo.py`

## Important Caveats

Stage 1 is intentionally lighter than Stage 2 in runtime trace preservation.

- exact prompt templates are preserved here
- the canonical Stage 1 run does not persist per-call request and response logs
- that is a property of the original stage design, not a missing copy step in this audit bundle

Stage 4 caveat:

- Stage 4 is a separate human-authored adjudication layer
- treat `outputs/manual_audit/human_review.csv` as a reviewer artifact rather than as part of the authoritative automated Stage 1 to Stage 3 run

Output-wrapper note:

- the workbook and JSON variants of the main outputs carry the same information in different wrappers
- open the workbook first if you want the clearest review surface

## Rebuilding The Bundle

```bash
python scripts/build_audit_bundle.py
```
