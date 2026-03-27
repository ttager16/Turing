from __future__ import annotations

import unittest

from turing_takehome.stages.sample_requirements_analysis.audit_core.section_runner import VERDICT_SCORE
from turing_takehome.stages.sample_requirements_analysis.audit_core.workbook import (
    classify_ideal,
    classify_prompt,
    classify_tests,
)


class Stage1WorkbookLogicTests(unittest.TestCase):
    def test_unclear_prompt_result_is_not_marked_usable(self) -> None:
        row = {
            "p_function_signature_present": "PASS",
            "p_practical_algorithmic_problem": "PASS",
            "p_not_vague": "PASS",
            "p_no_conflicting_objectives": "PASS",
            "p_structured_layout": "UNCLEAR",
            "v_prompt_test_solution_aligned": "PASS",
            "v_model_breaking_prompt_defined_only": "PASS",
            "v_no_unmentioned_internal_logic": "PASS",
            "p_no_unrealistic_constraints": "PASS",
        }
        self.assertEqual(classify_prompt(row), "Needs Fixing")

    def test_unclear_ideal_result_is_not_marked_usable(self) -> None:
        row = {
            "i_executes_without_error": "PASS",
            "i_passes_internal_tests": "PASS",
            "Runtime_Pass_Rate": "5/5",
            "i_no_globals": "UNCLEAR",
            "v_no_unmentioned_internal_logic": "PASS",
            "v_prompt_test_solution_aligned": "PASS",
            "v_model_breaking_prompt_defined_only": "PASS",
        }
        self.assertEqual(classify_ideal(row), "Needs Fixing")

    def test_unclear_tests_result_is_not_marked_usable(self) -> None:
        row = {
            "t_json_encoded": "PASS",
            "t_string_fields": "PASS",
            "t_single_call_per_test": "UNCLEAR",
            "v_no_extra_parameters": "PASS",
            "v_prompt_test_solution_aligned": "PASS",
            "v_model_breaking_prompt_defined_only": "PASS",
            "t_json_escaping_valid": "PASS",
            "t_input_json_object": "PASS",
            "t_output_json_object": "PASS",
            "v_cross_verified_dry_run": "PASS",
        }
        self.assertEqual(classify_tests(row), "Needs Fixing")

    def test_unclear_subsection_score_is_conservative(self) -> None:
        self.assertEqual(VERDICT_SCORE["UNCLEAR"], 0.25)


if __name__ == "__main__":
    unittest.main()
