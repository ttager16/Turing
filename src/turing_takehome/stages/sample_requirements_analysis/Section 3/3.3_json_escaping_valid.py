"""Standalone evaluator for `3.3_json_escaping_valid`.

Requirement captured:
  Test I/O strings use valid escaping, braces, and double-quoted JSON when object-formatted.

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


COLUMN_NAME = "3.3_json_escaping_valid"
LEGACY_KEY = "t_json_escaping_valid"


def evaluate(context):
    total = 0
    good = 0
    for test in context.all_tests:
        for field in ('input', 'output'):
            raw = str(test[field]).strip()
            if raw.startswith('{'):
                total += 1
                try:
                    json.loads(raw)
                    good += 1
                except Exception:
                    pass
    verdict = PASS if total == good else PARTIAL if good > 0 else FAIL if total > 0 else NA
    return EvaluationOutcome(verdict, [])
