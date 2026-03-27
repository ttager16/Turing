"""Standalone evaluator for `1.1_structured_layout`.

Requirement captured:
  Prompt uses a clean structured layout with sections for objectives, constraints, and expected outputs.

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


COLUMN_NAME = "1.1_structured_layout"
LEGACY_KEY = "p_structured_layout"


def evaluate(context):
    q = context.question
    structured_hits = sum(1 for marker in ("Objective", "Constraints", "Input", "Output", "Function Signature") if marker.lower() in q.lower())
    verdict = PASS if structured_hits >= 3 else PARTIAL if structured_hits >= 1 else FAIL
    return EvaluationOutcome(verdict, [])
