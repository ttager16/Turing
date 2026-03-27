"""Standalone evaluator for `3.1_single_call_per_test`.

Requirement captured:
  Each test corresponds to exactly one call of the entry function.

Guideline anchor:
  Each test should have a clear purpose and correspond cleanly to the intended sample behavior.

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


COLUMN_NAME = "3.1_single_call_per_test"
LEGACY_KEY = "t_single_call_per_test"


def evaluate(context):
    arity = context.starter_signature['total_args']
    arg_counts = context.arg_counts
    ratio = (sum(1 for count in arg_counts if count == arity) / len(arg_counts)) if arg_counts and arity else 0.0
    verdict = PASS if ratio == 1.0 else PARTIAL if ratio >= 0.5 else FAIL
    return EvaluationOutcome(verdict, [])
