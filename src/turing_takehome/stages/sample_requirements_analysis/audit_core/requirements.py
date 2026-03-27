from __future__ import annotations

from dataclasses import dataclass


PASS = "PASS"
PARTIAL = "PARTIAL"
FAIL = "FAIL"
UNCLEAR = "UNCLEAR"
NA = "NA"
ALLOWED_VERDICTS = {PASS, PARTIAL, FAIL, UNCLEAR, NA}


@dataclass(frozen=True)
class Requirement:
    key: str
    label: str
    section: str
    values: tuple[str, ...]
    description: str


@dataclass
class EvaluationOutcome:
    verdict: str
    notes: list[str]


REQUIREMENTS: list[Requirement] = [
    Requirement("p_structured_layout", "Prompt structured layout", "Prompt", (PASS, PARTIAL, FAIL, UNCLEAR), "Prompt uses a clean structured layout with sections for objectives, constraints, and expected outputs."),
    Requirement("p_realistic_context", "Prompt realistic context", "Prompt", (PASS, PARTIAL, FAIL, UNCLEAR), "Prompt uses a real-world or realistic problem context."),
    Requirement("p_practical_algorithmic_problem", "Prompt practical algorithmic problem", "Prompt", (PASS, PARTIAL, FAIL, UNCLEAR), "Prompt reflects a practical, algorithmically solvable problem."),
    Requirement("p_input_format_explicit", "Prompt explicit input format", "Prompt", (PASS, PARTIAL, FAIL, UNCLEAR), "Prompt explicitly describes the input format."),
    Requirement("p_output_format_explicit", "Prompt explicit output format", "Prompt", (PASS, PARTIAL, FAIL, UNCLEAR), "Prompt explicitly describes the output format."),
    Requirement("p_constraints_defined", "Prompt constraints defined", "Prompt", (PASS, PARTIAL, FAIL, UNCLEAR), "Prompt defines constraints."),
    Requirement("p_computational_limits_defined", "Prompt computational limits defined", "Prompt", (PASS, PARTIAL, FAIL, UNCLEAR), "Prompt defines expected computational limits when applicable."),
    Requirement("p_edge_cases_defined", "Prompt edge-case handling defined", "Prompt", (PASS, PARTIAL, FAIL, UNCLEAR), "Prompt defines edge-case handling."),
    Requirement("p_return_conditions_defined", "Prompt return conditions defined", "Prompt", (PASS, PARTIAL, FAIL, UNCLEAR), "Prompt defines return conditions or error-return behavior."),
    Requirement("p_function_signature_present", "Prompt function signature present", "Prompt", (PASS, FAIL, UNCLEAR), "Prompt contains a concrete, testable function signature."),
    Requirement("p_json_compatible_signature", "Prompt JSON-compatible signature", "Prompt", (PASS, PARTIAL, FAIL, UNCLEAR), "Prompt function signature uses JSON-compatible types only; no tuples, sets, or non-string dict keys."),
    Requirement("p_no_external_libs_stated", "Prompt bans external libs", "Prompt", (PASS, PARTIAL, FAIL, UNCLEAR), "Prompt states that only Python standard library is allowed or no external libraries."),
    Requirement("p_metadata_alignment", "Prompt aligned with metadata", "Prompt", (PASS, PARTIAL, FAIL, UNCLEAR), "Problem aligns with task metadata such as function name and topic."),
    Requirement("p_not_verbose", "Prompt not unnecessarily verbose", "Prompt", (PASS, PARTIAL, FAIL, UNCLEAR), "Prompt avoids unnecessary verbosity."),
    Requirement("p_measurable_objective", "Prompt measurable objective", "Prompt", (PASS, PARTIAL, FAIL, UNCLEAR), "Prompt has well-defined measurable objectives."),
    Requirement("p_difficulty_balanced", "Prompt difficulty or constraints balanced", "Prompt", (PASS, PARTIAL, FAIL, UNCLEAR), "Prompt constraints align with intended difficulty."),
    Requirement("p_example_present", "Prompt includes example I/O", "Prompt", (PASS, PARTIAL, FAIL, UNCLEAR), "Prompt includes at least one concrete sample input or output example."),
    Requirement("p_no_unrealistic_constraints", "Prompt no unrealistic constraints", "Prompt", (PASS, PARTIAL, FAIL, UNCLEAR), "Prompt avoids unrealistic or untestable requirements."),
    Requirement("p_not_vague", "Prompt not vague", "Prompt", (PASS, PARTIAL, FAIL, UNCLEAR), "Prompt avoids vague problem definitions."),
    Requirement("p_no_conflicting_objectives", "Prompt no conflicting objectives", "Prompt", (PASS, PARTIAL, FAIL, UNCLEAR), "Prompt avoids conflicting or undefined optimization objectives."),
    Requirement("p_no_buzzwords", "Prompt no irrelevant buzzwords", "Prompt", (PASS, PARTIAL, FAIL, UNCLEAR), "Prompt avoids buzzwords without algorithmic relevance."),
    Requirement("p_no_time_window_constraints", "Prompt no time-window constraints", "Prompt", (PASS, FAIL, UNCLEAR), "Prompt avoids time-window constraints."),
    Requirement("p_no_random_requirement", "Prompt no randomness requirement", "Prompt", (PASS, FAIL, UNCLEAR), "Prompt does not require or rely on randomness."),
    Requirement("s_necessary_imports", "Starter has necessary imports", "Starter", (PASS, PARTIAL, FAIL, UNCLEAR), "Starter code includes necessary import statements for referenced typing or library symbols."),
    Requirement("s_only_entry_signature", "Starter only entry-point signature", "Starter", (PASS, PARTIAL, FAIL, UNCLEAR), "Starter code contains only the main entry-point function signature."),
    Requirement("s_no_classes", "Starter has no classes", "Starter", (PASS, FAIL, UNCLEAR), "Starter code contains no class definitions."),
    Requirement("s_no_helpers", "Starter has no helper functions", "Starter", (PASS, FAIL, UNCLEAR), "Starter code contains no helper function definitions beyond the entry point."),
    Requirement("s_no_logic", "Starter has no implementation logic", "Starter", (PASS, PARTIAL, FAIL, UNCLEAR), "Starter code contains no implementation logic beyond an empty body placeholder."),
    Requirement("i_no_globals", "Ideal response no globals or shared mutable state", "Ideal response", (PASS, PARTIAL, FAIL, UNCLEAR), "Ideal response avoids global variables and mutable shared state."),
    Requirement("i_state_encapsulated", "Ideal response state encapsulated", "Ideal response", (PASS, PARTIAL, FAIL, UNCLEAR), "State and logic are encapsulated within classes or local scope."),
    Requirement("i_consistent_naming_docs", "Ideal response consistent naming and docs", "Ideal response", (PASS, PARTIAL, FAIL, UNCLEAR), "Ideal response follows consistent naming and documentation style."),
    Requirement("i_no_arbitrary_limits", "Ideal response no arbitrary depth or iteration limits", "Ideal response", (PASS, PARTIAL, FAIL, UNCLEAR), "Ideal response avoids hardcoded arbitrary depth or iteration limits unless prompt-specified."),
    Requirement("i_single_entry_aligned", "Ideal response single entry aligned", "Ideal response", (PASS, PARTIAL, FAIL, UNCLEAR), "Ideal response exposes a single entry point aligned with the prompt signature."),
    Requirement("i_helpers_for_repeated_logic", "Ideal response uses helpers for repeated logic", "Ideal response", (PASS, PARTIAL, FAIL, UNCLEAR), "Ideal response uses helper abstractions for repeated logic where appropriate."),
    Requirement("i_no_sample_io_in_main", "Ideal response no sample I/O in main block", "Ideal response", (PASS, FAIL, UNCLEAR), "Ideal response does not embed sample input or output in a main block."),
    Requirement("i_no_parallelism", "Ideal response no parallelism or threading", "Ideal response", (PASS, FAIL, UNCLEAR), "Ideal response avoids multiprocessing, threading, or concurrent execution."),
    Requirement("i_deterministic_solution", "Ideal response deterministic", "Ideal response", (PASS, FAIL, UNCLEAR), "Ideal response avoids random or time-based nondeterministic behavior."),
    Requirement("i_mp_module_level_functions", "If multiprocessing, functions are module-level", "Ideal response", (PASS, FAIL, UNCLEAR, NA), "If multiprocessing is used, worker functions must be defined at module level."),
    Requirement("i_mp_context_manager", "If multiprocessing, uses context manager", "Ideal response", (PASS, FAIL, UNCLEAR, NA), "If multiprocessing is used, pools are managed with a context manager."),
    Requirement("i_mp_sequential_fallback", "If multiprocessing, has sequential fallback", "Ideal response", (PASS, FAIL, UNCLEAR, NA), "If multiprocessing is used, a sequential fallback is provided."),
    Requirement("i_no_keyword_only_args", "Ideal response no keyword-only args", "Ideal response", (PASS, FAIL, UNCLEAR), "Ideal response avoids keyword-only arguments."),
    Requirement("i_no_future_import", "Ideal response no __future__ import", "Ideal response", (PASS, FAIL, UNCLEAR), "Ideal response does not import __future__."),
    Requirement("i_no_redundant_memoization", "Ideal response no redundant memoization", "Ideal response", (PASS, PARTIAL, FAIL, UNCLEAR), "Ideal response avoids redundant memoization logic spread across functions."),
    Requirement("i_clear_variable_names", "Ideal response clear variable names", "Ideal response", (PASS, PARTIAL, FAIL, UNCLEAR), "Ideal response uses clear variable names."),
    Requirement("i_no_nested_helpers", "Ideal response no unscoped nested helpers", "Ideal response", (PASS, PARTIAL, FAIL, UNCLEAR), "Ideal response avoids unscoped helper methods or nested function definitions."),
    Requirement("i_stdlib_only", "Ideal response stdlib only", "Ideal response", (PASS, FAIL, UNCLEAR), "Ideal response uses only the Python standard library."),
    Requirement("i_executes_without_error", "Ideal response executes", "Ideal response", (PASS, PARTIAL, FAIL, UNCLEAR), "Ideal response can be executed and the entry function can be resolved."),
    Requirement("i_passes_internal_tests", "Ideal response passes tests", "Ideal response", (PASS, PARTIAL, FAIL, UNCLEAR), "Ideal response passes the provided internal sample tests."),
    Requirement("t_min_5_public", "At least 5 public tests", "Tests", (PASS, FAIL, UNCLEAR), "Sample has at least 5 public tests."),
    Requirement("t_min_10_private", "At least 10 private tests", "Tests", (PASS, FAIL, UNCLEAR), "Sample has at least 10 private tests."),
    Requirement("t_recommended_15_20_total", "Recommended 15-20 total tests", "Tests", (PASS, PARTIAL, FAIL, UNCLEAR), "Sample has approximately 15 to 20 total tests."),
    Requirement("t_single_call_per_test", "Each test maps to one call", "Tests", (PASS, PARTIAL, FAIL, UNCLEAR), "Each test corresponds to exactly one call of the entry function."),
    Requirement("t_deterministic", "Tests deterministic", "Tests", (PASS, PARTIAL, FAIL, UNCLEAR), "Tests are deterministic and do not rely on randomness or time-based behavior."),
    Requirement("t_entry_function_only", "Tests target entry function only", "Tests", (PASS, PARTIAL, FAIL, UNCLEAR), "Tests target only the prompt-defined entry-point function."),
    Requirement("t_json_encoded", "Tests valid JSON container format", "Tests", (PASS, FAIL, UNCLEAR), "Public and private test collections are valid JSON and each case has input, output, and testtype fields."),
    Requirement("t_string_fields", "Tests use string fields", "Tests", (PASS, FAIL, UNCLEAR), "Each test case uses string-valued input, output, and testtype fields, not nested objects."),
    Requirement("t_input_json_object", "Test inputs are stringified JSON objects", "Tests", (PASS, PARTIAL, FAIL, UNCLEAR), "Each test input is a stringified JSON object."),
    Requirement("t_output_json_object", "Test outputs are stringified JSON objects", "Tests", (PASS, PARTIAL, FAIL, UNCLEAR), "Each test output is a stringified JSON object."),
    Requirement("t_json_escaping_valid", "Tests have valid JSON escaping", "Tests", (PASS, PARTIAL, FAIL, UNCLEAR), "Test I/O strings use valid escaping, braces, and double-quoted JSON when object-formatted."),
    Requirement("t_optional_values_included", "Optional values included in tests", "Tests", (PASS, PARTIAL, FAIL, UNCLEAR, NA), "If the entry point has optional or default parameters, tests still provide all input values."),
    Requirement("t_no_python_literals", "Tests avoid Python literals in JSON", "Tests", (PASS, FAIL, UNCLEAR), "Tests avoid Python literals such as True, False, None, or single-quoted pseudo-JSON."),
    Requirement("t_no_nonstring_keys", "Tests avoid non-string JSON keys", "Tests", (PASS, FAIL, UNCLEAR), "Tests avoid non-string JSON object keys."),
    Requirement("t_exception_tests_aligned", "Exception or error tests aligned", "Tests", (PASS, PARTIAL, FAIL, UNCLEAR, NA), "Exception or error-handling tests are aligned with prompt-described behavior."),
    Requirement("t_not_large_or_redundant", "Tests not overly large or redundant", "Tests", (PASS, PARTIAL, FAIL, UNCLEAR), "Test set is not overly large or redundant."),
    Requirement("t_public_test1_matches_prompt_example", "Public test 1 matches prompt example", "Tests", (PASS, PARTIAL, FAIL, UNCLEAR, NA), "If the prompt includes sample I/O, public test case 1 should correspond to it."),
    Requirement("v_prompt_test_solution_aligned", "Prompt, test, solution aligned", "Validation", (PASS, PARTIAL, FAIL, UNCLEAR), "Prompt, tests, and ideal solution are mutually aligned."),
    Requirement("v_entry_name_consistent", "Entry name consistent across artifacts", "Validation", (PASS, PARTIAL, FAIL, UNCLEAR), "Prompt, metadata, starter code, and ideal response use the same entry-point name."),
    Requirement("v_signature_arity_consistent", "Signature arity consistent", "Validation", (PASS, PARTIAL, FAIL, UNCLEAR), "Prompt or starter signature arity is consistent with test invocation arity."),
    Requirement("v_output_schema_aligned", "Output schema aligned with prompt", "Validation", (PASS, PARTIAL, FAIL, UNCLEAR), "Output keys returned or tested are described in the prompt."),
    Requirement("v_model_breaking_prompt_defined_only", "Model breaking only on prompt-defined constraints", "Validation", (PASS, PARTIAL, FAIL, UNCLEAR), "Tests only break the model on prompt-defined behavior."),
    Requirement("v_no_extra_parameters", "Tests add no extra parameters", "Validation", (PASS, FAIL, UNCLEAR), "Tests do not add extra parameters beyond the prompt signature."),
    Requirement("v_no_unmentioned_internal_logic", "Tests avoid unmentioned internal logic", "Validation", (PASS, PARTIAL, FAIL, UNCLEAR), "Tests do not depend on unprompted internal implementation details."),
    Requirement("v_prompt_edge_cases_tested", "Prompt-defined edge cases tested", "Validation", (PASS, PARTIAL, FAIL, UNCLEAR, NA), "Explicitly prompt-defined edge cases are covered by tests."),
    Requirement("v_prompt_constraints_tested", "Prompt-defined constraints tested", "Validation", (PASS, PARTIAL, FAIL, UNCLEAR, NA), "Prompt-defined constraints are exercised by tests."),
    Requirement("v_coverage_confidence", "Coverage confidence >=80%", "Validation", (PASS, PARTIAL, FAIL, UNCLEAR), "Combined prompt and tests suggest at least about 80 percent functional coverage."),
    Requirement("v_cross_verified_dry_run", "Cross-verification dry run", "Validation", (PASS, PARTIAL, FAIL, UNCLEAR), "Ideal response can be dry-run against tests without issues."),
]
