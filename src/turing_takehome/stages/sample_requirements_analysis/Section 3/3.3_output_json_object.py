"""Standalone evaluator for `3.3_output_json_object`.

Requirement captured:
  Each test output is a stringified JSON object.

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


COLUMN_NAME = "3.3_output_json_object"
LEGACY_KEY = "t_output_json_object"


def evaluate(context):
    summary = context.test_summary
    ratio = 1 - (summary['non_object_outputs'] / max(len(context.all_tests), 1))
    verdict = verdict_from_ratio(ratio, 1.0, 0.5)
    notes = ["many test outputs are scalars or lists rather than JSON objects"] if summary['non_object_outputs'] else []
    return EvaluationOutcome(verdict, notes[:1])
