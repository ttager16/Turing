"""Standalone evaluator for `1.2_not_vague`.

Requirement captured:
  Prompt avoids vague problem definitions.

Guideline anchor:
  Prompts should describe practical, realistic, well-scoped algorithmic work rather than vague or inflated scenarios.

Evaluation logic:
  This file contains the operative scoring logic for this single column. The section
  runner only calls `evaluate(context)` and records the returned verdict and notes.

Subjectivity and failure modes:
  This requirement is materially subjective. The file contains the exact LLM prompt plus the deterministic overrides and merge policy used around that prompt. Weaknesses include model sensitivity to phrasing, prompt truncation risk, and semantic ambiguity in the sample.
"""

from __future__ import annotations

import json
import re

from audit_core.context import signature_has_disallowed_types, verdict_from_ratio
from audit_core.requirements import EvaluationOutcome, FAIL, NA, PARTIAL, PASS, UNCLEAR


COLUMN_NAME = "1.2_not_vague"
LEGACY_KEY = "p_not_vague"


def evaluate(context):
    q = context.question
    objective_markers = len(re.findall(r"return|output|must|constraints|input format|output format|function signature|sample input|sample output", q, re.I))
    if objective_markers <= 2:
        return EvaluationOutcome(FAIL, ["prompt does not provide enough operational detail for reliable evaluation"])
    prompt = f'''Judge whether this prompt avoids vague concepts and gives enough operational detail for reliable evaluation.
    Return PASS, PARTIAL, or FAIL.
    Sample:
    {q[:9000]}'''
    llm = context.llm_judge(COLUMN_NAME, prompt)
    verdict = llm["verdict"]
    if objective_markers <= 4 and verdict == PASS:
        verdict = PARTIAL
    notes = [llm["note"]] if verdict != PASS and llm["note"] else []
    return EvaluationOutcome(verdict, notes[:1])
