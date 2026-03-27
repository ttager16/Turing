"""Standalone evaluator for `6.2_no_unmentioned_internal_logic`.

Requirement captured:
  Tests do not depend on unprompted internal implementation details.

Guideline anchor:
  Hidden rules, extra parameters, or unprompted implementation assumptions make a sample invalid as a model breaker.

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


COLUMN_NAME = "6.2_no_unmentioned_internal_logic"
LEGACY_KEY = "v_no_unmentioned_internal_logic"


def evaluate(context):
    extra_error_literals = sorted(msg for msg in context.test_error_literals if msg not in context.prompt_error_literals) if context.prompt_error_literals else sorted(context.test_error_literals)
    ideal_rule_lines = []
    for line in context.ideal_clean.splitlines():
        stripped = line.strip(' -#\t')
        if not stripped:
            continue
        if re.search(r"\b(exactly|can only|one at a time|independent|assume|scheduled on any day|sequentially checked|tie-break)\b", stripped, re.I):
            if stripped.lower() not in context.question.lower() and len(stripped) < 160:
                ideal_rule_lines.append(stripped)
    ideal_rule_lines = ideal_rule_lines[:4]
    if 'CLEAR RULES' in context.ideal_clean and 'CLEAR RULES' not in context.question:
        return EvaluationOutcome(FAIL, ['ideal response introduces explicit rules absent from the prompt'])
    if extra_error_literals:
        return EvaluationOutcome(FAIL, ['tests enforce error behavior not explicitly described in the prompt'])
    if ideal_rule_lines:
        return EvaluationOutcome(FAIL, [f"ideal response depends on hidden logic not present in the prompt: {ideal_rule_lines[0][:100]}"])
    prompt = f'''Judge whether the benchmark depends on internal logic or hidden rules that the prompt never states.
    Return PASS, PARTIAL, or FAIL.
    Fail when the ideal response introduces behavioral assumptions the prompt does not mention.
    Prompt:
    {context.question[:10000]}
    
    Ideal Response:
    {context.ideal_clean[:10000]}
    
    Tests Preview:
    {json.dumps((context.sample.public_tests + context.sample.private_tests)[:3], ensure_ascii=False)}'''
    llm = context.llm_judge(COLUMN_NAME, prompt)
    notes = [llm['note']] if llm['verdict'] != PASS and llm['note'] else []
    return EvaluationOutcome(llm['verdict'], notes[:1])
