from __future__ import annotations

import ast
import json
import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from textwrap import shorten
from typing import Any

from turing_takehome.llm import StageName, get_stage_model_label, request_structured_judgment

from .requirements import ALLOWED_VERDICTS, FAIL, NA, PARTIAL, PASS, UNCLEAR


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
        signature_match = re.search(r"^\s*(def\s+\w+\s*\(.*?\)\s*(?:->\s*[^:\n]+)?\s*:?)\s*$", code, re.M)
        if signature_match:
            stub = signature_match.group(1).rstrip()
            if not stub.endswith(":"):
                stub += ":"
            try:
                tree = ast.parse(stub + "\n    pass\n")
            except SyntaxError:
                return {"func_defs": [], "class_defs": [], "kwonly": 0, "defaulted_args": 0, "total_args": 0}
        else:
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
        except Exception:
            continue
        if isinstance(parsed, dict):
            keys.update(str(key) for key in parsed.keys())
    return keys


def extract_prompt_error_literals(text: str) -> set[str]:
    return set(re.findall(r"'error'\s*:\s*'([^']+)'", text))


@dataclass
class SampleRecord:
    index: int
    row: dict[str, Any]
    metadata: dict[str, Any]
    question_content: str
    starter_code: str
    ideal_response: str
    public_tests: list[dict[str, Any]]
    private_tests: list[dict[str, Any]]


def parse_sample(row_text: str, index: int) -> SampleRecord:
    row = json.loads(row_text)
    return SampleRecord(
        index=index,
        row=row,
        metadata=json.loads(row["metadata"]),
        question_content=row["question_content"],
        starter_code=row["starter_code"],
        ideal_response=row["ideal_response"],
        public_tests=json.loads(row["public_test_cases"]),
        private_tests=json.loads(row["private_test_cases"]),
    )


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


def runtime_eval(sample: SampleRecord) -> dict[str, Any]:
    code = strip_code_fences(sample.ideal_response)
    ns: dict[str, Any] = {"__name__": "__guideline_eval__"}
    results = {"executed": False, "passed": 0, "failed": 0, "total": 0, "errors": [], "callable_found": False}
    previous_disable = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        exec(code, ns, ns)
    except Exception as exc:
        results["errors"].append(f"ideal_response exec failed: {exc.__class__.__name__}: {exc}")
        logging.disable(previous_disable)
        return results
    func = ns.get(sample.metadata.get("func_name"))
    if not callable(func):
        results["errors"].append(f"entry function '{sample.metadata.get('func_name')}' not found after exec")
        logging.disable(previous_disable)
        return results
    results["callable_found"] = True
    for test in sample.public_tests + sample.private_tests:
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
                    except Exception:
                        pass
            if actual == expected:
                results["passed"] += 1
            else:
                results["failed"] += 1
                if len(results["errors"]) < 8:
                    results["errors"].append(f"mismatch expected {shorten(repr(expected), width=100)} got {shorten(repr(actual), width=100)}")
        except Exception as exc:
            results["failed"] += 1
            if len(results["errors"]) < 8:
                results["errors"].append(f"test execution failed: {exc.__class__.__name__}: {exc}")
    results["executed"] = True
    logging.disable(previous_disable)
    return results


@dataclass
class EvaluationContext:
    sample: SampleRecord
    stage_name: StageName
    use_llm: bool
    trace_dir: Path | None = None
    cache: dict[str, Any] = field(default_factory=dict)
    llm_cache: dict[str, dict[str, Any]] = field(default_factory=dict)

    def get(self, key: str, builder):
        if key not in self.cache:
            self.cache[key] = builder()
        return self.cache[key]

    @property
    def question(self) -> str:
        return self.sample.question_content

    @property
    def starter(self) -> str:
        return self.sample.starter_code

    @property
    def ideal(self) -> str:
        return self.sample.ideal_response

    @property
    def starter_clean(self) -> str:
        return self.get("starter_clean", lambda: strip_code_fences(self.sample.starter_code))

    @property
    def ideal_clean(self) -> str:
        return self.get("ideal_clean", lambda: strip_code_fences(self.sample.ideal_response))

    @property
    def all_tests(self) -> list[dict[str, Any]]:
        return self.sample.public_tests + self.sample.private_tests

    @property
    def prompt_signature_block(self) -> str | None:
        return self.get("prompt_signature_block", lambda: extract_prompt_signature_block(self.question))

    @property
    def prompt_signature_name(self) -> str | None:
        return self.get("prompt_signature_name", lambda: extract_function_name_from_code(self.prompt_signature_block or ""))

    @property
    def starter_signature(self) -> dict[str, Any]:
        return self.get("starter_signature", lambda: parse_signature_info(self.sample.starter_code))

    @property
    def ideal_signature(self) -> dict[str, Any]:
        return self.get("ideal_signature", lambda: parse_signature_info(self.sample.ideal_response))

    @property
    def starter_name(self) -> str | None:
        return self.get("starter_name", lambda: extract_function_name_from_code(self.sample.starter_code))

    @property
    def ideal_name(self) -> str | None:
        return self.get("ideal_name", lambda: extract_function_name_from_code(self.sample.ideal_response))

    @property
    def test_summary(self) -> dict[str, Any]:
        return self.get("test_summary", lambda: summarize_tests(self.sample.public_tests, self.sample.private_tests))

    @property
    def runtime(self) -> dict[str, Any]:
        return self.get("runtime", lambda: runtime_eval(self.sample))

    @property
    def runtime_pass_rate(self) -> str:
        runtime = self.runtime
        return f"{runtime.get('passed', 0)}/{runtime.get('total', 0)}"

    @property
    def tested_output_keys(self) -> set[str]:
        return self.get("tested_output_keys", lambda: extract_output_keys_from_tests(self.all_tests))

    @property
    def prompt_error_literals(self) -> set[str]:
        return self.get("prompt_error_literals", lambda: extract_prompt_error_literals(self.question))

    @property
    def test_error_literals(self) -> set[str]:
        def build() -> set[str]:
            literals: set[str] = set()
            for test in self.all_tests:
                raw = str(test.get("output", ""))
                literals.update(re.findall(r'"error"\s*:\s*"([^"]+)"', raw))
            return literals
        return self.get("test_error_literals", build)

    @property
    def arg_counts(self) -> list[int]:
        return self.get("arg_counts", lambda: [len([line for line in str(test["input"]).splitlines() if line.strip()]) for test in self.all_tests])

    @property
    def llm_model_label(self) -> str:
        return self.get("llm_model_label", lambda: get_stage_model_label(self.stage_name))

    def llm_judge(self, column_name: str, prompt_text: str) -> dict[str, Any]:
        if column_name in self.llm_cache:
            return self.llm_cache[column_name]
        if not self.use_llm:
            result = {"verdict": UNCLEAR, "note": "LLM disabled"}
            self.llm_cache[column_name] = result
            return result
        model_label = self.llm_model_label
        if not model_label:
            result = {"verdict": UNCLEAR, "note": "No configured model was available for this stage"}
            self.llm_cache[column_name] = result
            return result
        trace_dir = None if self.trace_dir is None else self.trace_dir / "llm"
        try:
            result = request_structured_judgment(
                self.stage_name,
                column_name.replace(".", "_"),
                prompt_text,
                trace_dir=trace_dir,
            )
        except Exception as exc:
            result = {"verdict": UNCLEAR, "note": f"LLM unavailable: {exc.__class__.__name__}: {exc}"}
        verdict = result.get("verdict", UNCLEAR)
        if verdict not in ALLOWED_VERDICTS:
            verdict = UNCLEAR
        note = str(result.get("note", "")).strip()
        clean = {"verdict": verdict, "note": note}
        self.llm_cache[column_name] = clean
        return clean
