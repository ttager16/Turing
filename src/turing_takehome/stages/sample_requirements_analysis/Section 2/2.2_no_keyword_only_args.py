"""Standalone evaluator for `2.2_no_keyword_only_args`.

Requirement captured:
  Ideal response avoids keyword-only arguments.

Guideline anchor:
  Ideal responses should avoid common coding patterns that make solutions brittle, confusing, or evaluator-specific.

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


COLUMN_NAME = "2.2_no_keyword_only_args"
LEGACY_KEY = "i_no_keyword_only_args"


def evaluate(context):
    verdict = PASS if context.ideal_signature['kwonly'] == 0 else FAIL
    return EvaluationOutcome(verdict, [])
