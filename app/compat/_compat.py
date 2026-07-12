"""Helpers for legacy root-module entrypoints.

The project historically executes and loads ``app/*.py`` files directly.  A
compatibility entrypoint executes the relocated implementation in its own
module namespace so callers can still replace module globals at runtime.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


APP_DIR = Path(__file__).resolve().parent.parent


def exec_relocated(module_globals: dict[str, Any], relative_path: str) -> None:
    """Execute a relocated implementation while preserving the legacy module."""
    source_path = APP_DIR / relative_path
    if str(APP_DIR) not in sys.path:
        sys.path.insert(0, str(APP_DIR))
    compat_dir = APP_DIR / "compat"
    if str(compat_dir) not in sys.path:
        sys.path.insert(0, str(compat_dir))
    legacy_name = Path(str(module_globals.get("__file__") or relative_path)).name
    module_globals["__file__"] = str(APP_DIR / legacy_name)
    module_globals["__implementation_file__"] = source_path
    code = compile(source_path.read_bytes(), str(source_path), "exec")
    exec(code, module_globals, module_globals)
