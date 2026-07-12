"""Pure record normalization and deduplication rules for push history."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


def stable_id(*parts: Any) -> str:
    raw = "\x1f".join(str(part or "") for part in parts)
    return hashlib.sha256(raw.encode("utf-8", "replace")).hexdigest()[:32]


def content_hash(content: str) -> str:
    return hashlib.sha256((content or "").encode("utf-8", "replace")).hexdigest()


def dumps(obj: Any) -> str | None:
    if obj is None:
        return None
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def message_dedupe_key(msg_id: Any, category: Any, content: Any, external_id: Any) -> str:
    content_text = str(content or "")
    category_text = str(category or "")
    external_text = str(external_id or "")
    if category_text == "us_ratings" and "买入评级" in content_text:
        normalized = " ".join(content_text.split())[:220]
        return f"us_ratings:{normalized}"
    if category_text == "x_monitor" and external_text:
        return f"x_monitor:{external_text}"
    return str(msg_id or "")


def x_metadata_priority(category: Any, metadata_json: Any) -> int:
    if str(category or "") != "x_monitor":
        return 0
    try:
        metadata = json.loads(str(metadata_json or "{}"))
    except Exception:
        metadata = {}
    post = metadata.get("post") if isinstance(metadata, dict) else None
    if not isinstance(post, dict):
        return 3
    if any(post.get(field) for field in ("media", "reply_to_media", "quoted_media")):
        return 0
    return 1


def x_row_is_better(
    candidate_metadata: Any,
    candidate_kind: Any,
    candidate_content: Any,
    candidate_timestamp: Any,
    candidate_id: Any,
    current_metadata: Any,
    current_kind: Any,
    current_content: Any,
    current_timestamp: Any,
    current_id: Any,
) -> int:
    """Return 1 when an X row is the preferred copy of the same post."""
    candidate_priority = x_metadata_priority("x_monitor", candidate_metadata)
    current_priority = x_metadata_priority("x_monitor", current_metadata)
    if candidate_priority != current_priority:
        return int(candidate_priority < current_priority)
    candidate_kind_priority = 0 if str(candidate_kind or "") == "cron_output" else 1
    current_kind_priority = 0 if str(current_kind or "") == "cron_output" else 1
    if candidate_kind_priority != current_kind_priority:
        return int(candidate_kind_priority < current_kind_priority)
    candidate_length = len(str(candidate_content or ""))
    current_length = len(str(current_content or ""))
    if candidate_length != current_length:
        return int(candidate_length > current_length)
    candidate_time = float(candidate_timestamp or 0)
    current_time = float(current_timestamp or 0)
    if candidate_time != current_time:
        return int(candidate_time > current_time)
    return int(str(candidate_id or "") > str(current_id or ""))


def row_to_dict(row: Mapping[str, Any]) -> dict[str, Any]:
    item = dict(row)
    item["matched"] = bool(item.get("matched"))
    for key in ("delivery_json", "metadata_json"):
        value = item.pop(key, None)
        out_key = key.replace("_json", "")
        if value:
            try:
                item[out_key] = json.loads(value)
            except Exception:
                item[out_key] = None
        else:
            item[out_key] = None
    item["time"] = item.get("time_text") or ""
    item["session_id"] = item.get("source_id") or ""
    return item
