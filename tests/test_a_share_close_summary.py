#!/usr/bin/env python3
import importlib.util
import sys
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "app"
sys.path.insert(0, str(SRC))
MODULE_PATH = SRC / "a_share_close_summary.py"


def load_module():
    spec = importlib.util.spec_from_file_location("a_share_close_summary_under_test", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.MODE = "close"
    mod.TITLE = "盘后总结"
    return mod


def sample_spot_rows():
    return [
        {"code": "600001", "name": "测试科技", "pct": 5.2, "price": 12.3, "amount": 420000000, "vol_ratio": 1.8, "industry": "半导体"},
        {"code": "600002", "name": "测试通信", "pct": 3.1, "price": 8.8, "amount": 380000000, "vol_ratio": 1.5, "industry": "通信"},
        {"code": "000001", "name": "测试银行", "pct": -1.2, "price": 9.7, "amount": 260000000, "vol_ratio": 0.9, "industry": "银行"},
        {"code": "300001", "name": "测试制造", "pct": 10.1, "price": 18.6, "amount": 230000000, "vol_ratio": 2.0, "industry": "机器人"},
        {"code": "600003", "name": "测试消费", "pct": 0.2, "price": 6.1, "amount": 190000000, "vol_ratio": 0.8, "industry": "食品消费"},
        {"code": "600004", "name": "测试芯片", "pct": 2.7, "price": 16.1, "amount": 170000000, "vol_ratio": 1.2, "industry": "半导体"},
    ]


class FakeFrame:
    columns = ["行业", "涨跌幅", "流入资金", "流出资金", "净额", "领涨股", "领涨股-涨跌幅"]

    def __init__(self, rows):
        self._rows = rows

    def __len__(self):
        return len(self._rows)

    def iterrows(self):
        for idx, row in enumerate(self._rows):
            yield idx, row


class AShareCloseSummaryTests(unittest.TestCase):
    def test_build_report_adds_next_day_premarket_guidance(self):
        mod = load_module()
        mod.NOW = datetime(2026, 7, 3, 15, 30, tzinfo=mod.CN_TZ)
        mod.fetch_spot = lambda: (sample_spot_rows(), None)
        mod.fetch_industry_fund_flow = lambda: (FakeFrame([
            {"行业": "半导体", "涨跌幅": 2.2, "流入资金": "8亿", "流出资金": "4亿", "净额": "4亿", "领涨股": "测试科技", "领涨股-涨跌幅": 5.2},
            {"行业": "通信", "涨跌幅": 1.4, "流入资金": "5亿", "流出资金": "2亿", "净额": "3亿", "领涨股": "测试通信", "领涨股-涨跌幅": 3.1},
            {"行业": "银行", "涨跌幅": -1.0, "流入资金": "1亿", "流出资金": "4亿", "净额": "-3亿", "领涨股": "测试银行", "领涨股-涨跌幅": -1.2},
        ]), None)
        mod.fetch_zt_pool = lambda: (None, None)

        report = mod.build_report()

        self.assertIn("次日买卖计划", report)
        self.assertIn("次日盘前指引", report)
        self.assertIn("2026-07-06", report)
        self.assertIn("竞价确认", report)
        self.assertIn("开仓条件", report)
        self.assertIn("次日关注池", report)
        self.assertIn("盘前执行规则", report)
        self.assertIn("测试科技", report)
        self.assertNotIn("今日买卖指引", report)

    def test_build_report_empty_spot_keeps_premarket_plan_defensive(self):
        mod = load_module()
        mod.NOW = datetime(2026, 7, 2, 15, 30, tzinfo=mod.CN_TZ)
        mod.fetch_spot = lambda: ([], "现货主接口暂不可用")
        mod.fetch_industry_fund_flow = lambda: (None, "行业资金流返回空")
        mod.fetch_zt_pool = lambda: (None, None)

        report = mod.build_report()

        self.assertIn("现货行情未取到有效数据", report)
        self.assertIn("风险级别：数据缺失", report)
        self.assertIn("不生成新增仓计划", report)
        self.assertIn("默认不开新仓", report)
        self.assertNotIn("涨停 `0`", report)
        self.assertNotIn("成交额 `0元`", report)


if __name__ == "__main__":
    unittest.main()
