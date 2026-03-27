"""Standalone evaluator for `6.2_no_extra_parameters`.

Requirement captured:
  Tests do not add extra parameters beyond the prompt signature.

Guideline anchor:
  Hidden rules, extra parameters, or unprompted implementation assumptions make a sample invalid as a model breaker.

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


COLUMN_NAME = "6.2_no_extra_parameters"
LEGACY_KEY = "v_no_extra_parameters"


def evaluate(context):
    arity = context.starter_signature['total_args']
    verdict = FAIL if any(count > arity for count in context.arg_counts) else PASS
    notes = ["tests pass extra parameters beyond the starter signature"] if verdict == FAIL else []
    return EvaluationOutcome(verdict, notes)
