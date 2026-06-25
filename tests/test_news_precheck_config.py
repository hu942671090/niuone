#!/usr/bin/env python3
import importlib.util
import os
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "app"
NEWS_ENV_KEYS = {
    "DASHBOARD_NEWS_MODEL",
    "DASHBOARD_NEWS_BASE_URL",
    "DASHBOARD_NEWS_API_KEY",
    "DASHBOARD_GROK_MODEL",
    "DASHBOARD_GROK_BASE_URL",
    "DASHBOARD_GROK_API_KEY",
}


def import_trader_with_env(updates: dict[str, str]):
    if str(SRC) not in sys.path:
        sys.path.insert(0, str(SRC))
    for key in NEWS_ENV_KEYS:
        os.environ.pop(key, None)
    os.environ.update(updates)
    spec = importlib.util.spec_from_file_location(
        f"niuniu_practice_trader_under_test_{len(sys.modules)}",
        SRC / "niuniu_practice_trader.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class NewsPrecheckConfigTests(unittest.TestCase):
    def setUp(self):
        self.original_env = {key: os.environ.get(key) for key in NEWS_ENV_KEYS}

    def tearDown(self):
        for key, value in self.original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_news_precheck_skips_when_unconfigured(self):
        module = import_trader_with_env({})

        self.assertIsNone(module.load_news_precheck_config())
        self.assertEqual(module.check_candidate_news_precheck([{"code": "000001", "name": "平安银行"}]), "")

    def test_news_precheck_requires_complete_config(self):
        module = import_trader_with_env({
            "DASHBOARD_NEWS_BASE_URL": "https://news.example/v1",
            "DASHBOARD_NEWS_MODEL": "search-model",
        })

        with self.assertRaisesRegex(RuntimeError, "DASHBOARD_NEWS_API_KEY"):
            module.load_news_precheck_config()

    def test_news_precheck_uses_independent_config(self):
        module = import_trader_with_env({
            "DASHBOARD_GROK_BASE_URL": "https://grok.example/v1",
            "DASHBOARD_GROK_API_KEY": "grok-secret",
            "DASHBOARD_GROK_MODEL": "grok-model",
            "DASHBOARD_NEWS_BASE_URL": "https://news.example/v1",
            "DASHBOARD_NEWS_API_KEY": "news-secret",
            "DASHBOARD_NEWS_MODEL": "search-model",
        })
        captured = {}

        def fake_api_call(base_url, api_key, payload, max_retries=3, timeout=60):
            captured.update({
                "base_url": base_url,
                "api_key": api_key,
                "payload": payload,
                "max_retries": max_retries,
                "timeout": timeout,
            })
            return {"choices": [{"message": {"content": "- 000001 平安银行：无重大消息（中性）"}}]}

        module.api_call_with_retry = fake_api_call
        result = module.check_candidate_news_precheck([{"code": "000001", "name": "平安银行"}])

        self.assertEqual(captured["base_url"], "https://news.example/v1")
        self.assertEqual(captured["api_key"], "news-secret")
        self.assertEqual(captured["payload"]["model"], "search-model")
        self.assertIn("【消息面预检（实时搜索）】", result)
        self.assertNotIn("Grok", result)


if __name__ == "__main__":
    unittest.main()
