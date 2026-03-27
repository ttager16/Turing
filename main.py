from __future__ import annotations

import argparse
import importlib
import sys
import time
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from turing_takehome.runtime_setup import ensure_preflight, load_local_env

STAGE_CHOICES = (
    "all",
    "sample-requirements-analysis",
    "sample-efficacy-analysis",
    "dataset-analysis",
    "manual-audit",
)

STAGE_SECONDS_PER_SAMPLE = {
    "sample-requirements-analysis": 18.5,
    "sample-efficacy-analysis": 81.8,
    "dataset-analysis": 2.9,
    "manual-audit": 2.0,
}
DEFAULT_STAGE4_PACKET_SIZE = 26


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Repository entry point for the four-stage take-home workflow."
    )
    parser.add_argument("--stage", default="all", choices=STAGE_CHOICES)
    parser.add_argument(
        "--manual-audit",
        action="store_true",
        help="Launch the Stage 4 review UI directly.",
    )
    parser.add_argument(
        "--proxy-audit",
        action="store_true",
        help="Run the optional LLM proxy audit over the current outputs.",
    )
    parser.add_argument(
        "--tool",
        default=None,
        help=(
            "Optional stage-specific tool. "
            "Stage 1: audit, render-samples, batch-run, aggregate-batches. "
            "Stage 2 and Stage 3: run, batch-run, aggregate-batches. "
            "Stage 4: run, review-ui, proxy-bug-hunt."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional sample limit for development slices when running canonical stages.",
    )
    parser.add_argument(
        "--prepare-stage4",
        action="store_true",
        help="When running --stage all, also generate the Stage 4 review packet and template.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help=(
            "Optional top-level batch size. "
            "When used with --stage all, orchestrates Stage 1-3 batch-run/aggregate-batches automatically."
        ),
    )
    parser.add_argument(
        "--batch-output-root",
        type=Path,
        default=None,
        help="Optional root directory for top-level batched pipeline outputs.",
    )
    parser.add_argument("--start-index", type=int, default=0, help="Optional batch start index for batched runs.")
    parser.add_argument("--end-index", type=int, default=None, help="Optional batch end index (exclusive) for batched runs.")
    return parser


def import_stage_module(stage_name: str):
    module_name = stage_name.replace("-", "_")
    return importlib.import_module(f"turing_takehome.stages.{module_name}")


def _dataset_size() -> int:
    samples_path = PROJECT_ROOT / "artifacts" / "provided" / "Samples.jsonl"
    if not samples_path.exists():
        return 0
    with samples_path.open("r", encoding="utf-8") as handle:
        return sum(1 for _ in handle)


def _extract_override_value(flag_name: str, remaining: list[str]) -> str | None:
    for index, value in enumerate(remaining):
        if value == flag_name and index + 1 < len(remaining):
            return remaining[index + 1]
        if value.startswith(flag_name + "="):
            return value.split("=", 1)[1]
    return None


def _estimate_sample_count(stage_name: str, args, remaining: list[str]) -> int:
    if stage_name == "manual-audit":
        return DEFAULT_STAGE4_PACKET_SIZE
    indices_value = _extract_override_value("--indices", remaining)
    if indices_value:
        return len([item for item in indices_value.split(",") if item.strip()])
    limit_value = _extract_override_value("--limit", remaining)
    if limit_value:
        try:
            return max(1, int(limit_value))
        except ValueError:
            pass
    if args.limit is not None:
        return max(1, args.limit)
    return _dataset_size()


def _estimate_stage_seconds(stage_name: str, args, remaining: list[str]) -> float:
    return _estimate_sample_count(stage_name, args, remaining) * STAGE_SECONDS_PER_SAMPLE.get(stage_name, 0.0)


def _format_seconds(seconds: float) -> str:
    total_seconds = max(0, int(round(seconds)))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _format_finish_time(seconds_from_now: float) -> str:
    local_tz = datetime.now().astimezone().tzinfo
    return datetime.fromtimestamp(
        time.time() + max(0, seconds_from_now),
        tz=local_tz,
    ).strftime("%Y-%m-%d %I:%M %p %Z")


def _run_stage(stage_name: str, args, remaining: list[str]) -> int:
    if args.stage == "all" and args.tool is not None:
        raise SystemExit("--tool is not supported when running the full pipeline.")
    stage_remaining = list(remaining)
    if args.limit is not None and stage_name in {
        "sample-requirements-analysis",
        "sample-efficacy-analysis",
        "dataset-analysis",
    } and "--limit" not in stage_remaining:
        stage_remaining.extend(["--limit", str(args.limit)])

    if stage_name == "sample-requirements-analysis":
        sample_requirements_analysis = import_stage_module(stage_name)
        tool = args.tool or "audit"
        if tool == "audit":
            return sample_requirements_analysis.run_cli(stage_remaining)
        if tool == "render-samples":
            return sample_requirements_analysis.run_render_samples_cli(stage_remaining)
        if tool == "batch-run":
            return sample_requirements_analysis.run_batch_cli(stage_remaining)
        if tool == "aggregate-batches":
            return sample_requirements_analysis.run_aggregate_batches_cli(stage_remaining)
        raise SystemExit(
            "Unsupported tool for sample-requirements-analysis. "
            "Use 'audit', 'render-samples', 'batch-run', or 'aggregate-batches'."
        )

    if stage_name == "sample-efficacy-analysis":
        sample_efficacy_analysis = import_stage_module(stage_name)
        tool = args.tool or "run"
        if tool == "run":
            return sample_efficacy_analysis.run_cli(stage_remaining)
        if tool == "batch-run":
            return sample_efficacy_analysis.run_batch_cli(stage_remaining)
        if tool == "aggregate-batches":
            return sample_efficacy_analysis.run_aggregate_batches_cli(stage_remaining)
        raise SystemExit(
            "Unsupported tool for sample-efficacy-analysis. "
            "Use 'run', 'batch-run', or 'aggregate-batches'."
        )

    if stage_name == "dataset-analysis":
        dataset_analysis = import_stage_module(stage_name)
        tool = args.tool or "run"
        if tool == "run":
            return dataset_analysis.run_cli(stage_remaining)
        if tool == "batch-run":
            return dataset_analysis.run_batch_cli(stage_remaining)
        if tool == "aggregate-batches":
            return dataset_analysis.run_aggregate_batches_cli(stage_remaining)
        raise SystemExit(
            "Unsupported tool for dataset-analysis. "
            "Use 'run', 'batch-run', or 'aggregate-batches'."
        )

    if stage_name == "manual-audit":
        manual_audit = import_stage_module(stage_name)
        tool = args.tool or "run"
        if tool == "run":
            return manual_audit.run_cli(stage_remaining)
        if tool == "review-ui":
            return manual_audit.run_review_ui_cli(stage_remaining)
        if tool == "proxy-bug-hunt":
            return manual_audit.run_proxy_bug_hunt_cli(stage_remaining)
        raise SystemExit(
            "Unsupported tool for manual-audit. Use 'run', 'review-ui', or 'proxy-bug-hunt'."
        )

    raise SystemExit(f"Unhandled stage '{stage_name}'.")


def _run_all_batched(args, remaining: list[str]) -> int:
    if args.tool is not None:
        raise SystemExit("--tool is not supported when using top-level batched full-pipeline mode.")
    batch_size = max(1, int(args.batch_size or 0))
    batch_root = (
        args.batch_output_root.resolve()
        if args.batch_output_root is not None
        else (PROJECT_ROOT / "outputs" / "pipeline_batches").resolve()
    )
    stage1_batch_root = batch_root / "stage1_batches"
    stage2_batch_root = batch_root / "stage2_batches"
    stage3_batch_root = batch_root / "stage3_batches"
    stage1_output = (PROJECT_ROOT / "outputs" / "sample_requirements_analysis").resolve()
    stage2_output = (PROJECT_ROOT / "outputs" / "sample_efficacy_analysis").resolve()
    stage3_output = (PROJECT_ROOT / "outputs" / "dataset_analysis").resolve()

    stage1_module = import_stage_module("sample-requirements-analysis")
    stage2_module = import_stage_module("sample-efficacy-analysis")
    stage3_module = import_stage_module("dataset-analysis")

    stage1_batch_args = [
        "--batch-size",
        str(batch_size),
        "--output-root",
        str(stage1_batch_root),
        "--start-index",
        str(max(0, args.start_index)),
    ]
    if args.end_index is not None:
        stage1_batch_args.extend(["--end-index", str(args.end_index)])
    stage1_module.run_batch_cli(stage1_batch_args)
    stage1_module.run_aggregate_batches_cli(
        [
            "--batch-root",
            str(stage1_batch_root),
            "--output-workbook",
            str(stage1_output / "guideline_audit.xlsx"),
        ]
    )

    stage2_batch_args = [
        "--batch-size",
        str(batch_size),
        "--output-root",
        str(stage2_batch_root),
        "--stage1-workbook",
        str(stage1_output / "guideline_audit.xlsx"),
        "--start-index",
        str(max(0, args.start_index)),
    ]
    if args.end_index is not None:
        stage2_batch_args.extend(["--end-index", str(args.end_index)])
    forwarded_flags = {
        "--attempts",
        "--generated-tests",
        "--timeout-seconds",
        "--k-values",
        "--model-targets",
        "--skip-llm",
    }
    stage2_batch_args.extend(_forward_flags(remaining, forwarded_flags))
    stage2_module.run_batch_cli(stage2_batch_args)
    stage2_module.run_aggregate_batches_cli(
        [
            "--batch-root",
            str(stage2_batch_root),
            "--output-root",
            str(stage2_output),
            "--stage1-workbook",
            str(stage1_output / "guideline_audit.xlsx"),
        ]
    )

    stage3_batch_args = [
        "--batch-size",
        str(batch_size),
        "--output-root",
        str(stage3_batch_root),
        "--stage1-workbook",
        str(stage1_output / "guideline_audit.xlsx"),
        "--stage2-dir",
        str(stage2_output),
        "--start-index",
        str(max(0, args.start_index)),
    ]
    if args.end_index is not None:
        stage3_batch_args.extend(["--end-index", str(args.end_index)])
    forwarded_stage3_flags = {
        "--near-duplicate-threshold",
        "--template-threshold",
        "--cluster-threshold",
    }
    stage3_batch_args.extend(_forward_flags(remaining, forwarded_stage3_flags))
    stage3_module.run_batch_cli(stage3_batch_args)
    stage3_aggregate_args = [
        "--batch-root",
        str(stage3_batch_root),
        "--output-dir",
        str(stage3_output),
        "--stage1-workbook",
        str(stage1_output / "guideline_audit.xlsx"),
        "--stage2-dir",
        str(stage2_output),
    ]
    stage3_aggregate_args.extend(_forward_flags(remaining, forwarded_stage3_flags))
    stage3_module.run_aggregate_batches_cli(stage3_aggregate_args)

    if args.prepare_stage4:
        return _run_stage("manual-audit", args, remaining)
    return 0


def _forward_flags(remaining: list[str], allowed_flags: set[str]) -> list[str]:
    forwarded: list[str] = []
    index = 0
    while index < len(remaining):
        item = remaining[index]
        if item in allowed_flags:
            forwarded.append(item)
            if index + 1 < len(remaining) and not remaining[index + 1].startswith("--"):
                forwarded.append(remaining[index + 1])
                index += 2
                continue
        elif any(item.startswith(flag + "=") for flag in allowed_flags):
            forwarded.append(item)
        index += 1
    return forwarded


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args, remaining = parser.parse_known_args(argv)
    if remaining and remaining[0] == "--":
        remaining = remaining[1:]

    if args.manual_audit and args.proxy_audit:
        raise SystemExit("Use only one of --manual-audit or --proxy-audit at a time.")
    if args.manual_audit:
        args.stage = "manual-audit"
        args.tool = "review-ui"
    elif args.proxy_audit:
        args.stage = "manual-audit"
        args.tool = "proxy-bug-hunt"

    load_local_env()
    require_openai = args.stage in {
        "all",
        "sample-requirements-analysis",
        "sample-efficacy-analysis",
        "dataset-analysis",
    } or (args.stage == "manual-audit" and args.tool == "proxy-bug-hunt")
    ok, messages = ensure_preflight(require_openai=require_openai)
    for message in messages:
        print(message)
    if not ok:
        return 1

    try:
        if args.stage == "all":
            if args.batch_size is not None:
                print(
                    "Running top-level batched full pipeline with "
                    f"batch size {args.batch_size}."
                )
                started_at = time.perf_counter()
                result = _run_all_batched(args, remaining)
                actual_elapsed = time.perf_counter() - started_at
                print(f"Finished batched full pipeline in {_format_seconds(actual_elapsed)}.")
                return result
            stage_sequence = [
                "sample-requirements-analysis",
                "sample-efficacy-analysis",
                "dataset-analysis",
            ]
            if args.prepare_stage4:
                stage_sequence.append("manual-audit")
            estimated_total = sum(_estimate_stage_seconds(stage_name, args, remaining) for stage_name in stage_sequence)
            print(
                "Approximate total runtime remaining: "
                f"{_format_seconds(estimated_total)} "
                f"(target finish around {_format_finish_time(estimated_total)})"
            )
            elapsed_so_far = 0.0
            for stage_name in stage_sequence:
                stage_estimate = _estimate_stage_seconds(stage_name, args, remaining)
                remaining_after_stage = max(0.0, estimated_total - elapsed_so_far)
                print(
                    f"Starting {stage_name}. "
                    f"Approximate time remaining before this stage completes: "
                    f"{_format_seconds(remaining_after_stage)} "
                    f"(finish around {_format_finish_time(remaining_after_stage)})"
                )
                started_at = time.perf_counter()
                result = _run_stage(stage_name, args, remaining)
                if result != 0:
                    return result
                actual_elapsed = time.perf_counter() - started_at
                elapsed_so_far += actual_elapsed
                remaining_estimate = max(0.0, estimated_total - elapsed_so_far)
                print(
                    f"Finished {stage_name} in {_format_seconds(actual_elapsed)}. "
                    f"Approximate runtime remaining: {_format_seconds(remaining_estimate)} "
                    f"(finish around {_format_finish_time(remaining_estimate)})"
                )
            return 0
        stage_estimate = _estimate_stage_seconds(args.stage, args, remaining)
        print(
            f"Approximate runtime for {args.stage}: {_format_seconds(stage_estimate)} "
            f"(finish around {_format_finish_time(stage_estimate)})"
        )
        started_at = time.perf_counter()
        result = _run_stage(args.stage, args, remaining)
        actual_elapsed = time.perf_counter() - started_at
        print(f"Finished {args.stage} in {_format_seconds(actual_elapsed)}.")
        return result
    except NotImplementedError as exc:
        print(str(exc))
        return 1
    except SystemExit as exc:
        message = str(exc)
        if message:
            print(message)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
