#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import sys
import unittest
import urllib.error
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

from dashboard.iwencai_connectivity import (  # noqa: E402
    IWENCAI_TEST_QUERY,
    iwencai_test_metadata,
    test_iwencai_connection as run_iwencai_connection_test,
)


class _Response:
    def __init__(self, payload: dict) -> None:
        self.body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, limit=-1) -> bytes:
        return self.body if limit < 0 else self.body[:limit]


class IwencaiConnectivityTests(unittest.TestCase):
    def test_metadata_targets_iwencai_settings_without_exposing_values(self):
        metadata = iwencai_test_metadata()

        self.assertEqual(metadata["id"], "iwencai")
        self.assertEqual(metadata["group_slug"], "iwencai")
        self.assertEqual(
            metadata["field_names"],
            ["IWENCAI_BASE_URL", "IWENCAI_API_KEY", "IWENCAI_TIMEOUT_SECONDS"],
        )

    def test_success_sends_one_small_read_only_query(self):
        calls = []

        def opener(request, timeout=0):
            calls.append((request, timeout))
            return _Response({"datas": [{"指数简称": "上证指数"}], "trace_id": "private-trace"})

        ticks = iter((20.0, 20.08))
        result = run_iwencai_connection_test(
            {
                "IWENCAI_BASE_URL": "https://iwencai.example/",
                "IWENCAI_API_KEY": "private-key",
                "IWENCAI_TIMEOUT_SECONDS": "60",
            },
            opener=opener,
            monotonic=lambda: next(ticks),
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["elapsed_ms"], 80)
        self.assertEqual(result["returned_count"], 1)
        self.assertNotIn("private", json.dumps(result, ensure_ascii=False))
        self.assertEqual(len(calls), 1)
        request, timeout = calls[0]
        self.assertEqual(request.full_url, "https://iwencai.example/v1/query2data")
        self.assertEqual(request.get_header("Authorization"), "Bearer private-key")
        self.assertEqual(timeout, 30)
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload, {
            "query": IWENCAI_TEST_QUERY,
            "page": "1",
            "limit": "1",
            "is_cache": "1",
            "expand_index": "false",
        })

    def test_missing_key_and_invalid_base_url_are_reported_without_network(self):
        calls = []
        missing = run_iwencai_connection_test(
            {"IWENCAI_BASE_URL": "https://openapi.iwencai.com"},
            opener=lambda *_args, **_kwargs: calls.append(True),
        )
        invalid = run_iwencai_connection_test(
            {
                "IWENCAI_BASE_URL": "http://openapi.iwencai.com",
                "IWENCAI_API_KEY": "private-key",
            },
            opener=lambda *_args, **_kwargs: calls.append(True),
        )

        self.assertFalse(missing["ok"])
        self.assertEqual(missing["error_code"], "api_key_missing")
        self.assertIn("API Key", missing["error"])
        self.assertFalse(invalid["ok"])
        self.assertEqual(invalid["error_code"], "invalid_base_url")
        self.assertIn("HTTPS", invalid["error"])
        self.assertEqual(calls, [])

    def test_http_and_response_failures_are_sanitized(self):
        values = {
            "IWENCAI_BASE_URL": "https://openapi.iwencai.com",
            "IWENCAI_API_KEY": "private-key",
        }

        def unauthorized(request, timeout=0):
            raise urllib.error.HTTPError(
                request.full_url,
                401,
                "private-key-in-reason",
                {},
                io.BytesIO(b'{"error":"private-key-in-body"}'),
            )

        denied = run_iwencai_connection_test(values, opener=unauthorized)
        invalid = run_iwencai_connection_test(
            values,
            opener=lambda _request, timeout=0: _Response({"message": "not datas"}),
        )

        self.assertEqual(denied["error_code"], "http_error")
        self.assertIn("HTTP 401", denied["error"])
        self.assertNotIn("private-key", json.dumps(denied, ensure_ascii=False))
        self.assertEqual(invalid["error_code"], "upstream_error")
        self.assertIn("返回格式", invalid["error"])


if __name__ == "__main__":
    unittest.main()
