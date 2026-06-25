#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'app'


class UsRatingReportTests(unittest.TestCase):
    def test_paths_are_dashboard_home_scoped_and_prompt_has_no_telegram(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env['DASHBOARD_HOME'] = tmp
            code = f"""
import importlib.util, json, sys
sys.path.insert(0, {str(SRC)!r})
spec = importlib.util.spec_from_file_location('us_rating_report_under_test', {str(SRC / 'us_rating_report.py')!r})
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
prompt = m.build_user_prompt()
print(json.dumps({{
  'dashboard_home': str(m.DASHBOARD_HOME),
  'config_path': str(m.CONFIG_PATH),
  'output_dir': str(m.OUTPUT_DIR),
  'mentions_telegram': 'telegram' in prompt.lower(),
}}, ensure_ascii=False))
"""
            out = subprocess.check_output([sys.executable, '-c', code], env=env, text=True)
            data = json.loads(out)
            self.assertEqual(data['dashboard_home'], tmp)
            self.assertEqual(data['config_path'], str(Path(tmp) / 'config.yaml'))
            self.assertEqual(data['output_dir'], str(Path(tmp) / 'cron' / 'output' / 'fd0b807138f4'))
            self.assertFalse(data['mentions_telegram'])

    def test_archive_and_db_write_create_dashboard_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env['DASHBOARD_HOME'] = tmp
            sample = """**牛牛大王，美股机构买入评级日报（2026年06月23日）**

- TEST / Test Corp
  机构/分析师：Example Bank / Analyst
  评级动作：新覆盖 Buy
  目标价：100美元
  核心理由/催化剂：测试催化剂
  风险点：测试风险
  适合关注类型：中线趋势
"""
            code = f"""
import importlib.util, json, sys
from datetime import datetime, timezone
sys.path.insert(0, {str(SRC)!r})
spec = importlib.util.spec_from_file_location('us_rating_report_under_test', {str(SRC / 'us_rating_report.py')!r})
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
now = datetime(2026, 6, 23, 3, 0, 0, tzinfo=timezone.utc)
path = m.archive_report({sample!r}, now=now)
count = m.write_report_to_db({sample!r}, path, now=now)
import push_history
data = push_history.query_messages(category='us_ratings', limit=5)
record = data['records'][0]
print(json.dumps({{
  'archive_path': str(path),
  'db_count': count,
  'record_category': record.get('category'),
  'record_kind': record.get('kind'),
  'record_source_type': record.get('source_type'),
  'record_contains_sample': 'TEST / Test Corp' in record.get('content', ''),
}}, ensure_ascii=False))
"""
            out = subprocess.check_output([sys.executable, '-c', textwrap.dedent(code)], env=env, text=True)
            data = json.loads(out)
            self.assertEqual(data['archive_path'], str(Path(tmp) / 'cron' / 'output' / 'fd0b807138f4' / '2026-06-23_11-00-00.md'))
            self.assertEqual(data['db_count'], 1)
            self.assertEqual(data['record_category'], 'us_ratings')
            self.assertEqual(data['record_kind'], 'cron_output')
            self.assertEqual(data['record_source_type'], 'us_ratings')
            self.assertTrue(data['record_contains_sample'])


if __name__ == '__main__':
    unittest.main()
