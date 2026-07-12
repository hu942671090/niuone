"""Pure technical-analysis helpers used by the sell strategy.

The functions in this module only transform caller-provided market data.  They do
not load configuration, fetch quotes, mutate portfolio state, or perform any I/O.
"""

from __future__ import annotations

import statistics
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class SellSignalConfig:
    """Thresholds needed by the strategy-specific pattern detectors."""

    luzhu_medium_yang_pct: float = 2.0
    s1_high_zone_pct: float = 0.90
    s1_uptrend_min_pct: float = 15.0
    s1_volume_ratio: float = 1.5
    s1_close_low_position: float = 0.30


DEFAULT_CONFIG = SellSignalConfig()

RowFloat = Callable[..., float]


def _dependency(provided: Any, default: Any) -> Any:
    return default if provided is None else provided


def _row_float(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(row.get(key) or default)
    except Exception:
        return default


def _ma_last(values: list[float], n: int, end: int | None = None) -> float | None:
    end = len(values) if end is None else end
    if end < n:
        return None
    window = values[end - n:end]
    return statistics.mean(window) if len(window) == n else None


def _ema_series(values: list[float], n: int) -> list[float]:
    if not values:
        return []
    k = 2 / (n + 1)
    out = []
    ema = values[0]
    for value in values:
        ema = value * k + ema * (1 - k)
        out.append(ema)
    return out


def _compute_bbi_series(
    closes: list[float],
    *,
    ma_last: Callable[..., float | None] | None = None,
) -> list[float | None]:
    ma_last = _dependency(ma_last, _ma_last)
    out: list[float | None] = []
    for i in range(len(closes)):
        end = i + 1
        values = [ma_last(closes, n, end) for n in (3, 6, 12, 24)]
        out.append(None if any(value is None for value in values) else sum(float(value) for value in values) / 4)
    return out


def _compute_kdj_snapshot(rows: list[dict[str, Any]]) -> dict[str, float | None]:
    if len(rows) < 9:
        return {
            "k": None,
            "d": None,
            "j": None,
            "k_prev": None,
            "d_prev": None,
            "j_prev": None,
            "min_j_10d": None,
        }
    k_vals: list[float | None] = []
    d_vals: list[float | None] = []
    j_vals: list[float | None] = []
    for i in range(len(rows)):
        if i < 8:
            k_vals.append(None)
            d_vals.append(None)
            j_vals.append(None)
            continue
        window = rows[i - 8:i + 1]
        low = min(float(row.get("low") or 0) for row in window)
        high = max(float(row.get("high") or 0) for row in window)
        close = float(rows[i].get("close") or 0)
        rsv = ((close - low) / (high - low) * 100) if high > low else 50.0
        if i == 8:
            k = 50.0
            d = 50.0
        else:
            k = (2 / 3) * float(k_vals[-1] or 50.0) + (1 / 3) * rsv
            d = (2 / 3) * float(d_vals[-1] or 50.0) + (1 / 3) * k
        j = 3 * k - 2 * d
        k_vals.append(k)
        d_vals.append(d)
        j_vals.append(j)
    valid = [j for j in j_vals[-10:] if j is not None]
    return {
        "k": k_vals[-1],
        "d": d_vals[-1],
        "j": j_vals[-1],
        "k_prev": k_vals[-2] if len(k_vals) >= 2 else None,
        "d_prev": d_vals[-2] if len(d_vals) >= 2 else None,
        "j_prev": j_vals[-2] if len(j_vals) >= 2 else None,
        "min_j_10d": min(valid) if valid else None,
    }


def _compute_latest_kdj(
    rows: list[dict[str, Any]],
    *,
    compute_snapshot: Callable[[list[dict[str, Any]]], dict[str, float | None]] | None = None,
) -> tuple[float | None, float | None, float | None]:
    """Return latest J, previous J and 10-day minimum J."""
    snapshot = _dependency(compute_snapshot, _compute_kdj_snapshot)(rows)
    return snapshot.get("j"), snapshot.get("j_prev"), snapshot.get("min_j_10d")


def _compute_macd_dif_series(
    rows: list[dict[str, Any]],
    *,
    row_float: RowFloat | None = None,
    ema_series: Callable[[list[float], int], list[float]] | None = None,
) -> list[float]:
    row_float = _dependency(row_float, _row_float)
    ema_series = _dependency(ema_series, _ema_series)
    closes = [row_float(row, "close") for row in rows if row_float(row, "close") > 0]
    if not closes:
        return []
    ema12 = ema_series(closes, 12)
    ema26 = ema_series(closes, 26)
    return [fast - slow for fast, slow in zip(ema12, ema26)]


def _compute_z_lines(
    rows: list[dict[str, Any]],
    *,
    row_float: RowFloat | None = None,
    ema_series: Callable[[list[float], int], list[float]] | None = None,
    ma_last: Callable[..., float | None] | None = None,
) -> dict[str, float | bool | None]:
    row_float = _dependency(row_float, _row_float)
    ema_series = _dependency(ema_series, _ema_series)
    ma_last = _dependency(ma_last, _ma_last)
    closes = [row_float(row, "close") for row in rows if row_float(row, "close") > 0]
    if len(closes) < 10:
        return {"white": None, "white_prev": None, "yellow": None, "yellow_prev": None, "dead_cross": False}

    ema1 = ema_series(closes, 10)
    white_series = ema_series(ema1, 10)

    yellow_series: list[float | None] = []
    for i in range(len(closes)):
        end = i + 1
        values = [ma_last(closes, n, end) for n in (14, 28, 57, 114)]
        yellow_series.append(
            None if any(value is None for value in values) else sum(float(value) for value in values) / 4
        )

    white = white_series[-1]
    white_prev = white_series[-2] if len(white_series) >= 2 else None
    yellow = yellow_series[-1]
    yellow_prev = yellow_series[-2] if len(yellow_series) >= 2 else None
    dead_cross = bool(
        white is not None
        and white_prev is not None
        and yellow is not None
        and yellow_prev is not None
        and white_prev >= yellow_prev
        and white < yellow
    )
    return {
        "white": white,
        "white_prev": white_prev,
        "yellow": yellow,
        "yellow_prev": yellow_prev,
        "dead_cross": dead_cross,
    }


def _is_fangliang_yinxian(
    rows: list[dict[str, Any]],
    index: int,
    *,
    row_float: RowFloat | None = None,
) -> bool:
    row_float = _dependency(row_float, _row_float)
    if index <= 0 or index >= len(rows):
        return False
    today = rows[index]
    close = row_float(today, "close")
    open_price = row_float(today, "open")
    volume = row_float(today, "volume")
    previous_volume = row_float(rows[index - 1], "volume")
    start = max(0, index - 5)
    average_volume = statistics.mean(
        [row_float(row, "volume") for row in rows[start:index] if row_float(row, "volume") > 0]
        or [previous_volume]
    )
    return close < open_price and volume >= max(previous_volume, average_volume) * 1.3


def _compute_atr(rows: list[dict[str, Any]], lookback: int = 20) -> float | None:
    if len(rows) < 2:
        return None
    ranges = []
    for i in range(1, len(rows)):
        high = float(rows[i].get("high") or 0)
        low = float(rows[i].get("low") or 0)
        previous_close = float(rows[i - 1].get("close") or 0)
        if high <= 0 or low <= 0 or previous_close <= 0:
            continue
        ranges.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
    if not ranges:
        return None
    return statistics.mean(ranges[-lookback:])


def _compute_sell_score(
    rows: list[dict[str, Any]],
    bbi: float | None,
    *,
    row_float: RowFloat | None = None,
    compute_bbi: Callable[[list[float]], list[float | None]] | None = None,
    compute_kdj: Callable[[list[dict[str, Any]]], dict[str, float | None]] | None = None,
    is_volume_bear: Callable[[list[dict[str, Any]], int], bool] | None = None,
    ma_last: Callable[..., float | None] | None = None,
) -> dict[str, Any]:
    """Zettaranc 防卖飞 V1.4: 5-point hold/reduce/exit score."""
    if len(rows) < 2:
        return {"score": 3, "reason": "K线不足", "items": {}}
    row_float = _dependency(row_float, _row_float)
    compute_bbi = _dependency(compute_bbi, _compute_bbi_series)
    compute_kdj = _dependency(compute_kdj, _compute_kdj_snapshot)
    is_volume_bear = _dependency(is_volume_bear, _is_fangliang_yinxian)
    ma_last = _dependency(ma_last, _ma_last)
    today = rows[-1]
    yesterday = rows[-2]
    closes = [row_float(row, "close") for row in rows if row_float(row, "close") > 0]
    bbi_series = compute_bbi(closes)
    kdj = compute_kdj(rows)

    score = 5
    reasons = []
    items: dict[str, bool] = {}

    close_up = row_float(today, "close") > (
        row_float(yesterday, "close") or row_float(today, "prev_close")
    )
    items["close_up"] = close_up
    if not close_up:
        score -= 1
        reasons.append("收盘不涨")

    bbi_value = bbi if bbi else (bbi_series[-1] if bbi_series else None)
    bbi_ok = row_float(today, "close") >= float(bbi_value or 0) if bbi_value else True
    items["above_bbi"] = bbi_ok
    if not bbi_ok:
        score -= 1
        reasons.append("跌破BBI")

    not_volume_bear = not is_volume_bear(rows, len(rows) - 1)
    items["not_volume_bear"] = not_volume_bear
    if not not_volume_bear:
        score -= 1
        reasons.append("放量阴线")

    ma5 = ma_last(closes, 5)
    ma5_previous = ma_last(closes, 5, len(closes) - 1)
    bbi_up = (
        bbi_series[-1] is not None
        and len(bbi_series) >= 2
        and bbi_series[-2] is not None
        and float(bbi_series[-1]) >= float(bbi_series[-2])
    )
    trend_up = bool((ma5 is not None and ma5_previous is not None and ma5 >= ma5_previous) or bbi_up)
    items["trend_up"] = trend_up
    if not trend_up:
        score -= 1
        reasons.append("趋势走弱")

    k_value, d_value, j_value = kdj.get("k"), kdj.get("d"), kdj.get("j")
    j_ok = not (
        isinstance(k_value, (int, float))
        and isinstance(d_value, (int, float))
        and isinstance(j_value, (int, float))
        and float(j_value) < float(k_value)
        and float(j_value) < float(d_value)
    )
    items["kdj_not_dead"] = j_ok
    if not j_ok:
        score -= 1
        reasons.append("J处于死叉状态")

    return {
        "score": max(0, score),
        "reason": "；".join(reasons) if reasons else "无扣分项",
        "items": items,
    }


def _detect_luzhu_half(
    rows: list[dict[str, Any]],
    bbi: float | None,
    *,
    config: SellSignalConfig = DEFAULT_CONFIG,
    row_float: RowFloat | None = None,
) -> dict[str, Any] | None:
    """Zettaranc 卤煮：站上BBI后连续中/大阳，先放飞半仓。"""
    if len(rows) < 2 or not bbi:
        return None
    row_float = _dependency(row_float, _row_float)
    today, yesterday = rows[-1], rows[-2]
    close = row_float(today, "close")
    if close <= bbi:
        return None
    two_yang = close >= row_float(today, "open") and row_float(yesterday, "close") >= row_float(yesterday, "open")
    if not two_yang:
        return None
    today_pct = (
        (close / row_float(yesterday, "close") - 1) * 100
        if row_float(yesterday, "close") > 0
        else row_float(today, "change_pct")
    )
    yesterday_base = row_float(rows[-3], "close") if len(rows) >= 3 else row_float(yesterday, "open")
    yesterday_pct = (
        (row_float(yesterday, "close") / yesterday_base - 1) * 100
        if yesterday_base > 0
        else row_float(yesterday, "change_pct")
    )
    medium_yang = (
        today_pct >= config.luzhu_medium_yang_pct
        and yesterday_pct >= config.luzhu_medium_yang_pct
    )
    volume_ok = (
        row_float(today, "volume") >= row_float(yesterday, "volume") * 0.8
        if row_float(yesterday, "volume") > 0
        else True
    )
    if medium_yang and volume_ok:
        return {"today_pct": round(today_pct, 2), "yesterday_pct": round(yesterday_pct, 2)}
    return None


def _detect_chuhuo_wushi(
    rows: list[dict[str, Any]],
    *,
    row_float: RowFloat | None = None,
) -> dict[str, Any]:
    """主力出货五式：涨多后放量阴线/双头/阶梯/绿肥红瘦。"""
    _row_float = _dependency(row_float, globals()["_row_float"])
    if len(rows) < 20:
        return {"total_score": 0.0, "patterns": [], "is_selling": False}
    today = rows[-1]
    recent_20 = rows[-20:]
    recent_10 = rows[-10:]
    recent_high = max(_row_float(row, "high") for row in recent_20)
    close = _row_float(today, "close")
    if recent_high <= 0 or close < recent_high * 0.85:
        return {"total_score": 0.0, "patterns": [], "is_selling": False}

    patterns: list[dict[str, Any]] = []
    volumes = [_row_float(row, "volume") for row in recent_20 if _row_float(row, "volume") > 0]
    average_volume_5 = (
        statistics.mean(volumes[-5:])
        if len(volumes) >= 5
        else (statistics.mean(volumes) if volumes else 0)
    )
    maximum_volume_20 = max(volumes) if volumes else 0
    pct_change = (
        (close / _row_float(rows[-2], "close") - 1) * 100
        if len(rows) >= 2 and _row_float(rows[-2], "close") > 0
        else 0
    )

    price_10_days_ago = _row_float(rows[-10], "close") if len(rows) >= 10 else close
    up_pct_10 = (recent_high / price_10_days_ago - 1) * 100 if price_10_days_ago > 0 else 0
    is_tianliang = (
        _row_float(today, "volume") >= maximum_volume_20 * 0.8
        or _row_float(today, "volume") >= average_volume_5 * 2
    )
    if up_pct_10 > 20 and pct_change < -5 and is_tianliang:
        patterns.append({"type": "加速后单日放天量大阴", "confidence": 0.95})

    high_5d = max(_row_float(row, "high") for row in recent_10[:5]) if len(recent_10) >= 5 else recent_high
    if _row_float(today, "high") >= high_5d * 0.98 and pct_change < -3 and close < _row_float(today, "open"):
        if len(rows) >= 2 and _row_float(today, "volume") >= _row_float(rows[-2], "volume") * 1.5:
            patterns.append({"type": "次高点巨量长阴", "confidence": 0.90})

    consecutive_yin = 0
    for i in range(1, min(6, len(rows))):
        row = rows[-i]
        if _row_float(row, "close") < _row_float(row, "open"):
            consecutive_yin += 1
        else:
            break
    if consecutive_yin >= 3:
        yin_volumes = [_row_float(rows[-i], "volume") for i in range(1, consecutive_yin + 1)]
        if average_volume_5 > 0 and statistics.mean(yin_volumes) >= average_volume_5 * 1.2:
            patterns.append({"type": f"阶梯放量下跌({consecutive_yin}日)", "confidence": 0.85})

    highs = sorted(
        [(i, _row_float(row, "high")) for i, row in enumerate(recent_20)],
        key=lambda item: item[1],
        reverse=True,
    )[:2]
    if (
        len(highs) == 2
        and highs[0][1] > 0
        and abs(highs[0][1] - highs[1][1]) / highs[0][1] < 0.05
        and abs(highs[0][0] - highs[1][0]) >= 3
    ):

        def _has_volume_bear_after(index: int) -> bool:
            for j in range(index + 1, min(index + 4, len(recent_20))):
                row = recent_20[j]
                if (
                    _row_float(row, "close") < _row_float(row, "open")
                    and average_volume_5 > 0
                    and _row_float(row, "volume") >= average_volume_5 * 1.3
                ):
                    return True
            return False

        if _has_volume_bear_after(highs[0][0]) and _has_volume_bear_after(highs[1][0]):
            patterns.append({"type": "双头双放量巨阴", "confidence": 0.90})

    yin_volume = sum(
        _row_float(row, "volume")
        for row in recent_10
        if _row_float(row, "close") < _row_float(row, "open")
    )
    yang_volume = sum(
        _row_float(row, "volume")
        for row in recent_10
        if _row_float(row, "close") >= _row_float(row, "open")
    )
    if yang_volume > 0 and yin_volume / yang_volume > 1.5:
        patterns.append({"type": "顶部绿肥红瘦", "confidence": 0.80})

    total_score = max([pattern["confidence"] for pattern in patterns], default=0.0) + 0.1 * max(0, len(patterns) - 1)
    total_score = min(total_score, 1.0)
    return {"total_score": round(total_score, 2), "patterns": patterns, "is_selling": total_score >= 0.80}


def _detect_s1_s2_s3(
    rows: list[dict[str, Any]],
    *,
    config: SellSignalConfig = DEFAULT_CONFIG,
    row_float: RowFloat | None = None,
    is_volume_bear: Callable[[list[dict[str, Any]], int], bool] | None = None,
    compute_macd: Callable[[list[dict[str, Any]]], list[float]] | None = None,
) -> dict[str, Any]:
    _row_float = _dependency(row_float, globals()["_row_float"])
    _is_fangliang_yinxian = _dependency(is_volume_bear, globals()["_is_fangliang_yinxian"])
    _compute_macd_dif_series = _dependency(compute_macd, globals()["_compute_macd_dif_series"])
    if len(rows) < 20:
        return {"signal": "", "reason": ""}

    def _is_s1_at(index: int) -> bool:
        if index < 20:
            return False
        window = rows[index - 19:index + 1]
        today = rows[index]
        previous = rows[index - 1]
        recent_high = max(_row_float(row, "high") for row in window)
        recent_low = min(_row_float(row, "low") for row in window[:-1])
        if recent_low <= 0:
            return False
        up_pct = (recent_high / recent_low - 1) * 100
        if up_pct < config.s1_uptrend_min_pct or _row_float(today, "close") < recent_high * config.s1_high_zone_pct:
            return False
        day_range = _row_float(today, "high") - _row_float(today, "low")
        close_position = (_row_float(today, "close") - _row_float(today, "low")) / day_range if day_range > 0 else 0.5
        jiayin = (
            _row_float(today, "close") < _row_float(today, "open")
            and _row_float(today, "close") > _row_float(previous, "close")
        )
        ugly = _is_fangliang_yinxian(rows, index) or (
            jiayin
            and _row_float(today, "volume") > _row_float(previous, "volume") * config.s1_volume_ratio
        )
        return ugly and close_position <= config.s1_close_low_position

    if _is_s1_at(len(rows) - 1):
        return {"signal": "s1_distribution", "reason": "S1逃顶：流畅上涨后高位放量丑陋阴线"}

    if len(rows) >= 30:
        dif = _compute_macd_dif_series(rows)
        if len(dif) == len([row for row in rows if _row_float(row, "close") > 0]):
            prior_window = rows[-30:-5]
            if prior_window:
                prior_high = max(_row_float(row, "high") for row in prior_window)
                prior_index_relative = next(
                    (i for i, row in enumerate(prior_window) if _row_float(row, "high") == prior_high),
                    None,
                )
                if prior_index_relative is not None:
                    prior_index = len(rows) - 30 + prior_index_relative
                    if (
                        _row_float(rows[-1], "close") >= prior_high * 0.97
                        and _row_float(rows[-1], "close") > _row_float(rows[prior_index], "close")
                        and dif[-1] < dif[prior_index] * 0.98
                    ):
                        return {"signal": "s2_macd_divergence", "reason": "S2逃顶：挑战前高但MACD DIF顶背离"}

    for index in range(max(20, len(rows) - 15), len(rows) - 1):
        if not _is_s1_at(index):
            continue
        s1 = rows[index]
        today = rows[-1]
        if _row_float(s1, "volume") <= 0:
            continue
        near_s1_zone = (
            _row_float(s1, "open") * 0.95
            <= _row_float(today, "close")
            <= _row_float(s1, "high") * 1.02
        )
        weak_rebound = _row_float(today, "volume") < _row_float(s1, "volume") * 0.7
        pct_change = (
            (_row_float(today, "close") / _row_float(rows[-2], "close") - 1) * 100
            if _row_float(rows[-2], "close") > 0
            else 0
        )
        if near_s1_zone and weak_rebound and pct_change <= 2:
            return {"signal": "s3_last_escape", "reason": "S3逃顶：S1后反抽到下沿但量能不足"}

    return {"signal": "", "reason": ""}


def _sell_signal(reason: str, signal: str, sell_ratio: float = 1.0) -> dict[str, Any]:
    return {"reason": reason, "signal": signal, "sell_ratio": sell_ratio}
