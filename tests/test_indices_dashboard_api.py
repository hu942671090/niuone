#!/usr/bin/env python3
import importlib.util
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "app"
sys.path.insert(0, str(SRC))
MODULE_PATH = SRC / "indices_dashboard_api.py"


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

        def minute_line(code):
            return [{"time": f"10:{i % 60:02d}", "minute": i, "price": 1000 + i} for i in range(120)]

        def global_line(symbol):
            return [{"time": f"{i // 60:02d}:{i % 60:02d}", "price": 2000 + i} for i in range(240)]

        mod._fetch_minute_line = minute_line
        mod._fetch_yahoo_minute_line = lambda symbol: minute_line(symbol)
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
        mod._fetch_minute_line = lambda code: []
        mod._fetch_yahoo_minute_line = lambda symbol: []
        mod._fetch_sina_global_minute_line = lambda symbol: []
        mod._fetch_kline = lambda code: [float(i) for i in range(20)]

        payload = mod.fetch_indices_data()

        self.assertIn("groups", payload)
        self.assertIn("market_groups", payload)
        self.assertEqual(len(payload["groups"]["domestic"]), 4)
        self.assertLess(time.time() - time.mktime(time.strptime(payload["generated_at"], "%Y-%m-%d %H:%M:%S")), 10)


if __name__ == "__main__":
    unittest.main()
