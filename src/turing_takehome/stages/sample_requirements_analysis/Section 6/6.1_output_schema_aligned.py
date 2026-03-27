"""Standalone evaluator for `6.1_output_schema_aligned`.

Requirement captured:
  Output keys returned or tested are described in the prompt.

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


COLUMN_NAME = "6.1_output_schema_aligned"
LEGACY_KEY = "v_output_schema_aligned"


def evaluate(context):
    missing = [key for key in context.tested_output_keys if key.lower() not in context.question.lower()]
    verdict = PASS if not missing else PARTIAL if len(missing) <= 2 else FAIL
    notes = [] if verdict == PASS else ["tests or outputs include fields not clearly described in the prompt"]
    return EvaluationOutcome(verdict, notes[:1])
