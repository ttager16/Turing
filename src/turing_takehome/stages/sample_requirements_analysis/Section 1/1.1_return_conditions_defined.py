"""Standalone evaluator for `1.1_return_conditions_defined`.

Requirement captured:
  Prompt defines return conditions or error-return behavior.

Guideline anchor:
  Prompts should define a clear contract: what the task is, what comes in, what comes out, and what constraints or edge conditions matter.

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


COLUMN_NAME = "1.1_return_conditions_defined"
LEGACY_KEY = "p_return_conditions_defined"


def evaluate(context):
    verdict = PASS if re.search(r"return|returns", context.question, re.I) else FAIL
    return EvaluationOutcome(verdict, [])
