from __future__ import annotations

from pathlib import Path

from . import schema
from .requirements import REQUIREMENTS


OBJECTIVE_DOC = (
    "This requirement is scored with deterministic or runtime-grounded logic. The file "
    "contains the operative thresholds and conditions directly, so review of this file "
    "should be sufficient to understand why PASS, PARTIAL, FAIL, UNCLEAR, or NA was emitted."
)

SEMI_SUBJECTIVE_DOC = (
    "This requirement uses explicit deterministic signals, but the class boundaries still "
    "embed judgment. The file documents the rule set and any thresholds used. Known failure "
    "modes include brittle keyword matching and edge cases where a human reviewer might set "
    "a different boundary."
)

SUBJECTIVE_DOC = (
    "This requirement is materially subjective. The file contains the exact LLM prompt plus "
    "the deterministic overrides and merge policy used around that prompt. Weaknesses include "
    "model sensitivity to phrasing, prompt truncation risk, and semantic ambiguity in the sample."
)

IMPORT_BLOCK = """from __future__ import annotations

import json
import re

from audit_core.context import signature_has_disallowed_types, verdict_from_ratio
from audit_core.requirements import EvaluationOutcome, FAIL, NA, PARTIAL, PASS, UNCLEAR
"""


BODY_MAP = {
    "p_structured_layout": """q = context.question
structured_hits = sum(1 for marker in ("Objective", "Constraints", "Input", "Output", "Function Signature") if marker.lower() in q.lower())
verdict = PASS if structured_hits >= 3 else PARTIAL if structured_hits >= 1 else FAIL
return EvaluationOutcome(verdict, [])""",
    "p_realistic_context": """q = context.question
inflation_hits = re.findall(r"microsecond|nanosecond|ultra-fast|extreme load|fault tolerance|thread safety|lock-free|heavy-light decomposition|segment tree|trie|abc\\b|distributed signal tracking|real-time", q, re.I)
if len(inflation_hits) >= 4:
    return EvaluationOutcome(FAIL, ["prompt context is inflated beyond a realistic benchmark scenario"])
prompt = f'''Judge whether this coding prompt uses a realistic engineering or data-problem context.
Return PASS for a believable, grounded context, PARTIAL for a somewhat inflated but still recognizable context, and FAIL for speculative or unrealistic framing.
Sample:\n{q[:9000]}'''
llm = context.llm_judge(COLUMN_NAME, prompt)
verdict = llm["verdict"]
notes = [llm["note"]] if llm["verdict"] != PASS and llm["note"] else []
if len(inflation_hits) >= 2 and verdict == PASS:
    verdict = PARTIAL
if re.search(r"microsecond|nanosecond|ultra-fast|extreme load", q, re.I):
    notes.insert(0, "prompt uses unrealistic performance framing")
return EvaluationOutcome(verdict, notes[:2])""",
    "p_input_format_explicit": """verdict = PASS if re.search(r"\\bInput\\b", context.question, re.I) else FAIL
return EvaluationOutcome(verdict, [])""",
    "p_output_format_explicit": """verdict = PASS if re.search(r"\\bOutput\\b", context.question, re.I) else FAIL
return EvaluationOutcome(verdict, [])""",
    "p_constraints_defined": """verdict = PASS if re.search(r"\\bConstraint", context.question, re.I) else FAIL
return EvaluationOutcome(verdict, [])""",
    "p_computational_limits_defined": """q = context.question
verdict = PASS if re.search(r"O\\(|time complexity|space complexity|[<>≤≥]=?\\s*\\d", q, re.I) else PARTIAL if re.search(r"\\bConstraint", q, re.I) else FAIL
return EvaluationOutcome(verdict, [])""",
    "p_edge_cases_defined": """q = context.question
verdict = PASS if re.search(r"edge case|empty|invalid|error|return .* if|if .* return", q, re.I) else PARTIAL if re.search(r"error handling", q, re.I) else FAIL
return EvaluationOutcome(verdict, [])""",
    "p_return_conditions_defined": """verdict = PASS if re.search(r"return|returns", context.question, re.I) else FAIL
return EvaluationOutcome(verdict, [])""",
    "p_function_signature_present": """verdict = PASS if re.search(r"def\\s+\\w+\\s*\\(", context.question) else FAIL
return EvaluationOutcome(verdict, [])""",
    "p_no_external_libs_stated": """q = context.question
if re.search(r"numpy|pandas|scipy|tensorflow|torch|sklearn", q, re.I):
    return EvaluationOutcome(FAIL, ["prompt appears to rely on non-stdlib libraries"])
verdict = PASS if re.search(r"no external libr|standard libr|pure python only", q, re.I) else PARTIAL
notes = [] if verdict == PASS else ["prompt does not explicitly restate the stdlib-only constraint"]
return EvaluationOutcome(verdict, notes[:1])""",
    "p_metadata_alignment": """func_name = str(context.sample.metadata.get("func_name", "")).strip()
prompt_name = context.prompt_signature_name or ""
starter_name = context.starter_name or ""
ideal_name = context.ideal_name or ""
names = [name for name in [func_name, prompt_name, starter_name, ideal_name] if name]
unique_names = set(names)
q = context.question.lower()
if not func_name:
    return EvaluationOutcome(UNCLEAR, [])
if len(unique_names) >= 3:
    return EvaluationOutcome(FAIL, ["function naming drifts across metadata, prompt, starter, or solution"])
if len(unique_names) == 2 or func_name.lower() not in q:
    return EvaluationOutcome(PARTIAL, ["function name is only partially aligned across artifacts"])
return EvaluationOutcome(PASS, [])""",
    "p_not_verbose": """q = context.question
word_count = len(q.split())
heading_count = len(re.findall(r"^#+\\s|^[-*]\\s|^\\d+\\.", q, re.M))
if word_count > 1700 or (word_count > 1300 and heading_count > 18):
    return EvaluationOutcome(FAIL, [f"prompt is overly long for benchmark use ({word_count} words)"])
if word_count < 950:
    return EvaluationOutcome(PASS, [])
prompt = f'''Judge whether this coding prompt is unnecessarily verbose for benchmark use.
Use PASS for concise prompts, PARTIAL for somewhat bloated prompts that remain usable, and FAIL for prompts where verbosity materially obscures the contract.
Word count: {word_count}\nSample:\n{q[:9000]}'''
llm = context.llm_judge(COLUMN_NAME, prompt)
verdict = llm["verdict"]
if word_count > 1200 and verdict == PASS:
    verdict = PARTIAL
notes = [llm["note"]] if verdict != PASS and llm["note"] else []
if verdict != PASS and not notes:
    notes = [f"prompt is longer than needed for a benchmark task ({word_count} words)"]
return EvaluationOutcome(verdict, notes[:1])""",
    "p_practical_algorithmic_problem": """q = context.question
inflation_hits = len(re.findall(r"segment tree|heavy-light decomposition|trie|alpha-beta|iterative deepening|thread|concurrent|lock|fault tolerance|near real-time|distributed|microsecond|nanosecond", q, re.I))
if inflation_hits >= 5:
    return EvaluationOutcome(FAIL, ["prompt is overengineered rather than a practical algorithmic problem"])
prompt = f'''Judge whether this sample is a practical algorithmic problem rather than an overengineered or unrealistic bundle of requirements.
Use PASS, PARTIAL, or FAIL accordingly.
Sample:\n{q[:9000]}'''
llm = context.llm_judge(COLUMN_NAME, prompt)
verdict = llm["verdict"]
if inflation_hits >= 3 and verdict == PASS:
    verdict = PARTIAL
notes = [llm["note"]] if verdict != PASS and llm["note"] else []
if verdict != PASS and not notes:
    notes = ["prompt bundles too many architectural or systems concerns"]
return EvaluationOutcome(verdict, notes[:1])""",
    "p_measurable_objective": """q = context.question
objective_signals = sum(1 for marker in ["minimize", "maximize", "return", "output", "must", "should"] if marker in q.lower())
verdict = PASS if objective_signals >= 3 else PARTIAL if objective_signals >= 1 else FAIL
notes = [] if verdict == PASS else ["objectives are only partially operationalized"] if verdict == PARTIAL else ["prompt does not define a sufficiently measurable target"]
return EvaluationOutcome(verdict, notes[:1])""",
    "p_difficulty_balanced": """q = context.question
difficulty = str(context.sample.row.get("difficulty", "")).lower()
word_count = len(q.split())
advanced_hits = len(re.findall(r"segment tree|heavy-light decomposition|trie|alpha-beta|iterative deepening|union-find|backtracking|concurrent|thread|lock|real-time|fault tolerance|distributed|multi-phase", q, re.I))
if difficulty == "easy":
    verdict = FAIL if advanced_hits >= 3 or word_count > 1000 else PARTIAL if advanced_hits >= 2 or word_count > 750 else PASS
elif difficulty == "medium":
    verdict = FAIL if advanced_hits >= 6 or word_count > 1500 else PARTIAL if advanced_hits >= 4 or word_count > 1100 else PASS
elif difficulty == "hard":
    verdict = FAIL if word_count < 220 and advanced_hits == 0 else PARTIAL if (advanced_hits <= 1 and word_count < 320) or word_count > 1800 else PASS
else:
    verdict = PARTIAL
notes = [] if verdict == PASS else ["difficulty label and specification burden are not well matched"]
return EvaluationOutcome(verdict, notes[:1])""",
    "p_example_present": """verdict = PASS if re.search(r"sample input|sample output|## Example|Example", context.question, re.I) else FAIL
return EvaluationOutcome(verdict, [])""",
    "p_no_unrealistic_constraints": """q = context.question
bad_hits = re.findall(r"microsecond|nanosecond|extreme load|fault tolerance|thread safety|lock-free|concurrent optimization|near real-time|distributed signal tracking", q, re.I)
if len(bad_hits) >= 2:
    return EvaluationOutcome(FAIL, ["prompt contains unrealistic systems or performance constraints"])
prompt = f'''Judge whether the prompt contains unrealistic, untestable, or benchmark-distorting constraints.
Return PASS for realistic constraints, PARTIAL for somewhat inflated but salvageable constraints, and FAIL when unrealistic constraints materially weaken the sample.
Sample:\n{q[:9000]}'''
llm = context.llm_judge(COLUMN_NAME, prompt)
verdict = llm["verdict"]
if len(bad_hits) == 1 and verdict == PASS:
    verdict = PARTIAL
notes = [llm["note"]] if verdict != PASS and llm["note"] else []
if re.search(r"microsecond|nanosecond|ultra-fast|extreme load", q, re.I):
    notes.insert(0, "prompt uses unrealistic performance framing")
return EvaluationOutcome(verdict, notes[:2])""",
    "p_not_vague": """q = context.question
objective_markers = len(re.findall(r"return|output|must|constraints|input format|output format|function signature|sample input|sample output", q, re.I))
if objective_markers <= 2:
    return EvaluationOutcome(FAIL, ["prompt does not provide enough operational detail for reliable evaluation"])
prompt = f'''Judge whether this prompt avoids vague concepts and gives enough operational detail for reliable evaluation.
Return PASS, PARTIAL, or FAIL.
Sample:\n{q[:9000]}'''
llm = context.llm_judge(COLUMN_NAME, prompt)
verdict = llm["verdict"]
if objective_markers <= 4 and verdict == PASS:
    verdict = PARTIAL
notes = [llm["note"]] if verdict != PASS and llm["note"] else []
return EvaluationOutcome(verdict, notes[:1])""",
    "p_no_conflicting_objectives": """q = context.question
conflict_hits = len(re.findall(r"minimi\\w+.*maximi\\w+|optimality.*computational overhead|latency.*fault tolerance|scalability.*near-microsecond|safest possible.*shortest path|balance .* and .* and .*", q, re.I))
prompt = f'''Judge whether the prompt avoids conflicting or underdefined optimization objectives.
Return PASS when the objective is coherent, PARTIAL when tradeoffs exist but are mostly manageable, and FAIL when objectives materially conflict.
Sample:\n{q[:9000]}'''
llm = context.llm_judge(COLUMN_NAME, prompt)
verdict = llm["verdict"]
if conflict_hits >= 2:
    verdict = FAIL
elif conflict_hits == 1 and verdict == PASS:
    verdict = PARTIAL
notes = [llm["note"]] if verdict != PASS and llm["note"] else []
if verdict != PASS and not notes:
    notes = ["prompt defines competing objectives without a clear prioritization rule"]
return EvaluationOutcome(verdict, notes[:1])""",
    "p_no_buzzwords": """q = context.question
buzz_hits = len(re.findall(r"world-class|state-of-the-art|ultra-competitive|near-microsecond|fault tolerance|multi-layered decision engine|compressed heavy-light decomposition|lock-free|rapidly transforming", q, re.I))
if buzz_hits >= 3:
    return EvaluationOutcome(FAIL, ["prompt uses heavy architectural or marketing buzzwords"])
prompt = f'''Judge whether the prompt avoids irrelevant buzzwords or architecture inflation.
Return PASS, PARTIAL, or FAIL.
Sample:\n{q[:9000]}'''
llm = context.llm_judge(COLUMN_NAME, prompt)
verdict = llm["verdict"]
if buzz_hits >= 1 and verdict == PASS:
    verdict = PARTIAL
notes = [llm["note"]] if verdict != PASS and llm["note"] else []
return EvaluationOutcome(verdict, notes[:1])""",
    "p_no_time_window_constraints": """verdict = FAIL if re.search(r"time window|time windows", context.question, re.I) else PASS
notes = ["prompt uses time-window constraints"] if verdict == FAIL else []
return EvaluationOutcome(verdict, notes)""",
    "p_no_random_requirement": """verdict = FAIL if re.search(r"\\brandom\\b", context.question, re.I) else PASS
notes = ["prompt mentions randomness"] if verdict == FAIL else []
return EvaluationOutcome(verdict, notes)""",
    "p_json_compatible_signature": """signature_source = context.prompt_signature_block or context.sample.starter_code
verdict = FAIL if context.prompt_signature_block is None and not re.search(r"def\\s+\\w+\\s*\\(", context.sample.starter_code) else FAIL if context.prompt_signature_block and signature_has_disallowed_types(signature_source) else PASS
notes = ["prompt signature uses non-JSON-compatible types"] if verdict == FAIL and context.prompt_signature_block else []
return EvaluationOutcome(verdict, notes)""",
    "s_necessary_imports": """starter_clean = context.starter_clean
import_names = set()
for match in re.finditer(r"^\\s*from\\s+[\\w.]+\\s+import\\s+(.+)$", starter_clean, re.M):
    for piece in match.group(1).split(','):
        import_names.add(piece.strip().split(' as ')[0].strip())
for match in re.finditer(r"^\\s*import\\s+(.+)$", starter_clean, re.M):
    for piece in match.group(1).split(','):
        import_names.add(piece.strip().split(' as ')[0].strip().split('.')[0])
needed_names = set(re.findall(r"\\b(List|Dict|Set|Tuple|Any|Optional|Union|defaultdict|heapq|math|cmath|gcd|json)\\b", starter_clean))
missing = sorted(name for name in needed_names if name not in import_names and name != 'json')
verdict = PASS if not missing else PARTIAL
notes = [] if not missing else [f"starter may miss imports: {', '.join(missing[:4])}"]
return EvaluationOutcome(verdict, notes)""",
    "s_only_entry_signature": """sig = context.starter_signature
lines = [line.strip() for line in context.starter_clean.splitlines() if line.strip()]
extra_lines = [line for line in lines if not (line.startswith('import ') or line.startswith('from ') or line.startswith('def ') or line in {'pass', '...'} or line.startswith('\"\"\"') or line.startswith(\"'''\"))]
verdict = PASS if len(sig['func_defs']) == 1 and not sig['class_defs'] and not extra_lines else PARTIAL if len(sig['func_defs']) == 1 else FAIL
notes = ["starter contains extra implementation or detail lines"] if extra_lines else []
return EvaluationOutcome(verdict, notes[:1])""",
    "s_no_classes": """verdict = PASS if not context.starter_signature['class_defs'] else FAIL
return EvaluationOutcome(verdict, [])""",
    "s_no_helpers": """verdict = PASS if len(context.starter_signature['func_defs']) <= 1 else FAIL
return EvaluationOutcome(verdict, [])""",
    "s_no_logic": """lines = [line.strip() for line in context.starter_clean.splitlines() if line.strip()]
extra_lines = [line for line in lines if not (line.startswith('import ') or line.startswith('from ') or line.startswith('def ') or line in {'pass', '...'} or line.startswith('\"\"\"') or line.startswith(\"'''\"))]
verdict = PASS if not extra_lines else FAIL
notes = ["starter contains extra implementation or detail lines"] if extra_lines else []
return EvaluationOutcome(verdict, notes[:1])""",
    "i_no_globals": """mutable_globals = re.findall(r"^[a-z_][a-z0-9_]*\\s*=\\s*(\\{|\\[|set\\(|defaultdict\\(|dict\\(|list\\()", context.ideal_clean, re.M)
constant_globals = re.findall(r"^[A-Z_][A-Z0-9_]*\\s*=", context.ideal_clean, re.M)
if mutable_globals:
    return EvaluationOutcome(FAIL, ["ideal response defines module-level mutable state"])
verdict = PARTIAL if len(constant_globals) >= 4 else PASS
notes = [] if verdict == PASS else ["ideal response relies on many module-level constants"]
return EvaluationOutcome(verdict, notes[:1])""",
    "i_state_encapsulated": """clean = context.ideal_clean
verdict = PASS if ('class ' in clean or len(context.ideal_signature['func_defs']) >= 1) else PARTIAL
notes = [] if verdict == PASS else ["state organization is only weakly encapsulated"]
return EvaluationOutcome(verdict, notes)""",
    "i_consistent_naming_docs": """clean = context.ideal_clean
verdict = PASS if re.search(r'\"\"\"', clean) or re.search(r"\\b[a-z_]{3,}\\b", clean) else PARTIAL
notes = [] if verdict == PASS else ["naming or documentation signals are weak"]
return EvaluationOutcome(verdict, notes)""",
    "i_no_arbitrary_limits": """verdict = FAIL if re.search(r"\\bMAX_(?:ITERATIONS|DEPTH)\\b|\\bBASE_MAX_ITERATIONS\\b", context.ideal_clean) else PASS
notes = ["ideal response appears to use arbitrary iteration or depth limits"] if verdict == FAIL else []
return EvaluationOutcome(verdict, notes)""",
    "i_single_entry_aligned": """func_name = context.sample.metadata.get('func_name')
verdict = PASS if func_name and func_name in context.ideal_clean else PARTIAL
notes = [] if verdict == PASS else ["ideal response entry point is only weakly aligned with metadata"]
return EvaluationOutcome(verdict, notes)""",
    "i_helpers_for_repeated_logic": """clean = context.ideal_clean
line_count = len([line for line in clean.splitlines() if line.strip()])
has_helpers = len(context.ideal_signature['func_defs']) > 1 or 'class ' in clean
if has_helpers or line_count <= 45:
    return EvaluationOutcome(PASS, [])
verdict = FAIL if line_count > 120 else PARTIAL
notes = ["solution is monolithic despite substantial repeated or multi-phase logic"]
return EvaluationOutcome(verdict, notes[:1])""",
    "i_no_sample_io_in_main": """verdict = FAIL if re.search(r"if\\s+__name__\\s*==\\s*['\\\"]__main__['\\\"]", context.ideal_clean) else PASS
return EvaluationOutcome(verdict, [])""",
    "i_no_parallelism": """verdict = FAIL if re.search(r"\\b(threading|multiprocessing|ThreadPoolExecutor|ProcessPoolExecutor|concurrent\\.futures)\\b", context.ideal_clean) else PASS
return EvaluationOutcome(verdict, [])""",
    "i_deterministic_solution": """verdict = FAIL if re.search(r"\\b(random|time\\.time|datetime\\.now|uuid)\\b", context.ideal_clean, re.I) else PASS
return EvaluationOutcome(verdict, [])""",
    "i_mp_module_level_functions": """uses_mp = bool(re.search(r"\\bmultiprocessing\\b|Pool\\s*\\(", context.ideal_clean))
if not uses_mp:
    return EvaluationOutcome(NA, [])
verdict = FAIL if re.search(r"^\\s{4,}def\\s+\\w+\\s*\\(", context.ideal_clean, re.M) else PASS
return EvaluationOutcome(verdict, [])""",
    "i_mp_context_manager": """uses_mp = bool(re.search(r"\\bmultiprocessing\\b|Pool\\s*\\(", context.ideal_clean))
if not uses_mp:
    return EvaluationOutcome(NA, [])
verdict = PASS if re.search(r"with\\s+multiprocessing\\.Pool\\s*\\(", context.ideal_clean) or re.search(r"with\\s+Pool\\s*\\(", context.ideal_clean) else FAIL
return EvaluationOutcome(verdict, [])""",
    "i_mp_sequential_fallback": """uses_mp = bool(re.search(r"\\bmultiprocessing\\b|Pool\\s*\\(", context.ideal_clean))
if not uses_mp:
    return EvaluationOutcome(NA, [])
verdict = PASS if re.search(r"sequential|fallback|if\\s+not\\s+use_multiprocessing|else:\\s*#?\\s*sequential", context.ideal_clean, re.I) else FAIL
return EvaluationOutcome(verdict, [])""",
    "i_no_keyword_only_args": """verdict = PASS if context.ideal_signature['kwonly'] == 0 else FAIL
return EvaluationOutcome(verdict, [])""",
    "i_no_future_import": """verdict = FAIL if re.search(r"^\\s*from\\s+__future__\\s+import", context.ideal_clean, re.M) else PASS
return EvaluationOutcome(verdict, [])""",
    "i_no_redundant_memoization": """clean = context.ideal_clean.lower()
hits = clean.count('memo') + clean.count('cache') + clean.count('lru_cache')
verdict = PASS if hits <= 2 else PARTIAL if hits <= 4 else FAIL
notes = [] if verdict == PASS else ["memoization logic may be redundant or overused"]
return EvaluationOutcome(verdict, notes)""",
    "i_clear_variable_names": """prompt = f'''Judge whether the ideal response uses clear, readable variable and function names.
Return PASS, PARTIAL, or FAIL.
Code:\n{context.ideal_clean[:12000]}'''
llm = context.llm_judge(COLUMN_NAME, prompt)
notes = [llm['note']] if llm['verdict'] != PASS and llm['note'] else []
return EvaluationOutcome(llm['verdict'], notes[:1])""",
    "i_no_nested_helpers": """nested_count = len(re.findall(r"^\\s{4,}def\\s+\\w+\\s*\\(", context.ideal_clean, re.M))
verdict = PASS if nested_count == 0 else PARTIAL if nested_count == 1 else FAIL
notes = ["ideal response defines nested helper functions"] if nested_count else []
return EvaluationOutcome(verdict, notes[:1])""",
    "i_stdlib_only": """verdict = FAIL if re.search(r"^\\s*(?:from|import)\\s+(numpy|pandas|scipy|sklearn|torch|tensorflow)\\b", context.ideal_clean, re.M) else PASS
return EvaluationOutcome(verdict, [])""",
    "i_executes_without_error": """runtime = context.runtime
verdict = PASS if runtime.get('callable_found') and runtime.get('executed') else FAIL
notes = [] if verdict == PASS else ([runtime['errors'][0]] if runtime.get('errors') else ["ideal response could not be executed"])
return EvaluationOutcome(verdict, notes[:1])""",
    "i_passes_internal_tests": """runtime = context.runtime
verdict = PASS if runtime.get('total', 0) and runtime['failed'] == 0 else PARTIAL if runtime.get('passed', 0) > 0 else FAIL
notes = [] if verdict == PASS else ([runtime['errors'][0]] if runtime.get('errors') else ["ideal response does not pass all provided tests"])
return EvaluationOutcome(verdict, notes[:1])""",
    "t_min_5_public": """verdict = PASS if len(context.sample.public_tests) >= 5 else FAIL
return EvaluationOutcome(verdict, [])""",
    "t_min_10_private": """verdict = PASS if len(context.sample.private_tests) >= 10 else FAIL
return EvaluationOutcome(verdict, [])""",
    "t_recommended_15_20_total": """total = len(context.all_tests)
verdict = PASS if 15 <= total <= 20 else PARTIAL if 10 <= total <= 30 else FAIL
return EvaluationOutcome(verdict, [])""",
    "t_single_call_per_test": """arity = context.starter_signature['total_args']
arg_counts = context.arg_counts
ratio = (sum(1 for count in arg_counts if count == arity) / len(arg_counts)) if arg_counts and arity else 0.0
verdict = PASS if ratio == 1.0 else PARTIAL if ratio >= 0.5 else FAIL
return EvaluationOutcome(verdict, [])""",
    "t_deterministic": """verdict = FAIL if re.search(r"\\b(random|time\\.time|datetime\\.now|uuid)\\b", context.question + '\\n' + context.ideal_clean, re.I) else PASS
return EvaluationOutcome(verdict, [])""",
    "t_entry_function_only": """verdict = PASS if context.sample.metadata.get('func_name') else UNCLEAR
return EvaluationOutcome(verdict, [])""",
    "t_json_encoded": """verdict = PASS if all(isinstance(test, dict) and {'input', 'output', 'testtype'} <= set(test) for test in context.all_tests) else FAIL
return EvaluationOutcome(verdict, [])""",
    "t_string_fields": """verdict = PASS if all(all(isinstance(test.get(field), str) for field in ('input', 'output', 'testtype')) for test in context.all_tests) else FAIL
return EvaluationOutcome(verdict, [])""",
    "t_input_json_object": """summary = context.test_summary
ratio = 1 - (summary['non_object_inputs'] / max(len(context.all_tests), 1))
verdict = verdict_from_ratio(ratio, 1.0, 0.5)
notes = ["many test inputs are positional or multiline rather than JSON objects"] if summary['non_object_inputs'] else []
return EvaluationOutcome(verdict, notes[:1])""",
    "t_output_json_object": """summary = context.test_summary
ratio = 1 - (summary['non_object_outputs'] / max(len(context.all_tests), 1))
verdict = verdict_from_ratio(ratio, 1.0, 0.5)
notes = ["many test outputs are scalars or lists rather than JSON objects"] if summary['non_object_outputs'] else []
return EvaluationOutcome(verdict, notes[:1])""",
    "t_json_escaping_valid": """total = 0
good = 0
for test in context.all_tests:
    for field in ('input', 'output'):
        raw = str(test[field]).strip()
        if raw.startswith('{'):
            total += 1
            try:
                json.loads(raw)
                good += 1
            except Exception:
                pass
verdict = PASS if total == good else PARTIAL if good > 0 else FAIL if total > 0 else NA
return EvaluationOutcome(verdict, [])""",
    "t_optional_values_included": """if context.starter_signature['defaulted_args'] <= 0:
    return EvaluationOutcome(NA, [])
ratio = (sum(1 for count in context.arg_counts if count == context.starter_signature['total_args']) / len(context.arg_counts)) if context.arg_counts else 0.0
verdict = PASS if ratio == 1.0 else PARTIAL if ratio >= 0.5 else FAIL
return EvaluationOutcome(verdict, [])""",
    "t_no_python_literals": """verdict = FAIL if context.test_summary['py_literal_hits'] else PASS
return EvaluationOutcome(verdict, [])""",
    "t_no_nonstring_keys": """verdict = FAIL if re.search(r"{\\s*\\d+\\s*:", context.question) else PASS
return EvaluationOutcome(verdict, [])""",
    "t_exception_tests_aligned": """prompt_literals = context.prompt_error_literals
test_literals = context.test_error_literals
if not test_literals:
    return EvaluationOutcome(NA, [])
extra = sorted(msg for msg in test_literals if msg not in prompt_literals) if prompt_literals else sorted(test_literals)
verdict = FAIL if extra else PARTIAL
notes = ["tests enforce error behavior not explicitly described in the prompt"] if extra else ["error behavior is present but only weakly specified in the prompt"]
return EvaluationOutcome(verdict, notes[:1])""",
    "t_not_large_or_redundant": """total = len(context.all_tests)
private_len = len(context.sample.row['private_test_cases'])
verdict = PASS if total <= 30 and private_len <= 50000 else PARTIAL if total <= 60 else FAIL
notes = [] if verdict == PASS else ["test set may be oversized or redundant"]
return EvaluationOutcome(verdict, notes[:1])""",
    "t_public_test1_matches_prompt_example": """q = context.question
if not re.search(r"sample input|sample output|## Example|Example", q, re.I):
    return EvaluationOutcome(NA, [])
if not context.sample.public_tests:
    return EvaluationOutcome(FAIL, ["prompt includes an example but no public tests are available"])
sample_input_match = re.search(r"Sample Input\\s*```(?:python)?\\s*(.*?)```", q, re.S | re.I)
sample_output_match = re.search(r"Sample Output\\s*```(?:python)?\\s*(.*?)```", q, re.S | re.I)
if not sample_input_match or not sample_output_match:
    example_blocks = re.findall(r"Example.*?```(?:python)?\\s*(.*?)```", q, re.S | re.I)
    if len(example_blocks) >= 2:
        sample_input = example_blocks[0].strip()
        sample_output = example_blocks[1].strip()
    else:
        return EvaluationOutcome(UNCLEAR, ["prompt example exists but could not be extracted reliably"])
else:
    sample_input = sample_input_match.group(1).strip()
    sample_output = sample_output_match.group(1).strip()
def normalize(raw: str) -> str:
    return re.sub(r"\\s+", "", raw.strip().replace("\\r", ""))
public0 = context.sample.public_tests[0]
input_match = normalize(sample_input) == normalize(str(public0.get("input", "")))
output_match = normalize(sample_output) == normalize(str(public0.get("output", "")))
verdict = PASS if input_match and output_match else PARTIAL if input_match or output_match else FAIL
notes = [] if verdict == PASS else ["public test 1 does not cleanly match the prompt's sample I/O"]
return EvaluationOutcome(verdict, notes[:1])""",
    "v_coverage_confidence": """total = len(context.all_tests)
verdict = PASS if total >= 15 else PARTIAL if total >= 10 else FAIL
notes = [] if verdict == PASS else ["test volume provides only partial coverage confidence"] if verdict == PARTIAL else ["test volume is too low for strong coverage confidence"]
return EvaluationOutcome(verdict, notes[:1])""",
    "v_cross_verified_dry_run": """runtime = context.runtime
verdict = PASS if runtime.get('total', 0) and runtime['failed'] == 0 else PARTIAL if runtime.get('passed', 0) > 0 else FAIL
notes = [] if verdict == PASS else ([runtime['errors'][0]] if runtime.get('errors') else ["dry run did not complete cleanly"])
return EvaluationOutcome(verdict, notes[:1])""",
    "v_entry_name_consistent": """names = [name for name in [context.sample.metadata.get('func_name'), context.prompt_signature_name, context.starter_name, context.ideal_name] if name]
unique_names = set(names)
verdict = PASS if len(unique_names) == 1 else PARTIAL if len(unique_names) == 2 else FAIL
notes = [] if verdict == PASS else ["entry-point names are inconsistent across prompt, starter, metadata, or solution"]
return EvaluationOutcome(verdict, notes[:1])""",
    "v_signature_arity_consistent": """arity = context.starter_signature['total_args']
if not context.arg_counts:
    return EvaluationOutcome(UNCLEAR, [])
verdict = PASS if all(count <= arity for count in context.arg_counts) else FAIL if any(count > arity for count in context.arg_counts) else UNCLEAR
notes = ["tests appear to invoke more arguments than the starter signature exposes"] if verdict == FAIL else []
return EvaluationOutcome(verdict, notes[:1])""",
    "v_output_schema_aligned": """missing = [key for key in context.tested_output_keys if key.lower() not in context.question.lower()]
verdict = PASS if not missing else PARTIAL if len(missing) <= 2 else FAIL
notes = [] if verdict == PASS else ["tests or outputs include fields not clearly described in the prompt"]
return EvaluationOutcome(verdict, notes[:1])""",
    "v_prompt_edge_cases_tested": """q = context.question
edge_phrases = sorted(set(re.findall(r"empty|invalid|error|duplicate|single element|no path|start equals end|unreachable|not found", q, re.I)))
if not edge_phrases:
    return EvaluationOutcome(NA, [])
test_blob = "\\n".join(str(test.get("input", "")) + "\\n" + str(test.get("output", "")) for test in context.all_tests[:8])
matched = [phrase for phrase in edge_phrases if phrase.lower() in test_blob.lower()]
if len(matched) >= min(2, len(edge_phrases)):
    return EvaluationOutcome(PASS, [])
prompt = f'''The prompt explicitly mentions these edge-case concepts: {edge_phrases}.
Judge whether the provided tests meaningfully exercise those prompt-defined edge cases.
Return PASS, PARTIAL, or FAIL.
Prompt:\n{q[:8000]}\n\nTests Preview:\n{json.dumps(context.all_tests[:6], ensure_ascii=False)}'''
llm = context.llm_judge(COLUMN_NAME, prompt)
notes = [llm['note']] if llm['verdict'] != PASS and llm['note'] else []
if not notes and llm['verdict'] != PASS:
    notes = ["prompt-defined edge cases are only weakly covered by tests"]
return EvaluationOutcome(llm['verdict'], notes[:1])""",
    "v_prompt_constraints_tested": """q = context.question
constraint_phrases = sorted(set(re.findall(r"must|at least|at most|deadline|time window|capacity|security|availability|priority|group|service time", q, re.I)))
if not constraint_phrases:
    return EvaluationOutcome(NA, [])
test_blob = "\\n".join(str(test.get("input", "")) + "\\n" + str(test.get("output", "")) for test in context.all_tests[:8])
matched = [phrase for phrase in constraint_phrases if phrase.lower() in test_blob.lower()]
if len(matched) >= min(3, max(1, len(constraint_phrases) // 3)):
    return EvaluationOutcome(PASS, [])
prompt = f'''The prompt explicitly names these constraint concepts: {constraint_phrases[:12]}.
Judge whether the provided tests meaningfully exercise the prompt-defined constraints.
Return PASS, PARTIAL, or FAIL.
Prompt:\n{q[:8000]}\n\nTests Preview:\n{json.dumps(context.all_tests[:6], ensure_ascii=False)}'''
llm = context.llm_judge(COLUMN_NAME, prompt)
notes = [llm['note']] if llm['verdict'] != PASS and llm['note'] else []
if not notes and llm['verdict'] != PASS:
    notes = ["prompt-defined constraints are only weakly exercised by the supplied tests"]
return EvaluationOutcome(llm['verdict'], notes[:1])""",
    "v_no_extra_parameters": """arity = context.starter_signature['total_args']
verdict = FAIL if any(count > arity for count in context.arg_counts) else PASS
notes = ["tests pass extra parameters beyond the starter signature"] if verdict == FAIL else []
return EvaluationOutcome(verdict, notes)""",
    "v_prompt_test_solution_aligned": """missing_output_keys = [key for key in context.tested_output_keys if key.lower() not in context.question.lower()]
extra_error_literals = sorted(msg for msg in context.test_error_literals if msg not in context.prompt_error_literals) if context.prompt_error_literals else sorted(context.test_error_literals)
ideal_rule_lines = []
for line in context.ideal_clean.splitlines():
    stripped = line.strip(' -#\\t')
    if not stripped:
        continue
    if re.search(r"\\b(exactly|can only|must|one at a time|independent|scheduled on any day|tie-break|assume|sequentially checked)\\b", stripped, re.I):
        if stripped.lower() not in context.question.lower() and len(stripped) < 160:
            ideal_rule_lines.append(stripped)
ideal_rule_lines = ideal_rule_lines[:4]
if 'CLEAR RULES' in context.ideal_clean and 'CLEAR RULES' not in context.question:
    return EvaluationOutcome(FAIL, ['ideal response introduces explicit rules absent from the prompt'])
if extra_error_literals:
    return EvaluationOutcome(FAIL, ['tests enforce error behavior not explicitly described in the prompt'])
if len(missing_output_keys) > 2:
    return EvaluationOutcome(FAIL, ['tests or outputs include fields not clearly described in the prompt'])
if ideal_rule_lines:
    return EvaluationOutcome(FAIL, [f"ideal response adds behavioral rules absent from the prompt: {ideal_rule_lines[0][:100]}"])
prompt = f'''Judge whether the prompt, tests, and ideal solution are mutually aligned as a model-evaluation contract.
Return PASS when they line up cleanly, PARTIAL when they mostly align but need minor repair, and FAIL when the contract is materially broken.
Explicitly fail if the tests or ideal solution require behavior not stated in the prompt.
Prompt:\n{context.question[:10000]}\n\nStarter:\n{context.starter_clean[:4000]}\n\nIdeal Response:\n{context.ideal_clean[:10000]}\n\nPublic Tests Preview:\n{json.dumps(context.sample.public_tests[:2], ensure_ascii=False)}'''
llm = context.llm_judge(COLUMN_NAME, prompt)
notes = [llm['note']] if llm['verdict'] != PASS and llm['note'] else []
return EvaluationOutcome(llm['verdict'], notes[:1])""",
    "v_model_breaking_prompt_defined_only": """missing_output_keys = [key for key in context.tested_output_keys if key.lower() not in context.question.lower()]
extra_error_literals = sorted(msg for msg in context.test_error_literals if msg not in context.prompt_error_literals) if context.prompt_error_literals else sorted(context.test_error_literals)
ideal_rule_lines = []
for line in context.ideal_clean.splitlines():
    stripped = line.strip(' -#\\t')
    if not stripped:
        continue
    if re.search(r"\\b(exactly|can only|one at a time|independent|assume|scheduled on any day|sequentially checked)\\b", stripped, re.I):
        if stripped.lower() not in context.question.lower() and len(stripped) < 160:
            ideal_rule_lines.append(stripped)
if extra_error_literals:
    return EvaluationOutcome(FAIL, ['tests enforce error behavior not explicitly described in the prompt'])
if len(missing_output_keys) > 2:
    return EvaluationOutcome(FAIL, ['tests or outputs include fields not clearly described in the prompt'])
if ideal_rule_lines:
    return EvaluationOutcome(FAIL, ['sample breaks models on solution-only rules rather than prompt-defined behavior'])
prompt = f'''Judge whether the sample only breaks models on behavior that is actually defined in the prompt.
Return PASS, PARTIAL, or FAIL.
Fail when the tests or ideal solution appear to rely on hidden rules or extra contract assumptions.
Prompt:\n{context.question[:10000]}\n\nIdeal Response:\n{context.ideal_clean[:10000]}\n\nTests Preview:\n{json.dumps((context.sample.public_tests + context.sample.private_tests)[:3], ensure_ascii=False)}'''
llm = context.llm_judge(COLUMN_NAME, prompt)
notes = [llm['note']] if llm['verdict'] != PASS and llm['note'] else []
return EvaluationOutcome(llm['verdict'], notes[:1])""",
    "v_no_unmentioned_internal_logic": """extra_error_literals = sorted(msg for msg in context.test_error_literals if msg not in context.prompt_error_literals) if context.prompt_error_literals else sorted(context.test_error_literals)
ideal_rule_lines = []
for line in context.ideal_clean.splitlines():
    stripped = line.strip(' -#\\t')
    if not stripped:
        continue
    if re.search(r"\\b(exactly|can only|one at a time|independent|assume|scheduled on any day|sequentially checked|tie-break)\\b", stripped, re.I):
        if stripped.lower() not in context.question.lower() and len(stripped) < 160:
            ideal_rule_lines.append(stripped)
ideal_rule_lines = ideal_rule_lines[:4]
if 'CLEAR RULES' in context.ideal_clean and 'CLEAR RULES' not in context.question:
    return EvaluationOutcome(FAIL, ['ideal response introduces explicit rules absent from the prompt'])
if extra_error_literals:
    return EvaluationOutcome(FAIL, ['tests enforce error behavior not explicitly described in the prompt'])
if ideal_rule_lines:
    return EvaluationOutcome(FAIL, [f"ideal response depends on hidden logic not present in the prompt: {ideal_rule_lines[0][:100]}"])
prompt = f'''Judge whether the benchmark depends on internal logic or hidden rules that the prompt never states.
Return PASS, PARTIAL, or FAIL.
Fail when the ideal response introduces behavioral assumptions the prompt does not mention.
Prompt:\n{context.question[:10000]}\n\nIdeal Response:\n{context.ideal_clean[:10000]}\n\nTests Preview:\n{json.dumps((context.sample.public_tests + context.sample.private_tests)[:3], ensure_ascii=False)}'''
llm = context.llm_judge(COLUMN_NAME, prompt)
notes = [llm['note']] if llm['verdict'] != PASS and llm['note'] else []
return EvaluationOutcome(llm['verdict'], notes[:1])""",
}


STAR_EXPLANATION = {0: OBJECTIVE_DOC, 1: SEMI_SUBJECTIVE_DOC, 2: SUBJECTIVE_DOC}


def module_text(spec, description):
    body = BODY_MAP[spec.key]
    return f'''"""Standalone evaluator for `{spec.display_name}`.

Requirement captured:
  {description}

Guideline anchor:
  {spec.guideline_anchor}

Evaluation logic:
  This file contains the operative scoring logic for this single column. The section
  runner only calls `evaluate(context)` and records the returned verdict and notes.

Subjectivity and failure modes:
  {STAR_EXPLANATION[spec.star_level]}
"""

{IMPORT_BLOCK}

COLUMN_NAME = "{spec.display_name}"
LEGACY_KEY = "{spec.key}"


def evaluate(context):
    {body.replace(chr(10), chr(10) + "    ")}
'''


def section_main_text(section_number):
    return f'''"""Section {section_number} runner.

This script executes all per-column evaluators for Section {section_number}. Each column
module owns its own verdict logic. This section runner only coordinates execution order
and aggregates subsection-level averages for the workbook's second tab.
"""

from pathlib import Path

from audit_core.section_runner import run_section


def run(contexts):
    return run_section("{section_number}", Path(__file__).parent, contexts)
'''


def generate(base_dir: Path) -> None:
    requirement_lookup = {requirement.key: requirement for requirement in REQUIREMENTS}
    specs = schema.build_column_specs()
    for section_number in schema.SECTION_NUMBERS:
        section_dir = base_dir / schema.section_folder_name(section_number)
        section_dir.mkdir(parents=True, exist_ok=True)
        (section_dir / f"section_{section_number}_main.py").write_text(section_main_text(section_number), encoding="utf-8")
        for spec in [item for item in specs if item.section_number.split(".", 1)[0] == section_number]:
            text = module_text(spec, requirement_lookup[spec.key].description)
            (section_dir / f"{spec.display_name}.py").write_text(text, encoding="utf-8")


def main() -> int:
    generate(Path(__file__).resolve().parents[1])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
