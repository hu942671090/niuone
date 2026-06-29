#!/usr/bin/env python3
import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "app"
sys.path.insert(0, str(SRC))

import a_share_calendar as cal  # noqa: E402


class AShareCalendarTests(unittest.TestCase):
    def test_cached_calendar_overrides_weekday_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "calendar.json"
            cache.write_text(json.dumps({
                "source": "test",
                "updated_at": "2026-01-01 00:00:00",
                "dates": ["2026-02-13", "2026-02-17"],
            }))

            status = cal.trading_day_status(
                datetime(2026, 2, 16, 10, 0),
                cache_file=cache,
                allow_refresh=False,
            )

        self.assertFalse(status["is_trading_day"])
        self.assertEqual(status["previous_trading_day"], "2026-02-13")
        self.assertEqual(status["next_trading_day"], "2026-02-17")
        self.assertTrue(status["calendar_cached"])

    def test_missing_calendar_falls_back_to_weekday(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "missing.json"
            weekday = cal.trading_day_status(
                datetime(2026, 2, 16, 10, 0),
                cache_file=cache,
                allow_refresh=False,
            )
            weekend = cal.trading_day_status(
                datetime(2026, 2, 15, 10, 0),
                cache_file=cache,
                allow_refresh=False,
            )

        self.assertTrue(weekday["is_trading_day"])
        self.assertFalse(weekend["is_trading_day"])
        self.assertFalse(weekday["calendar_cached"])


if __name__ == "__main__":
    unittest.main()
