from __future__ import annotations

import argparse
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import re
import traceback
from pathlib import Path
from typing import Any

from turing_takehome.llm import (
    generate_text_for_target,
    get_stage_comparison_target_names,
    get_stage_generated_test_target_name,
    get_target_model_label,
)
from turing_takehome.reporting import export_combined_report

from .data import SampleRecord, TestCase, load_samples
from .execution import (
    execute_arguments,
    prepare_execution_workspace,
    probe_candidate,
    run_test_case,
)
from .extraction import extract_python_code
from .labeling import classify_sample, estimate_pass_at_k, pass_rate_for, summarize_test_outcomes
from .prompting import build_solver_prompt
from .test_generation import build_generated_test_case, generate_additional_tests


PROJECT_ROOT = Path(__file__).resolve().parents[4]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "sample_efficacy_analysis"
STAGE1_WORKBOOK = PROJECT_ROOT / "outputs" / "sample_requirements_analysis" / "guideline_audit.xlsx"
STAGE_NAME = "sample-efficacy-analysis"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Stage 2 Sample Efficacy Analysis on a subset of samples."
    )
    parser.add_argument(
        "--jsonl",
        type=Path,
        default=ARTIFACTS_DIR / "provided" / "Samples.jsonl",
    )
    parser.add_argument("--stage1-workbook", type=Path, default=STAGE1_WORKBOOK)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--indices", default=None)
    parser.add_argument("--timeout-seconds", type=int, default=10)
    parser.add_argument("--attempts", type=int, default=2)
    parser.add_argument("--generated-tests", type=int, default=3)
    parser.add_argument("--k-values", default="1,2")
    parser.add_argument("--model-targets", default=None)
    parser.add_argument("--skip-llm", action="store_true")
    return parser


def run_cli(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_dir = args.output_dir if args.output_dir.is_absolute() else (PROJECT_ROOT / args.output_dir)
    output_dir = output_dir.resolve()
    traces_dir = output_dir / "traces"
    output_dir.mkdir(parents=True, exist_ok=True)
    traces_dir.mkdir(parents=True, exist_ok=True)

    target_names = _parse_model_targets(args.model_targets)
    k_values = _parse_k_values(args.k_values, args.attempts)
    samples = load_samples(
        args.jsonl,
        limit=args.limit,
        offset=args.offset,
        indices=args.indices,
    )
    _write_run_manifest(output_dir / "run_manifest.json", args, samples, target_names, k_values)

    comparison_rows: list[dict[str, Any]] = []
    model_rows: list[dict[str, Any]] = []
    attempt_rows: list[dict[str, Any]] = []
    per_test_rows: list[dict[str, Any]] = []

    for sample in samples:
        sample_trace_dir = traces_dir / f"sample_{sample.index}"
        sample_trace_dir.mkdir(parents=True, exist_ok=True)
        comparison_row, sample_model_rows, sample_attempt_rows, sample_test_rows = evaluate_sample(
            sample,
            sample_trace_dir=sample_trace_dir,
            timeout_seconds=args.timeout_seconds,
            attempts=args.attempts,
            k_values=k_values,
            target_names=target_names,
            generated_test_count=args.generated_tests,
            use_llm=not args.skip_llm,
        )
        comparison_rows.append(comparison_row)
        model_rows.extend(sample_model_rows)
        attempt_rows.extend(sample_attempt_rows)
        per_test_rows.extend(sample_test_rows)

    _write_jsonl(output_dir / "sample_results.jsonl", comparison_rows)
    _write_csv(output_dir / "sample_results.csv", comparison_rows)
    _write_jsonl(output_dir / "sample_model_results.jsonl", model_rows)
    _write_csv(output_dir / "sample_model_results.csv", model_rows)
    _write_jsonl(output_dir / "model_attempts.jsonl", attempt_rows)
    _write_jsonl(output_dir / "per_test_results.jsonl", per_test_rows)
    _write_summary(output_dir / "summary.md", comparison_rows, model_rows, attempt_rows, per_test_rows)
    _export_combined_if_available(output_dir, stage1_workbook=_resolve_path(args.stage1_workbook))

    print(f"Wrote sample comparison results to {output_dir / 'sample_results.csv'}")
    print(f"Wrote per-model results to {output_dir / 'sample_model_results.csv'}")
    print(f"Wrote attempt-level results to {output_dir / 'model_attempts.jsonl'}")
    print(f"Wrote per-test results to {output_dir / 'per_test_results.jsonl'}")
    print(f"Wrote summary report to {output_dir / 'summary.md'}")
    return 0


def _export_combined_if_available(stage2_output_dir: Path, *, stage1_workbook: Path) -> None:
    if not stage1_workbook.exists():
        return
    workbook_path, json_path = export_combined_report(
        stage1_workbook_path=stage1_workbook,
        stage2_output_root=stage2_output_dir,
    )
    print(f"Wrote combined workbook to {workbook_path}")
    print(f"Wrote combined json to {json_path}")


def evaluate_sample(
    sample: SampleRecord,
    *,
    sample_trace_dir: Path,
    timeout_seconds: int,
    attempts: int,
    k_values: list[int],
    target_names: list[str],
    generated_test_count: int,
    use_llm: bool,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    prompt = build_solver_prompt(sample)
    (sample_trace_dir / "solver_prompt.txt").write_text(prompt, encoding="utf-8")

    oracle_path, oracle_harness_path = prepare_execution_workspace(
        sample_trace_dir / "oracle",
        _strip_code_fences(sample.ideal_response),
    )
    oracle_probe = probe_candidate(
        oracle_path,
        oracle_harness_path,
        sample.function_name,
        timeout_seconds=timeout_seconds,
    )
    oracle_test_rows = _oracle_test_rows(sample, oracle_path, oracle_harness_path, timeout_seconds)
    oracle_summary = summarize_test_outcomes(oracle_test_rows) if oracle_test_rows else None

    generated_tests, generated_case_rows = _build_generated_tests(
        sample,
        sample_trace_dir,
        oracle_path,
        oracle_harness_path,
        timeout_seconds=timeout_seconds,
        generated_test_count=generated_test_count,
        use_llm=use_llm,
        oracle_probe_ok=(oracle_probe.status == "ok"),
    )

    per_test_rows: list[dict[str, Any]] = [*generated_case_rows, *oracle_test_rows]
    sample_model_rows: list[dict[str, Any]] = []
    sample_attempt_rows: list[dict[str, Any]] = []

    future_map = {}
    max_workers = min(max(1, len(target_names) * attempts), 8)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for target_name in target_names:
            target_dir = sample_trace_dir / _slugify(target_name)
            target_dir.mkdir(parents=True, exist_ok=True)
            for attempt_index in range(1, attempts + 1):
                attempt_dir = target_dir / f"attempt_{attempt_index}"
                attempt_dir.mkdir(parents=True, exist_ok=True)
                future = executor.submit(
                    _evaluate_attempt,
                    sample,
                    prompt,
                    target_name=target_name,
                    attempt_index=attempt_index,
                    attempt_dir=attempt_dir,
                    timeout_seconds=timeout_seconds,
                    use_llm=use_llm,
                    provided_tests=sample.all_tests,
                    generated_tests=generated_tests,
                    oracle_summary=oracle_summary,
                )
                future_map[future] = (target_name, attempt_index)

        records_by_target: dict[str, list[tuple[int, dict[str, Any], list[dict[str, Any]]]]] = {
            target_name: [] for target_name in target_names
        }
        for future in as_completed(future_map):
            target_name, attempt_index = future_map[future]
            attempt_record, attempt_test_rows = future.result()
            records_by_target[target_name].append((attempt_index, attempt_record, attempt_test_rows))

    for target_name in target_names:
        ordered_attempts = sorted(records_by_target[target_name], key=lambda item: item[0])
        attempt_records = [record for _, record, _ in ordered_attempts]
        for _, attempt_record, attempt_test_rows in ordered_attempts:
            sample_attempt_rows.append(attempt_record)
            per_test_rows.extend(attempt_test_rows)
        sample_model_rows.append(
            _aggregate_model_attempts(
                sample,
                target_name=target_name,
                attempt_records=attempt_records,
                k_values=k_values,
                oracle_summary=oracle_summary,
                generated_tests=generated_tests,
            )
        )

    comparison_row = _build_comparison_row(
        sample,
        sample_model_rows,
        oracle_probe_status=oracle_probe.status,
        oracle_summary=oracle_summary,
        generated_tests=generated_tests,
        k_values=k_values,
    )
    return comparison_row, sample_model_rows, sample_attempt_rows, per_test_rows


def _evaluate_attempt(
    sample: SampleRecord,
    prompt: str,
    *,
    target_name: str,
    attempt_index: int,
    attempt_dir: Path,
    timeout_seconds: int,
    use_llm: bool,
    provided_tests: list[TestCase],
    generated_tests: list[TestCase],
    oracle_summary: dict[str, Any] | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    generation = _generate_candidate(prompt, target_name, attempt_dir, use_llm=use_llm)
    raw_response = generation.get("text", "")
    (attempt_dir / "raw_model_response.txt").write_text(raw_response, encoding="utf-8")
    (attempt_dir / "generation_metadata.json").write_text(
        json.dumps({k: v for k, v in generation.items() if k != "text"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    extraction = extract_python_code(raw_response)
    generation_error = str(generation.get("error", "")).strip()
    if generation_error:
        note = extraction.note
        extraction = type(extraction)(
            status=extraction.status if raw_response.strip() else "no_code",
            code=extraction.code,
            note=f"{note} Upstream LLM error: {generation_error}".strip(),
        )
    incomplete_reason = _incomplete_generation_reason(generation)
    if incomplete_reason:
        extraction = type(extraction)(
            status="incomplete_generation",
            code=extraction.code,
            note=(
                f"Model completion was incomplete ({incomplete_reason}); "
                "skipping execution because the candidate may be truncated."
            ),
        )
    (attempt_dir / "extraction.json").write_text(
        json.dumps({"status": extraction.status, "note": extraction.note}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    probe_status = "not_run"
    provided_test_rows: list[dict[str, Any]] = []
    generated_test_rows: list[dict[str, Any]] = []
    if extraction.status == "ok" and sample.function_name:
        candidate_path, harness_path = prepare_execution_workspace(attempt_dir, extraction.code)
        probe = probe_candidate(
            candidate_path,
            harness_path,
            sample.function_name,
            timeout_seconds=timeout_seconds,
        )
        probe_status = probe.status
        (attempt_dir / "execution_probe.json").write_text(
            json.dumps(
                {
                    "status": probe.status,
                    "exception_type": probe.exception_type,
                    "timeout": probe.timeout,
                    "stdout": probe.stdout,
                    "stderr": probe.stderr,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        if probe.status == "ok":
            provided_test_rows = [
                _to_test_row(
                    sample,
                    run_test_case(
                        candidate_path,
                        harness_path,
                        sample.function_name,
                        test_case,
                        timeout_seconds=timeout_seconds,
                    ),
                    source="model_candidate",
                    target_name=target_name,
                    attempt_index=attempt_index,
                )
                for test_case in provided_tests
            ]
            generated_test_rows = [
                _to_test_row(
                    sample,
                    run_test_case(
                        candidate_path,
                        harness_path,
                        sample.function_name,
                        test_case,
                        timeout_seconds=timeout_seconds,
                    ),
                    source="model_candidate",
                    target_name=target_name,
                    attempt_index=attempt_index,
                )
                for test_case in generated_tests
            ]

    provided_summary = summarize_test_outcomes(provided_test_rows)
    combined_summary = summarize_test_outcomes([*provided_test_rows, *generated_test_rows])
    classification = classify_sample(
        generation_status=extraction.status,
        probe_status=probe_status,
        test_summary=combined_summary,
        oracle_summary=oracle_summary,
    )
    attempt_row = {
        "Index": sample.index,
        "QuestionId": sample.row["question_id"],
        "QuestionTitle": sample.row["question_title"],
        "Difficulty": sample.row["difficulty"],
        "TargetName": target_name,
        "ModelLabel": generation.get("model_label", ""),
        "AttemptIndex": attempt_index,
        "GenerationStatus": extraction.status,
        "GenerationNote": extraction.note,
        "ExecutionProbeStatus": probe_status,
        "ProvidedPassRate": round(provided_summary["pass_rate"], 4),
        "PublicPassRate": round(pass_rate_for(provided_summary, "public"), 4),
        "PrivatePassRate": round(pass_rate_for(provided_summary, "private"), 4),
        "GeneratedPassRate": round(pass_rate_for(combined_summary, "generated"), 4),
        "CombinedPassRate": round(combined_summary["pass_rate"], 4),
        "ProvidedPassedTests": provided_summary["passed_tests"],
        "ProvidedTotalTests": provided_summary["total_tests"],
        "GeneratedTotalTests": int(combined_summary["visibility_stats"].get("generated", {}).get("tests", 0)),
        "CombinedPassedTests": combined_summary["passed_tests"],
        "CombinedTotalTests": combined_summary["total_tests"],
        "DifficultyEstimate": classification["difficulty_estimate"],
        "FailureCategory": classification["failure_category"],
        "BenchmarkQualitySignal": classification["benchmark_quality_signal"],
        "EfficacyLabel": classification["efficacy_label"],
        "Suspicious": classification["suspicious"],
        "NeedsAudit": classification["needs_audit"],
        "DominantFailureType": _dominant_failure_type(combined_summary),
        "TraceDir": str(attempt_dir),
    }
    return attempt_row, [*provided_test_rows, *generated_test_rows]


def _aggregate_model_attempts(
    sample: SampleRecord,
    *,
    target_name: str,
    attempt_records: list[dict[str, Any]],
    k_values: list[int],
    oracle_summary: dict[str, Any] | None,
    generated_tests: list[TestCase],
) -> dict[str, Any]:
    best_attempt = max(
        attempt_records,
        key=lambda row: (
            float(row["CombinedPassRate"]),
            float(row["ProvidedPassRate"]),
            float(row["GeneratedPassRate"]),
        ),
    )
    provided_successes = sum(
        1
        for row in attempt_records
        if row["ExecutionProbeStatus"] == "ok" and float(row["ProvidedPassRate"]) >= 0.9999
    )
    combined_successes = sum(
        1
        for row in attempt_records
        if row["ExecutionProbeStatus"] == "ok" and float(row["CombinedPassRate"]) >= 0.9999
    )
    row = {
        "Index": sample.index,
        "QuestionId": sample.row["question_id"],
        "QuestionTitle": sample.row["question_title"],
        "Difficulty": sample.row["difficulty"],
        "TargetName": target_name,
        "ModelLabel": best_attempt["ModelLabel"],
        "Attempts": len(attempt_records),
        "BestAttemptIndex": best_attempt["AttemptIndex"],
        "BestProvidedPassRate": best_attempt["ProvidedPassRate"],
        "BestGeneratedPassRate": best_attempt["GeneratedPassRate"],
        "BestCombinedPassRate": best_attempt["CombinedPassRate"],
        "AverageCombinedPassRate": round(
            sum(float(item["CombinedPassRate"]) for item in attempt_records) / len(attempt_records),
            4,
        ),
        "ProvidedSuccesses": provided_successes,
        "CombinedSuccesses": combined_successes,
        "OraclePassRate": round(oracle_summary["pass_rate"], 4) if oracle_summary else None,
        "GeneratedTests": len(generated_tests),
        "DifficultyEstimate": best_attempt["DifficultyEstimate"],
        "FailureCategory": best_attempt["FailureCategory"],
        "BenchmarkQualitySignal": best_attempt["BenchmarkQualitySignal"],
        "EfficacyLabel": best_attempt["EfficacyLabel"],
        "Suspicious": best_attempt["Suspicious"],
        "NeedsAudit": best_attempt["NeedsAudit"],
    }
    for k in k_values:
        row[f"ProvidedPass@{k}"] = round(estimate_pass_at_k(len(attempt_records), provided_successes, k), 4)
        row[f"CombinedPass@{k}"] = round(estimate_pass_at_k(len(attempt_records), combined_successes, k), 4)
    return row


def _build_comparison_row(
    sample: SampleRecord,
    model_rows: list[dict[str, Any]],
    *,
    oracle_probe_status: str,
    oracle_summary: dict[str, Any] | None,
    generated_tests: list[TestCase],
    k_values: list[int],
) -> dict[str, Any]:
    ordered_rows = sorted(model_rows, key=lambda row: row["TargetName"])
    first = ordered_rows[0]
    second = ordered_rows[1] if len(ordered_rows) > 1 else None

    comparison_note = _comparison_note(first, second, len(generated_tests))
    winner = _winner(first, second)
    row = {
        "Index": sample.index,
        "QuestionId": sample.row["question_id"],
        "QuestionTitle": sample.row["question_title"],
        "Difficulty": sample.row["difficulty"],
        "ComparedModels": ", ".join(item["TargetName"] for item in ordered_rows),
        "OracleProbeStatus": oracle_probe_status,
        "OraclePassRate": round(oracle_summary["pass_rate"], 4) if oracle_summary else None,
        "GeneratedTests": len(generated_tests),
        "Winner": winner,
        "ComparisonNote": comparison_note,
        "Suspicious": any(bool(item["Suspicious"]) for item in ordered_rows),
        "NeedsAudit": any(bool(item["NeedsAudit"]) for item in ordered_rows),
    }
    row.update(_model_projection("ModelA", first, k_values))
    if second is not None:
        row.update(_model_projection("ModelB", second, k_values))
        row["CombinedPassRateDelta"] = round(
            float(first["BestCombinedPassRate"]) - float(second["BestCombinedPassRate"]),
            4,
        )
        row["GeneratedPassRateDelta"] = round(
            float(first["BestGeneratedPassRate"]) - float(second["BestGeneratedPassRate"]),
            4,
        )
    return row


def _build_generated_tests(
    sample: SampleRecord,
    sample_trace_dir: Path,
    oracle_path: Path,
    oracle_harness_path: Path,
    *,
    timeout_seconds: int,
    generated_test_count: int,
    use_llm: bool,
    oracle_probe_ok: bool,
) -> tuple[list[TestCase], list[dict[str, Any]]]:
    generated_trace_dir = sample_trace_dir / "generated_tests"
    generated_trace_dir.mkdir(parents=True, exist_ok=True)
    if not use_llm or generated_test_count <= 0 or not oracle_probe_ok or not sample.function_name:
        return [], []

    target_name = get_stage_generated_test_target_name(STAGE_NAME)
    try:
        generated_cases = generate_additional_tests(
            sample,
            target_name=target_name,
            count=generated_test_count,
            trace_dir=generated_trace_dir / "llm",
        )
    except Exception as exc:
        (generated_trace_dir / "generation_error.txt").write_text(
            "".join(traceback.format_exception(exc)),
            encoding="utf-8",
        )
        return [], []

    (generated_trace_dir / "raw_cases.json").write_text(
        json.dumps(generated_cases, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    accepted_tests: list[TestCase] = []
    trace_rows: list[dict[str, Any]] = []
    for case in generated_cases:
        args = list(case["args"])
        execution = execute_arguments(
            oracle_path,
            oracle_harness_path,
            sample.function_name,
            args,
            timeout_seconds=timeout_seconds,
        )
        trace_row = {
            "sample_index": sample.index,
            "question_id": sample.row["question_id"],
            "function_name": sample.function_name,
            "source": "generated_case_oracle",
            "target_name": target_name,
            "attempt_index": 0,
            "visibility": "generated",
            "case_index": int(case["case_index"]),
            "status": execution.status,
            "expected": None,
            "actual": execution.actual,
            "exception_type": execution.exception_type,
            "exception_message": execution.exception_message,
            "stdout": execution.stdout,
            "stderr": execution.stderr,
            "timeout": execution.timeout,
            "failure_type": "",
            "focus": case["focus"],
        }
        if execution.status == "ok":
            accepted_tests.append(
                build_generated_test_case(int(case["case_index"]), args, execution.actual)
            )
            trace_row["expected"] = execution.actual
        trace_rows.append(trace_row)
    (generated_trace_dir / "accepted_cases.json").write_text(
        json.dumps(
            [
                {
                    "case_index": test.case_index,
                    "input_text": test.input_text,
                    "output_text": test.output_text,
                }
                for test in accepted_tests
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return accepted_tests, trace_rows


def _oracle_test_rows(
    sample: SampleRecord,
    oracle_path: Path,
    oracle_harness_path: Path,
    timeout_seconds: int,
) -> list[dict[str, Any]]:
    if not sample.function_name:
        return []
    return [
        _to_test_row(
            sample,
            run_test_case(
                oracle_path,
                oracle_harness_path,
                sample.function_name,
                test_case,
                timeout_seconds=timeout_seconds,
            ),
            source="oracle_solution",
            target_name="oracle",
            attempt_index=0,
        )
        for test_case in sample.all_tests
    ]


def _generate_candidate(
    prompt: str,
    target_name: str,
    attempt_dir: Path,
    *,
    use_llm: bool,
) -> dict[str, Any]:
    if not use_llm:
        return {
            "text": "",
            "provider": "",
            "model": "",
            "model_label": "",
            "timestamp_utc": "",
            "finish_reason": "",
            "status": "",
            "incomplete_details": None,
            "usage": None,
        }
    try:
        payload = generate_text_for_target(
            target_name,
            prompt,
            trace_dir=attempt_dir / "llm",
        )
        payload["model_label"] = get_target_model_label(target_name)
        return payload
    except Exception as exc:
        trace_dir = attempt_dir / "llm"
        trace_dir.mkdir(parents=True, exist_ok=True)
        (trace_dir / "text_generation_error.txt").write_text(
            "".join(traceback.format_exception(exc)),
            encoding="utf-8",
        )
        model_label = ""
        try:
            model_label = get_target_model_label(target_name)
        except Exception:
            model_label = ""
        return {
            "text": "",
            "provider": "",
            "model": "",
            "model_label": model_label,
            "timestamp_utc": "",
            "finish_reason": "error",
            "status": "error",
            "incomplete_details": None,
            "usage": None,
            "error": f"{exc.__class__.__name__}: {exc}",
        }


def _incomplete_generation_reason(generation: dict[str, Any]) -> str:
    incomplete_details = generation.get("incomplete_details")
    if isinstance(incomplete_details, dict):
        reason = str(incomplete_details.get("reason", "")).strip()
        if reason:
            return reason
    finish_reason = str(generation.get("finish_reason", "")).strip().lower()
    if finish_reason in {"length", "incomplete"}:
        return finish_reason
    status = str(generation.get("status", "")).strip().lower()
    if status == "incomplete":
        return "incomplete"
    return ""


def _to_test_row(
    sample: SampleRecord,
    result,
    *,
    source: str,
    target_name: str,
    attempt_index: int,
) -> dict[str, Any]:
    return {
        "sample_index": sample.index,
        "question_id": sample.row["question_id"],
        "function_name": sample.function_name,
        "source": source,
        "target_name": target_name,
        "attempt_index": attempt_index,
        "visibility": result.visibility,
        "case_index": result.case_index,
        "status": result.status,
        "expected": result.expected,
        "actual": result.actual,
        "exception_type": result.exception_type,
        "exception_message": result.exception_message,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "timeout": result.timeout,
        "failure_type": result.failure_type,
    }


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
    comparison_rows: list[dict[str, Any]],
    model_rows: list[dict[str, Any]],
    attempt_rows: list[dict[str, Any]],
    per_test_rows: list[dict[str, Any]],
) -> None:
    winner_counts: dict[str, int] = {}
    suspicious = [row for row in comparison_rows if row.get("Suspicious")]
    for row in comparison_rows:
        winner = str(row.get("Winner", ""))
        winner_counts[winner] = winner_counts.get(winner, 0) + 1
    by_model: dict[str, list[dict[str, Any]]] = {}
    for row in model_rows:
        by_model.setdefault(str(row["TargetName"]), []).append(row)

    lines = [
        "# Stage 2 Summary",
        "",
        f"Samples evaluated: {len(comparison_rows)}",
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
        avg_pass1 = 0.0
        pass1_keys = [key for key in rows[0].keys() if key.startswith("CombinedPass@1")]
        if pass1_keys:
            avg_pass1 = sum(float(row[pass1_keys[0]]) for row in rows) / len(rows)
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


def _write_run_manifest(
    path: Path,
    args: argparse.Namespace,
    samples: list[SampleRecord],
    target_names: list[str],
    k_values: list[int],
) -> None:
    payload = {
        "stage": STAGE_NAME,
        "jsonl": str(args.jsonl),
        "stage1_workbook": str(args.stage1_workbook),
        "output_dir": str(args.output_dir),
        "limit": args.limit,
        "offset": args.offset,
        "indices": args.indices,
        "timeout_seconds": args.timeout_seconds,
        "attempts": args.attempts,
        "generated_tests": args.generated_tests,
        "k_values": k_values,
        "skip_llm": args.skip_llm,
        "model_targets": target_names,
        "model_labels": {target_name: get_target_model_label(target_name) for target_name in target_names},
        "generated_test_target": get_stage_generated_test_target_name(STAGE_NAME),
        "sample_indices": [sample.index for sample in samples],
        "question_ids": [sample.row["question_id"] for sample in samples],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _parse_model_targets(raw: str | None) -> list[str]:
    if not raw:
        return list(get_stage_comparison_target_names(STAGE_NAME))
    return [piece.strip() for piece in raw.split(",") if piece.strip()]


def _parse_k_values(raw: str, attempts: int) -> list[int]:
    values: list[int] = []
    for piece in raw.split(","):
        part = piece.strip()
        if not part:
            continue
        values.append(max(1, min(int(part), attempts)))
    deduped = sorted(set(values))
    return deduped or [1]


def _comparison_note(first: dict[str, Any], second: dict[str, Any] | None, generated_tests: int) -> str:
    if second is None:
        if str(first.get("Suspicious")) == "True":
            return f"single-model run; {first.get('BenchmarkQualitySignal', '').strip() or 'needs audit'}"
        return f"single-model run; {first.get('EfficacyLabel', '').strip() or 'evaluated'}"
    combined_delta = float(first["BestCombinedPassRate"]) - float(second["BestCombinedPassRate"])
    generated_delta = float(first["BestGeneratedPassRate"]) - float(second["BestGeneratedPassRate"])
    if abs(generated_delta) >= 0.34 and generated_tests > 0:
        stronger = first["TargetName"] if generated_delta > 0 else second["TargetName"]
        return f"generated tests separate the models; {stronger} is stronger on edge cases"
    if abs(combined_delta) < 0.05:
        return "models are effectively tied on this sample"
    stronger = first["TargetName"] if combined_delta > 0 else second["TargetName"]
    return f"{stronger} achieves the stronger combined pass rate"


def _winner(first: dict[str, Any], second: dict[str, Any] | None) -> str:
    if second is None:
        return first["TargetName"]
    first_rate = float(first["BestCombinedPassRate"])
    second_rate = float(second["BestCombinedPassRate"])
    if abs(first_rate - second_rate) < 0.05:
        return "tie"
    return first["TargetName"] if first_rate > second_rate else second["TargetName"]


def _model_projection(prefix: str, row: dict[str, Any], k_values: list[int]) -> dict[str, Any]:
    payload = {
        f"{prefix}Target": row["TargetName"],
        f"{prefix}ModelLabel": row["ModelLabel"],
        f"{prefix}BestCombinedPassRate": row["BestCombinedPassRate"],
        f"{prefix}BestProvidedPassRate": row["BestProvidedPassRate"],
        f"{prefix}BestGeneratedPassRate": row["BestGeneratedPassRate"],
        f"{prefix}EfficacyLabel": row["EfficacyLabel"],
        f"{prefix}BenchmarkQualitySignal": row["BenchmarkQualitySignal"],
    }
    for k in k_values:
        payload[f"{prefix}CombinedPass@{k}"] = row.get(f"CombinedPass@{k}")
    return payload


def _dominant_failure_type(summary: dict[str, Any]) -> str:
    failure_types = summary["failure_types"]
    if not failure_types:
        return ""
    return max(failure_types, key=failure_types.get)


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z0-9_+-]*\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _slugify(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", text).strip("_").lower() or "model"


def _resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()
