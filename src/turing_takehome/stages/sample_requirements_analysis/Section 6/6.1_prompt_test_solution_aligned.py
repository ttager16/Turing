"""Standalone evaluator for `6.1_prompt_test_solution_aligned`.

Requirement captured:
  Prompt, tests, and ideal solution are mutually aligned.

Guideline anchor:
  A valid model breaker only tests behavior that is truly defined and aligned across prompt, tests, and solution.

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


COLUMN_NAME = "6.1_prompt_test_solution_aligned"
LEGACY_KEY = "v_prompt_test_solution_aligned"


def evaluate(context):
    missing_output_keys = [key for key in context.tested_output_keys if key.lower() not in context.question.lower()]
    extra_error_literals = sorted(msg for msg in context.test_error_literals if msg not in context.prompt_error_literals) if context.prompt_error_literals else sorted(context.test_error_literals)
    ideal_rule_lines = []
    for line in context.ideal_clean.splitlines():
        stripped = line.strip(' -#\t')
        if not stripped:
            continue
        if re.search(r"\b(exactly|can only|must|one at a time|independent|scheduled on any day|tie-break|assume|sequentially checked)\b", stripped, re.I):
            if stripped.lower() not in context.question.lower() and len(stripped) < 160:
                ideal_rule_lines.append(stripped)
    ideal_rule_lines = ideal_rule_lines[:4]
    if 'CLEAR RULES' in context.ideal_clean and 'CLEAR RULES' not in context.question:
        return EvaluationOutcome(FAIL, ['ideal response introduces explicit rules absent from the prompt'])
    if extra_error_literals:
        return EvaluationOutcome(FAIL, ['tests enforce error behavior not explicitly described in the prompt'])
    if len(missing_output_keys) > 2:
        return EvaluationOutcome(FAIL, ['tests or outputs include fields not clearly described in the prompt'])
    if ideal_rule_lines:
        return EvaluationOutcome(FAIL, [f"ideal response adds behavioral rules absent from the prompt: {ideal_rule_lines[0][:100]}"])
    prompt = f'''Judge whether the prompt, tests, and ideal solution are mutually aligned as a model-evaluation contract.
    Return PASS when they line up cleanly, PARTIAL when they mostly align but need minor repair, and FAIL when the contract is materially broken.
    Explicitly fail if the tests or ideal solution require behavior not stated in the prompt.
    Prompt:
    {context.question[:10000]}
    
    Starter:
    {context.starter_clean[:4000]}
    
    Ideal Response:
    {context.ideal_clean[:10000]}
    
    Public Tests Preview:
    {json.dumps(context.sample.public_tests[:2], ensure_ascii=False)}'''
    llm = context.llm_judge(COLUMN_NAME, prompt)
    notes = [llm['note']] if llm['verdict'] != PASS and llm['note'] else []
    return EvaluationOutcome(llm['verdict'], notes[:1])
