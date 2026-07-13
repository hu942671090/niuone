#!/usr/bin/env python3
import contextlib
import importlib.util
import io
import json
import os
import sys
import unittest
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "app"
COMPAT = SRC / "compat"
ENTRYPOINTS = SRC / "entrypoints"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(COMPAT))
MODULE_PATH = COMPAT / "a_share_close_summary.py"


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


class FakePoolFrame:
    columns = ["代码"]

    def __init__(self, codes):
        self._codes = codes

    def __len__(self):
        return len(self._codes)

    def __getitem__(self, key):
        if key != "代码":
            raise KeyError(key)
        return self._codes


class AShareCloseSummaryTests(unittest.TestCase):
    def test_fetch_spot_uses_tencent_after_eastmoney_failures(self):
        mod = load_module()
        full_rows = sample_spot_rows()

        class FakeAk:
            stock_zh_a_spot_em = staticmethod(lambda: [])
            stock_zh_a_spot = staticmethod(lambda: self.fail("Sina should not be called after Tencent succeeds"))

        mod.ak = FakeAk()
        mod.quiet_call = lambda fn, *args, **kwargs: fn(*args, **kwargs)
        mod.fetch_eastmoney_spot_direct = lambda: ([], "东财分页直连返回空")
        mod.fetch_tencent_spot_snapshot = lambda _home: (full_rows, None)
        original_min_rows = os.environ.get("A_SHARE_SUMMARY_SPOT_MIN_ROWS")
        try:
            os.environ["A_SHARE_SUMMARY_SPOT_MIN_ROWS"] = "5"
            spot, warning = mod.fetch_spot()
        finally:
            if original_min_rows is None:
                os.environ.pop("A_SHARE_SUMMARY_SPOT_MIN_ROWS", None)
            else:
                os.environ["A_SHARE_SUMMARY_SPOT_MIN_ROWS"] = original_min_rows

        self.assertIs(spot, full_rows)
        self.assertIn("已切换腾讯全市场行情", warning)

    def test_direct_spot_retries_with_backup_endpoint(self):
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
            for i in range(150)
        ]
        calls = []

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
            parsed = urlparse(req.full_url)
            page = int(parse_qs(parsed.query)["pn"][0])
            calls.append((parsed.hostname, page))
            if parsed.hostname == "primary.invalid":
                raise mod.RemoteDisconnected("upstream reset")
            start = (page - 1) * 100
            return FakeResponse({"data": {"total": len(items), "diff": items[start:start + 100]}})

        original_urlopen = mod.urlopen
        original_sleep = mod.time.sleep
        env_names = (
            "A_SHARE_SUMMARY_DIRECT_ENDPOINTS",
            "A_SHARE_SUMMARY_DIRECT_RETRIES",
            "A_SHARE_SUMMARY_DIRECT_DEADLINE",
            "A_SHARE_SUMMARY_DIRECT_WORKERS",
        )
        original_env = {name: os.environ.get(name) for name in env_names}
        try:
            mod.urlopen = fake_urlopen
            mod.time.sleep = lambda _seconds: None
            os.environ["A_SHARE_SUMMARY_DIRECT_ENDPOINTS"] = (
                "https://primary.invalid/api/qt/clist/get,"
                "https://backup.invalid/api/qt/clist/get"
            )
            os.environ["A_SHARE_SUMMARY_DIRECT_RETRIES"] = "2"
            os.environ["A_SHARE_SUMMARY_DIRECT_DEADLINE"] = "5"
            os.environ["A_SHARE_SUMMARY_DIRECT_WORKERS"] = "2"

            rows, warning = mod.fetch_eastmoney_spot_direct()
        finally:
            mod.urlopen = original_urlopen
            mod.time.sleep = original_sleep
            for name, value in original_env.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

        self.assertEqual(len(rows), 150)
        self.assertIn("已切换备用域名", warning)
        self.assertEqual(calls.count(("primary.invalid", 1)), 1)
        self.assertIn(("backup.invalid", 1), calls)
        self.assertIn(("backup.invalid", 2), calls)

    def test_full_market_filter_keeps_bse_st_and_new_a_shares(self):
        mod = load_module()
        rows = mod.extract_eastmoney_spot_rows([
            {"f12": "830001", "f14": "北交测试", "f2": 10, "f3": 1, "f6": 1},
            {"f12": "600001", "f14": "ST测试", "f2": 10, "f3": -1, "f6": 1},
            {"f12": "301001", "f14": "N测试", "f2": 10, "f3": 30, "f6": 1},
            {"f12": "900901", "f14": "B股测试", "f2": 1, "f3": 1, "f6": 1},
        ])

        self.assertEqual({row["code"] for row in rows}, {"830001", "600001", "301001"})

    def test_spot_completeness_requires_bse_coverage(self):
        mod = load_module()
        rows = sample_spot_rows()
        env_names = ("A_SHARE_SUMMARY_SPOT_MIN_ROWS", "A_SHARE_SUMMARY_SPOT_MIN_BSE_ROWS")
        original_env = {name: os.environ.get(name) for name in env_names}
        try:
            os.environ["A_SHARE_SUMMARY_SPOT_MIN_ROWS"] = "5"
            os.environ["A_SHARE_SUMMARY_SPOT_MIN_BSE_ROWS"] = "1"
            issue = mod.spot_snapshot_issue(rows, None)
        finally:
            for name, value in original_env.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

        self.assertIn("北交所A股样本仅 0 只", issue)

    def test_fetch_spot_continues_to_sina_after_partial_direct_snapshot(self):
        mod = load_module()
        full_rows = sample_spot_rows()
        class FakeAk:
            stock_zh_a_spot_em = staticmethod(lambda: [])
            stock_zh_a_spot = staticmethod(lambda: full_rows)

        mod.ak = FakeAk()
        mod.quiet_call = lambda fn, *args, **kwargs: fn(*args, **kwargs)
        mod.fetch_eastmoney_spot_direct = lambda: (
            sample_spot_rows(),
            "东财直连只取到 6/5000 只，已按现有样本生成",
        )
        mod.fetch_tencent_spot_snapshot = lambda _home: ([], "腾讯备用行情不可用")
        original_min_rows = os.environ.get("A_SHARE_SUMMARY_SPOT_MIN_ROWS")
        try:
            os.environ["A_SHARE_SUMMARY_SPOT_MIN_ROWS"] = "5"
            spot, warning = mod.fetch_spot()
        finally:
            if original_min_rows is None:
                os.environ.pop("A_SHARE_SUMMARY_SPOT_MIN_ROWS", None)
            else:
                os.environ["A_SHARE_SUMMARY_SPOT_MIN_ROWS"] = original_min_rows

        self.assertIs(spot, full_rows)
        self.assertIn("已切换新浪现货", warning)

    def test_spot_completeness_rejects_silent_all_zero_snapshot(self):
        mod = load_module()
        rows = [
            {
                "code": f"60000{i}",
                "name": f"测试{i}",
                "pct": 0.0,
                "price": 0.0,
                "amount": 0.0,
                "vol_ratio": 0.0,
                "industry": "测试",
            }
            for i in range(5)
        ]
        original_min_rows = os.environ.get("A_SHARE_SUMMARY_SPOT_MIN_ROWS")
        try:
            os.environ["A_SHARE_SUMMARY_SPOT_MIN_ROWS"] = "5"
            issue = mod.spot_snapshot_issue(rows, None)
        finally:
            if original_min_rows is None:
                os.environ.pop("A_SHARE_SUMMARY_SPOT_MIN_ROWS", None)
            else:
                os.environ["A_SHARE_SUMMARY_SPOT_MIN_ROWS"] = original_min_rows

        self.assertIn("最新价有效覆盖率", issue)

    def test_spot_completeness_rejects_preclose_delayed_snapshot(self):
        mod = load_module()
        mod.MODE = "close"
        mod.NOW = datetime(2026, 7, 10, 15, 10, tzinfo=mod.CN_TZ)
        stale_timestamp = int(datetime(2026, 7, 10, 14, 45, tzinfo=mod.CN_TZ).timestamp())
        rows = [dict(row, quote_ts=stale_timestamp) for row in sample_spot_rows()]
        original_min_rows = os.environ.get("A_SHARE_SUMMARY_SPOT_MIN_ROWS")
        try:
            os.environ["A_SHARE_SUMMARY_SPOT_MIN_ROWS"] = "5"
            issue = mod.spot_snapshot_issue(rows, None)
        finally:
            if original_min_rows is None:
                os.environ.pop("A_SHARE_SUMMARY_SPOT_MIN_ROWS", None)
            else:
                os.environ["A_SHARE_SUMMARY_SPOT_MIN_ROWS"] = original_min_rows

        self.assertIn("收盘后时间戳覆盖率", issue)

    def test_build_report_adds_next_day_premarket_guidance(self):
        mod = load_module()
        mod.NOW = datetime(2026, 7, 3, 15, 30, tzinfo=mod.CN_TZ)
        mod.fetch_spot = lambda: (sample_spot_rows(), None)
        mod.fetch_industry_fund_flow = lambda: (FakeFrame([
            {"行业": "半导体", "涨跌幅": 2.2, "流入资金": "8亿", "流出资金": "4亿", "净额": "4亿", "领涨股": "测试科技", "领涨股-涨跌幅": 5.2},
            {"行业": "通信", "涨跌幅": 1.4, "流入资金": "5亿", "流出资金": "2亿", "净额": "3亿", "领涨股": "测试通信", "领涨股-涨跌幅": 3.1},
            {"行业": "银行", "涨跌幅": -1.0, "流入资金": "1亿", "流出资金": "4亿", "净额": "-3亿", "领涨股": "测试银行", "领涨股-涨跌幅": -1.2},
        ]), None)
        mod.fetch_limit_pools = lambda: (None, None, "封板池暂不可用")

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

    def test_build_report_uses_sealed_limit_pools_instead_of_pct_thresholds(self):
        mod = load_module()
        mod.NOW = datetime(2026, 7, 3, 15, 30, tzinfo=mod.CN_TZ)
        mod.fetch_spot = lambda: (sample_spot_rows(), None)
        mod.fetch_industry_fund_flow = lambda: (None, "行业资金流返回空")
        mod.fetch_limit_pools = lambda: (
            FakePoolFrame(["600001", "000001", "600001"]),
            FakePoolFrame(["600002"]),
            None,
        )

        report = mod.build_report()

        self.assertIn("全A样本 `6` 只", report)
        self.assertIn("封死涨停 `2` · 封死跌停 `1`", report)
        self.assertNotIn("封死涨停 `1` · 封死跌停 `0`", report)

    def test_build_report_empty_spot_keeps_premarket_plan_defensive(self):
        mod = load_module()
        mod.NOW = datetime(2026, 7, 2, 15, 30, tzinfo=mod.CN_TZ)
        mod.fetch_spot = lambda: ([], "现货主接口暂不可用")
        mod.fetch_industry_fund_flow = lambda: (None, "行业资金流返回空")
        mod.fetch_limit_pools = lambda: (None, None, "封板池暂不可用")

        report = mod.build_report()

        self.assertIn("现货行情未取到有效数据", report)
        self.assertIn("风险级别：数据缺失", report)
        self.assertIn("不生成新增仓计划", report)
        self.assertIn("默认不开新仓", report)
        self.assertNotIn("涨停 `0`", report)
        self.assertNotIn("成交额 `0元`", report)

    def test_build_report_marks_unavailable_limit_pools_without_estimating(self):
        mod = load_module()
        mod.NOW = datetime(2026, 7, 2, 15, 30, tzinfo=mod.CN_TZ)
        mod.fetch_spot = lambda: (sample_spot_rows(), None)
        mod.fetch_industry_fund_flow = lambda: (None, "行业资金流返回空")
        mod.fetch_limit_pools = lambda: (None, None, "封板池暂不可用")

        report = mod.build_report()

        self.assertIn("封死涨停 数据缺失 · 封死跌停 数据缺失", report)
        self.assertNotIn("封死涨停 `0`", report)

    def test_scheduled_report_rejects_missing_spot_before_optional_fetches(self):
        mod = load_module()
        mod.NOW = datetime(2026, 7, 2, 15, 30, tzinfo=mod.CN_TZ)
        mod.fetch_spot = lambda: ([], "现货主接口暂不可用")
        optional_calls = []
        mod.fetch_industry_fund_flow = lambda: optional_calls.append("fund")
        mod.fetch_limit_pools = lambda: optional_calls.append("limit")

        with self.assertRaises(mod.SpotSnapshotUnavailable):
            mod.build_report(require_complete_spot=True)

        self.assertEqual(optional_calls, [])

    def test_scheduled_report_rejects_partial_spot_snapshot(self):
        mod = load_module()
        mod.NOW = datetime(2026, 7, 2, 15, 30, tzinfo=mod.CN_TZ)
        mod.fetch_spot = lambda: (sample_spot_rows(), None)
        original_min_rows = os.environ.get("A_SHARE_SUMMARY_SPOT_MIN_ROWS")
        try:
            os.environ["A_SHARE_SUMMARY_SPOT_MIN_ROWS"] = "1000"
            with self.assertRaisesRegex(mod.SpotSnapshotUnavailable, "完整性下限"):
                mod.build_report(require_complete_spot=True)
        finally:
            if original_min_rows is None:
                os.environ.pop("A_SHARE_SUMMARY_SPOT_MIN_ROWS", None)
            else:
                os.environ["A_SHARE_SUMMARY_SPOT_MIN_ROWS"] = original_min_rows

    def test_main_exits_nonzero_so_scheduler_retries_missing_spot(self):
        mod = load_module()
        strict_values = []

        def missing_report(*, require_complete_spot=False):
            strict_values.append(require_complete_spot)
            raise mod.SpotSnapshotUnavailable("现货快照为空")

        mod.build_report = missing_report
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as raised:
            mod.main()

        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(strict_values, [True])
        self.assertIn("等待调度器重试", output.getvalue())


if __name__ == "__main__":
    unittest.main()
