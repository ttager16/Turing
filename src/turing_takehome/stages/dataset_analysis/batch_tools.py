from __future__ import annotations

import argparse
import json
from pathlib import Path

from .runner import ARTIFACTS_DIR, OUTPUT_DIR, PROJECT_ROOT, STAGE1_WORKBOOK, STAGE2_DIR, run_cli


DEFAULT_BATCH_ROOT = PROJECT_ROOT / "outputs" / "dataset_analysis_batches"
DEFAULT_AGGREGATED_ROOT = OUTPUT_DIR


def build_batch_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Stage 3 in resumable sample batches."
    )
    parser.add_argument(
        "--jsonl",
        type=Path,
        default=ARTIFACTS_DIR / "provided" / "Samples.jsonl",
    )
    parser.add_argument("--stage1-workbook", type=Path, default=STAGE1_WORKBOOK)
    parser.add_argument("--stage2-dir", type=Path, default=STAGE2_DIR)
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_BATCH_ROOT)
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--end-index", type=int, default=None)
    parser.add_argument("--near-duplicate-threshold", type=float, default=0.68)
    parser.add_argument("--template-threshold", type=float, default=0.55)
    parser.add_argument("--cluster-threshold", type=float, default=0.50)
    return parser


def build_aggregate_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Aggregate Stage 3 batch runs into a canonical full Stage 3 output."
    )
    parser.add_argument("--batch-root", type=Path, default=DEFAULT_BATCH_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_AGGREGATED_ROOT)
    parser.add_argument(
        "--jsonl",
        type=Path,
        default=ARTIFACTS_DIR / "provided" / "Samples.jsonl",
    )
    parser.add_argument("--stage1-workbook", type=Path, default=STAGE1_WORKBOOK)
    parser.add_argument("--stage2-dir", type=Path, default=STAGE2_DIR)
    parser.add_argument("--near-duplicate-threshold", type=float, default=0.68)
    parser.add_argument("--template-threshold", type=float, default=0.55)
    parser.add_argument("--cluster-threshold", type=float, default=0.50)
    return parser


def run_batch_cli(argv: list[str] | None = None) -> int:
    args = build_batch_parser().parse_args(argv)
    output_root = _resolve_path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    sample_count = _count_samples(_resolve_path(args.jsonl))
    start_index = max(0, args.start_index)
    end_index = sample_count if args.end_index is None else min(args.end_index, sample_count)
    for batch_start in range(start_index, end_index, args.batch_size):
        batch_end = min(batch_start + args.batch_size, end_index)
        batch_indices = list(range(batch_start, batch_end))
        batch_dir = output_root / f"batch_{batch_start:03d}_{batch_end - 1:03d}"
        payload_path = batch_dir / "dataset_analysis.json"
        if payload_path.exists():
            print(f"Skipping existing batch {batch_dir.name}")
            continue
        batch_dir.mkdir(parents=True, exist_ok=True)
        batch_args = [
            "--jsonl",
            str(_resolve_path(args.jsonl)),
            "--stage1-workbook",
            str(_resolve_path(args.stage1_workbook)),
            "--stage2-dir",
            str(_resolve_path(args.stage2_dir)),
            "--indices",
            ",".join(str(index) for index in batch_indices),
            "--output-dir",
            str(batch_dir),
            "--near-duplicate-threshold",
            str(args.near_duplicate_threshold),
            "--template-threshold",
            str(args.template_threshold),
            "--cluster-threshold",
            str(args.cluster_threshold),
        ]
        run_cli(batch_args)
    return 0


def run_aggregate_batches_cli(argv: list[str] | None = None) -> int:
    args = build_aggregate_parser().parse_args(argv)
    batch_root = _resolve_path(args.batch_root)
    output_dir = _resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifests = _collect_manifests(batch_root)
    sample_indices = sorted(
        {
            int(index)
            for manifest in manifests
            for index in manifest.get("sample_indices", [])
        }
    )
    aggregate_args = [
        "--jsonl",
        str(_resolve_path(args.jsonl)),
        "--stage1-workbook",
        str(_resolve_path(args.stage1_workbook)),
        "--stage2-dir",
        str(_resolve_path(args.stage2_dir)),
        "--output-dir",
        str(output_dir),
        "--near-duplicate-threshold",
        str(args.near_duplicate_threshold),
        "--template-threshold",
        str(args.template_threshold),
        "--cluster-threshold",
        str(args.cluster_threshold),
    ]
    if sample_indices:
        aggregate_args.extend(["--indices", ",".join(str(index) for index in sample_indices)])
    return run_cli(aggregate_args)


def _collect_manifests(batch_root: Path) -> list[dict]:
    manifests: list[dict] = []
    if not batch_root.exists():
        return manifests
    for batch_dir in sorted(path for path in batch_root.iterdir() if path.is_dir()):
        manifest_path = batch_dir / "run_manifest.json"
        if manifest_path.exists():
            manifests.append(json.loads(manifest_path.read_text(encoding="utf-8")))
    return manifests


def _count_samples(jsonl_path: Path) -> int:
    return len([line for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()])


def _resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()
