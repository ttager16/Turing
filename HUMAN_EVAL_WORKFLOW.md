# Human Eval Workflow

Purpose: explain how to use the repo's Stage 4 human-evaluation feature, where annotations are saved, and how to inspect existing human-eval artifacts.

This document is about operating the human-eval workflow inside the repo. It is not a grading guide for evaluating this take-home submission itself.

## Recommended Workflow

Use the local review UI instead of editing the CSV directly:

```bash
python main.py --manual-audit
```

That opens a local browser-based review surface, saves progress automatically, and writes:

- `outputs/manual_audit/human_review.csv`

When you reopen the UI, it lets you work through:

- the curated exemplar set

You can also jump to any dataset index directly. Even if that index is outside the curated exemplar set, the UI will still save it into the same human-review artifact.

If you prefer, you can still edit `outputs/manual_audit/review_template.csv` directly.

## Files You Need

- review packet: `outputs/manual_audit/review_packet.json`
- fillable template: `outputs/manual_audit/review_template.csv`
- canonical saved human review: `outputs/manual_audit/human_review.csv`
- combined context: `outputs/dataset_analysis.xlsx`

## Recommended Review Order

If you use the review UI, you do not need to choose sample indices manually. The UI can guide you through the curated exemplar set automatically.

If you review directly in CSV/JSON instead, use the order in `outputs/manual_audit/run_manifest.json`.

## What To Fill In

The editable columns in `review_template.csv` are:

- `BenchmarkTrustCheck`
- `Notes-BenchmarkTrustCheck`
- `FailureAttribution`
- `Notes-FailureAttribution`
- `PipelineCalibrationCheck`
- `Notes-PipelineCalibrationCheck`
- `FinalAction`
- `Notes-FinalAction`
- `SummaryConfidence`
- `Finding1DefectType`
- `Finding1Severity`
- `Finding1Confidence`
- `Notes-Finding1`
- `Finding2DefectType`
- `Finding2Severity`
- `Finding2Confidence`
- `Notes-Finding2`
- `Finding3DefectType`
- `Finding3Severity`
- `Finding3Confidence`
- `Notes-Finding3`

Use short notes. The goal is to point to what a later reviewer should inspect, not to write a long essay.

Important: Stage 4 is not asking you to re-run Stage 1 and Stage 2 manually. The goal is targeted adjudication. In practice that means:

- do not fully re-solve the coding task unless something looks obviously inconsistent
- use the ideal response and pipeline context to judge whether the sample seems trustworthy as a benchmark item
- use the observed failed-test evidence as a clue about what to inspect, not as automatic ground truth
- focus on likely dataset defects, ambiguity, or miscalibration in the automated pipeline
- if the sample looks clean, a quick `trustworthy` / `agree` / `keep` judgment is enough
- add structured findings only when there is a concrete issue worth recording
- most samples should need zero or one finding; use two or three only when there are clearly distinct issues

## Suggested Label Vocabulary

- `BenchmarkTrustCheck`
  - `trustworthy`
  - `defective`
  - `ambiguous`
- `FindingNDefectType`
  - `none`
  - `prompt_ambiguity`
  - `ideal_response_issue`
  - `test_issue`
  - `alignment_issue`
  - `difficulty_misalignment`
  - `redundancy`
  - `other`
- `FailureAttribution`
  - `model_fail`
  - `dataset_fail`
  - `ambiguous`
- `PipelineCalibrationCheck`
  - `agree`
  - `overstates_problem`
  - `misses_problem`
  - `partially_agree`
- `FinalAction`
  - `keep`
  - `fix`
  - `remove`
- `FindingNSeverity`
  - `low`
  - `medium`
  - `high`
- `SummaryConfidence` / `FindingNConfidence`
  - `low`
  - `medium`
  - `high`

## Finalizing Stage 4

After you finish reviewing in the UI, finalize Stage 4 with:

```bash
python main.py --stage manual-audit --review-input outputs/manual_audit/human_review.csv
```

If you instead edited the template CSV directly, run:

```bash
python main.py --stage manual-audit --review-input outputs/manual_audit/review_template.csv
```

That will refresh:

- `outputs/manual_audit/manual_audit.json`
- `outputs/manual_audit/manual_audit.xlsx`
- the stable combined workbook and JSON at `outputs/dataset_analysis.xlsx` and `outputs/dataset_analysis.json`

## Practical Advice

- prioritize decisive judgment over exhaustive prose
- if a sample is subtly broken, write just enough for future you to find the defect again
- if you are uncertain, use `ambiguous` rather than forcing a sharper claim than the evidence supports
