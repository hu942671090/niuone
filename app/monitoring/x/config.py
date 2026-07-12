"""Pure watchlist and token-limit configuration parsing."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable, Mapping


def parse_watchlist_accounts(value: str | None) -> list[str]:
    accounts: list[str] = []
    seen: set[str] = set()
    for raw in re.split(r"[,，;\s]+", str(value or "")):
        handle = raw.strip().lstrip("@").lower()
        if not handle or not re.fullmatch(r"[a-z0-9_]{1,15}", handle):
            continue
        if handle not in seen:
            seen.add(handle)
            accounts.append(handle)
    return accounts


def env_token_count(
    *names: str,
    default: int = 0,
    environ: Mapping[str, str],
) -> int:
    for name in names:
        raw = str(environ.get(name) or "").strip()
        if not raw:
            continue
        compact = raw.replace(",", "").replace("_", "").strip()
        match = re.fullmatch(r"(\d+(?:\.\d+)?)([kKmM]?)", compact)
        if not match:
            continue
        number = float(match.group(1))
        unit = match.group(2).lower()
        multiplier = 1_000_000 if unit == "m" else 1_000 if unit == "k" else 1
        value = int(number * multiplier)
        if value > 0:
            return value
    return default


def watchlist_accounts_from_state(
    path: Path,
    *,
    account_parser: Callable[[str | None], list[str]] = parse_watchlist_accounts,
) -> list[str]:
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(state, dict):
        return []
    accounts: list[str] = []
    seen: set[str] = set()

    def add(value: object) -> None:
        for handle in account_parser(str(value or "")):
            if handle not in seen:
                seen.add(handle)
                accounts.append(handle)

    for key in ("latest", "seen_ids"):
        section = state.get(key)
        if isinstance(section, dict):
            for handle in section:
                add(handle)
    sent_missing = state.get("sent_missing_context")
    if isinstance(sent_missing, list):
        for item in sent_missing:
            if isinstance(item, dict):
                add(item.get("handle"))
    return accounts
