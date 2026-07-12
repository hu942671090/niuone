#!/usr/bin/env python3
import importlib.util
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "app"
COMPAT = SRC / "compat"
ENTRYPOINTS = SRC / "entrypoints"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(COMPAT))
MODULE_PATH = COMPAT / "indices_dashboard_api.py"


def load_module():
    spec = importlib.util.spec_from_file_location("indices_dashboard_api_under_test", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class IndicesDashboardApiTests(unittest.TestCase):
    def test_fetch_indices_data_returns_compact_payload_by_default(self):
        mod = load_module()
        mod.MINUTE_LINE_MAX_POINTS = 10
        mod.INCLUDE_LEGACY_GROUPS = False
        mod._CACHE = {"ts": 0, "data": None}
        mod._qt_query = lambda codes: ""
        mod._sina_query = lambda codes: ""
        mod._sina_us_index_query = lambda: ""
        mod._fetch_minute_quote = lambda code: {}

        def minute_line(code):
            return [{"time": f"10:{i % 60:02d}", "minute": i, "price": 1000 + i} for i in range(120)]

        def global_line(symbol):
            return [{"time": f"{i // 60:02d}:{i % 60:02d}", "price": 2000 + i} for i in range(240)]

        mod._fetch_minute_line = minute_line
        mod._fetch_eastmoney_us_minute_line = lambda code: []
        mod._fetch_yahoo_minute_line = lambda symbol: minute_line(symbol)
        mod._fetch_sina_us_minute_line = lambda symbol: []
        mod._fetch_sina_global_minute_line = global_line
        mod._fetch_kline = lambda code: [float(i) for i in range(80)]

        payload = mod.fetch_indices_data()

        self.assertEqual(set(payload.keys()), {"items", "generated_at"})
        self.assertEqual(len(payload["items"]), len(mod.INDEX_DEFS) + len(mod.SINA_DEFS))
        for item in payload["items"]:
            self.assertLessEqual(len(item["minute_line"]), 10)
            if item["minute_line"]:
                self.assertEqual(item["sparkline"], [])
                self.assertEqual(item["minute_line"][0]["price"], 1000 if item["key"] in {"sh", "sz", "cyb", "kc50", "dow", "nas", "spx"} else 2000)
                self.assertGreater(item["minute_line"][-1]["price"], item["minute_line"][0]["price"])

    def test_fetch_indices_data_can_emit_legacy_groups_when_enabled(self):
        mod = load_module()
        mod.MINUTE_LINE_MAX_POINTS = 5
        mod.INCLUDE_LEGACY_GROUPS = True
        mod._CACHE = {"ts": 0, "data": None}
        mod._qt_query = lambda codes: ""
        mod._sina_query = lambda codes: ""
        mod._sina_us_index_query = lambda: ""
        mod._fetch_minute_quote = lambda code: {}
        mod._fetch_minute_line = lambda code: []
        mod._fetch_eastmoney_us_minute_line = lambda code: []
        mod._fetch_yahoo_minute_line = lambda symbol: []
        mod._fetch_sina_us_minute_line = lambda symbol: []
        mod._fetch_sina_global_minute_line = lambda symbol: []
        mod._fetch_kline = lambda code: [float(i) for i in range(20)]

        payload = mod.fetch_indices_data()

        self.assertIn("groups", payload)
        self.assertIn("market_groups", payload)
        self.assertEqual(len(payload["groups"]["domestic"]), 4)
        self.assertLess(time.time() - time.mktime(time.strptime(payload["generated_at"], "%Y-%m-%d %H:%M:%S")), 10)

    def test_us_index_uses_tencent_minute_quote_and_yahoo_line(self):
        mod = load_module()
        mod.MINUTE_LINE_MAX_POINTS = 10
        mod.INCLUDE_LEGACY_GROUPS = False
        mod._CACHE = {"ts": 0, "data": None}
        mod._qt_query = lambda codes: ""
        mod._sina_query = lambda codes: ""
        mod._sina_us_index_query = lambda: ""
        mod._fetch_minute_quote = lambda code: {
            "price": 52260.22,
            "prev_close": 51876.11,
            "change": 384.11,
            "change_pct": 0.74,
            "time": "2026-06-29 14:07:00",
        } if code == "usDJI" else {}
        mod._fetch_minute_line = lambda code: [{"time": "14:07", "price": 52260.22}] if code == "usDJI" else []
        mod._fetch_eastmoney_us_minute_line = lambda code: []
        mod._fetch_yahoo_minute_line = lambda symbol: [
            {"time": "09:30", "price": 51995.14},
            {"time": "09:31", "price": 52010.0},
            {"time": "14:07", "price": 52260.22},
        ] if symbol == "^DJI" else []
        mod._fetch_sina_us_minute_line = lambda symbol: []
        mod._fetch_sina_global_minute_line = lambda symbol: []
        mod._fetch_kline = lambda code: []

        payload = mod.fetch_indices_data()
        dow = next(item for item in payload["items"] if item["key"] == "dow")

        self.assertEqual(dow["price"], 52260.22)
        self.assertEqual(dow["prev_close"], 51876.11)
        self.assertEqual(len(dow["minute_line"]), 3)
        self.assertEqual(dow["sparkline"], [])

    def test_us_index_can_fallback_to_sina_minute_line(self):
        mod = load_module()
        mod.MINUTE_LINE_MAX_POINTS = 10
        mod.INCLUDE_LEGACY_GROUPS = False
        mod._CACHE = {"ts": 0, "data": None}
        mod._qt_query = lambda codes: ""
        mod._sina_query = lambda codes: ""
        mod._sina_us_index_query = lambda: ""
        mod._fetch_minute_quote = lambda code: {}
        mod._fetch_minute_line = lambda code: []
        mod._fetch_eastmoney_us_minute_line = lambda code: []
        mod._fetch_yahoo_minute_line = lambda symbol: []
        mod._fetch_sina_us_minute_line = lambda symbol: [
            {"time": "09:30", "price": 25290.0},
            {"time": "09:31", "price": 25300.0},
        ] if symbol == ".IXIC" else []
        mod._fetch_sina_global_minute_line = lambda symbol: []
        mod._fetch_kline = lambda code: []

        payload = mod.fetch_indices_data()
        nas = next(item for item in payload["items"] if item["key"] == "nas")

        self.assertEqual(len(nas["minute_line"]), 2)
        self.assertEqual(nas["minute_line"][0]["price"], 25290.0)

    def test_us_index_prefers_eastmoney_minute_line(self):
        mod = load_module()
        mod.MINUTE_LINE_MAX_POINTS = 10
        mod.INCLUDE_LEGACY_GROUPS = False
        mod._CACHE = {"ts": 0, "data": None}
        mod._qt_query = lambda codes: ""
        mod._sina_query = lambda codes: ""
        mod._sina_us_index_query = lambda: ""
        mod._fetch_minute_quote = lambda code: {}
        mod._fetch_minute_line = lambda code: [{"time": "14:07", "price": 7434.0}] if code == "usINX" else []
        mod._fetch_eastmoney_us_minute_line = lambda code: [
            {"time": "09:30", "price": 7391.88},
            {"time": "09:31", "price": 7398.0},
            {"time": "14:07", "price": 7434.0},
        ] if code == "usINX" else []
        mod._fetch_yahoo_minute_line = lambda symbol: []
        mod._fetch_sina_us_minute_line = lambda symbol: []
        mod._fetch_sina_global_minute_line = lambda symbol: []
        mod._fetch_kline = lambda code: []

        payload = mod.fetch_indices_data()
        spx = next(item for item in payload["items"] if item["key"] == "spx")

        self.assertEqual(len(spx["minute_line"]), 3)
        self.assertEqual(spx["minute_line"][0]["time"], "09:30")


if __name__ == "__main__":
    unittest.main()
