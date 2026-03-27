"""Standalone evaluator for `6.3_prompt_edge_cases_tested`.

Requirement captured:
  Explicitly prompt-defined edge cases are covered by tests.

Guideline anchor:
  If the prompt names constraints or edge cases, the tests should meaningfully exercise them.

Evaluation logic:
  This file contains the operative scoring logic for this single column. The section
  runner only calls `evaluate(context)` and records the returned verdict and notes.

Subjectivity and failure modes:
  This requirement uses explicit deterministic signals, but the class boundaries still embed judgment. The file documents the rule set and any thresholds used. Known failure modes include brittle keyword matching and edge cases where a human reviewer might set a different boundary.
"""

from __future__ import annotations

import json
import re

from audit_core.context import signature_has_disallowed_types, verdict_from_ratio
from audit_core.requirements import EvaluationOutcome, FAIL, NA, PARTIAL, PASS, UNCLEAR


COLUMN_NAME = "6.3_prompt_edge_cases_tested"
LEGACY_KEY = "v_prompt_edge_cases_tested"


def evaluate(context):
    q = context.question
    edge_phrases = sorted(set(re.findall(r"empty|invalid|error|duplicate|single element|no path|start equals end|unreachable|not found", q, re.I)))
    if not edge_phrases:
        return EvaluationOutcome(NA, [])
    test_blob = "\n".join(str(test.get("input", "")) + "\n" + str(test.get("output", "")) for test in context.all_tests[:8])
    matched = [phrase for phrase in edge_phrases if phrase.lower() in test_blob.lower()]
    if len(matched) >= min(2, len(edge_phrases)):
        return EvaluationOutcome(PASS, [])
    prompt = f'''The prompt explicitly mentions these edge-case concepts: {edge_phrases}.
    Judge whether the provided tests meaningfully exercise those prompt-defined edge cases.
    Return PASS, PARTIAL, or FAIL.
    Prompt:
    {q[:8000]}
    
    Tests Preview:
    {json.dumps(context.all_tests[:6], ensure_ascii=False)}'''
    llm = context.llm_judge(COLUMN_NAME, prompt)
    notes = [llm['note']] if llm['verdict'] != PASS and llm['note'] else []
    if not notes and llm['verdict'] != PASS:
        notes = ["prompt-defined edge cases are only weakly covered by tests"]
    return EvaluationOutcome(llm['verdict'], notes[:1])
