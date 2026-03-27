"""Standalone evaluator for `1.2_difficulty_balanced`.

Requirement captured:
  Prompt constraints align with intended difficulty.

Guideline anchor:
  Prompts should describe practical, realistic, well-scoped algorithmic work rather than vague or inflated scenarios.

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


COLUMN_NAME = "1.2_difficulty_balanced"
LEGACY_KEY = "p_difficulty_balanced"


def evaluate(context):
    q = context.question
    difficulty = str(context.sample.row.get("difficulty", "")).lower()
    word_count = len(q.split())
    advanced_hits = len(re.findall(r"segment tree|heavy-light decomposition|trie|alpha-beta|iterative deepening|union-find|backtracking|concurrent|thread|lock|real-time|fault tolerance|distributed|multi-phase", q, re.I))
    if difficulty == "easy":
        verdict = FAIL if advanced_hits >= 3 or word_count > 1000 else PARTIAL if advanced_hits >= 2 or word_count > 750 else PASS
    elif difficulty == "medium":
        verdict = FAIL if advanced_hits >= 6 or word_count > 1500 else PARTIAL if advanced_hits >= 4 or word_count > 1100 else PASS
    elif difficulty == "hard":
        verdict = FAIL if word_count < 220 and advanced_hits == 0 else PARTIAL if (advanced_hits <= 1 and word_count < 320) or word_count > 1800 else PASS
    else:
        verdict = PARTIAL
    notes = [] if verdict == PASS else ["difficulty label and specification burden are not well matched"]
    return EvaluationOutcome(verdict, notes[:1])
