# Methodology

Purpose: explain the benchmark-audit design, the role of each stage, and how to interpret the automated pipeline at a high level.

## Problem Framing

The take-home is not only a sample-scoring task. It is a benchmark-governance task: decide whether a newly created coding dataset is trustworthy enough to evaluate a frontier model, and do so with reproducible artifacts rather than ad hoc spot checks.

A naive pass over the dataset would fail in two ways:

- artifact quality and benchmark quality are not the same thing
- a benchmark can look large while still being redundant, broken, or misleading

That is why this repo decomposes the problem into four stages.

## Stage Decomposition

### Stage 1: Sample Requirements Analysis

Question answered:
- Is this sample valid and usable as a benchmark artifact under the annotation guideline?

Method:
- deterministic structural checks
- LLM-assisted guideline judgments
- section-level outputs preserved in a detailed workbook

Why it matters:
- catches malformed prompts, hidden contracts, misalignment, invalid tests, and weak ideal responses before treating a sample as benchmark signal

### Stage 2: Sample Efficacy Analysis

Question answered:
- Does this sample produce meaningful model-evaluation signal when actually executed?

Method:
- solve with `gpt-5-mini`
- extract code
- run execution probe
- run public, private, and generated tests
- preserve per-test, per-attempt, and per-sample artifacts

Why it matters:
- separates static artifact quality from real evaluation behavior
- surfaces execution failures, brittle tests, suspicious public/private divergence, and benchmark-defect candidates

### Stage 3: Dataset Analysis

Question answered:
- Is the dataset, as a whole, a balanced, efficient, and trustworthy benchmark tool?

Method:
- descriptive dataset profile
- redundancy analysis using lexical, structural, and embedding signals
- attempt-variance analysis
- lightweight disagreement analysis
- threshold-sensitivity analysis
- contradiction detection
- ranked audit queues for Stage 4

Why it matters:
- benchmark failure modes often appear across samples rather than within one sample
- Stage 3 turns many individual outputs into benchmark-level conclusions and review priorities

### Stage 4: Manual Audit

Question answered:
- On the highest-value uncertainty surfaced by Stages 1 to 3, where is the pipeline right, where is it wrong, and what action should be taken?

Method:
- queue-driven review packet
- structured calibration-first review template
- human judgments on benchmark trustworthiness, attribution, calibration, and action
- up to a few structured findings per sample, each with defect type, severity, confidence, and short note
- final `Summary` and `Detailed` outputs after reviewer input

Why it matters:
- validates the validator
- turns prioritization into adjudication
- creates the foundation for later calibration of earlier-stage heuristics

## Reproducibility

The repo emphasizes reproducibility in several ways:

- single root entry point in `main.py`
- reviewer entry point in `README.md`
- stable stage-local outputs under `outputs/`
- stable combined workbook and JSON at `outputs/dataset_analysis.xlsx` and `outputs/dataset_analysis.json`
- timestamped historical combined workbook and JSON under `outputs/reports/`
- centralized prompts, traces, and manifests under `artifacts/audit/`
- `run_manifest.json` files per stage
- centralized model and embedding wiring in `src/turing_takehome/llm.py`
- content-addressed caching for note and embedding artifacts

## Why This Decomposition

This decomposition intentionally mirrors how a data organization would reduce risk:

- Stage 1 checks artifact validity
- Stage 2 checks behavioral signal
- Stage 3 checks benchmark quality at the dataset level
- Stage 4 adjudicates the cases where automation is most likely to mislead

The goal is not to automate every decision. The goal is to automate the expensive parts, preserve evidence, and focus scarce human review time where it has the highest value.

## Optional Tightening Workflow

In addition to the core Stage 1 to Stage 4 pipeline, the repo now includes an optional skeptical proxy-audit workflow:

```bash
python main.py --proxy-audit
```

This is not treated as a fifth canonical stage. It is a post-analysis tightening aid used to look for likely pipeline bugs, grader weaknesses, and benchmark defects around the core pipeline.

Its main auditable output is a structured CSV under `outputs/proxy_audit/`.

## What The Current System Should And Should Not Be Trusted For

Trust more:

- deterministic format and contract failures
- execution traces and per-test outcomes
- Stage 3 redundancy and contradiction queues as prioritization signals

Trust less:

- heuristic efficacy labels as if they were calibrated truth
- strict-equality failures when semantic equivalence may exist
- dataset-level difficulty claims that ignore upstream caveats

The repo is strongest as a benchmark-auditing and review-prioritization system. Final benchmark policy should treat the Stage 4 human-eval layer as the reviewer-side adjudication and calibration step.
