"""Built-in notification channel validation, adapters, and factories."""
from __future__ import annotations

import base64
import hashlib
import hmac
import re
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Mapping

from .models import (
    DINGTALK_SECRET_ENV,
    DINGTALK_WEBHOOK_ENV,
    FEISHU_SECRET_ENV,
    FEISHU_WEBHOOK_ENV,
    TELEGRAM_CHAT_ID_ENV,
    TELEGRAM_TOKEN_ENV,
    WECOM_WEBHOOK_ENV,
    Notification,
    NotificationChannel,
    NotificationConfigError,
    NotificationDeliveryError,
    JsonTransport,
    Clock,
)


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
            raise NotificationDeliveryError(
                f"provider rejected request (code={_safe_provider_code(code)})"
            )


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
            raise NotificationDeliveryError(
                f"provider rejected request (code={_safe_provider_code(code)})"
            )


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
            raise NotificationDeliveryError(
                f"provider rejected request (code={_safe_provider_code(code)})"
            )


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


__all__ = ["FeishuChannel", "DingTalkChannel", "WeComChannel", "TelegramChannel"]
