# Turing Take-Home Benchmark Audit

Purpose: reviewer-facing entrypoint for understanding the repo, reproducing the pipeline, and locating the canonical artifacts.

This repository audits the supplied coding dataset as a benchmark, not just as a collection of samples. The workflow has four stages:

1. Stage 1: sample requirements analysis
2. Stage 2: sample efficacy analysis
3. Stage 3: dataset analysis
4. Stage 4: targeted human adjudication

## Open These First

1. [SUBMISSION_MAP.md](SUBMISSION_MAP.md)
2. [final_report.docx](final_report.docx)
3. [METHODOLOGY.md](METHODOLOGY.md)
4. [AUDIT_REPORT.md](AUDIT_REPORT.md)
5. [MODEL_AND_RUN_SUMMARY.md](MODEL_AND_RUN_SUMMARY.md)
6. [EXEMPLAR_SET.md](EXEMPLAR_SET.md)

Then inspect the stable combined artifacts:

- [outputs/dataset_analysis.xlsx](outputs/dataset_analysis.xlsx)
- [outputs/dataset_analysis.json](outputs/dataset_analysis.json)
- [outputs/workbook_field_guide.xlsx](outputs/workbook_field_guide.xlsx)

The workbook and JSON carry the same combined Stage 1 to Stage 3 content in different wrappers. Open the workbook first if you want the clearest review surface.

## Repo Map

- [main.py](main.py): single runtime entrypoint
- [src/turing_takehome/](src/turing_takehome/): stage logic, shared LLM gateway, reporting
- [outputs/](outputs/): canonical working outputs used by the pipeline
- [submission_artifacts/](submission_artifacts/): frozen copies of deliverable outputs so a rerun does not destroy the shipped state
- [artifacts/audit/](artifacts/audit/): centralized prompts, traces, manifests, and reviewer-facing audit artifacts
- [artifacts/provided/](artifacts/provided/): assignment inputs
- `artifacts/tmp/`: noncanonical scratch, smoke, and debugging artifacts; not intended for evaluator review

## Setup

1. Create a virtual environment:

```bash
python -m venv .venv
```

2. Activate it.

Windows:

```bash
.venv\Scripts\activate
```

macOS / Linux:

```bash
source .venv/bin/activate
```

3. Install dependencies:

```bash
python -m pip install -r requirements.txt
```

4. Export your OpenAI API key for `gpt-5-mini`.

Windows PowerShell:

```powershell
$env:OPENAI_API_KEY="..."
```

macOS / Linux:

```bash
export OPENAI_API_KEY="..."
```

5. Install the embedding model in LM Studio.

Use LM Studio, not Hugging Face, and download:

- model: `nomic-ai/nomic-embed-text-v1.5-GGUF`
- quantization: `Q4_0`

Expose it locally as:

- `text-embedding-nomic-embed-text-v1.5`

Optional local-model environment variables are documented in [.env.example](.env.example).

6. Run the environment check:

```bash
python scripts/check_setup.py
```

## Reproduction

Run the canonical automated pipeline:

```bash
python main.py
```

Run a smaller slice:

```bash
python main.py --limit 5
```

Run a batched pipeline:

```bash
python main.py --batch-size 5
```

Launch the Stage 4 review UI:

```bash
python main.py --manual-audit
```

Run the optional LLM proxy audit:

```bash
python main.py --proxy-audit
```

This proxy audit is not part of the canonical Stage 1 to Stage 4 deliverables. It is a secondary tightening workflow used to look for likely pipeline bugs, grader weaknesses, and benchmark defects after the core analysis has completed.

Its output lives under `outputs/proxy_audit/`. `proxy_bug_hunt.csv` is the primary auditable artifact.

## Canonical Outputs

Stable combined artifacts:

- [outputs/dataset_analysis.xlsx](outputs/dataset_analysis.xlsx)
- [outputs/dataset_analysis.json](outputs/dataset_analysis.json)
- [outputs/workbook_field_guide.xlsx](outputs/workbook_field_guide.xlsx)

Stage-specific outputs:

- Stage 1: [outputs/sample_requirements_analysis/guideline_audit.xlsx](outputs/sample_requirements_analysis/guideline_audit.xlsx)
- Stage 2: [outputs/sample_efficacy_analysis/](outputs/sample_efficacy_analysis/)
- Stage 3: [outputs/dataset_analysis/](outputs/dataset_analysis/)
- Stage 4: [outputs/manual_audit/](outputs/manual_audit/)

Human review artifact:

- [outputs/manual_audit/human_review.csv](outputs/manual_audit/human_review.csv)

## Reviewer Paths

If you want the methodology:

- [METHODOLOGY.md](METHODOLOGY.md)
- [MODEL_AND_RUN_SUMMARY.md](MODEL_AND_RUN_SUMMARY.md)
- [docs/workflow.md](docs/workflow.md)
- [docs/architecture.md](docs/architecture.md)

If you want the findings:

- [AUDIT_REPORT.md](AUDIT_REPORT.md)
- [EXEMPLAR_SET.md](EXEMPLAR_SET.md)
- [outputs/dataset_analysis.xlsx](outputs/dataset_analysis.xlsx)
- [outputs/workbook_field_guide.xlsx](outputs/workbook_field_guide.xlsx)

Quick triage for "is this a meaningful and reliable eval sample?":

- Stage 1 Summary:
  - `Prompt`
  - `Ideal Response`
  - `Test Cases`
- Stage 2 Summary:
  - `EfficacyLabel`
  - `BenchmarkQualitySignal`
  - `OraclePassRate`

That is the fastest high-signal read on whether a sample looks clear enough to evaluate, trustworthy enough to grade, and useful enough to expose real model behavior.

If you want prompts, traces, and manifests:

- [artifacts/audit/README.md](artifacts/audit/README.md)

If you want the manual-review workflow:

- [HUMAN_EVAL_WORKFLOW.md](HUMAN_EVAL_WORKFLOW.md)
- [EXEMPLAR_SET.md](EXEMPLAR_SET.md)

If you want frozen copies of the shipped outputs:

- [submission_artifacts/](submission_artifacts/)

## What This Repo Does Not Claim

- Stage 2 is execution-backed but still uses heuristic classification thresholds.
- Stage 3 queueing and prioritization are intended as audit routing signals, not final policy by themselves.
- Stage 4 is the final adjudication layer, and its artifacts are reviewer-authored rather than automated.
- Semantic equivalence remains partially heuristic for some task types, especially order-insensitive structured outputs.

## More Detail

- [SUBMISSION_MAP.md](SUBMISSION_MAP.md)
- [docs/limitations_and_next_steps.md](docs/limitations_and_next_steps.md)
