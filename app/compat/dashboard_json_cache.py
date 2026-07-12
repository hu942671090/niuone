"""Compatibility facade for :mod:`core.json_cache`."""

if __package__ == "app":
    from .core.json_cache import *  # noqa: F401,F403
else:
    from core.json_cache import *  # noqa: F401,F403
