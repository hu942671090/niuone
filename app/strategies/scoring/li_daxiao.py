"""Li Daxiao style bottom-value strategy scorer."""
import statistics
from typing import Any

from .common import (
    LI_DAXIAO_HOT_TURNOVER,
    LI_DAXIAO_MAX_BBI_DISTANCE,
    LI_DAXIAO_MAX_DAILY_CHASE_PCT,
    LI_DAXIAO_MAX_TURNOVER,
    LI_DAXIAO_MIN_AMOUNT,
    li_daxiao_bottom_stage,
    return_pct,
    safe_float,
    safe_round,
    volatility_pct,
    with_strategy_profile,
)


def score_li_daxiao_bottom(rows) -> dict[str, Any] | None:
    """李大霄风格代理：低估蓝筹、底部发育、远离黑五类和杠杆热度。"""
    if len(rows) < 80:
        return None

    recent = rows[-1]
    close = recent["close"]
    bbi_r = recent.get("bbi")
    ema20_r = recent.get("ema20")
    ema50_r = recent.get("ema50")
    if bbi_r is None or ema20_r is None or ema50_r is None:
        return None

    window120 = rows[-min(120, len(rows)):]
    high120 = max(r["high"] for r in window120)
    low120 = min(r["low"] for r in window120)
    low20 = min(r["low"] for r in rows[-20:])
    drawdown_from_high = return_pct(close, high120) or 0
    distance_from_low = return_pct(close, low120) or 0
    dist_bbi = (close / bbi_r - 1) * 100 if bbi_r else 99
    recent_change = safe_float(recent.get("change_pct"))
    amount = safe_float(recent.get("quote_amount") if "quote_amount" in recent else recent.get("amount"))
    turnover = safe_float(recent.get("quote_turnover") if "quote_turnover" in recent else recent.get("turnover"))
    symbol_code = str(recent.get("symbol_code") or recent.get("code") or "")
    stock_name = str(recent.get("stock_name") or recent.get("name") or "")
    vol20 = volatility_pct(rows, 20)
    recent5_vol = statistics.mean(r["volume"] for r in rows[-5:])
    prior20_vol = statistics.mean(r["volume"] for r in rows[-25:-5]) if len(rows) >= 25 else recent5_vol
    avg60_vol = statistics.mean(r["volume"] for r in rows[-60:])
    volume_shrink = prior20_vol > 0 and recent5_vol <= prior20_vol * 0.9
    quote_liquidity_ok = amount is None or amount >= LI_DAXIAO_MIN_AMOUNT
    volume_liquidity_ok = avg60_vol > 0 and recent5_vol >= avg60_vol * 0.35
    bluechip_liquidity_proxy = volume_liquidity_ok and quote_liquidity_ok
    turnover_calm = turnover is None or turnover <= LI_DAXIAO_MAX_TURNOVER
    turnover_hot = turnover is not None and turnover >= LI_DAXIAO_HOT_TURNOVER
    core_board_proxy = not symbol_code or symbol_code.startswith(("600", "601", "603", "605", "000", "001", "002"))
    not_fresh_listing_proxy = len(rows) >= 110 and not stock_name.startswith(("N", "C"))
    daily_chase = recent_change is not None and recent_change > LI_DAXIAO_MAX_DAILY_CHASE_PCT
    speculation_heat = (
        turnover_hot
        or (turnover is not None and turnover > LI_DAXIAO_MAX_TURNOVER and (recent_change or 0) > 2)
        or (daily_chase and dist_bbi > 2.5)
    )
    value_anchor_proxy = bluechip_liquidity_proxy and turnover_calm and core_board_proxy
    anti_black_five_proxy = (
        not_fresh_listing_proxy
        and quote_liquidity_ok
        and not speculation_heat
        and (core_board_proxy or turnover_calm)
    )
    no_chase_zone = dist_bbi <= LI_DAXIAO_MAX_BBI_DISTANCE and not daily_chase
    bbi_flattening = len(rows) >= 5 and bbi_r >= min((r.get("bbi") or bbi_r) for r in rows[-5:]) * 0.995
    stabilizing = close >= bbi_r * 0.98 and close >= ema20_r * 0.97 and recent["low"] >= low20 * 0.985
    bottom_zone = -45 <= drawdown_from_high <= -12 and distance_from_low <= 18
    breakdown_risk = close < low20 * 1.02 and (recent.get("change_pct") or 0) < -1.5
    low_volatility = vol20 is not None and vol20 <= 3.8
    bottom_stage = li_daxiao_bottom_stage(drawdown_from_high, distance_from_low)

    score = 0.0
    if bottom_zone:
        score += 2.2
    elif -55 <= drawdown_from_high <= -8 and distance_from_low <= 25:
        score += 1.3
    if stabilizing:
        score += 1.6
    elif close >= bbi_r * 0.96:
        score += 0.8
    if volume_shrink:
        score += 1.0
    if low_volatility:
        score += 1.1 if vol20 is not None and vol20 <= 2.8 else 0.7
    if bbi_flattening:
        score += 0.8
    if value_anchor_proxy:
        score += 1.4
    elif bluechip_liquidity_proxy:
        score += 0.6
    if anti_black_five_proxy:
        score += 1.0
    if no_chase_zone:
        score += 0.8
    if not breakdown_risk:
        score += 0.6
    if close >= ema50_r * 0.94:
        score += 0.5
    if distance_from_low > 25:
        score = min(score, 7.2)
    if breakdown_risk:
        score = min(score, 6.8)
    if vol20 is not None and vol20 > 4.5:
        score = min(score, 6.5)
    if not value_anchor_proxy:
        score = min(score, 7.6)
    if not anti_black_five_proxy:
        score = min(score, 7.4)
    if not no_chase_zone:
        score = min(score, 7.0)
    if speculation_heat:
        score = min(score, 6.8)
    if not not_fresh_listing_proxy:
        score = min(score, 6.8)
    score = min(10, score)

    risk_flags = []
    if not bottom_zone:
        risk_flags.append("低位区不充分")
    if not stabilizing:
        risk_flags.append("企稳不足")
    if not volume_shrink:
        risk_flags.append("未缩量")
    if breakdown_risk:
        risk_flags.append("仍贴近破位低点")
    if vol20 is not None and vol20 > 3.8:
        risk_flags.append("底部波动偏高")
    if not value_anchor_proxy:
        risk_flags.append("低估蓝筹代理不足")
    if not anti_black_five_proxy:
        risk_flags.append("黑五类/题材热度代理偏高")
    if not no_chase_zone:
        risk_flags.append("不符合正金字塔低吸")
    if turnover_hot:
        risk_flags.append("换手偏热")
    if daily_chase:
        risk_flags.append("单日涨幅偏高")
    if not not_fresh_listing_proxy:
        risk_flags.append("次新代理风险")

    verdict = ("高匹配李大霄" if score >= 8 else
               "中等匹配李大霄" if score >= 6 else
               "弱匹配李大霄" if score >= 4 else "不匹配")
    return with_strategy_profile("li_daxiao_bottom", {
        "score": score, "score_total": 10, "verdict": verdict,
        "bbi": safe_round(bbi_r, 2), "distance_pct": safe_round(dist_bbi, 2),
        "above_bbi": close >= bbi_r,
        "bbi_upward": bbi_flattening,
        "bottom_zone": bottom_zone,
        "bottom_stage": bottom_stage,
        "stabilizing": stabilizing,
        "volume_shrink": volume_shrink,
        "bluechip_liquidity_proxy": bluechip_liquidity_proxy,
        "value_anchor_proxy": value_anchor_proxy,
        "anti_black_five_proxy": anti_black_five_proxy,
        "not_fresh_listing_proxy": not_fresh_listing_proxy,
        "no_chase_zone": no_chase_zone,
        "speculation_heat": speculation_heat,
        "core_board_proxy": core_board_proxy,
        "turnover_calm": turnover_calm,
        "quote_amount_yi": safe_round(amount / 1e8, 2) if amount is not None else None,
        "quote_turnover_pct": safe_round(turnover, 2),
        "breakdown_risk": breakdown_risk,
        "drawdown_from_high_pct": safe_round(drawdown_from_high, 2),
        "distance_from_low_pct": safe_round(distance_from_low, 2),
        "volatility_20d_pct": safe_round(vol20, 2),
        "ema20": safe_round(ema20_r, 2),
        "ema50": safe_round(ema50_r, 2),
        "risk_flags": risk_flags,
        "recent_close": safe_round(close, 2),
        "change_pct": safe_round(recent.get("change_pct"), 2),
    })
