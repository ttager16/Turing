"""Standalone evaluator for `3.2_recommended_15_20_total`.

Requirement captured:
  Sample has approximately 15 to 20 total tests.

Guideline anchor:
  Test suites should be large enough, deterministic, and focused on the defined entry function.

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


COLUMN_NAME = "3.2_recommended_15_20_total"
LEGACY_KEY = "t_recommended_15_20_total"


def evaluate(context):
    total = len(context.all_tests)
    verdict = PASS if 15 <= total <= 20 else PARTIAL if 10 <= total <= 30 else FAIL
    return EvaluationOutcome(verdict, [])
