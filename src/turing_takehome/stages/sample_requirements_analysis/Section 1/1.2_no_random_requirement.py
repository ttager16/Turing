"""Standalone evaluator for `1.2_no_random_requirement`.

Requirement captured:
  Prompt does not require or rely on randomness.

Guideline anchor:
  Prompts should describe practical, realistic, well-scoped algorithmic work rather than vague or inflated scenarios.

Evaluation logic:
  This file contains the operative scoring logic for this single column. The section
  runner only calls `evaluate(context)` and records the returned verdict and notes.

Subjectivity and failure modes:
  This requirement is scored with deterministic or runtime-grounded logic. The file contains the operative thresholds and conditions directly, so review of this file should be sufficient to understand why PASS, PARTIAL, FAIL, UNCLEAR, or NA was emitted.
"""

from __future__ import annotations

import json
import re

from audit_core.context import signature_has_disallowed_types, verdict_from_ratio
from audit_core.requirements import EvaluationOutcome, FAIL, NA, PARTIAL, PASS, UNCLEAR


COLUMN_NAME = "1.2_no_random_requirement"
LEGACY_KEY = "p_no_random_requirement"


def evaluate(context):
    verdict = FAIL if re.search(r"\brandom\b", context.question, re.I) else PASS
    notes = ["prompt mentions randomness"] if verdict == FAIL else []
    return EvaluationOutcome(verdict, notes)
