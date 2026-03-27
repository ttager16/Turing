"""Standalone evaluator for `2.1_no_globals`.

Requirement captured:
  Ideal response avoids global variables and mutable shared state.

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


COLUMN_NAME = "2.1_no_globals"
LEGACY_KEY = "i_no_globals"


def evaluate(context):
    mutable_globals = re.findall(r"^[a-z_][a-z0-9_]*\s*=\s*(\{|\[|set\(|defaultdict\(|dict\(|list\()", context.ideal_clean, re.M)
    constant_globals = re.findall(r"^[A-Z_][A-Z0-9_]*\s*=", context.ideal_clean, re.M)
    if mutable_globals:
        return EvaluationOutcome(FAIL, ["ideal response defines module-level mutable state"])
    verdict = PARTIAL if len(constant_globals) >= 4 else PASS
    notes = [] if verdict == PASS else ["ideal response relies on many module-level constants"]
    return EvaluationOutcome(verdict, notes[:1])
