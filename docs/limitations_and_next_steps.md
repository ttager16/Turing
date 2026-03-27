# Limitations And Next Steps

Purpose: this document is the take-home's public-facing "what I would do with more time" companion. It focuses on the highest-value remaining limitations, their likely downstream consequences, and the next investments that would most improve benchmark trust.

## Current Trust Posture

- The repo is already strong at surfacing suspicious samples, preserving evidence, and routing human attention efficiently.
- High-confidence benchmark policy should incorporate the Stage 4 human-adjudication layer.
- The current authoritative submission state is the final Stage 1 to Stage 3 run. Stage 4 is implemented and review-ready, but final human adjudication is still the intended trust-tightening layer.

## Highest-Priority Next Steps

### 1. Calibrate automated labels against completed human review

- Calibrate Stage 2 efficacy thresholds against a targeted human-reviewed disagreement slice.
- Use completed Stage 4 outcomes to tune Stage 3 queue heuristics, especially contradiction, redundancy, and instability routing.
- Estimate queue precision by Stage 3 flag type so later human review becomes real recalibration data rather than only anecdotal feedback.

### 2. Improve task-aware semantic comparison

- Add tolerant and semantic comparison for outputs where strict equality is too brittle.
- Add explicit task-aware policies for order-insensitive outputs, especially graph-, conduit-, and set-like tasks.
- Add explicit evaluator policy for exception-expected tasks so "correctly raises / returns validation failure" is treated consistently.

### 3. Turn human review into a stronger adjudication system

- Add multi-rater support and formal adjudication rules for disagreements.
- Add richer reviewer metadata such as reviewer ID, timestamps, and disagreement resolution.
- Feed completed Stage 4 judgments back into earlier-stage threshold tuning instead of keeping Stage 4 as a terminal note-taking step.

### 4. Strengthen reproducibility and final-run confidence

- Add a fresh-clone smoke-test path or lightweight CI check so the shipped repo is validated from a clean environment rather than only from the development machine.
- Pin more of the canonical runtime environment explicitly, including clearer model snapshot and dependency capture.
- Version Stage 4 review context against an immutable output snapshot or run manifest so saved human notes cannot silently drift against newer Stage 1 to Stage 3 outputs after a rerun.

## Known Caveats That Can Affect Interpretation

### Semantic-comparison caveats

- Some graph / conduit tasks appear to allow unordered outputs, but the current comparator can still treat list order as significant.
- Likely downstream consequence: samples such as `126` may be overstated as suspicious or high-efficacy when the model output is semantically correct.
- Report implication: any exemplar or benchmark-defect interpretation touching those samples should be caveated until this is adjudicated and rerun.

### Exception-policy caveats

- Some validation-heavy tasks may want "raises the correct exception" or "returns the correct error object" to count as success, but the current execution path is still primarily return-value-oriented.
- Likely downstream consequence: samples like `15` may mix real model weakness with evaluator-policy ambiguity.
- Report implication: those cases should not be framed too confidently as purely model or purely dataset failures.

### Oracle / expected-output caveats

- A subset of late suspicious cases appears dominated by oracle or expected-output issues rather than model logic errors, especially around samples like `121`, `123`, `129`, and parts of `145` to `154`.
- Likely downstream consequence: those samples are still useful benchmark-defect examples, but they should not be used as clean "model breaker" exemplars without a note that benchmark construction may be materially contributing to the failure.

### Context-drift caveat for saved human review

- Today the review UI overlays saved human judgments onto the current live outputs in `outputs/`.
- Likely downstream consequence: if Stages 1 to 3 are rerun later and evidence changes materially, a reviewer inspecting existing human eval may see notes written against an earlier result while the UI displays newer pipeline evidence.
- Operational implication: saved adjudications should eventually be pinned to immutable output snapshots or specific run manifests.

## High-ROI Operational Improvements

- Add a formal per-sample decision table that combines Stages 1 to 4 into a reviewer-facing keep / fix / remove / deprioritize recommendation artifact.
- Expand end-to-end regression coverage around Stage 2 comparison behavior, Stage 4 CSV ingestion, and workbook / JSON parity.
- Add more explicit provenance / confidence metadata to Stage 1 checks so deterministic and LLM-assisted outputs are not interpreted equivalently.
- Add richer run instrumentation such as per-stage wall-clock time, API call counts, cache hit rates, and execution-failure counts by type.

## If This Became A Production Benchmark Program

- Harden code execution isolation into a real sandbox.
- Add stronger schema validation and ingestion-failure handling for malformed source rows.
- Add benchmark contamination guardrails such as canary strings or provenance checks.
- Support richer multi-model comparisons and explicit benchmark-drift tracking over time.

## Recommended Interpretation Until Those Improvements Exist

- Treat the current system as strong at evidence preservation, audit prioritization, and benchmark-risk surfacing.
- Treat current labels as evidence-backed heuristics rather than final benchmark truth.
- Use the completed human-review pass as the final step before converting the current outputs into stronger benchmark policy.
