"""Standalone evaluator for `7_no_classes`.

Requirement captured:
  Starter code contains no class definitions.

Guideline anchor:
  Starter code should stay minimal and should not leak implementation logic.

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


COLUMN_NAME = "7_no_classes"
LEGACY_KEY = "s_no_classes"


def evaluate(context):
    verdict = PASS if not context.starter_signature['class_defs'] else FAIL
    return EvaluationOutcome(verdict, [])
