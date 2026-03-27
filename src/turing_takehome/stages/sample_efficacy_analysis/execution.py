from __future__ import annotations

import json
import math
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .data import TestCase


HARNESS_CODE = """
from __future__ import annotations

import importlib.util
import json
import sys
import traceback
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")


def normalize_result(value):
    return value


def load_module(code_path: Path):
    spec = importlib.util.spec_from_file_location("candidate_solution", code_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module from {code_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    if len(sys.argv) < 4:
        raise SystemExit("Usage: harness.py <mode> <code_path> <function_name>")
    mode = sys.argv[1]
    code_path = Path(sys.argv[2])
    function_name = sys.argv[3]
    payload = json.loads(sys.stdin.read() or "{}")
    try:
        module = load_module(code_path)
        function = getattr(module, function_name)
        if mode == "probe":
            print(json.dumps({"ok": True}))
            return 0
        if mode != "test":
            raise RuntimeError(f"Unsupported mode: {mode}")
        args = payload.get("args", [])
        result = function(*args)
        print(json.dumps({"ok": True, "result": normalize_result(result)}))
        return 0
    except Exception as exc:
        traceback.print_exc()
        print(json.dumps({
            "ok": False,
            "exception_type": exc.__class__.__name__,
            "exception_message": str(exc),
        }))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
"""


@dataclass(frozen=True)
class ExecutionProbeResult:
    status: str
    exception_type: str
    stdout: str
    stderr: str
    timeout: bool


@dataclass(frozen=True)
class TestExecutionResult:
    visibility: str
    case_index: int
    status: str
    expected: Any
    actual: Any
    exception_type: str
    exception_message: str
    stdout: str
    stderr: str
    timeout: bool
    failure_type: str


@dataclass(frozen=True)
class ArgumentExecutionResult:
    status: str
    actual: Any
    exception_type: str
    exception_message: str
    stdout: str
    stderr: str
    timeout: bool


@dataclass(frozen=True)
class _HarnessRun:
    returncode: int
    stdout: str
    stderr: str
    timeout: bool


def prepare_execution_workspace(trace_dir: Path, extracted_code: str) -> tuple[Path, Path]:
    trace_dir.mkdir(parents=True, exist_ok=True)
    candidate_path = trace_dir / "candidate_solution.py"
    candidate_path.write_text(extracted_code, encoding="utf-8")
    harness_path = trace_dir / "_stage2_harness.py"
    harness_path.write_text(textwrap.dedent(HARNESS_CODE).strip() + "\n", encoding="utf-8")
    return candidate_path, harness_path


def probe_candidate(
    candidate_path: Path,
    harness_path: Path,
    function_name: str,
    *,
    timeout_seconds: int,
) -> ExecutionProbeResult:
    completed = _run_harness(
        harness_path,
        "probe",
        candidate_path,
        function_name,
        payload={},
        timeout_seconds=timeout_seconds,
    )
    payload = _parse_payload(completed.stdout)
    if completed.timeout:
        return ExecutionProbeResult("timeout", "", completed.stdout, completed.stderr, True)
    if completed.returncode == 0 and payload.get("ok") is True:
        return ExecutionProbeResult("ok", "", completed.stdout, completed.stderr, False)
    return ExecutionProbeResult(
        "error",
        str(payload.get("exception_type", "")),
        completed.stdout,
        completed.stderr,
        False,
    )


def run_test_case(
    candidate_path: Path,
    harness_path: Path,
    function_name: str,
    test_case: TestCase,
    *,
    timeout_seconds: int,
) -> TestExecutionResult:
    try:
        args = [json.loads(line) for line in test_case.input_text.splitlines() if line.strip()]
        expected = json.loads(test_case.output_text)
    except Exception as exc:
        return TestExecutionResult(
            visibility=test_case.visibility,
            case_index=test_case.case_index,
            status="error",
            expected=test_case.output_text,
            actual=None,
            exception_type=exc.__class__.__name__,
            exception_message=str(exc),
            stdout="",
            stderr="",
            timeout=False,
            failure_type="invalid_test_case",
        )
    execution = execute_arguments(
        candidate_path,
        harness_path,
        function_name,
        args,
        timeout_seconds=timeout_seconds,
    )
    if execution.timeout:
        return TestExecutionResult(
            visibility=test_case.visibility,
            case_index=test_case.case_index,
            status="timeout",
            expected=expected,
            actual=None,
            exception_type="TimeoutExpired",
            exception_message="Timed out while running the test case.",
            stdout=execution.stdout,
            stderr=execution.stderr,
            timeout=True,
            failure_type="timeout",
        )
    if execution.status != "ok":
        exception_type = execution.exception_type or "ExecutionError"
        return TestExecutionResult(
            visibility=test_case.visibility,
            case_index=test_case.case_index,
            status="error",
            expected=expected,
            actual=None,
            exception_type=exception_type,
            exception_message=execution.exception_message,
            stdout=execution.stdout,
            stderr=execution.stderr,
            timeout=False,
            failure_type=_classify_execution_failure(exception_type),
        )

    actual = execution.actual
    status = "pass" if outputs_match(expected, actual) else "fail"
    return TestExecutionResult(
        visibility=test_case.visibility,
        case_index=test_case.case_index,
        status=status,
        expected=expected,
        actual=actual,
        exception_type="",
        exception_message="",
        stdout=execution.stdout,
        stderr=execution.stderr,
        timeout=False,
        failure_type=_classify_mismatch_failure(expected, actual) if status == "fail" else "",
    )


def execute_arguments(
    candidate_path: Path,
    harness_path: Path,
    function_name: str,
    args: list[Any],
    *,
    timeout_seconds: int,
) -> ArgumentExecutionResult:
    completed = _run_harness(
        harness_path,
        "test",
        candidate_path,
        function_name,
        payload={"args": args},
        timeout_seconds=timeout_seconds,
    )
    payload = _parse_payload(completed.stdout)
    if completed.timeout:
        return ArgumentExecutionResult(
            status="timeout",
            actual=None,
            exception_type="TimeoutExpired",
            exception_message="Timed out while running the function.",
            stdout=completed.stdout,
            stderr=completed.stderr,
            timeout=True,
        )
    if completed.returncode != 0 or payload.get("ok") is False:
        exception_type = str(payload.get("exception_type", "")) or "ExecutionError"
        return ArgumentExecutionResult(
            status="error",
            actual=None,
            exception_type=exception_type,
            exception_message=str(payload.get("exception_message", "")),
            stdout=completed.stdout,
            stderr=completed.stderr,
            timeout=False,
        )
    return ArgumentExecutionResult(
        status="ok",
        actual=payload.get("result"),
        exception_type="",
        exception_message="",
        stdout=completed.stdout,
        stderr=completed.stderr,
        timeout=False,
    )


def _run_harness(
    harness_path: Path,
    mode: str,
    candidate_path: Path,
    function_name: str,
    *,
    payload: dict[str, Any],
    timeout_seconds: int,
) -> _HarnessRun:
    try:
        env = dict(**__import__("os").environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        completed = subprocess.run(
            [sys.executable, str(harness_path), mode, str(candidate_path), function_name],
            input=json.dumps(payload, ensure_ascii=False),
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
            env=env,
        )
        return _HarnessRun(
            completed.returncode,
            completed.stdout,
            completed.stderr,
            False,
        )
    except subprocess.TimeoutExpired as exc:
        return _HarnessRun(
            1,
            exc.stdout or "",
            exc.stderr or "",
            True,
        )


def _parse_payload(stdout_text: str) -> dict[str, Any]:
    text = stdout_text.strip()
    if not text:
        return {}
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return {}
    try:
        return json.loads(lines[-1])
    except Exception:
        return {}


def _classify_execution_failure(exception_type: str) -> str:
    lowered = exception_type.lower()
    if "syntax" in lowered:
        return "syntax_error"
    return "runtime_error"


def _classify_mismatch_failure(expected: Any, actual: Any) -> str:
    if type(expected) is not type(actual):
        return "format_mismatch"
    return "incorrect_output"


def outputs_match(expected: Any, actual: Any) -> bool:
    if isinstance(expected, bool) or isinstance(actual, bool):
        return expected is actual
    if expected is None or actual is None:
        return expected is actual
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return _numbers_match(expected, actual)
    if isinstance(expected, str) and isinstance(actual, str):
        return expected == actual
    if isinstance(expected, list) and isinstance(actual, list):
        return len(expected) == len(actual) and all(
            outputs_match(expected_item, actual_item)
            for expected_item, actual_item in zip(expected, actual)
        )
    if isinstance(expected, dict) and isinstance(actual, dict):
        if set(expected.keys()) != set(actual.keys()):
            return False
        return all(outputs_match(expected[key], actual[key]) for key in expected)
    return expected == actual


def _numbers_match(expected: int | float, actual: int | float) -> bool:
    expected_value = float(expected)
    actual_value = float(actual)
    if expected_value.is_integer() and actual_value.is_integer():
        return int(expected_value) == int(actual_value)
    return math.isclose(expected_value, actual_value, rel_tol=1e-9, abs_tol=1e-5)
