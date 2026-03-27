"""Standalone evaluator for `6.1_signature_arity_consistent`.

Requirement captured:
  Prompt or starter signature arity is consistent with test invocation arity.

Guideline anchor:
  A valid model breaker only tests behavior that is truly defined and aligned across prompt, tests, and solution.

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


COLUMN_NAME = "6.1_signature_arity_consistent"
LEGACY_KEY = "v_signature_arity_consistent"


def evaluate(context):
    arity = context.starter_signature['total_args']
    if not context.arg_counts:
        return EvaluationOutcome(UNCLEAR, [])
    verdict = PASS if all(count <= arity for count in context.arg_counts) else FAIL if any(count > arity for count in context.arg_counts) else UNCLEAR
    notes = ["tests appear to invoke more arguments than the starter signature exposes"] if verdict == FAIL else []
    return EvaluationOutcome(verdict, notes[:1])
