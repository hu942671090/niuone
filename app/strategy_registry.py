#!/usr/bin/env python3
"""Shared strategy metadata for scanner, trader, and dashboard payloads."""
from __future__ import annotations

import os
from typing import Any


PERSONA_STRATEGY_ENV = "DASHBOARD_ENABLED_PERSONA_STRATEGIES"
DEPRECATED_STRATEGY_OPTION_IDS = {"buffett_value"}

STRATEGY_DEFINITIONS: dict[str, dict[str, Any]] = {
    "b3_accelerate": {
        "label": "B3中继",
        "color": "#a78bfa",
        "desc": "B2后小阳/十字星分歧转一致",
        "family": "persona",
        "persona": "zettaranc",
        "scorer": "score_b3_accelerate",
        "display_order": 10,
        "position_limit_pct": 10.0,
        "aliases": ["B3", "B3中继", "b3_accelerate"],
        "profile": {
            "priority": 90,
            "entry_threshold": 8.5,
            "score_basis": "确定性最高/盈亏比最低",
            "position_hint": "快进快出，次日09:30不涨走",
            "time_stop": "T+1开盘09:30不涨退出",
            "certainty_rank": 1,
            "risk_reward_rank": 4,
        },
    },
    "b2_confirm": {
        "label": "B2确认",
        "color": "#22c55e",
        "desc": "B1后3日内放量中/大阳确认趋势",
        "family": "persona",
        "persona": "zettaranc",
        "scorer": "score_b2_confirm",
        "display_order": 20,
        "position_limit_pct": 10.0,
        "aliases": ["B2", "B2确认", "b2_confirm"],
        "profile": {
            "priority": 82,
            "entry_threshold": 8.0,
            "score_basis": "趋势确认/放量长阳",
            "position_hint": "确认仓，拒绝追高",
            "time_stop": "T+2尾盘14:45不延续退出",
            "certainty_rank": 2,
            "risk_reward_rank": 3,
        },
    },
    "breakout": {
        "label": "突破确认",
        "color": "#ec4899",
        "desc": "平台/前高突破后回踩站稳",
        "family": "local",
        "scorer": "score_breakout",
        "display_order": 30,
        "position_limit_pct": 10.0,
        "aliases": ["突破确认", "突破", "breakout"],
        "profile": {
            "priority": 76,
            "entry_threshold": 8.0,
            "score_basis": "突破确认",
            "position_hint": "确认仓",
            "time_stop": "跌回平台内降预期",
            "certainty_rank": 2,
            "risk_reward_rank": 3,
        },
    },
    "shaofu_b1": {
        "label": "少妇B1",
        "color": "#f97316",
        "desc": "J≤12(最好负值)+N型上移+缩量回调+牛绳约束",
        "family": "persona",
        "persona": "zettaranc",
        "scorer": "score_shaofu_b1",
        "display_order": 40,
        "position_limit_pct": 8.0,
        "aliases": ["少妇B1", "shaofu_b1"],
        "profile": {
            "priority": 72,
            "entry_threshold": 8.0,
            "score_basis": "胜率与盈亏比优先",
            "position_hint": "试错仓，止损必须近",
            "time_stop": "3天不涨走",
            "certainty_rank": 3,
            "risk_reward_rank": 1,
        },
    },
    "trend_pullback": {
        "label": "趋势回踩",
        "color": "#60a5fa",
        "desc": "趋势股回踩BBI/EMA不破",
        "family": "local",
        "scorer": "score_trend_pullback",
        "display_order": 50,
        "position_limit_pct": 8.0,
        "aliases": ["趋势回踩", "trend_pullback"],
        "profile": {
            "priority": 68,
            "entry_threshold": 8.0,
            "score_basis": "趋势回踩",
            "position_hint": "低吸仓",
            "time_stop": "跌破BBI/EMA支撑走",
            "certainty_rank": 3,
            "risk_reward_rank": 2,
        },
    },
    "super_b1": {
        "label": "超级B1",
        "color": "#fb7185",
        "desc": "放量破位洗盘后缩量企稳且J值仍负",
        "family": "persona",
        "persona": "zettaranc",
        "scorer": "score_super_b1",
        "display_order": 70,
        "position_limit_pct": 6.0,
        "aliases": ["超级B1", "super_b1"],
        "profile": {
            "priority": 58,
            "entry_threshold": 8.5,
            "score_basis": "洗盘反转/只赌一次",
            "position_hint": "小仓试错，破洗盘低点走",
            "time_stop": "14:45检查未兑现则退出",
            "certainty_rank": 4,
            "risk_reward_rank": 2,
        },
    },
    "li_daxiao_bottom": {
        "label": "李大霄",
        "color": "#f59e0b",
        "desc": "低估蓝筹、底部发育、逆向情绪和去杠杆防守代理",
        "family": "persona",
        "persona": "li_daxiao",
        "scorer": "score_li_daxiao_bottom",
        "display_order": 80,
        "position_limit_pct": 5.0,
        "aliases": ["李大霄", "李大霄底部", "李大霄低位企稳", "li_daxiao", "li_daxiao_bottom"],
        "profile": {
            "priority": 56,
            "entry_threshold": 8.0,
            "score_basis": "低估蓝筹/底部发育/安全边际代理",
            "position_hint": "余钱小仓、正金字塔分批，不追高不上杠杆",
            "time_stop": "底部发育失败、放量破位或题材过热退出",
            "certainty_rank": 4,
            "risk_reward_rank": 2,
            "decision_heuristics": [
                "做好人买好股得好报：只看主板高流动性蓝筹代理，优先低估和高股息方向",
                "黑五类回避：小盘、次新、伪成长、垃圾、题材炒作一律降级观察",
                "正金字塔分批：底部区域越跌越谨慎观察，涨疯了不追",
                "杠杆毒药：高换手、融资偿还、放量破位时不买或降仓",
            ],
        },
    },
}


STRATEGY_META: dict[str, dict[str, Any]] = {
    key: {
        "label": value["label"],
        "color": value["color"],
        "desc": value["desc"],
        "family": value.get("family", ""),
        "display_order": value.get("display_order", 999),
    }
    for key, value in STRATEGY_DEFINITIONS.items()
}

STRATEGY_SCORE_PROFILES: dict[str, dict[str, Any]] = {
    key: dict(value["profile"])
    for key, value in STRATEGY_DEFINITIONS.items()
}

STRATEGY_POSITION_LIMIT_PCT: dict[str, float] = {
    key: float(value.get("position_limit_pct", 10.0))
    for key, value in STRATEGY_DEFINITIONS.items()
}

DISPLAY_STRATEGY_ORDER: tuple[str, ...] = tuple(
    key
    for key, _ in sorted(
        STRATEGY_DEFINITIONS.items(),
        key=lambda item: int(item[1].get("display_order", 999)),
    )
)

_ALIAS_TO_STRATEGY: dict[str, str] = {}
for _strategy_id, _definition in STRATEGY_DEFINITIONS.items():
    for _alias in [_strategy_id, *(_definition.get("aliases") or [])]:
        _ALIAS_TO_STRATEGY[str(_alias).lower()] = _strategy_id


def known_strategy_ids() -> set[str]:
    return set(STRATEGY_DEFINITIONS.keys())


def strategy_ids_for_family(family: str) -> tuple[str, ...]:
    return tuple(
        key
        for key in DISPLAY_STRATEGY_ORDER
        if STRATEGY_DEFINITIONS.get(key, {}).get("family") == family
    )


def strategy_ids_for_persona(persona: str) -> tuple[str, ...]:
    return tuple(
        key
        for key in DISPLAY_STRATEGY_ORDER
        if STRATEGY_DEFINITIONS.get(key, {}).get("persona") == persona
    )


CONFIGURABLE_STRATEGY_GROUPS: dict[str, dict[str, Any]] = {
    "zettaranc": {
        "id": "zettaranc",
        "label": "Z哥",
        "desc": "少妇B1、B2确认、B3中继、超级B1",
        "color": "#f97316",
        "strategy_ids": strategy_ids_for_persona("zettaranc"),
    },
}


def individual_persona_strategy_ids() -> tuple[str, ...]:
    grouped_ids = {
        str(strategy_id)
        for group in CONFIGURABLE_STRATEGY_GROUPS.values()
        for strategy_id in (group.get("strategy_ids") or ())
    }
    return tuple(
        key
        for key in DISPLAY_STRATEGY_ORDER
        if STRATEGY_DEFINITIONS.get(key, {}).get("family") == "persona" and key not in grouped_ids
    )


def configurable_strategy_option_ids() -> tuple[str, ...]:
    return tuple(CONFIGURABLE_STRATEGY_GROUPS.keys()) + individual_persona_strategy_ids()


def default_enabled_persona_strategies_value() -> str:
    options = configurable_strategy_option_ids()
    return options[0] if options else ""


def normalize_strategy_list_update(value: str, *, family: str = "persona") -> str:
    allowed = set(configurable_strategy_option_ids() if family == "persona" else strategy_ids_for_family(family))
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in str(value or "").replace("，", ",").split(","):
        strategy_id = raw.strip()
        if not strategy_id:
            continue
        if strategy_id in DEPRECATED_STRATEGY_OPTION_IDS:
            continue
        if strategy_id not in allowed:
            raise ValueError(f"未知策略: {strategy_id}")
        if strategy_id not in seen:
            seen.add(strategy_id)
            normalized.append(strategy_id)
        if family == "persona" and normalized:
            break
    return ",".join(normalized)


def enabled_persona_strategy_ids(raw: str | None = None) -> set[str]:
    if raw is None:
        raw = os.environ.get(PERSONA_STRATEGY_ENV)
    if raw is None:
        raw = default_enabled_persona_strategies_value()
    normalized = normalize_strategy_list_update(raw, family="persona")
    return set(normalized.split(",")) if normalized else set()


def enabled_strategy_ids(enabled_persona_raw: str | None = None) -> set[str]:
    enabled = {
        key
        for key, definition in STRATEGY_DEFINITIONS.items()
        if definition.get("family") == "local"
    }
    enabled_options = enabled_persona_strategy_ids(enabled_persona_raw)
    for option_id in enabled_options:
        group = CONFIGURABLE_STRATEGY_GROUPS.get(option_id)
        if group:
            enabled.update(str(strategy_id) for strategy_id in group.get("strategy_ids") or ())
        elif option_id in STRATEGY_DEFINITIONS:
            enabled.add(option_id)
    return enabled


def enabled_strategy_meta(enabled_persona_raw: str | None = None) -> dict[str, dict[str, Any]]:
    enabled = enabled_strategy_ids(enabled_persona_raw)
    return {key: value for key, value in STRATEGY_META.items() if key in enabled}


def enabled_strategy_score_profiles(enabled_persona_raw: str | None = None) -> dict[str, dict[str, Any]]:
    enabled = enabled_strategy_ids(enabled_persona_raw)
    return {key: value for key, value in STRATEGY_SCORE_PROFILES.items() if key in enabled}


def classify_strategy_text(text: str) -> str | None:
    """Return a strategy id when text contains a registered id or alias."""
    raw = str(text or "")
    if not raw:
        return None
    lowered = raw.lower()
    for alias in sorted(_ALIAS_TO_STRATEGY, key=len, reverse=True):
        if alias and alias in lowered:
            return _ALIAS_TO_STRATEGY[alias]
    for alias, strategy_id in sorted(_ALIAS_TO_STRATEGY.items(), key=lambda item: len(item[0]), reverse=True):
        if alias and alias in raw:
            return strategy_id
    return None


def strategy_prompt_labels(enabled_ids: set[str] | None = None) -> dict[str, str]:
    selected = set(STRATEGY_DEFINITIONS.keys()) if enabled_ids is None else enabled_ids
    return {
        key: f"{value['label']}（{value['desc']}）"
        for key, value in STRATEGY_DEFINITIONS.items()
        if key in selected
    }


def strategy_settings_options(*, family: str = "persona") -> list[dict[str, Any]]:
    group_options = [
        {
            "id": key,
            "label": value["label"],
            "desc": value["desc"],
            "color": value["color"],
        }
        for key, value in CONFIGURABLE_STRATEGY_GROUPS.items()
    ] if family == "persona" else []
    strategy_ids = individual_persona_strategy_ids() if family == "persona" else strategy_ids_for_family(family)
    strategy_options = [
        {
            "id": key,
            "label": STRATEGY_DEFINITIONS[key]["label"],
            "desc": STRATEGY_DEFINITIONS[key]["desc"],
            "color": STRATEGY_DEFINITIONS[key]["color"],
        }
        for key in strategy_ids
    ]
    return group_options + strategy_options
