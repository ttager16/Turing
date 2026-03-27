from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILES = (PROJECT_ROOT / ".env.local", PROJECT_ROOT / ".env")


def load_local_env() -> dict[str, str]:
    loaded: dict[str, str] = {}
    for env_path in ENV_FILES:
        if not env_path.exists():
            continue
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
                loaded[key] = value
    return loaded


def read_local_env_value(key: str) -> str | None:
    load_local_env()
    return os.getenv(key)


def write_env_local(values: dict[str, str]) -> Path:
    env_path = PROJECT_ROOT / ".env.local"
    lines = [
        "# Local reviewer-specific settings for the Turing take-home repo.",
        "# This file is intentionally gitignored.",
        "",
    ]
    for key, value in values.items():
        lines.append(f"{key}={value}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return env_path


def post_json(url: str, payload: dict[str, Any], *, timeout: int = 30) -> dict[str, Any]:
    request = urllib.request.Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def get_json(url: str, *, timeout: int = 30) -> dict[str, Any] | list[dict[str, Any]]:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def local_server_reachable(base_url: str) -> tuple[bool, str]:
    try:
        get_json(base_url.rstrip("/") + "/models", timeout=10)
        return True, ""
    except Exception as exc:  # pragma: no cover - best effort helper
        return False, str(exc)


def build_preflight_summary(*, require_openai: bool) -> dict[str, Any]:
    load_local_env()
    openai_key_present = bool(os.getenv("OPENAI_API_KEY"))
    local_base_url = os.getenv("LOCAL_OPENAI_COMPAT_BASE_URL", "http://192.168.1.172:1234/v1")
    reachable, error = local_server_reachable(local_base_url)
    return {
        "openai_api_key_present": openai_key_present,
        "local_openai_compat_base_url": local_base_url,
        "local_server_reachable": reachable,
        "local_server_error": error,
        "require_openai": require_openai,
    }


def ensure_preflight(*, require_openai: bool) -> tuple[bool, list[str]]:
    summary = build_preflight_summary(require_openai=require_openai)
    messages: list[str] = []
    ok = True
    if require_openai and not summary["openai_api_key_present"]:
        ok = False
        messages.append(
            "Missing OpenAI credentials. Set OPENAI_API_KEY or add it to .env.local."
        )
    if not summary["local_server_reachable"]:
        messages.append(
            "Local OpenAI-compatible server was not reachable. Stage 3 will still run, "
            "but embedding-backed redundancy will degrade to non-embedding signals until the local server is available."
        )
    return ok, messages
