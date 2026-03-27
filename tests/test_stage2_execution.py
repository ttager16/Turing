import unittest

from turing_takehome.stages.sample_efficacy_analysis.execution import outputs_match


class Stage2ExecutionTests(unittest.TestCase):
    def test_outputs_match_preserves_string_literals(self) -> None:
        self.assertTrue(outputs_match("0", "0"))
        self.assertFalse(outputs_match("0", 0))
        self.assertFalse(outputs_match("true", True))

    def test_outputs_match_allows_small_float_noise(self) -> None:
        self.assertTrue(outputs_match(2.276367, 2.2763671875))
        self.assertTrue(
            outputs_match(
                {"polynomial_value": -0.461125, "values": [1.91211, -0.54688]},
                {"polynomial_value": -0.46112500000000023, "values": [1.912109375, -0.546875]},
            )
        )

    def test_outputs_match_requires_real_numeric_agreement(self) -> None:
        self.assertTrue(outputs_match(3, 3.0))
        self.assertFalse(outputs_match(3, 3.01))
        self.assertFalse(outputs_match({"x": 1.0}, {"x": 1.01}))


if __name__ == "__main__":
    unittest.main()
