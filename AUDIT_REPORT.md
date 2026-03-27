# Audit Report

Purpose: summarize the substantive findings from the automated audit and frame the remaining caveats for reviewer interpretation.

## Executive Summary

I treated the dataset as a benchmark to audit, not just a collection of coding samples to score. The repository therefore separates artifact validity, observed model behavior, dataset-level benchmark health, and targeted adjudication into distinct layers.

Bottom line:

- the dataset is directionally useful, but should be filtered and adjudicated before being treated as a high-trust benchmark
- the strongest current risks are defective tests, redundancy, contradiction between static and dynamic signals, and a long tail of unstable or ambiguous samples
- the pipeline is strongest at preserving evidence and routing human attention efficiently

## Final Automated Outputs

The final full run covered all `155` samples.

Stage 1:

- Prompt: `64` `Unusable`, `91` `Needs Fixing`
- Ideal response: `65` `Unusable`, `90` `Needs Fixing`
- Test cases: `92` `Unusable`, `63` `Needs Fixing`

Stage 2:

- `High Efficacy`: `53`
- `Moderate Efficacy`: `50`
- `Low Efficacy`: `40`
- `Suspicious (Needs Audit)`: `5`
- `Inconclusive`: `7`

Stage 3:

- `19` duplicate pairs
- `20` Stage 1 to Stage 2 relationship rules
- `55` total audit-queue rows

These should be interpreted as audit signals, not as final policy decisions.

## Stage-Level Interpretation

### Stage 1

Stage 1 is a contract-validation layer. Its main value is finding benchmark-artifact defects:

- prompt ambiguity
- hidden or conflicting requirements
- weak or mismatched ideal responses
- malformed or low-quality test cases

Its labels are intentionally conservative. A Stage 1 `Unusable` judgment means “not trustworthy enough as a benchmark artifact,” not “contains zero behavioral signal.”

### Stage 2

Stage 2 tests whether a sample produces meaningful evaluation signal when actually executed. It is strongest where static quality and behavioral quality diverge.

The key takeaway from the final run is that the dataset is not trivial, but it is also noisy:

- some structurally weak samples still produce real model failures
- some apparently difficult samples are likely defective benchmark items
- some outcomes still deserve task-aware semantic comparison rather than plain strict equality

### Stage 3

Stage 3 is where the benchmark-level story becomes clear.

The most important dataset-level findings are:

- real redundancy pressure, including several near-duplicate or semantically duplicate pairs
- contradiction cases where static quality and dynamic behavior disagree strongly
- saturated items that are probably too easy to add much new measurement value
- benchmark-defect candidates where the dataset artifact appears to be part of the failure

This makes the dataset better suited to filtered or caveated evaluation than to blind aggregate benchmarking.

## Exemplar Categories

The pipeline now surfaces useful categories for final discussion and manual review, including:

- benchmark-defect candidates
- contradiction candidates
- redundancy examples
- saturated / trivial items
- strong exemplar items
- disagreement / instability cases

These categories are useful because they translate raw evaluation output into benchmark-governance decisions rather than just scores.

## Optional Tightening Layer

In addition to the core Stage 1 to Stage 4 workflow, the repo also supports an optional LLM proxy audit pass:

```bash
python main.py --proxy-audit
```

This is not part of the core benchmark pipeline and should not be treated as ground truth. Its purpose is to look for:

- likely pipeline bugs
- likely grader or oracle weaknesses
- likely benchmark defects that deserve a closer human look

The proxy audit writes auditable companion artifacts under `outputs/proxy_audit/`. The CSV is the main reviewer-facing output.

That tightening workflow was valuable during development, but real human review remains the final adjudication layer.

## Human Review Positioning

Stage 4 is a targeted adjudication system, not a manual replay of the whole benchmark.

The Stage 4 workflow is implemented as a separate human-authored adjudication layer. The automated findings below should therefore be read as the authoritative Stage 1 to Stage 3 picture, with Stage 4 serving as the intended reviewer-side calibration and action layer.

The human reviewer is asked to answer a narrow set of high-value questions:

- does the sample look trustworthy as a benchmark item?
- if there is a real issue, is it mostly dataset-side or model-side?
- did the automated pipeline diagnose the sample correctly?
- should the sample be kept, fixed, or removed?

That is the right use of human time when the goal is recalibrating an automated benchmark-audit pipeline.

## Recommendations

Immediate:

- filter or downweight the strongest redundancy candidates before using aggregate benchmark claims
- manually adjudicate contradiction and benchmark-defect candidates before treating them as clean benchmark signal
- treat unstable repeated-attempt samples as caveated rather than robust measurement signal

Near-term:

- calibrate Stage 2 thresholds against completed Stage 4 review
- improve task-aware semantic comparison in Stage 2
- use completed manual adjudications to tune Stage 3 queueing heuristics

## Positioning As A Deliverable

The strongest honest positioning for this project is:

- strong on evidence preservation
- strong on reproducibility
- strong on benchmark-audit thinking
- intentionally conservative about claiming benchmark truth without adjudication

## Take-Home Feedback

The take-home is strong because it tests operational judgment, evidence preservation, and benchmark thinking rather than only coding speed. The main improvement I would suggest is a slightly more explicit deliverables checklist up front, especially around expected final artifacts and the intended completion level for the human-review stage.

## Further Work

The substantive roadmap, remaining known caveats, and “what I would do with more time” items are captured in [docs/limitations_and_next_steps.md](docs/limitations_and_next_steps.md).
