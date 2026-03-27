"""Standalone evaluator for `2.1_helpers_for_repeated_logic`.

Requirement captured:
  Ideal response uses helper abstractions for repeated logic where appropriate.

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


COLUMN_NAME = "2.1_helpers_for_repeated_logic"
LEGACY_KEY = "i_helpers_for_repeated_logic"


def evaluate(context):
    clean = context.ideal_clean
    line_count = len([line for line in clean.splitlines() if line.strip()])
    has_helpers = len(context.ideal_signature['func_defs']) > 1 or 'class ' in clean
    if has_helpers or line_count <= 45:
        return EvaluationOutcome(PASS, [])
    verdict = FAIL if line_count > 120 else PARTIAL
    notes = ["solution is monolithic despite substantial repeated or multi-phase logic"]
    return EvaluationOutcome(verdict, notes[:1])
