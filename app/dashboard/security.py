"""Stateless security and request-parsing helpers for the dashboard."""

from __future__ import annotations

import hashlib
import ipaddress
from collections.abc import Callable, Iterable
from http import cookies


Network = ipaddress.IPv4Network | ipaddress.IPv6Network
NetworkParser = Callable[[str], Network | None]


def hash_token(token: str) -> str:
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()


def parse_request_cookies(header: str | None) -> dict[str, str]:
    jar = cookies.SimpleCookie()
    if header:
        try:
            jar.load(header)
        except cookies.CookieError:
            return {}
    return {key: morsel.value for key, morsel in jar.items()}


def is_truthy_header(value: str | None) -> bool:
    return bool(value and value.strip().lower() in {"1", "true", "yes", "on", "https"})


def parse_ip_network(value: str) -> Network | None:
    try:
        return ipaddress.ip_network(value.strip(), strict=False)
    except ValueError:
        return None


def is_trusted_proxy_ip(
    ip_text: str,
    trusted_proxy_cidrs: Iterable[str],
    *,
    parse_network: NetworkParser = parse_ip_network,
) -> bool:
    try:
        ip = ipaddress.ip_address(str(ip_text or "").strip())
    except ValueError:
        return False
    networks = [parse_network(item) for item in trusted_proxy_cidrs]
    return any(network is not None and ip in network for network in networks)


def first_forwarded_ip(*headers: str | None) -> str:
    for header in headers:
        for part in str(header or "").split(","):
            candidate = part.strip()
            if not candidate:
                continue
            try:
                ipaddress.ip_address(candidate)
            except ValueError:
                continue
            return candidate
    return ""


def clamp_limit(raw: str | None, *, default: int, maximum: int) -> int:
    try:
        value = int(raw) if raw else default
    except (TypeError, ValueError):
        value = default
    if value == 0:
        return 0
    return max(1, min(maximum, value))


def clamp_offset(raw: str | None, *, maximum: int) -> int:
    try:
        value = int(raw) if raw else 0
    except (TypeError, ValueError):
        value = 0
    return max(0, min(maximum, value))
