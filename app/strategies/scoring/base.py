"""Built-in local strategy scorers."""
import statistics
from typing import Any

from .common import safe_round, with_strategy_profile


def score_trend_pullback(rows) -> dict[str, Any] | None:
    """趋势回踩战法：强趋势股回踩 BBI/EMA20 不破"""
    if len(rows) < 30:
        return None

    recent = rows[-1]; prev = rows[-2]
    close = recent["close"]
    bbi_r = recent.get("bbi"); bbi_p = prev.get("bbi")
    ema20_r = recent.get("ema20"); ema20_p = prev.get("ema20")
    ema50_r = recent.get("ema50")
    ema20_list = [r.get("ema20") for r in rows[-20:] if r.get("ema20") is not None]

    if bbi_r is None or ema20_r is None:
        return None

    dist_bbi = ((close / bbi_r - 1) * 100) if bbi_r else 99
    dist_ema20 = ((close / ema20_r - 1) * 100) if ema20_r else 99

    # BBI上升趋势
    bbi_up_3d = all(
        rows[i].get("bbi") is not None and rows[i].get("bbi") > (rows[i-1].get("bbi") or 0)
        for i in range(-3, 0)
    ) if len(rows) >= 4 else False

    # 近5日是否有回踩 (最低点接近 BBI)
    recent5_low = min(r["low"] for r in rows[-5:])
    pullback_occurred = recent5_low <= bbi_r * 1.03  # 回踩到了离BBI 3%内
    pullback_held = recent5_low >= bbi_r * 0.97     # 回踩不破BBI 3%

    # 调整期缩量(近5日均量 < 前10日均量 * 0.8)
    recent5_vol = statistics.mean(r["volume"] for r in rows[-5:])
    prior10_vol = statistics.mean(r["volume"] for r in rows[-15:-5]) if len(rows) >= 15 else recent5_vol
    vol_shrink = recent5_vol < prior10_vol * 0.85

    # 当日转强
    today_strong = recent.get("change_pct") is not None and recent.get("change_pct", -99) > -1.5

    # 趋势确认
    trend_up = bbi_up_3d and (ema20_r >= ema50_r * 0.98 if ema50_r else True)

    # 位置舒服
    position_ok = 0 <= dist_bbi <= 5 and -1 <= dist_ema20 <= 4

    # 10分制打分
    score = 0
    # 板块/趋势强度 (0-2)
    score += 2 if trend_up else (1 if bbi_up_3d else 0)
    # 回踩质量 (0-3)
    if pullback_occurred and pullback_held and vol_shrink:
        score += 3
    elif pullback_occurred and pullback_held:
        score += 2
    elif pullback_occurred:
        score += 1
    # 转强确认 (0-2)
    score += 2 if today_strong and close >= bbi_r else (1 if close >= bbi_r else 0)
    # 位置舒适度 (0-3)
    if position_ok and dist_bbi <= 3:
        score += 3
    elif position_ok:
        score += 2
    elif close >= bbi_r:
        score += 1

    # 偏离过远降级
    if dist_bbi > 6.5:
        score = max(0, score - 2)
    if dist_bbi > 10:
        score = max(0, score - 3)

    risk_flags = []
    if close < bbi_r:
        risk_flags.append("收盘在BBI下方")
    if dist_bbi > 6.5:
        risk_flags.append("距BBI偏远")
    if not trend_up:
        risk_flags.append("趋势不明确")

    verdict = ("高匹配趋势回踩" if score >= 8 else
               "中等匹配趋势回踩" if score >= 6 else
               "弱匹配趋势回踩" if score >= 4 else "不匹配")

    return with_strategy_profile("trend_pullback", {
        "score": score, "score_total": 10, "verdict": verdict,
        "bbi": safe_round(bbi_r, 2), "distance_pct": safe_round(dist_bbi, 2),
        "ema20_distance": safe_round(dist_ema20, 2),
        "bbi_upward": bbi_up_3d, "above_bbi": close >= bbi_r,
        "pullback_occurred": pullback_occurred, "pullback_held": pullback_held,
        "vol_shrink": vol_shrink, "today_strong": today_strong,
        "risk_flags": risk_flags,
        "recent_close": safe_round(close, 2),
        "change_pct": safe_round(recent.get("change_pct"), 2),
    })


def score_breakout(rows) -> dict[str, Any] | None:
    """突破确认战法：平台/前高突破后回踩不破"""
    if len(rows) < 40:
        return None

    recent = rows[-1]; close = recent["close"]
    bbi_r = recent.get("bbi"); ema20_r = recent.get("ema20")

    if bbi_r is None:
        return None

    # 找过去30日的高点平台 (看前15-30日的价格区间)
    platform_lookback = rows[-30:-5] if len(rows) >= 35 else rows[-25:-3]
    if len(platform_lookback) < 10:
        return None
    platform_high = max(r["high"] for r in platform_lookback)
    platform_low = min(r["low"] for r in platform_lookback)
    platform_range = (platform_high / platform_low - 1) * 100 if platform_low > 0 else 0

    # 平台必须有一定宽度（不是单边趋势）
    has_platform = 3 <= platform_range <= 18

    # 近5日是否突破了平台高点
    recent5_high = max(r["high"] for r in rows[-5:])
    above_platform = close > platform_high * 1.005  # 收盘站稳平台上方0.5%

    # 突破当天的量能（近3日均量 vs 平台期均量）
    recent3_vol = statistics.mean(r["volume"] for r in rows[-3:])
    platform_vol = statistics.mean(r["volume"] for r in platform_lookback)
    vol_expand = recent3_vol >= platform_vol * 1.15  # 量能放大15%以上
    vol_not_explode = recent3_vol <= platform_vol * 3.5  # 不放量过猛

    # 如果无清晰平台，尝试看前高突破 (40日新高)
    high40 = max(r["high"] for r in rows[-40:])
    is_new_high = close > high40 * 0.98 and close >= high40 * 0.99  # 接近或刷新40日高点

    # 回踩确认：突破后没有立刻跌回平台
    recent5_low = min(r["low"] for r in rows[-5:])
    pullback_confirmed = recent5_low >= platform_high * 0.97 if above_platform else True

    # BBI向上
    bbi_up = all(
        rows[i].get("bbi") is not None and (rows[i].get("bbi") or 0) > (rows[i-1].get("bbi") or 0)
        for i in range(-3, 0)
    ) if len(rows) >= 4 else False

    # 位置不能太远
    dist_bbi = ((close / bbi_r - 1) * 100) if bbi_r else 99

    # 10分制打分
    score = 0
    # 蓄势质量 (0-2)
    score += 2 if has_platform else (1 if platform_range > 0 else 0)
    # 突破有效性 (0-3)
    if above_platform and vol_expand and vol_not_explode and pullback_confirmed:
        score += 3
    elif above_platform and vol_expand:
        score += 2
    elif above_platform or (is_new_high and vol_expand):
        score += 1
    # 趋势支撑 (0-2)
    score += 2 if bbi_up and close >= bbi_r else (1 if close >= bbi_r else 0)
    # 位置/盈亏比 (0-3)
    if dist_bbi <= 4 and above_platform:
        score += 3
    elif dist_bbi <= 6:
        score += 2
    elif dist_bbi <= 8:
        score += 1

    # 距离过远降级
    if dist_bbi > 8:
        score = max(0, score - 2)
    if dist_bbi > 12:
        score = max(0, score - 3)

    risk_flags = []
    if not pullback_confirmed and above_platform:
        risk_flags.append("回踩确认不充分")
    if vol_expand and not vol_not_explode:
        risk_flags.append("放量过猛(疑似出货)")
    if close < bbi_r:
        risk_flags.append("收盘在BBI下方")
    if dist_bbi > 8:
        risk_flags.append("距BBI偏远")

    verdict = ("高匹配突破确认" if score >= 8 else
               "中等匹配突破确认" if score >= 6 else
               "弱匹配突破确认" if score >= 4 else "不匹配")

    return with_strategy_profile("breakout", {
        "score": score, "score_total": 10, "verdict": verdict,
        "bbi": safe_round(bbi_r, 2), "distance_pct": safe_round(dist_bbi, 2),
        "bbi_upward": bbi_up, "above_bbi": close >= bbi_r,
        "platform_detected": has_platform, "above_platform": above_platform,
        "vol_expand": vol_expand, "pullback_confirmed": pullback_confirmed,
        "risk_flags": risk_flags,
        "recent_close": safe_round(close, 2),
        "change_pct": safe_round(recent.get("change_pct"), 2),
    })
