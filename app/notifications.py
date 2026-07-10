"""Extensible, best-effort notification delivery for NiuOne.

The module deliberately uses only the Python standard library.  Notification
failures are represented as :class:`DeliveryResult` values and never need to
escape into the trading path.  Each enabled channel is attempted at most once
and enabled channels are delivered concurrently.
"""
from __future__ import annotations

import base64
import concurrent.futures
import hashlib
import hmac
import json
import math
import os
import re
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping, Protocol


GLOBAL_ENABLED_ENV = "DASHBOARD_NOTIFICATION_ENABLED"
TIMEOUT_ENV = "DASHBOARD_NOTIFICATION_TIMEOUT_SECONDS"

FEISHU_ENABLED_ENV = "DASHBOARD_FEISHU_NOTIFICATION_ENABLED"
FEISHU_WEBHOOK_ENV = "DASHBOARD_FEISHU_WEBHOOK_URL"
FEISHU_SECRET_ENV = "DASHBOARD_FEISHU_SIGNING_SECRET"

DINGTALK_ENABLED_ENV = "DASHBOARD_DINGTALK_NOTIFICATION_ENABLED"
DINGTALK_WEBHOOK_ENV = "DASHBOARD_DINGTALK_WEBHOOK_URL"
DINGTALK_SECRET_ENV = "DASHBOARD_DINGTALK_SIGNING_SECRET"

WECOM_ENABLED_ENV = "DASHBOARD_WECOM_NOTIFICATION_ENABLED"
WECOM_WEBHOOK_ENV = "DASHBOARD_WECOM_WEBHOOK_URL"

TELEGRAM_ENABLED_ENV = "DASHBOARD_TELEGRAM_NOTIFICATION_ENABLED"
TELEGRAM_TOKEN_ENV = "DASHBOARD_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID_ENV = "DASHBOARD_TELEGRAM_CHAT_ID"

DEFAULT_TIMEOUT_SECONDS = 5.0
MIN_TIMEOUT_SECONDS = 1.0
MAX_TIMEOUT_SECONDS = 30.0
MAX_RESPONSE_BYTES = 64 * 1024
# Enterprise WeChat has the tightest plain-text allowance of the built-in
# channels.  A shared conservative cap keeps one rendering valid everywhere.
MAX_MESSAGE_BYTES = 1900
TRUTHY_VALUES = frozenset({"1", "true", "yes", "on"})


class NotificationConfigError(ValueError):
    """A notification channel is enabled but its configuration is invalid."""


class NotificationDeliveryError(RuntimeError):
    """A remote endpoint returned an unusable or unsuccessful response."""


@dataclass(frozen=True)
class Notification:
    """Channel-neutral notification content."""

    event_type: str
    title: str
    text: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def plain_text(self) -> str:
        title = str(self.title or "").strip()
        body = str(self.text or "").strip()
        rendered = "\n".join(part for part in (title, body) if part)
        return _truncate_utf8(rendered, MAX_MESSAGE_BYTES)


@dataclass(frozen=True)
class DeliveryResult:
    """Sanitized outcome for one channel delivery attempt."""

    channel: str
    ok: bool
    error: str = ""


JsonTransport = Callable[[str, Mapping[str, Any], float], Mapping[str, Any]]
Clock = Callable[[], float]


class NotificationChannel(Protocol):
    """Adapter contract used by the channel registry."""

    name: str

    def send(
        self,
        notification: Notification,
        *,
        timeout: float,
        transport: JsonTransport,
        clock: Clock,
    ) -> None:
        """Send once or raise a sanitized notification-specific exception."""


ChannelFactory = Callable[[Mapping[str, Any]], NotificationChannel]


@dataclass(frozen=True)
class _ChannelRegistration:
    name: str
    enabled_env: str
    factory: ChannelFactory


_CHANNEL_REGISTRY: dict[str, _ChannelRegistration] = {}
_REGISTRY_LOCK = threading.RLock()


def register_channel(
    name: str,
    factory: ChannelFactory,
    *,
    enabled_env: str,
    replace: bool = False,
) -> None:
    """Register a channel factory without coupling callers to its adapter.

    Factories are only called when ``enabled_env`` is truthy.  Registration
    order is also delivery-result order, even though network calls are made in
    parallel.
    """

    normalized_name = str(name or "").strip().lower()
    if not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", normalized_name):
        raise ValueError("invalid notification channel name")
    if not callable(factory):
        raise TypeError("notification channel factory must be callable")
    if not re.fullmatch(r"[A-Z_][A-Z0-9_]*", str(enabled_env or "")):
        raise ValueError("invalid notification channel enabled setting")
    with _REGISTRY_LOCK:
        if normalized_name in _CHANNEL_REGISTRY and not replace:
            raise ValueError(f"notification channel already registered: {normalized_name}")
        _CHANNEL_REGISTRY[normalized_name] = _ChannelRegistration(
            normalized_name,
            str(enabled_env),
            factory,
        )


def registered_channels() -> tuple[str, ...]:
    """Return a stable snapshot of registered channel names."""

    with _REGISTRY_LOCK:
        return tuple(_CHANNEL_REGISTRY)


def _env_text(env: Mapping[str, Any], name: str) -> str:
    value = env.get(name, "")
    return str(value if value is not None else "").strip()


def _enabled(env: Mapping[str, Any], name: str) -> bool:
    return _env_text(env, name).lower() in TRUTHY_VALUES


def _timeout_seconds(env: Mapping[str, Any]) -> float:
    raw = _env_text(env, TIMEOUT_ENV)
    if not raw:
        return DEFAULT_TIMEOUT_SECONDS
    try:
        timeout = float(raw)
    except (TypeError, ValueError) as exc:
        raise NotificationConfigError(f"{TIMEOUT_ENV} must be a number") from exc
    if not math.isfinite(timeout) or not MIN_TIMEOUT_SECONDS <= timeout <= MAX_TIMEOUT_SECONDS:
        raise NotificationConfigError(
            f"{TIMEOUT_ENV} must be between {int(MIN_TIMEOUT_SECONDS)} and {int(MAX_TIMEOUT_SECONDS)}"
        )
    return timeout


def _reject_controls(value: str, field_name: str) -> str:
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise NotificationConfigError(f"{field_name} contains control characters")
    return value


def _required_credential(env: Mapping[str, Any], name: str) -> str:
    raw = str(env.get(name, "") if env.get(name, "") is not None else "")
    _reject_controls(raw, name)
    value = raw.strip()
    if not value:
        raise NotificationConfigError(f"{name} is required")
    return value


def _optional_credential(env: Mapping[str, Any], name: str) -> str:
    raw = str(env.get(name, "") if env.get(name, "") is not None else "")
    _reject_controls(raw, name)
    return raw.strip()


def _split_https_url(raw_url: str, field_name: str) -> urllib.parse.SplitResult:
    _reject_controls(raw_url, field_name)
    try:
        parsed = urllib.parse.urlsplit(raw_url)
        port = parsed.port
    except (TypeError, ValueError) as exc:
        raise NotificationConfigError(f"{field_name} is not a valid URL") from exc
    if parsed.scheme.lower() != "https":
        raise NotificationConfigError(f"{field_name} must use HTTPS")
    if parsed.username is not None or parsed.password is not None:
        raise NotificationConfigError(f"{field_name} must not contain URL credentials")
    if port not in (None, 443):
        raise NotificationConfigError(f"{field_name} must use the default HTTPS port")
    if parsed.fragment:
        raise NotificationConfigError(f"{field_name} must not contain a fragment")
    if not parsed.hostname:
        raise NotificationConfigError(f"{field_name} must contain a host")
    return parsed


def _require_host(parsed: urllib.parse.SplitResult, allowed: set[str], field_name: str) -> None:
    host = str(parsed.hostname or "").lower()
    if host not in allowed:
        raise NotificationConfigError(f"{field_name} host is not allowed")


def _single_query_value(
    parsed: urllib.parse.SplitResult,
    key: str,
    field_name: str,
) -> str:
    query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    if set(query) != {key} or len(query.get(key, [])) != 1 or not query[key][0]:
        raise NotificationConfigError(f"{field_name} must contain one {key} value")
    return _reject_controls(query[key][0], field_name)


def _validate_feishu_webhook(url: str) -> str:
    parsed = _split_https_url(url, FEISHU_WEBHOOK_ENV)
    _require_host(parsed, {"open.feishu.cn", "open.larksuite.com"}, FEISHU_WEBHOOK_ENV)
    if parsed.query:
        raise NotificationConfigError(f"{FEISHU_WEBHOOK_ENV} must not contain a query")
    if not re.fullmatch(r"/open-apis/bot/v2/hook/[A-Za-z0-9_-]{8,}", parsed.path):
        raise NotificationConfigError(f"{FEISHU_WEBHOOK_ENV} path is invalid")
    return url


def _validate_dingtalk_webhook(url: str) -> str:
    parsed = _split_https_url(url, DINGTALK_WEBHOOK_ENV)
    _require_host(parsed, {"oapi.dingtalk.com"}, DINGTALK_WEBHOOK_ENV)
    if parsed.path != "/robot/send":
        raise NotificationConfigError(f"{DINGTALK_WEBHOOK_ENV} path is invalid")
    _single_query_value(parsed, "access_token", DINGTALK_WEBHOOK_ENV)
    return url


def _validate_wecom_webhook(url: str) -> str:
    parsed = _split_https_url(url, WECOM_WEBHOOK_ENV)
    _require_host(parsed, {"qyapi.weixin.qq.com"}, WECOM_WEBHOOK_ENV)
    if parsed.path != "/cgi-bin/webhook/send":
        raise NotificationConfigError(f"{WECOM_WEBHOOK_ENV} path is invalid")
    _single_query_value(parsed, "key", WECOM_WEBHOOK_ENV)
    return url


def _safe_provider_code(value: Any) -> str:
    code = str(value if value is not None else "unknown")
    return code if re.fullmatch(r"[A-Za-z0-9_.:-]{1,32}", code) else "unknown"


def _zero_code(value: Any) -> bool:
    return value == 0 or value == "0"


def _require_mapping_response(response: Mapping[str, Any] | Any) -> Mapping[str, Any]:
    if not isinstance(response, Mapping):
        raise NotificationDeliveryError("provider returned an invalid response")
    return response


@dataclass(frozen=True)
class FeishuChannel:
    webhook_url: str
    signing_secret: str = ""
    name: str = field(default="feishu", init=False)

    def send(
        self,
        notification: Notification,
        *,
        timeout: float,
        transport: JsonTransport,
        clock: Clock,
    ) -> None:
        payload: dict[str, Any] = {
            "msg_type": "text",
            "content": {"text": notification.plain_text()},
        }
        if self.signing_secret:
            timestamp = str(int(clock()))
            string_to_sign = f"{timestamp}\n{self.signing_secret}".encode("utf-8")
            digest = hmac.new(string_to_sign, digestmod=hashlib.sha256).digest()
            payload.update({
                "timestamp": timestamp,
                "sign": base64.b64encode(digest).decode("ascii"),
            })
        response = _require_mapping_response(transport(self.webhook_url, payload, timeout))
        code = response.get("code") if "code" in response else response.get("StatusCode")
        if not _zero_code(code):
            raise NotificationDeliveryError(f"provider rejected request (code={_safe_provider_code(code)})")


@dataclass(frozen=True)
class DingTalkChannel:
    webhook_url: str
    signing_secret: str = ""
    name: str = field(default="dingtalk", init=False)

    def _signed_url(self, clock: Clock) -> str:
        if not self.signing_secret:
            return self.webhook_url
        timestamp = str(int(clock() * 1000))
        string_to_sign = f"{timestamp}\n{self.signing_secret}".encode("utf-8")
        digest = hmac.new(
            self.signing_secret.encode("utf-8"),
            string_to_sign,
            digestmod=hashlib.sha256,
        ).digest()
        sign = base64.b64encode(digest).decode("ascii")
        parsed = urllib.parse.urlsplit(self.webhook_url)
        query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        query.extend((("timestamp", timestamp), ("sign", sign)))
        return urllib.parse.urlunsplit(parsed._replace(query=urllib.parse.urlencode(query)))

    def send(
        self,
        notification: Notification,
        *,
        timeout: float,
        transport: JsonTransport,
        clock: Clock,
    ) -> None:
        payload = {
            "msgtype": "text",
            "text": {"content": notification.plain_text()},
            "at": {"isAtAll": False},
        }
        response = _require_mapping_response(transport(self._signed_url(clock), payload, timeout))
        code = response.get("errcode")
        if not _zero_code(code):
            raise NotificationDeliveryError(f"provider rejected request (code={_safe_provider_code(code)})")


@dataclass(frozen=True)
class WeComChannel:
    webhook_url: str
    name: str = field(default="wecom", init=False)

    def send(
        self,
        notification: Notification,
        *,
        timeout: float,
        transport: JsonTransport,
        clock: Clock,
    ) -> None:
        del clock
        payload = {
            "msgtype": "text",
            "text": {"content": notification.plain_text()},
        }
        response = _require_mapping_response(transport(self.webhook_url, payload, timeout))
        code = response.get("errcode")
        if not _zero_code(code):
            raise NotificationDeliveryError(f"provider rejected request (code={_safe_provider_code(code)})")


@dataclass(frozen=True)
class TelegramChannel:
    bot_token: str
    chat_id: str
    name: str = field(default="telegram", init=False)

    @property
    def endpoint(self) -> str:
        return f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

    def send(
        self,
        notification: Notification,
        *,
        timeout: float,
        transport: JsonTransport,
        clock: Clock,
    ) -> None:
        del clock
        payload = {
            "chat_id": self.chat_id,
            "text": notification.plain_text(),
            "disable_web_page_preview": True,
        }
        response = _require_mapping_response(transport(self.endpoint, payload, timeout))
        if response.get("ok") is not True:
            raise NotificationDeliveryError("provider rejected request")


def _feishu_factory(env: Mapping[str, Any]) -> NotificationChannel:
    webhook = _validate_feishu_webhook(_required_credential(env, FEISHU_WEBHOOK_ENV))
    return FeishuChannel(webhook, _optional_credential(env, FEISHU_SECRET_ENV))


def _dingtalk_factory(env: Mapping[str, Any]) -> NotificationChannel:
    webhook = _validate_dingtalk_webhook(_required_credential(env, DINGTALK_WEBHOOK_ENV))
    return DingTalkChannel(webhook, _optional_credential(env, DINGTALK_SECRET_ENV))


def _wecom_factory(env: Mapping[str, Any]) -> NotificationChannel:
    webhook = _validate_wecom_webhook(_required_credential(env, WECOM_WEBHOOK_ENV))
    return WeComChannel(webhook)


def _telegram_factory(env: Mapping[str, Any]) -> NotificationChannel:
    token = _required_credential(env, TELEGRAM_TOKEN_ENV)
    if not re.fullmatch(r"\d+:[A-Za-z0-9_-]{20,}", token):
        raise NotificationConfigError(f"{TELEGRAM_TOKEN_ENV} format is invalid")
    chat_id = _required_credential(env, TELEGRAM_CHAT_ID_ENV)
    numeric_chat = bool(re.fullmatch(r"-?\d+", chat_id))
    named_chat = bool(re.fullmatch(r"@[A-Za-z][A-Za-z0-9_]{4,31}", chat_id))
    if not numeric_chat and not named_chat:
        raise NotificationConfigError(f"{TELEGRAM_CHAT_ID_ENV} format is invalid")
    return TelegramChannel(token, chat_id)


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


def _post_json(url: str, payload: Mapping[str, Any], timeout: float) -> Mapping[str, Any]:
    """POST JSON without following redirects and return a bounded JSON object."""

    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=encoded,
        method="POST",
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json",
            "User-Agent": "NiuOne/1.0",
        },
    )
    opener = urllib.request.build_opener(_NoRedirectHandler())
    with opener.open(request, timeout=timeout) as response:
        status = getattr(response, "status", None)
        if status is None and hasattr(response, "getcode"):
            status = response.getcode()
        if status is not None and not 200 <= int(status) < 300:
            raise NotificationDeliveryError(f"HTTP status {int(status)}")
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise NotificationDeliveryError("provider response is too large")
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NotificationDeliveryError("provider returned invalid JSON") from exc
    if not isinstance(decoded, Mapping):
        raise NotificationDeliveryError("provider returned an invalid response")
    return decoded


def _sensitive_values(env: Mapping[str, Any]) -> tuple[str, ...]:
    values: set[str] = set()
    sensitive_name = re.compile(r"(?:SECRET|TOKEN|WEBHOOK|PASSWORD|API_KEY|CREDENTIAL)")
    try:
        items = tuple(env.items())
    except Exception:
        return ()
    for name, raw_value in items:
        if not sensitive_name.search(str(name).upper()):
            continue
        value = str(raw_value if raw_value is not None else "").strip()
        if len(value) < 4:
            continue
        values.add(value)
        try:
            parsed = urllib.parse.urlsplit(value)
            if parsed.scheme and parsed.path:
                tail = parsed.path.rstrip("/").rsplit("/", 1)[-1]
                if len(tail) >= 4:
                    values.add(tail)
                for _key, query_value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True):
                    if len(query_value) >= 4:
                        values.add(query_value)
        except (TypeError, ValueError):
            pass
    return tuple(sorted(values, key=len, reverse=True))


def _redact_error_text(value: str, secrets: tuple[str, ...]) -> str:
    redacted = str(value or "")
    for secret in secrets:
        redacted = redacted.replace(secret, "[redacted]")
    return redacted[:240]


def _sanitized_error(exc: BaseException, secrets: tuple[str, ...] = ()) -> str:
    if isinstance(exc, (NotificationConfigError, NotificationDeliveryError)):
        return _redact_error_text(str(exc), secrets)
    if isinstance(exc, urllib.error.HTTPError):
        return f"HTTP error {int(exc.code)}"
    if isinstance(exc, urllib.error.URLError):
        reason = getattr(exc, "reason", None)
        if isinstance(reason, (TimeoutError, socket.timeout)):
            return "request timed out"
        return "network error"
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return "request timed out"
    # Never include arbitrary exception text: it may contain a webhook URL or
    # bot token supplied by a transport implementation.
    return type(exc).__name__ or "delivery error"


def _deliver_once(
    channel: NotificationChannel,
    notification: Notification,
    timeout: float,
    transport: JsonTransport,
    clock: Clock,
    secrets: tuple[str, ...],
) -> DeliveryResult:
    try:
        channel.send(notification, timeout=timeout, transport=transport, clock=clock)
        return DeliveryResult(channel=channel.name, ok=True)
    except Exception as exc:  # channel isolation is intentional
        return DeliveryResult(channel=channel.name, ok=False, error=_sanitized_error(exc, secrets))


def dispatch(
    notification: Notification,
    env: Mapping[str, Any] | None = None,
    *,
    transport: JsonTransport | None = None,
    clock: Clock | None = None,
) -> list[DeliveryResult]:
    """Deliver to every enabled channel once, concurrently and in stable order."""

    settings: Mapping[str, Any] = os.environ if env is None else env
    if not _enabled(settings, GLOBAL_ENABLED_ENV):
        return []
    with _REGISTRY_LOCK:
        registrations = tuple(_CHANNEL_REGISTRY.values())
    active = [registration for registration in registrations if _enabled(settings, registration.enabled_env)]
    if not active:
        return []
    secrets = _sensitive_values(settings)

    try:
        timeout = _timeout_seconds(settings)
    except Exception as exc:
        error = _sanitized_error(exc, secrets)
        return [DeliveryResult(item.name, False, error) for item in active]

    selected_transport = transport or _post_json
    selected_clock = clock or time.time
    slots: list[DeliveryResult | None] = [None] * len(active)
    ready: list[tuple[int, NotificationChannel]] = []
    for index, registration in enumerate(active):
        try:
            channel = registration.factory(settings)
            ready.append((index, channel))
        except Exception as exc:
            slots[index] = DeliveryResult(registration.name, False, _sanitized_error(exc, secrets))

    if ready:
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(ready))) as executor:
                futures = {
                    executor.submit(
                        _deliver_once,
                        channel,
                        notification,
                        timeout,
                        selected_transport,
                        selected_clock,
                        secrets,
                    ): index
                    for index, channel in ready
                }
                for future, index in futures.items():
                    try:
                        slots[index] = future.result()
                    except Exception as exc:  # guard executor/future failures too
                        slots[index] = DeliveryResult(active[index].name, False, _sanitized_error(exc, secrets))
        except Exception as exc:
            error = _sanitized_error(exc, secrets)
            for index, _channel in ready:
                if slots[index] is None:
                    slots[index] = DeliveryResult(active[index].name, False, error)

    return [
        result if result is not None else DeliveryResult(active[index].name, False, "delivery error")
        for index, result in enumerate(slots)
    ]


def dispatch_to_channel(
    notification: Notification,
    channel_name: str,
    env: Mapping[str, Any] | None = None,
    *,
    transport: JsonTransport | None = None,
    clock: Clock | None = None,
) -> DeliveryResult:
    """Deliver one notification to one registered channel for configuration tests.

    This deliberately ignores the global and per-channel enabled flags.  It is
    intended for an explicit, authenticated test action where the caller has
    already selected exactly one channel.
    """

    normalized_name = str(channel_name or "").strip().lower()
    with _REGISTRY_LOCK:
        registration = _CHANNEL_REGISTRY.get(normalized_name)
    if registration is None:
        return DeliveryResult(normalized_name or "notification", False, "unknown notification channel")

    settings: Mapping[str, Any] = os.environ if env is None else env
    secrets = _sensitive_values(settings)
    try:
        timeout = _timeout_seconds(settings)
        channel = registration.factory(settings)
    except Exception as exc:
        return DeliveryResult(registration.name, False, _sanitized_error(exc, secrets))

    return _deliver_once(
        channel,
        notification,
        timeout,
        transport or _post_json,
        clock or time.time,
        secrets,
    )


def _clean_trade_text(value: Any, max_chars: int = 120) -> str:
    text = re.sub(r"[\x00-\x1f\x7f]+", " ", str(value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= max_chars else text[: max(1, max_chars - 1)].rstrip() + "…"


def _finite_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _money(value: Any) -> str:
    number = _finite_float(value)
    return f"¥{number:,.2f}" if number is not None else "-"


def _price(value: Any) -> str:
    number = _finite_float(value)
    return f"¥{number:,.3f}" if number is not None else "-"


def _percentage(value: Any) -> str:
    number = _finite_float(value)
    return f"{number:.2f}%" if number is not None else "-"


def _trade_notification(trades: Iterable[Mapping[str, Any]]) -> Notification | None:
    normalized: list[Mapping[str, Any]] = []
    for trade in trades:
        if not isinstance(trade, Mapping):
            continue
        if str(trade.get("action") or "").strip().upper() in {"BUY", "SELL"}:
            normalized.append(trade)
    if not normalized:
        return None

    lines = ["模拟成交，非实盘"]
    actions: list[str] = []
    for index, trade in enumerate(normalized, 1):
        action = str(trade.get("action") or "").strip().upper()
        actions.append(action)
        label = "买入" if action == "BUY" else "卖出"
        name = _clean_trade_text(trade.get("name"), 32) or "未知股票"
        code = _clean_trade_text(trade.get("code"), 24) or "-"
        try:
            shares = int(float(trade.get("shares") or 0))
        except (TypeError, ValueError, OverflowError):
            shares = 0
        details = [
            f"{index}. {label} {name}({code})",
            f"{shares}股 @ {_price(trade.get('price'))}",
            f"金额 {_money(trade.get('amount'))}",
        ]
        fee = _finite_float(trade.get("fee"))
        if fee is not None:
            details.append(f"费用 {_money(fee)}")
        if action == "BUY":
            position_pct = trade.get("position_after_trade_pct")
            if _finite_float(position_pct) is not None:
                details.append(f"成交后单票仓位 {_percentage(position_pct)}")
        else:
            pnl = _finite_float(trade.get("pnl"))
            pnl_pct = _finite_float(trade.get("pnl_pct"))
            if pnl is not None:
                pnl_text = f"盈亏 {_money(pnl)}"
                if pnl_pct is not None:
                    pnl_text += f" / {_percentage(pnl_pct)}"
                details.append(pnl_text)
        trade_time = _clean_trade_text(trade.get("time"), 32)
        if trade_time:
            details.append(f"时间 {trade_time}")
        lines.append("｜".join(details))

        strategy = _clean_trade_text(
            trade.get("exit_rule") if action == "SELL" else trade.get("buy_strategy"),
            60,
        )
        reason = _clean_trade_text(trade.get("reason"), 100)
        annotations = []
        if strategy:
            annotations.append(f"策略 {strategy}")
        if reason:
            annotations.append(f"原因 {reason}")
        if annotations:
            lines.append("   " + "；".join(annotations))

    count = len(normalized)
    return Notification(
        event_type="trade.executed",
        title=f"牛牛1号模拟成交（{count}笔）",
        text="\n".join(lines),
        metadata={"trade_count": count, "actions": tuple(actions)},
    )


def _truncate_utf8(value: str, max_bytes: int) -> str:
    encoded = str(value or "").encode("utf-8")
    if len(encoded) <= max_bytes:
        return str(value or "")
    suffix = "\n…内容已截断".encode("utf-8")
    prefix = encoded[: max(0, max_bytes - len(suffix))]
    while prefix:
        try:
            text = prefix.decode("utf-8")
            return text.rstrip() + suffix.decode("utf-8")
        except UnicodeDecodeError:
            prefix = prefix[:-1]
    return suffix.decode("utf-8")


def notify_trade_executions(
    trades: Iterable[Mapping[str, Any]],
    env: Mapping[str, Any] | None = None,
    *,
    transport: JsonTransport | None = None,
    clock: Clock | None = None,
) -> list[DeliveryResult]:
    """Format a persisted BUY/SELL batch and dispatch it to configured channels."""

    try:
        notification = _trade_notification(trades)
    except Exception as exc:
        return [DeliveryResult("notification", False, _sanitized_error(exc))]
    if notification is None:
        return []
    try:
        return dispatch(notification, env, transport=transport, clock=clock)
    except Exception as exc:  # final safety boundary for callers in trading code
        return [DeliveryResult("notification", False, _sanitized_error(exc))]


register_channel("feishu", _feishu_factory, enabled_env=FEISHU_ENABLED_ENV)
register_channel("dingtalk", _dingtalk_factory, enabled_env=DINGTALK_ENABLED_ENV)
register_channel("wecom", _wecom_factory, enabled_env=WECOM_ENABLED_ENV)
register_channel("telegram", _telegram_factory, enabled_env=TELEGRAM_ENABLED_ENV)
