from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from turing_takehome.stages.sample_efficacy_analysis.data import TestCase
from turing_takehome.stages.sample_efficacy_analysis.execution import (
    prepare_execution_workspace,
    probe_candidate,
    run_test_case,
)


class Stage2HarnessRegressionTests(unittest.TestCase):
    def _workspace(self, code: str) -> tuple[Path, Path, tempfile.TemporaryDirectory[str]]:
        tmpdir = tempfile.TemporaryDirectory()
        trace_dir = Path(tmpdir.name)
        candidate_path, harness_path = prepare_execution_workspace(trace_dir, code)
        return candidate_path, harness_path, tmpdir

    def test_string_literal_output_is_not_coerced(self) -> None:
        code = "\n".join(
            [
                "def solve():",
                '    return "0"',
            ]
        )
        candidate_path, harness_path, tmpdir = self._workspace(code)
        self.addCleanup(tmpdir.cleanup)
        result = run_test_case(
            candidate_path,
            harness_path,
            "solve",
            TestCase("public", 0, "", '"0"', "stdout"),
            timeout_seconds=5,
        )
        self.assertEqual(result.status, "pass")
        self.assertEqual(result.actual, "0")

    def test_unicode_output_round_trips_through_harness(self) -> None:
        code = "\n".join(
            [
                "def solve():",
                '    return {"explanation": "A → B"}',
            ]
        )
        candidate_path, harness_path, tmpdir = self._workspace(code)
        self.addCleanup(tmpdir.cleanup)
        result = run_test_case(
            candidate_path,
            harness_path,
            "solve",
            TestCase("public", 0, "", '{"explanation": "A → B"}', "json"),
            timeout_seconds=5,
        )
        self.assertEqual(result.status, "pass")
        self.assertEqual(result.actual, {"explanation": "A → B"})

    def test_probe_candidate_reports_syntax_error_for_incomplete_code(self) -> None:
        code = "\n".join(
            [
                "def solve(x):",
                "    return (x +",
            ]
        )
        candidate_path, harness_path, tmpdir = self._workspace(code)
        self.addCleanup(tmpdir.cleanup)
        probe = probe_candidate(
            candidate_path,
            harness_path,
            "solve",
            timeout_seconds=5,
        )
        self.assertEqual(probe.status, "error")
        self.assertEqual(probe.exception_type, "SyntaxError")

    def test_nested_float_noise_is_tolerated(self) -> None:
        code = "\n".join(
            [
                "def solve():",
                "    return {",
                '        "polynomial_value": -0.46112500000000023,',
                '        "values": [1.912109375, -0.546875],',
                "    }",
            ]
        )
        candidate_path, harness_path, tmpdir = self._workspace(code)
        self.addCleanup(tmpdir.cleanup)
        result = run_test_case(
            candidate_path,
            harness_path,
            "solve",
            TestCase(
                "private",
                10,
                "",
                '{"polynomial_value": -0.461125, "values": [1.91211, -0.54688]}',
                "json",
            ),
            timeout_seconds=5,
        )
        self.assertEqual(result.status, "pass")


if __name__ == "__main__":
    unittest.main()
