"""Standalone evaluator for `1.1_not_verbose`.

Requirement captured:
  Prompt avoids unnecessary verbosity.

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


COLUMN_NAME = "1.1_not_verbose"
LEGACY_KEY = "p_not_verbose"


def evaluate(context):
    q = context.question
    word_count = len(q.split())
    heading_count = len(re.findall(r"^#+\s|^[-*]\s|^\d+\.", q, re.M))
    if word_count > 1700 or (word_count > 1300 and heading_count > 18):
        return EvaluationOutcome(FAIL, [f"prompt is overly long for benchmark use ({word_count} words)"])
    if word_count < 950:
        return EvaluationOutcome(PASS, [])
    prompt = f'''Judge whether this coding prompt is unnecessarily verbose for benchmark use.
    Use PASS for concise prompts, PARTIAL for somewhat bloated prompts that remain usable, and FAIL for prompts where verbosity materially obscures the contract.
    Word count: {word_count}
    Sample:
    {q[:9000]}'''
    llm = context.llm_judge(COLUMN_NAME, prompt)
    verdict = llm["verdict"]
    if word_count > 1200 and verdict == PASS:
        verdict = PARTIAL
    notes = [llm["note"]] if verdict != PASS and llm["note"] else []
    if verdict != PASS and not notes:
        notes = [f"prompt is longer than needed for a benchmark task ({word_count} words)"]
    return EvaluationOutcome(verdict, notes[:1])
