from __future__ import annotations

import argparse
import asyncio
import csv
import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from turing_takehome.llm import AsyncTaskSpec, request_json_for_target_async, run_async_job_builders
from turing_takehome.stages.sample_efficacy_analysis.data import SampleRecord, TestCase, load_samples


PROJECT_ROOT = Path(__file__).resolve().parents[4]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "proxy_audit"
DEFAULT_STAGE2_DIR = PROJECT_ROOT / "outputs" / "sample_efficacy_analysis"

PROXY_OUTPUT_COLUMNS = [
    "SampleIndex",
    "QuestionId",
    "QuestionTitle",
    "Visibility",
    "CaseIndex",
    "FailureType",
    "ExceptionType",
    "ExceptionMessage",
    "Stage2TargetName",
    "AttemptIndex",
    "CaseFocus",
    "CaseInputText",
    "CaseExpectedText",
    "final_verdict",
    "pipeline_integrity",
    "test_validity",
    "sample_validity",
    "likely_root_cause",
    "confidence",
    "reason",
    "recommended_followup",
]

BUG_HUNT_SCHEMA = {
    "type": "object",
    "properties": {
        "final_verdict": {
            "type": "string",
            "enum": [
                "pipeline_or_test_fault",
                "sample_fault",
                "both_sample_and_pipeline_or_test_fault",
                "model_candidate_fault_only",
                "unclear",
            ],
        },
        "pipeline_integrity": {
            "type": "string",
            "enum": ["bug_confirmed", "bug_suspected", "looks_valid", "unclear"],
        },
        "test_validity": {
            "type": "string",
            "enum": ["valid", "questionable", "invalid", "unclear"],
        },
        "sample_validity": {
            "type": "string",
            "enum": ["likely_valid", "likely_invalid", "unclear"],
        },
        "likely_root_cause": {
            "type": "string",
            "enum": [
                "extraction_bug",
                "execution_harness_bug",
                "test_case_bug",
                "oracle_or_expected_output_bug",
                "sample_spec_or_ideal_bug",
                "model_logic_failure",
                "other",
            ],
        },
        "confidence": {
            "type": "string",
            "enum": ["low", "medium", "high"],
        },
        "reason": {"type": "string"},
        "recommended_followup": {"type": "string"},
    },
    "required": [
        "final_verdict",
        "pipeline_integrity",
        "test_validity",
        "sample_validity",
        "likely_root_cause",
        "confidence",
        "reason",
        "recommended_followup",
    ],
    "additionalProperties": False,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run a skeptical proxy-human bug-hunt over individual failed Stage 2 test cases. "
            "This is a development tool for surfacing pipeline and test bugs, not the canonical Stage 4 workflow."
        )
    )
    parser.add_argument(
        "--jsonl",
        type=Path,
        default=ARTIFACTS_DIR / "provided" / "Samples.jsonl",
    )
    parser.add_argument("--stage2-dir", type=Path, default=DEFAULT_STAGE2_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--indices", default=None)
    parser.add_argument("--max-tests-per-sample", type=int, default=None)
    parser.add_argument("--max-concurrency", type=int, default=8)
    parser.add_argument("--target-name", default="openai-gpt-5-mini")
    parser.add_argument("--batch-size", type=int, default=40)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--max-batches", type=int, default=None)
    return parser


def run_cli(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    jsonl_path = _resolve_path(args.jsonl)
    stage2_dir = _resolve_path(args.stage2_dir)
    output_dir = _resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    samples = {
        sample.index: sample
        for sample in load_samples(
            jsonl_path,
            indices=args.indices or _all_stage2_indices(stage2_dir),
            limit=None,
            offset=0,
        )
    }
    stage2_rows = _load_stage2_rows(stage2_dir)
    per_test_rows = _group_stage2_test_rows(stage2_dir)

    candidate_specs: list[dict[str, Any]] = []
    for index in sorted(samples):
        sample = samples[index]
        stage2_row = stage2_rows.get(index)
        if not stage2_row:
            continue
        target_name = str(stage2_row.get("TargetName", "")).strip() or args.target_name
        trace_dir = stage2_dir / "traces" / f"sample_{index}"
        generated_cases = _load_generated_cases(trace_dir)
        solver_prompt = _read_optional_text(trace_dir / "solver_prompt.txt")
        failed_rows = _select_failed_rows_for_all_attempts(
            grouped_rows=per_test_rows,
            sample_index=index,
            target_name=target_name,
        )
        if args.max_tests_per_sample is not None:
            failed_rows = failed_rows[: max(0, args.max_tests_per_sample)]
        trace_cache: dict[int, tuple[str, str]] = {}
        for row in failed_rows:
            attempt_index = int(row.get("attempt_index", 0))
            if attempt_index not in trace_cache:
                raw_response = _read_optional_text(
                    trace_dir / target_name / f"attempt_{attempt_index}" / "raw_model_response.txt"
                )
                candidate_code = _read_optional_text(
                    trace_dir / target_name / f"attempt_{attempt_index}" / "candidate_solution.py"
                )
                trace_cache[attempt_index] = (raw_response, candidate_code)
            else:
                raw_response, candidate_code = trace_cache[attempt_index]
            candidate_specs.append(
                _build_test_audit_spec(
                    sample=sample,
                    stage2_row=stage2_row,
                    failed_row=row,
                    raw_response=raw_response,
                    candidate_code=candidate_code,
                    solver_prompt=solver_prompt,
                    generated_cases=generated_cases,
                    output_dir=output_dir,
                    target_name=args.target_name,
                )
            )

    if not candidate_specs:
        raise SystemExit("No failed per-test rows were found for the requested indices.")

    progress_path = output_dir / "progress.jsonl"
    completed_rows = _load_progress_rows(progress_path) if args.resume else {}
    pending_specs = [
        spec for spec in candidate_specs if spec["request_id"] not in completed_rows
    ]

    started = time.perf_counter()
    if pending_specs:
        checkpoints_dir = output_dir / "checkpoints"
        checkpoints_dir.mkdir(parents=True, exist_ok=True)
        for batch_number, batch_specs in enumerate(
            _chunked(pending_specs, max(1, args.batch_size)),
            start=1,
        ):
            if args.max_batches is not None and batch_number > max(0, args.max_batches):
                break
            batch_results = asyncio.run(
                _run_safe_proxy_tasks(
                    [spec["task_spec"] for spec in batch_specs],
                    max_concurrency=max(1, args.max_concurrency),
                )
            )
            normalized_rows: list[dict[str, Any]] = []
            for spec in batch_specs:
                payload = _normalize_audit_payload(batch_results[spec["request_id"]])
                row = dict(spec["base_row"])
                row.update(payload)
                normalized = _normalize_output_row(row)
                normalized_rows.append(normalized)
                completed_rows[spec["request_id"]] = normalized
            _append_progress_rows(progress_path, normalized_rows)
            elapsed_so_far = time.perf_counter() - started
            detailed_rows_so_far = [
                completed_rows[spec["request_id"]]
                for spec in candidate_specs
                if spec["request_id"] in completed_rows
            ]
            detailed_rows_so_far.sort(
                key=lambda row: (
                    int(row["SampleIndex"]),
                    int(row["AttemptIndex"]),
                    str(row["Visibility"]),
                    int(row["CaseIndex"]),
                )
            )
            checkpoint_summary = _build_summary(
                detailed_rows_so_far,
                elapsed_so_far,
                max(1, len(detailed_rows_so_far)),
            )
            checkpoint_manifest = {
                "batch_number": batch_number,
                "completed_pairs": len(detailed_rows_so_far),
                "pending_pairs": max(0, len(candidate_specs) - len(detailed_rows_so_far)),
                "max_concurrency": max(1, args.max_concurrency),
                "batch_size": max(1, args.batch_size),
                "max_batches": args.max_batches,
                "resume": bool(args.resume),
                "timing": checkpoint_summary["timing"],
            }
            _write_snapshot(
                output_dir=output_dir,
                detailed_rows=detailed_rows_so_far,
                summary_rows=checkpoint_summary["rows"],
                manifest=checkpoint_manifest,
            )
            _write_snapshot(
                output_dir=checkpoints_dir / f"batch_{batch_number:03d}",
                detailed_rows=normalized_rows,
                summary_rows=checkpoint_summary["rows"],
                manifest=checkpoint_manifest,
            )
            print(
                f"Completed batch {batch_number}: "
                f"{len(normalized_rows)} pairs this batch, "
                f"{len(detailed_rows_so_far)}/{len(candidate_specs)} total."
            )
    elapsed = time.perf_counter() - started

    detailed_rows = [
        completed_rows[spec["request_id"]]
        for spec in candidate_specs
        if spec["request_id"] in completed_rows
    ]
    detailed_rows.sort(
        key=lambda row: (
            int(row["SampleIndex"]),
            int(row["AttemptIndex"]),
            str(row["Visibility"]),
            int(row["CaseIndex"]),
        )
    )
    summary = _build_summary(detailed_rows, elapsed, max(1, len(detailed_rows)))
    manifest = {
        "indices": [int(index) for index in sorted(samples)],
        "stage2_dir": str(stage2_dir),
        "output_dir": str(output_dir),
        "target_name": args.target_name,
        "max_concurrency": max(1, args.max_concurrency),
        "batch_size": max(1, args.batch_size),
        "max_tests_per_sample": args.max_tests_per_sample,
        "resume": bool(args.resume),
        "timing": summary["timing"],
    }
    _write_snapshot(
        output_dir=output_dir,
        detailed_rows=detailed_rows,
        summary_rows=summary["rows"],
        manifest=manifest,
    )

    print(f"Wrote proxy bug-hunt CSV to {output_dir / 'proxy_bug_hunt.csv'}")
    print(f"Wrote proxy bug-hunt summary to {output_dir / 'summary.md'}")
    return 0


def _build_test_audit_spec(
    *,
    sample: SampleRecord,
    stage2_row: dict[str, Any],
    failed_row: dict[str, Any],
    raw_response: str,
    candidate_code: str,
    solver_prompt: str,
    generated_cases: dict[int, dict[str, Any]],
    output_dir: Path,
    target_name: str,
) -> dict[str, Any]:
    sample_index = int(failed_row["sample_index"])
    visibility = str(failed_row.get("visibility", "")).strip() or "unknown"
    case_index = int(failed_row.get("case_index", 0))
    attempt_index = int(failed_row.get("attempt_index", 0))
    request_id = f"sample{sample_index}_attempt{attempt_index}_{visibility}_{case_index}"
    case_context = _resolve_case_context(sample, failed_row, generated_cases)
    trace_dir = output_dir / "traces" / f"sample_{sample_index}" / visibility / f"case_{case_index}"
    prompt = _build_proxy_bug_hunt_prompt(
        sample=sample,
        stage2_row=stage2_row,
        failed_row=failed_row,
        case_context=case_context,
        raw_response=raw_response,
        candidate_code=candidate_code,
        solver_prompt=solver_prompt,
    )
    base_row = {
        "SampleIndex": sample_index,
        "QuestionId": str(failed_row.get("question_id", "")),
        "QuestionTitle": sample.row.get("question_title", ""),
        "Visibility": visibility,
        "CaseIndex": case_index,
        "FailureType": str(failed_row.get("failure_type", "")),
        "ExceptionType": str(failed_row.get("exception_type", "")),
        "ExceptionMessage": str(failed_row.get("exception_message", "")),
        "Stage2TargetName": str(failed_row.get("target_name", "")),
        "AttemptIndex": attempt_index,
        "CaseFocus": case_context.get("focus", ""),
        "CaseInputText": case_context.get("input_text", ""),
        "CaseExpectedText": case_context.get("output_text", ""),
    }
    task_spec = AsyncTaskSpec(
        request_id=request_id,
        task_type="json",
        kwargs={
            "target_name": target_name,
            "schema_name": "proxy_bug_hunt_audit",
            "schema": BUG_HUNT_SCHEMA,
            "user_prompt": prompt,
            "system_prompt": (
                "You are a skeptical benchmark-pipeline auditor. "
                "Assume the pipeline or test may be wrong until the evidence rules that out. "
                "Return only strict JSON matching the schema. "
                "Do not defer to the existing labels."
            ),
            "trace_dir": trace_dir,
        },
    )
    return {
        "request_id": request_id,
        "task_spec": task_spec,
        "base_row": base_row,
    }


def _head_tail_excerpt(text: str, *, head: int = 3200, tail: int = 2200) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return "<missing>"
    if len(cleaned) <= head + tail + 200:
        return cleaned
    return (
        f"[truncated for proxy audit; total_chars={len(cleaned)}]\n"
        f"--- BEGIN HEAD ---\n{cleaned[:head]}\n"
        f"--- END HEAD ---\n"
        f"...\n"
        f"--- BEGIN TAIL ---\n{cleaned[-tail:]}\n"
        f"--- END TAIL ---"
    )


def _build_proxy_bug_hunt_prompt(
    *,
    sample: SampleRecord,
    stage2_row: dict[str, Any],
    failed_row: dict[str, Any],
    case_context: dict[str, Any],
    raw_response: str,
    candidate_code: str,
    solver_prompt: str,
) -> str:
    expected_text = case_context.get("output_text") or json.dumps(
        failed_row.get("expected"),
        ensure_ascii=False,
        indent=2,
    )
    actual_text = json.dumps(failed_row.get("actual"), ensure_ascii=False, indent=2)
    return "\n".join(
        [
            "Audit task:",
            "A Stage 2 benchmark test failed. Determine whether the evidence points to a pipeline/test bug, a sample bug, a pure model-candidate failure, or a mix.",
            "",
            "Bias for this review:",
            "- Start by trying to prove that the pipeline, extraction logic, harness, or test is compromised.",
            "- Only blame the sample itself if you cannot find concrete evidence that the pipeline or test is flawed.",
            "- It is allowed to conclude both the sample and the pipeline/test are at fault.",
            "",
            "Decision guidance:",
            "- Compare the raw model response against the executed candidate code. If imports, helpers, or top-level code were lost, that is strong pipeline-bug evidence.",
            "- Check whether the failed test seems consistent with the problem statement and ideal response.",
            "- Check whether the expected output looks wrong, underspecified, or inconsistent with the sample's own requirements.",
            "- If the candidate simply appears logically wrong and the test looks sound, call it model_candidate_fault_only.",
            "",
            f"Sample index: {sample.index}",
            f"Question title: {sample.row.get('question_title', '')}",
            f"Function name: {sample.function_name}",
            f"Stage 2 label: {stage2_row.get('EfficacyLabel', '')}",
            f"Stage 2 failure category: {stage2_row.get('FailureCategory', '')}",
            "",
            "Problem statement:",
            sample.question_content.strip(),
            "",
            "Starter code:",
            (sample.starter_code or "").strip() or "<none>",
            "",
            "Ideal response:",
            _head_tail_excerpt(sample.ideal_response or "", head=3200, tail=2200),
            "",
            "Solver prompt used to generate the candidate:",
            _head_tail_excerpt(solver_prompt or "", head=2200, tail=1400),
            "",
            "Raw model response:",
            _head_tail_excerpt(raw_response or "", head=3200, tail=2200),
            "",
            "Executed candidate code:",
            _head_tail_excerpt(candidate_code or "", head=3200, tail=2200),
            "",
            f"Failed test visibility: {failed_row.get('visibility', '')}",
            f"Failed test case index: {failed_row.get('case_index', '')}",
            f"Recorded failure type: {failed_row.get('failure_type', '')}",
            f"Recorded exception type: {failed_row.get('exception_type', '')}",
            f"Recorded exception message: {failed_row.get('exception_message', '')}",
            "",
            "Test input as stored by the pipeline:",
            case_context.get("input_text", "") or "<missing>",
            "",
            "Expected output for this test:",
            expected_text,
            "",
            "Actual output recorded for this test:",
            actual_text,
            "",
            "Focused metadata for this test:",
            case_context.get("focus", "") or "<none>",
            "",
            "Captured stderr:",
            str(failed_row.get("stderr", ""))[:3000],
            "",
            "Return a compact verdict. Your reason should cite concrete evidence, not broad speculation.",
        ]
    )


def _resolve_case_context(
    sample: SampleRecord,
    failed_row: dict[str, Any],
    generated_cases: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    visibility = str(failed_row.get("visibility", "")).strip()
    case_index = int(failed_row.get("case_index", 0))
    if visibility == "public":
        return _test_case_to_context(_lookup_test(sample.public_tests, case_index))
    if visibility == "private":
        return _test_case_to_context(_lookup_test(sample.private_tests, case_index))
    if visibility == "generated":
        generated = generated_cases.get(case_index, {})
        return {
            "input_text": str(generated.get("input_text", "")),
            "output_text": str(generated.get("output_text", "")),
            "focus": str(generated.get("focus", "")),
        }
    return {
        "input_text": "",
        "output_text": json.dumps(failed_row.get("expected"), ensure_ascii=False, indent=2),
        "focus": "",
    }


def _lookup_test(cases: list[TestCase], case_index: int) -> TestCase | None:
    for case in cases:
        if case.case_index == case_index:
            return case
    return None


def _test_case_to_context(test_case: TestCase | None) -> dict[str, str]:
    if test_case is None:
        return {"input_text": "", "output_text": "", "focus": ""}
    return {
        "input_text": test_case.input_text,
        "output_text": test_case.output_text,
        "focus": test_case.testtype,
    }


def _load_generated_cases(trace_dir: Path) -> dict[int, dict[str, Any]]:
    accepted_path = trace_dir / "generated_tests" / "accepted_cases.json"
    raw_path = trace_dir / "generated_tests" / "raw_cases.json"
    accepted_rows: dict[int, dict[str, Any]] = {}
    raw_rows: dict[int, dict[str, Any]] = {}
    if accepted_path.exists():
        accepted_rows = {
            int(row.get("case_index", 0)): row
            for row in json.loads(accepted_path.read_text(encoding="utf-8"))
        }
    if raw_path.exists():
        raw_rows = {
            int(row.get("case_index", 0)): row
            for row in json.loads(raw_path.read_text(encoding="utf-8"))
        }
    merged: dict[int, dict[str, Any]] = {}
    for case_index in sorted(set(accepted_rows) | set(raw_rows)):
        merged[case_index] = {
            "input_text": accepted_rows.get(case_index, {}).get(
                "input_text",
                "\n".join(raw_rows.get(case_index, {}).get("input_lines", [])),
            ),
            "output_text": accepted_rows.get(case_index, {}).get("output_text", ""),
            "focus": raw_rows.get(case_index, {}).get("focus", ""),
        }
    return merged


def _select_failed_rows_for_all_attempts(
    *,
    grouped_rows: dict[tuple[int, str, int], list[dict[str, Any]]],
    sample_index: int,
    target_name: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    matching_attempts = sorted(
        attempt
        for (index, row_target, attempt) in grouped_rows.keys()
        if index == sample_index and row_target == target_name
    )
    for attempt in matching_attempts:
        attempt_rows = grouped_rows.get((sample_index, target_name, attempt), [])
        rows.extend(
            row
            for row in attempt_rows
            if str(row.get("status", "")).strip().lower() not in {"ok", "pass", "passed", "success"}
        )
    return rows


def _group_stage2_test_rows(stage2_dir: Path) -> dict[tuple[int, str, int], list[dict[str, Any]]]:
    path = stage2_dir / "per_test_results.jsonl"
    grouped: dict[tuple[int, str, int], list[dict[str, Any]]] = defaultdict(list)
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            raw = line.strip()
            if not raw:
                continue
            row = json.loads(raw)
            sample_index = int(row.get("sample_index"))
            target_name = str(row.get("target_name", "")).strip()
            attempt_index = int(row.get("attempt_index", 0))
            grouped[(sample_index, target_name, attempt_index)].append(row)
    return grouped


def _load_stage2_rows(stage2_dir: Path) -> dict[int, dict[str, Any]]:
    rows: dict[int, dict[str, Any]] = {}
    with (stage2_dir / "sample_model_results.csv").open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            index = int(row["Index"])
            existing = rows.get(index)
            if existing is None or _to_float(row.get("BestCombinedPassRate")) > _to_float(existing.get("BestCombinedPassRate")):
                rows[index] = row
    return rows


def _all_stage2_indices(stage2_dir: Path) -> str:
    rows = _load_stage2_rows(stage2_dir)
    return ",".join(str(index) for index in sorted(rows))


def _build_summary(
    detailed_rows: list[dict[str, Any]],
    elapsed: float,
    pair_count: int,
) -> dict[str, Any]:
    verdict_counts: dict[str, int] = defaultdict(int)
    root_counts: dict[str, int] = defaultdict(int)
    for row in detailed_rows:
        verdict_counts[str(row.get("final_verdict", ""))] += 1
        root_counts[str(row.get("likely_root_cause", ""))] += 1
    rows = [
        {
            "AnalysisArea": "timing",
            "TestName": "proxy_bug_hunt_runtime",
            "Result": "INFO",
            "Evidence": (
                f"pairs={pair_count}; total_seconds={elapsed:.2f}; "
                f"seconds_per_pair={elapsed / max(1, pair_count):.2f}"
            ),
            "Interpretation": "Use this empirical rate to estimate larger skeptical proxy-audit runs.",
            "Recommendation": "",
        },
        {
            "AnalysisArea": "verdicts",
            "TestName": "proxy_bug_hunt_outcomes",
            "Result": "INFO",
            "Evidence": _format_counter(verdict_counts),
            "Interpretation": "Counts of where the skeptical proxy review placed responsibility.",
            "Recommendation": "",
        },
        {
            "AnalysisArea": "root_causes",
            "TestName": "proxy_bug_hunt_root_causes",
            "Result": "INFO",
            "Evidence": _format_counter(root_counts),
            "Interpretation": "Most common concrete failure modes identified by the skeptical proxy review.",
            "Recommendation": "",
        },
    ]
    return {
        "rows": rows,
        "timing": {
            "total_seconds": elapsed,
            "pairs": pair_count,
            "seconds_per_pair": elapsed / max(1, pair_count),
        },
    }


async def _run_safe_proxy_tasks(
    task_specs: list[AsyncTaskSpec],
    *,
    max_concurrency: int,
) -> dict[str, Any]:
    async def build(spec: AsyncTaskSpec) -> dict[str, Any]:
        try:
            return await request_json_for_target_async(**spec.kwargs)
        except Exception as exc:
            return {
                "final_verdict": "unclear",
                "pipeline_integrity": "unclear",
                "test_validity": "unclear",
                "sample_validity": "unclear",
                "likely_root_cause": "other",
                "confidence": "low",
                "reason": f"Proxy audit request failed: {exc.__class__.__name__}: {exc}",
                "recommended_followup": (
                    "Retry this audit item with lower concurrency or inspect the trace manually."
                ),
            }

    jobs = [(spec.request_id, (lambda spec=spec: build(spec))) for spec in task_specs]
    return await run_async_job_builders(jobs, max_concurrency=max_concurrency)


def _write_markdown(path: Path, summary_rows: list[dict[str, Any]], detailed_rows: list[dict[str, Any]]) -> None:
    lines = [
        "# Proxy Bug Hunt",
        "",
        f"- Audited failed test pairs: {len(detailed_rows)}",
        "",
        "## Summary",
    ]
    for row in summary_rows:
        lines.append(f"- {row['TestName']}: {row['Evidence']}")
    lines.extend(["", "## Suspected Bugs"])
    for row in detailed_rows[:20]:
        if row.get("final_verdict") == "pipeline_or_test_fault":
            lines.append(
                f"- sample {row['SampleIndex']} / {row['Visibility']} {row['CaseIndex']}: "
                f"{row.get('likely_root_cause', '')} [{row.get('confidence', '')}]"
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _read_optional_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PROXY_OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("-inf")


def _format_counter(counter: dict[str, int]) -> str:
    parts = [f"{key}={value}" for key, value in sorted(counter.items()) if key]
    return ", ".join(parts)


def _resolve_path(path: Path | None) -> Path:
    if path is None:
        raise ValueError("Path cannot be None.")
    return path if path.is_absolute() else (PROJECT_ROOT / path)


def _normalize_audit_payload(payload: Any) -> dict[str, str]:
    if not isinstance(payload, dict):
        payload = {}
    normalized = {
        "final_verdict": str(payload.get("final_verdict", "")).strip() or "unclear",
        "pipeline_integrity": str(payload.get("pipeline_integrity", "")).strip() or "unclear",
        "test_validity": str(payload.get("test_validity", "")).strip() or "unclear",
        "sample_validity": str(payload.get("sample_validity", "")).strip() or "unclear",
        "likely_root_cause": str(payload.get("likely_root_cause", "")).strip() or "other",
        "confidence": str(payload.get("confidence", "")).strip() or "low",
        "reason": str(payload.get("reason", "")).strip(),
        "recommended_followup": str(payload.get("recommended_followup", "")).strip(),
    }
    return normalized


def _normalize_output_row(row: dict[str, Any]) -> dict[str, Any]:
    return {column: row.get(column, "") for column in PROXY_OUTPUT_COLUMNS}


def _append_progress_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_snapshot(
    *,
    output_dir: Path,
    detailed_rows: list[dict[str, Any]],
    summary_rows: list[dict[str, Any]],
    manifest: dict[str, Any],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "proxy_bug_hunt.csv", detailed_rows)
    _write_markdown(output_dir / "summary.md", summary_rows, detailed_rows)
    _write_json(output_dir / "run_manifest.json", manifest)


def _load_progress_rows(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    rows: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            raw = line.strip()
            if not raw:
                continue
            row = json.loads(raw)
            request_id = _request_id_for_row(row)
            if request_id:
                rows[request_id] = _normalize_output_row(row)
    return rows


def _request_id_for_row(row: dict[str, Any]) -> str:
    try:
        return (
            f"sample{int(row['SampleIndex'])}_attempt{int(row['AttemptIndex'])}_"
            f"{str(row['Visibility'])}_{int(row['CaseIndex'])}"
        )
    except Exception:
        return ""


def _chunked(items: list[Any], size: int) -> list[list[Any]]:
    return [items[index : index + size] for index in range(0, len(items), size)]
