"""Standalone evaluator for `2.2_no_nested_helpers`.

Requirement captured:
  Ideal response avoids unscoped helper methods or nested function definitions.

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


COLUMN_NAME = "2.2_no_nested_helpers"
LEGACY_KEY = "i_no_nested_helpers"


def evaluate(context):
    nested_count = len(re.findall(r"^\s{4,}def\s+\w+\s*\(", context.ideal_clean, re.M))
    verdict = PASS if nested_count == 0 else PARTIAL if nested_count == 1 else FAIL
    notes = ["ideal response defines nested helper functions"] if nested_count else []
    return EvaluationOutcome(verdict, notes[:1])
