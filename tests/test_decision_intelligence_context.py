#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "app"
COMPAT = SRC / "compat"
ENTRYPOINTS = SRC / "entrypoints"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(COMPAT))

import niuniu_practice_trader as trader  # noqa: E402


class DecisionIntelligenceContextTests(unittest.TestCase):
    def setUp(self):
        self._fetch = trader.fetch_global_decision_sources
        self._enabled = trader.DECISION_INTELLIGENCE_ENABLED

    def tearDown(self):
        trader.fetch_global_decision_sources = self._fetch
        trader.DECISION_INTELLIGENCE_ENABLED = self._enabled

    def test_builds_prompt_with_global_market_channels(self):
        trader.DECISION_INTELLIGENCE_ENABLED = True

        def fake_sources(force=False):
            return {
                "enabled": True,
                "generated_at": "2026-07-02 10:00:00",
                "sources": {
                    "indices": {
                        "items": [
                            {"key": "sh", "name": "上证指数", "market_type": "a_index", "price": 3000, "change_pct": -1.2},
                            {"key": "cyb", "name": "创业板指", "market_type": "a_index", "price": 2000, "change_pct": -0.8},
                            {"key": "a50_fut", "name": "富时中国A50期货", "market_type": "a_futures", "price": 12000, "change_pct": -1.1},
                            {"key": "nas_fut", "name": "纳斯达克期货", "market_type": "us_futures", "price": 18000, "change_pct": 0.4},
                        ],
                    },
                    "sectors": {
                        "gain_top": [{"name": "半导体", "pct": 2.3}],
                        "loss_top": [{"name": "房地产", "pct": -2.1}],
                    },
                    "money_flow": {
                        "inflow": [{"name": "半导体", "pct": 2.3, "net_flow_yi": 18.5}],
                        "outflow": [{"name": "银行", "pct": -1.4, "net_flow_yi": -28.0}],
                    },
                    "hot_stocks": {
                        "amount_top": [{"code": "600001", "name": "测试科技", "pct": 4.2, "amount_yi": 21.0}],
                        "turnover_top": [{"code": "600001", "name": "测试科技", "pct": 4.2, "turnover": 12.0}],
                        "gain_top": [{"code": "600001", "name": "测试科技", "pct": 4.2}],
                    },
                    "market_flow": {"net_flow_yi": None},
                },
            }

        trader.fetch_global_decision_sources = fake_sources
        portfolio = {
            "total_equity": 1000000,
            "cash": 400000,
            "market_value": 600000,
            "positions": [
                {"code": "000001", "name": "平安银行", "market_value": 120000, "pnl_pct": -1.5, "today_pnl_pct": -0.8, "available_qty": 1000}
            ],
        }
        candidates = [{"code": "600001", "name": "测试科技", "industry": "半导体", "sector": "半导体"}]
        market_ctx = {
            "enabled": True,
            "tone_label": "谨慎",
            "phase": "morning",
            "max_open_positions": 3,
            "max_new_buys_per_decision": 1,
            "max_total_position_pct": 50,
            "min_cash_reserve_pct": 40,
            "buy_budget_multiplier": 0.6,
            "allow_new_buys": True,
            "overnight_us": {
                "available": True,
                "tone_label": "中性",
                "summary": "美股三大指数分化",
                "sector_mappings": ["半导体(SMH) +1.20%；A股：半导体、芯片设备；正映射"],
            },
        }

        ctx = trader.build_decision_intelligence_context(
            portfolio,
            candidates,
            market_ctx,
            "【消息面预检（实时搜索）】\n- 600001 测试科技：订单增长（利好）",
        )
        prompt = trader.format_decision_intelligence_context_for_prompt(ctx)

        self.assertTrue(ctx["news_precheck"]["available"])
        self.assertIn("上证指数-1.20%", prompt)
        self.assertIn("富时中国A50期货-1.10%", prompt)
        self.assertIn("隔夜美股：中性", prompt)
        self.assertIn("隔夜美股映射", prompt)
        self.assertIn("芯片设备", prompt)
        self.assertIn("行业资金：流入 半导体+2.30%/18.5亿", prompt)
        self.assertIn("候选共振/背离", prompt)
        self.assertIn("强势板块", prompt)
        self.assertIn("资金流入", prompt)
        self.assertIn("热门榜", prompt)
        self.assertIn("决策要求", prompt)

    def test_disabled_context_formats_as_closed(self):
        self.assertEqual(
            trader.format_decision_intelligence_context_for_prompt({"enabled": False}),
            "【全局决策情报包】已关闭。",
        )


if __name__ == "__main__":
    unittest.main()
