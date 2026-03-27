from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TestCase:
    visibility: str
    case_index: int
    input_text: str
    output_text: str
    testtype: str


@dataclass(frozen=True)
class SampleRecord:
    index: int
    row: dict[str, Any]
    metadata: dict[str, Any]
    question_content: str
    starter_code: str
    ideal_response: str
    public_tests: list[TestCase]
    private_tests: list[TestCase]

    @property
    def function_name(self) -> str:
        return str(self.metadata.get("func_name", "")).strip()

    @property
    def all_tests(self) -> list[TestCase]:
        return [*self.public_tests, *self.private_tests]


def parse_indices_arg(raw: str | None) -> list[int] | None:
    if not raw:
        return None
    raw_path = Path(raw)
    if raw_path.exists() and raw_path.is_file():
        raw = ",".join(
            line.strip()
            for line in raw_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    values: list[int] = []
    for piece in raw.split(","):
        part = piece.strip()
        if not part:
            continue
        values.append(int(part))
    return values or None


def load_samples(
    jsonl_path: Path,
    *,
    limit: int | None = None,
    offset: int = 0,
    indices: str | None = None,
) -> list[SampleRecord]:
    rows_text = [
        line for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    explicit_indices = parse_indices_arg(indices)
    if explicit_indices is not None:
        selected_pairs = [(index, rows_text[index]) for index in explicit_indices]
    else:
        selected = rows_text[offset:]
        if limit is not None:
            selected = selected[:limit]
        selected_pairs = list(enumerate(selected, start=offset))
    return [parse_sample(row_text, index) for index, row_text in selected_pairs]


def parse_sample(row_text: str, index: int) -> SampleRecord:
    row = json.loads(row_text)
    metadata = json.loads(row["metadata"])
    return SampleRecord(
        index=index,
        row=row,
        metadata=metadata,
        question_content=row["question_content"],
        starter_code=row["starter_code"],
        ideal_response=row["ideal_response"],
        public_tests=_parse_tests(row["public_test_cases"], "public"),
        private_tests=_parse_tests(row["private_test_cases"], "private"),
    )


def _parse_tests(raw: str, visibility: str) -> list[TestCase]:
    payload = json.loads(raw)
    return [
        TestCase(
            visibility=visibility,
            case_index=index,
            input_text=str(item.get("input", "")),
            output_text=str(item.get("output", "")),
            testtype=str(item.get("testtype", "")),
        )
        for index, item in enumerate(payload)
    ]
