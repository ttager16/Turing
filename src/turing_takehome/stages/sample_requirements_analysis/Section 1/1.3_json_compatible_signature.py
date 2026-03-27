"""Standalone evaluator for `1.3_json_compatible_signature`.

Requirement captured:
  Prompt function signature uses JSON-compatible types only; no tuples, sets, or non-string dict keys.

Guideline anchor:
  Prompt signatures should stay JSON-compatible so the task can be exercised and validated mechanically.

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


COLUMN_NAME = "1.3_json_compatible_signature"
LEGACY_KEY = "p_json_compatible_signature"


def evaluate(context):
    signature_source = context.prompt_signature_block or context.sample.starter_code
    verdict = FAIL if context.prompt_signature_block is None and not re.search(r"def\s+\w+\s*\(", context.sample.starter_code) else FAIL if context.prompt_signature_block and signature_has_disallowed_types(signature_source) else PASS
    notes = ["prompt signature uses non-JSON-compatible types"] if verdict == FAIL and context.prompt_signature_block else []
    return EvaluationOutcome(verdict, notes)
