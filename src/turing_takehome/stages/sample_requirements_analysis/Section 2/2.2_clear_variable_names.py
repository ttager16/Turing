"""Standalone evaluator for `2.2_clear_variable_names`.

Requirement captured:
  Ideal response uses clear variable names.

Guideline anchor:
  Ideal responses should avoid common coding patterns that make solutions brittle, confusing, or evaluator-specific.

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


COLUMN_NAME = "2.2_clear_variable_names"
LEGACY_KEY = "i_clear_variable_names"


def evaluate(context):
    prompt = f'''Judge whether the ideal response uses clear, readable variable and function names.
    Return PASS, PARTIAL, or FAIL.
    Code:
    {context.ideal_clean[:12000]}'''
    llm = context.llm_judge(COLUMN_NAME, prompt)
    notes = [llm['note']] if llm['verdict'] != PASS and llm['note'] else []
    return EvaluationOutcome(llm['verdict'], notes[:1])
