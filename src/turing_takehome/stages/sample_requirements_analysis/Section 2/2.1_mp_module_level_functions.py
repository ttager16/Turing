"""Standalone evaluator for `2.1_mp_module_level_functions`.

Requirement captured:
  If multiprocessing is used, worker functions must be defined at module level.

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


COLUMN_NAME = "2.1_mp_module_level_functions"
LEGACY_KEY = "i_mp_module_level_functions"


def evaluate(context):
    uses_mp = bool(re.search(r"\bmultiprocessing\b|Pool\s*\(", context.ideal_clean))
    if not uses_mp:
        return EvaluationOutcome(NA, [])
    verdict = FAIL if re.search(r"^\s{4,}def\s+\w+\s*\(", context.ideal_clean, re.M) else PASS
    return EvaluationOutcome(verdict, [])
