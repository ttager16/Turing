from __future__ import annotations

import importlib.util
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from types import ModuleType
from typing import Any

from . import schema
from .requirements import FAIL, NA, PARTIAL, PASS, UNCLEAR


VERDICT_SCORE = {PASS: 1.0, PARTIAL: 0.5, UNCLEAR: 0.25, FAIL: 0.0}


def load_module_from_path(module_path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_path.stem.replace(".", "_"), module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_section_column_modules(section_folder: Path) -> list[ModuleType]:
    modules: list[ModuleType] = []
    for module_path in sorted(section_folder.glob("*.py")):
        if module_path.name.startswith("section_"):
            continue
        modules.append(load_module_from_path(module_path))
    order = {key: index for index, key in enumerate(schema.DETAILED_KEYS)}
    return sorted(modules, key=lambda module: order.get(module.LEGACY_KEY, 10_000))


def run_section(section_number: str, section_folder: Path, contexts) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    modules = load_section_column_modules(section_folder)
    keys = [module.LEGACY_KEY for module in modules]
    grouped: dict[str, list[str]] = defaultdict(list)
    for key in keys:
        grouped[schema.SECTION_MAP[key][1]].append(key)

    detailed_rows: list[dict[str, Any]] = []
    subsection_rows: list[dict[str, Any]] = []
    detailed_rows_by_index: dict[int, dict[str, Any]] = {}
    raw_results_by_index: dict[int, dict[str, str]] = {context.sample.index: {} for context in contexts}

    for context in contexts:
        detailed_rows_by_index[context.sample.index] = {
            "Index": context.sample.index,
            "Question_Id": context.sample.row["question_id"],
            "Question_Title": context.sample.row["question_title"],
            "Difficulty": context.sample.row["difficulty"],
            "Function_Name": context.sample.metadata.get("func_name", ""),
            "Runtime_Pass_Rate": context.runtime_pass_rate,
        }

    with ThreadPoolExecutor(max_workers=min(8, max(1, len(contexts)))) as executor:
        for module in modules:
            future_map = {
                executor.submit(module.evaluate, context): context.sample.index
                for context in contexts
            }
            for future in as_completed(future_map):
                sample_index = future_map[future]
                outcome = future.result()
                raw_results_by_index[sample_index][module.LEGACY_KEY] = outcome.verdict
                detailed_rows_by_index[sample_index][module.COLUMN_NAME] = outcome.verdict
                detailed_rows_by_index[sample_index][f"Notes-{module.COLUMN_NAME}"] = _format_note_text(outcome.notes)

    for context in contexts:
        detailed_rows.append(detailed_rows_by_index[context.sample.index])
        raw_results = raw_results_by_index[context.sample.index]
        subsection_row = {
            "Index": context.sample.index,
            "Question_Id": context.sample.row["question_id"],
            "Question_Title": context.sample.row["question_title"],
            "Difficulty": context.sample.row["difficulty"],
            "Function_Name": context.sample.metadata.get("func_name", ""),
            "Runtime_Pass_Rate": context.runtime_pass_rate,
        }
        for subsection_name in sorted(grouped, key=schema.section_sort_key):
            subsection_keys = grouped[subsection_name]
            values = [VERDICT_SCORE[raw_results[key]] for key in subsection_keys if raw_results.get(key) in VERDICT_SCORE]
            if values:
                subsection_row[subsection_name] = sum(values) / len(values)
            elif all(raw_results.get(key) == NA for key in subsection_keys):
                subsection_row[subsection_name] = NA
            elif any(raw_results.get(key) == UNCLEAR for key in subsection_keys):
                subsection_row[subsection_name] = UNCLEAR
            else:
                subsection_row[subsection_name] = None
        subsection_rows.append(subsection_row)
    return detailed_rows, subsection_rows


def _format_note_text(notes: list[str]) -> str:
    clean_notes: list[str] = []
    for note in notes:
        clean = str(note).replace("\n", " ").strip()
        if clean and clean not in clean_notes:
            clean_notes.append(clean)
    return "; ".join(clean_notes[:2])
