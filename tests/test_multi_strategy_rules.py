#!/usr/bin/env python3
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "app"
sys.path.insert(0, str(SRC))

import multi_strategy_screen as screen  # noqa: E402


class MultiStrategyRuleTests(unittest.TestCase):
    def test_recent_b1_indices_require_core_negative_j(self):
        rows = [{"j": None, "open": 10.0, "close": 10.0} for _ in range(10)]
        rows[4]["j"] = -9.5
        rows[6]["j"] = -10.5

        self.assertEqual(screen.recent_b1_indices(rows, lookback=9, end_offset=1), [6])

    def test_shaofu_b1_above_core_j_is_watch_only(self):
        payload = screen.with_strategy_profile("shaofu_b1", {
            "score": 9.0,
            "distance_pct": 1.0,
            "current_j": -5.0,
            "vol_shrink": True,
            "pullback_shrink": True,
            "n_structure": True,
            "bull_rope": True,
            "stop_space_pct": 4.0,
            "pressure_space_pct": 8.0,
            "risk_flags": [],
        })

        self.assertFalse(payload["actionable"])
        self.assertIn("B1核心J未≤-10", payload["hard_blockers"])

    def test_select_trade_candidates_excludes_hard_blocked_items(self):
        good = {
            "code": "600001",
            "best_score": 9.0,
            "entry_threshold": 8.0,
            "distance_pct": 1.0,
            "actionable": True,
            "hard_blockers": [],
        }
        blocked = {
            "code": "600002",
            "best_score": 9.5,
            "entry_threshold": 8.0,
            "distance_pct": 1.0,
            "actionable": False,
            "hard_blockers": ["B1核心J未≤-10"],
        }

        self.assertEqual(screen.select_trade_candidates([blocked, good]), [good])

    def test_extract_industry_from_individual_info_rows(self):
        rows = [
            {"item": "股票简称", "value": "测试股份"},
            {"item": "行业", "value": "半导体行业"},
        ]

        self.assertEqual(screen.extract_industry_from_individual_info(rows), "半导体")
        self.assertEqual(
            screen.extract_industry_from_individual_info([{"所属板块": "消费电子板块"}]),
            "消费电子",
        )

    def test_extract_industry_from_cninfo_prefers_sw_short_name(self):
        rows = [
            {"分类标准": "中证行业分类标准", "行业中类": "游戏", "变更日期": "2021-12-17"},
            {"分类标准": "申银万国行业分类标准", "行业中类": "游戏Ⅲ", "变更日期": "2021-07-30"},
        ]

        self.assertEqual(screen.extract_industry_from_cninfo_change(rows), "游戏")

    def test_annotate_candidate_industries_adds_sector_alias_once(self):
        display = [{"code": "600001", "name": "测试A"}]
        trade = [{"code": "600001", "name": "测试A"}]
        calls: list[str] = []

        def fake_lookup(code: str) -> str:
            calls.append(code)
            return "银行板块"

        screen.annotate_candidate_industries(display, trade, lookup=fake_lookup)

        self.assertEqual(calls, ["600001"])
        self.assertEqual(display[0]["industry"], "银行")
        self.assertEqual(display[0]["sector"], "银行")
        self.assertEqual(trade[0]["industry"], "银行")
        self.assertEqual(trade[0]["sector"], "银行")

    def test_persona_strategies_are_registered(self):
        old = os.environ.get(screen.PERSONA_STRATEGY_ENV)
        try:
            os.environ.pop(screen.PERSONA_STRATEGY_ENV, None)
            self.assertIn("li_daxiao_bottom", screen.STRATEGY_META)
            self.assertNotIn("buffett_value", screen.STRATEGY_META)
            self.assertIn("li_daxiao_bottom", screen.STRATEGY_SCORERS)
            self.assertNotIn("buffett_value", screen.STRATEGY_SCORERS)
            self.assertEqual(screen.STRATEGY_META["shaofu_b1"]["family"], "persona")
            self.assertEqual(screen.enabled_persona_strategy_ids(), {"zettaranc"})
        finally:
            if old is None:
                os.environ.pop(screen.PERSONA_STRATEGY_ENV, None)
            else:
                os.environ[screen.PERSONA_STRATEGY_ENV] = old

    def test_active_strategy_scorers_follow_persona_setting(self):
        old = os.environ.get(screen.PERSONA_STRATEGY_ENV)
        try:
            os.environ[screen.PERSONA_STRATEGY_ENV] = "buffett_value"
            active = screen.active_strategy_scorers()
            self.assertNotIn("buffett_value", active)
            self.assertNotIn("li_daxiao_bottom", active)
            self.assertNotIn("shaofu_b1", active)
            self.assertIn("trend_pullback", active)

            os.environ[screen.PERSONA_STRATEGY_ENV] = "zettaranc,li_daxiao_bottom,buffett_value"
            active = screen.active_strategy_scorers()
            self.assertNotIn("buffett_value", active)
            self.assertNotIn("li_daxiao_bottom", active)
            self.assertIn("shaofu_b1", active)
            self.assertIn("b3_accelerate", active)

            os.environ[screen.PERSONA_STRATEGY_ENV] = "li_daxiao_bottom,zettaranc"
            active = screen.active_strategy_scorers()
            self.assertIn("li_daxiao_bottom", active)
            self.assertNotIn("shaofu_b1", active)
            self.assertNotIn("b3_accelerate", active)

            os.environ[screen.PERSONA_STRATEGY_ENV] = ""
            active = screen.active_strategy_scorers()
            self.assertNotIn("buffett_value", active)
            self.assertNotIn("li_daxiao_bottom", active)
            self.assertNotIn("shaofu_b1", active)
            self.assertIn("trend_pullback", active)
        finally:
            if old is None:
                os.environ.pop(screen.PERSONA_STRATEGY_ENV, None)
            else:
                os.environ[screen.PERSONA_STRATEGY_ENV] = old

    def test_li_daxiao_profile_applies_hard_blockers(self):
        payload = screen.with_strategy_profile("li_daxiao_bottom", {
            "score": 9.0,
            "distance_pct": 1.0,
            "bottom_zone": False,
            "stabilizing": False,
            "bluechip_liquidity_proxy": True,
            "value_anchor_proxy": True,
            "anti_black_five_proxy": True,
            "not_fresh_listing_proxy": True,
            "no_chase_zone": True,
            "speculation_heat": False,
            "breakdown_risk": False,
            "volatility_20d_pct": 2.0,
            "risk_flags": [],
        })

        self.assertFalse(payload["actionable"])
        self.assertIn("未处低位区", payload["hard_blockers"])
        self.assertIn("底部未企稳", payload["hard_blockers"])

    def test_li_daxiao_profile_blocks_speculative_chasing(self):
        payload = screen.with_strategy_profile("li_daxiao_bottom", {
            "score": 9.0,
            "distance_pct": 3.2,
            "bottom_zone": True,
            "stabilizing": True,
            "bluechip_liquidity_proxy": True,
            "value_anchor_proxy": False,
            "anti_black_five_proxy": False,
            "not_fresh_listing_proxy": False,
            "no_chase_zone": False,
            "speculation_heat": True,
            "breakdown_risk": False,
            "volatility_20d_pct": 2.0,
            "risk_flags": [],
        })

        self.assertFalse(payload["actionable"])
        self.assertIn("低估蓝筹代理不足", payload["hard_blockers"])
        self.assertIn("黑五类/题材热度代理偏高", payload["hard_blockers"])
        self.assertIn("次新代理风险", payload["hard_blockers"])
        self.assertIn("李大霄不追高", payload["hard_blockers"])
        self.assertIn("换手/涨幅过热", payload["hard_blockers"])


if __name__ == "__main__":
    unittest.main()
