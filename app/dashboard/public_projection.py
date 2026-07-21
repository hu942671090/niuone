"""Build the small, public read model consumed by Dashboard v2.

The legacy dashboard payload mirrors internal trading state and therefore must
not be served directly from a public CDN.  This module deliberately copies an
explicit field allow-list into versioned presentation sections.  Anything not
listed here remains server-side.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from typing import Any


PUBLIC_SCHEMA_VERSION = 2

ACCOUNT_FIELDS = (
    "initial_cash",
    "cash",
    "market_value",
    "total_equity",
    "total_pnl",
    "total_pnl_pct",
    "sector_tide_open_risk_pct",
)
POSITION_FIELDS = (
    "code",
    "name",
    "qty",
    "available_qty",
    "avg_cost",
    "last_price",
    "prev_close",
    "change_pct",
    "day_high_pct",
    "day_low_pct",
    "today_pnl",
    "today_pnl_pct",
    "market_value",
    "position_pct",
    "pnl",
    "pnl_pct",
    "bought_today",
    "buy_strategy",
    "entry_reason",
    "strategy_mark_id",
    "strategy_mark_label",
    "industry",
)
EQUITY_FIELDS = ("time", "equity", "cash", "market_value", "pnl", "pnl_pct")
TRADE_FIELDS = (
    "time",
    "action",
    "code",
    "name",
    "shares",
    "price",
    "amount",
    "fee",
    "pnl",
    "pnl_pct",
    "is_full_exit",
    "position_after_trade_pct",
    "reason",
)
DECISION_FIELDS = ("time", "trade_reason", "status", "summary")
CANDIDATE_FIELDS = (
    "code",
    "name",
    "strategy",
    "strategies",
    "score",
    "price",
    "change_pct",
    "industry",
    "sector",
    "reason",
    "rank",
)
MESSAGE_FIELDS = ("id", "created_at", "time", "category", "platform", "title", "content", "summary")
BENCHMARK_FIELDS = ("symbol", "name", "base", "count")
BENCHMARK_POINT_FIELDS = ("time", "minute", "price", "pct")


def _public_scalar(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return str(value)


def _public_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return default


def _copy_fields(source: Any, fields: Iterable[str]) -> dict[str, Any]:
    if not isinstance(source, Mapping):
        return {}
    return {field: _public_scalar(source[field]) for field in fields if field in source}


def _copy_rows(source: Any, fields: Iterable[str], *, limit: int) -> list[dict[str, Any]]:
    if not isinstance(source, list):
        return []
    rows = [_copy_fields(item, fields) for item in source[-limit:] if isinstance(item, Mapping)]
    return [row for row in rows if row]


def _decision_rows(source: Any, *, limit: int = 30) -> list[dict[str, Any]]:
    if not isinstance(source, list):
        return []
    result: list[dict[str, Any]] = []
    for item in source[-limit:]:
        if not isinstance(item, Mapping):
            continue
        row = _copy_fields(item, DECISION_FIELDS)
        decision = item.get("decision")
        if isinstance(decision, Mapping):
            row["summary"] = _public_scalar(decision.get("summary") or row.get("summary") or "")
            actions = decision.get("actions")
            if isinstance(actions, list):
                row["action_count"] = len(actions)
        executed = item.get("executed")
        if isinstance(executed, list):
            row["executed_count"] = len(executed)
        if row:
            result.append(row)
    return result


def _candidate_rows(source: Any, *, limit: int = 24) -> list[dict[str, Any]]:
    if not isinstance(source, list):
        return []
    result = []
    for item in source[:limit]:
        row = _copy_fields(item, CANDIDATE_FIELDS)
        strategies = item.get("strategies") if isinstance(item, Mapping) else None
        if isinstance(strategies, list):
            row["strategies"] = [_public_scalar(value) for value in strategies[:8]]
        if row:
            result.append(row)
    return result


def _benchmark_rows(source: Any) -> list[dict[str, Any]]:
    if not isinstance(source, list):
        return []
    result = []
    for item in source[:8]:
        if not isinstance(item, Mapping):
            continue
        row = _copy_fields(item, BENCHMARK_FIELDS)
        row["points"] = _copy_rows(item.get("points"), BENCHMARK_POINT_FIELDS, limit=300)
        result.append(row)
    return result


def build_public_sections(
    practice: Mapping[str, Any] | None,
    *,
    candidates: Mapping[str, Any] | None = None,
    benchmarks: Mapping[str, Any] | None = None,
    messages: Mapping[str, Any] | None = None,
    market_summary: Mapping[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """Return independently cacheable, sanitised presentation sections."""

    practice = practice if isinstance(practice, Mapping) else {}
    candidates = candidates if isinstance(candidates, Mapping) else {}
    benchmarks = benchmarks if isinstance(benchmarks, Mapping) else {}
    messages = messages if isinstance(messages, Mapping) else {}
    market_summary = market_summary if isinstance(market_summary, Mapping) else {}
    candidate_items = candidates.get("items") or candidates.get("candidates")
    candidate_default_count = len(candidate_items) if isinstance(candidate_items, list) else 0

    metadata = {
        "schema_version": PUBLIC_SCHEMA_VERSION,
        "source_last_equity_time": _public_scalar(practice.get("source_last_equity_time") or ""),
        "snapshot_mode": _public_scalar(practice.get("snapshot_mode") or "fast"),
        "history_scope": _public_scalar(practice.get("equity_history_scope") or "latest_day"),
        "degraded": bool(practice.get("last_error")),
        "trading_paused": bool(practice.get("trading_paused")),
        "pause_reason": _public_scalar(practice.get("pause_reason") or ""),
        "decision_model": _public_scalar(practice.get("decision_model") or ""),
        "decision_provider": _public_scalar(practice.get("decision_provider") or ""),
    }
    account = {
        "schema_version": PUBLIC_SCHEMA_VERSION,
        **_copy_fields(practice, ACCOUNT_FIELDS),
        "positions": _copy_rows(practice.get("positions"), POSITION_FIELDS, limit=100),
    }
    history = {
        "schema_version": PUBLIC_SCHEMA_VERSION,
        "intraday": _copy_rows(practice.get("equity_history"), EQUITY_FIELDS, limit=360),
        "daily": _copy_rows(practice.get("daily_equity_history"), EQUITY_FIELDS, limit=520),
        "trade_markers": _copy_rows(practice.get("trade_markers"), TRADE_FIELDS, limit=300),
    }
    activity = {
        "schema_version": PUBLIC_SCHEMA_VERSION,
        "trades": _copy_rows(practice.get("trade_log"), TRADE_FIELDS, limit=50),
        "decisions": _decision_rows(practice.get("decision_log"), limit=30),
    }
    candidate_section = {
        "schema_version": PUBLIC_SCHEMA_VERSION,
        "count": _public_int(candidates.get("count"), candidate_default_count),
        "items": _candidate_rows(candidate_items),
    }
    benchmark_section = {
        "schema_version": PUBLIC_SCHEMA_VERSION,
        "items": _benchmark_rows(benchmarks.get("items")),
        "degraded": bool(benchmarks.get("error")),
    }
    message_section = {
        "schema_version": PUBLIC_SCHEMA_VERSION,
        "total": _public_int(messages.get("total")),
        "records": _copy_rows(messages.get("records"), MESSAGE_FIELDS, limit=40),
    }
    summary_section = {
        "schema_version": PUBLIC_SCHEMA_VERSION,
        "available": bool(market_summary.get("available") or market_summary.get("summary")),
        "summary": _public_scalar(market_summary.get("summary") or market_summary.get("content") or ""),
        "status": _public_scalar(market_summary.get("status") or ""),
    }
    return {
        "metadata": metadata,
        "account": account,
        "history": history,
        "activity": activity,
        "candidates": candidate_section,
        "benchmarks": benchmark_section,
        "messages": message_section,
        "market_summary": summary_section,
    }
