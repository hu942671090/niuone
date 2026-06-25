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


class XWatchlistMonitorTests(unittest.TestCase):
    def test_paths_are_dashboard_home_scoped_and_telegram_helpers_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env['DASHBOARD_HOME'] = tmp
            code = f"""
import importlib.util, json, sys
sys.path.insert(0, {str(SRC)!r})
spec = importlib.util.spec_from_file_location('x_watchlist_monitor_under_test', {str(SRC / 'x_watchlist_monitor.py')!r})
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
print(json.dumps({{
  'dashboard_home': str(m.DASHBOARD_HOME),
  'state_path': str(m.STATE_PATH),
  'config_path': str(m.CONFIG_PATH),
  'archive_dir': str(m.X_ARCHIVE_DIR),
  'has_telegram_delivery': hasattr(m, 'deliver_cards_directly') or hasattr(m, 'telegram_api_call'),
}}, ensure_ascii=False))
"""
            out = subprocess.check_output([sys.executable, '-c', code], env=env, text=True)
            data = json.loads(out)
            self.assertEqual(data['dashboard_home'], tmp)
            self.assertEqual(data['state_path'], str(Path(tmp) / 'cron' / 'state' / 'x_watchlist_latest.json'))
            self.assertEqual(data['config_path'], str(Path(tmp) / 'config.yaml'))
            self.assertEqual(data['archive_dir'], str(Path(tmp) / 'cron' / 'output' / 'x_watchlist_direct'))
            self.assertFalse(data['has_telegram_delivery'])

    def test_accounts_can_be_overridden_from_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env['DASHBOARD_HOME'] = tmp
            env['X_WATCHLIST_ACCOUNTS'] = '@Foo, bar;Foo invalid-handle-too-long'
            code = f"""
import importlib.util, json, sys
sys.path.insert(0, {str(SRC)!r})
spec = importlib.util.spec_from_file_location('x_watchlist_monitor_under_test', {str(SRC / 'x_watchlist_monitor.py')!r})
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
print(json.dumps({{
  'accounts': m.ACCOUNTS,
  'parsed_default_len': len(m.parse_watchlist_accounts('')),
}}, ensure_ascii=False))
"""
            out = subprocess.check_output([sys.executable, '-c', textwrap.dedent(code)], env=env, text=True)
            data = json.loads(out)
            self.assertEqual(data['accounts'], ['foo', 'bar'])
            self.assertGreater(data['parsed_default_len'], 1)

    def test_send_ready_items_archives_to_dashboard_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env['DASHBOARD_HOME'] = tmp
            code = f"""
import importlib.util, json, sys, time
from pathlib import Path
sys.path.insert(0, {str(SRC)!r})
spec = importlib.util.spec_from_file_location('x_watchlist_monitor_under_test', {str(SRC / 'x_watchlist_monitor.py')!r})
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
state = {{'seen_ids': {{}}, 'latest': {{}}}}
post = {{
  'post_id': 'unit-post-1',
  'time': '2026-06-23 10:00:00',
  'chinese_text': '测试推文正文',
  'conversation_type': 'original',
  'media': [],
}}
ok = m.send_ready_items('', '', state, [('测试账号', post, 'unit-post-1', 'tester')], {{}}, time.monotonic() + 30)
archive_files = sorted(Path({tmp!r}).glob('cron/output/x_watchlist_direct/*.md'))
archive_text = archive_files[0].read_text(encoding='utf-8') if archive_files else ''
print(json.dumps({{
  'ok': ok,
  'mode': state.get('last_delivery_mode'),
  'seen': state.get('seen_ids'),
  'archive_count': len(archive_files),
  'archive_has_dashboard_mode': '**Mode:** dashboard archive only' in archive_text,
  'archive_mentions_telegram': 'telegram' in archive_text.lower(),
}}, ensure_ascii=False))
"""
            out = subprocess.check_output([sys.executable, '-c', textwrap.dedent(code)], env=env, text=True)
            data = json.loads(out)
            self.assertTrue(data['ok'])
            self.assertEqual(data['mode'], 'dashboard_archive_only')
            self.assertEqual(data['seen'], {'tester': ['unit-post-1']})
            self.assertEqual(data['archive_count'], 1)
            self.assertTrue(data['archive_has_dashboard_mode'])
            self.assertFalse(data['archive_mentions_telegram'])

    def test_sent_missing_context_is_repaired_in_dashboard_db(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env['DASHBOARD_HOME'] = tmp
            code = f"""
import importlib.util, json, sqlite3, sys, time
from pathlib import Path
sys.path.insert(0, {str(SRC)!r})
spec = importlib.util.spec_from_file_location('x_watchlist_monitor_under_test', {str(SRC / 'x_watchlist_monitor.py')!r})
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
state = {{'seen_ids': {{}}, 'latest': {{}}}}
post = {{
  'post_id': 'reply-post-1',
  'time': '2026-06-23 10:00:00',
  'chinese_text': '这是一条短回复',
  'conversation_type': 'reply',
  'media': [],
}}
ok = m.send_ready_items('', '', state, [('投研荟', post, 'reply-post-1', 'freearkshaw')], {{}}, time.monotonic() + 30)
queued_before = len(state.get('sent_missing_context') or [])
def fake_repair(_base_url, _api_key, display_name, original_post, post_id, handle, timeout=10):
    repaired = dict(original_post)
    repaired.update({{
      'reply_to_author': '上文作者',
      'reply_to_text': '上文原文',
      'reply_to_chinese_text': '上文原文',
      'conversation_type': 'reply',
    }})
    return repaired
m.repair_one_context = fake_repair
repaired_count = m.repair_sent_missing_contexts('', '', state, time.monotonic() + 30, max_items=1)
con = m.push_history.connect()
try:
    row = con.execute(
        "SELECT content, metadata_json FROM dashboard_messages WHERE external_id = ?",
        ('reply-post-1',),
    ).fetchone()
finally:
    con.close()
content = row['content'] if row else ''
metadata = json.loads(row['metadata_json']) if row and row['metadata_json'] else {{}}
print(json.dumps({{
  'ok': ok,
  'queued_before': queued_before,
  'repaired_count': repaired_count,
  'queue_after': len(state.get('sent_missing_context') or []),
  'warning_present': '未取到被回复原推' in content,
  'has_parent': '原帖｜上文作者' in content and '上文原文' in content,
  'metadata_parent': metadata.get('post', {{}}).get('reply_to_author'),
}}, ensure_ascii=False))
"""
            out = subprocess.check_output([sys.executable, '-c', textwrap.dedent(code)], env=env, text=True)
            data = json.loads(out)
            self.assertTrue(data['ok'])
            self.assertEqual(data['queued_before'], 1)
            self.assertEqual(data['repaired_count'], 1)
            self.assertEqual(data['queue_after'], 0)
            self.assertFalse(data['warning_present'])
            self.assertTrue(data['has_parent'])
            self.assertEqual(data['metadata_parent'], '上文作者')

    def test_extract_x_media_normalizes_and_deduplicates_pbs_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env['DASHBOARD_HOME'] = tmp
            code = f"""
import importlib.util, json, sys
sys.path.insert(0, {str(SRC)!r})
spec = importlib.util.spec_from_file_location('x_watchlist_monitor_under_test', {str(SRC / 'x_watchlist_monitor.py')!r})
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
raw = '''
<meta property="og:image" content="https://pbs.twimg.com/media/ABC123.jpg:large">
<meta property="twitter:image" content="https://pbs.twimg.com/profile_images/1990755625417203712/9WXSzgqU_200x200.jpg">
<script type="application/ld+json">{{"@type":"SocialMediaPosting","image":"https://pbs.twimg.com/media/ABC123.jpg"}}</script>
relayRecords={{media_url_https:"https://pbs.twimg.com/media/DEF456.png:large"}}
'''
social = m.parse_social_posting(raw)
items = m.extract_x_media(raw, social=social)
print(json.dumps(items, ensure_ascii=False))
"""
            out = subprocess.check_output([sys.executable, '-c', textwrap.dedent(code)], env=env, text=True)
            items = json.loads(out)
            self.assertEqual([item['url'] for item in items], [
                'https://pbs.twimg.com/media/ABC123.jpg:large',
                'https://pbs.twimg.com/media/DEF456.png:large',
            ])
            self.assertTrue(all(item['type'] == 'image' for item in items))


if __name__ == '__main__':
    unittest.main()
