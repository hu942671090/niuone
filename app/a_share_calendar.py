#!/usr/bin/env python3
"""A-share trading calendar with a cached data-source lookup."""
from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from niuone_paths import get_dashboard_home

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_HOME = get_dashboard_home(PROJECT_ROOT)
CALENDAR_CACHE_FILE = Path(
    os.environ.get(
        "A_SHARE_TRADING_CALENDAR_CACHE",
        DASHBOARD_HOME / "cron" / "state" / "a_share_trading_calendar.json",
    )
).expanduser()

_LOCAL_SITE_PACKAGES_READY = False
_CACHE_MEMO: dict[str, Any] | None = None
_REFRESH_ATTEMPTED_YEARS: set[int] = set()


def _normalize_date(value: datetime | date | str | None = None) -> date:
    if value is None:
        return datetime.now().date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


def _date_text(value: datetime | date | str | None = None) -> str:
    return _normalize_date(value).strftime("%Y-%m-%d")


def _add_local_runtime_site_packages() -> None:
    global _LOCAL_SITE_PACKAGES_READY
    if _LOCAL_SITE_PACKAGES_READY:
        return
    _LOCAL_SITE_PACKAGES_READY = True
    site_root = DASHBOARD_HOME.parent / ".venv" / "lib"
    if not site_root.exists():
        return
    for site_packages in sorted(site_root.glob("python*/site-packages"), reverse=True):
        if site_packages.exists() and str(site_packages) not in sys.path:
            sys.path.insert(0, str(site_packages))
            break


def _parse_trade_date(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return ""
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return text[:10]


def _fetch_trade_dates_from_akshare() -> tuple[set[str], str]:
    _add_local_runtime_site_packages()
    import akshare as ak  # type: ignore

    df = ak.tool_trade_date_hist_sina()
    dates: set[str] = set()
    if df is None:
        return dates, "akshare.tool_trade_date_hist_sina"
    columns = list(getattr(df, "columns", []))
    date_col = "trade_date" if "trade_date" in columns else (columns[0] if columns else "")
    if hasattr(df, "iterrows") and date_col:
        for _, row in df.iterrows():
            text = _parse_trade_date(row.get(date_col))
            if text:
                dates.add(text)
    else:
        for item in df:
            text = _parse_trade_date(item)
            if text:
                dates.add(text)
    return dates, "akshare.tool_trade_date_hist_sina"


def load_cached_calendar(cache_file: Path | None = None) -> dict[str, Any]:
    global _CACHE_MEMO
    cache_file = cache_file or CALENDAR_CACHE_FILE
    if cache_file == CALENDAR_CACHE_FILE and _CACHE_MEMO is not None:
        return dict(_CACHE_MEMO)
    try:
        payload = json.loads(cache_file.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    dates = sorted({d for d in (_parse_trade_date(x) for x in payload.get("dates", [])) if d})
    loaded = {
        "dates": dates,
        "source": payload.get("source") or "",
        "updated_at": payload.get("updated_at") or "",
    }
    if cache_file == CALENDAR_CACHE_FILE:
        _CACHE_MEMO = loaded
    return dict(loaded)


def save_cached_calendar(dates: set[str], source: str, cache_file: Path | None = None) -> dict[str, Any]:
    global _CACHE_MEMO
    cache_file = cache_file or CALENDAR_CACHE_FILE
    payload = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": source,
        "dates": sorted(dates),
    }
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = cache_file.with_suffix(cache_file.suffix + ".new")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(cache_file)
    if cache_file == CALENDAR_CACHE_FILE:
        _CACHE_MEMO = payload
    return dict(payload)


def refresh_trading_calendar(
    *,
    cache_file: Path | None = None,
    fetcher: Callable[[], tuple[set[str], str]] | None = None,
) -> dict[str, Any]:
    fetch_fn = fetcher or _fetch_trade_dates_from_akshare
    dates, source = fetch_fn()
    if not dates:
        raise RuntimeError("empty A-share trading calendar")
    return save_cached_calendar(dates, source, cache_file=cache_file)


def _cache_has_year(dates: set[str], year: int) -> bool:
    prefix = f"{year:04d}-"
    return any(d.startswith(prefix) for d in dates)


def _fallback_previous_weekday(target: date) -> str:
    cur = target - timedelta(days=1)
    while cur.weekday() >= 5:
        cur -= timedelta(days=1)
    return cur.strftime("%Y-%m-%d")


def trading_day_status(
    value: datetime | date | str | None = None,
    *,
    cache_file: Path | None = None,
    allow_refresh: bool = True,
    fetcher: Callable[[], tuple[set[str], str]] | None = None,
) -> dict[str, Any]:
    target = _normalize_date(value)
    target_text = target.strftime("%Y-%m-%d")
    cache_file = cache_file or CALENDAR_CACHE_FILE
    payload = load_cached_calendar(cache_file)
    dates = set(payload.get("dates") or [])
    source = payload.get("source") or "cache"

    if allow_refresh and not _cache_has_year(dates, target.year) and target.year not in _REFRESH_ATTEMPTED_YEARS:
        _REFRESH_ATTEMPTED_YEARS.add(target.year)
        try:
            payload = refresh_trading_calendar(cache_file=cache_file, fetcher=fetcher)
            dates = set(payload.get("dates") or [])
            source = payload.get("source") or source
        except Exception as exc:
            source = f"weekday_fallback:{type(exc).__name__}"

    if _cache_has_year(dates, target.year):
        previous = max((d for d in dates if d < target_text), default="")
        next_day = min((d for d in dates if d > target_text), default="")
        return {
            "date": target_text,
            "is_trading_day": target_text in dates,
            "previous_trading_day": previous,
            "next_trading_day": next_day,
            "source": source or "cache",
            "calendar_cached": True,
        }

    is_weekday = target.weekday() < 5
    return {
        "date": target_text,
        "is_trading_day": is_weekday,
        "previous_trading_day": _fallback_previous_weekday(target),
        "next_trading_day": "",
        "source": source or "weekday_fallback",
        "calendar_cached": False,
    }


def is_a_share_trading_day(value: datetime | date | str | None = None) -> bool:
    return bool(trading_day_status(value).get("is_trading_day"))
