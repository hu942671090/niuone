#!/usr/bin/env python3
import contextlib
import io
import os
import sys
import tempfile
import types
import unittest
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "app"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

_tmp_home = tempfile.TemporaryDirectory()
os.environ.setdefault("DASHBOARD_HOME", _tmp_home.name)

import niuniu_practice_trader as trader  # noqa: E402


@contextlib.contextmanager
def patched(**updates):
    originals = {name: getattr(trader, name) for name in updates}
    try:
        for name, value in updates.items():
            setattr(trader, name, value)
        yield
    finally:
        for name, value in originals.items():
            setattr(trader, name, value)


def sample_sell() -> dict:
    return {
        "time": "2026-07-11 10:00:00",
        "action": "SELL",
        "code": "600000",
        "name": "浦发银行",
        "shares": 100,
        "price": 10.5,
        "amount": 1050.0,
        "fee": 0.54,
        "pnl": 49.46,
        "pnl_pct": 4.95,
        "reason": "测试卖出",
    }


class TradeNotificationHookTests(unittest.TestCase):
    def test_auto_exit_notifies_only_after_state_is_saved(self):
        events = []
        executed = [sample_sell()]
        with patched(
            load_state=lambda: {"positions": {}, "trade_log": [], "cash": 1000.0},
            refresh_realtime_prices=lambda state: None,
            refresh_position_intraday=lambda state: None,
            _refresh_position_bbi=lambda state: None,
            check_auto_exits=lambda state, dt: executed,
            record_equity=lambda state: None,
            save_state=lambda state: events.append("save"),
            _notify_trade_executions_safely=lambda trades: events.append(("notify", trades)),
            enrich_portfolio=lambda state: {},
        ):
            result = trader.run_auto_exits_once(datetime(2026, 7, 11, 10, 0))

        self.assertEqual(result["executed"], executed)
        self.assertEqual(events, ["save", ("notify", executed)])

    def test_auto_exit_with_no_fill_does_not_notify(self):
        events = []
        with patched(
            load_state=lambda: {"positions": {}, "trade_log": [], "cash": 1000.0},
            refresh_realtime_prices=lambda state: None,
            refresh_position_intraday=lambda state: None,
            _refresh_position_bbi=lambda state: None,
            check_auto_exits=lambda state, dt: [],
            record_equity=lambda state: None,
            save_state=lambda state: events.append("save"),
            _notify_trade_executions_safely=lambda trades: events.append("notify"),
            enrich_portfolio=lambda state: {},
        ):
            trader.run_auto_exits_once(datetime(2026, 7, 11, 10, 0))

        self.assertEqual(events, ["save"])

    def test_deferred_fill_notifies_once_after_state_is_saved(self):
        events = []
        executed = [sample_sell()]
        state = {
            "cash": 1000.0,
            "positions": {},
            "trade_log": [],
            "decision_log": [],
            "pending_decisions": [{
                "id": "pending-1",
                "status": "pending",
                "due_at": "",
                "decision": {"summary": "延迟测试", "actions": []},
                "candidates": [],
                "schedule_slot": "2026-07-11 09:25",
            }],
        }
        with patched(
            is_a_share_execution_time=lambda now=None: (True, "连续竞价交易时段"),
            load_state=lambda: state,
            current_market_strategy_context=lambda: {},
            refine_overlimit_buy_actions=lambda *args, **kwargs: {},
            execute_actions=lambda *args, **kwargs: executed,
            enrich_portfolio=lambda value: {},
            _sync_decision_to_db=lambda entry: None,
            _sync_trades_to_db=lambda trades: None,
            _sync_positions_to_db=lambda value: None,
            record_equity=lambda value: None,
            save_state=lambda value: events.append("save"),
            _notify_trade_executions_safely=lambda trades: events.append(("notify", trades)),
        ):
            result = trader.execute_due_pending_decisions(datetime(2026, 7, 11, 13, 0))

        self.assertEqual(result["executed"], executed)
        self.assertEqual(events, ["save", ("notify", executed)])

    def test_model_fill_notifies_once_after_state_is_saved(self):
        events = []
        executed = [sample_sell()]
        state = {"cash": 1000.0, "positions": {}, "trade_log": [], "decision_log": [], "equity_history": []}
        decision = {"summary": "测试决策", "actions": [{"action": "SELL", "code": "600000", "shares": 100}]}
        market_context = {
            "tone_label": "中性",
            "max_open_positions": 6,
            "max_new_buys_per_decision": 2,
            "allow_new_buys": True,
        }
        with patched(
            load_state=lambda: state,
            market_strategy_context_for_b1=lambda payload: market_context,
            compact_market_strategy_context=lambda value: value,
            check_daily_loss_budget=lambda value: (False, 0.0),
            get_adaptive_params=lambda: {},
            is_a_share_execution_time=lambda now=None: (True, "连续竞价交易时段"),
            check_market_environment=lambda: {"bullish": True},
            check_market_sentiment=lambda: {"sentiment": "neutral", "detail": ""},
            enrich_portfolio=lambda value: {},
            call_model_decision=lambda *args, **kwargs: decision,
            refine_overlimit_buy_actions=lambda *args, **kwargs: {},
            execute_actions=lambda *args, **kwargs: executed,
            _sync_decision_to_db=lambda entry: None,
            _sync_trades_to_db=lambda trades: None,
            _sync_positions_to_db=lambda value: None,
            record_equity=lambda value: None,
            save_state=lambda value: events.append("save"),
            _notify_trade_executions_safely=lambda trades: events.append(("notify", trades)),
        ):
            result = trader.run_decision_after_b1({"generated_at": "2026-07-11 10:00:00"}, force=True)

        self.assertEqual(result["executed"], executed)
        self.assertEqual(events, ["save", ("notify", executed)])

    def test_dispatcher_exception_is_isolated_without_echoing_secret(self):
        original = sys.modules.get("notifications")
        secret = "private-webhook-token"
        sys.modules["notifications"] = types.SimpleNamespace(
            notify_trade_executions=lambda trades: (_ for _ in ()).throw(RuntimeError(secret))
        )
        stderr = io.StringIO()
        try:
            with contextlib.redirect_stderr(stderr):
                trader._notify_trade_executions_safely([sample_sell()])
        finally:
            if original is None:
                sys.modules.pop("notifications", None)
            else:
                sys.modules["notifications"] = original

        self.assertIn("RuntimeError", stderr.getvalue())
        self.assertNotIn(secret, stderr.getvalue())

    def test_failed_delivery_log_does_not_echo_channel_or_error_secrets(self):
        original = sys.modules.get("notifications")
        secret = "private-provider-error"
        sys.modules["notifications"] = types.SimpleNamespace(
            notify_trade_executions=lambda trades: [
                types.SimpleNamespace(channel="feishu", ok=False, error=secret),
                types.SimpleNamespace(channel=f"telegram-{secret}", ok=False, error=secret),
            ]
        )
        stderr = io.StringIO()
        try:
            with contextlib.redirect_stderr(stderr):
                trader._notify_trade_executions_safely([sample_sell()])
        finally:
            if original is None:
                sys.modules.pop("notifications", None)
            else:
                sys.modules["notifications"] = original

        self.assertIn("2 个渠道", stderr.getvalue())
        self.assertNotIn(secret, stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
