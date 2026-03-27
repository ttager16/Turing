from __future__ import annotations

import importlib.util
import json
import sys
import traceback
from pathlib import Path


def normalize_result(value):
    if isinstance(value, str):
        stripped = value.strip()
        if stripped[:1] in '{["tfn-0123456789':
            try:
                return json.loads(stripped)
            except Exception:
                return value
    return value


def load_module(code_path: Path):
    spec = importlib.util.spec_from_file_location("candidate_solution", code_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module from {code_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    if len(sys.argv) < 4:
        raise SystemExit("Usage: harness.py <mode> <code_path> <function_name>")
    mode = sys.argv[1]
    code_path = Path(sys.argv[2])
    function_name = sys.argv[3]
    payload = json.loads(sys.stdin.read() or "{}")
    try:
        module = load_module(code_path)
        function = getattr(module, function_name)
        if mode == "probe":
            print(json.dumps({"ok": True}))
            return 0
        if mode != "test":
            raise RuntimeError(f"Unsupported mode: {mode}")
        args = payload.get("args", [])
        result = function(*args)
        print(json.dumps({"ok": True, "result": normalize_result(result)}, ensure_ascii=False))
        return 0
    except Exception as exc:
        traceback.print_exc()
        print(json.dumps({
            "ok": False,
            "exception_type": exc.__class__.__name__,
            "exception_message": str(exc),
        }, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
