"""Standalone evaluator for `3.3.1_exception_tests_aligned`.

Requirement captured:
  Exception or error-handling tests are aligned with prompt-described behavior.

Guideline anchor:
  Error-handling tests are only valid when they enforce behavior the prompt actually defines.

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


COLUMN_NAME = "3.3.1_exception_tests_aligned"
LEGACY_KEY = "t_exception_tests_aligned"


def evaluate(context):
    prompt_literals = context.prompt_error_literals
    test_literals = context.test_error_literals
    if not test_literals:
        return EvaluationOutcome(NA, [])
    extra = sorted(msg for msg in test_literals if msg not in prompt_literals) if prompt_literals else sorted(test_literals)
    verdict = FAIL if extra else PARTIAL
    notes = ["tests enforce error behavior not explicitly described in the prompt"] if extra else ["error behavior is present but only weakly specified in the prompt"]
    return EvaluationOutcome(verdict, notes[:1])
