"""Standalone evaluator for `3.3_optional_values_included`.

Requirement captured:
  If the entry point has optional or default parameters, tests still provide all input values.

Guideline anchor:
  Test inputs and outputs should follow the required JSON-string format consistently.

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


COLUMN_NAME = "3.3_optional_values_included"
LEGACY_KEY = "t_optional_values_included"


def evaluate(context):
    if context.starter_signature['defaulted_args'] <= 0:
        return EvaluationOutcome(NA, [])
    ratio = (sum(1 for count in context.arg_counts if count == context.starter_signature['total_args']) / len(context.arg_counts)) if context.arg_counts else 0.0
    verdict = PASS if ratio == 1.0 else PARTIAL if ratio >= 0.5 else FAIL
    return EvaluationOutcome(verdict, [])
