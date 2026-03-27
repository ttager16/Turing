from __future__ import annotations

import json
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from turing_takehome.llm import (  # noqa: E402
    DEFAULT_LOCAL_EMBEDDING_MODEL,
    LOCAL_OPENAI_COMPAT_BASE_URL,
    resolve_embedding_model_name_for_target,
)
from turing_takehome.runtime_setup import build_preflight_summary, load_local_env  # noqa: E402


def main() -> int:
    load_local_env()
    summary = build_preflight_summary(require_openai=False)
    print("Environment check")
    print(json.dumps(
        {
            "python_executable": sys.executable,
            "python_version": sys.version.split()[0],
            "project_root": str(PROJECT_ROOT),
            "openai_api_key_present": bool(os.getenv("OPENAI_API_KEY")),
            "local_openai_compat_base_url": LOCAL_OPENAI_COMPAT_BASE_URL,
            "requested_local_embedding_model": DEFAULT_LOCAL_EMBEDDING_MODEL,
            "local_server_reachable": bool(summary["local_server_reachable"]),
            "local_server_error": summary["local_server_error"],
        },
        indent=2,
    ))

    try:
        discovered_embedding_model = resolve_embedding_model_name_for_target("local-qwen")
        print(f"discovered_local_embedding_model={discovered_embedding_model}")
    except Exception as exc:
        print(f"discovered_local_embedding_model=unavailable ({exc})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
