#!/usr/bin/env python3
"""Backward-compatible import shim for the strategy package.

New code should import from :mod:`strategies.registry`.
"""

try:
    from strategies import registry as _registry_module
    from strategies.registry import *  # noqa: F401,F403
except ModuleNotFoundError as exc:
    if exc.name != "strategies":
        raise
    if __package__:
        from .strategies import registry as _registry_module
        from .strategies.registry import *  # type: ignore[no-redef]  # noqa: F401,F403
    else:
        import sys
        from pathlib import Path

        _app_dir = str(Path(__file__).resolve().parent)
        if _app_dir not in sys.path:
            sys.path.insert(0, _app_dir)
        from strategies import registry as _registry_module
        from strategies.registry import *  # type: ignore[no-redef]  # noqa: F401,F403


def __getattr__(name: str):
    return getattr(_registry_module, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_registry_module)))
