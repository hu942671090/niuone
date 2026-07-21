#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(ROOT / "app" / "compat"))

from dashboard.apis import sectors_service  # noqa: E402


class SectorsServiceTests(unittest.TestCase):
    def test_compute_keeps_industry_and_concept_rankings_separate(self):
        rows = [
            {"name": "国家大基金持股", "pct": 10.78, "source": "概念"},
            {"name": "半导体", "pct": 9.83, "source": "行业"},
            {"name": "存储芯片", "pct": 8.98, "source": "概念"},
            {"name": "电子化学品", "pct": 8.92, "source": "行业"},
            {"name": "油气开采及服务", "pct": -3.84, "source": "行业"},
        ]

        with patch.object(sectors_service, "_ak_rows", return_value=rows):
            payload = sectors_service._compute()

        self.assertEqual(payload["gain_top"][0]["name"], "国家大基金持股")
        self.assertEqual(payload["industry_gain_top"][0]["name"], "半导体")
        self.assertEqual(payload["concept_gain_top"][0]["name"], "国家大基金持股")
        self.assertEqual(payload["industry_loss_top"][0]["name"], "油气开采及服务")


if __name__ == "__main__":
    unittest.main()
