"""Standalone evaluator for `1.2_example_present`.

Requirement captured:
  Prompt includes at least one concrete sample input or output example.

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


COLUMN_NAME = "1.2_example_present"
LEGACY_KEY = "p_example_present"


def evaluate(context):
    verdict = PASS if re.search(r"sample input|sample output|## Example|Example", context.question, re.I) else FAIL
    return EvaluationOutcome(verdict, [])
