"""Standalone evaluator for `2.1_no_arbitrary_limits`.

Requirement captured:
  Ideal response avoids hardcoded arbitrary depth or iteration limits unless prompt-specified.

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


COLUMN_NAME = "2.1_no_arbitrary_limits"
LEGACY_KEY = "i_no_arbitrary_limits"


def evaluate(context):
    verdict = FAIL if re.search(r"\bMAX_(?:ITERATIONS|DEPTH)\b|\bBASE_MAX_ITERATIONS\b", context.ideal_clean) else PASS
    notes = ["ideal response appears to use arbitrary iteration or depth limits"] if verdict == FAIL else []
    return EvaluationOutcome(verdict, notes)
