"""Zettaranc (Z哥) strategy scorers."""
import math
import re
import statistics
from typing import Any

from .common import (
    B1_CORE_J_CEILING,
    B1_WATCH_J_CEILING,
    candle_amplitude_pct,
    candle_body_pct,
    is_yang,
    is_yin,
    n_structure_ok,
    pct_change,
    safe_round,
    with_strategy_profile,
)


ZETTARANC_STRATEGY_IDS = frozenset({
    "shaofu_b1",
    "b2_confirm",
    "b3_accelerate",
    "super_b1",
})
ZETTARANC_INDUSTRY_FLOW_MAX_BONUS = 1.50
ZETTARANC_INDUSTRY_FLOW_RANK_STEP = 0.15
_ZETTARANC_VERDICT_LABELS = {
    "shaofu_b1": "少妇B1",
    "b2_confirm": "B2确认",
    "b3_accelerate": "B3中继",
    "super_b1": "超级B1",
}


def _industry_name(value: Any) -> str:
    text = re.sub(r"\s+", "", str(value or "")).strip()
    text = re.sub(r"[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+$", "", text).strip()
    for suffix in ("行业", "板块", "概念", "指数"):
        if text.endswith(suffix) and len(text) > len(suffix) + 1:
            text = text[: -len(suffix)]
    return text


def _flow_number(value: Any) -> float | None:
    try:
        number = float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def zettaranc_industry_flow_signal(
    rows: list[dict[str, Any]],
    context: dict[str, Any] | None,
) -> dict[str, Any]:
    """Map the shared industry main-flow inflow ranking to one Z哥 candidate."""
    latest = rows[-1] if rows else {}
    industry = _industry_name(latest.get("industry"))
    source_context = context if isinstance(context, dict) else {}
    flow_payload = source_context.get("industry_money_flow")
    if not isinstance(flow_payload, dict):
        flow_payload = {}

    metadata = {
        "industry": industry,
        "industry_flow_available": False,
        "industry_flow_matched": False,
        "industry_flow_direction": "neutral",
        "industry_flow_rank": None,
        "industry_flow_rank_total": 0,
        "industry_flow_net_yi": None,
        "industry_outflow_matched": False,
        "industry_outflow_rank": None,
        "industry_outflow_rank_total": 0,
        "industry_outflow_net_yi": None,
        "industry_flow_adjustment": 0.0,
        "industry_flow_source": str(flow_payload.get("source") or ""),
        "industry_flow_generated_at": str(flow_payload.get("generated_at") or ""),
    }
    if (
        not industry
        or flow_payload.get("stale_cache")
        or flow_payload.get("error")
        or str(flow_payload.get("metric") or "") != "industry_main_net_flow"
    ):
        return metadata

    def ranked_rows(key: str, *, positive: bool) -> list[tuple[str, float]]:
        ranked: list[tuple[str, float]] = []
        for row in flow_payload.get(key) or []:
            if not isinstance(row, dict):
                continue
            name = _industry_name(row.get("name") or row.get("industry"))
            value = _flow_number(
                row.get("net_flow_yi")
                if row.get("net_flow_yi") is not None
                else row.get("main_net_flow_yi")
            )
            if name and value is not None and ((positive and value > 0) or (not positive and value < 0)):
                ranked.append((name, value))
        ranked.sort(key=(lambda item: (-item[1], item[0])) if positive else (lambda item: (item[1], item[0])))
        return ranked

    def unique_match(ranked: list[tuple[str, float]]) -> int | None:
        exact = [index for index, (name, _value) in enumerate(ranked) if name == industry]
        partial = [
            index
            for index, (name, _value) in enumerate(ranked)
            if industry in name or name in industry
        ]
        matches = exact or partial
        # Ambiguous partial names (for example, 汽车 vs 汽车整车/汽车零部件)
        # must stay neutral rather than receiving a possibly incorrect signal.
        return matches[0] if len(matches) == 1 else None

    ranked = ranked_rows("inflow", positive=True)
    ranked_outflow = ranked_rows("outflow", positive=False)
    if not ranked and not ranked_outflow:
        return metadata

    metadata["industry_flow_available"] = True
    metadata["industry_flow_rank_total"] = len(ranked)
    metadata["industry_outflow_rank_total"] = len(ranked_outflow)

    matched_index = unique_match(ranked)
    if matched_index is not None:
        matched_name, net_flow_yi = ranked[matched_index]
        rank = matched_index + 1
        adjustment = max(
            0.0,
            ZETTARANC_INDUSTRY_FLOW_MAX_BONUS
            - (rank - 1) * ZETTARANC_INDUSTRY_FLOW_RANK_STEP,
        )
        metadata.update({
            "industry_flow_matched": True,
            "industry_flow_direction": "inflow",
            "industry_flow_industry": matched_name,
            "industry_flow_rank": rank,
            "industry_flow_net_yi": round(net_flow_yi, 4),
            "industry_flow_adjustment": round(adjustment, 2),
        })
        return metadata

    outflow_index = unique_match(ranked_outflow)
    if outflow_index is None:
        return metadata
    matched_name, net_flow_yi = ranked_outflow[outflow_index]
    metadata.update({
        "industry_flow_direction": "outflow",
        "industry_outflow_matched": True,
        "industry_flow_industry": matched_name,
        "industry_outflow_rank": outflow_index + 1,
        "industry_outflow_net_yi": round(net_flow_yi, 4),
    })
    return metadata


def _with_zettaranc_profile(
    strategy_name: str,
    rows: list[dict[str, Any]],
    context: dict[str, Any] | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Apply the bounded industry-flow preference before final profile gates."""
    technical_score = max(0.0, min(10.0, float(payload.get("score") or 0.0)))
    flow_signal = zettaranc_industry_flow_signal(rows, context)
    adjustment = float(flow_signal.get("industry_flow_adjustment") or 0.0)
    adjusted_score = technical_score + adjustment
    displayed_score = min(10.0, adjusted_score)
    label = _ZETTARANC_VERDICT_LABELS[strategy_name]
    payload.update(flow_signal)
    payload["score_before_industry_flow"] = round(technical_score, 1)
    payload["score"] = displayed_score
    payload["verdict"] = (
        f"高匹配{label}" if displayed_score >= 8 else
        f"中等匹配{label}" if displayed_score >= 6 else
        f"弱匹配{label}" if displayed_score >= 4 else "不匹配"
    )
    profiled = with_strategy_profile(strategy_name, payload)
    # Keep the ranking bonus effective even when the visible 10-point score is
    # capped, while retaining the existing score_total contract.
    priority = int(profiled.get("strategy_priority") or 0)
    blocker_penalty = len(profiled.get("hard_blockers") or []) * 1.5
    profiled["decision_score"] = round(
        adjusted_score + priority / 100 - blocker_penalty,
        2,
    )
    return profiled


def recent_b1_indices(rows, lookback=15, end_offset=1):
    """Find recent Z哥B1 traces before the latest bar."""
    end = len(rows) - end_offset
    start = max(0, end - lookback)
    out = []
    for idx in range(start, end):
        row = rows[idx]
        j = row.get("j")
        if j is None:
            continue
        recent4 = rows[max(0, idx - 3):idx + 1]
        green_count = sum(1 for r in recent4 if is_yin(r))
        if j <= B1_CORE_J_CEILING and green_count < 4:
            out.append(idx)
    return out


def score_shaofu_b1(
    rows,
    context: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Z哥少妇B1：J≤12(最好负值) + N型上移 + 缩量回调 + 牛绳/BBI约束。"""
    if len(rows) < 30:
        return None
    recent = rows[-1]
    prev = rows[-2]
    close = recent["close"]
    bbi_r = recent.get("bbi")
    j = recent.get("j")
    if bbi_r is None or j is None or j > B1_WATCH_J_CEILING:
        return None

    recent4 = rows[-4:]
    green_count = sum(1 for r in recent4 if is_yin(r))
    if green_count >= 4:
        return None

    dist_bbi = (close / bbi_r - 1) * 100 if bbi_r else 99
    vol_shrink = recent["volume"] < prev["volume"] * 0.85 if prev.get("volume") else False
    recent5_vol = statistics.mean(r["volume"] for r in rows[-5:])
    prior10_vol = statistics.mean(r["volume"] for r in rows[-15:-5]) if len(rows) >= 15 else recent5_vol
    pullback_shrink = recent5_vol < prior10_vol * 0.9 if prior10_vol else vol_shrink
    n_ok = n_structure_ok(rows, 20)
    white = recent.get("z_white")
    yellow = recent.get("z_yellow")
    bull_rope = (white is not None and yellow is not None and white >= yellow * 0.98) or close >= bbi_r
    stop_space = max(0, (close / recent["low"] - 1) * 100) if recent.get("low") else 99
    yellow_dist = (close / yellow - 1) * 100 if yellow else dist_bbi
    high20 = max(r["high"] for r in rows[-20:])
    pressure_space = (high20 / close - 1) * 100 if close else 0

    score = 0
    if j <= -10:
        score += 2.5
    elif j <= 0:
        score += 2
    else:
        score += 1
    if vol_shrink and pullback_shrink:
        score += 2
    elif vol_shrink or pullback_shrink:
        score += 1.2
    if n_ok:
        score += 1.5
    if bull_rope:
        score += 1
    if stop_space <= 4.5:
        score += 1.5
    elif stop_space <= 6:
        score += 1
    if -3 <= dist_bbi <= 5 and abs(yellow_dist) <= 8:
        score += 1
    if pressure_space >= 5:
        score += 1
    if j > B1_CORE_J_CEILING:
        score = min(score, 7.5)
    if dist_bbi > 6.5:
        score = min(score, 7.5)
    if stop_space > 8:
        score = min(score, 6.5)
    score = min(10, score)

    risk_flags = []
    if not vol_shrink and not pullback_shrink:
        risk_flags.append("未明显缩量")
    if j > B1_CORE_J_CEILING:
        risk_flags.append("J值未到核心B1")
    if not n_ok:
        risk_flags.append("N型上移不足")
    if not bull_rope:
        risk_flags.append("白线/BBI支撑不足")
    if dist_bbi > 6.5:
        risk_flags.append("距BBI偏远")
    if stop_space > 8:
        risk_flags.append("止损空间偏大")
    if pressure_space < 5:
        risk_flags.append("上方空间不足")

    return _with_zettaranc_profile("shaofu_b1", rows, context, {
        "score": score, "score_total": 10,
        "bbi": safe_round(bbi_r, 2), "distance_pct": safe_round(dist_bbi, 2),
        "above_bbi": close >= bbi_r, "bbi_upward": bool(len(rows) >= 2 and rows[-2].get("bbi") and bbi_r >= rows[-2]["bbi"]),
        "current_j": safe_round(j, 2), "min_j_10d": safe_round(min(r.get("j") for r in rows[-10:] if r.get("j") is not None), 2),
        "j_recovering": len(rows) >= 2 and rows[-2].get("j") is not None and j > rows[-2]["j"],
        "j_oversold": j <= B1_CORE_J_CEILING,
        "vol_shrink": vol_shrink, "pullback_shrink": pullback_shrink,
        "n_structure": n_ok, "bull_rope": bull_rope,
        "z_white": safe_round(white, 2), "z_yellow": safe_round(yellow, 2),
        "stop_space_pct": safe_round(stop_space, 2),
        "yellow_distance_pct": safe_round(yellow_dist, 2),
        "pressure_space_pct": safe_round(pressure_space, 2),
        "risk_flags": risk_flags,
        "recent_close": safe_round(close, 2),
        "change_pct": safe_round(recent.get("change_pct"), 2),
    })


def score_b2_confirm(
    rows,
    context: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Z哥B2确认：B1后3日内放量中/大阳，J未过热，趋势确认。"""
    if len(rows) < 35:
        return None
    recent = rows[-1]
    prev = rows[-2]
    b1_idxs = recent_b1_indices(rows, lookback=3, end_offset=1)
    if not b1_idxs:
        return None
    days_from_b1 = len(rows) - 1 - b1_idxs[-1]
    if days_from_b1 < 1 or days_from_b1 > 3:
        return None

    change_pct = recent.get("change_pct") or pct_change(recent, prev) or 0
    j = recent.get("j") or 99
    bbi_r = recent.get("bbi")
    close = recent["close"]
    if bbi_r is None:
        return None
    dist_bbi = (close / bbi_r - 1) * 100 if bbi_r else 99

    long_yang = is_yang(recent) and change_pct >= 4
    vol_ratio = recent["volume"] / prev["volume"] if prev.get("volume") else 0
    vol_expand = vol_ratio >= 1.2
    above_bbi = close >= bbi_r
    upper_shadow = recent["high"] - max(recent["close"], recent["open"])
    body = abs(recent["close"] - recent["open"])
    upper_ok = body <= 0 or upper_shadow <= body * 1.2

    if not long_yang:
        return None

    score = 4
    if 1 <= days_from_b1 <= 3:
        score += 1.5
    if vol_expand:
        score += 1.5
        if vol_ratio <= 3:
            score += 0.5
    if j < 55:
        score += 1.5
    elif j < 70:
        score += 0.5
    if above_bbi:
        score += 1
    if upper_ok:
        score += 1
    if dist_bbi <= 6.5:
        score += 1
    if j >= 70:
        score = min(score, 7.0)
    if dist_bbi > 8:
        score = min(score, 7.5)
    if change_pct >= 9 and dist_bbi > 6.5:
        score = min(score, 7.0)
    score = min(10, score)

    risk_flags = []
    if not vol_expand:
        risk_flags.append("量能确认不足")
    if j >= 55:
        risk_flags.append("J值偏热")
    if not upper_ok:
        risk_flags.append("上影偏长")
    if not above_bbi:
        risk_flags.append("未站上BBI")
    if dist_bbi > 6.5:
        risk_flags.append("距BBI偏远")

    return _with_zettaranc_profile("b2_confirm", rows, context, {
        "score": score, "score_total": 10,
        "bbi": safe_round(bbi_r, 2), "distance_pct": safe_round(dist_bbi, 2),
        "above_bbi": above_bbi, "bbi_upward": bool(len(rows) >= 2 and rows[-2].get("bbi") and bbi_r >= rows[-2]["bbi"]),
        "current_j": safe_round(j, 2), "j_recovering": True, "j_oversold": False,
        "days_from_b1": days_from_b1, "vol_expand": vol_expand, "vol_ratio": safe_round(vol_ratio, 2),
        "risk_flags": risk_flags,
        "recent_close": safe_round(close, 2),
        "change_pct": safe_round(change_pct, 2),
    })


def score_b3_accelerate(
    rows,
    context: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Z哥B3：B2后小阳/十字星，振幅小，分歧转一致。"""
    if len(rows) < 40:
        return None
    recent = rows[-1]
    prev = rows[-2]
    bbi_r = recent.get("bbi")
    if bbi_r is None:
        return None

    has_b2 = False
    b2_distance = None
    for offset in range(2, min(6, len(rows))):
        row = rows[-offset]
        prev_row = rows[-offset - 1] if offset + 1 <= len(rows) else None
        row_pct = row.get("change_pct") or pct_change(row, prev_row) or 0
        vol_ok = prev_row is not None and row["volume"] >= prev_row["volume"] * 1.2
        if row_pct >= 4 and is_yang(row) and vol_ok:
            has_b2 = True
            b2_distance = offset - 1
            break
    if not has_b2:
        return None
    if b2_distance is None or b2_distance > 3:
        return None

    change_pct = recent.get("change_pct") or pct_change(recent, prev) or 0
    amplitude = candle_amplitude_pct(recent)
    small_consensus = -1.5 <= change_pct < 2 and amplitude < 6 and recent["close"] >= recent["open"] * 0.985
    if not small_consensus:
        return None

    close = recent["close"]
    j = recent.get("j") or 99
    dist_bbi = (close / bbi_r - 1) * 100 if bbi_r else 99
    score = 6
    if close >= bbi_r and dist_bbi <= 5:
        score += 1
    if j < 70:
        score += 0.8
    if amplitude <= 4.5:
        score += 1
    elif amplitude < 6:
        score += 0.5
    if b2_distance <= 1:
        score += 1.2
    elif b2_distance <= 2:
        score += 1
    else:
        score += 0.4
    volume_not_explode = recent["volume"] <= prev["volume"] * 1.2 if prev.get("volume") else True
    if volume_not_explode:
        score += 1
    if -0.5 <= change_pct <= 1.5:
        score += 0.5
    if j >= 90:
        score = min(score, 8.0)
    elif j >= 70:
        score = min(score, 8.5)
    if dist_bbi > 6.5:
        score = min(score, 7.5)
    score = min(10, score)

    risk_flags = []
    if close < bbi_r:
        risk_flags.append("未站上BBI")
    if j >= 70:
        risk_flags.append("J值过热")
    if amplitude >= 6:
        risk_flags.append("振幅偏大")
    if dist_bbi > 6.5:
        risk_flags.append("距BBI偏远")

    return _with_zettaranc_profile("b3_accelerate", rows, context, {
        "score": score, "score_total": 10,
        "bbi": safe_round(bbi_r, 2), "distance_pct": safe_round(dist_bbi, 2),
        "above_bbi": close >= bbi_r, "bbi_upward": bool(len(rows) >= 2 and rows[-2].get("bbi") and bbi_r >= rows[-2]["bbi"]),
        "current_j": safe_round(j, 2), "j_recovering": True, "j_oversold": False,
        "b2_distance": b2_distance, "amplitude_pct": safe_round(amplitude, 2),
        "volume_not_explode": volume_not_explode,
        "risk_flags": risk_flags,
        "recent_close": safe_round(close, 2),
        "change_pct": safe_round(change_pct, 2),
    })


def score_super_b1(
    rows,
    context: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Z哥超级B1：放量破位洗盘后缩量企稳，J值仍在负值/低位。"""
    if len(rows) < 35:
        return None
    recent = rows[-1]
    prev = rows[-2]
    bbi_r = recent.get("bbi")
    j = recent.get("j")
    if bbi_r is None or j is None or j > -5:
        return None

    wash_idx = None
    for idx in range(max(1, len(rows) - 6), len(rows) - 1):
        row = rows[idx]
        prior = rows[idx - 1]
        row_pct = row.get("change_pct") or pct_change(row, prior) or 0
        if is_yin(row) and row["volume"] >= prior["volume"] * 1.5 and row_pct <= -2:
            wash_idx = idx
            break
    if wash_idx is None:
        return None

    close = recent["close"]
    wash_low = rows[wash_idx]["low"]
    wash_days_ago = len(rows) - 1 - wash_idx
    shrink = recent["volume"] < prev["volume"] * 0.85 if prev.get("volume") else False
    stable = close >= wash_low * 0.98 and recent["low"] >= wash_low * 0.97
    small_body = candle_body_pct(recent) <= 2.5
    n_ok = n_structure_ok(rows, 20)
    dist_bbi = (close / bbi_r - 1) * 100 if bbi_r else 99
    stop_space = (close / wash_low - 1) * 100 if wash_low else 99
    if not (shrink and stable):
        return None

    score = 2.5
    if j <= -10:
        score += 2
    else:
        score += 1
    if shrink:
        score += 1
    if stable:
        score += 1
    if small_body:
        score += 1
    if close >= bbi_r * 0.97 and dist_bbi <= 5:
        score += 1
    if n_ok:
        score += 1
    if wash_days_ago <= 3:
        score += 1
    if stop_space <= 6:
        score += 1
    if close < bbi_r * 0.97:
        score = min(score, 7.0)
    if stop_space > 8:
        score = min(score, 7.0)
    if wash_days_ago > 3:
        score = min(score, 7.5)
    score = min(9, score)

    risk_flags = []
    if close < bbi_r * 0.97:
        risk_flags.append("仍低于BBI")
    if not n_ok:
        risk_flags.append("N型结构不足")
    if not small_body:
        risk_flags.append("企稳K线实体偏大")
    if stop_space > 8:
        risk_flags.append("洗盘低点止损空间偏大")
    if wash_days_ago > 3:
        risk_flags.append("洗盘信号不够新")

    return _with_zettaranc_profile("super_b1", rows, context, {
        "score": score, "score_total": 10,
        "bbi": safe_round(bbi_r, 2), "distance_pct": safe_round(dist_bbi, 2),
        "above_bbi": close >= bbi_r, "bbi_upward": bool(len(rows) >= 2 and rows[-2].get("bbi") and bbi_r >= rows[-2]["bbi"]),
        "current_j": safe_round(j, 2), "min_j_10d": safe_round(min(r.get("j") for r in rows[-10:] if r.get("j") is not None), 2),
        "j_recovering": len(rows) >= 2 and rows[-2].get("j") is not None and j > rows[-2]["j"],
        "j_oversold": True,
        "wash_days_ago": wash_days_ago,
        "stop_space_pct": safe_round(stop_space, 2),
        "risk_flags": risk_flags,
        "recent_close": safe_round(close, 2),
        "change_pct": safe_round(recent.get("change_pct"), 2),
    })


score_shaofu_b1.requires_context = True  # type: ignore[attr-defined]
score_b2_confirm.requires_context = True  # type: ignore[attr-defined]
score_b3_accelerate.requires_context = True  # type: ignore[attr-defined]
score_super_b1.requires_context = True  # type: ignore[attr-defined]
