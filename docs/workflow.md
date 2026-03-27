# Workflow

This is the intended operating workflow for the repo in its current delivery state.

## Canonical Flow

1. Start from the provided files in `artifacts/provided/`.
2. Run `python scripts/setup_repo.py` or do the equivalent manual setup.
3. Run `python scripts/check_setup.py`.
4. Run Stage 1 with `python main.py --stage sample-requirements-analysis`.
5. Run Stage 2 with `python main.py --stage sample-efficacy-analysis`.
6. Run Stage 3 with `python main.py --stage dataset-analysis`.
7. Run Stage 4 with `python main.py --stage manual-audit` to generate the review packet and template.
8. After a human reviewer fills the template, rerun Stage 4 with `--review-input` to finalize the manual-audit outputs and refresh the combined report.
9. Optionally run `python main.py --proxy-audit` as a skeptical post-analysis tightening pass over the current outputs.
   - This writes secondary companion artifacts under `outputs/proxy_audit/`.
   - Treat `proxy_bug_hunt.csv` as the main reviewer-facing output from that pass.

## Development Slices

- For Stage 2, use `--limit 5` or `--indices ...` during development.
- For Stage 4, it is safe to regenerate the review packet repeatedly because it is fast and downstream only from the canonical Stage 3 outputs.

## One-Command Reproduction

- `python main.py` reproduces canonical Stages 1 to 3.
- Add `--prepare-stage4` to also generate the Stage 4 review packet and template.
- Use `--limit N` for a smaller slice.
- Stage 4 finalization remains a separate human-in-the-loop step because reviewer input is intentionally external to the automated pipeline.

## Batch Workflow

1. Use each stage's `batch-run` tool with `--batch-size 10` when a long rerun needs resumability.
2. Re-run the same command safely; completed batch folders are skipped.
3. Use `aggregate-batches` to write the canonical stage-local outputs.
4. For Stage 3 specifically, treat per-batch outputs as provisional only. The aggregate step reruns canonical Stage 3 across the union of completed indices so cross-sample claims stay exact.
5. Keep batch roots and smoke runs in `artifacts/tmp/`.

## Review Workflow

- Stage 4 is queue-driven, not random-sample-driven.
- The default review slice is budgeted for roughly 20 to 30 samples.
- The preferred review surface is `python main.py --manual-audit`.
- The human task is calibration-oriented adjudication:
  - benchmark trustworthiness
  - likely model-vs-dataset attribution
  - whether the automated pipeline is directionally right
  - up to a few concrete structured findings with defect type, severity, confidence, and a short note
- The intended order of attention is:
  - contradictions
  - disagreement and instability
  - redundancy representatives
  - clean baseline samples

## Practical Guardrails

- Canonical outputs belong only in `outputs/`.
- Centralized reviewer-facing prompts, traces, and manifests belong in `artifacts/audit/`.
- Demo, proxy, or scratch review artifacts belong in `artifacts/tmp/`.
- The optional proxy audit is a post-analysis tightening workflow, not part of the canonical Stage 1 to Stage 4 pipeline.
- Its artifacts should be interpreted as companion bug-hunting evidence, not as primary benchmark outputs.
- If output schema changes, regenerate only the affected downstream stages instead of rerunning the full pipeline unnecessarily.
