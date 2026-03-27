from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from turing_takehome.llm import get_stage_model_label

from audit_core.legacy import evaluate_guideline as legacy


@dataclass
class SampleContext:
    """Shared evaluation state for one sample.

    The refactor keeps the proven evaluator as the scoring backend for now so
    the split section files can stay thin and auditable while still producing
    identical requirement values. Each per-column file reads its own verdict
    from this context, and any subjective logic notes point back to the merged
    deterministic plus LLM pipeline embodied here.
    """

    index: int
    sample: dict[str, Any]
    runtime: dict[str, Any]
    verdicts: dict[str, str]
    notes: list[str]
    row: dict[str, Any]


def parse_indices_arg(raw: str | None) -> list[int] | None:
    return legacy.parse_indices_arg(raw)


def build_context(sample: dict[str, Any], use_llm: bool, trace_dir: Path | None = None) -> SampleContext:
    runtime = legacy.runtime_eval(sample)
    sample["runtime_pass_rate"] = f"{runtime.get('passed', 0)}/{runtime.get('total', 0)}"
    verdicts, notes = legacy.heuristics(sample, runtime)
    llm_result = legacy.llm_semantic_eval(sample, use_llm, trace_dir=trace_dir)
    sample["llm_used"] = use_llm
    sample["llm_model"] = get_stage_model_label("sample-requirements-analysis") if use_llm else ""
    verdicts, notes = legacy.merge_verdicts(verdicts, llm_result, notes)
    row = legacy.finalize_row(sample, verdicts, notes)
    return SampleContext(index=sample["index"], sample=sample, runtime=runtime, verdicts=verdicts, notes=notes, row=row)


def collect_contexts(args: argparse.Namespace) -> list[SampleContext]:
    rows_text = [line for line in args.jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]
    explicit_indices = parse_indices_arg(args.indices)
    if explicit_indices is not None:
        selected_pairs = [(index, rows_text[index]) for index in explicit_indices]
    else:
        selected = rows_text[args.offset:]
        if args.limit is not None:
            selected = selected[: args.limit]
        selected_pairs = list(enumerate(selected, start=args.offset))

    contexts: list[SampleContext] = []
    for index, row_text in selected_pairs:
        sample = legacy.parse_sample(row_text, index)
        sample_trace_dir = None if args.trace_dir is None else args.trace_dir / f"sample_{index}"
        contexts.append(build_context(sample, not args.no_llm, trace_dir=sample_trace_dir))
    return contexts
