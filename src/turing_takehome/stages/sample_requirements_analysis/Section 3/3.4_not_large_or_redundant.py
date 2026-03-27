"""Standalone evaluator for `3.4_not_large_or_redundant`.

Requirement captured:
  Test set is not overly large or redundant.

Guideline anchor:
  Test suites should avoid unnecessary redundancy or bloat.

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


COLUMN_NAME = "3.4_not_large_or_redundant"
LEGACY_KEY = "t_not_large_or_redundant"


def evaluate(context):
    total = len(context.all_tests)
    private_len = len(context.sample.row['private_test_cases'])
    verdict = PASS if total <= 30 and private_len <= 50000 else PARTIAL if total <= 60 else FAIL
    notes = [] if verdict == PASS else ["test set may be oversized or redundant"]
    return EvaluationOutcome(verdict, notes[:1])
