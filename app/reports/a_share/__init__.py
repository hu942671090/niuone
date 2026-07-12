"""Shared A-share report primitives."""

from .common import (
    first_col,
    fmt_amt_yuan,
    is_normal_a_share,
    is_trading_day_guess,
    normalize_code,
    normalize_industry_name,
    parse_money_to_yuan,
    safe_float,
    safe_int,
    time_limit,
)
from .calendar import is_a_share_trading_day, trading_day_status

__all__ = [
    "first_col",
    "fmt_amt_yuan",
    "is_normal_a_share",
    "is_a_share_trading_day",
    "is_trading_day_guess",
    "normalize_code",
    "normalize_industry_name",
    "parse_money_to_yuan",
    "safe_float",
    "safe_int",
    "time_limit",
    "trading_day_status",
]
