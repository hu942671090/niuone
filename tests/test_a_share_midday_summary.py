#!/usr/bin/env python3
import importlib.util
import json
import sys
import unittest
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "app"
sys.path.insert(0, str(SRC))
MODULE_PATH = SRC / "a_share_midday_summary.py"


def load_module():
    spec = importlib.util.spec_from_file_location("a_share_midday_summary_under_test", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.MODE = "midday"
    mod.TITLE = "午盘总结"
    return mod


def sample_spot_rows():
    return [
        {"code": "600001", "name": "测试科技", "pct": 5.2, "price": 12.3, "amount": 220000000, "vol_ratio": 1.8, "industry": "半导体"},
        {"code": "600002", "name": "测试通信", "pct": 3.1, "price": 8.8, "amount": 180000000, "vol_ratio": 1.5, "industry": "通信"},
        {"code": "000001", "name": "测试银行", "pct": -1.2, "price": 9.7, "amount": 160000000, "vol_ratio": 0.9, "industry": "银行"},
        {"code": "300001", "name": "测试制造", "pct": 10.1, "price": 18.6, "amount": 130000000, "vol_ratio": 2.0, "industry": "机器人"},
        {"code": "600003", "name": "测试消费", "pct": 0.2, "price": 6.1, "amount": 90000000, "vol_ratio": 0.8, "industry": "食品消费"},
    ]


class FakeFrame:
    columns = ["行业", "涨跌幅", "流入资金", "流出资金", "净额"]

    def __init__(self, rows):
        self._rows = rows

    def __len__(self):
        return len(self._rows)

    def iterrows(self):
        for idx, row in enumerate(self._rows):
            yield idx, row


class AShareMiddaySummaryTests(unittest.TestCase):
    def test_fetch_eastmoney_spot_direct_pages_full_market(self):
        mod = load_module()
        items = [
            {
                "f12": f"60{i:04d}",
                "f14": f"测试{i:03d}",
                "f2": 10 + i / 100,
                "f3": 1.5,
                "f6": 1000000 + i,
                "f10": 1.2,
                "f100": "半导体",
            }
            for i in range(250)
        ]
        seen_pages = []

        class FakeResponse:
            def __init__(self, payload):
                self.payload = payload

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps(self.payload).encode("utf-8")

        def fake_urlopen(req, timeout=0):
            page = int(parse_qs(urlparse(req.full_url).query)["pn"][0])
            seen_pages.append(page)
            start = (page - 1) * 100
            payload = {"data": {"total": len(items), "diff": items[start:start + 100]}}
            return FakeResponse(payload)

        original_urlopen = mod.urlopen
        original_deadline = mod.os.environ.get("A_SHARE_SUMMARY_DIRECT_DEADLINE")
        try:
            mod.urlopen = fake_urlopen
            mod.os.environ["A_SHARE_SUMMARY_DIRECT_DEADLINE"] = "5"
            rows, warning = mod.fetch_eastmoney_spot_direct()
        finally:
            mod.urlopen = original_urlopen
            if original_deadline is None:
                mod.os.environ.pop("A_SHARE_SUMMARY_DIRECT_DEADLINE", None)
            else:
                mod.os.environ["A_SHARE_SUMMARY_DIRECT_DEADLINE"] = original_deadline

        self.assertEqual(len(rows), 250)
        self.assertIsNone(warning)
        self.assertEqual(set(seen_pages), {1, 2, 3})
        self.assertEqual(rows[0]["industry"], "半导体")

    def test_build_report_empty_spot_does_not_render_zero_market_stats(self):
        mod = load_module()
        mod.NOW = datetime(2026, 7, 2, 11, 40, tzinfo=mod.CN_TZ)
        mod.fetch_spot = lambda: ([], "现货主接口暂不可用")
        mod.fetch_industry_fund_flow = lambda: (None, "行业资金流返回空")
        mod.fetch_zt_pool = lambda: (None, None)

        report = mod.build_report()

        self.assertIn("现货行情未取到有效数据", report)
        self.assertIn("行业资金流暂不可用", report)
        self.assertIn("风险级别：数据缺失", report)
        self.assertNotIn("涨停 `0`", report)
        self.assertNotIn("成交额 `0元`", report)

    def test_build_report_ignores_all_zero_fund_flow(self):
        mod = load_module()
        mod.NOW = datetime(2026, 7, 2, 11, 40, tzinfo=mod.CN_TZ)
        mod.fetch_spot = lambda: (sample_spot_rows(), None)
        mod.fetch_industry_fund_flow = lambda: (FakeFrame([
            {"行业": "半导体", "涨跌幅": 1.2, "流入资金": 0, "流出资金": 0, "净额": 0},
        ]), None)
        mod.fetch_zt_pool = lambda: (None, None)

        report = mod.build_report()

        self.assertIn("行业资金流暂不可用", report)
        self.assertIn("行业资金流净额全为0", report)
        self.assertNotIn("流入：半导体 0元", report)

    def test_build_report_adds_midday_watchlist(self):
        mod = load_module()
        mod.NOW = datetime(2026, 7, 2, 11, 40, tzinfo=mod.CN_TZ)
        mod.fetch_spot = lambda: (sample_spot_rows(), None)
        mod.fetch_industry_fund_flow = lambda: (None, "行业资金流返回空")
        mod.fetch_zt_pool = lambda: (None, None)

        report = mod.build_report()

        self.assertIn("午后关注", report)
        self.assertIn("主线延续", report)
        self.assertIn("承接观察", report)
        self.assertIn("测试科技", report)


if __name__ == "__main__":
    unittest.main()
