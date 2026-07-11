"""Candidate eligibility and strategy-aware display selection."""
from typing import Any

from .registry import DISPLAY_STRATEGY_ORDER
from .scoring import COMMON_MAX_BBI_DISTANCE_PCT, safe_float


DISPLAY_HEAD_LIMIT = 8


def candidate_is_trade_ready(item: dict[str, Any]) -> bool:
    raw_score = item.get("best_score")
    if raw_score is None:
        raw_score = item.get("score")
    score = safe_float(raw_score) or 0
    threshold = safe_float(item.get("entry_threshold")) or 8
    blockers = item.get("hard_blockers") or []
    distance = safe_float(item.get("distance_pct"))
    return (
        bool(item.get("actionable", score >= threshold))
        and score >= threshold
        and not blockers
        and (distance is None or distance <= COMMON_MAX_BBI_DISTANCE_PCT)
    )


def select_trade_candidates(results: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    """Return candidates allowed to reach the trading decision model."""
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in results:
        if len(selected) >= limit:
            break
        code = str(item.get("code") or "")
        if not code or code in seen or not candidate_is_trade_ready(item):
            continue
        selected.append(item)
        seen.add(code)
    return selected


def select_display_candidates(
    results: list[dict[str, Any]],
    limit: int = 16,
) -> list[dict[str, Any]]:
    """Keep top-ranked names while reserving slots for each strategy family."""
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(item: dict[str, Any]) -> None:
        if len(selected) >= limit:
            return
        code = str(item.get("code") or "")
        if not code or code in seen:
            return
        selected.append(item)
        seen.add(code)

    trade_ready = [item for item in results if candidate_is_trade_ready(item)]
    for item in trade_ready[:DISPLAY_HEAD_LIMIT]:
        add(item)

    for strategy_id in DISPLAY_STRATEGY_ORDER:
        for item in trade_ready:
            if item.get("best_strategy") == strategy_id:
                add(item)
                break

    for item in trade_ready:
        add(item)

    for item in results:
        add(item)

    return selected
