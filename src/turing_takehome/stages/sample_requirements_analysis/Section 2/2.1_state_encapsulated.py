"""Standalone evaluator for `2.1_state_encapsulated`.

Requirement captured:
  State and logic are encapsulated within classes or local scope.

Guideline anchor:
  Ideal responses should be clean, deterministic, and structured without unnecessary complexity or hidden state.

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


COLUMN_NAME = "2.1_state_encapsulated"
LEGACY_KEY = "i_state_encapsulated"


def evaluate(context):
    clean = context.ideal_clean
    verdict = PASS if ('class ' in clean or len(context.ideal_signature['func_defs']) >= 1) else PARTIAL
    notes = [] if verdict == PASS else ["state organization is only weakly encapsulated"]
    return EvaluationOutcome(verdict, notes)
