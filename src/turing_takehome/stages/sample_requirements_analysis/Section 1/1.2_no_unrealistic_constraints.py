"""Standalone evaluator for `1.2_no_unrealistic_constraints`.

Requirement captured:
  Prompt avoids unrealistic or untestable requirements.

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


COLUMN_NAME = "1.2_no_unrealistic_constraints"
LEGACY_KEY = "p_no_unrealistic_constraints"


def evaluate(context):
    q = context.question
    bad_hits = re.findall(r"microsecond|nanosecond|extreme load|fault tolerance|thread safety|lock-free|concurrent optimization|near real-time|distributed signal tracking", q, re.I)
    if len(bad_hits) >= 2:
        return EvaluationOutcome(FAIL, ["prompt contains unrealistic systems or performance constraints"])
    prompt = f'''Judge whether the prompt contains unrealistic, untestable, or benchmark-distorting constraints.
    Return PASS for realistic constraints, PARTIAL for somewhat inflated but salvageable constraints, and FAIL when unrealistic constraints materially weaken the sample.
    Sample:
    {q[:9000]}'''
    llm = context.llm_judge(COLUMN_NAME, prompt)
    verdict = llm["verdict"]
    if len(bad_hits) == 1 and verdict == PASS:
        verdict = PARTIAL
    notes = [llm["note"]] if verdict != PASS and llm["note"] else []
    if re.search(r"microsecond|nanosecond|ultra-fast|extreme load", q, re.I):
        notes.insert(0, "prompt uses unrealistic performance framing")
    return EvaluationOutcome(verdict, notes[:2])
