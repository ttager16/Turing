from __future__ import annotations

from dataclasses import dataclass


OUTPUT_WORKBOOK_NAME = "guideline_audit.xlsx"
BACKUP_DIR_NAME = "backups"

METADATA_COLUMNS = [
    ("Index", "Index"),
    ("Question_Id", "QuestionId"),
    ("Question_Title", "QuestionTitle"),
    ("Difficulty", "Difficulty"),
    ("Function_Name", "FunctionName"),
    ("Runtime_Pass_Rate", "RuntimePassRate"),
]

DROP_REQUIREMENTS = {
    "s_in_markdown",
    "i_structured_classes_or_functions",
    "i_consistent_structure",
    "t_no_markdown_json_fence",
    "t_one_to_one_json_cases",
    "t_exact_output_check",
}

SECTION_MAP: dict[str, tuple[str, str, str]] = {}
DISPLAY_ORDER: list[str] = []


def assign(keys: list[str], code: str, subsection: str, category: str) -> None:
    for key in keys:
        SECTION_MAP[key] = (code, subsection, category)
        DISPLAY_ORDER.append(key)


assign(
    [
        "p_structured_layout",
        "p_realistic_context",
        "p_input_format_explicit",
        "p_output_format_explicit",
        "p_constraints_defined",
        "p_computational_limits_defined",
        "p_edge_cases_defined",
        "p_return_conditions_defined",
        "p_function_signature_present",
        "p_no_external_libs_stated",
        "p_metadata_alignment",
        "p_not_verbose",
    ],
    "1.1",
    "1.1_Structural_Expectations",
    "Prompt",
)
assign(
    [
        "p_practical_algorithmic_problem",
        "p_measurable_objective",
        "p_difficulty_balanced",
        "p_example_present",
        "p_no_unrealistic_constraints",
        "p_not_vague",
        "p_no_conflicting_objectives",
        "p_no_buzzwords",
        "p_no_time_window_constraints",
        "p_no_random_requirement",
    ],
    "1.2",
    "1.2_Content_Guidelines",
    "Prompt",
)
assign(["p_json_compatible_signature"], "1.3", "1.3_Quality_Checklist", "Prompt")
assign(
    [
        "i_no_globals",
        "i_state_encapsulated",
        "i_consistent_naming_docs",
        "i_no_arbitrary_limits",
        "i_single_entry_aligned",
        "i_helpers_for_repeated_logic",
        "i_no_sample_io_in_main",
        "i_no_parallelism",
        "i_deterministic_solution",
        "i_mp_module_level_functions",
        "i_mp_context_manager",
        "i_mp_sequential_fallback",
    ],
    "2.1",
    "2.1_Code_Quality_Expectations",
    "Ideal Response",
)
assign(
    [
        "i_no_keyword_only_args",
        "i_no_future_import",
        "i_no_redundant_memoization",
        "i_clear_variable_names",
        "i_no_nested_helpers",
        "i_stdlib_only",
    ],
    "2.2",
    "2.2_Common_Errors_to_Avoid",
    "Ideal Response",
)
assign(["i_executes_without_error", "i_passes_internal_tests"], "2.3", "2.3_Verification_Checklist", "Ideal Response")
assign(["t_single_call_per_test", "t_public_test1_matches_prompt_example"], "3.1", "3.1_Structure_and_Purpose", "Test Cases")
assign(
    ["t_min_5_public", "t_min_10_private", "t_recommended_15_20_total", "t_deterministic", "t_entry_function_only"],
    "3.2",
    "3.2_Test_Requirements",
    "Test Cases",
)
assign(
    [
        "t_json_encoded",
        "t_string_fields",
        "t_input_json_object",
        "t_output_json_object",
        "t_json_escaping_valid",
        "t_optional_values_included",
        "t_no_python_literals",
        "t_no_nonstring_keys",
    ],
    "3.3",
    "3.3_JSON_Format_Compliance",
    "Test Cases",
)
assign(["t_exception_tests_aligned"], "3.3.1", "3.3.1_Exception_and_Error_Handling", "Test Cases")
assign(["t_not_large_or_redundant"], "3.4", "3.4_Common_Test_Mistakes", "Test Cases")
assign(["v_coverage_confidence", "v_cross_verified_dry_run"], "4", "4_Final_Validation_Workflow", "Test Cases")
assign(["v_prompt_test_solution_aligned", "v_entry_name_consistent", "v_signature_arity_consistent", "v_output_schema_aligned"], "6.1", "6.1_Model_Breaking_Definition", "Test Cases")
assign(["v_model_breaking_prompt_defined_only", "v_no_extra_parameters", "v_no_unmentioned_internal_logic"], "6.2", "6.2_Invalid_Model_Breaking", "Test Cases")
assign(["v_prompt_edge_cases_tested", "v_prompt_constraints_tested"], "6.3", "6.3_Valid_Model_Breaking", "Test Cases")
assign(["s_necessary_imports", "s_only_entry_signature", "s_no_classes", "s_no_helpers", "s_no_logic"], "7", "7_Starter_Code", "Prompt")


DETAILED_KEYS = [key for key in DISPLAY_ORDER if key not in DROP_REQUIREMENTS]


@dataclass(frozen=True)
class ColumnSpec:
    key: str
    display_name: str
    section_number: str
    subsection_name: str
    category: str
    star_level: int
    guideline_anchor: str


GUIDELINE_ANCHORS = {
    "1.1": "Prompts should define a clear contract: what the task is, what comes in, what comes out, and what constraints or edge conditions matter.",
    "1.2": "Prompts should describe practical, realistic, well-scoped algorithmic work rather than vague or inflated scenarios.",
    "1.3": "Prompt signatures should stay JSON-compatible so the task can be exercised and validated mechanically.",
    "2.1": "Ideal responses should be clean, deterministic, and structured without unnecessary complexity or hidden state.",
    "2.2": "Ideal responses should avoid common coding patterns that make solutions brittle, confusing, or evaluator-specific.",
    "2.3": "Ideal responses should actually run and succeed on the supplied tests.",
    "3.1": "Each test should have a clear purpose and correspond cleanly to the intended sample behavior.",
    "3.2": "Test suites should be large enough, deterministic, and focused on the defined entry function.",
    "3.3": "Test inputs and outputs should follow the required JSON-string format consistently.",
    "3.3.1": "Error-handling tests are only valid when they enforce behavior the prompt actually defines.",
    "3.4": "Test suites should avoid unnecessary redundancy or bloat.",
    "4": "Validation should include concrete dry-run evidence rather than only manual inspection.",
    "6.1": "A valid model breaker only tests behavior that is truly defined and aligned across prompt, tests, and solution.",
    "6.2": "Hidden rules, extra parameters, or unprompted implementation assumptions make a sample invalid as a model breaker.",
    "6.3": "If the prompt names constraints or edge cases, the tests should meaningfully exercise them.",
    "7": "Starter code should stay minimal and should not leak implementation logic.",
}


STAR_LEVELS = {
    "p_structured_layout": 1,
    "p_realistic_context": 2,
    "p_practical_algorithmic_problem": 2,
    "p_input_format_explicit": 1,
    "p_output_format_explicit": 1,
    "p_constraints_defined": 1,
    "p_computational_limits_defined": 1,
    "p_edge_cases_defined": 1,
    "p_return_conditions_defined": 1,
    "p_function_signature_present": 0,
    "p_json_compatible_signature": 0,
    "p_no_external_libs_stated": 0,
    "p_metadata_alignment": 1,
    "p_not_verbose": 2,
    "p_measurable_objective": 1,
    "p_difficulty_balanced": 1,
    "p_example_present": 1,
    "p_no_unrealistic_constraints": 2,
    "p_not_vague": 2,
    "p_no_conflicting_objectives": 2,
    "p_no_buzzwords": 2,
    "p_no_time_window_constraints": 0,
    "p_no_random_requirement": 0,
    "s_necessary_imports": 0,
    "s_only_entry_signature": 0,
    "s_no_classes": 0,
    "s_no_helpers": 0,
    "s_no_logic": 0,
    "i_no_globals": 0,
    "i_state_encapsulated": 1,
    "i_consistent_naming_docs": 1,
    "i_no_arbitrary_limits": 1,
    "i_single_entry_aligned": 0,
    "i_helpers_for_repeated_logic": 1,
    "i_no_sample_io_in_main": 0,
    "i_no_parallelism": 0,
    "i_deterministic_solution": 0,
    "i_mp_module_level_functions": 0,
    "i_mp_context_manager": 0,
    "i_mp_sequential_fallback": 0,
    "i_no_keyword_only_args": 0,
    "i_no_future_import": 0,
    "i_no_redundant_memoization": 1,
    "i_clear_variable_names": 1,
    "i_no_nested_helpers": 1,
    "i_stdlib_only": 0,
    "i_executes_without_error": 0,
    "i_passes_internal_tests": 0,
    "t_single_call_per_test": 1,
    "t_public_test1_matches_prompt_example": 1,
    "t_min_5_public": 0,
    "t_min_10_private": 0,
    "t_recommended_15_20_total": 0,
    "t_deterministic": 1,
    "t_entry_function_only": 1,
    "t_json_encoded": 0,
    "t_string_fields": 0,
    "t_input_json_object": 0,
    "t_output_json_object": 0,
    "t_json_escaping_valid": 0,
    "t_optional_values_included": 0,
    "t_no_python_literals": 0,
    "t_no_nonstring_keys": 0,
    "t_exception_tests_aligned": 1,
    "t_not_large_or_redundant": 1,
    "v_coverage_confidence": 1,
    "v_cross_verified_dry_run": 0,
    "v_prompt_test_solution_aligned": 2,
    "v_entry_name_consistent": 0,
    "v_signature_arity_consistent": 1,
    "v_output_schema_aligned": 1,
    "v_model_breaking_prompt_defined_only": 2,
    "v_no_extra_parameters": 0,
    "v_no_unmentioned_internal_logic": 2,
    "v_prompt_edge_cases_tested": 1,
    "v_prompt_constraints_tested": 1,
}


def display_name(key: str) -> str:
    code, _, _ = SECTION_MAP[key]
    return f"{code}_{key.split('_', 1)[1]}"


def section_folder_name(section_number: str) -> str:
    return f"Section {section_number.split('.', 1)[0]}"


def section_sort_key(label: str) -> tuple[int, ...]:
    code = label.split("_", 1)[0]
    return tuple(int(part) for part in code.split("."))


def subsection_order() -> list[str]:
    seen: list[str] = []
    for key in DETAILED_KEYS:
        subsection = SECTION_MAP[key][1]
        if subsection not in seen:
            seen.append(subsection)
    return sorted(seen, key=section_sort_key)


def build_column_specs() -> list[ColumnSpec]:
    specs: list[ColumnSpec] = []
    for key in DETAILED_KEYS:
        section_number, subsection_name, category = SECTION_MAP[key]
        specs.append(
            ColumnSpec(
                key=key,
                display_name=display_name(key),
                section_number=section_number,
                subsection_name=subsection_name,
                category=category,
                star_level=STAR_LEVELS.get(key, 0),
                guideline_anchor=GUIDELINE_ANCHORS[section_number],
            )
        )
    return specs


SECTION_NUMBERS = sorted({SECTION_MAP[key][0].split(".", 1)[0] for key in DETAILED_KEYS}, key=int)
SECTION_TO_KEYS: dict[str, list[str]] = {}
for key in DETAILED_KEYS:
    top = SECTION_MAP[key][0].split(".", 1)[0]
    SECTION_TO_KEYS.setdefault(top, []).append(key)
