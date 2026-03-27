from __future__ import annotations

import argparse
import ast
import csv
import json
import re
import sys
import traceback
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from textwrap import shorten
from typing import Any

SRC_DIR = Path(__file__).resolve().parents[5]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from turing_takehome.llm import get_stage_model_label, request_json, resolve_model_name


EVALUATOR_VERSION = "v3"
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
    Requirement("p_no_external_libs_stated", "Prompt bans external libs", "Prompt", (PASS, PARTIAL, FAIL, UNCLEAR), "Prompt states that only Python standard library is allowed / no external libraries."),
    Requirement("p_metadata_alignment", "Prompt aligned with metadata", "Prompt", (PASS, PARTIAL, FAIL, UNCLEAR), "Problem aligns with task metadata such as function name and topic."),
    Requirement("p_not_verbose", "Prompt not unnecessarily verbose", "Prompt", (PASS, PARTIAL, FAIL, UNCLEAR), "Prompt avoids unnecessary verbosity."),
    Requirement("p_measurable_objective", "Prompt measurable objective", "Prompt", (PASS, PARTIAL, FAIL, UNCLEAR), "Prompt has well-defined measurable objectives."),
    Requirement("p_difficulty_balanced", "Prompt difficulty/constraints balanced", "Prompt", (PASS, PARTIAL, FAIL, UNCLEAR), "Prompt constraints align with intended difficulty."),
    Requirement("p_example_present", "Prompt includes example I/O", "Prompt", (PASS, PARTIAL, FAIL, UNCLEAR), "Prompt includes at least one concrete sample input/output example."),
    Requirement("p_no_unrealistic_constraints", "Prompt no unrealistic constraints", "Prompt", (PASS, PARTIAL, FAIL, UNCLEAR), "Prompt avoids unrealistic or untestable requirements."),
    Requirement("p_not_vague", "Prompt not vague", "Prompt", (PASS, PARTIAL, FAIL, UNCLEAR), "Prompt avoids vague problem definitions."),
    Requirement("p_no_conflicting_objectives", "Prompt no conflicting objectives", "Prompt", (PASS, PARTIAL, FAIL, UNCLEAR), "Prompt avoids conflicting or undefined optimization objectives."),
    Requirement("p_no_buzzwords", "Prompt no irrelevant buzzwords", "Prompt", (PASS, PARTIAL, FAIL, UNCLEAR), "Prompt avoids buzzwords without algorithmic relevance."),
    Requirement("p_no_time_window_constraints", "Prompt no time-window constraints", "Prompt", (PASS, FAIL, UNCLEAR), "Prompt avoids time-window constraints."),
    Requirement("p_no_random_requirement", "Prompt no randomness requirement", "Prompt", (PASS, FAIL, UNCLEAR), "Prompt does not require or rely on randomness."),
    Requirement("s_necessary_imports", "Starter has necessary imports", "Starter", (PASS, PARTIAL, FAIL, UNCLEAR), "Starter code includes necessary import statements for referenced typing / library symbols."),
    Requirement("s_in_markdown", "Starter in markdown", "Starter", (PASS, FAIL, UNCLEAR), "Starter code is presented in markdown/code fences."),
    Requirement("s_only_entry_signature", "Starter only entry-point signature", "Starter", (PASS, PARTIAL, FAIL, UNCLEAR), "Starter code contains only the main entry-point function signature."),
    Requirement("s_no_classes", "Starter has no classes", "Starter", (PASS, FAIL, UNCLEAR), "Starter code contains no class definitions."),
    Requirement("s_no_helpers", "Starter has no helper functions", "Starter", (PASS, FAIL, UNCLEAR), "Starter code contains no helper function definitions beyond the entry point."),
    Requirement("s_no_logic", "Starter has no implementation logic", "Starter", (PASS, PARTIAL, FAIL, UNCLEAR), "Starter code contains no implementation logic beyond an empty body placeholder."),
    Requirement("i_no_globals", "Ideal response no globals/shared mutable state", "Ideal response", (PASS, PARTIAL, FAIL, UNCLEAR), "Ideal response avoids global variables and mutable shared state."),
    Requirement("i_state_encapsulated", "Ideal response state encapsulated", "Ideal response", (PASS, PARTIAL, FAIL, UNCLEAR), "State and logic are encapsulated within classes or local scope."),
    Requirement("i_structured_classes_or_functions", "Ideal response well-structured", "Ideal response", (PASS, PARTIAL, FAIL, UNCLEAR), "Ideal response uses well-structured classes or functions."),
    Requirement("i_consistent_naming_docs", "Ideal response consistent naming/docs", "Ideal response", (PASS, PARTIAL, FAIL, UNCLEAR), "Ideal response follows consistent naming and documentation style."),
    Requirement("i_no_arbitrary_limits", "Ideal response no arbitrary depth/iteration limits", "Ideal response", (PASS, PARTIAL, FAIL, UNCLEAR), "Ideal response avoids hardcoded arbitrary depth or iteration limits unless prompt-specified."),
    Requirement("i_single_entry_aligned", "Ideal response single entry aligned", "Ideal response", (PASS, PARTIAL, FAIL, UNCLEAR), "Ideal response exposes a single entry point aligned with the prompt signature."),
    Requirement("i_helpers_for_repeated_logic", "Ideal response uses helpers for repeated logic", "Ideal response", (PASS, PARTIAL, FAIL, UNCLEAR), "Ideal response uses helper abstractions for repeated logic where appropriate."),
    Requirement("i_no_sample_io_in_main", "Ideal response no sample I/O in main block", "Ideal response", (PASS, FAIL, UNCLEAR), "Ideal response does not embed sample input/output in a main block."),
    Requirement("i_no_parallelism", "Ideal response no parallelism/threading", "Ideal response", (PASS, FAIL, UNCLEAR), "Ideal response avoids multiprocessing/threading/concurrent execution."),
    Requirement("i_deterministic_solution", "Ideal response deterministic", "Ideal response", (PASS, FAIL, UNCLEAR), "Ideal response avoids random/time-based nondeterministic behavior."),
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
    Requirement("i_consistent_structure", "Ideal response consistent structure", "Ideal response", (PASS, PARTIAL, FAIL, UNCLEAR), "Ideal response has a consistent overall structure and naming style."),
    Requirement("t_min_5_public", "At least 5 public tests", "Tests", (PASS, FAIL, UNCLEAR), "Sample has at least 5 public tests."),
    Requirement("t_min_10_private", "At least 10 private tests", "Tests", (PASS, FAIL, UNCLEAR), "Sample has at least 10 private tests."),
    Requirement("t_recommended_15_20_total", "Recommended 15-20 total tests", "Tests", (PASS, PARTIAL, FAIL, UNCLEAR), "Sample has approximately 15-20 total tests."),
    Requirement("t_single_call_per_test", "Each test maps to one call", "Tests", (PASS, PARTIAL, FAIL, UNCLEAR), "Each test corresponds to exactly one call of the entry function."),
    Requirement("t_deterministic", "Tests deterministic", "Tests", (PASS, PARTIAL, FAIL, UNCLEAR), "Tests are deterministic and do not rely on randomness or time-based behavior."),
    Requirement("t_entry_function_only", "Tests target entry function only", "Tests", (PASS, PARTIAL, FAIL, UNCLEAR), "Tests target only the prompt-defined entry-point function."),
    Requirement("t_json_encoded", "Tests valid JSON container format", "Tests", (PASS, FAIL, UNCLEAR), "Public/private test collections are valid JSON and each case has input/output/testtype fields."),
    Requirement("t_string_fields", "Tests use string fields", "Tests", (PASS, FAIL, UNCLEAR), "Each test case uses string-valued input/output/testtype fields, not nested objects."),
    Requirement("t_no_markdown_json_fence", "Tests avoid markdown JSON fences", "Tests", (PASS, FAIL, UNCLEAR), "Tests avoid markdown code fences such as ```JSON in JSON payloads."),
    Requirement("t_input_json_object", "Test inputs are stringified JSON objects", "Tests", (PASS, PARTIAL, FAIL, UNCLEAR), "Each test input is a stringified JSON object."),
    Requirement("t_output_json_object", "Test outputs are stringified JSON objects", "Tests", (PASS, PARTIAL, FAIL, UNCLEAR), "Each test output is a stringified JSON object."),
    Requirement("t_json_escaping_valid", "Tests have valid JSON escaping", "Tests", (PASS, PARTIAL, FAIL, UNCLEAR), "Test I/O strings use valid escaping, braces, and double-quoted JSON when object-formatted."),
    Requirement("t_optional_values_included", "Optional values included in tests", "Tests", (PASS, PARTIAL, FAIL, UNCLEAR, NA), "If the entry point has optional/default parameters, tests still provide all input values."),
    Requirement("t_no_python_literals", "Tests avoid Python literals in JSON", "Tests", (PASS, FAIL, UNCLEAR), "Tests avoid Python literals such as True/False/None or single-quoted pseudo-JSON."),
    Requirement("t_no_nonstring_keys", "Tests avoid non-string JSON keys", "Tests", (PASS, FAIL, UNCLEAR), "Tests avoid non-string JSON object keys."),
    Requirement("t_one_to_one_json_cases", "One-to-one JSON test cases", "Tests", (PASS, PARTIAL, FAIL, UNCLEAR), "Each test corresponds 1:1 to a JSON test case."),
    Requirement("t_exact_output_check", "Tests allow exact output matching", "Tests", (PASS, PARTIAL, FAIL, UNCLEAR), "Tests specify exact outputs rather than fuzzy assertions."),
    Requirement("t_exception_tests_aligned", "Exception/error tests aligned", "Tests", (PASS, PARTIAL, FAIL, UNCLEAR, NA), "Exception/error-handling tests are aligned with prompt-described behavior."),
    Requirement("t_not_large_or_redundant", "Tests not overly large/redundant", "Tests", (PASS, PARTIAL, FAIL, UNCLEAR), "Test set is not overly large or redundant."),
    Requirement("t_public_test1_matches_prompt_example", "Public test 1 matches prompt example", "Tests", (PASS, PARTIAL, FAIL, UNCLEAR, NA), "If the prompt includes sample I/O, public test case 1 should correspond to it."),
    Requirement("v_prompt_test_solution_aligned", "Prompt/test/solution aligned", "Validation", (PASS, PARTIAL, FAIL, UNCLEAR), "Prompt, tests, and ideal solution are mutually aligned."),
    Requirement("v_entry_name_consistent", "Entry name consistent across artifacts", "Validation", (PASS, PARTIAL, FAIL, UNCLEAR), "Prompt, metadata, starter code, and ideal response use the same entry-point name."),
    Requirement("v_signature_arity_consistent", "Signature arity consistent", "Validation", (PASS, PARTIAL, FAIL, UNCLEAR), "Prompt/starter signature arity is consistent with test invocation arity."),
    Requirement("v_output_schema_aligned", "Output schema aligned with prompt", "Validation", (PASS, PARTIAL, FAIL, UNCLEAR), "Output keys returned or tested are described in the prompt."),
    Requirement("v_model_breaking_prompt_defined_only", "Model breaking only on prompt-defined constraints", "Validation", (PASS, PARTIAL, FAIL, UNCLEAR), "Tests only break the model on prompt-defined behavior."),
    Requirement("v_no_extra_parameters", "Tests add no extra parameters", "Validation", (PASS, FAIL, UNCLEAR), "Tests do not add extra parameters beyond the prompt signature."),
    Requirement("v_no_unmentioned_internal_logic", "Tests avoid unmentioned internal logic", "Validation", (PASS, PARTIAL, FAIL, UNCLEAR), "Tests do not depend on unprompted internal implementation details."),
    Requirement("v_prompt_edge_cases_tested", "Prompt-defined edge cases tested", "Validation", (PASS, PARTIAL, FAIL, UNCLEAR, NA), "Explicitly prompt-defined edge cases are covered by tests."),
    Requirement("v_prompt_constraints_tested", "Prompt-defined constraints tested", "Validation", (PASS, PARTIAL, FAIL, UNCLEAR, NA), "Prompt-defined constraints are exercised by tests."),
    Requirement("v_coverage_confidence", "Coverage confidence >=80%", "Validation", (PASS, PARTIAL, FAIL, UNCLEAR), "Combined prompt/tests suggest at least ~80% functional coverage."),
    Requirement("v_cross_verified_dry_run", "Cross-verification dry run", "Validation", (PASS, PARTIAL, FAIL, UNCLEAR), "Ideal response can be dry-run against tests without issues."),
]


def strip_code_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z0-9_+-]*\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def verdict_from_ratio(ratio: float, pass_at: float = 1.0, partial_at: float = 0.5) -> str:
    if ratio >= pass_at:
        return PASS
    if ratio >= partial_at:
        return PARTIAL
    return FAIL


def parse_signature_info(code: str) -> dict[str, Any]:
    code = strip_code_fences(code)
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return {"func_defs": [], "class_defs": [], "kwonly": 0, "defaulted_args": 0, "total_args": 0}
    func_defs = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    class_defs = [node for node in tree.body if isinstance(node, ast.ClassDef)]
    if func_defs:
        fn = func_defs[0]
        kwonly = len(fn.args.kwonlyargs)
        total_args = len(fn.args.args) + len(fn.args.posonlyargs)
        defaulted_args = len(fn.args.defaults)
    else:
        kwonly = 0
        total_args = 0
        defaulted_args = 0
    return {
        "func_defs": func_defs,
        "class_defs": class_defs,
        "kwonly": kwonly,
        "defaulted_args": defaulted_args,
        "total_args": total_args,
    }


def annotation_contains_disallowed_type(node: ast.AST | None) -> bool:
    if node is None:
        return False
    if isinstance(node, ast.Name):
        return node.id in {"Tuple", "Set", "tuple", "set"}
    if isinstance(node, ast.Subscript):
        base = node.value
        if isinstance(base, ast.Name) and base.id in {"Tuple", "Set", "tuple", "set"}:
            return True
        if isinstance(base, ast.Name) and base.id in {"Dict", "dict"}:
            slice_node = node.slice
            values = slice_node.elts if isinstance(slice_node, ast.Tuple) else [slice_node]
            if values:
                key_node = values[0]
                if not (isinstance(key_node, ast.Name) and key_node.id == "str"):
                    return True
        return annotation_contains_disallowed_type(base) or annotation_contains_disallowed_type(node.slice)
    if isinstance(node, ast.Tuple):
        return any(annotation_contains_disallowed_type(elt) for elt in node.elts)
    if isinstance(node, ast.BinOp):
        return annotation_contains_disallowed_type(node.left) or annotation_contains_disallowed_type(node.right)
    if isinstance(node, ast.Attribute):
        return node.attr in {"Tuple", "Set", "tuple", "set"}
    return False


def signature_has_disallowed_types(code: str) -> bool:
    info = parse_signature_info(code)
    if not info["func_defs"]:
        return False
    fn = info["func_defs"][0]
    annotations = [arg.annotation for arg in fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs]
    annotations.append(fn.returns)
    return any(annotation_contains_disallowed_type(node) for node in annotations)


def extract_prompt_signature_block(text: str) -> str | None:
    code_blocks = re.findall(r"```(?:python)?\s*(.*?)```", text, flags=re.S | re.I)
    for block in code_blocks:
        if re.search(r"\bdef\s+\w+\s*\(", block):
            return block
    match = re.search(r"(def\s+\w+\s*\([^`]+)", text, re.S)
    if match:
        snippet = match.group(1)
        return snippet.split("\n\n")[0]
    return None


def extract_function_name_from_code(code: str) -> str | None:
    info = parse_signature_info(code)
    if info["func_defs"]:
        return info["func_defs"][0].name
    return None


def extract_output_keys_from_tests(tests: list[dict[str, Any]]) -> set[str]:
    keys: set[str] = set()
    for test in tests:
        raw = str(test.get("output", "")).strip()
        if not raw.startswith("{"):
            continue
        try:
            parsed = json.loads(raw)
        except Exception:  # noqa: BLE001
            continue
        if isinstance(parsed, dict):
            keys.update(str(key) for key in parsed.keys())
    return keys


def extract_prompt_error_literals(text: str) -> set[str]:
    return set(re.findall(r"'error'\s*:\s*'([^']+)'", text))


def parse_sample(row_text: str, index: int) -> dict[str, Any]:
    row = json.loads(row_text)
    return {
        "index": index,
        "row": row,
        "metadata": json.loads(row["metadata"]),
        "question_content": row["question_content"],
        "starter_code": row["starter_code"],
        "ideal_response": row["ideal_response"],
        "public_tests": json.loads(row["public_test_cases"]),
        "private_tests": json.loads(row["private_test_cases"]),
    }


def summarize_tests(public_tests: list[dict[str, Any]], private_tests: list[dict[str, Any]]) -> dict[str, Any]:
    all_tests = public_tests + private_tests
    input_first_chars = Counter()
    output_first_chars = Counter()
    py_literal_hits = 0
    non_object_inputs = 0
    non_object_outputs = 0
    for test in all_tests:
        inp = str(test.get("input", "")).lstrip()
        out = str(test.get("output", "")).lstrip()
        input_first_chars[inp[:1]] += 1
        output_first_chars[out[:1]] += 1
        if not inp.startswith("{"):
            non_object_inputs += 1
        if not out.startswith("{"):
            non_object_outputs += 1
        if re.search(r"\b(True|False|None)\b", inp) or re.search(r"\b(True|False|None)\b", out):
            py_literal_hits += 1
        if re.search(r"{\s*'|:\s*'|'[,\]}]", inp) or re.search(r"{\s*'|:\s*'|'[,\]}]", out):
            py_literal_hits += 1
    return {
        "total_tests": len(all_tests),
        "input_first_chars": dict(input_first_chars),
        "output_first_chars": dict(output_first_chars),
        "non_object_inputs": non_object_inputs,
        "non_object_outputs": non_object_outputs,
        "py_literal_hits": py_literal_hits,
    }


def runtime_eval(sample: dict[str, Any]) -> dict[str, Any]:
    import logging

    code = strip_code_fences(sample["ideal_response"])
    ns: dict[str, Any] = {"__name__": "__guideline_eval__"}
    results = {"executed": False, "passed": 0, "failed": 0, "total": 0, "errors": []}
    previous_disable = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        exec(code, ns, ns)
    except Exception as exc:  # noqa: BLE001
        results["errors"].append(f"ideal_response exec failed: {exc.__class__.__name__}: {exc}")
        logging.disable(previous_disable)
        return results
    func = ns.get(sample["metadata"].get("func_name"))
    if not callable(func):
        results["errors"].append(f"entry function '{sample['metadata'].get('func_name')}' not found after exec")
        logging.disable(previous_disable)
        return results
    results["callable_found"] = True
    for test in sample["public_tests"] + sample["private_tests"]:
        results["total"] += 1
        try:
            args = [json.loads(line) for line in str(test["input"]).splitlines() if line.strip()]
            expected = json.loads(test["output"])
            actual = func(*args)
            if isinstance(actual, str):
                stripped = actual.strip()
                if stripped[:1] in "{[\"tfn-0123456789":
                    try:
                        actual = json.loads(stripped)
                    except Exception:  # noqa: BLE001
                        pass
            if actual == expected:
                results["passed"] += 1
            else:
                results["failed"] += 1
                if len(results["errors"]) < 8:
                    results["errors"].append(
                        f"mismatch expected {shorten(repr(expected), width=100)} got {shorten(repr(actual), width=100)}"
                    )
        except Exception as exc:  # noqa: BLE001
            results["failed"] += 1
            if len(results["errors"]) < 8:
                results["errors"].append(f"test execution failed: {exc.__class__.__name__}: {exc}")
    results["executed"] = True
    logging.disable(previous_disable)
    return results


def pick_model() -> str | None:
    return resolve_model_name("sample-requirements-analysis")


def llm_semantic_eval(sample: dict[str, Any], enabled: bool, trace_dir: Path | None = None) -> dict[str, Any]:
    if not enabled:
        return {}
    model_id = pick_model()
    if not model_id:
        return {"_llm_error": "could not discover model"}
    llm_keys = [
        "p_realistic_context",
        "p_practical_algorithmic_problem",
        "p_metadata_alignment",
        "p_not_verbose",
        "p_measurable_objective",
        "p_difficulty_balanced",
        "p_no_unrealistic_constraints",
        "p_not_vague",
        "p_no_conflicting_objectives",
        "p_no_buzzwords",
        "i_no_globals",
        "i_state_encapsulated",
        "i_structured_classes_or_functions",
        "i_consistent_naming_docs",
        "i_no_arbitrary_limits",
        "i_helpers_for_repeated_logic",
        "i_no_redundant_memoization",
        "i_clear_variable_names",
        "i_no_nested_helpers",
        "i_consistent_structure",
        "t_exception_tests_aligned",
        "t_not_large_or_redundant",
        "v_prompt_test_solution_aligned",
        "v_model_breaking_prompt_defined_only",
        "v_no_unmentioned_internal_logic",
        "v_prompt_edge_cases_tested",
        "v_prompt_constraints_tested",
        "v_coverage_confidence",
        "t_public_test1_matches_prompt_example",
    ]
    prompt = {
        "task": "Grade this coding-dataset sample against the listed requirement keys. Return JSON only.",
        "allowed_verdicts": [PASS, PARTIAL, FAIL, UNCLEAR, NA],
        "keys": llm_keys,
        "sample": {
            "index": sample["index"],
            "metadata": sample["metadata"],
            "question_title": sample["row"]["question_title"],
            "difficulty": sample["row"]["difficulty"],
            "question_content": sample["question_content"][:18000],
            "starter_code": sample["starter_code"],
            "ideal_response": sample["ideal_response"][:22000],
            "public_tests_preview": sample["public_tests"][:2],
            "private_tests_preview": sample["private_tests"][:2],
            "test_summary": summarize_tests(sample["public_tests"], sample["private_tests"]),
        },
        "output_format": {"verdicts": {"key": "verdict"}, "notes": ["short fragment"]},
    }
    schema = {
        "type": "object",
        "properties": {
            "verdicts": {
                "type": "object",
                "properties": {key: {"type": "string", "enum": [PASS, PARTIAL, FAIL, UNCLEAR, NA]} for key in llm_keys},
                "required": llm_keys,
                "additionalProperties": False,
            },
            "notes": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": ["verdicts", "notes"],
        "additionalProperties": False,
    }
    try:
        parsed = request_json(
            "sample-requirements-analysis",
            f"guideline_audit_result_{sample['index']}",
            schema,
            json.dumps(prompt, ensure_ascii=False),
            trace_dir=trace_dir,
        )
    except Exception as exc:  # noqa: BLE001
        if trace_dir is not None:
            (trace_dir / f"{sample['index']}_error.txt").write_text(f"{exc.__class__.__name__}: {exc}", encoding="utf-8")
        return {"_llm_error": f"{exc.__class__.__name__}: {exc}"}
    verdicts = parsed.get("verdicts", {})
    clean: dict[str, Any] = {}
    for key, value in verdicts.items():
        if value in ALLOWED_VERDICTS:
            clean[key] = value
    if "notes" in parsed:
        clean["_llm_notes"] = parsed["notes"]
    return clean


def heuristics(sample: dict[str, Any], runtime: dict[str, Any]) -> tuple[dict[str, str], list[str]]:
    q = sample["question_content"]
    starter = sample["starter_code"]
    ideal = sample["ideal_response"]
    prompt_signature = extract_prompt_signature_block(q)
    prompt_signature_name = extract_function_name_from_code(prompt_signature or "")
    starter_name = extract_function_name_from_code(starter)
    ideal_name = extract_function_name_from_code(ideal)
    metadata = sample["metadata"]
    public_tests = sample["public_tests"]
    private_tests = sample["private_tests"]
    all_tests = public_tests + private_tests
    starter_clean = strip_code_fences(starter)
    ideal_clean = strip_code_fences(ideal)
    starter_sig = parse_signature_info(starter)
    ideal_sig = parse_signature_info(ideal)
    test_summary = summarize_tests(public_tests, private_tests)
    out: dict[str, str] = {}
    notes: list[str] = []

    def add_note(text: str) -> None:
        if text and text not in notes:
            notes.append(text)

    structured_hits = sum(1 for marker in ("Objective", "Constraints", "Input", "Output", "Function Signature") if marker.lower() in q.lower())
    out["p_structured_layout"] = PASS if structured_hits >= 3 else PARTIAL if structured_hits >= 1 else FAIL
    out["p_practical_algorithmic_problem"] = PARTIAL
    out["p_no_time_window_constraints"] = PASS
    out["p_no_random_requirement"] = PASS
    out["p_input_format_explicit"] = PASS if re.search(r"\bInput\b", q, re.I) else FAIL
    out["p_output_format_explicit"] = PASS if re.search(r"\bOutput\b", q, re.I) else FAIL
    out["p_constraints_defined"] = PASS if re.search(r"\bConstraint", q, re.I) else FAIL
    out["p_computational_limits_defined"] = PASS if re.search(r"O\(|time complexity|space complexity|[<>≤≥]=?\s*\d", q, re.I) else PARTIAL if re.search(r"\bConstraint", q, re.I) else FAIL
    out["p_edge_cases_defined"] = PASS if re.search(r"edge case|empty|invalid|error|return .* if|if .* return", q, re.I) else PARTIAL if re.search(r"error handling", q, re.I) else FAIL
    out["p_return_conditions_defined"] = PASS if re.search(r"return|returns", q, re.I) else FAIL
    out["p_function_signature_present"] = PASS if re.search(r"def\s+\w+\s*\(", q) else FAIL
    signature_source = prompt_signature or starter
    out["p_json_compatible_signature"] = FAIL if signature_has_disallowed_types(signature_source) else PASS
    out["p_no_external_libs_stated"] = PASS if re.search(r"no external libr|standard libr", q, re.I) else FAIL
    out["p_example_present"] = PASS if re.search(r"sample input|sample output|## Example|Example", q, re.I) else FAIL

    out["s_in_markdown"] = PASS if starter.strip().startswith("```") and starter.strip().endswith("```") else FAIL
    out["s_no_classes"] = PASS if not starter_sig["class_defs"] else FAIL
    out["s_no_helpers"] = PASS if len(starter_sig["func_defs"]) <= 1 else FAIL
    lines = [line.strip() for line in starter_clean.splitlines() if line.strip()]
    extra_lines = [line for line in lines if not (line.startswith("import ") or line.startswith("from ") or line.startswith("def ") or line in {"pass", "..."} or line.startswith('"""') or line.startswith("'''"))]
    out["s_only_entry_signature"] = PASS if len(starter_sig["func_defs"]) == 1 and not starter_sig["class_defs"] and not extra_lines else PARTIAL if len(starter_sig["func_defs"]) == 1 else FAIL
    out["s_no_logic"] = PASS if not extra_lines else FAIL
    if extra_lines:
        add_note("starter contains extra implementation/detail lines")

    import_names: set[str] = set()
    for match in re.finditer(r"^\s*from\s+[\w.]+\s+import\s+(.+)$", starter_clean, re.M):
        for piece in match.group(1).split(","):
            import_names.add(piece.strip().split(" as ")[0].strip())
    for match in re.finditer(r"^\s*import\s+(.+)$", starter_clean, re.M):
        for piece in match.group(1).split(","):
            import_names.add(piece.strip().split(" as ")[0].strip().split(".")[0])
    needed_names = set(re.findall(r"\b(List|Dict|Set|Tuple|Any|Optional|Union|defaultdict|heapq|math|cmath|gcd|json)\b", starter_clean))
    missing = sorted(name for name in needed_names if name not in import_names and name != "json")
    out["s_necessary_imports"] = PASS if not missing else PARTIAL
    if missing:
        add_note(f"starter may miss imports: {', '.join(missing[:4])}")

    out["i_no_keyword_only_args"] = PASS if ideal_sig["kwonly"] == 0 else FAIL
    out["i_no_future_import"] = FAIL if re.search(r"^\s*from\s+__future__\s+import", ideal_clean, re.M) else PASS
    out["i_no_sample_io_in_main"] = FAIL if re.search(r"if\s+__name__\s*==\s*['\"]__main__['\"]", ideal_clean) else PASS
    out["i_no_parallelism"] = FAIL if re.search(r"\b(threading|multiprocessing|ThreadPoolExecutor|ProcessPoolExecutor|concurrent\.futures)\b", ideal_clean) else PASS
    out["i_deterministic_solution"] = FAIL if re.search(r"\b(random|time\.time|datetime\.now|uuid)\b", ideal_clean, re.I) else PASS
    uses_mp = bool(re.search(r"\bmultiprocessing\b|Pool\s*\(", ideal_clean))
    out["i_mp_module_level_functions"] = NA
    out["i_mp_context_manager"] = NA
    out["i_mp_sequential_fallback"] = NA
    if uses_mp:
        out["i_mp_module_level_functions"] = FAIL if re.search(r"^\s{4,}def\s+\w+\s*\(", ideal_clean, re.M) else PASS
        out["i_mp_context_manager"] = PASS if re.search(r"with\s+multiprocessing\.Pool\s*\(", ideal_clean) or re.search(r"with\s+Pool\s*\(", ideal_clean) else FAIL
        out["i_mp_sequential_fallback"] = PASS if re.search(r"sequential|fallback|if\s+not\s+use_multiprocessing|else:\s*#?\s*sequential", ideal_clean, re.I) else FAIL
    out["i_no_nested_helpers"] = FAIL if re.search(r"^\s{4,}def\s+\w+\s*\(", ideal_clean, re.M) else PASS
    out["i_stdlib_only"] = FAIL if re.search(r"^\s*(?:from|import)\s+(numpy|pandas|scipy|sklearn|torch|tensorflow)\b", ideal_clean, re.M) else PASS
    out["i_single_entry_aligned"] = PASS if metadata.get("func_name") in ideal_clean else PARTIAL
    out["i_executes_without_error"] = PASS if runtime.get("callable_found") and runtime.get("executed") else FAIL
    out["i_passes_internal_tests"] = PASS if runtime.get("total", 0) and runtime["failed"] == 0 else PARTIAL if runtime.get("passed", 0) > 0 else FAIL
    out["i_clear_variable_names"] = PASS
    out["i_consistent_structure"] = PASS
    out["i_structured_classes_or_functions"] = PASS if ("class " in ideal_clean or "def " in ideal_clean) else FAIL
    out["i_helpers_for_repeated_logic"] = PASS if len(ideal_sig["func_defs"]) > 1 or "class " in ideal_clean else PARTIAL
    out["i_no_globals"] = FAIL if re.search(r"^[A-Z_][A-Z0-9_]*\s*=", ideal_clean, re.M) else PASS
    out["i_state_encapsulated"] = PASS if ("class " in ideal_clean or len(ideal_sig["func_defs"]) >= 1) else PARTIAL
    out["i_consistent_naming_docs"] = PASS if re.search(r'"""', ideal_clean) or re.search(r"\b[a-z_]{3,}\b", ideal_clean) else PARTIAL
    out["i_no_arbitrary_limits"] = FAIL if re.search(r"\bMAX_(?:ITERATIONS|DEPTH)\b|\bBASE_MAX_ITERATIONS\b", ideal_clean) else PASS
    out["i_no_redundant_memoization"] = PASS

    out["t_min_5_public"] = PASS if len(public_tests) >= 5 else FAIL
    out["t_min_10_private"] = PASS if len(private_tests) >= 10 else FAIL
    total_tests = len(all_tests)
    out["t_recommended_15_20_total"] = PASS if 15 <= total_tests <= 20 else PARTIAL if 10 <= total_tests <= 30 else FAIL
    out["t_json_encoded"] = PASS if all(isinstance(test, dict) and {"input", "output", "testtype"} <= set(test) for test in all_tests) else FAIL
    out["t_string_fields"] = PASS if all(all(isinstance(test.get(field), str) for field in ("input", "output", "testtype")) for test in all_tests) else FAIL
    out["t_no_markdown_json_fence"] = FAIL if any("```JSON" in str(test.get("input", "")) or "```JSON" in str(test.get("output", "")) for test in all_tests) else PASS
    arity = starter_sig["total_args"]
    arg_counts = [len([line for line in str(test["input"]).splitlines() if line.strip()]) for test in all_tests]
    ratio_matching = (sum(1 for count in arg_counts if count == arity) / len(arg_counts)) if arg_counts and arity else 0.0
    out["t_single_call_per_test"] = PASS if ratio_matching == 1.0 else PARTIAL if ratio_matching >= 0.5 else FAIL
    out["v_no_extra_parameters"] = FAIL if any(count > arity for count in arg_counts) else PASS
    out["t_deterministic"] = FAIL if re.search(r"\b(random|time\.time|datetime\.now|uuid)\b", q + "\n" + ideal_clean, re.I) else PASS
    out["t_entry_function_only"] = PASS if metadata.get("func_name") else UNCLEAR
    out["t_input_json_object"] = verdict_from_ratio(1 - (test_summary["non_object_inputs"] / max(total_tests, 1)), 1.0, 0.5)
    out["t_output_json_object"] = verdict_from_ratio(1 - (test_summary["non_object_outputs"] / max(total_tests, 1)), 1.0, 0.5)
    json_escaping_total = 0
    json_escaping_good = 0
    for test in all_tests:
        for field in ("input", "output"):
            raw = str(test[field]).strip()
            if raw.startswith("{"):
                json_escaping_total += 1
                try:
                    json.loads(raw)
                    json_escaping_good += 1
                except Exception:  # noqa: BLE001
                    pass
    out["t_json_escaping_valid"] = PASS if json_escaping_total == json_escaping_good else PARTIAL if json_escaping_good > 0 else FAIL if json_escaping_total > 0 else NA
    if test_summary["non_object_inputs"]:
        add_note("many test inputs are positional/multiline rather than JSON objects")
    if test_summary["non_object_outputs"]:
        add_note("many test outputs are scalars/lists rather than JSON objects")
    if starter_sig["defaulted_args"] > 0:
        out["t_optional_values_included"] = PASS if ratio_matching == 1.0 else PARTIAL if ratio_matching >= 0.5 else FAIL
    else:
        out["t_optional_values_included"] = NA
    out["t_no_python_literals"] = FAIL if test_summary["py_literal_hits"] else PASS
    out["t_no_nonstring_keys"] = FAIL if re.search(r"{\s*\d+\s*:", q) else PASS
    out["t_one_to_one_json_cases"] = PASS if all_tests else FAIL
    out["t_exact_output_check"] = PASS if all_tests else FAIL
    out["t_exception_tests_aligned"] = PARTIAL if any("error" in str(test.get("output", "")) for test in all_tests) else NA
    out["t_not_large_or_redundant"] = PASS if total_tests <= 30 and len(sample["row"]["private_test_cases"]) <= 50000 else PARTIAL if total_tests <= 60 else FAIL
    out["t_public_test1_matches_prompt_example"] = NA
    if out["p_example_present"] == PASS and public_tests:
        out["t_public_test1_matches_prompt_example"] = PARTIAL
    out["v_cross_verified_dry_run"] = PASS if runtime.get("total", 0) and runtime["failed"] == 0 else PARTIAL if runtime.get("passed", 0) > 0 else FAIL
    names = [name for name in [metadata.get("func_name"), prompt_signature_name, starter_name, ideal_name] if name]
    unique_names = set(names)
    out["v_entry_name_consistent"] = PASS if len(unique_names) == 1 else PARTIAL if len(unique_names) == 2 else FAIL
    out["v_signature_arity_consistent"] = PASS if arg_counts and all(count <= arity for count in arg_counts) else FAIL if arg_counts and any(count > arity for count in arg_counts) else UNCLEAR
    tested_output_keys = extract_output_keys_from_tests(all_tests)
    missing_output_keys = [key for key in tested_output_keys if key.lower() not in q.lower()]
    out["v_output_schema_aligned"] = PASS if not missing_output_keys else PARTIAL if len(missing_output_keys) <= 2 else FAIL
    out["v_prompt_test_solution_aligned"] = PARTIAL
    out["v_model_breaking_prompt_defined_only"] = PARTIAL
    out["v_no_unmentioned_internal_logic"] = PARTIAL
    out["v_prompt_edge_cases_tested"] = PARTIAL if re.search(r"edge case|empty|invalid|error", q, re.I) else NA
    out["v_prompt_constraints_tested"] = PARTIAL if re.search(r"constraint|must|range", q, re.I) else NA
    out["v_coverage_confidence"] = PASS if total_tests >= 15 else PARTIAL if total_tests >= 10 else FAIL

    if "CLEAR RULES" in ideal_clean and "CLEAR RULES" not in q:
        out["v_prompt_test_solution_aligned"] = FAIL
        out["v_no_unmentioned_internal_logic"] = FAIL
        add_note("ideal response introduces explicit rules absent from the prompt")
    prompt_error_literals = extract_prompt_error_literals(q)
    test_error_literals = set()
    for test in all_tests:
        raw = str(test.get("output", ""))
        matches = re.findall(r'"error"\s*:\s*"([^"]+)"', raw)
        test_error_literals.update(matches)
    extra_error_literals = sorted(msg for msg in test_error_literals if msg not in prompt_error_literals) if prompt_error_literals else sorted(test_error_literals)
    if extra_error_literals:
        out["t_exception_tests_aligned"] = FAIL if prompt_error_literals or test_error_literals else out["t_exception_tests_aligned"]
        out["v_model_breaking_prompt_defined_only"] = FAIL
        out["v_no_unmentioned_internal_logic"] = FAIL
        add_note("tests enforce error behavior not explicitly described in the prompt")
    if missing_output_keys:
        add_note("tests/outputs include fields not clearly described in the prompt")
        if len(missing_output_keys) > 2:
            out["v_prompt_test_solution_aligned"] = FAIL
            out["v_model_breaking_prompt_defined_only"] = FAIL
    if out["v_no_unmentioned_internal_logic"] == FAIL or out["v_model_breaking_prompt_defined_only"] == FAIL or out["v_output_schema_aligned"] == FAIL:
        out["v_prompt_test_solution_aligned"] = FAIL
    elif PARTIAL in {out["v_entry_name_consistent"], out["v_signature_arity_consistent"], out["v_output_schema_aligned"]} and out["v_prompt_test_solution_aligned"] == PASS:
        out["v_prompt_test_solution_aligned"] = PARTIAL

    if re.search(r"time window|time windows", q, re.I):
        add_note("prompt uses time-window constraints")
        out["p_no_time_window_constraints"] = FAIL
    if re.search(r"\brandom\b", q, re.I):
        add_note("prompt mentions randomness")
        out["p_no_random_requirement"] = FAIL
    if re.search(r"microsecond|nanosecond|real-time|ultra-fast|extreme load", q, re.I):
        add_note("prompt uses unrealistic performance framing")
    if re.search(r"#### Problem Statement.+#### Problem Statement", q, re.S):
        add_note("prompt repeats the problem statement heading")
    if runtime.get("errors"):
        add_note(shorten(runtime["errors"][0], width=140))
    return out, notes


def merge_verdicts(base: dict[str, str], llm: dict[str, Any], notes: list[str]) -> tuple[dict[str, str], list[str]]:
    severity = {PASS: 0, PARTIAL: 1, FAIL: 2, UNCLEAR: -1, NA: -1}
    protected_keys = {
        "p_no_time_window_constraints",
        "p_no_random_requirement",
        "p_json_compatible_signature",
        "t_json_encoded",
        "t_string_fields",
        "t_no_markdown_json_fence",
        "t_input_json_object",
        "t_output_json_object",
        "t_json_escaping_valid",
        "t_min_5_public",
        "t_min_10_private",
        "t_no_python_literals",
        "t_no_nonstring_keys",
        "i_no_parallelism",
        "i_deterministic_solution",
        "i_no_future_import",
        "i_no_keyword_only_args",
        "i_no_sample_io_in_main",
    }
    for key, value in llm.items():
        if key.startswith("_"):
            continue
        if key in protected_keys:
            continue
        if value in ALLOWED_VERDICTS:
            if key.startswith("v_") and key in base and base[key] in ALLOWED_VERDICTS:
                base[key] = value if severity.get(value, -1) > severity.get(base[key], -1) else base[key]
            else:
                base[key] = value
    for note in llm.get("_llm_notes", []):
        if isinstance(note, str) and note not in notes:
            notes.append(note)
    if llm.get("_llm_error"):
        notes.append(f"LLM unavailable: {llm['_llm_error']}")
    return base, notes


def finalize_row(sample: dict[str, Any], verdicts: dict[str, str], notes: list[str]) -> dict[str, Any]:
    row = {
        "EvaluatorVersion": EVALUATOR_VERSION,
        "Index": sample["index"],
        "QuestionId": sample["row"]["question_id"],
        "QuestionTitle": sample["row"]["question_title"],
        "Difficulty": sample["row"]["difficulty"],
        "FunctionName": sample["metadata"].get("func_name", ""),
        "LLMModel": sample.get("llm_model", ""),
        "LLMUsed": "YES" if sample.get("llm_used") else "NO",
        "RuntimePassRate": sample.get("runtime_pass_rate", ""),
    }
    for requirement in REQUIREMENTS:
        row[requirement.key] = verdicts.get(requirement.key, UNCLEAR)
    concise_notes = [shorten(note.replace("\n", " "), width=110, placeholder="...") for note in notes[:8]]
    row["Notes"] = "; ".join(concise_notes)
    return row


def evaluate_sample(sample: dict[str, Any], use_llm: bool, trace_dir: Path | None = None) -> dict[str, Any]:
    runtime = runtime_eval(sample)
    sample["runtime_pass_rate"] = f"{runtime.get('passed', 0)}/{runtime.get('total', 0)}"
    verdicts, notes = heuristics(sample, runtime)
    llm_result = llm_semantic_eval(sample, use_llm, trace_dir=trace_dir)
    sample["llm_used"] = use_llm
    sample["llm_model"] = get_stage_model_label("sample-requirements-analysis") if use_llm else ""
    verdicts, notes = merge_verdicts(verdicts, llm_result, notes)
    return finalize_row(sample, verdicts, notes)


def write_csv(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def parse_indices_arg(raw: str | None) -> list[int] | None:
    if not raw:
        return None
    values: list[int] = []
    for piece in raw.split(","):
        part = piece.strip()
        if not part:
            continue
        values.append(int(part))
    return values or None


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit coding samples against the Data Annotation Guideline.")
    parser.add_argument("--jsonl", type=Path, default=Path("Samples.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("guideline_audit.csv"))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--indices", default=None, help="Comma-separated explicit sample indices to evaluate.")
    parser.add_argument("--trace-dir", type=Path, default=None, help="Optional directory for saving per-sample LLM request/response traces.")
    parser.add_argument("--no-llm", action="store_true")
    args = parser.parse_args()

    rows_text = [line for line in args.jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]
    explicit_indices = parse_indices_arg(args.indices)
    if explicit_indices is not None:
        selected_pairs = [(index, rows_text[index]) for index in explicit_indices]
    else:
        selected = rows_text[args.offset:]
        if args.limit is not None:
            selected = selected[: args.limit]
        selected_pairs = list(enumerate(selected, start=args.offset))

    output_rows: list[dict[str, Any]] = []
    for index, row_text in selected_pairs:
        sample = parse_sample(row_text, index)
        print(f"Evaluating sample {index}...", file=sys.stderr)
        try:
            sample_trace_dir = None if args.trace_dir is None else args.trace_dir / f"sample_{index}"
            output_rows.append(evaluate_sample(sample, not args.no_llm, trace_dir=sample_trace_dir))
        except Exception:  # noqa: BLE001
            error_row = {
                "Index": index,
                "QuestionId": sample["row"]["question_id"],
                "QuestionTitle": sample["row"]["question_title"],
                "Difficulty": sample["row"]["difficulty"],
                "FunctionName": sample["metadata"].get("func_name", ""),
            }
            for requirement in REQUIREMENTS:
                error_row[requirement.key] = UNCLEAR
            error_row["Notes"] = "evaluator crashed: " + shorten(traceback.format_exc().replace("\n", " | "), width=300)
            output_rows.append(error_row)
    write_csv(output_rows, args.output)
    print(f"Wrote {len(output_rows)} rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
