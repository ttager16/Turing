"""Standalone evaluator for `1.2_no_conflicting_objectives`.

Requirement captured:
  Prompt avoids conflicting or undefined optimization objectives.

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


COLUMN_NAME = "1.2_no_conflicting_objectives"
LEGACY_KEY = "p_no_conflicting_objectives"


def evaluate(context):
    q = context.question
    conflict_hits = len(re.findall(r"minimi\w+.*maximi\w+|optimality.*computational overhead|latency.*fault tolerance|scalability.*near-microsecond|safest possible.*shortest path|balance .* and .* and .*", q, re.I))
    prompt = f'''Judge whether the prompt avoids conflicting or underdefined optimization objectives.
    Return PASS when the objective is coherent, PARTIAL when tradeoffs exist but are mostly manageable, and FAIL when objectives materially conflict.
    Sample:
    {q[:9000]}'''
    llm = context.llm_judge(COLUMN_NAME, prompt)
    verdict = llm["verdict"]
    if conflict_hits >= 2:
        verdict = FAIL
    elif conflict_hits == 1 and verdict == PASS:
        verdict = PARTIAL
    notes = [llm["note"]] if verdict != PASS and llm["note"] else []
    if verdict != PASS and not notes:
        notes = ["prompt defines competing objectives without a clear prioritization rule"]
    return EvaluationOutcome(verdict, notes[:1])
