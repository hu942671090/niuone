"""Normalized Dashboard services backed by the iWencai query gateway."""

from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo

if __package__ and __package__.startswith("app."):
    from ...core.json_cache import read_json_cache, write_json_cache
    from ...market_data.iwencai_client import (
        IwencaiClient,
        IwencaiConfig,
        IwencaiError,
    )
else:
    from core.json_cache import read_json_cache, write_json_cache
    from market_data.iwencai_client import IwencaiClient, IwencaiConfig, IwencaiError


CN_TZ = ZoneInfo("Asia/Shanghai")
SOURCE_NAME = "同花顺问财"
DEFAULT_LIMIT = 100
MAX_LIMIT = 100
SOURCE_PAGE_LIMIT = 100
MAX_SOURCE_PAGES = 5
DETAIL_FIELDS = (
    "list_date",
    "list_type",
    "reason",
    "buy_amount_yuan",
    "sell_amount_yuan",
    "net_amount_yuan",
    "buy_ratio_pct",
    "sell_ratio_pct",
    "net_ratio_pct",
)


def read_dragon_tiger_snapshot(
    path: Path,
    *,
    trade_date: str | None = None,
) -> dict[str, Any] | None:
    """Read a validated durable snapshot, optionally requiring one trade date."""

    payload = read_json_cache(path)
    if not payload or payload.get("available") is not True:
        return None
    if not isinstance(payload.get("items"), list) or not payload.get("items"):
        return None
    snapshot_date = str(payload.get("date") or "")
    if trade_date is not None and snapshot_date != normalize_trade_date(trade_date):
        return None
    result = dict(payload)
    result["items"] = deduplicate_dragon_tiger_items(result["items"])
    result["returned_count"] = len(result["items"])
    result["unique_count"] = max(
        len(result["items"]),
        int(result.get("unique_count") or 0),
    )
    result["snapshot"] = True
    return result


def write_dragon_tiger_snapshot(path: Path, payload: Mapping[str, Any]) -> bool:
    """Atomically persist only a complete, non-empty successful response."""

    items = payload.get("items")
    if payload.get("available") is not True or not isinstance(items, list) or not items:
        return False
    trade_date = normalize_trade_date(str(payload.get("date") or ""))
    stored = dict(payload)
    stored["date"] = trade_date
    stored["snapshot"] = True
    stored["snapshot_saved_at"] = datetime.now(CN_TZ).isoformat(timespec="seconds")
    write_json_cache(path, stored)
    return True


def normalize_trade_date(value: str | None, *, now: datetime | None = None) -> str:
    raw = str(value or "").strip()
    if not raw:
        current = now or datetime.now(CN_TZ)
        return current.astimezone(CN_TZ).strftime("%Y-%m-%d")
    compact = raw.replace("-", "")
    try:
        parsed = datetime.strptime(compact, "%Y%m%d")
    except ValueError as exc:
        raise ValueError("date 必须使用 YYYY-MM-DD") from exc
    return parsed.strftime("%Y-%m-%d")


def normalize_page(value: int | str) -> int:
    try:
        page = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("page 必须是正整数") from exc
    if page < 1 or page > 100:
        raise ValueError("page 必须在 1 到 100 之间")
    return page


def normalize_limit(value: int | str) -> int:
    try:
        limit = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("limit 必须是正整数") from exc
    if limit < 1 or limit > MAX_LIMIT:
        raise ValueError(f"limit 必须在 1 到 {MAX_LIMIT} 之间")
    return limit


def _number(value: Any) -> float | None:
    if value in (None, "", "--"):
        return None
    try:
        return float(str(value).replace(",", "").replace("%", "").strip())
    except (TypeError, ValueError):
        return None


def _streak_count(value: Any) -> int | None:
    """Normalize iWencai streak fields such as 2, 2.0, or ``2天``."""

    if value in (None, "", "--"):
        return None
    matched = re.search(r"-?\d+(?:\.\d+)?", str(value).replace(",", ""))
    if not matched:
        return None
    return max(0, int(float(matched.group(0))))


def _max_streak(*values: Any) -> int | None:
    normalized = [count for value in values if (count := _streak_count(value)) is not None]
    return max(normalized) if normalized else None


def _dynamic_value(item: Mapping[str, Any], *prefixes: str) -> Any:
    for prefix in prefixes:
        if prefix in item:
            return item[prefix]
        for key, value in item.items():
            if str(key).startswith(prefix + "["):
                return value
    return None


def _iso_list_date(value: Any, fallback: str) -> str:
    compact = str(value or "").strip().replace("-", "")
    if len(compact) == 8 and compact.isdigit():
        return f"{compact[:4]}-{compact[4:6]}-{compact[6:]}"
    return fallback


def _sector_parts(value: Any) -> list[str]:
    if isinstance(value, (list, tuple)):
        candidates = value
    else:
        candidates = str(value or "").replace(">", "/").split("/")
    return [str(part).strip() for part in candidates if str(part).strip()]


def _sector_values(item: Mapping[str, Any]) -> tuple[str, str]:
    parts = _sector_parts(
        item.get("所属同花顺行业")
        or item.get("所属行业")
        or item.get("板块")
    )
    return (parts[-1] if parts else "", " / ".join(parts))


def _normalize_item(
    item: Mapping[str, Any],
    trade_date: str,
    *,
    sector: str = "",
    sector_path: str = "",
) -> dict[str, Any]:
    return {
        "code": str(item.get("股票代码") or item.get("证券代码") or ""),
        "name": str(item.get("股票简称") or item.get("证券简称") or ""),
        "sector": sector,
        "sector_path": sector_path,
        "price": _number(item.get("最新价")),
        "change_pct": _number(item.get("最新涨跌幅")),
        "limit_up_streak": _streak_count(_dynamic_value(item, "连续涨停天数")),
        "limit_down_streak": _streak_count(
            _dynamic_value(item, "连续跌停天数", "最近连续跌停天数")
        ),
        "list_date": _iso_list_date(item.get("上榜日期"), trade_date),
        "list_type": str(item.get("榜单类型") or ""),
        "reason": str(item.get("上榜原因") or ""),
        "buy_amount_yuan": _number(_dynamic_value(item, "买入额", "龙虎榜买入额")),
        "sell_amount_yuan": _number(_dynamic_value(item, "卖出额", "龙虎榜卖出额")),
        "net_amount_yuan": _number(_dynamic_value(item, "净买入额", "龙虎榜净买入额")),
        "buy_ratio_pct": _number(_dynamic_value(item, "买入额占成交额比例")),
        "sell_ratio_pct": _number(_dynamic_value(item, "卖出额占成交额比例")),
        "net_ratio_pct": _number(_dynamic_value(item, "净买入额占成交额比例")),
    }


def _detail_from_item(item: Mapping[str, Any]) -> dict[str, Any]:
    return {field: item.get(field) for field in DETAIL_FIELDS}


def _detail_key(item: Mapping[str, Any]) -> tuple[Any, ...]:
    return tuple(item.get(field) for field in DETAIL_FIELDS)


def _primary_rank(item: Mapping[str, Any]) -> tuple[int, int]:
    list_type = str(item.get("list_type") or "")
    return (
        2 if "单日" in list_type else 1 if "三日" in list_type else 0,
        1 if item.get("net_amount_yuan") is not None else 0,
    )


def deduplicate_dragon_tiger_items(items: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return one row per stock while retaining distinct leaderboard details."""

    grouped: dict[str, dict[str, Any]] = {}
    detail_keys: dict[str, set[tuple[Any, ...]]] = {}
    for index, source in enumerate(items):
        item = dict(source)
        code = str(item.get("code") or "").strip()
        name = str(item.get("name") or "").strip()
        stock_key = code or (f"name:{name}" if name else f"row:{index}")
        current = grouped.get(stock_key)
        if current is None:
            current = dict(item)
            current["details"] = []
            grouped[stock_key] = current
            detail_keys[stock_key] = set()
        elif _primary_rank(item) > _primary_rank(current):
            preserved_details = current["details"]
            preserved_sector = current.get("sector")
            preserved_sector_path = current.get("sector_path")
            preserved_limit_up_streak = current.get("limit_up_streak")
            preserved_limit_down_streak = current.get("limit_down_streak")
            current.update(item)
            current["details"] = preserved_details
            if not current.get("sector"):
                current["sector"] = preserved_sector
            if not current.get("sector_path"):
                current["sector_path"] = preserved_sector_path
            current["limit_up_streak"] = _max_streak(
                current.get("limit_up_streak"),
                preserved_limit_up_streak,
            )
            current["limit_down_streak"] = _max_streak(
                current.get("limit_down_streak"),
                preserved_limit_down_streak,
            )
        else:
            if not current.get("sector") and item.get("sector"):
                current["sector"] = item.get("sector")
            if not current.get("sector_path") and item.get("sector_path"):
                current["sector_path"] = item.get("sector_path")
            current["limit_up_streak"] = _max_streak(
                current.get("limit_up_streak"),
                item.get("limit_up_streak"),
            )
            current["limit_down_streak"] = _max_streak(
                current.get("limit_down_streak"),
                item.get("limit_down_streak"),
            )

        source_details = item.get("details")
        if not isinstance(source_details, list) or not source_details:
            source_details = [_detail_from_item(item)]
        for source_detail in source_details:
            if not isinstance(source_detail, Mapping):
                continue
            detail = {field: source_detail.get(field) for field in DETAIL_FIELDS}
            if not any(value not in (None, "") for value in detail.values()):
                continue
            key = _detail_key(detail)
            if key in detail_keys[stock_key]:
                continue
            detail_keys[stock_key].add(key)
            current["details"].append(detail)

    result = list(grouped.values())
    for item in result:
        item["detail_count"] = len(item["details"])
    result.sort(
        key=lambda item: (
            item.get("net_amount_yuan") is not None,
            item.get("net_amount_yuan") or 0.0,
        ),
        reverse=True,
    )
    return result


def _reported_count(result: Mapping[str, Any]) -> int:
    try:
        return int(result.get("code_count") or 0)
    except (TypeError, ValueError):
        return 0


def _stock_code(item: Mapping[str, Any]) -> str:
    return str(item.get("股票代码") or item.get("证券代码") or "").strip()


def _query_all_stock_rows(
    client: IwencaiClient,
    query: str,
) -> tuple[list[dict[str, Any]], int, str]:
    rows: list[dict[str, Any]] = []
    seen_codes: set[str] = set()
    reported_count = 0
    trace_id = ""
    for source_page in range(1, MAX_SOURCE_PAGES + 1):
        result = client.query(
            query,
            page=source_page,
            limit=SOURCE_PAGE_LIMIT,
        )
        if not trace_id:
            trace_id = str(result.get("trace_id") or "")
        reported_count = max(reported_count, _reported_count(result))
        page_rows = [item for item in result.get("datas", []) if isinstance(item, dict)]
        rows.extend(page_rows)
        seen_codes.update(filter(None, (_stock_code(item) for item in page_rows)))
        if not page_rows:
            break
        if len(page_rows) < SOURCE_PAGE_LIMIT and (
            not reported_count or len(seen_codes) >= reported_count
        ):
            break
    return rows, reported_count, trace_id


def _empty_payload(
    *,
    enabled: bool,
    trade_date: str,
    page: int,
    limit: int,
    error: str,
) -> dict[str, Any]:
    return {
        "enabled": enabled,
        "available": False,
        "source": SOURCE_NAME,
        "date": trade_date,
        "page": page,
        "limit": limit,
        "reported_count": 0,
        "returned_count": 0,
        "has_more": False,
        "count_mismatch": False,
        "items": [],
        "error": error,
    }


def fetch_dragon_tiger(
    trade_date: str | None = None,
    *,
    page: int | str = 1,
    limit: int | str = DEFAULT_LIMIT,
    env: Mapping[str, str] | None = None,
    client: IwencaiClient | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Fetch one normalized daily dragon-tiger list without exposing free-form queries."""

    normalized_date = normalize_trade_date(trade_date, now=now)
    normalized_page = normalize_page(page)
    normalized_limit = normalize_limit(limit)
    values = os.environ if env is None else env
    try:
        config = IwencaiConfig.from_env(values)
    except IwencaiError as exc:
        return _empty_payload(
            enabled=False,
            trade_date=normalized_date,
            page=normalized_page,
            limit=normalized_limit,
            error=exc.code,
        )
    if not config.enabled:
        return _empty_payload(
            enabled=False,
            trade_date=normalized_date,
            page=normalized_page,
            limit=normalized_limit,
            error="iwencai_disabled",
        )
    if not config.api_key:
        return _empty_payload(
            enabled=True,
            trade_date=normalized_date,
            page=normalized_page,
            limit=normalized_limit,
            error="iwencai_not_configured",
        )

    parsed_date = datetime.strptime(normalized_date, "%Y-%m-%d")
    display_date = f"{parsed_date.year}年{parsed_date.month}月{parsed_date.day}日"
    query = (
        f"{display_date}龙虎榜上榜股票、上榜原因、龙虎榜买入金额、卖出金额、净买入额、"
        "连续涨停天数、最近连续跌停天数"
    )
    sector_query = f"{display_date}龙虎榜上榜股票、所属行业"
    active_client = client or IwencaiClient(config)
    try:
        raw_items, reported_count, trace_id = _query_all_stock_rows(active_client, query)
    except IwencaiError as exc:
        payload = _empty_payload(
            enabled=True,
            trade_date=normalized_date,
            page=normalized_page,
            limit=normalized_limit,
            error=exc.code,
        )
        if exc.status_code is not None:
            payload["status_code"] = exc.status_code
        return payload

    sector_by_code: dict[str, tuple[str, str]] = {}
    sector_error = ""
    try:
        sector_rows, _sector_reported_count, _sector_trace_id = _query_all_stock_rows(
            active_client,
            sector_query,
        )
    except IwencaiError as exc:
        sector_error = exc.code
        sector_rows = []
    for raw_item in sector_rows:
        code = _stock_code(raw_item)
        if code and code not in sector_by_code:
            sector_by_code[code] = _sector_values(raw_item)

    normalized_items: list[dict[str, Any]] = []
    for raw_item in raw_items:
        sector, sector_path = sector_by_code.get(_stock_code(raw_item), ("", ""))
        normalized_items.append(
            _normalize_item(
                raw_item,
                normalized_date,
                sector=sector,
                sector_path=sector_path,
            )
        )
    all_items = deduplicate_dragon_tiger_items(normalized_items)
    unique_count = len(all_items)
    offset = (normalized_page - 1) * normalized_limit
    items = all_items[offset : offset + normalized_limit]
    returned_count = len(items)
    has_more = offset + returned_count < unique_count
    expected_returned_count = min(
        normalized_limit,
        max(0, reported_count - offset),
    )
    payload = {
        "enabled": True,
        "available": True,
        "source": SOURCE_NAME,
        "date": normalized_date,
        "generated_at": datetime.now(CN_TZ).isoformat(timespec="seconds"),
        "query": query,
        "sector_query": sector_query,
        "page": normalized_page,
        "limit": normalized_limit,
        "reported_count": reported_count,
        "unique_count": unique_count,
        "returned_count": returned_count,
        "raw_returned_count": len(raw_items),
        "expected_returned_count": expected_returned_count,
        "has_more": has_more,
        "count_mismatch": unique_count != reported_count,
        "trace_id": trace_id,
        "items": items,
    }
    if sector_error:
        payload["sector_error"] = sector_error
    return payload
