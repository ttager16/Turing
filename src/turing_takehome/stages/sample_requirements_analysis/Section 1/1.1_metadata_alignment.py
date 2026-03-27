"""Standalone evaluator for `1.1_metadata_alignment`.

Requirement captured:
  Problem aligns with task metadata such as function name and topic.

Guideline anchor:
  Prompts should define a clear contract: what the task is, what comes in, what comes out, and what constraints or edge conditions matter.

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


COLUMN_NAME = "1.1_metadata_alignment"
LEGACY_KEY = "p_metadata_alignment"


def evaluate(context):
    func_name = str(context.sample.metadata.get("func_name", "")).strip()
    prompt_name = context.prompt_signature_name or ""
    starter_name = context.starter_name or ""
    ideal_name = context.ideal_name or ""
    names = [name for name in [func_name, prompt_name, starter_name, ideal_name] if name]
    unique_names = set(names)
    q = context.question.lower()
    if not func_name:
        return EvaluationOutcome(UNCLEAR, [])
    if len(unique_names) >= 3:
        return EvaluationOutcome(FAIL, ["function naming drifts across metadata, prompt, starter, or solution"])
    if len(unique_names) == 2 or func_name.lower() not in q:
        return EvaluationOutcome(PARTIAL, ["function name is only partially aligned across artifacts"])
    return EvaluationOutcome(PASS, [])
