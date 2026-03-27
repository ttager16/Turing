# Manual Audit

Status: implemented

Open first if you want:
- the human-eval usage guide: `HUMAN_EVAL_WORKFLOW.md`
- the chosen exemplar note: `EXEMPLAR_SET.md`
- the review packet scaffold: `outputs/manual_audit/review_packet.json`
- the reviewer-authored CSV: `outputs/manual_audit/human_review.csv`

This stage is the human-adjudication layer of the repo. It does not sample randomly. It consumes the highest-value uncertainty surfaced by Stage 3 and turns that into a review packet, a fillable template, and finalized manual-audit outputs once reviewer input is provided.

Inputs:
- canonical Stage 1 workbook
- canonical Stage 2 output directory
- canonical Stage 3 output directory
- optional completed review CSV

Outputs:
- `manual_audit.json`
- `manual_audit.xlsx`
- `review_packet.json`
- `review_template.csv`
- `detailed_rows.csv`
- `run_manifest.json`
- `summary.md`
- centralized review-artifact copies under `artifacts/audit/stage4/` after running `python scripts/build_audit_bundle.py`

Review checks:
- `BenchmarkTrustCheck`
- `FailureAttribution`
- `PipelineCalibrationCheck`
- `FinalAction`
- up to three optional structured findings, each with:
  - defect type
  - severity
  - confidence
  - short note

Interpretation note:
- Stage 4 is a calibration-oriented adjudication layer, not a request to manually rerun Stage 1 and Stage 2.
- The highest-value human signal is whether a sample looks trustworthy as a benchmark item, which concrete defects are present if any, and whether the automated pipeline is overcalling or missing the issue.

Operating note:
- The Stage 4 runner is designed for real human review.
- Any proxy-review or demo-only input used to test the flow should live in `artifacts/tmp/`, not in the Stage 4 implementation itself.
- See `HUMAN_EVAL_WORKFLOW.md` for the intended human-eval flow.
- The preferred local review surface is `python main.py --manual-audit`.
- The review UI autosaves progress to `outputs/manual_audit/human_review.csv` and shows concise observed Stage 2 failed-test evidence as review context.
- `outputs/manual_audit/human_review.csv` is a reviewer-authored artifact, separate from the authoritative automated Stage 1 to Stage 3 run.
- `python main.py --proxy-audit` runs the optional skeptical per-failed-test LLM proxy audit over the current outputs. It is useful for tightening and bug hunting, but it is not canonical Stage 4 human review.
- The proxy audit writes to `outputs/proxy_audit/`. `proxy_bug_hunt.csv` is the main reviewer-facing artifact.
- If no human review has been completed, `human_review.csv` remains an empty scaffold rather than a finished adjudication artifact.
