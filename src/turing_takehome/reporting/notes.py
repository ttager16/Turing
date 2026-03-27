from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from turing_takehome.llm import (
    AsyncTaskSpec,
    get_stage_primary_target_name,
    run_async_tasks_sync,
)

NOTE_CACHE_VERSION = "notes-cache-v2"
NOTES_SYSTEM_PROMPT = (
    "You write extremely concise benchmark-audit notes. "
    "Return JSON only. Prefer a short phrase. Use a full sentence only when needed."
)

NOTES_SCHEMA = {
    "type": "object",
    "properties": {
        "notes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "column": {"type": "string"},
                    "note": {"type": "string"},
                },
                "required": ["column", "note"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["notes"],
    "additionalProperties": False,
}


def generate_notes_for_requests(
    stage_name: str,
    requests: list[dict[str, Any]],
    *,
    max_concurrency: int = 8,
    trace_dir: Path | None = None,
) -> dict[str, dict[str, str]]:
    if not requests:
        return {}
    target_name = get_stage_primary_target_name(stage_name)  # type: ignore[arg-type]
    task_specs: list[AsyncTaskSpec] = []
    for request in requests:
        request_id = str(request["request_id"])
        prompt = str(request["prompt"])
        request_trace_dir = None if trace_dir is None else trace_dir / request_id.replace(":", "_")
        task_specs.append(
            AsyncTaskSpec(
                request_id=request_id,
                task_type="json",
                kwargs={
                    "target_name": target_name,
                    "schema_name": "brief_test_notes",
                    "schema": NOTES_SCHEMA,
                    "user_prompt": prompt,
                    "system_prompt": NOTES_SYSTEM_PROMPT,
                    "trace_dir": request_trace_dir,
                },
            )
        )
    raw_results = run_async_tasks_sync(task_specs, max_concurrency=max_concurrency)
    output: dict[str, dict[str, str]] = {}
    allowed_columns_by_request = {
        str(request["request_id"]): {str(column) for column in request.get("allowed_columns", [])}
        for request in requests
    }
    for request_id, payload in raw_results.items():
        notes_by_column: dict[str, str] = {}
        allowed_columns = allowed_columns_by_request.get(request_id, set())
        for item in payload.get("notes", []):
            column = str(item.get("column", "")).strip()
            note = str(item.get("note", "")).strip()
            if column and note and (not allowed_columns or column in allowed_columns):
                notes_by_column[column] = note
        output[request_id] = notes_by_column
    return output


def split_cached_note_requests(
    stage_name: str,
    requests: list[dict[str, Any]],
    cache_path: Path,
) -> tuple[dict[str, dict[str, str]], list[dict[str, Any]]]:
    cache_payload = _load_note_cache(cache_path)
    cached_notes: dict[str, dict[str, str]] = {}
    missing_requests: list[dict[str, Any]] = []
    for request in requests:
        request_id = str(request["request_id"])
        fingerprint = build_note_cache_fingerprint(stage_name, request)
        cached_entry = cache_payload["entries"].get(request_id)
        if cached_entry and cached_entry.get("fingerprint") == fingerprint:
            cached_notes[request_id] = dict(cached_entry.get("notes", {}))
        else:
            missing_requests.append(request)
    return cached_notes, missing_requests


def update_note_cache(
    stage_name: str,
    requests: list[dict[str, Any]],
    notes_by_request: dict[str, dict[str, str]],
    cache_path: Path,
) -> None:
    cache_payload = _load_note_cache(cache_path)
    for request in requests:
        request_id = str(request["request_id"])
        if request_id not in notes_by_request:
            continue
        cache_payload["entries"][request_id] = {
            "fingerprint": build_note_cache_fingerprint(stage_name, request),
            "notes": notes_by_request[request_id],
        }
    cache_path.write_text(json.dumps(cache_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_note_cache_fingerprint(stage_name: str, request: dict[str, Any]) -> str:
    target_name = get_stage_primary_target_name(stage_name)  # type: ignore[arg-type]
    payload = {
        "cache_version": NOTE_CACHE_VERSION,
        "stage_name": stage_name,
        "target_name": target_name,
        "schema": NOTES_SCHEMA,
        "system_prompt": NOTES_SYSTEM_PROMPT,
        "prompt": str(request.get("prompt", "")),
        "allowed_columns": list(request.get("allowed_columns", [])),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load_note_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"cache_version": NOTE_CACHE_VERSION, "entries": {}}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("cache_version") != NOTE_CACHE_VERSION:
        return {"cache_version": NOTE_CACHE_VERSION, "entries": {}}
    entries = payload.get("entries", {})
    if not isinstance(entries, dict):
        return {"cache_version": NOTE_CACHE_VERSION, "entries": {}}
    return {"cache_version": NOTE_CACHE_VERSION, "entries": entries}
