"""Standalone evaluator for `1.1_function_signature_present`.

Requirement captured:
  Prompt contains a concrete, testable function signature.

Guideline anchor:
  Prompts should define a clear contract: what the task is, what comes in, what comes out, and what constraints or edge conditions matter.

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


COLUMN_NAME = "1.1_function_signature_present"
LEGACY_KEY = "p_function_signature_present"


def evaluate(context):
    verdict = PASS if re.search(r"def\s+\w+\s*\(", context.question) else FAIL
    return EvaluationOutcome(verdict, [])
