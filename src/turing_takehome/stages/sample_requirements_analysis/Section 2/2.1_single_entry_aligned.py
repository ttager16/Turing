"""Standalone evaluator for `2.1_single_entry_aligned`.

Requirement captured:
  Ideal response exposes a single entry point aligned with the prompt signature.

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


COLUMN_NAME = "2.1_single_entry_aligned"
LEGACY_KEY = "i_single_entry_aligned"


def evaluate(context):
    func_name = context.sample.metadata.get('func_name')
    verdict = PASS if func_name and func_name in context.ideal_clean else PARTIAL
    notes = [] if verdict == PASS else ["ideal response entry point is only weakly aligned with metadata"]
    return EvaluationOutcome(verdict, notes)
