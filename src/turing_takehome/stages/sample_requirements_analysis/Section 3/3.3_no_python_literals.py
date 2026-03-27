"""Standalone evaluator for `3.3_no_python_literals`.

Requirement captured:
  Tests avoid Python literals such as True, False, None, or single-quoted pseudo-JSON.

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


COLUMN_NAME = "3.3_no_python_literals"
LEGACY_KEY = "t_no_python_literals"


def evaluate(context):
    verdict = FAIL if context.test_summary['py_literal_hits'] else PASS
    return EvaluationOutcome(verdict, [])
