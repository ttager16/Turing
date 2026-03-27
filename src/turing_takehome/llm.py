from __future__ import annotations

import asyncio
import hashlib
import json
import os
import urllib.parse
import urllib.request
import urllib.error
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Literal


StageName = Literal[
    "sample-requirements-analysis",
    "sample-efficacy-analysis",
    "dataset-analysis",
    "manual-audit",
]

ProviderName = Literal[
    "openai-compatible",
    "openai",
    "anthropic",
    "gemini",
]


@dataclass(frozen=True)
class ModelTargetConfig:
    provider: ProviderName
    model: str | None
    enabled: bool = True
    base_url: str | None = None
    api_key_env: str | None = None
    timeout_seconds: int = 60
    anthropic_version: str = "2023-06-01"
    temperature: float | None = 0.0
    max_output_tokens: int = 4096


@dataclass(frozen=True)
class StageLLMConfig:
    primary_target: str
    comparison_targets: tuple[str, ...] = ()
    generated_test_target: str | None = None
    enabled: bool = True


LOCAL_OPENAI_COMPAT_BASE_URL = os.getenv("LOCAL_OPENAI_COMPAT_BASE_URL", "http://192.168.1.172:1234/v1")
DEFAULT_LOCAL_EMBEDDING_MODEL = os.getenv(
    "LOCAL_EMBEDDING_MODEL",
    "text-embedding-nomic-embed-text-v1.5",
)

# This is the single place to change repository-wide LLM behavior.
#
# As of March 23, 2026, the official OpenAI API model name for the small GPT-5
# variant is `gpt-5-mini`. We keep a human-readable target alias here so stage
# configs can refer to it without repeating provider-specific wiring.
MODEL_TARGETS: dict[str, ModelTargetConfig] = {
    "local-qwen": ModelTargetConfig(
        provider="openai-compatible",
        model=None,
        base_url=LOCAL_OPENAI_COMPAT_BASE_URL,
        timeout_seconds=180,
        temperature=0.0,
        max_output_tokens=4096,
    ),
    "openai-gpt-5-mini": ModelTargetConfig(
        provider="openai",
        model="gpt-5-mini",
        api_key_env="OPENAI_API_KEY",
        timeout_seconds=180,
        temperature=None,
        max_output_tokens=4096,
    ),
    "anthropic-placeholder": ModelTargetConfig(
        provider="anthropic",
        model="<set-anthropic-model>",
        api_key_env="ANTHROPIC_API_KEY",
        enabled=False,
    ),
    "gemini-placeholder": ModelTargetConfig(
        provider="gemini",
        model="<set-gemini-model>",
        api_key_env="GEMINI_API_KEY",
        enabled=False,
    ),
}


STAGE_LLM_CONFIGS: dict[StageName, StageLLMConfig] = {
    "sample-requirements-analysis": StageLLMConfig(
        primary_target="openai-gpt-5-mini",
        comparison_targets=("openai-gpt-5-mini",),
        enabled=True,
    ),
    "sample-efficacy-analysis": StageLLMConfig(
        primary_target="openai-gpt-5-mini",
        comparison_targets=("openai-gpt-5-mini",),
        generated_test_target="openai-gpt-5-mini",
        enabled=True,
    ),
    "dataset-analysis": StageLLMConfig(
        primary_target="openai-gpt-5-mini",
        comparison_targets=("openai-gpt-5-mini",),
        enabled=False,
    ),
    "manual-audit": StageLLMConfig(
        primary_target="anthropic-placeholder",
        comparison_targets=("anthropic-placeholder",),
        enabled=False,
    ),
}

DEFAULT_SYSTEM_PROMPT = "You are a strict data-quality auditor. Return compact JSON only."


@dataclass(frozen=True)
class AsyncTaskSpec:
    request_id: str
    task_type: Literal["json", "text"]
    kwargs: dict[str, Any]


def get_stage_llm_config(stage_name: StageName) -> StageLLMConfig:
    try:
        return STAGE_LLM_CONFIGS[stage_name]
    except KeyError as exc:
        raise ValueError(f"Unknown stage '{stage_name}'.") from exc


def get_model_target_config(target_name: str) -> ModelTargetConfig:
    try:
        return MODEL_TARGETS[target_name]
    except KeyError as exc:
        raise ValueError(f"Unknown model target '{target_name}'.") from exc


def get_stage_primary_target_name(stage_name: StageName) -> str:
    return get_stage_llm_config(stage_name).primary_target


def get_stage_comparison_target_names(stage_name: StageName) -> tuple[str, ...]:
    config = get_stage_llm_config(stage_name)
    if config.comparison_targets:
        return config.comparison_targets
    return (config.primary_target,)


def get_stage_generated_test_target_name(stage_name: StageName) -> str:
    config = get_stage_llm_config(stage_name)
    return config.generated_test_target or config.primary_target


def override_stage_targets(
    stage_name: StageName,
    *,
    primary_target: str | None = None,
    comparison_targets: tuple[str, ...] | None = None,
    generated_test_target: str | None = None,
    enabled: bool | None = None,
) -> StageLLMConfig:
    current = get_stage_llm_config(stage_name)
    updated = replace(
        current,
        primary_target=primary_target if primary_target is not None else current.primary_target,
        comparison_targets=(
            comparison_targets if comparison_targets is not None else current.comparison_targets
        ),
        generated_test_target=(
            generated_test_target
            if generated_test_target is not None
            else current.generated_test_target
        ),
        enabled=enabled if enabled is not None else current.enabled,
    )
    STAGE_LLM_CONFIGS[stage_name] = updated
    return updated


def is_stage_llm_enabled(stage_name: StageName) -> bool:
    config = get_stage_llm_config(stage_name)
    if not config.enabled:
        return False
    target = get_model_target_config(config.primary_target)
    return target.enabled


def get_target_model_label(target_name: str) -> str:
    target = get_model_target_config(target_name)
    model = resolve_model_name_for_target(target_name)
    if not model:
        return ""
    return f"{target.provider}:{model}"


def get_stage_model_label(stage_name: StageName) -> str:
    return get_target_model_label(get_stage_primary_target_name(stage_name))


def resolve_model_name(stage_name: StageName) -> str | None:
    return resolve_model_name_for_target(get_stage_primary_target_name(stage_name))


def resolve_model_name_for_target(target_name: str) -> str | None:
    config = get_model_target_config(target_name)
    if config.model and not config.model.startswith("<set-"):
        return config.model
    if config.provider == "openai-compatible":
        return _discover_openai_compatible_model(config)
    return None


def resolve_embedding_model_name_for_target(target_name: str) -> str | None:
    config = get_model_target_config(target_name)
    if config.provider == "openai-compatible":
        return _discover_openai_compatible_embedding_model(config)
    if config.provider == "openai":
        return DEFAULT_LOCAL_EMBEDDING_MODEL
    return None


def request_json(
    stage_name: StageName,
    schema_name: str,
    schema: dict[str, Any],
    user_prompt: str,
    *,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    trace_dir: Path | None = None,
) -> dict[str, Any]:
    return request_json_for_target(
        get_stage_primary_target_name(stage_name),
        schema_name,
        schema,
        user_prompt,
        system_prompt=system_prompt,
        trace_dir=trace_dir,
    )


def request_json_for_target(
    target_name: str,
    schema_name: str,
    schema: dict[str, Any],
    user_prompt: str,
    *,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    trace_dir: Path | None = None,
) -> dict[str, Any]:
    config = get_model_target_config(target_name)
    if not config.enabled:
        raise RuntimeError(f"LLM target '{target_name}' is disabled.")

    model = resolve_model_name_for_target(target_name)
    if not model:
        raise RuntimeError(
            f"No model configured for target '{target_name}' and automatic discovery failed."
        )

    if config.provider in {"openai-compatible", "openai"}:
        return _request_openai_family_json(
            config=config,
            model=model,
            schema_name=schema_name,
            schema=schema,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            trace_dir=trace_dir,
        )
    if config.provider == "anthropic":
        return _request_anthropic_json(
            config=config,
            model=model,
            schema_name=schema_name,
            schema=schema,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            trace_dir=trace_dir,
        )
    if config.provider == "gemini":
        return _request_gemini_json(
            config=config,
            model=model,
            schema_name=schema_name,
            schema=schema,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            trace_dir=trace_dir,
        )
    raise RuntimeError(f"Unsupported provider '{config.provider}'.")


def generate_text(
    stage_name: StageName,
    user_prompt: str,
    *,
    system_prompt: str = "You are a careful coding assistant. Return the best possible answer for the task.",
    trace_dir: Path | None = None,
) -> dict[str, Any]:
    return generate_text_for_target(
        get_stage_primary_target_name(stage_name),
        user_prompt,
        system_prompt=system_prompt,
        trace_dir=trace_dir,
    )


def generate_text_for_target(
    target_name: str,
    user_prompt: str,
    *,
    system_prompt: str = "You are a careful coding assistant. Return the best possible answer for the task.",
    trace_dir: Path | None = None,
) -> dict[str, Any]:
    config = get_model_target_config(target_name)
    if not config.enabled:
        raise RuntimeError(f"LLM target '{target_name}' is disabled.")

    model = resolve_model_name_for_target(target_name)
    if not model:
        raise RuntimeError(
            f"No model configured for target '{target_name}' and automatic discovery failed."
        )

    if config.provider in {"openai-compatible", "openai"}:
        return _generate_openai_family_text(
            config=config,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            trace_dir=trace_dir,
        )
    if config.provider == "anthropic":
        return _generate_anthropic_text(
            config=config,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            trace_dir=trace_dir,
        )
    if config.provider == "gemini":
        return _generate_gemini_text(
            config=config,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            trace_dir=trace_dir,
        )
    raise RuntimeError(f"Unsupported provider '{config.provider}'.")


def embed_texts_for_target(
    target_name: str,
    texts: list[str],
    *,
    model_name: str | None = None,
    trace_dir: Path | None = None,
) -> dict[str, Any]:
    config = get_model_target_config(target_name)
    if not config.enabled:
        raise RuntimeError(f"LLM target '{target_name}' is disabled.")

    if config.provider not in {"openai-compatible", "openai"}:
        raise RuntimeError(
            f"Embeddings are only supported for OpenAI-compatible targets, not '{config.provider}'."
        )

    model = model_name or resolve_embedding_model_name_for_target(target_name)
    if not model:
        raise RuntimeError(f"No embedding model configured for target '{target_name}'.")
    if config.provider == "openai":
        base_url = "https://api.openai.com/v1"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {_require_api_key(config)}",
        }
    else:
        base_url = config.base_url or "https://api.openai.com/v1"
        headers = {"Content-Type": "application/json"}
    body = {
        "model": model,
        "input": texts,
    }
    payload = _http_json(
        url=base_url.rstrip("/") + "/embeddings",
        body=body,
        headers=headers,
        timeout_seconds=config.timeout_seconds,
        trace_dir=trace_dir,
        trace_stem="embeddings",
    )
    data = payload.get("data", [])
    vectors = [list(item.get("embedding", [])) for item in data]
    return {
        "vectors": vectors,
        "provider": config.provider,
        "model": model,
        "timestamp_utc": _utc_now(),
        "usage": payload.get("usage"),
    }


def embed_texts_cached_for_target(
    target_name: str,
    texts: list[str],
    *,
    cache_path: Path,
    model_name: str | None = None,
    trace_dir: Path | None = None,
) -> dict[str, Any]:
    model = model_name or resolve_embedding_model_name_for_target(target_name)
    cache_payload = _load_embedding_cache(cache_path)
    vectors: list[list[float]] = []
    missing_indices: list[int] = []
    missing_texts: list[str] = []
    for index, text in enumerate(texts):
        fingerprint = _embedding_fingerprint(
            target_name=target_name,
            model_name=model,
            text=text,
        )
        cached_entry = cache_payload["entries"].get(fingerprint)
        if cached_entry is None:
            missing_indices.append(index)
            missing_texts.append(text)
            vectors.append([])
            continue
        vectors.append(list(cached_entry.get("vector", [])))

    usage: dict[str, Any] | None = None
    if missing_texts:
        fresh = embed_texts_for_target(
            target_name,
            missing_texts,
            model_name=model,
            trace_dir=trace_dir,
        )
        usage = fresh.get("usage")
        fresh_vectors = fresh.get("vectors", [])
        if len(fresh_vectors) != len(missing_indices):
            raise RuntimeError("Embedding response size did not match the requested text count.")
        for offset, sample_index in enumerate(missing_indices):
            text = texts[sample_index]
            vector = list(fresh_vectors[offset])
            fingerprint = _embedding_fingerprint(
                target_name=target_name,
                model_name=model,
                text=text,
            )
            cache_payload["entries"][fingerprint] = {
                "vector": vector,
            }
            vectors[sample_index] = vector
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(cache_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    return {
        "vectors": vectors,
        "provider": get_model_target_config(target_name).provider,
        "model": model,
        "timestamp_utc": _utc_now(),
        "usage": usage,
        "cache_hits": len(texts) - len(missing_texts),
        "cache_misses": len(missing_texts),
    }


async def request_json_for_target_async(
    target_name: str,
    schema_name: str,
    schema: dict[str, Any],
    user_prompt: str,
    *,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    trace_dir: Path | None = None,
) -> dict[str, Any]:
    return await asyncio.to_thread(
        request_json_for_target,
        target_name,
        schema_name,
        schema,
        user_prompt,
        system_prompt=system_prompt,
        trace_dir=trace_dir,
    )


async def generate_text_for_target_async(
    target_name: str,
    user_prompt: str,
    *,
    system_prompt: str = "You are a careful coding assistant. Return the best possible answer for the task.",
    trace_dir: Path | None = None,
) -> dict[str, Any]:
    return await asyncio.to_thread(
        generate_text_for_target,
        target_name,
        user_prompt,
        system_prompt=system_prompt,
        trace_dir=trace_dir,
    )


async def run_async_tasks(
    task_specs: list[AsyncTaskSpec],
    *,
    max_concurrency: int = 8,
) -> dict[str, Any]:
    async def build_runner(spec: AsyncTaskSpec) -> Any:
        if spec.task_type == "json":
            return await request_json_for_target_async(**spec.kwargs)
        if spec.task_type == "text":
            return await generate_text_for_target_async(**spec.kwargs)
        raise ValueError(f"Unsupported async task type '{spec.task_type}'.")

    return await run_async_job_builders(
        [(spec.request_id, (lambda spec=spec: build_runner(spec))) for spec in task_specs],
        max_concurrency=max_concurrency,
    )


def run_async_tasks_sync(
    task_specs: list[AsyncTaskSpec],
    *,
    max_concurrency: int = 8,
) -> dict[str, Any]:
    return asyncio.run(run_async_tasks(task_specs, max_concurrency=max_concurrency))


async def run_async_job_builders(
    jobs: list[tuple[str, Callable[[], Awaitable[Any]]]],
    *,
    max_concurrency: int = 8,
) -> dict[str, Any]:
    semaphore = asyncio.Semaphore(max(1, max_concurrency))

    async def execute(job_id: str, builder: Callable[[], Awaitable[Any]]) -> tuple[str, Any]:
        async with semaphore:
            return job_id, await builder()

    tasks = [asyncio.create_task(execute(job_id, builder)) for job_id, builder in jobs]
    results: dict[str, Any] = {}
    for task in asyncio.as_completed(tasks):
        job_id, result = await task
        results[job_id] = result
    return results


def request_structured_judgment(
    stage_name: StageName,
    schema_name: str,
    user_prompt: str,
    *,
    trace_dir: Path | None = None,
) -> dict[str, Any]:
    return request_structured_judgment_for_target(
        get_stage_primary_target_name(stage_name),
        schema_name,
        user_prompt,
        trace_dir=trace_dir,
    )


def request_structured_judgment_for_target(
    target_name: str,
    schema_name: str,
    user_prompt: str,
    *,
    trace_dir: Path | None = None,
) -> dict[str, Any]:
    schema = {
        "type": "object",
        "properties": {
            "verdict": {
                "type": "string",
                "enum": ["PASS", "PARTIAL", "FAIL", "UNCLEAR", "NA"],
            },
            "note": {"type": "string"},
        },
        "required": ["verdict", "note"],
        "additionalProperties": False,
    }
    return request_json_for_target(
        target_name,
        schema_name,
        schema,
        user_prompt,
        trace_dir=trace_dir,
    )


def _discover_openai_compatible_model(config: ModelTargetConfig) -> str | None:
    if not config.base_url:
        return None
    payload = _http_json(
        url=config.base_url.rstrip("/") + "/models",
        body=None,
        headers={},
        timeout_seconds=config.timeout_seconds,
        method="GET",
    )
    ids = [item.get("id", "") for item in payload.get("data", [])]
    for preferred in ("Qwen3-Coder-Next", "qwen3-coder-next", "Qwen", "qwen"):
        for model_id in ids:
            if preferred.lower() in model_id.lower():
                return model_id
    return ids[0] if ids else None


def _discover_openai_compatible_embedding_model(config: ModelTargetConfig) -> str | None:
    if not config.base_url:
        return None
    payload = _http_json(
        url=config.base_url.rstrip("/") + "/models",
        body=None,
        headers={},
        timeout_seconds=config.timeout_seconds,
        method="GET",
    )
    preferred_ids: list[str] = []
    for item in payload.get("data", []):
        model_id = str(item.get("id", "")).strip()
        if not model_id:
            continue
        lowered = model_id.lower()
        if "embedding" in lowered or "embed" in lowered:
            if "text-embedding" in lowered or "embed-text" in lowered:
                return model_id
            preferred_ids.append(model_id)
    return preferred_ids[0] if preferred_ids else None


def _request_openai_family_json(
    *,
    config: ModelTargetConfig,
    model: str,
    schema_name: str,
    schema: dict[str, Any],
    system_prompt: str,
    user_prompt: str,
    trace_dir: Path | None,
) -> dict[str, Any]:
    base_url = config.base_url or "https://api.openai.com/v1"
    headers = {"Content-Type": "application/json"}
    if config.provider == "openai":
        headers["Authorization"] = f"Bearer {_require_api_key(config)}"

    body = {
        "model": model,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": schema_name,
                "schema": schema,
            },
        },
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    if config.temperature is not None:
        body["temperature"] = config.temperature
    payload = _http_json(
        url=base_url.rstrip("/") + "/chat/completions",
        body=body,
        headers=headers,
        timeout_seconds=config.timeout_seconds,
        trace_dir=trace_dir,
        trace_stem=schema_name,
    )
    content = payload["choices"][0]["message"]["content"].strip()
    return _parse_json_text(content)


def _generate_openai_family_text(
    *,
    config: ModelTargetConfig,
    model: str,
    system_prompt: str,
    user_prompt: str,
    trace_dir: Path | None,
) -> dict[str, Any]:
    if config.provider == "openai":
        return _generate_openai_responses_text(
            config=config,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            trace_dir=trace_dir,
        )
    base_url = config.base_url or "https://api.openai.com/v1"
    headers = {"Content-Type": "application/json"}

    body = {
        "model": model,
        "max_tokens": config.max_output_tokens,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    if config.temperature is not None:
        body["temperature"] = config.temperature
    payload = _http_json(
        url=base_url.rstrip("/") + "/chat/completions",
        body=body,
        headers=headers,
        timeout_seconds=config.timeout_seconds,
        trace_dir=trace_dir,
        trace_stem="text_generation",
    )
    choice = payload["choices"][0]
    content = choice["message"]["content"]
    return {
        "text": content,
        "provider": config.provider,
        "model": model,
        "timestamp_utc": _utc_now(),
        "finish_reason": choice.get("finish_reason"),
        "usage": payload.get("usage"),
        "status": payload.get("status", "completed"),
        "incomplete_details": payload.get("incomplete_details"),
    }


def _generate_openai_responses_text(
    *,
    config: ModelTargetConfig,
    model: str,
    system_prompt: str,
    user_prompt: str,
    trace_dir: Path | None,
) -> dict[str, Any]:
    body = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": system_prompt}],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": user_prompt}],
            },
        ],
        "reasoning": {"effort": "minimal"},
        "text": {"verbosity": "low"},
        "max_output_tokens": config.max_output_tokens,
    }
    payload = _http_json(
        url="https://api.openai.com/v1/responses",
        body=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {_require_api_key(config)}",
        },
        timeout_seconds=config.timeout_seconds,
        trace_dir=trace_dir,
        trace_stem="text_generation",
    )
    text_parts: list[str] = []
    for item in payload.get("output", []):
        if item.get("type") != "message":
            continue
        for content_item in item.get("content", []):
            if content_item.get("type") == "output_text":
                text_parts.append(str(content_item.get("text", "")))
    return {
        "text": "\n".join(part for part in text_parts if part).strip(),
        "provider": config.provider,
        "model": str(payload.get("model", model)),
        "timestamp_utc": _utc_now(),
        "finish_reason": payload.get("status"),
        "usage": payload.get("usage"),
        "status": payload.get("status"),
        "incomplete_details": payload.get("incomplete_details"),
    }


def _request_anthropic_json(
    *,
    config: ModelTargetConfig,
    model: str,
    schema_name: str,
    schema: dict[str, Any],
    system_prompt: str,
    user_prompt: str,
    trace_dir: Path | None,
) -> dict[str, Any]:
    body = {
        "model": model,
        "max_tokens": 1200,
        "temperature": 0,
        "system": system_prompt,
        "tools": [
            {
                "name": schema_name,
                "description": "Return the structured result for this request.",
                "input_schema": schema,
            }
        ],
        "tool_choice": {"type": "tool", "name": schema_name},
        "messages": [{"role": "user", "content": user_prompt}],
    }
    payload = _http_json(
        url="https://api.anthropic.com/v1/messages",
        body=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": _require_api_key(config),
            "anthropic-version": config.anthropic_version,
        },
        timeout_seconds=config.timeout_seconds,
        trace_dir=trace_dir,
        trace_stem=schema_name,
    )
    for block in payload.get("content", []):
        if block.get("type") == "tool_use":
            tool_input = block.get("input")
            if isinstance(tool_input, dict):
                return tool_input
    raise RuntimeError("Anthropic response did not contain the expected structured tool output.")


def _generate_anthropic_text(
    *,
    config: ModelTargetConfig,
    model: str,
    system_prompt: str,
    user_prompt: str,
    trace_dir: Path | None,
) -> dict[str, Any]:
    body = {
        "model": model,
        "max_tokens": config.max_output_tokens,
        "temperature": config.temperature,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    payload = _http_json(
        url="https://api.anthropic.com/v1/messages",
        body=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": _require_api_key(config),
            "anthropic-version": config.anthropic_version,
        },
        timeout_seconds=config.timeout_seconds,
        trace_dir=trace_dir,
        trace_stem="text_generation",
    )
    text_parts = [
        block.get("text", "")
        for block in payload.get("content", [])
        if block.get("type") == "text"
    ]
    return {
        "text": "".join(text_parts).strip(),
        "provider": config.provider,
        "model": model,
        "timestamp_utc": _utc_now(),
        "finish_reason": payload.get("stop_reason"),
        "usage": payload.get("usage"),
    }


def _request_gemini_json(
    *,
    config: ModelTargetConfig,
    model: str,
    schema_name: str,
    schema: dict[str, Any],
    system_prompt: str,
    user_prompt: str,
    trace_dir: Path | None,
) -> dict[str, Any]:
    api_key = _require_api_key(config)
    base_url = config.base_url or "https://generativelanguage.googleapis.com/v1beta"
    body = {
        "system_instruction": {
            "parts": [{"text": system_prompt}],
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_prompt}],
            }
        ],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
            "responseSchema": schema,
        },
    }
    url = (
        f"{base_url.rstrip('/')}/models/{urllib.parse.quote(model, safe='')}:generateContent"
        f"?key={urllib.parse.quote(api_key, safe='')}"
    )
    payload = _http_json(
        url=url,
        body=body,
        headers={"Content-Type": "application/json"},
        timeout_seconds=config.timeout_seconds,
        trace_dir=trace_dir,
        trace_stem=schema_name,
    )
    candidates = payload.get("candidates", [])
    if not candidates:
        raise RuntimeError("Gemini response did not include any candidates.")
    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(part.get("text", "") for part in parts if isinstance(part, dict)).strip()
    if not text:
        raise RuntimeError("Gemini response did not include JSON text content.")
    return _parse_json_text(text)


def _generate_gemini_text(
    *,
    config: ModelTargetConfig,
    model: str,
    system_prompt: str,
    user_prompt: str,
    trace_dir: Path | None,
) -> dict[str, Any]:
    api_key = _require_api_key(config)
    base_url = config.base_url or "https://generativelanguage.googleapis.com/v1beta"
    body = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_prompt}],
            }
        ],
        "generationConfig": {
            "maxOutputTokens": config.max_output_tokens,
        },
    }
    if config.temperature is not None:
        body["generationConfig"]["temperature"] = config.temperature
    url = (
        f"{base_url.rstrip('/')}/models/{urllib.parse.quote(model, safe='')}:generateContent"
        f"?key={urllib.parse.quote(api_key, safe='')}"
    )
    payload = _http_json(
        url=url,
        body=body,
        headers={"Content-Type": "application/json"},
        timeout_seconds=config.timeout_seconds,
        trace_dir=trace_dir,
        trace_stem="text_generation",
    )
    candidates = payload.get("candidates", [])
    if not candidates:
        raise RuntimeError("Gemini response did not include any candidates.")
    candidate = candidates[0]
    parts = candidate.get("content", {}).get("parts", [])
    text = "".join(part.get("text", "") for part in parts if isinstance(part, dict)).strip()
    return {
        "text": text,
        "provider": config.provider,
        "model": model,
        "timestamp_utc": _utc_now(),
        "finish_reason": candidate.get("finishReason"),
        "usage": payload.get("usageMetadata"),
    }


def _require_api_key(config: ModelTargetConfig) -> str:
    if not config.api_key_env:
        raise RuntimeError(f"Provider '{config.provider}' requires an API key env var.")
    value = os.environ.get(config.api_key_env, "").strip()
    if not value:
        raise RuntimeError(
            f"Missing API key. Set the {config.api_key_env} environment variable."
        )
    return value


def _embedding_fingerprint(*, target_name: str, model_name: str, text: str) -> str:
    payload = {
        "cache_version": "embedding-cache-v1",
        "target_name": target_name,
        "model_name": model_name,
        "text": text,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load_embedding_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"cache_version": "embedding-cache-v1", "entries": {}}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("cache_version") != "embedding-cache-v1":
        return {"cache_version": "embedding-cache-v1", "entries": {}}
    entries = payload.get("entries", {})
    if not isinstance(entries, dict):
        return {"cache_version": "embedding-cache-v1", "entries": {}}
    return {"cache_version": "embedding-cache-v1", "entries": entries}


def _http_json(
    *,
    url: str,
    body: dict[str, Any] | None,
    headers: dict[str, str],
    timeout_seconds: int,
    method: str | None = None,
    trace_dir: Path | None = None,
    trace_stem: str | None = None,
) -> dict[str, Any]:
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method=method or ("POST" if body is not None else "GET"),
    )
    if trace_dir is not None and trace_stem is not None and body is not None:
        trace_dir.mkdir(parents=True, exist_ok=True)
        (trace_dir / f"{trace_stem}_request.json").write_text(
            json.dumps(body, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_text = exc.read().decode("utf-8", errors="replace")
        if trace_dir is not None and trace_stem is not None:
            trace_dir.mkdir(parents=True, exist_ok=True)
            (trace_dir / f"{trace_stem}_error.txt").write_text(error_text, encoding="utf-8")
        raise RuntimeError(
            f"HTTP {exc.code} error from {url}: {error_text}"
        ) from exc
    if trace_dir is not None and trace_stem is not None:
        trace_dir.mkdir(parents=True, exist_ok=True)
        (trace_dir / f"{trace_stem}_response.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return payload


def _parse_json_text(text: str) -> dict[str, Any]:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise
        parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise RuntimeError("Structured LLM response was not a JSON object.")
    return parsed


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
