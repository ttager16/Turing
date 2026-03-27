from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from textwrap import shorten


STAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = STAGE_DIR.parents[3]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
OUTPUTS_DIR = PROJECT_ROOT / "outputs" / "sample_requirements_analysis"

if str(STAGE_DIR) not in sys.path:
    sys.path.insert(0, str(STAGE_DIR))

from audit_core import schema
from audit_core.artifacts import prepare_output_path
from audit_core.collector import collect_contexts
from audit_core.workbook import build_summary_rows, merge_section_rows, write_workbook


def load_run_callable(module_path: Path):
    spec = importlib.util.spec_from_file_location(module_path.stem, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run


def load_module(module_path: Path):
    spec = importlib.util.spec_from_file_location(module_path.stem, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def resolve_column_module(base_dir: Path, column_name: str) -> tuple[Path, object]:
    for key in schema.DETAILED_KEYS:
        display_name = schema.display_name(key)
        if column_name in {key, display_name}:
            section_dir = base_dir / schema.section_folder_name(schema.SECTION_MAP[key][0])
            module_path = section_dir / f"{display_name}.py"
            return module_path, load_module(module_path)
    raise ValueError(
        f"Unknown column '{column_name}'. Use a display name like "
        "'6.1_prompt_test_solution_aligned' or a legacy key."
    )


def write_single_column_report(report_path: Path, module, contexts) -> None:
    lines = [
        f"# Single Column Report: {module.COLUMN_NAME}",
        "",
        f"Legacy key: `{module.LEGACY_KEY}`",
        f"Samples evaluated: {len(contexts)}",
        "",
        "| Index | Question Id | Difficulty | Function | Verdict | Notes |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for context in contexts:
        outcome = module.evaluate(context)
        note_text = "; ".join(
            shorten(note.replace("\n", " ").strip(), width=220, placeholder="...")
            for note in outcome.notes
            if note
        ).replace("|", "/")
        lines.append(
            "| {index} | {question_id} | {difficulty} | {function_name} | {verdict} | {notes} |".format(
                index=context.sample.index,
                question_id=context.sample.row["question_id"],
                difficulty=context.sample.row["difficulty"],
                function_name=context.sample.metadata.get("func_name", ""),
                verdict=outcome.verdict,
                notes=note_text,
            )
        )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the Sample Requirements Analysis auditor."
    )
    parser.add_argument(
        "--jsonl",
        type=Path,
        default=ARTIFACTS_DIR / "provided" / "Samples.jsonl",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUTS_DIR,
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--indices", default=None)
    parser.add_argument("--trace-dir", type=Path, default=None)
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument(
        "--column",
        default=None,
        help="Run only one column evaluator by display name or legacy key.",
    )
    parser.add_argument(
        "--report-name",
        default="single_column_report.md",
        help="Filename for single-column disposable report mode.",
    )
    return parser


def run_cli(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_dir = args.output_dir if args.output_dir.is_absolute() else (PROJECT_ROOT / args.output_dir)
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    contexts = collect_contexts(args)
    if args.column:
        _, module = resolve_column_module(STAGE_DIR, args.column)
        report_path = prepare_output_path(output_dir, args.report_name)
        write_single_column_report(report_path, module, contexts)
        print(f"Wrote single-column report to {report_path}")
        return 0

    detailed_chunks = []
    subsection_chunks = []
    for section_number in schema.SECTION_NUMBERS:
        section_dir = STAGE_DIR / schema.section_folder_name(section_number)
        run_callable = load_run_callable(section_dir / f"section_{section_number}_main.py")
        detailed_rows, subsection_rows = run_callable(contexts)
        detailed_chunks.append(detailed_rows)
        subsection_chunks.append(subsection_rows)

    detailed_rows = merge_section_rows(detailed_chunks)
    subsection_rows = merge_section_rows(subsection_chunks)
    summary_rows = build_summary_rows(detailed_rows)

    workbook_path = prepare_output_path(output_dir, schema.OUTPUT_WORKBOOK_NAME)
    write_workbook(detailed_rows, subsection_rows, summary_rows, workbook_path)

    print(f"Wrote workbook to {workbook_path}")
    return 0
