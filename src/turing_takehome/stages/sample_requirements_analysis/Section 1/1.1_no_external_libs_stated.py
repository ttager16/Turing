"""Standalone evaluator for `1.1_no_external_libs_stated`.

Requirement captured:
  Prompt states that only Python standard library is allowed or no external libraries.

Guideline anchor:
  Prompts should define a clear contract: what the task is, what comes in, what comes out, and what constraints or edge conditions matter.

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


COLUMN_NAME = "1.1_no_external_libs_stated"
LEGACY_KEY = "p_no_external_libs_stated"


def evaluate(context):
    q = context.question
    if re.search(r"numpy|pandas|scipy|tensorflow|torch|sklearn", q, re.I):
        return EvaluationOutcome(FAIL, ["prompt appears to rely on non-stdlib libraries"])
    verdict = PASS if re.search(r"no external libr|standard libr|pure python only", q, re.I) else PARTIAL
    notes = [] if verdict == PASS else ["prompt does not explicitly restate the stdlib-only constraint"]
    return EvaluationOutcome(verdict, notes[:1])
