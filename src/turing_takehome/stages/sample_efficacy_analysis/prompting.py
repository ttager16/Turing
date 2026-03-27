from __future__ import annotations

import re

from .data import SampleRecord


def build_solver_prompt(sample: SampleRecord) -> str:
    starter = _strip_code_fences(sample.starter_code).strip()
    sections = [
        "Solve the following Python coding task.",
        "",
        "Requirements:",
        "- Return only Python code.",
        "- Implement the requested entry function exactly.",
        "- Do not include explanations before or after the code.",
        "- Use only the Python standard library unless the prompt explicitly permits otherwise.",
        "",
        "Problem Statement:",
        sample.question_content.strip(),
    ]
    if starter:
        sections.extend(
            [
                "",
                "Starter Code:",
                "```python",
                starter,
                "```",
            ]
        )
    return "\n".join(sections).strip() + "\n"


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z0-9_+-]*\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()
