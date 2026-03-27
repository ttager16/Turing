"""Standalone evaluator for `6.1_entry_name_consistent`.

Requirement captured:
  Prompt, metadata, starter code, and ideal response use the same entry-point name.

Guideline anchor:
  A valid model breaker only tests behavior that is truly defined and aligned across prompt, tests, and solution.

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


COLUMN_NAME = "6.1_entry_name_consistent"
LEGACY_KEY = "v_entry_name_consistent"


def evaluate(context):
    names = [name for name in [context.sample.metadata.get('func_name'), context.prompt_signature_name, context.starter_name, context.ideal_name] if name]
    unique_names = set(names)
    verdict = PASS if len(unique_names) == 1 else PARTIAL if len(unique_names) == 2 else FAIL
    notes = [] if verdict == PASS else ["entry-point names are inconsistent across prompt, starter, metadata, or solution"]
    return EvaluationOutcome(verdict, notes[:1])
