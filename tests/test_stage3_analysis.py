from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from turing_takehome.stages.dataset_analysis.runner import (
    _attempt_variance_features,
    _build_relationship_rows,
    _failure_flags_for_relationships,
    _stage3_auditor_disagreement,
    _model_disagreement_features,
    _similarity_pairs,
    _threshold_sensitivity_features,
)


def _base_row(index: int, *, flags: str = "", pass_rate: float = 0.8, suspicious: bool = False) -> dict:
    return {
        "Index": index,
        "Stage1Flags": flags,
        "WinnerCombinedPassRate": pass_rate,
        "Suspicious": suspicious,
        "Stage1Section1Score": 0.8,
        "Stage1Section2Score": 0.8,
        "Stage1Section3Score": 0.8,
        "Stage1Section4Score": 0.8,
        "Stage1Section6Score": 0.8,
        "Stage1Section7Score": 0.8,
        "Stage1Score": 0.8,
        "Stage1CriticalFailCount": 0,
    }


class Stage3RelationshipTest(unittest.TestCase):
    def test_sparse_failing_checks_are_excluded(self) -> None:
        rows = [_base_row(index) for index in range(12)]
        for index in range(4):
            rows[index]["Stage1Flags"] = "sparse_signal"
            rows[index]["WinnerCombinedPassRate"] = 0.1
            rows[index]["Suspicious"] = True
        relationship_rows = _build_relationship_rows(rows)
        failing_signals = {row["Signal"] for row in relationship_rows if row["Group"] == "failing_check"}
        self.assertNotIn("sparse_signal", failing_signals)

    def test_supported_signal_includes_adjusted_strength_and_reliability(self) -> None:
        rows = [_base_row(index) for index in range(20)]
        for index in range(8):
            rows[index]["Stage1Flags"] = "supported_signal"
            rows[index]["WinnerCombinedPassRate"] = 0.15
            rows[index]["Suspicious"] = index < 4
        relationship_rows = _build_relationship_rows(rows)
        matching = [row for row in relationship_rows if row["Signal"] == "supported_signal"]
        self.assertEqual(len(matching), 1)
        self.assertGreater(matching[0]["AdjustedStrength"], 0.0)
        self.assertIn(matching[0]["Reliability"], {"moderate", "broad"})

    def test_attempt_variance_marks_volatile_samples(self) -> None:
        features = _attempt_variance_features(
            [
                {"CombinedPassRate": 0.95, "ExecutionProbeStatus": "ok"},
                {"CombinedPassRate": 0.30, "ExecutionProbeStatus": "ok"},
                {"CombinedPassRate": 0.90, "ExecutionProbeStatus": "error"},
            ]
        )
        self.assertEqual(features["label"], "volatile")
        self.assertGreater(features["range"], 0.5)

    def test_model_disagreement_detects_large_gap(self) -> None:
        features = _model_disagreement_features(
            [
                {"BestCombinedPassRate": 0.9, "EfficacyLabel": "Low Efficacy", "BenchmarkQualitySignal": "clean_evaluation", "Suspicious": False},
                {"BestCombinedPassRate": 0.2, "EfficacyLabel": "High Efficacy", "BenchmarkQualitySignal": "clean_evaluation", "Suspicious": True},
            ]
        )
        self.assertEqual(features["label"], "strong_disagreement")
        self.assertTrue(features["efficacy_disagreement"])
        self.assertTrue(features["suspicion_disagreement"])

    def test_threshold_sensitivity_detects_near_boundary(self) -> None:
        features = _threshold_sensitivity_features(
            combined_pass_rate=0.948,
            efficacy_label="Low Efficacy",
            suspicious=False,
        )
        self.assertEqual(features["label"], "high")
        self.assertEqual(features["nearest_boundary"], "saturation_boundary")

    def test_similarity_pairs_use_embedding_signal(self) -> None:
        left = {
            "Index": 1,
            "FunctionName": "solve",
            "_prompt_ngrams": {"abc", "bcd"},
            "_template_ngrams": {"tpl"},
            "_test_signature": {"test_a"},
            "_starter_signature": {"def solve", "return"},
            "_title_ngrams": {"array"},
            "_function_signature": {"solve"},
            "_embedding_vector": [1.0, 0.0],
        }
        right = {
            "Index": 2,
            "FunctionName": "solve",
            "_prompt_ngrams": {"xyz"},
            "_template_ngrams": {"tpl"},
            "_test_signature": {"test_a"},
            "_starter_signature": {"def solve", "return"},
            "_title_ngrams": {"list"},
            "_function_signature": {"solve"},
            "_embedding_vector": [0.99, 0.01],
        }
        pairs = _similarity_pairs([left, right], near_duplicate_threshold=0.68, template_threshold=0.55)
        self.assertEqual(len(pairs), 1)
        self.assertIn(pairs[0].similarity_label, {"semantic_duplicate", "near_duplicate"})
        self.assertGreater(pairs[0].embedding_similarity, 0.9)

    def test_similarity_pairs_do_not_flag_title_only_overlap(self) -> None:
        left = {
            "Index": 1,
            "FunctionName": "solve_left",
            "_prompt_ngrams": {"aaa"},
            "_template_ngrams": {"bbb"},
            "_test_signature": {"test_a"},
            "_starter_signature": {"left"},
            "_title_ngrams": {"shared", "title"},
            "_function_signature": {"solve_left"},
            "_embedding_vector": [],
        }
        right = {
            "Index": 2,
            "FunctionName": "solve_right",
            "_prompt_ngrams": {"zzz"},
            "_template_ngrams": {"yyy"},
            "_test_signature": {"test_b"},
            "_starter_signature": {"right"},
            "_title_ngrams": {"shared", "title"},
            "_function_signature": {"solve_right"},
            "_embedding_vector": [],
        }
        pairs = _similarity_pairs([left, right], near_duplicate_threshold=0.68, template_threshold=0.55)
        self.assertEqual(pairs, [])

    def test_stage3_auditor_disagreement_works_without_stage2_multimodel(self) -> None:
        rows = [
            {
                "Index": 7,
                "QuestionTitle": "Sample",
                "Difficulty": "medium",
                "WinnerCombinedPassRate": 0.82,
                "OraclePassRate": 1.0,
                "EfficacyLabel": "Moderate Efficacy",
                "Suspicious": False,
                "RedundancyScore": 0.1,
                "DuplicateLabel": "",
                "OutlierFlags": "",
                "AttemptVarianceLabel": "stable",
                "ThresholdSensitivityLabel": "stable",
                "ContradictionLabel": "",
                "AuditPriority": "medium",
            }
        ]
        mocked = {
            "stage3-audit:7:openai-gpt-5-mini": {
                "dataset_utility_label": "usable",
                "primary_risk": "none",
                "audit_priority": "medium",
            },
            "stage3-audit:7:local-qwen": {
                "dataset_utility_label": "caveated",
                "primary_risk": "benchmark_defect",
                "audit_priority": "high",
            },
        }
        with patch("turing_takehome.stages.dataset_analysis.runner.run_async_tasks_sync", return_value=mocked):
            result = _stage3_auditor_disagreement(rows, output_dir=Path("."))
        self.assertEqual(result[7]["label"], "strong_disagreement")
        self.assertEqual(result[7]["recommended_priority"], "high")

    def test_relationships_use_full_internal_failure_flags_not_truncated_display(self) -> None:
        rows = [_base_row(index) for index in range(20)]
        for index in range(8):
            rows[index]["Stage1Flags"] = "display_only"
            rows[index]["_Stage1FailureFlags"] = ["display_only", "hidden_signal"]
            rows[index]["WinnerCombinedPassRate"] = 0.1
            rows[index]["Suspicious"] = True
        relationship_rows = _build_relationship_rows(rows)
        signals = {row["Signal"] for row in relationship_rows}
        self.assertIn("hidden_signal", signals)

    def test_failure_flags_helper_falls_back_to_display_flags(self) -> None:
        flags = _failure_flags_for_relationships({"Stage1Flags": "a; b"})
        self.assertEqual(flags, {"a", "b"})


if __name__ == "__main__":
    unittest.main()
