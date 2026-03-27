"""Standalone evaluator for `1.2_measurable_objective`.

Requirement captured:
  Prompt has well-defined measurable objectives.

Guideline anchor:
  Prompts should describe practical, realistic, well-scoped algorithmic work rather than vague or inflated scenarios.

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


COLUMN_NAME = "1.2_measurable_objective"
LEGACY_KEY = "p_measurable_objective"


def evaluate(context):
    q = context.question
    objective_signals = sum(1 for marker in ["minimize", "maximize", "return", "output", "must", "should"] if marker in q.lower())
    verdict = PASS if objective_signals >= 3 else PARTIAL if objective_signals >= 1 else FAIL
    notes = [] if verdict == PASS else ["objectives are only partially operationalized"] if verdict == PARTIAL else ["prompt does not define a sufficiently measurable target"]
    return EvaluationOutcome(verdict, notes[:1])
