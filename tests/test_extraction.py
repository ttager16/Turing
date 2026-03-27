from __future__ import annotations

import unittest

from turing_takehome.stages.sample_efficacy_analysis.extraction import extract_python_code


class ExtractionTest(unittest.TestCase):
    def test_preserves_top_level_imports_when_response_is_plain_python(self) -> None:
        response = "\n".join(
            [
                "from typing import Any, Dict, List",
                "import threading",
                "",
                "def build_adaptive_sensor_list(data_stream, invalidations=[]):",
                "    lock = threading.Lock()",
                "    return {}",
            ]
        )
        result = extract_python_code(response)
        self.assertEqual(result.status, "ok")
        self.assertIn("import threading", result.code)
        self.assertIn("def build_adaptive_sensor_list", result.code)

    def test_trims_leading_prose_but_keeps_helpers_and_imports(self) -> None:
        response = "\n".join(
            [
                "Here is the solution:",
                "",
                "import math",
                "",
                "class Helper:",
                "    pass",
                "",
                "def solve(x):",
                "    return math.ceil(x)",
            ]
        )
        result = extract_python_code(response)
        self.assertEqual(result.status, "ok")
        self.assertNotIn("Here is the solution:", result.code)
        self.assertIn("import math", result.code)
        self.assertIn("class Helper", result.code)
        self.assertIn("def solve", result.code)

    def test_prefers_fenced_code_when_available(self) -> None:
        response = "text\n```python\nimport math\n\ndef solve(x):\n    return math.floor(x)\n```\nthanks"
        result = extract_python_code(response)
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.code.strip().splitlines()[0], "import math")

    def test_trims_trailing_prose_after_valid_code(self) -> None:
        response = "\n".join(
            [
                "import math",
                "",
                "def solve(x):",
                "    return math.floor(x)",
                "",
                "This explanation is not part of the code.",
            ]
        )
        result = extract_python_code(response)
        self.assertEqual(result.status, "ok")
        self.assertNotIn("This explanation", result.code)
        self.assertIn("return math.floor(x)", result.code)

    def test_preserves_decorators_and_top_level_constants(self) -> None:
        response = "\n".join(
            [
                "DEFAULT_SCALE = 2",
                "",
                "@staticmethod",
                "def solve(x):",
                "    return round(x, DEFAULT_SCALE)",
            ]
        )
        result = extract_python_code(response)
        self.assertEqual(result.status, "ok")
        self.assertIn("DEFAULT_SCALE = 2", result.code)
        self.assertIn("@staticmethod", result.code)

    def test_skips_malformed_early_snippet_if_later_function_is_valid(self) -> None:
        response = "\n".join(
            [
                "import math",
                "def broken(",
                "",
                "def solve(x):",
                "    return math.ceil(x)",
            ]
        )
        result = extract_python_code(response)
        self.assertEqual(result.status, "ok")
        self.assertNotIn("def broken(", result.code)
        self.assertIn("def solve", result.code)


if __name__ == "__main__":
    unittest.main()
