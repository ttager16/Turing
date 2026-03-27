from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from turing_takehome.llm import embed_texts_cached_for_target


class EmbeddingCacheTest(unittest.TestCase):
    def test_embedding_cache_reuses_vectors_for_same_text(self) -> None:
        call_counter = {"count": 0}

        def fake_embed_texts_for_target(target_name: str, texts: list[str], *, model_name: str | None = None, trace_dir: Path | None = None) -> dict:
            call_counter["count"] += 1
            return {
                "vectors": [[float(index + 1), 0.0] for index, _ in enumerate(texts)],
                "model": model_name or "nomic-embed-code",
                "usage": {"prompt_tokens": len(texts)},
            }

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "embeddings.json"
            with patch("turing_takehome.llm.embed_texts_for_target", side_effect=fake_embed_texts_for_target):
                first = embed_texts_cached_for_target(
                    "local-qwen",
                    ["alpha", "beta"],
                    cache_path=cache_path,
                    model_name="nomic-embed-code",
                )
                second = embed_texts_cached_for_target(
                    "local-qwen",
                    ["alpha", "beta"],
                    cache_path=cache_path,
                    model_name="nomic-embed-code",
                )
                payload = json.loads(cache_path.read_text(encoding="utf-8"))

        self.assertEqual(call_counter["count"], 1)
        self.assertEqual(first["vectors"], second["vectors"])
        self.assertEqual(second["cache_hits"], 2)
        self.assertEqual(payload.get("cache_version"), "embedding-cache-v1")


if __name__ == "__main__":
    unittest.main()
