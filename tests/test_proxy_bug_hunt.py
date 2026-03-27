from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from turing_takehome.stages.manual_audit.proxy_bug_hunt import (
    _load_generated_cases,
    run_cli,
)
from turing_takehome.stages.sample_efficacy_analysis.data import SampleRecord


class ProxyBugHuntTest(unittest.TestCase):
    def test_load_generated_cases_merges_focus_and_io(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            generated_dir = root / "generated_tests"
            generated_dir.mkdir(parents=True, exist_ok=True)
            (generated_dir / "accepted_cases.json").write_text(
                json.dumps(
                    [
                        {
                            "case_index": 1,
                            "input_text": "arg1\narg2",
                            "output_text": '{"ok": true}',
                        }
                    ]
                ),
                encoding="utf-8",
            )
            (generated_dir / "raw_cases.json").write_text(
                json.dumps(
                    [
                        {
                            "case_index": 1,
                            "input_lines": ["arg1", "arg2"],
                            "focus": "edge_case",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            merged = _load_generated_cases(root)
            self.assertEqual(merged[1]["input_text"], "arg1\narg2")
            self.assertEqual(merged[1]["output_text"], '{"ok": true}')
            self.assertEqual(merged[1]["focus"], "edge_case")

    def test_run_cli_writes_checkpoint_and_whitelisted_csv(self) -> None:
        sample = SampleRecord(
            index=7,
            row={"question_id": "q7", "question_title": "Title"},
            metadata={"func_name": "solve"},
            question_content="Prompt",
            starter_code="",
            ideal_response="def solve():\n    return 1",
            public_tests=[],
            private_tests=[],
        )
        stage2_rows = {
            7: {
                "TargetName": "openai-gpt-5-mini",
                "EfficacyLabel": "Low Efficacy",
                "FailureCategory": "benchmark_suspicion",
            }
        }
        grouped_rows = {
            (7, "openai-gpt-5-mini", 1): [
                {
                    "sample_index": 7,
                    "question_id": "q7",
                    "visibility": "public",
                    "case_index": 0,
                    "attempt_index": 1,
                    "failure_type": "incorrect_output",
                    "exception_type": "",
                    "exception_message": "",
                    "target_name": "openai-gpt-5-mini",
                    "status": "fail",
                    "expected": {"ok": True},
                    "actual": {"ok": False},
                    "stderr": "",
                }
            ]
        }

        async def fake_run_safe_proxy_tasks(task_specs, *, max_concurrency):
            return {
                task_specs[0].request_id: {
                    "final_verdict": "pipeline_or_test_fault",
                    "pipeline_integrity": "bug_confirmed",
                    "test_validity": "valid",
                    "sample_validity": "likely_valid",
                    "likely_root_cause": "test_case_bug",
                    "confidence": "high",
                    "reason": "reason",
                    "recommended_followup": "followup",
                    "unexpected_key": "ignored",
                }
            }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "out"
            with (
                patch("turing_takehome.stages.manual_audit.proxy_bug_hunt.load_samples", return_value=[sample]),
                patch("turing_takehome.stages.manual_audit.proxy_bug_hunt._load_stage2_rows", return_value=stage2_rows),
                patch("turing_takehome.stages.manual_audit.proxy_bug_hunt._group_stage2_test_rows", return_value=grouped_rows),
                patch("turing_takehome.stages.manual_audit.proxy_bug_hunt._read_optional_text", return_value=""),
                patch("turing_takehome.stages.manual_audit.proxy_bug_hunt._load_generated_cases", return_value={}),
                patch("turing_takehome.stages.manual_audit.proxy_bug_hunt._run_safe_proxy_tasks", side_effect=fake_run_safe_proxy_tasks),
            ):
                exit_code = run_cli(
                    [
                        "--indices",
                        "7",
                        "--output-dir",
                        str(output_dir),
                        "--stage2-dir",
                        str(output_dir / "stage2"),
                        "--batch-size",
                        "1",
                        "--max-batches",
                        "1",
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertTrue((output_dir / "proxy_bug_hunt.csv").exists())
            self.assertTrue((output_dir / "summary.md").exists())
            self.assertTrue((output_dir / "checkpoints" / "batch_001" / "proxy_bug_hunt.csv").exists())
            csv_text = (output_dir / "proxy_bug_hunt.csv").read_text(encoding="utf-8")
            self.assertNotIn("unexpected_key", csv_text)

    def test_resume_skips_completed_rows(self) -> None:
        sample = SampleRecord(
            index=8,
            row={"question_id": "q8", "question_title": "Resume Title"},
            metadata={"func_name": "solve"},
            question_content="Prompt",
            starter_code="",
            ideal_response="def solve():\n    return 1",
            public_tests=[],
            private_tests=[],
        )
        stage2_rows = {8: {"TargetName": "openai-gpt-5-mini", "EfficacyLabel": "Low Efficacy", "FailureCategory": "benchmark_suspicion"}}
        grouped_rows = {
            (8, "openai-gpt-5-mini", 1): [
                {
                    "sample_index": 8,
                    "question_id": "q8",
                    "visibility": "public",
                    "case_index": 0,
                    "attempt_index": 1,
                    "failure_type": "incorrect_output",
                    "exception_type": "",
                    "exception_message": "",
                    "target_name": "openai-gpt-5-mini",
                    "status": "fail",
                    "expected": 1,
                    "actual": 0,
                    "stderr": "",
                },
                {
                    "sample_index": 8,
                    "question_id": "q8",
                    "visibility": "private",
                    "case_index": 1,
                    "attempt_index": 1,
                    "failure_type": "incorrect_output",
                    "exception_type": "",
                    "exception_message": "",
                    "target_name": "openai-gpt-5-mini",
                    "status": "fail",
                    "expected": 2,
                    "actual": 0,
                    "stderr": "",
                },
            ]
        }

        call_counter = {"count": 0}

        async def fake_run_safe_proxy_tasks(task_specs, *, max_concurrency):
            call_counter["count"] += 1
            return {
                spec.request_id: {
                    "final_verdict": "model_candidate_fault_only",
                    "pipeline_integrity": "looks_valid",
                    "test_validity": "valid",
                    "sample_validity": "likely_valid",
                    "likely_root_cause": "model_logic_failure",
                    "confidence": "medium",
                    "reason": spec.request_id,
                    "recommended_followup": "inspect",
                }
                for spec in task_specs
            }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "out"
            patches = (
                patch("turing_takehome.stages.manual_audit.proxy_bug_hunt.load_samples", return_value=[sample]),
                patch("turing_takehome.stages.manual_audit.proxy_bug_hunt._load_stage2_rows", return_value=stage2_rows),
                patch("turing_takehome.stages.manual_audit.proxy_bug_hunt._group_stage2_test_rows", return_value=grouped_rows),
                patch("turing_takehome.stages.manual_audit.proxy_bug_hunt._read_optional_text", return_value=""),
                patch("turing_takehome.stages.manual_audit.proxy_bug_hunt._load_generated_cases", return_value={}),
                patch("turing_takehome.stages.manual_audit.proxy_bug_hunt._run_safe_proxy_tasks", side_effect=fake_run_safe_proxy_tasks),
            )
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
                run_cli(
                    [
                        "--indices",
                        "8",
                        "--output-dir",
                        str(output_dir),
                        "--stage2-dir",
                        str(output_dir / "stage2"),
                        "--batch-size",
                        "1",
                        "--max-batches",
                        "1",
                    ]
                )
                self.assertEqual(call_counter["count"], 1)
                run_cli(
                    [
                        "--indices",
                        "8",
                        "--output-dir",
                        str(output_dir),
                        "--stage2-dir",
                        str(output_dir / "stage2"),
                        "--batch-size",
                        "1",
                        "--resume",
                    ]
                )
            self.assertEqual(call_counter["count"], 2)
            progress_rows = (output_dir / "progress.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(progress_rows), 2)


if __name__ == "__main__":
    unittest.main()
