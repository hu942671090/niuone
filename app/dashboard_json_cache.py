"""Small JSON cache helpers for dashboard data producers."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


def read_json_cache(path: Path, ttl_seconds: int | float | None = None) -> dict[str, Any] | None:
    """Return cached JSON when it exists, parses, and is fresh enough."""
    try:
        stat = path.stat()
        if ttl_seconds is not None and time.time() - stat.st_mtime >= ttl_seconds:
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError, TypeError):
        return None


def write_json_cache(path: Path, data: dict[str, Any]) -> None:
    """Atomically write a dashboard JSON cache file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{time.monotonic_ns()}.tmp")
    try:
        tmp.write_text(json.dumps(data, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(path)
    finally:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass

