"""Standalone evaluator for `3.2_entry_function_only`.

Requirement captured:
  Tests target only the prompt-defined entry-point function.

Guideline anchor:
  Test suites should be large enough, deterministic, and focused on the defined entry function.

Evaluation logic:
  This file contains the operative scoring logic for this single column. The section
  runner only calls `evaluate(context)` and records the returned verdict and notes.

Subjectivity and failure modes:
  This requirement uses explicit deterministic signals, but the class boundaries still embed judgment. The file documents the rule set and any thresholds used. Known failure modes include brittle keyword matching and edge cases where a human reviewer might set a different boundary.
"""

from __future__ import annotations

import json
import re

from audit_core.context import signature_has_disallowed_types, verdict_from_ratio
from audit_core.requirements import EvaluationOutcome, FAIL, NA, PARTIAL, PASS, UNCLEAR


COLUMN_NAME = "3.2_entry_function_only"
LEGACY_KEY = "t_entry_function_only"


def evaluate(context):
    verdict = PASS if context.sample.metadata.get('func_name') else UNCLEAR
    return EvaluationOutcome(verdict, [])
