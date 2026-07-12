"""Bootstrap relocated services with legacy-compatible runtime paths."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


APP_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = APP_DIR.parent
COMPAT_DIR = APP_DIR / "compat"
for path in (str(COMPAT_DIR), str(APP_DIR), str(PROJECT_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from _compat import exec_relocated


def run(module_globals: dict[str, Any], implementation: str, legacy_name: str) -> None:
    module_globals["__file__"] = str(APP_DIR / legacy_name)
    exec_relocated(module_globals, implementation)
