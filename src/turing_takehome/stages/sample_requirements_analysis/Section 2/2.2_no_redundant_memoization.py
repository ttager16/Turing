"""Standalone evaluator for `2.2_no_redundant_memoization`.

Requirement captured:
  Ideal response avoids redundant memoization logic spread across functions.

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


COLUMN_NAME = "2.2_no_redundant_memoization"
LEGACY_KEY = "i_no_redundant_memoization"


def evaluate(context):
    clean = context.ideal_clean.lower()
    hits = clean.count('memo') + clean.count('cache') + clean.count('lru_cache')
    verdict = PASS if hits <= 2 else PARTIAL if hits <= 4 else FAIL
    notes = [] if verdict == PASS else ["memoization logic may be redundant or overused"]
    return EvaluationOutcome(verdict, notes)
