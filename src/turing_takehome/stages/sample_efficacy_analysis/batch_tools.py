from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from turing_takehome.llm import override_stage_targets
from turing_takehome.reporting import export_combined_report

from .runner import ARTIFACTS_DIR, OUTPUT_DIR, PROJECT_ROOT, run_cli


DEFAULT_BATCH_ROOT = PROJECT_ROOT / "outputs" / "sample_efficacy_analysis_batches"
DEFAULT_AGGREGATED_ROOT = OUTPUT_DIR
STAGE1_WORKBOOK = PROJECT_ROOT / "outputs" / "sample_requirements_analysis" / "guideline_audit.xlsx"


def build_batch_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Stage 2 in resumable sample batches."
    )
    parser.add_argument(
        "--jsonl",
        type=Path,
        default=ARTIFACTS_DIR / "provided" / "Samples.jsonl",
    )
    parser.add_argument("--stage1-workbook", type=Path, default=STAGE1_WORKBOOK)
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_BATCH_ROOT)
    parser.add_argument("--model-targets", default=None)
    parser.add_argument("--attempts", type=int, default=2)
    parser.add_argument("--generated-tests", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=int, default=10)
    parser.add_argument("--k-values", default="1,2")
    parser.add_argument("--skip-llm", action="store_true")
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--end-index", type=int, default=None)
    return parser


def build_aggregate_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Aggregate Stage 2 batch outputs into a single result set."
    )
    parser.add_argument("--batch-root", type=Path, default=DEFAULT_BATCH_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_AGGREGATED_ROOT)
    parser.add_argument("--stage1-workbook", type=Path, default=STAGE1_WORKBOOK)
    return parser


def run_batch_cli(argv: list[str] | None = None) -> int:
    args = build_batch_parser().parse_args(argv)
    output_root = _resolve_path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    sample_count = _count_samples(args.jsonl)
    start_index = max(0, args.start_index)
    end_index = sample_count if args.end_index is None else min(args.end_index, sample_count)
    target_names = _parse_targets(args.model_targets)
    if target_names:
        override_stage_targets(
            "sample-efficacy-analysis",
            primary_target=target_names[0],
            comparison_targets=tuple(target_names),
        )
    for batch_start in range(start_index, end_index, args.batch_size):
        batch_end = min(batch_start + args.batch_size, end_index)
        batch_indices = list(range(batch_start, batch_end))
        batch_dir = output_root / f"batch_{batch_start:03d}_{batch_end - 1:03d}"
        results_path = batch_dir / "sample_results.csv"
        if results_path.exists():
            print(f"Skipping existing batch {batch_dir.name}")
            continue
        batch_dir.mkdir(parents=True, exist_ok=True)
        batch_args = [
            "--jsonl",
            str(args.jsonl),
            "--indices",
            ",".join(str(index) for index in batch_indices),
            "--output-dir",
            str(batch_dir),
            "--stage1-workbook",
            str(_resolve_path(args.stage1_workbook)),
            "--attempts",
            str(args.attempts),
            "--generated-tests",
            str(args.generated_tests),
            "--timeout-seconds",
            str(args.timeout_seconds),
            "--k-values",
            args.k_values,
        ]
        if args.model_targets:
            batch_args.extend(["--model-targets", args.model_targets])
        if args.skip_llm:
            batch_args.append("--skip-llm")
        run_cli(batch_args)
    return 0


def run_aggregate_batches_cli(argv: list[str] | None = None) -> int:
    args = build_aggregate_parser().parse_args(argv)
    batch_root = _resolve_path(args.batch_root)
    output_root = _resolve_path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    batch_dirs = sorted(path for path in batch_root.iterdir() if path.is_dir())

    sample_rows = _collect_jsonl(batch_dirs, "sample_results.jsonl")
    model_rows = _collect_jsonl(batch_dirs, "sample_model_results.jsonl")
    attempt_rows = _collect_jsonl(batch_dirs, "model_attempts.jsonl")
    per_test_rows = _collect_jsonl(batch_dirs, "per_test_results.jsonl")
    manifests = _collect_json(batch_dirs, "run_manifest.json")

    _improve_single_model_notes(sample_rows, model_rows)

    sample_rows = sorted(sample_rows, key=lambda row: int(row["Index"]))
    model_rows = sorted(model_rows, key=lambda row: (int(row["Index"]), str(row["TargetName"])))
    attempt_rows = sorted(
        attempt_rows,
        key=lambda row: (int(row["Index"]), str(row["TargetName"]), int(row["AttemptIndex"])),
    )
    per_test_rows = sorted(
        per_test_rows,
        key=lambda row: (
            int(row["sample_index"]),
            str(row.get("target_name", "")),
            int(row.get("attempt_index", 0)),
            str(row["source"]),
            int(row["case_index"]),
        ),
    )

    _write_jsonl(output_root / "sample_results.jsonl", sample_rows)
    _write_csv(output_root / "sample_results.csv", sample_rows)
    _write_jsonl(output_root / "sample_model_results.jsonl", model_rows)
    _write_csv(output_root / "sample_model_results.csv", model_rows)
    _write_jsonl(output_root / "model_attempts.jsonl", attempt_rows)
    _write_jsonl(output_root / "per_test_results.jsonl", per_test_rows)
    _write_summary(output_root / "summary.md", sample_rows, model_rows, attempt_rows, per_test_rows)
    _write_aggregate_manifest(output_root / "run_manifest.json", manifests)
    stage1_workbook = _resolve_path(args.stage1_workbook)
    if stage1_workbook.exists():
        workbook_path, json_path = export_combined_report(
            stage1_workbook_path=stage1_workbook,
            stage2_output_root=output_root,
        )
        print(f"Wrote combined workbook to {workbook_path}")
        print(f"Wrote combined json to {json_path}")
    print(f"Wrote aggregated Stage 2 outputs to {output_root}")
    return 0


def _collect_jsonl(batch_dirs: list[Path], filename: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for batch_dir in batch_dirs:
        path = batch_dir / filename
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    return rows


def _collect_json(batch_dirs: list[Path], filename: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for batch_dir in batch_dirs:
        path = batch_dir / filename
        if path.exists():
            rows.append(json.loads(path.read_text(encoding="utf-8")))
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_summary(
    path: Path,
    sample_rows: list[dict[str, Any]],
    model_rows: list[dict[str, Any]],
    attempt_rows: list[dict[str, Any]],
    per_test_rows: list[dict[str, Any]],
) -> None:
    winner_counts: dict[str, int] = {}
    suspicious = [row for row in sample_rows if row.get("Suspicious")]
    for row in sample_rows:
        winner = str(row.get("Winner", ""))
        winner_counts[winner] = winner_counts.get(winner, 0) + 1
    by_model: dict[str, list[dict[str, Any]]] = {}
    for row in model_rows:
        by_model.setdefault(str(row["TargetName"]), []).append(row)
    lines = [
        "# Stage 2 Summary",
        "",
        f"Samples evaluated: {len(sample_rows)}",
        f"Model result rows: {len(model_rows)}",
        f"Attempt rows: {len(attempt_rows)}",
        f"Per-test rows: {len(per_test_rows)}",
        "",
        "## Comparison Winners",
    ]
    for key in sorted(winner_counts):
        lines.append(f"- {key}: {winner_counts[key]}")
    lines.extend(["", "## Model Performance"])
    for target_name in sorted(by_model):
        rows = by_model[target_name]
        avg_best_combined = sum(float(row["BestCombinedPassRate"]) for row in rows) / len(rows)
        avg_pass1 = sum(float(row.get("CombinedPass@1", 0.0)) for row in rows) / len(rows)
        lines.append(
            f"- {target_name}: avg best combined pass rate {avg_best_combined:.3f}, avg CombinedPass@1 {avg_pass1:.3f}"
        )
    lines.extend(["", "## Suspicious Samples"])
    if suspicious:
        for row in suspicious:
            lines.append(
                f"- sample {row['Index']} ({row['QuestionId']}): {row['ComparisonNote']}"
            )
    else:
        lines.append("- none")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_aggregate_manifest(path: Path, manifests: list[dict[str, Any]]) -> None:
    batch_dirs = [manifest.get("output_dir", "") for manifest in manifests]
    sample_indices: list[int] = []
    question_ids: list[str] = []
    for manifest in manifests:
        sample_indices.extend(int(value) for value in manifest.get("sample_indices", []))
        question_ids.extend(str(value) for value in manifest.get("question_ids", []))
    payload = {
        "stage": "sample-efficacy-analysis",
        "batched": True,
        "batch_count": len(manifests),
        "batch_output_dirs": batch_dirs,
        "sample_indices": sorted(set(sample_indices)),
        "question_ids": question_ids,
        "source_manifests": manifests,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _improve_single_model_notes(sample_rows: list[dict[str, Any]], model_rows: list[dict[str, Any]]) -> None:
    model_by_index = {int(row["Index"]): row for row in model_rows}
    for row in sample_rows:
        if str(row.get("ComparisonNote", "")).strip() != "single-model run":
            continue
        model_row = model_by_index.get(int(row["Index"]))
        if not model_row:
            continue
        if str(model_row.get("Suspicious", "")) == "True":
            row["ComparisonNote"] = (
                f"single-model run; {model_row.get('BenchmarkQualitySignal', '').strip() or 'needs audit'}"
            )
        else:
            row["ComparisonNote"] = (
                f"single-model run; {model_row.get('EfficacyLabel', '').strip() or 'evaluated'}"
            )


def _count_samples(jsonl_path: Path) -> int:
    return len([line for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()])


def _resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def _parse_targets(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [piece.strip() for piece in raw.split(",") if piece.strip()]
