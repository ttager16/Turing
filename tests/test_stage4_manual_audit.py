from __future__ import annotations

import unittest

from turing_takehome.stages.manual_audit.runner import (
    _build_detailed_rows,
    _build_summary_rows,
)


class Stage4ManualAuditTest(unittest.TestCase):
    def test_detailed_rows_include_notes_columns(self) -> None:
        selected_rows = [
            {
                "Index": 1,
                "QuestionId": "q1",
                "QuestionTitle": "Title",
                "Difficulty": "hard",
                "SelectionBucket": "contradiction",
                "SelectionReason": "reason",
                "Stage3AuditPriority": "critical",
                "PipelineUtilityLabel": "caveated",
                "Stage1Prompt": "Needs Fixing",
                "Stage1IdealResponse": "Usable",
                "Stage1TestCases": "Usable",
                "Stage2EfficacyLabel": "Suspicious (Needs Audit)",
                "Stage2BenchmarkQualitySignal": "public_private_divergence",
                "Stage2FailureCategory": "benchmark_suspicion",
                "WinnerCombinedPassRate": 0.4,
                "OraclePassRate": 1.0,
                "Stage3ModelDisagreementSource": "stage3_auditors",
                "ReviewContext": "context",
                "PromptExcerpt": "prompt",
            }
        ]
        reviews = {
            1: {
                "BenchmarkTrustCheck": "defective",
                "Notes-BenchmarkTrustCheck": "note a",
                "FailureAttribution": "dataset_fail",
                "Notes-FailureAttribution": "note b",
                "PipelineCalibrationCheck": "misses_problem",
                "Notes-PipelineCalibrationCheck": "note c",
                "FinalAction": "fix",
                "Notes-FinalAction": "note d",
                "SummaryConfidence": "medium",
                "Finding1DefectType": "test_issue",
                "Finding1Severity": "high",
                "Finding1Confidence": "medium",
                "Notes-Finding1": "note aa",
            }
        }
        rows = _build_detailed_rows(selected_rows, reviews)
        self.assertEqual(rows[0]["BenchmarkTrustCheck"], "defective")
        self.assertEqual(rows[0]["Notes-BenchmarkTrustCheck"], "note a")
        self.assertEqual(rows[0]["Finding1DefectType"], "test_issue")
        self.assertEqual(rows[0]["Finding1Severity"], "high")
        self.assertEqual(rows[0]["Notes-FinalAction"], "note d")

    def test_summary_rows_report_completion_and_agreement(self) -> None:
        selected_rows = [
            {"SelectionBucket": "contradiction"},
            {"SelectionBucket": "baseline"},
        ]
        detailed_rows = [
            {
                "ReviewStatus": "completed",
                "PipelineCalibrationCheck": "agree",
                "BenchmarkTrustCheck": "trustworthy",
                "FinalAction": "keep",
                "Finding1DefectType": "none",
                "Finding1Severity": "low",
                "Finding1Confidence": "high",
                "FailureAttribution": "model_fail",
                "SummaryConfidence": "high",
            },
            {
                "ReviewStatus": "pending",
                "PipelineCalibrationCheck": "",
                "BenchmarkTrustCheck": "",
                "FinalAction": "",
                "Finding1DefectType": "",
                "Finding1Severity": "",
                "Finding1Confidence": "",
                "FailureAttribution": "",
                "SummaryConfidence": "",
            },
        ]
        rows = _build_summary_rows(selected_rows, detailed_rows)
        by_name = {row["TestName"]: row for row in rows}
        self.assertEqual(by_name["review_completion"]["Result"], "REVIEW")
        self.assertIn("1 of 2", by_name["review_completion"]["Evidence"])
        self.assertIn("high=1", by_name["summary_confidence"]["Evidence"])


if __name__ == "__main__":
    unittest.main()
