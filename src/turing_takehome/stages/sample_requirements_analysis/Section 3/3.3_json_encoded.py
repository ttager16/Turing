"""Standalone evaluator for `3.3_json_encoded`.

Requirement captured:
  Public and private test collections are valid JSON and each case has input, output, and testtype fields.

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


COLUMN_NAME = "3.3_json_encoded"
LEGACY_KEY = "t_json_encoded"


def evaluate(context):
    verdict = PASS if all(isinstance(test, dict) and {'input', 'output', 'testtype'} <= set(test) for test in context.all_tests) else FAIL
    return EvaluationOutcome(verdict, [])
