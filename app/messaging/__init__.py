"""Canonical notification package with a legacy top-level import alias.

The implementation always loads as :mod:`app.messaging`.  Importing the old
top-level :mod:`messaging` spelling redirects to that canonical module before
any registry state is created, so concurrent imports cannot create two channel
registries.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping


if __name__ == "messaging":
    __niuone_messaging_forwarder__ = True
    project_root = str(Path(__file__).resolve().parents[2])
    added_project_root = project_root not in sys.path
    if added_project_root:
        sys.path.insert(0, project_root)
    try:
        canonical = importlib.import_module("app.messaging")
    finally:
        if added_project_root:
            try:
                sys.path.remove(project_root)
            except ValueError:
                pass
    sys.modules[__name__] = canonical
    globals().update({
        name: value
        for name, value in canonical.__dict__.items()
        if not (name.startswith("__") and name.endswith("__"))
    })
else:
    from . import _api

    globals().update({
        name: value
        for name, value in _api.__dict__.items()
        if not (name.startswith("__") and name.endswith("__"))
    })
    __all__ = _api.__all__

    def notify_trade_executions(
        trades: Iterable[Mapping[str, Any]],
        env: Mapping[str, Any] | None = None,
        *,
        transport: JsonTransport | None = None,
        clock: Clock | None = None,
    ) -> list[DeliveryResult]:
        """Format trades and use the package's current dispatch hook."""

        return _trades_module.notify_trade_executions(
            trades,
            env,
            transport=transport,
            clock=clock,
            _dispatch=dispatch,
        )

    _canonical_package = sys.modules[__name__]
    _legacy_package = sys.modules.get("messaging")
    if _legacy_package is None or getattr(_legacy_package, "__niuone_messaging_forwarder__", False):
        sys.modules["messaging"] = _canonical_package
        _legacy_package = _canonical_package
    for _module_name, _module in (
        ("_api", _api),
        ("models", _models_module),
        ("channels", _channels_module),
        ("transport", _transport_module),
        ("dispatcher", _dispatcher_module),
        ("trades", _trades_module),
    ):
        sys.modules.setdefault(f"app.messaging.{_module_name}", _module)
        if _legacy_package is _canonical_package:
            sys.modules.setdefault(f"messaging.{_module_name}", _module)
        globals()[_module_name] = _module
