from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from turing_takehome.runtime_setup import (  # noqa: E402
    get_json,
    local_server_reachable,
    post_json,
    read_local_env_value,
    write_env_local,
)


DEFAULT_LOCAL_BASE_URL = "http://192.168.1.172:1234/v1"
DEFAULT_EMBEDDING_MODEL = "text-embedding-nomic-embed-text-v1.5"


def native_api_root(base_url: str) -> str:
    root = base_url.rstrip("/")
    if root.endswith("/v1"):
        return root[:-3]
    return root


def native_model_registry(api_root: str) -> list[dict[str, object]]:
    response = get_json(api_root + "/api/v1/models", timeout=30)
    if isinstance(response, dict):
        models = response.get("models", [])
        if isinstance(models, list):
            return [model for model in models if isinstance(model, dict)]
    return []


def find_registered_model(models: list[dict[str, object]], model_name: str) -> dict[str, object] | None:
    for model in models:
        key = str(model.get("key", "")).strip()
        display_name = str(model.get("display_name", "")).strip()
        if model_name in {key, display_name}:
            return model
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bootstrap the local reviewer environment for the Turing take-home repo."
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Use existing environment values and defaults without prompting.",
    )
    return parser


def prompt_value(label: str, default: str, *, interactive: bool) -> str:
    if not interactive:
        return default
    entered = input(f"{label} [{default}]: ").strip()
    return entered or default


def create_venv_and_install() -> Path:
    venv_dir = PROJECT_ROOT / ".venv"
    if not venv_dir.exists():
        print("Creating virtual environment at .venv ...")
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], cwd=PROJECT_ROOT, check=True)
    python_path = venv_dir / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")
    print("Installing Python dependencies into .venv ...")
    subprocess.run([str(python_path), "-m", "pip", "install", "-r", "requirements.txt"], cwd=PROJECT_ROOT, check=True)
    return python_path


def maybe_write_env_file(*, interactive: bool) -> Path | None:
    current_key = read_local_env_value("OPENAI_API_KEY") or ""
    current_base = read_local_env_value("LOCAL_OPENAI_COMPAT_BASE_URL") or DEFAULT_LOCAL_BASE_URL
    current_embedding = read_local_env_value("LOCAL_EMBEDDING_MODEL") or DEFAULT_EMBEDDING_MODEL

    print("")
    print("OpenAI setup")
    if interactive:
        api_key = input(
            "Enter your OpenAI API key for gpt-5-mini, or press Enter to leave it unset for now: "
        ).strip()
    else:
        api_key = current_key
    values = {
        "LOCAL_OPENAI_COMPAT_BASE_URL": prompt_value(
            "Local OpenAI-compatible base URL",
            current_base,
            interactive=interactive,
        ),
        "LOCAL_EMBEDDING_MODEL": prompt_value(
            "Local embedding model name",
            current_embedding,
            interactive=interactive,
        ),
    }
    if api_key:
        values["OPENAI_API_KEY"] = api_key
    elif current_key:
        values["OPENAI_API_KEY"] = current_key
    env_path = write_env_local(values)
    print(f"Wrote local configuration to {env_path}")
    if not api_key and not current_key:
        print("OpenAI API key left unset.")
        print("Set OPENAI_API_KEY later in your shell, or add it to .env.local before running Stages 1 to 3.")
    return env_path


def maybe_download_and_load_embedding_model(base_url: str, model_name: str) -> None:
    print("")
    print("Local embedding model setup")
    reachable, error = local_server_reachable(base_url)
    if not reachable:
        print(f"Local server not reachable at {base_url}.")
        print("Start LM Studio's local server first, then rerun this script if you want embedding-backed Stage 3 redundancy.")
        if error:
            print(f"Server check error: {error}")
        return

    print(f"Local server reachable at {base_url}.")
    try:
        api_root = native_api_root(base_url)
        models = native_model_registry(api_root)
        registered_model = find_registered_model(models, model_name)
        if registered_model is None:
            print(f"Ensuring embedding model '{model_name}' is downloaded ...")
            download_response = post_json(
                api_root + "/api/v1/models/download",
                {"model": model_name},
                timeout=60,
            )
            print(json.dumps(download_response, indent=2))
            job_id = download_response.get("job_id")
            status = str(download_response.get("status", ""))
            if job_id and status in {"downloading", "paused"}:
                status_url = api_root + f"/api/v1/models/download/status/{job_id}"
                for _ in range(120):
                    time.sleep(2)
                    try:
                        poll = get_json(status_url, timeout=30)
                    except Exception:
                        break
                    status = str(poll.get("status", ""))
                    if status in {"completed", "already_downloaded"}:
                        break
                    if status == "failed":
                        print("Model download failed according to LM Studio.")
                        return
            models = native_model_registry(api_root)
            registered_model = find_registered_model(models, model_name)
        else:
            print(f"Embedding model '{model_name}' is already present in LM Studio.")
        if registered_model is None:
            print("Embedding model is still not visible in the LM Studio model registry.")
            return
        loaded_instances = registered_model.get("loaded_instances", [])
        if isinstance(loaded_instances, list) and loaded_instances:
            print(f"Embedding model '{model_name}' is already loaded.")
            return
        print(f"Loading embedding model '{model_name}' ...")
        load_response = post_json(
            api_root + "/api/v1/models/load",
            {"model": model_name, "echo_load_config": True},
            timeout=120,
        )
        print(json.dumps(load_response, indent=2))
        print("Embedding model load request completed.")
        print("LM Studio decides the appropriate device placement for embedding models.")
    except Exception as exc:
        print(f"Automatic embedding setup did not complete cleanly: {exc}")
        print("You can still run the repo. Stage 3 will degrade gracefully if embeddings are unavailable.")


def main() -> int:
    args = build_parser().parse_args()
    interactive = sys.stdin.isatty() and not args.non_interactive
    print("Turing take-home setup")
    python_path = create_venv_and_install()
    env_path = maybe_write_env_file(interactive=interactive)
    base_url = read_local_env_value("LOCAL_OPENAI_COMPAT_BASE_URL") or DEFAULT_LOCAL_BASE_URL
    model_name = read_local_env_value("LOCAL_EMBEDDING_MODEL") or DEFAULT_EMBEDDING_MODEL
    maybe_download_and_load_embedding_model(base_url, model_name)
    print("")
    print("Setup complete.")
    print(f"Virtual environment python: {python_path}")
    if env_path:
        print(f"Local settings file: {env_path}")
    print("Next step:")
    print(f"{python_path} main.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
