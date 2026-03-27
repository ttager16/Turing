"""Standalone evaluator for `1.1_realistic_context`.

Requirement captured:
  Prompt uses a real-world or realistic problem context.

Guideline anchor:
  Prompts should define a clear contract: what the task is, what comes in, what comes out, and what constraints or edge conditions matter.

Evaluation logic:
  This file contains the operative scoring logic for this single column. The section
  runner only calls `evaluate(context)` and records the returned verdict and notes.

Subjectivity and failure modes:
  This requirement is materially subjective. The file contains the exact LLM prompt plus the deterministic overrides and merge policy used around that prompt. Weaknesses include model sensitivity to phrasing, prompt truncation risk, and semantic ambiguity in the sample.
"""

from __future__ import annotations

import json
import re

from audit_core.context import signature_has_disallowed_types, verdict_from_ratio
from audit_core.requirements import EvaluationOutcome, FAIL, NA, PARTIAL, PASS, UNCLEAR


COLUMN_NAME = "1.1_realistic_context"
LEGACY_KEY = "p_realistic_context"


def evaluate(context):
    q = context.question
    inflation_hits = re.findall(r"microsecond|nanosecond|ultra-fast|extreme load|fault tolerance|thread safety|lock-free|heavy-light decomposition|segment tree|trie|abc\b|distributed signal tracking|real-time", q, re.I)
    if len(inflation_hits) >= 4:
        return EvaluationOutcome(FAIL, ["prompt context is inflated beyond a realistic benchmark scenario"])
    prompt = f'''Judge whether this coding prompt uses a realistic engineering or data-problem context.
    Return PASS for a believable, grounded context, PARTIAL for a somewhat inflated but still recognizable context, and FAIL for speculative or unrealistic framing.
    Sample:
    {q[:9000]}'''
    llm = context.llm_judge(COLUMN_NAME, prompt)
    verdict = llm["verdict"]
    notes = [llm["note"]] if llm["verdict"] != PASS and llm["note"] else []
    if len(inflation_hits) >= 2 and verdict == PASS:
        verdict = PARTIAL
    if re.search(r"microsecond|nanosecond|ultra-fast|extreme load", q, re.I):
        notes.insert(0, "prompt uses unrealistic performance framing")
    return EvaluationOutcome(verdict, notes[:2])
