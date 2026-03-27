"""Standalone evaluator for `7_only_entry_signature`.

Requirement captured:
  Starter code contains only the main entry-point function signature.

Guideline anchor:
  Starter code should stay minimal and should not leak implementation logic.

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


COLUMN_NAME = "7_only_entry_signature"
LEGACY_KEY = "s_only_entry_signature"


def evaluate(context):
    sig = context.starter_signature
    lines = [line.strip() for line in context.starter_clean.splitlines() if line.strip()]
    extra_lines = [line for line in lines if not (line.startswith('import ') or line.startswith('from ') or line.startswith('def ') or line in {'pass', '...'} or line.startswith('"""') or line.startswith("'''"))]
    verdict = PASS if len(sig['func_defs']) == 1 and not sig['class_defs'] and not extra_lines else PARTIAL if len(sig['func_defs']) == 1 else FAIL
    notes = ["starter contains extra implementation or detail lines"] if extra_lines else []
    return EvaluationOutcome(verdict, notes[:1])
