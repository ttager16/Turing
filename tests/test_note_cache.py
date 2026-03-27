from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from turing_takehome.reporting.notes import (
    build_note_cache_fingerprint,
    split_cached_note_requests,
    update_note_cache,
)


class NoteCacheTest(unittest.TestCase):
    def test_cache_hit_requires_matching_fingerprint(self) -> None:
        request = {
            "request_id": "stage2:1:model:0",
            "prompt": "Explain Public_01 only.",
            "allowed_columns": ["Public_01"],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "notes.json"
            update_note_cache(
                "sample-efficacy-analysis",
                [request],
                {"stage2:1:model:0": {"Public_01": "first note"}},
                cache_path,
            )
            cached_notes, missing_requests = split_cached_note_requests(
                "sample-efficacy-analysis",
                [request],
                cache_path,
            )
            self.assertEqual(cached_notes["stage2:1:model:0"]["Public_01"], "first note")
            self.assertEqual(missing_requests, [])

    def test_prompt_change_invalidates_cache(self) -> None:
        original_request = {
            "request_id": "stage3:7",
            "prompt": "Describe DifficultySignalRegime.",
            "allowed_columns": ["DifficultySignalRegime"],
        }
        changed_request = {
            "request_id": "stage3:7",
            "prompt": "Describe DifficultySignalRegime with stronger wording.",
            "allowed_columns": ["DifficultySignalRegime"],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "notes.json"
            update_note_cache(
                "dataset-analysis",
                [original_request],
                {"stage3:7": {"DifficultySignalRegime": "old note"}},
                cache_path,
            )
            cached_notes, missing_requests = split_cached_note_requests(
                "dataset-analysis",
                [changed_request],
                cache_path,
            )
            self.assertEqual(cached_notes, {})
            self.assertEqual(missing_requests, [changed_request])

    def test_fingerprint_changes_when_allowed_columns_change(self) -> None:
        left = build_note_cache_fingerprint(
            "dataset-analysis",
            {
                "request_id": "stage3:1",
                "prompt": "Same prompt.",
                "allowed_columns": ["BenchmarkDefectCandidate"],
            },
        )
        right = build_note_cache_fingerprint(
            "dataset-analysis",
            {
                "request_id": "stage3:1",
                "prompt": "Same prompt.",
                "allowed_columns": ["DifficultySignalRegime"],
            },
        )
        self.assertNotEqual(left, right)


if __name__ == "__main__":
    unittest.main()
