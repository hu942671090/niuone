"""Compatibility facade for the canonical :mod:`core.paths` module."""

if __package__ == "app":
    from .core.paths import *  # noqa: F401,F403
else:
    from core.paths import *  # noqa: F401,F403
