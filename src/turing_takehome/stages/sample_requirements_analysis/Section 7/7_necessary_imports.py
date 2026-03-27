"""Standalone evaluator for `7_necessary_imports`.

Requirement captured:
  Starter code includes necessary import statements for referenced typing or library symbols.

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


COLUMN_NAME = "7_necessary_imports"
LEGACY_KEY = "s_necessary_imports"


def evaluate(context):
    starter_clean = context.starter_clean
    import_names = set()
    for match in re.finditer(r"^\s*from\s+[\w.]+\s+import\s+(.+)$", starter_clean, re.M):
        for piece in match.group(1).split(','):
            import_names.add(piece.strip().split(' as ')[0].strip())
    for match in re.finditer(r"^\s*import\s+(.+)$", starter_clean, re.M):
        for piece in match.group(1).split(','):
            import_names.add(piece.strip().split(' as ')[0].strip().split('.')[0])
    needed_names = set(re.findall(r"\b(List|Dict|Set|Tuple|Any|Optional|Union|defaultdict|heapq|math|cmath|gcd|json)\b", starter_clean))
    missing = sorted(name for name in needed_names if name not in import_names and name != 'json')
    verdict = PASS if not missing else PARTIAL
    notes = [] if not missing else [f"starter may miss imports: {', '.join(missing[:4])}"]
    return EvaluationOutcome(verdict, notes)
