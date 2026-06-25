#!/usr/bin/env python3
import importlib.util
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "app"
sys.path.insert(0, str(SRC))


spec = importlib.util.spec_from_file_location(
    "dashboard_under_test",
    str(SRC / "niuone_dashboard.py"),
)
dashboard = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(dashboard)


class CronOutputFilterTests(unittest.TestCase):
    def test_script_failed_output_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fd0b807138f4" / "2026-06-23_11-02-23.md"
            path.parent.mkdir(parents=True)
            path.write_text(textwrap.dedent("""
                # Cron Job: 每日美股机构买入评级汇报

                **Job ID:** fd0b807138f4
                **Run Time:** 2026-06-23 11:02:23
                **Mode:** no_agent (script)
                **Status:** script failed

                Script timed out after 120s: /home/example/.hermes/scripts/us_rating_report.py
            """).strip(), encoding="utf-8")

            self.assertEqual(dashboard.parse_cron_output_records(path), [])

    def test_normal_us_rating_output_is_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fd0b807138f4" / "2026-06-23_12-26-40.md"
            path.parent.mkdir(parents=True)
            path.write_text(textwrap.dedent("""
                # Cron Job: 每日美股机构买入评级汇报

                **Job ID:** fd0b807138f4
                **Run Time:** 2026-06-23 12:26:40
                **Mode:** dashboard archive only
                **Status:** archived

                ---
                标题：美股机构买入评级日报

                1. **AMD / Advanced Micro Devices**
                - **评级动作：** Buy
                - **目标价：** $200
            """).strip(), encoding="utf-8")

            records = dashboard.parse_cron_output_records(path)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["category"], "us_ratings")
            self.assertIn("AMD", records[0]["content"])


if __name__ == "__main__":
    unittest.main()
