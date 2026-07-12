#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'app'
COMPAT = SRC / 'compat'
ENTRYPOINTS = SRC / 'entrypoints'


class DashboardStandalonePathTests(unittest.TestCase):
    def test_direct_dashboard_start_loads_admin_password_from_private_env_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / 'dashboard.env'
            env_file.write_text("DASHBOARD_ADMIN_PASSWORD='管理员密码'\n", encoding='utf-8')
            env = os.environ.copy()
            env.pop('DASHBOARD_ADMIN_PASSWORD', None)
            env['DASHBOARD_HOME'] = tmp
            env['DASHBOARD_ENV_FILE'] = str(env_file)
            code = f"""
import importlib.util, json, sys
sys.path[:0] = [{str(ENTRYPOINTS)!r}, {str(COMPAT)!r}, {str(SRC)!r}]
spec = importlib.util.spec_from_file_location('dashboard_direct_start_test', {str(ENTRYPOINTS / 'niuone_dashboard.py')!r})
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
print(json.dumps({{
  'configured': bool(d.ADMIN_PASSWORD),
  'accepted': d.verify_admin_credential('管理员密码'),
  'wrong_rejected': not d.verify_admin_credential('错误密码'),
}}))
"""
            out = subprocess.check_output([sys.executable, '-c', code], env=env, text=True)
            data = json.loads(out)
            self.assertTrue(data['configured'])
            self.assertTrue(data['accepted'])
            self.assertTrue(data['wrong_rejected'])

    def test_dashboard_home_env_controls_runtime_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env['DASHBOARD_HOME'] = tmp
            code = f"""
import importlib.util, json, sys
from pathlib import Path
sys.path[:0] = [{str(ENTRYPOINTS)!r}, {str(COMPAT)!r}, {str(SRC)!r}]
spec = importlib.util.spec_from_file_location('dashboard_under_test', {str(ENTRYPOINTS / 'niuone_dashboard.py')!r})
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
import push_history
print(json.dumps({{
  'runtime_home': str(d.DASHBOARD_HOME),
  'stats_db': str(d.STATS_DB),
  'cron_output_dir': str(d.CRON_OUTPUT_DIR),
  'trader_script': str(d.TRADER_SCRIPT),
  'push_history_db': str(push_history.DB_PATH),
}}, ensure_ascii=False))
"""
            out = subprocess.check_output([sys.executable, '-c', code], env=env, text=True)
            data = json.loads(out)
            self.assertEqual(data['runtime_home'], tmp)
            self.assertTrue(data['stats_db'].startswith(tmp + os.sep))
            self.assertTrue(data['cron_output_dir'].startswith(tmp + os.sep))
            self.assertEqual(data['push_history_db'], str(Path(tmp) / 'push_history.db'))
            self.assertEqual(data['trader_script'], str(ENTRYPOINTS / 'niuniu_practice_trader.py'))

    def test_migrated_helper_modules_use_dashboard_home_and_app_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env['DASHBOARD_HOME'] = tmp
            code = f"""
import importlib.util, json, sys
from pathlib import Path
sys.path[:0] = [{str(COMPAT)!r}, {str(SRC)!r}]
mods = {{}}
for name in ['niuniu_practice_trader', 'niuniu_db', 'self_optimizer', 'multi_strategy_screen']:
    path = {str(COMPAT)!r} + '/' + name + '.py'
    spec = importlib.util.spec_from_file_location(name + '_under_test', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mods[name] = mod
print(json.dumps({{
  'stock_tools_script': str(mods['niuniu_practice_trader'].STOCK_TOOLS_SCRIPT),
  'portfolio_state': str(mods['niuniu_practice_trader'].STATE_FILE),
  'niuniu_db': str(mods['niuniu_db'].DB_PATH),
  'optimizer_state': str(mods['self_optimizer'].STATE_FILE),
  'b1_cache': str(mods['multi_strategy_screen'].B1_CACHE_FILE),
}}, ensure_ascii=False))
"""
            out = subprocess.check_output([sys.executable, '-c', code], env=env, text=True)
            data = json.loads(out)
            self.assertEqual(data['stock_tools_script'], str(ENTRYPOINTS / 'cn_stock_tools.py'))
            self.assertEqual(data['portfolio_state'], str(Path(tmp) / 'cron' / 'output' / 'niuniu_practice_portfolio.json'))
            self.assertEqual(data['niuniu_db'], str(Path(tmp) / 'niuniu.db'))
            self.assertEqual(data['optimizer_state'], str(Path(tmp) / 'cron' / 'output' / 'niuniu_practice_portfolio.json'))
            self.assertEqual(data['b1_cache'], str(Path(tmp) / 'cron' / 'output' / 'b1_screen_latest.json'))


if __name__ == '__main__':
    unittest.main()
