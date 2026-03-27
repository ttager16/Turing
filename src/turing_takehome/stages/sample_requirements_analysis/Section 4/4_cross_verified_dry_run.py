"""Standalone evaluator for `4_cross_verified_dry_run`.

Requirement captured:
  Ideal response can be dry-run against tests without issues.

Guideline anchor:
  Validation should include concrete dry-run evidence rather than only manual inspection.

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


COLUMN_NAME = "4_cross_verified_dry_run"
LEGACY_KEY = "v_cross_verified_dry_run"


def evaluate(context):
    runtime = context.runtime
    verdict = PASS if runtime.get('total', 0) and runtime['failed'] == 0 else PARTIAL if runtime.get('passed', 0) > 0 else FAIL
    notes = [] if verdict == PASS else ([runtime['errors'][0]] if runtime.get('errors') else ["dry run did not complete cleanly"])
    return EvaluationOutcome(verdict, notes[:1])
