"""Standalone evaluator for `1.2_practical_algorithmic_problem`.

Requirement captured:
  Prompt reflects a practical, algorithmically solvable problem.

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


COLUMN_NAME = "1.2_practical_algorithmic_problem"
LEGACY_KEY = "p_practical_algorithmic_problem"


def evaluate(context):
    q = context.question
    inflation_hits = len(re.findall(r"segment tree|heavy-light decomposition|trie|alpha-beta|iterative deepening|thread|concurrent|lock|fault tolerance|near real-time|distributed|microsecond|nanosecond", q, re.I))
    if inflation_hits >= 5:
        return EvaluationOutcome(FAIL, ["prompt is overengineered rather than a practical algorithmic problem"])
    prompt = f'''Judge whether this sample is a practical algorithmic problem rather than an overengineered or unrealistic bundle of requirements.
    Use PASS, PARTIAL, or FAIL accordingly.
    Sample:
    {q[:9000]}'''
    llm = context.llm_judge(COLUMN_NAME, prompt)
    verdict = llm["verdict"]
    if inflation_hits >= 3 and verdict == PASS:
        verdict = PARTIAL
    notes = [llm["note"]] if verdict != PASS and llm["note"] else []
    if verdict != PASS and not notes:
        notes = ["prompt bundles too many architectural or systems concerns"]
    return EvaluationOutcome(verdict, notes[:1])
