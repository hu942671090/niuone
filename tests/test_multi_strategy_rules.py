#!/usr/bin/env python3
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


if __name__ == "__main__":
    unittest.main()
