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


class DashboardStandalonePathTests(unittest.TestCase):
    def test_dashboard_home_env_makes_runtime_paths_independent_from_hermes(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env['DASHBOARD_HOME'] = tmp
            code = f"""
import importlib.util, json, sys
from pathlib import Path
sys.path.insert(0, {str(SRC)!r})
spec = importlib.util.spec_from_file_location('dashboard_under_test', {str(SRC / 'niuone_dashboard.py')!r})
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
import push_history
print(json.dumps({{
  'runtime_home': str(d.DASHBOARD_HOME),
  'state_db': str(d.STATE_DB),
  'auth_db': str(d.AUTH_DB),
  'cron_output_dir': str(d.CRON_OUTPUT_DIR),
  'trader_script': str(d.TRADER_SCRIPT),
  'push_history_db': str(push_history.DB_PATH),
}}, ensure_ascii=False))
"""
            out = subprocess.check_output([sys.executable, '-c', code], env=env, text=True)
            data = json.loads(out)
            self.assertEqual(data['runtime_home'], tmp)
            self.assertTrue(data['state_db'].startswith(tmp + os.sep))
            self.assertTrue(data['auth_db'].startswith(tmp + os.sep))
            self.assertTrue(data['cron_output_dir'].startswith(tmp + os.sep))
            self.assertEqual(data['push_history_db'], str(Path(tmp) / 'push_history.db'))
            self.assertEqual(data['trader_script'], str(SRC / 'niuniu_practice_trader.py'))

    def test_migrated_helper_modules_use_dashboard_home_and_app_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env['DASHBOARD_HOME'] = tmp
            code = f"""
import importlib.util, json, sys
from pathlib import Path
sys.path.insert(0, {str(SRC)!r})
mods = {{}}
for name in ['niuniu_practice_trader', 'niuniu_db', 'self_optimizer', 'multi_strategy_screen']:
    path = {str(SRC)!r} + '/' + name + '.py'
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
            self.assertEqual(data['stock_tools_script'], str(SRC / 'cn_stock_tools.py'))
            self.assertEqual(data['portfolio_state'], str(Path(tmp) / 'cron' / 'output' / 'niuniu_practice_portfolio.json'))
            self.assertEqual(data['niuniu_db'], str(Path(tmp) / 'niuniu.db'))
            self.assertEqual(data['optimizer_state'], str(Path(tmp) / 'cron' / 'output' / 'niuniu_practice_portfolio.json'))
            self.assertEqual(data['b1_cache'], str(Path(tmp) / 'cron' / 'output' / 'b1_screen_latest.json'))


if __name__ == '__main__':
    unittest.main()
