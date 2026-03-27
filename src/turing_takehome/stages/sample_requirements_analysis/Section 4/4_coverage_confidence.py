"""Standalone evaluator for `4_coverage_confidence`.

Requirement captured:
  Combined prompt and tests suggest at least about 80 percent functional coverage.

Guideline anchor:
  Validation should include concrete dry-run evidence rather than only manual inspection.

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


COLUMN_NAME = "4_coverage_confidence"
LEGACY_KEY = "v_coverage_confidence"


def evaluate(context):
    total = len(context.all_tests)
    verdict = PASS if total >= 15 else PARTIAL if total >= 10 else FAIL
    notes = [] if verdict == PASS else ["test volume provides only partial coverage confidence"] if verdict == PARTIAL else ["test volume is too low for strong coverage confidence"]
    return EvaluationOutcome(verdict, notes[:1])
