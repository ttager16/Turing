"""Standalone evaluator for `3.1_public_test1_matches_prompt_example`.

Requirement captured:
  If the prompt includes sample I/O, public test case 1 should correspond to it.

Guideline anchor:
  Each test should have a clear purpose and correspond cleanly to the intended sample behavior.

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


COLUMN_NAME = "3.1_public_test1_matches_prompt_example"
LEGACY_KEY = "t_public_test1_matches_prompt_example"


def evaluate(context):
    q = context.question
    if not re.search(r"sample input|sample output|## Example|Example", q, re.I):
        return EvaluationOutcome(NA, [])
    if not context.sample.public_tests:
        return EvaluationOutcome(FAIL, ["prompt includes an example but no public tests are available"])
    sample_input_match = re.search(r"Sample Input\s*```(?:python)?\s*(.*?)```", q, re.S | re.I)
    sample_output_match = re.search(r"Sample Output\s*```(?:python)?\s*(.*?)```", q, re.S | re.I)
    if not sample_input_match or not sample_output_match:
        example_blocks = re.findall(r"Example.*?```(?:python)?\s*(.*?)```", q, re.S | re.I)
        if len(example_blocks) >= 2:
            sample_input = example_blocks[0].strip()
            sample_output = example_blocks[1].strip()
        else:
            return EvaluationOutcome(UNCLEAR, ["prompt example exists but could not be extracted reliably"])
    else:
        sample_input = sample_input_match.group(1).strip()
        sample_output = sample_output_match.group(1).strip()
    def normalize(raw: str) -> str:
        return re.sub(r"\s+", "", raw.strip().replace("\r", ""))
    public0 = context.sample.public_tests[0]
    input_match = normalize(sample_input) == normalize(str(public0.get("input", "")))
    output_match = normalize(sample_output) == normalize(str(public0.get("output", "")))
    verdict = PASS if input_match and output_match else PARTIAL if input_match or output_match else FAIL
    notes = [] if verdict == PASS else ["public test 1 does not cleanly match the prompt's sample I/O"]
    return EvaluationOutcome(verdict, notes[:1])
