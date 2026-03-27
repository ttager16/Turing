"""Standalone evaluator for `2.1_deterministic_solution`.

Requirement captured:
  Ideal response avoids random or time-based nondeterministic behavior.

Guideline anchor:
  Ideal responses should be clean, deterministic, and structured without unnecessary complexity or hidden state.

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


COLUMN_NAME = "2.1_deterministic_solution"
LEGACY_KEY = "i_deterministic_solution"


def evaluate(context):
    verdict = FAIL if re.search(r"\b(random|time\.time|datetime\.now|uuid)\b", context.ideal_clean, re.I) else PASS
    return EvaluationOutcome(verdict, [])
