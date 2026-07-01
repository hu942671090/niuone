#!/usr/bin/env python3
import importlib.util
import sys
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "app"
sys.path.insert(0, str(SRC))
MODULE_PATH = SRC / "a_share_auction_summary.py"


def load_module():
    spec = importlib.util.spec_from_file_location("a_share_auction_summary_under_test", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class AShareAuctionSummaryTests(unittest.TestCase):
    def test_extract_auction_snapshot_uses_open_price_and_turnover(self):
        mod = load_module()

        rows = mod.extract_auction_snapshot_rows([
            {"f12": "600001", "f14": "测试科技", "f17": 11.0, "f18": 10.0, "f2": 11.2, "f5": 12345, "f6": 67890000, "f100": "半导体"},
            {"f12": "830000", "f14": "北交测试", "f17": 9.0, "f18": 10.0, "f5": 1, "f6": 1, "f100": "其他"},
            {"f12": "300001", "f14": "N新股", "f17": 12.0, "f18": 10.0, "f5": 1, "f6": 1, "f100": "其他"},
        ])

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["code"], "600001")
        self.assertAlmostEqual(rows[0]["auction_pct"], 10.0)
        self.assertEqual(rows[0]["amount"], 67890000)
        self.assertEqual(rows[0]["volume_lot"], 12345)
        self.assertEqual(rows[0]["industry"], "半导体")

    def test_build_report_uses_auction_sections_not_fund_flow(self):
        mod = load_module()
        mod.NOW = datetime(2026, 7, 2, 9, 25, tzinfo=mod.CN_TZ)
        mod.fetch_auction_snapshot = lambda: ([
            {"code": "600001", "name": "测试科技", "industry": "半导体", "open_price": 11.0, "latest_price": 11.0, "prev_close": 10.0, "auction_pct": 10.0, "change_pct": 10.0, "amount": 120000000, "volume_lot": 120000, "vol_ratio": 2.1},
            {"code": "000001", "name": "测试银行", "industry": "银行", "open_price": 9.8, "latest_price": 9.8, "prev_close": 10.0, "auction_pct": -2.0, "change_pct": -2.0, "amount": 50000000, "volume_lot": 50000, "vol_ratio": 1.1},
        ], None)
        mod.fetch_zt_pool = lambda: (mod.pd.DataFrame([
            {"代码": "600001", "名称": "测试科技", "涨跌幅": 10.0, "最新价": 11.0, "封单资金": 30000000},
        ]), None)
        mod.fetch_dt_pool = lambda: (mod.pd.DataFrame([
            {"代码": "000001", "名称": "测试银行", "涨跌幅": -10.0, "最新价": 9.0, "封单资金": 10000000},
        ]), None)

        report = mod.build_report()

        self.assertIn("开盘价强弱", report)
        self.assertIn("竞价强势板块", report)
        self.assertIn("竞价成交活跃", report)
        self.assertIn("跌停风险Top5", report)
        self.assertIn("竞价额", report)
        self.assertNotIn("资金流向", report)
        self.assertNotIn("资金净流入", report)


if __name__ == "__main__":
    unittest.main()
