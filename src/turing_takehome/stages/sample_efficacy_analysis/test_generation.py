from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from turing_takehome.llm import request_json_for_target

from .data import SampleRecord, TestCase


def generate_additional_tests(
    sample: SampleRecord,
    *,
    target_name: str,
    count: int,
    trace_dir: Path | None = None,
) -> list[dict[str, Any]]:
    if count <= 0:
        return []
    schema = {
        "type": "object",
        "properties": {
            "cases": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "input_lines": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "focus": {"type": "string"},
                    },
                    "required": ["input_lines", "focus"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["cases"],
        "additionalProperties": False,
    }
    prompt = _build_generated_test_prompt(sample, count)
    payload = request_json_for_target(
        target_name,
        "generated_test_cases",
        schema,
        prompt,
        system_prompt=(
            "You design compact, high-value coding benchmark tests. "
            "Return only valid JSON matching the schema."
        ),
        trace_dir=trace_dir,
    )
    cases = payload.get("cases", [])
    clean_cases: list[dict[str, Any]] = []
    for index, case in enumerate(cases):
        input_lines = case.get("input_lines", [])
        if not isinstance(input_lines, list) or not all(isinstance(item, str) for item in input_lines):
            continue
        focus = str(case.get("focus", "")).strip()
        try:
            args = [json.loads(line) for line in input_lines if line.strip()]
        except Exception:
            continue
        clean_cases.append(
            {
                "case_index": index,
                "args": args,
                "input_lines": input_lines,
                "focus": focus,
            }
        )
    return clean_cases[:count]


def build_generated_test_case(case_index: int, args: list[Any], expected: Any) -> TestCase:
    return TestCase(
        visibility="generated",
        case_index=case_index,
        input_text="\n".join(json.dumps(arg, ensure_ascii=False) for arg in args),
        output_text=json.dumps(expected, ensure_ascii=False),
        testtype="generated",
    )


def _build_generated_test_prompt(sample: SampleRecord, count: int) -> str:
    public_examples = []
    for test in sample.public_tests[: min(3, len(sample.public_tests))]:
        public_examples.append(
            {
                "input": test.input_text,
                "output": test.output_text,
            }
        )
    sections = [
        f"Generate {count} additional Python function test inputs for this benchmark sample.",
        "",
        "Rules:",
        "- Return only test inputs, not expected outputs.",
        "- Focus on edge cases, boundary conditions, format-sensitive cases, and cases likely to separate strong from merely pattern-matching solutions.",
        "- Do not require external libraries.",
        "- Keep inputs valid under the problem statement.",
        "- Match the existing function-call argument shape.",
        "- Each input_lines item must be one JSON-encoded argument value, matching how the existing tests are stored.",
        "",
        f"Function name: {sample.function_name}",
        "",
        "Problem Statement:",
        sample.question_content.strip(),
    ]
    starter = sample.starter_code.strip()
    if starter:
        sections.extend(["", "Starter Code:", starter])
    if public_examples:
        sections.extend(
            [
                "",
                "Public test examples:",
                json.dumps(public_examples, ensure_ascii=False, indent=2),
            ]
        )
    return "\n".join(sections).strip() + "\n"
