#!/usr/bin/env python3
import sys
import types
import unittest
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
sys.path.insert(0, str(APP))

from market_data.news_precheck import (  # noqa: E402
    NewsPrecheckConfig,
    fetch_candidate_news_records,
    format_cached_news_records,
    parse_chat_completion_content,
    parse_candidate_news_record,
    request_candidate_news,
)
import market_data.news_precheck as news_precheck  # noqa: E402


class NewsPrecheckServiceTests(unittest.TestCase):
    def test_config_is_optional_but_rejects_partial_values(self):
        self.assertIsNone(NewsPrecheckConfig.from_mapping({}))
        with self.assertRaisesRegex(ValueError, "incomplete_news_precheck_config"):
            NewsPrecheckConfig.from_mapping({"DASHBOARD_NEWS_MODEL": "test-model"})

    def test_parser_requires_an_explicit_sentiment_label(self):
        positive = parse_candidate_news_record(
            {"code": "600000", "name": "测试"},
            "- 600000 测试：订单增长（利好）",
            fetched_at="2026-07-17T10:00:00+08:00",
        )
        ambiguous = parse_candidate_news_record(
            {"code": "600001", "name": "测试二"},
            "既有利好也有利空，需要继续核验",
            fetched_at="2026-07-17T10:00:00+08:00",
        )

        self.assertTrue(positive["available"])
        self.assertEqual(positive["tone"], "positive")
        self.assertFalse(ambiguous["available"])
        self.assertEqual(ambiguous["error"], "unclassified_response")

    def test_chat_parser_accepts_json_and_sse_responses(self):
        json_content = parse_chat_completion_content(
            '{"choices":[{"message":{"content":"消息稳定（中性）"}}]}'
        )
        sse_content = parse_chat_completion_content(
            'data: {"choices":[{"delta":{"content":"订单"}}]}\n\n'
            'data: {"choices":[{"delta":{"content":"增长（利好）"}}]}\n\n'
            "data: [DONE]\n\n"
        )

        self.assertEqual(json_content, "消息稳定（中性）")
        self.assertEqual(sse_content, "订单增长（利好）")

    def test_fetch_preserves_order_and_degrades_individual_failures(self):
        config = NewsPrecheckConfig(
            base_url="https://news.example/v1",
            api_key="secret",
            model="test-model",
            concurrency=2,
        )

        def requester(candidate, _config):
            if candidate["code"] == "600001":
                raise TimeoutError("timeout")
            return f"- {candidate['code']} {candidate['name']}：最近3天无明确重大消息（中性）"

        records = fetch_candidate_news_records(
            [
                {"code": "600000", "name": "甲"},
                {"code": "600001", "name": "乙"},
                {"code": "600002", "name": "丙"},
            ],
            config,
            requester=requester,
            now=datetime(2026, 7, 17, 10, 0, 0),
        )

        self.assertEqual([record["code"] for record in records], ["600000", "600001", "600002"])
        self.assertTrue(records[0]["available"])
        self.assertFalse(records[1]["available"])
        self.assertEqual(records[1]["error"], "request_TimeoutError")
        self.assertEqual(records[2]["tone"], "neutral")
        self.assertIn("扫描阶段缓存", format_cached_news_records(records))

    def test_request_uses_central_model_api_with_search_mode(self):
        config = NewsPrecheckConfig(
            base_url="https://news.example/v1",
            api_key="secret",
            model="gpt-5.6-sol",
            api_mode="auto",
            max_requests=1,
        )
        captured = {}
        original_request_model = news_precheck.request_model
        try:
            def fake_request(model_request, api_key, **kwargs):
                captured["request"] = model_request
                captured["api_key"] = api_key
                captured["kwargs"] = kwargs
                return types.SimpleNamespace(content="- 600000 测试：订单增长（利好）")

            news_precheck.request_model = fake_request
            content = request_candidate_news({"code": "600000", "name": "测试"}, config)
        finally:
            news_precheck.request_model = original_request_model

        self.assertIn("订单增长", content)
        self.assertEqual(captured["request"].api_mode, "responses")
        self.assertEqual(captured["request"].payload["tools"], [{"type": "web_search"}])
        self.assertNotIn("max_output_tokens", captured["request"].payload)
        self.assertEqual(captured["kwargs"]["timeout"], 45)


if __name__ == "__main__":
    unittest.main()
