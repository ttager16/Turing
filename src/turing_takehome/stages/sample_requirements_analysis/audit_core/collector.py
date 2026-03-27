from __future__ import annotations

import argparse
from pathlib import Path

from turing_takehome.llm import StageName

from .context import EvaluationContext, parse_sample


def parse_indices_arg(raw: str | None) -> list[int] | None:
    if not raw:
        return None
    raw_path = Path(raw)
    if raw_path.exists() and raw_path.is_file():
        raw = ",".join(line.strip() for line in raw_path.read_text(encoding="utf-8").splitlines() if line.strip())
    values: list[int] = []
    for piece in raw.split(","):
        part = piece.strip()
        if not part:
            continue
        values.append(int(part))
    return values or None


def collect_contexts(args: argparse.Namespace) -> list[EvaluationContext]:
    rows_text = [line for line in args.jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]
    explicit_indices = parse_indices_arg(args.indices)
    if explicit_indices is not None:
        selected_pairs = [(index, rows_text[index]) for index in explicit_indices]
    else:
        selected = rows_text[args.offset:]
        if args.limit is not None:
            selected = selected[: args.limit]
        selected_pairs = list(enumerate(selected, start=args.offset))

    contexts: list[EvaluationContext] = []
    stage_name: StageName = "sample-requirements-analysis"
    for index, row_text in selected_pairs:
        sample = parse_sample(row_text, index)
        sample_trace_dir = None if args.trace_dir is None else Path(args.trace_dir) / f"sample_{index}"
        contexts.append(
            EvaluationContext(
                sample=sample,
                stage_name=stage_name,
                use_llm=not args.no_llm,
                trace_dir=sample_trace_dir,
            )
        )
    return contexts
