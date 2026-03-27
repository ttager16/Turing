from __future__ import annotations

from collections import Counter
from math import comb
from typing import Any


def summarize_test_outcomes(test_results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(test_results)
    passed = sum(1 for result in test_results if result["status"] == "pass")
    visibility_groups: dict[str, list[dict[str, Any]]] = {}
    for result in test_results:
        visibility_groups.setdefault(str(result["visibility"]), []).append(result)
    failure_counter = Counter(
        result["failure_type"] for result in test_results if result["failure_type"]
    )
    visibility_stats: dict[str, dict[str, Any]] = {}
    for visibility, rows in visibility_groups.items():
        passed_rows = sum(1 for row in rows if row["status"] == "pass")
        visibility_stats[visibility] = {
            "tests": len(rows),
            "passed": passed_rows,
            "pass_rate": (passed_rows / len(rows)) if rows else 0.0,
        }
    return {
        "total_tests": total,
        "passed_tests": passed,
        "pass_rate": (passed / total) if total else 0.0,
        "visibility_stats": visibility_stats,
        "failure_types": dict(failure_counter),
    }


def pass_rate_for(summary: dict[str, Any], visibility: str) -> float:
    return float(summary["visibility_stats"].get(visibility, {}).get("pass_rate", 0.0))


def tests_for(summary: dict[str, Any], visibility: str) -> int:
    return int(summary["visibility_stats"].get(visibility, {}).get("tests", 0))


def estimate_pass_at_k(num_attempts: int, num_successes: int, k: int) -> float:
    if num_attempts <= 0 or k <= 0:
        return 0.0
    if num_successes <= 0:
        return 0.0
    if k >= num_attempts:
        return 1.0 if num_successes > 0 else 0.0
    failures = num_attempts - num_successes
    if failures < k:
        return 1.0
    return 1.0 - (comb(failures, k) / comb(num_attempts, k))


def classify_sample(
    *,
    generation_status: str,
    probe_status: str,
    test_summary: dict[str, Any],
    oracle_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    if generation_status != "ok":
        return _result(
            difficulty="unknown",
            failure_category="generation_failure",
            benchmark_quality="clean_evaluation",
            efficacy="Inconclusive",
            suspicious=False,
            needs_audit=False,
        )
    if probe_status != "ok":
        return _result(
            difficulty="unknown",
            failure_category="execution_failure",
            benchmark_quality="clean_evaluation",
            efficacy="Inconclusive",
            suspicious=False,
            needs_audit=False,
        )

    if oracle_summary is not None and oracle_summary["pass_rate"] < 1.0:
        return _result(
            difficulty="unknown",
            failure_category="benchmark_suspicion",
            benchmark_quality="misaligned_or_broken",
            efficacy="Suspicious (Needs Audit)",
            suspicious=True,
            needs_audit=True,
        )

    pass_rate = test_summary["pass_rate"]
    public_pass_rate = pass_rate_for(test_summary, "public")
    private_pass_rate = pass_rate_for(test_summary, "private")
    generated_pass_rate = pass_rate_for(test_summary, "generated")
    failure_types = test_summary["failure_types"]
    dominant_failure = max(failure_types, key=failure_types.get) if failure_types else "clean"

    if public_pass_rate == 1.0 and private_pass_rate == 0.0 and tests_for(test_summary, "private") > 0:
        return _result(
            difficulty="reasonable",
            failure_category="benchmark_suspicion",
            benchmark_quality="hidden_or_underspecified_requirements",
            efficacy="Suspicious (Needs Audit)",
            suspicious=True,
            needs_audit=True,
        )

    if (
        tests_for(test_summary, "public") > 0
        and tests_for(test_summary, "private") > 0
        and abs(public_pass_rate - private_pass_rate) >= 0.5
        and max(public_pass_rate, private_pass_rate) >= 0.75
    ):
        return _result(
            difficulty="reasonable",
            failure_category="benchmark_suspicion",
            benchmark_quality="public_private_divergence",
            efficacy="Suspicious (Needs Audit)",
            suspicious=True,
            needs_audit=True,
        )

    if tests_for(test_summary, "generated") > 0 and public_pass_rate >= 0.9 and generated_pass_rate <= 0.4:
        return _result(
            difficulty="reasonable",
            failure_category="logical_or_edge_failure",
            benchmark_quality="generated_tests_expose_weakness",
            efficacy="High Efficacy",
            suspicious=False,
            needs_audit=False,
        )

    if pass_rate >= 0.95:
        return _result(
            difficulty="trivial",
            failure_category="clean_pass",
            benchmark_quality="clean_evaluation",
            efficacy="Low Efficacy",
            suspicious=False,
            needs_audit=False,
        )

    if 0.25 <= pass_rate < 0.95:
        benchmark_quality = (
            "ambiguous_or_brittle"
            if dominant_failure == "format_mismatch"
            else "clean_evaluation"
        )
        efficacy = "Moderate Efficacy" if pass_rate > 0.8 else "High Efficacy"
        return _result(
            difficulty="reasonable",
            failure_category="logical_or_edge_failure",
            benchmark_quality=benchmark_quality,
            efficacy=efficacy,
            suspicious=benchmark_quality != "clean_evaluation",
            needs_audit=benchmark_quality != "clean_evaluation",
        )

    if pass_rate == 0.0:
        return _result(
            difficulty="extreme",
            failure_category="logical_or_test_failure",
            benchmark_quality="clean_evaluation",
            efficacy="Moderate Efficacy",
            suspicious=False,
            needs_audit=False,
        )

    return _result(
        difficulty="reasonable",
        failure_category="logical_or_edge_failure",
        benchmark_quality="clean_evaluation",
        efficacy="Moderate Efficacy",
        suspicious=False,
        needs_audit=False,
    )


def _result(
    *,
    difficulty: str,
    failure_category: str,
    benchmark_quality: str,
    efficacy: str,
    suspicious: bool,
    needs_audit: bool,
) -> dict[str, Any]:
    return {
        "difficulty_estimate": difficulty,
        "failure_category": failure_category,
        "benchmark_quality_signal": benchmark_quality,
        "efficacy_label": efficacy,
        "suspicious": suspicious,
        "needs_audit": needs_audit,
    }
