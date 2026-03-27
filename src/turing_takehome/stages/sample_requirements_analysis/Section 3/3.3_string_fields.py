"""Standalone evaluator for `3.3_string_fields`.

Requirement captured:
  Each test case uses string-valued input, output, and testtype fields, not nested objects.

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


COLUMN_NAME = "3.3_string_fields"
LEGACY_KEY = "t_string_fields"


def evaluate(context):
    verdict = PASS if all(all(isinstance(test.get(field), str) for field in ('input', 'output', 'testtype')) for test in context.all_tests) else FAIL
    return EvaluationOutcome(verdict, [])
