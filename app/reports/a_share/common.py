"""Side-effect-free helpers shared by A-share report entry points."""

from __future__ import annotations

import contextlib
import math
import re
import signal
from collections.abc import Iterator
from typing import Any


def is_trading_day_guess(day: Any) -> bool:
    """Return the weekday guard used by scheduled report jobs.

    The cron scheduler owns holiday-calendar accuracy; this fallback only
    prevents direct weekend execution.
    """

    return day.weekday() < 5


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, str):
            value = value.replace("%", "").replace(",", "").strip()
            if value in {"", "-", "--", "None", "nan"}:
                return default
        number = float(value)
        return default if math.isnan(number) or math.isinf(number) else number
    except Exception:
        return default


def safe_int(
    value: Any,
    default: int = 0,
    *,
    safe_number: Any = None,
) -> int:
    parser = safe_float if safe_number is None else safe_number
    return int(parser(value, default))


def fmt_amt_yuan(value: float | int | None) -> str:
    if value is None:
        return "-"
    amount = float(value)
    if abs(amount) >= 1e8:
        return f"{amount / 1e8:.2f}亿"
    if abs(amount) >= 1e4:
        return f"{amount / 1e4:.0f}万"
    return f"{amount:.0f}元"


def parse_money_to_yuan(value: Any, *, safe_number: Any = None) -> float:
    """Parse Chinese money strings such as ``1.23亿`` into yuan."""

    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        parser = safe_float if safe_number is None else safe_number
        return parser(value)
    text = str(value).replace(",", "").strip()
    if not text or text in {"-", "--", "nan", "None"}:
        return 0.0
    match = re.search(r"([-+]?\d+(?:\.\d+)?)", text)
    if not match:
        return 0.0
    amount = float(match.group(1))
    if "亿" in text:
        amount *= 1e8
    elif "万" in text:
        amount *= 1e4
    return amount


@contextlib.contextmanager
def time_limit(seconds: int) -> Iterator[None]:
    """Bound an optional slow source on platforms that provide ``SIGALRM``."""

    if seconds <= 0 or not hasattr(signal, "SIGALRM"):
        yield
        return

    def _handler(_signum: int, _frame: Any) -> None:
        raise TimeoutError(f"timed out after {seconds}s")

    previous = signal.signal(signal.SIGALRM, _handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


def first_col(frame: Any, names: list[str]) -> Any | None:
    columns = {str(column): column for column in frame.columns}
    for name in names:
        if name in columns:
            return columns[name]
    for name in names:
        for column in frame.columns:
            if name in str(column):
                return column
    return None


def normalize_code(code: Any) -> str:
    text = str(code).strip()
    match = re.search(r"(\d{6})", text)
    return match.group(1) if match else text


def is_normal_a_share(code: str, name: str, *, code_normalizer: Any = None) -> bool:
    normalizer = normalize_code if code_normalizer is None else code_normalizer
    normalized = normalizer(code)
    if not re.match(r"^(60|68|00|30)\d{4}$", normalized):
        return False
    return "ST" not in name.upper() and "退" not in name and not name.startswith("N")


def is_full_market_a_share(code: str, name: str = "", *, code_normalizer: Any = None) -> bool:
    """Return whether a quote belongs to the full on-exchange A-share universe.

    Market-breadth reports intentionally keep ST, newly listed, and delisting-period
    stocks because they are trading A shares and affect the day's advance/decline
    totals.  The Beijing Stock Exchange prefixes cover both legacy NEEQ-derived
    codes and the newer 92xxxx code range.
    """

    del name  # Kept in the signature so callers can share their existing filter shape.
    normalizer = normalize_code if code_normalizer is None else code_normalizer
    normalized = normalizer(code)
    return bool(re.match(r"^(?:(?:60|68|00|30|43|83|87|88|92)\d{4})$", normalized))


def is_bse_a_share(code: str, *, code_normalizer: Any = None) -> bool:
    """Return whether an A-share code belongs to the Beijing Stock Exchange."""

    normalizer = normalize_code if code_normalizer is None else code_normalizer
    normalized = normalizer(code)
    return bool(re.match(r"^(?:43|83|87|88|92)\d{4}$", normalized))


def normalize_industry_name(name: str) -> str:
    normalized = str(name or "").strip()
    for suffix in ("行业", "板块", "概念"):
        if normalized.endswith(suffix) and len(normalized) > len(suffix) + 1:
            normalized = normalized[: -len(suffix)]
    return normalized
