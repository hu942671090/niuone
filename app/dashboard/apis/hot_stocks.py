"""Ranking-selection rules for the dashboard hot-stock API."""
from __future__ import annotations

from typing import Any


def select_hot_stock_ranking(data: dict[str, Any], sort_by: str = "amount") -> dict[str, Any]:
    if sort_by in ("turnover", "turnover_top"):
        data["items"] = data.get("turnover_top", [])
    elif sort_by in ("volume", "volume_top"):
        data["items"] = data.get("volume_top", [])
    elif sort_by in ("gain", "hot"):
        data["items"] = data.get("gain_top", [])
    else:
        data["items"] = data.get("amount_top", data.get("items", []))
    return data
