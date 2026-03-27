# Architecture

Purpose: describe the repo structure, stage boundaries, artifact layout, and operational design choices.

This codebase is organized as a four-stage benchmark-audit system. Each stage answers a different question, writes auditable artifacts, and hands structured evidence to the next stage.

## Stage Responsibilities

- `src/turing_takehome/stages/sample_requirements_analysis/`
  - Stage 1 asks whether an individual sample is a valid benchmark artifact.
  - It preserves the original section layout and per-check granularity from the take-home spreadsheet.
- `src/turing_takehome/stages/sample_efficacy_analysis/`
  - Stage 2 asks whether an individual sample actually produces useful evaluation signal.
  - It preserves traces, attempts, generated tests, per-test outcomes, and heuristic efficacy labels.
- `src/turing_takehome/stages/dataset_analysis/`
  - Stage 3 asks whether the dataset is a trustworthy benchmark as a whole.
  - It focuses on redundancy, attempt stability, lightweight disagreement, threshold sensitivity, contradiction detection, and audit queues.
- `src/turing_takehome/stages/manual_audit/`
  - Stage 4 asks a human reviewer to adjudicate the most decision-relevant uncertainty surfaced by Stage 3.
  - It produces review packets, templates, final manual-audit rows, and combined reports.

## Shared Layers

- `main.py`
  - Single root entry point for all stages and the optional proxy-audit / review-UI workflows.
- `src/turing_takehome/llm.py`
  - Centralized provider wiring for OpenAI and OpenAI-compatible targets.
  - Also owns async request execution, content-addressed note caching, and embedding access.
- `src/turing_takehome/reporting/combined.py`
  - Shared workbook and JSON export layer.
  - Extends the same report object with stage-local sections instead of inventing parallel reporting formats.

## Artifact Layout

- `artifacts/provided/`
  - Source inputs supplied with the take-home.
- `outputs/<stage>/`
  - Canonical stage-local outputs.
- `outputs/dataset_analysis.xlsx` and `outputs/dataset_analysis.json`
  - Stable combined artifacts for reviewer consumption.
- `outputs/reports/`
  - Timestamped historical combined workbook and JSON artifacts.
- `artifacts/audit/`
  - Centralized prompt, trace, and manifest bundle for reviewer inspection.
- `artifacts/tmp/`
  - Noncanonical runs, batch scratch state, and demo-only artifacts.
- `submission_artifacts/`
  - Frozen copies of the final deliverable outputs so the shipped state is preserved even if `outputs/` is regenerated.

## Design Principles

- Preserve auditability over cleverness.
- Preserve evidence instead of collapsing too early to a single score.
- Keep later stages dependent on earlier artifacts, not copies of earlier logic.
- Prefer stage-local `Detailed` and `Summary` views over oversized aggregate dumps.
- Keep the machine-readable JSON structurally aligned with the human-readable workbook.

## Operational Notes

- Stages 1 to 3 support resumable `batch-run` plus `aggregate-batches`.
- Stage 3 aggregate reruns canonical Stage 3 over the union of completed indices so redundancy and relationship claims remain truly dataset-level.
- Stage 4 is intentionally lightweight and queue-driven. It is designed to fit within a constrained human-review budget rather than to become another heavyweight automated stage.
