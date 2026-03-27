"""Standalone evaluator for `1.2_no_buzzwords`.

Requirement captured:
  Prompt avoids buzzwords without algorithmic relevance.

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


COLUMN_NAME = "1.2_no_buzzwords"
LEGACY_KEY = "p_no_buzzwords"


def evaluate(context):
    q = context.question
    buzz_hits = len(re.findall(r"world-class|state-of-the-art|ultra-competitive|near-microsecond|fault tolerance|multi-layered decision engine|compressed heavy-light decomposition|lock-free|rapidly transforming", q, re.I))
    if buzz_hits >= 3:
        return EvaluationOutcome(FAIL, ["prompt uses heavy architectural or marketing buzzwords"])
    prompt = f'''Judge whether the prompt avoids irrelevant buzzwords or architecture inflation.
    Return PASS, PARTIAL, or FAIL.
    Sample:
    {q[:9000]}'''
    llm = context.llm_judge(COLUMN_NAME, prompt)
    verdict = llm["verdict"]
    if buzz_hits >= 1 and verdict == PASS:
        verdict = PARTIAL
    notes = [llm["note"]] if verdict != PASS and llm["note"] else []
    return EvaluationOutcome(verdict, notes[:1])
