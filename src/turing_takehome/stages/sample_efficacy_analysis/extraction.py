from __future__ import annotations

import ast
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class CodeExtractionResult:
    status: str
    code: str
    note: str


REFUSAL_MARKERS = (
    "i can't help",
    "i cannot help",
    "i can’t provide",
    "i cannot provide",
    "sorry, but",
    "as an ai",
)


def extract_python_code(response_text: str) -> CodeExtractionResult:
    text = response_text.strip()
    if not text:
        return CodeExtractionResult("no_code", "", "Model returned an empty response.")

    lowered = text.lower()
    if any(marker in lowered for marker in REFUSAL_MARKERS):
        return CodeExtractionResult("refusal", "", "Model refused or declined to answer.")

    code_blocks = re.findall(r"```(?:python)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    if code_blocks:
        best = max(code_blocks, key=len).strip()
        if best:
            return CodeExtractionResult("ok", best, "Extracted the largest fenced code block.")

    syntax_aware = _extract_parseable_python_suffix(text)
    if syntax_aware:
        return CodeExtractionResult(
            "ok",
            syntax_aware,
            "Extracted the earliest parseable Python module that preserves top-level imports and helpers.",
        )

    return CodeExtractionResult("malformed_response", "", "No runnable Python function was found in the model output.")


def _extract_parseable_python_suffix(text: str) -> str:
    lines = text.splitlines()
    candidate_starts = _candidate_start_indices(lines)
    for start_index in candidate_starts:
        suffix_lines = lines[start_index:]
        candidate = "\n".join(suffix_lines).strip()
        if _is_parseable_python_module(candidate):
            return candidate
        # If there is trailing prose after otherwise valid code, trim from the end until parse succeeds.
        for end_index in range(len(suffix_lines) - 1, 0, -1):
            candidate = "\n".join(suffix_lines[:end_index]).strip()
            if _is_parseable_python_module(candidate):
                return candidate
    return ""


def _candidate_start_indices(lines: list[str]) -> list[int]:
    indices: list[int] = []
    saw_function_marker = False
    for index, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith(("def ", "async def ")):
            saw_function_marker = True
        if _looks_like_python_start(stripped):
            indices.append(index)
    if not saw_function_marker:
        return []
    # Preserve order while removing duplicates.
    seen: set[int] = set()
    ordered: list[int] = []
    for index in indices:
        if index in seen:
            continue
        seen.add(index)
        ordered.append(index)
    return ordered


def _looks_like_python_start(stripped: str) -> bool:
    if not stripped:
        return False
    if stripped.startswith(("from ", "import ", "def ", "async def ", "class ", "@", "#")):
        return True
    # Allow docstrings or common top-level assignments/constants above the entry function.
    if stripped.startswith(('"""', "'''")):
        return True
    if re.match(r"[A-Za-z_][A-Za-z0-9_]*\s*=", stripped):
        return True
    return False


def _is_parseable_python_module(candidate: str) -> bool:
    if not candidate:
        return False
    try:
        module = ast.parse(candidate)
    except SyntaxError:
        return False
    return any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) for node in module.body)
