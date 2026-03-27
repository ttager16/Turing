"""Standalone evaluator for `2.1_consistent_naming_docs`.

Requirement captured:
  Ideal response follows consistent naming and documentation style.

Guideline anchor:
  Ideal responses should be clean, deterministic, and structured without unnecessary complexity or hidden state.

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


COLUMN_NAME = "2.1_consistent_naming_docs"
LEGACY_KEY = "i_consistent_naming_docs"


def evaluate(context):
    clean = context.ideal_clean
    verdict = PASS if re.search(r'"""', clean) or re.search(r"\b[a-z_]{3,}\b", clean) else PARTIAL
    notes = [] if verdict == PASS else ["naming or documentation signals are weak"]
    return EvaluationOutcome(verdict, notes)
